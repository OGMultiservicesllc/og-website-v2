"""Consular Processing: case data, the visa-applicant setup step, and the case dashboard.

A Consular Processing case is the customer's immigrant-visa matter. It is NOT a USCIS case: it may LINK to the underlying petition (an I-130 that
lives in its own Family Petition case) without moving it, and it does not have to come from an I-130 at all. Every immigrant visa applicant is a REAL
Person with their own DS-260 application in the case (never one giant DS-260 for a family).

Sensitive case credentials (NVC case number, invoice ID): stored as case data, masked wherever they are shown, never placed in a URL, a log line,
an activity event or public metadata. CEAC passwords are never asked for or stored.
"""

import re
from datetime import date, datetime

from app import cases as case_svc
from app import persons as pers
from app.case_types import type_title
from app.extensions import db
from app.models import (ApplicationRole, Case, CasePerson, ConsularCaseData, Ds260Application, DocumentRequirement, FormSubmission, Person)

CASE_TYPE = "consular_processing"
_SAFE = re.compile(r"^[A-Za-z0-9\- ]{0,40}$")

PETITION_TYPES = [
    ("i130", "Family petition (Form I-130)", "Petición familiar (Formulario I-130)"),
    ("i140", "Employment-based petition (Form I-140)", "Petición basada en empleo (Formulario I-140)"),
    ("dv", "Diversity Visa", "Visa de Diversidad"),
    ("other", "Other / not sure", "Otra / no estoy seguro(a)"),
]

ERRORS = {
    "invalid": ("Please choose one of the options.", "Elige una de las opciones."),
    "names": ("Enter the first and last name of the new person.", "Escribe el nombre y el apellido de la persona nueva."),
    "duplicate": ("That person already has a DS-260 in this case, or an unfinished one.", "Esa persona ya tiene un DS-260 en este caso, o uno sin terminar."),
    "principal": ("This case already has a principal applicant. Choose “Derivative applicant” for this person.", "Este caso ya tiene un solicitante principal. Elige “Solicitante derivado” para esta persona."),
    "incompatible": ("This application cannot be added to that kind of case.", "Esta solicitud no se puede agregar a ese tipo de caso."),
    "credentials": ("Use only letters, numbers, spaces and hyphens (up to 40 characters) for the NVC case number and invoice ID.", "Usa solo letras, números, espacios y guiones (hasta 40 caracteres) para el número de caso del NVC y el ID de factura."),
    "date": ("Enter the priority date as a valid date, or leave it blank.", "Escribe la fecha de prioridad como una fecha válida, o déjala en blanco."),
}


def mask(value):
    value = str(value or "")
    return ("•" * max(len(value) - 3, 0) + value[-3:]) if len(value) > 3 else ("•" * len(value))


def case_data(case, create=False):
    row = case.consular_data
    if row is None and create:
        row = ConsularCaseData(case_id=case.id)
        db.session.add(row)
        db.session.flush()
        db.session.refresh(case)
    return row


def _date(text):
    text = (text or "").strip()
    if not text:
        return None, True
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date(), True
    except ValueError:
        return None, False


def ds260_row(submission, role=None, source=None):
    """The DS-260 bookkeeping row (created on demand, tied to the current source snapshot)."""
    row = submission.ds260
    if row is None:
        from app.ds260_source import current_source

        row = Ds260Application(submission_id=submission.id, source_id=(source or current_source()).id, applicant_role=role or "principal")
        db.session.add(row)
        db.session.commit()
        db.session.refresh(submission)
    elif role and row.applicant_role != role:
        row.applicant_role = role
        db.session.commit()
    return row


def applicants(case):
    """[{submission, person, role, ...}] the visa applicants of a consular case (one DS-260 each), principal first."""
    out = []
    for s in case.applications:
        if s.form.source_form_name != "DS-260" or s.status == "archived":
            continue
        role_row = ApplicationRole.query.filter_by(submission_id=s.id, role_key="visa_applicant").first()
        row = s.ds260
        out.append({"submission": s, "person": role_row.person if role_row else None, "role": (row.applicant_role if row else "principal"), "row": row})
    out.sort(key=lambda a: (a["role"] != "principal", a["submission"].id))
    return out


def form_progress(submission):
    from app.intake_engine import progress_for

    if submission.is_complete:
        return 100
    p = progress_for(submission.form, submission)
    return max(0, min(99, p["percent"]))


def document_counts(case, person):
    reqs = [r for r in DocumentRequirement.query.filter_by(case_id=case.id, person_id=person.id).all() if r.withdrawn_at is None] if person is not None else []
    got = sum(1 for r in reqs if r.status in ("uploaded", "under_review", "accepted"))
    return got, len(reqs)


def dashboard(case, lang="en"):
    """Per-applicant progress (independent for each) and the friendly case-level steps. Workflow completion only: never a legal conclusion."""
    en = lang == "en"
    apps = []
    for a in applicants(case):
        s = a["submission"]
        got, total = document_counts(case, a["person"])
        row = a["row"]
        apps.append({"submission": s, "person": a["person"], "role": a["role"], "role_label": ("Principal applicant" if a["role"] == "principal" else "Derivative applicant") if en else ("Solicitante principal" if a["role"] == "principal" else "Solicitante derivado"),
                     "percent": form_progress(s), "started": bool(s.values), "docs_got": got, "docs_total": total, "row": row})
    all_done = bool(apps) and all(x["submission"].is_complete for x in apps)
    any_started = any(x["started"] for x in apps)
    ready = bool(apps) and all(x["row"] is not None and x["row"].ready_for_ceac_at for x in apps)
    i864 = [s for s in case.applications if s.form.source_form_name == "I-864" and s.status != "archived"]
    civil_open = [r for r in case.requirements if r.withdrawn_at is None and r.category in ("birth_certificate", "marriage_certificate", "divorce_death_certificate", "other", "passport") and r.status in ("needed", "requested", "needs_replacement")]
    civil_any = [r for r in case.requirements if r.withdrawn_at is None]
    reviewed = bool(apps) and all(x["submission"].is_complete and x["submission"].status in ("in_review", "completed", "ready_for_ceac") for x in apps)
    ceac_submitted = bool(apps) and all(x["row"] is not None and x["row"].ceac_status == "submitted" for x in apps)

    def state(done, started):
        return "complete" if done else ("progress" if started else "todo")

    steps = [
        {"key": "setup", "label": "Case setup" if en else "Configuración del caso", "state": "complete" if apps else "todo"},
        {"key": "applicants", "label": "Applicant information" if en else "Información de los solicitantes", "state": state(all_done, any_started)},
        {"key": "sponsorship", "label": "Financial sponsorship" if en else "Patrocinio económico", "state": state(bool(i864) and all(s.is_complete for s in i864), bool(i864))},
        {"key": "documents", "label": "Civil documents" if en else "Documentos civiles", "state": ("attention" if civil_open else ("complete" if civil_any else "todo"))},
        {"key": "review", "label": "OG review" if en else "Revisión de OG", "state": state(reviewed, all_done)},
        {"key": "ceac", "label": "CEAC preparation" if en else "Preparación para CEAC", "state": "complete" if ceac_submitted else ("ready" if ready else "todo")},
    ]
    return {"applicants": apps, "steps": steps}


# ------------------------------------------------------------------ setup: WHO is the applicant, WHICH consular case
def _persons(student):
    return Person.query.filter_by(customer_id=student.id).order_by(Person.is_self.desc(), Person.id).all()


def person_choices(student, lang, none_label=None, self_label=True):
    en = lang == "en"
    out = []
    persons = _persons(student)
    if self_label and not any(p.is_self for p in persons):
        out.append({"value": "self", "label": f"{student.name} ({'you' if en else 'tú'})", "note": ""})
    for p in persons:
        roles = sorted({r.role_key for cp in p.case_people for r in ApplicationRole.query.filter_by(person_id=cp.id).all()})
        from app.case_types import role_label

        note = ", ".join(role_label(r, lang) for r in roles)
        out.append({"value": "self" if p.is_self else f"person:{p.id}", "label": (f"{p.full_name} ({'you' if en else 'tú'})" if p.is_self else p.full_name), "note": note})
    if none_label:
        out.insert(0, {"value": "none", "label": none_label, "note": ""})
    out.append({"value": "new", "label": "Add another person" if en else "Agregar otra persona", "note": ""})
    return out


def i130_choices(student, lang):
    en = lang == "en"
    out = []
    for s in FormSubmission.query.filter_by(student_id=student.id).order_by(FormSubmission.id.desc()).all():
        if s.form.source_form_name != "I-130" or s.status == "archived" or s.case_id is None:
            continue
        ben = ApplicationRole.query.filter_by(submission_id=s.id, role_key="beneficiary").first()
        out.append({"value": f"sub:{s.id}", "label": f"Form I-130 · {s.code}" + (f" · {ben.person.full_name}" if ben else ""),
                    "note": ("Submitted" if en else "Enviada") if s.is_complete else ("Draft" if en else "Borrador")})
    return out


def options(student, submission, lang):
    en = lang == "en"
    cases = []
    for case in Case.query.filter(Case.customer_id == student.id, Case.case_type == CASE_TYPE, Case.status != "closed").order_by(Case.id.desc()).all():
        cd = case.consular_data
        cases.append({"case": case, "applicants": ", ".join((a["person"].full_name if a["person"] else "?") for a in applicants(case)),
                      "post": (cd.post if cd else ""), "nvc": mask(cd.nvc_case_number) if cd and cd.nvc_case_number else ""})
    petitioners = person_choices(student, lang, none_label=("An employer, an organization, or I do not know yet" if en else "Un empleador, una organización, o todavía no lo sé"))
    petitioners.insert(1, {"value": "applicant", "label": "The applicant filed the petition themself" if en else "El propio solicitante presentó la petición", "note": ""})
    return {"persons": person_choices(student, lang), "petitioners": petitioners,
            "cases": cases, "i130": i130_choices(student, lang), "petition_types": [(k, e if en else s) for k, e, s in PETITION_TYPES]}


def _resolve(student, choice, given, family):
    """(owner Person | None (new person), error). Person ids from the form are ALWAYS re-read as the customer's own."""
    choice = (choice or "").strip()
    if choice == "self":
        return pers.self_person(student), None
    if choice.startswith("person:"):
        try:
            owner = Person.query.filter_by(id=int(choice[7:]), customer_id=student.id).first()
        except ValueError:
            owner = None
        return (owner, None) if owner is not None else (None, "invalid")
    if choice == "new":
        given, family = (given or "").strip()[:120], (family or "").strip()[:120]
        return (None, "names") if not (given and family) else (None, None)
    return None, "invalid"


def _duplicate(submission, case, owner):
    if owner is None:
        return False
    ids = [cp.id for cp in owner.case_people]
    if not ids:
        return False
    rows = (ApplicationRole.query.join(FormSubmission, FormSubmission.id == ApplicationRole.submission_id)
            .filter(ApplicationRole.person_id.in_(ids), ApplicationRole.role_key == "visa_applicant", FormSubmission.form_id == submission.form_id,
                    FormSubmission.id != submission.id, FormSubmission.status != "archived"))
    for r in rows.all():
        if not r.submission.is_complete or (case is not None and r.case_id == case.id):
            return True
    return False


def apply(student, submission, form, lang):
    """`form` = request.form. Attach the draft to a consular case with its visa applicant (a real Person). Returns (ok, error_key)."""
    from app.case_setup import needs_setup

    if not needs_setup(submission) or submission.student_id != student.id:
        return False, "invalid"
    role = form.get("role", "principal")
    if role not in ("principal", "derivative"):
        return False, "invalid"
    owner, err = _resolve(student, form.get("applicant"), form.get("ap_given"), form.get("ap_family"))
    if err:
        return False, err
    case, choice = None, form.get("case", "")
    if choice.startswith("case:"):
        try:
            case = case_svc.owned_case(student, int(choice[5:]))
        except ValueError:
            case = None
        if case is None or case.status == "closed":
            return False, "invalid"
        if case.case_type != CASE_TYPE:
            return False, "incompatible"
    elif choice != "new":
        return False, "invalid"
    if _duplicate(submission, case, owner):
        return False, "duplicate"
    if case is not None and role == "principal" and any(a["role"] == "principal" and a["submission"].id != submission.id and a["submission"].status != "archived" for a in applicants(case)):
        return False, "principal"

    data = {}
    if case is None:
        nvc, inv = (form.get("nvc_case_number") or "").strip(), (form.get("invoice_id") or "").strip()
        if not (_SAFE.match(nvc) and _SAFE.match(inv)):
            return False, "credentials"
        prio, ok = _date(form.get("priority_date"))
        if not ok:
            return False, "date"
        data = {"nvc_case_number": nvc or None, "invoice_id": inv or None, "priority_date": prio, "post": (form.get("post") or "").strip()[:120] or None,
                "visa_class": (form.get("visa_class") or "").strip().upper()[:20] or None, "country": (form.get("country") or "").strip()[:80] or None,
                "petition_type": form.get("petition_type") if form.get("petition_type") in {k for k, _e, _s in PETITION_TYPES} else None}
    pet_owner, pet_new, pet_none = None, False, False
    pchoice = form.get("petitioner", "none")
    if case is None or (case.consular_data is None or case.consular_data.petitioner_person_id is None):
        if pchoice == "none":
            pet_none = True
        elif pchoice == "applicant":  # the applicant filed the petition themself (a self-petition, a Diversity Visa)
            pass
        else:
            pet_owner, perr = _resolve(student, pchoice, form.get("pt_given"), form.get("pt_family"))
            if perr:
                return False, perr
            pet_new = pet_owner is None
    under = None
    if form.get("underlying", "none").startswith("sub:"):
        try:
            under = FormSubmission.query.filter_by(id=int(form["underlying"][4:]), student_id=student.id).first()
        except ValueError:
            under = None
        if under is None or under.form.source_form_name != "I-130":
            return False, "invalid"

    if case is None:
        case = case_svc.create_case(student, CASE_TYPE, None, origin="auto", lang=lang)
        cd = case_data(case, create=True)
        for k, v in data.items():
            setattr(cd, k, v)
    cd = case_data(case, create=True)

    def cp_for(owner_, given, family, rel="other"):
        if owner_ is not None:
            return pers.case_person_for(case, owner_)
        return case_svc.add_person(case, given, family, rel, actor="customer", actor_id=student.id)

    ap_cp = cp_for(owner, form.get("ap_given"), form.get("ap_family"))
    db.session.add(ApplicationRole(case_id=case.id, submission_id=submission.id, person_id=ap_cp.id, role_key="visa_applicant"))
    db.session.add(ApplicationRole(case_id=case.id, submission_id=submission.id, person_id=ap_cp.id, role_key="principal_applicant" if role == "principal" else "derivative_applicant"))
    if cd.petitioner_person_id is None and not pet_none:
        if pchoice == "applicant":
            pet_cp = ap_cp
        else:
            pet_cp = cp_for(pet_owner, form.get("pt_given"), form.get("pt_family"), "petitioner")
        cd.petitioner_person_id = pers.owner_of(pet_cp).id
    if cd.petitioner_person_id is not None:
        pet_person = db.session.get(Person, cd.petitioner_person_id)
        pet_cp = pers.case_person_for(case, pet_person, relationship_key="petitioner")
        if not ApplicationRole.query.filter_by(submission_id=submission.id, person_id=pet_cp.id, role_key="petitioner").first():
            db.session.add(ApplicationRole(case_id=case.id, submission_id=submission.id, person_id=pet_cp.id, role_key="petitioner"))
    if under is not None and cd.underlying_submission_id is None:
        cd.underlying_submission_id = under.id
    from app.intake_shared import _set

    fields = {f.internal_name: f for f in submission.form.all_fields}
    _set(submission.form, submission, fields, "ds_role", role)  # before the case attach: the role mapping reads it
    db.session.commit()
    case_svc.attach_application(case, submission, actor="customer", actor_id=student.id)
    ds260_row(submission, role="principal" if role == "principal" else "derivative")
    from app.shared_blocks import prime_blocks

    prime_blocks(submission)
    return True, None
