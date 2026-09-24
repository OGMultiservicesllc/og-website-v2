"""Choosing WHO an application is for, and WHICH case it belongs to, before its first question (Form I-485).

The applicant is a REAL Person of the customer (the customer, someone they already have in another case, or someone new). The case
only says where the application lives: a form can only enter a case type it is compatible with (`case_types.compatible_case_types`,
data-driven), so an I-485 is never put inside a Naturalization case; its person data comes from the shared Person instead.

Nothing is attached blindly:
  * only the signed-in customer's own, open, COMPATIBLE cases are offered (ids in the URL are never trusted);
  * a person from another case is linked EXPLICITLY (chosen from the customer's own people, never matched by name);
  * the same person cannot get a second active application of this form (same case, or another unfinished draft);
  * a person whose only role anywhere is petitioner is not offered as the applicant.
Nothing here reads or infers eligibility.
"""

from app import cases as case_svc
from app import persons as pers
from app.case_types import compatible_case_types, config_for, is_compatible, role_label, type_title
from app.extensions import db
from app.models import ApplicationRole, Case, CasePerson, FormSubmission, Person

ERRORS = {
    "invalid": ("Please choose one of the options.", "Elige una de las opciones."),
    "names": ("Enter the first and last name of the person this application is for.", "Escribe el nombre y el apellido de la persona para quien es esta solicitud."),
    "duplicate": ("That person already has an application for this form in this case, or an unfinished one.", "Esa persona ya tiene una solicitud de este formulario en este caso, o una sin terminar."),
    "petitioner": ("That person is the petitioner in your case, not the person applying. Choose the person the application is for.", "Esa persona es el peticionario en tu caso, no quien solicita. Elige a la persona para quien es la solicitud."),
    "incompatible": ("This application cannot be added to that kind of case.", "Esta solicitud no se puede agregar a ese tipo de caso."),
}


def needs_setup(submission):
    cfg = config_for(submission.form) if submission is not None else None
    return bool(cfg and cfg.get("case_setup") and submission.case_id is None and submission.student_id)


def _roles(person):
    ids = [cp.id for cp in person.case_people]
    if not ids:
        return set()
    return {r.role_key for r in ApplicationRole.query.filter(ApplicationRole.person_id.in_(ids)).all()}


def _problem(submission, case, person):
    """Why `person` (a real Person) cannot be this application's applicant (None when fine)."""
    roles = _roles(person)
    if roles and roles <= {"petitioner"}:
        return "petitioner"
    ids = [cp.id for cp in person.case_people]
    if ids:
        rows = (ApplicationRole.query.join(FormSubmission, FormSubmission.id == ApplicationRole.submission_id)
                .filter(ApplicationRole.person_id.in_(ids), ApplicationRole.role_key == "applicant", FormSubmission.form_id == submission.form_id,
                        FormSubmission.id != submission.id, FormSubmission.status != "archived"))
        for r in rows.all():
            if not r.submission.is_complete or (case is not None and r.case_id == case.id and not (config_for(submission.form) or {}).get("allow_repeat_in_case")):
                return "duplicate"
    return None


def _describe(person, lang, submission, case):
    en = lang == "en"
    roles = sorted(_roles(person))
    sub = ", ".join(role_label(r, lang) for r in roles) if roles else ("Known person" if en else "Persona conocida")
    problem = _problem(submission, case, person)
    label = f"{person.full_name} ({'you' if en else 'tú'})" if person.is_self else person.full_name
    return label, sub, problem


def options(student, submission, lang):
    """[{case, applications, choices:[{value, label, sub, disabled, reason}]}] the customer may pick from (compatible cases only)."""
    en = lang == "en"
    form_name = submission.form.source_form_name
    persons = Person.query.filter_by(customer_id=student.id).order_by(Person.is_self.desc(), Person.id).all()
    out = []
    cases = Case.query.filter(Case.customer_id == student.id, Case.status != "closed").order_by(Case.id.desc()).all()
    for case in cases:
        if not is_compatible(form_name, case.case_type):
            continue
        in_case = {cp.person_id: cp for cp in case.people if cp.person_id}
        choices = []
        for person in persons:
            cp = in_case.get(person.id)
            label, sub, problem = _describe(person, lang, submission, case)
            if cp is not None:
                value = f"case:{case.id}:" + ("self" if person.is_self else f"person:{cp.id}")
            elif person.is_self:
                value = f"case:{case.id}:self"
            else:
                value = f"case:{case.id}:link:{person.id}"
                sub = ("Already in your other cases — will be linked" if en else "Ya está en tus otros casos — se vinculará")
            choices.append({"value": value, "label": label, "sub": sub, "disabled": problem is not None, "reason": ERRORS[problem][0 if en else 1] if problem else ""})
        choices.append({"value": f"case:{case.id}:new", "label": "Someone else (a new person)" if en else "Otra persona (nueva)", "sub": "", "disabled": False, "reason": ""})
        apps = [f"{'Form ' + (s.form.source_form_name or s.form.name_admin)} · {s.code}" for s in case.applications if s.id != submission.id]
        out.append({"case": case, "choices": choices, "applications": apps})
    return out


def new_case_choices(student, submission, lang):
    en = lang == "en"
    out = []
    for person in Person.query.filter_by(customer_id=student.id).order_by(Person.is_self.desc(), Person.id).all():
        label, sub, problem = _describe(person, lang, submission, None)
        out.append({"value": "new:self" if person.is_self else f"new:link:{person.id}", "label": label, "sub": "" if person.is_self else sub,
                    "disabled": problem is not None, "reason": ERRORS[problem][0 if en else 1] if problem else ""})
    if not any(c["value"] == "new:self" for c in out):
        out.insert(0, {"value": "new:self", "label": f"{student.name} ({'you' if en else 'tú'})", "sub": "", "disabled": False, "reason": ""})
    out.append({"value": "new:new", "label": "Someone else (a new person)" if en else "Otra persona (nueva)", "sub": "", "disabled": False, "reason": ""})
    return out


def apply(student, submission, choice, given, family, lang):
    """Attach the draft to a compatible case with its applicant. Returns (ok, error_key)."""
    if not needs_setup(submission) or submission.student_id != student.id:
        return False, "invalid"
    parts = (choice or "").split(":")
    case, who = None, None
    if parts[:1] == ["new"] and len(parts) >= 2 and parts[1] in ("self", "new", "link"):
        who = parts[1:]
    elif parts[:1] == ["case"] and len(parts) >= 3:
        try:
            case = case_svc.owned_case(student, int(parts[1]))
        except ValueError:
            case = None
        if case is None or case.status == "closed":
            return False, "invalid"
        who = parts[2:]
    else:
        return False, "invalid"
    form_name = submission.form.source_form_name
    if case is not None and not is_compatible(form_name, case.case_type):
        return False, "incompatible"

    given, family = (given or "").strip()[:120], (family or "").strip()[:120]
    owner = None  # the real Person, when the applicant is someone the customer already has
    if who == ["new"]:
        if not (given and family):
            return False, "names"
    elif who == ["self"]:
        owner = pers.self_person(student)
    elif len(who) == 2 and who[0] == "person" and case is not None:
        try:
            cp = CasePerson.query.filter_by(id=int(who[1]), case_id=case.id).first()
        except ValueError:
            cp = None
        if cp is None or cp.is_customer:
            return False, "invalid"
        owner = pers.owner_of(cp)
    elif len(who) == 2 and who[0] == "link":
        try:
            owner = Person.query.filter_by(id=int(who[1]), customer_id=student.id).first()  # only the customer's own people
        except ValueError:
            owner = None
        if owner is None or owner.is_self:
            return False, "invalid"
    else:
        return False, "invalid"
    if owner is not None:
        problem = _problem(submission, case, owner)
        if problem:
            return False, problem

    if case is None:
        case = case_svc.create_case(student, compatible_case_types(form_name)[0], None, origin="auto", lang=lang)
    if owner is not None:
        cp = pers.case_person_for(case, owner)
    else:
        cp = case_svc.add_person(case, given, family, "other", actor="customer", actor_id=student.id)
    db.session.add(ApplicationRole(case_id=case.id, submission_id=submission.id, person_id=cp.id, role_key="applicant"))
    db.session.commit()
    case_svc.attach_application(case, submission, actor="customer", actor_id=student.id)
    from app.shared_blocks import prime_blocks

    prime_blocks(submission)
    return True, None


# ================================================================== Form I-864: WHO is the sponsor, WHO is the principal immigrant, WHICH case
ERRORS.update({
    "same": ("The sponsor and the principal immigrant must be two different people.", "El patrocinador y el inmigrante principal deben ser dos personas distintas."),
    "dup864": ("There is already an affidavit for this sponsor and principal immigrant in this case, or an unfinished one.", "Ya existe un affidavit para este patrocinador e inmigrante principal en este caso, o uno sin terminar."),
})


def setup_kind(submission):
    cfg = config_for(submission.form) if submission is not None else None
    return (cfg or {}).get("setup") or "applicant"


def _person_line(person, lang):
    """(label, note) for a Person of the customer: who they are and where else the customer already has them."""
    en = lang == "en"
    roles = sorted(_roles(person))
    role_txt = ", ".join(role_label(r, lang) for r in roles)
    cases = sorted({cp.case.case_number for cp in person.case_people if cp.case is not None and cp.case.status != "closed"})
    note = " · ".join(x for x in (role_txt, (("In " if en else "En ") + ", ".join(cases)) if cases else "") if x)
    return (f"{person.full_name} ({'you' if en else 'tú'})" if person.is_self else person.full_name), note


def person_choices_i864(student, lang):
    en = lang == "en"
    out = []
    persons = Person.query.filter_by(customer_id=student.id).order_by(Person.is_self.desc(), Person.id).all()
    if not any(p.is_self for p in persons):
        out.append({"value": "self", "label": f"{student.name} ({'you' if en else 'tú'})", "note": ""})
    for p in persons:
        label, note = _person_line(p, lang)
        out.append({"value": "self" if p.is_self else f"person:{p.id}", "label": label, "note": note})
    out.append({"value": "new", "label": "Add another person" if en else "Agregar otra persona", "note": ""})
    return out


_PAIR_DEFAULT = {
    "first": {"role": "sponsor", "title": {"en": "WHO IS THE SPONSOR?", "es": "¿QUIÉN ES EL PATROCINADOR?"},
              "subtitle": {"en": "The person signing the affidavit of support and promising financial support.", "es": "La persona que firma el affidavit de patrocinio económico y se compromete a dar el apoyo."}},
    "second": {"role": "principal_immigrant", "title": {"en": "WHO IS THE PRINCIPAL IMMIGRANT?", "es": "¿QUIÉN ES EL INMIGRANTE PRINCIPAL?"},
               "subtitle": {"en": "The person immigrating who is being sponsored.", "es": "La persona que inmigra y es patrocinada."}},
    "heading": {"en": "Who is sponsoring, and who is being sponsored?", "es": "¿Quién patrocina y a quién se patrocina?"},
    "intro": {"en": "Pick real people you already have in your cases so we do not ask for their information again. Nobody gets a login by being listed.",
              "es": "Elige a personas reales que ya tienes en tus casos para no pedir su información otra vez. Nadie recibe un acceso por aparecer aquí."},
    "dup": {"en": "There is already an affidavit for this sponsor and principal immigrant in this case, or an unfinished one.", "es": "Ya existe un affidavit para este patrocinador e inmigrante principal en este caso, o uno sin terminar."},
    "same": {"en": "The sponsor and the principal immigrant must be two different people.", "es": "El patrocinador y el inmigrante principal deben ser dos personas distintas."},
}


def pair_cfg(form):
    return (config_for(form) or {}).get("setup_pair") or _PAIR_DEFAULT


def options_i864(student, submission, lang):
    form_name = submission.form.source_form_name
    cases = []
    for case in Case.query.filter(Case.customer_id == student.id, Case.status != "closed").order_by(Case.id.desc()).all():
        if not is_compatible(form_name, case.case_type):
            continue
        apps = [f"{'Form ' + (s.form.source_form_name or s.form.name_admin)} · {s.code}" for s in case.applications if s.id != submission.id]
        cases.append({"case": case, "applications": apps, "people": ", ".join(cp.full_name for cp in case.people)})
    pair = pair_cfg(submission.form)
    return {"cases": cases, "sponsor": person_choices_i864(student, lang), "principal": person_choices_i864(student, lang),
            "titles": {"first": pair["first"]["title"][lang], "second": pair["second"]["title"][lang], "first_sub": pair["first"]["subtitle"][lang], "second_sub": pair["second"]["subtitle"][lang],
                       "heading": pair["heading"][lang], "intro": pair["intro"][lang]}}


def _resolve_person(student, choice, given, family):
    """(owner Person | None for a NEW person, error key | None). Person ids come from the form but are ALWAYS re-read as the customer's own."""
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


def _duplicate_864(submission, case, sponsor, principal):
    if sponsor is None or principal is None:
        return False
    q = FormSubmission.query.filter(FormSubmission.form_id == submission.form_id, FormSubmission.id != submission.id, FormSubmission.student_id == submission.student_id,
                                    FormSubmission.status != "archived", FormSubmission.case_id.isnot(None))
    for other in q.all():
        pair = pair_cfg(submission.form)
        if case is not None and other.case_id != case.id and other.is_complete:
            continue
        if case is None and other.is_complete and pair.get("completed_elsewhere_ok"):  # a finished petition does not block a fresh matter for the same pair
            continue
        sp = case_svc.role_person(other, pair["first"]["role"])
        pr = case_svc.role_person(other, pair["second"]["role"])
        if sp is not None and pr is not None and pers.owner_of(sp).id == sponsor.id and pers.owner_of(pr).id == principal.id:
            return True
    return False


def apply_i864(student, submission, form, lang):
    """`form` = request.form. Attach the draft to a compatible case with a sponsor and a principal immigrant (real Persons)."""
    if not needs_setup(submission) or submission.student_id != student.id:
        return False, "invalid"
    sp_owner, err = _resolve_person(student, form.get("sponsor"), form.get("sp_given"), form.get("sp_family"))
    if err:
        return False, err
    pi_owner, err = _resolve_person(student, form.get("principal"), form.get("pi_given"), form.get("pi_family"))
    if err:
        return False, err
    if sp_owner is not None and pi_owner is not None and sp_owner.id == pi_owner.id:
        same = pair_cfg(submission.form).get("same") or _PAIR_DEFAULT["same"]
        ERRORS["same"] = (same["en"], same["es"])
        return False, "same"
    case = None
    choice = form.get("case", "")
    if choice.startswith("case:"):
        try:
            case = case_svc.owned_case(student, int(choice[5:]))
        except ValueError:
            case = None
        if case is None or case.status == "closed":
            return False, "invalid"
        if not is_compatible(submission.form.source_form_name, case.case_type):
            return False, "incompatible"
    elif choice != "new":
        return False, "invalid"
    if _duplicate_864(submission, case, sp_owner, pi_owner):
        ERRORS["dup864"] = (pair_cfg(submission.form)["dup"]["en"], pair_cfg(submission.form)["dup"]["es"])
        return False, "dup864"
    if case is None:
        case = case_svc.create_case(student, compatible_case_types(submission.form.source_form_name)[0], None, origin="auto", lang=lang)

    def cp_for(owner, given, family):
        if owner is not None:
            return pers.case_person_for(case, owner)
        return case_svc.add_person(case, given, family, "other", actor="customer", actor_id=student.id)

    sp_cp = cp_for(sp_owner, form.get("sp_given"), form.get("sp_family"))
    pi_cp = cp_for(pi_owner, form.get("pi_given"), form.get("pi_family"))
    pair = pair_cfg(submission.form)
    db.session.add(ApplicationRole(case_id=case.id, submission_id=submission.id, person_id=sp_cp.id, role_key=pair["first"]["role"]))
    db.session.add(ApplicationRole(case_id=case.id, submission_id=submission.id, person_id=pi_cp.id, role_key=pair["second"]["role"]))
    db.session.commit()
    case_svc.attach_application(case, submission, actor="customer", actor_id=student.id)
    from app.shared_blocks import prime_blocks

    prime_blocks(submission)
    return True, None
