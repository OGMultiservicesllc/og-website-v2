"""ITIN Application case (Tax & ITIN Services): setup, applicants, dashboard, status.

One ITIN CASE holds several people; every person who needs an ITIN gets their OWN W-7 application (a FormSubmission of the W-7 intake) in that case. The case also holds the
tax context (tax year, income type) and OG's package / IRS tracking, so a future Tax Return case can reuse the people, documents and this basic tax information.

Scope is OG's OPERATIONAL scope, not an IRS eligibility decision: the online intake only accepts people physically in the U.S., with a U.S. mailing address, whose ITIN is
tied to a U.S. federal income tax return prepared by OG. Anything else gets the "contact OG" message and no case is created.
"""

import html
import secrets
from datetime import date, datetime

from app import cases as case_svc
from app import persons as pers
from app.case_types import type_title
from app.extensions import db
from app.forms_engine import generate_submission_code
from app.models import ApplicationRole, Case, FormSubmission, ItinCaseData, ItinDocTrack, Person, W7Application
from app.models.itin import ITIN_STAGES, STAGE_EN, STAGE_ES

html_escape = html.escape

CASE_TYPE = "itin_application"
MAX_DEPENDENTS = 6
KIND_LABEL = {"primary": ("Primary taxpayer", "Contribuyente principal"), "spouse": ("Spouse", "Cónyuge"), "dependent": ("Dependent", "Dependiente")}
ERRORS = {
    "scope": ("This type of ITIN request is not currently handled through OG's online ITIN intake. Please contact OG Multiservices for assistance.",
              "Este tipo de solicitud de ITIN no se maneja actualmente a través del formulario en línea de ITIN de OG. Comunícate con OG Multiservices para recibir ayuda."),
    "nobody": ("Choose who needs an ITIN.", "Elige quién necesita un ITIN."),
    "names": ("Enter the first and last name of each person you add.", "Escribe el nombre y el apellido de cada persona que agregues."),
    "dob": ("Enter a valid date of birth for each child or dependent (it tells OG which documents apply).", "Escribe una fecha de nacimiento válida para cada hijo o dependiente (le dice a OG qué documentos aplican)."),
    "invalid": ("Please choose one of the options.", "Elige una de las opciones."),
    "duplicate": ("The same person is listed twice.", "La misma persona aparece dos veces."),
    "year": ("Choose the tax year.", "Elige el año fiscal."),
}


def tax_year_options(today=None):
    y = (today or date.today()).year
    return list(range(y - 1, y - 5, -1))


def case_data(case, create=False):
    row = case.itin_data
    if row is None and create:
        row = ItinCaseData(case_id=case.id)
        db.session.add(row)
        db.session.flush()
        db.session.refresh(case)
    return row


def w7_row(submission, kind=None):
    row = submission.w7
    if row is None:
        cd = submission.case.itin_data if submission.case is not None else None
        row = W7Application(submission_id=submission.id, applicant_kind=kind or "primary", application_type=(cd.request_kind if cd else "new"))
        db.session.add(row)
        db.session.commit()
        db.session.refresh(submission)
    return row


def applicants(case):
    out = []
    for s in case.applications:
        if s.form.source_form_name != "W-7" or s.status == "archived":
            continue
        role = ApplicationRole.query.filter_by(submission_id=s.id, role_key="itin_applicant").first()
        out.append({"submission": s, "person": role.person if role else None, "kind": (s.w7.applicant_kind if s.w7 else "primary"), "row": s.w7})
    order = {"primary": 0, "spouse": 1, "dependent": 2}
    out.sort(key=lambda a: (order.get(a["kind"], 9), a["submission"].id))
    return out


def kind_label(kind, lang="en"):
    en, es = KIND_LABEL.get(kind, KIND_LABEL["primary"])
    return en if lang == "en" else es


# ------------------------------------------------------------------ setup
def person_choices(student, lang):
    en = lang == "en"
    out = []
    for p in Person.query.filter_by(customer_id=student.id, is_self=False).order_by(Person.id).all():  # the customer is chosen with the “Me” box, never as a spouse or dependent
        out.append({"value": f"person:{p.id}", "label": (f"{p.full_name} ({'you' if en else 'tú'})" if p.is_self else p.full_name), "self": p.is_self})
    return out


def setup_options(student, lang):
    return {"persons": person_choices(student, lang), "years": tax_year_options(), "default_year": tax_year_options()[0], "max_dependents": MAX_DEPENDENTS,
            "self_name": student.name}


def _owner_or_new(student, pick, given, family):
    """(Person | None(new), (given, family) | None, error). A picked id is re-read as THIS customer's own Person; never trusted from the form."""
    pick = (pick or "").strip()
    if pick.startswith("person:"):
        try:
            owner = Person.query.filter_by(id=int(pick[7:]), customer_id=student.id).first()
        except ValueError:
            owner = None
        return (owner, None, None) if owner is not None else (None, None, "invalid")
    given, family = (given or "").strip()[:120], (family or "").strip()[:120]
    if not (given and family):
        return None, None, "names"
    return None, (given, family), None


def _parse_date(text):
    try:
        d = datetime.strptime((text or "").strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    return d if d <= date.today() and d.year > 1900 else None


def _new_submission(form, student, lang, service, sample):
    sub = FormSubmission(form_id=form.id, code=generate_submission_code(), resume_token=secrets.token_urlsafe(32), language=lang, student_id=student.id,
                         service_id=service.id if service else None, current_page=1, display_name=student.name, display_email=student.email,
                         form_version=form.version, source_edition_snapshot=form.source_edition)
    db.session.add(sub)
    db.session.commit()
    return sub


def parse_setup(student, data):
    """(scope, applicants, error). `applicants` = [{kind, owner|None, names|None, dob|None, rel}] in order: me, spouse, dependents."""
    scope = {"in_us": data.get("in_us"), "us_address": data.get("us_address"), "request_kind": data.get("request_kind"), "preparing_return": data.get("preparing_return"),
             "taxpayer_us_status": data.get("taxpayer_us_status") if data.get("taxpayer_us_status") in ("yes", "no", "unsure") else "unsure"}
    if scope["in_us"] != "yes" or scope["us_address"] != "yes" or scope["preparing_return"] not in ("yes", "not_sure"):
        return scope, [], "scope"
    if scope["request_kind"] not in ("new", "renew", "unsure"):
        return scope, [], "invalid"
    try:
        scope["tax_year"] = int(data.get("tax_year", ""))
    except ValueError:
        return scope, [], "year"
    if scope["tax_year"] not in tax_year_options():
        return scope, [], "year"
    people = []
    if data.get("who_me"):
        people.append({"kind": "primary", "owner": pers.self_person(student), "names": None, "dob": None, "rel": "self"})
    if data.get("who_spouse"):
        owner, names, err = _owner_or_new(student, data.get("sp_pick"), data.get("sp_given"), data.get("sp_family"))
        if err:
            return scope, [], err
        people.append({"kind": "spouse", "owner": owner, "names": names, "dob": None, "rel": "spouse"})
    for i in range(1, MAX_DEPENDENTS + 1):
        if not data.get(f"dep{i}_on"):
            continue
        owner, names, err = _owner_or_new(student, data.get(f"dep{i}_pick"), data.get(f"dep{i}_given"), data.get(f"dep{i}_family"))
        if err:
            return scope, [], err
        dob = _parse_date(data.get(f"dep{i}_dob"))
        if dob is None:
            known = pers.get_fact(owner, "date_of_birth") if owner is not None else None
            if known is None:
                return scope, [], "dob"
        people.append({"kind": "dependent", "owner": owner, "names": names, "dob": dob, "rel": "child" if data.get(f"dep{i}_rel", "child") == "child" else "other"})
    if not people:
        return scope, [], "nobody"
    ids = [p["owner"].id for p in people if p["owner"] is not None]
    if len(ids) != len(set(ids)):
        return scope, [], "duplicate"
    return scope, people, None


def apply_setup(student, submission, data, lang):
    """Create the ITIN case, its people and one W-7 application per ITIN applicant. The customer's open draft becomes the first applicant's application.
    Returns (ok, error_key)."""
    from app import w7_docs
    from app.case_setup import needs_setup
    from app.intake_shared import _set

    if not needs_setup(submission) or submission.student_id != student.id:
        return False, "invalid"
    scope, people, err = parse_setup(student, data)
    if err:
        return False, err
    form = submission.form
    fields = {f.internal_name: f for f in form.all_fields}
    case = case_svc.create_case(student, CASE_TYPE, f"ITIN & Tax Return — {scope['tax_year']}" if lang == "en" else f"ITIN y declaración de impuestos — {scope['tax_year']}", origin="auto", lang=lang)
    cd = case_data(case, create=True)
    cd.tax_year, cd.request_kind, cd.preparing_return, cd.taxpayer_us_status = scope["tax_year"], scope["request_kind"], scope["preparing_return"], scope["taxpayer_us_status"]
    db.session.commit()
    taxpayer_cp = case_svc.ensure_customer_person(case)
    subs = []
    for i, p in enumerate(people):
        sub = submission if i == 0 else _new_submission(form, student, lang, submission.service, submission)
        if p["owner"] is not None:
            cp = pers.case_person_for(case, p["owner"], relationship_key=p["rel"])
        else:
            cp = case_svc.add_person(case, p["names"][0], p["names"][1], p["rel"], actor="customer", actor_id=student.id)
        db.session.commit()
        _set(form, sub, fields, "w_kind", p["kind"])
        owner_person = pers.owner_of(cp)
        if owner_person.given_name and owner_person.family_name:
            _set(form, sub, fields, "a_given", owner_person.given_name)
            _set(form, sub, fields, "a_family", owner_person.family_name)
        if p["dob"] is not None:
            _set(form, sub, fields, "a_dob", p["dob"].isoformat())
        db.session.commit()
        db.session.add(ApplicationRole(case_id=case.id, submission_id=sub.id, person_id=cp.id, role_key="itin_applicant"))
        db.session.add(ApplicationRole(case_id=case.id, submission_id=sub.id, person_id=cp.id, role_key={"primary": "primary_taxpayer", "spouse": "spouse_applicant", "dependent": "dependent_applicant"}[p["kind"]]))
        if p["kind"] != "primary" and taxpayer_cp.id != cp.id:
            db.session.add(ApplicationRole(case_id=case.id, submission_id=sub.id, person_id=taxpayer_cp.id, role_key="taxpayer"))
        db.session.commit()
        case_svc.attach_application(case, sub, actor="customer", actor_id=student.id)
        db.session.add(W7Application(submission_id=sub.id, applicant_kind=p["kind"], application_type=scope["request_kind"]))
        db.session.commit()
        db.session.refresh(sub)
        subs.append(sub)
    from app.shared_blocks import prime_blocks

    from app import w7_calc

    for sub in subs:
        prime_blocks(sub)
        w7_calc.write(form, sub, fields)
        w7_docs.sync(sub)
    db.session.commit()
    log_case_event(student.id, "itin_case_started", case, {"applicants": len(subs)})
    return True, None


def log_case_event(student_id, event, case, meta=None, entity=None, actor="customer", actor_id=None):
    """Activity entry for an ITIN case. Metadata never carries a passport number, SSN/ITIN, W-2 value or any other identifier."""
    from app.activity import log_event

    if student_id:
        log_event(student_id, event, actor=actor, actor_id=actor_id, entity=entity or ("case", case.id), meta=dict({"case": case.case_number}, **(meta or {})), case_id=case.id)


# ------------------------------------------------------------------ status
def open_requirements(case):
    return [r for r in case.requirements if r.withdrawn_at is None and r.status in ("needed", "requested", "needs_replacement")]


def pending_originals(case):
    out = []
    for r in case.requirements:
        t = getattr(r, "itin_track", None)
        if r.withdrawn_at is None and t is not None and t.original_required and t.original_state in ("required", "will_mail", "will_bring", "in_transit"):
            out.append(r)
    return out


def derived_stage(case):
    apps = applicants(case)
    if not apps or not all(a["submission"].is_complete for a in apps):
        return "intake_started"
    if open_requirements(case):
        return "waiting_docs"
    if pending_originals(case):
        return "waiting_originals"
    return "ready_review"


def stage_of(case):
    cd = case.itin_data
    return (cd.stage if cd is not None and cd.stage else None) or derived_stage(case)


def stage_label(key, lang="en"):
    return (STAGE_EN if lang == "en" else STAGE_ES).get(key, key)


def doc_counts(case, person=None):
    reqs = [r for r in case.requirements if r.withdrawn_at is None and (person is None or r.person_id == person.id)]
    got = sum(1 for r in reqs if r.status in ("uploaded", "under_review", "accepted"))
    return got, len(reqs)


IRS_OUTCOMES = {"itin_issued": ("ITIN issued", "ITIN emitido"), "irs_notice": ("IRS notice received", "Aviso del IRS recibido"), "other": ("Other response", "Otra respuesta")}


def dashboard(case, lang="en"):
    from app import consular, w7_text
    from app.w7_docs import passport_state
    from app.w7_views import passport_url

    en = lang == "en"
    apps = []
    for a in applicants(case):
        s = a["submission"]
        got, total = doc_counts(case, a["person"])
        apps.append({"submission": s, "person": a["person"], "kind": a["kind"], "kind_label": kind_label(a["kind"], lang), "percent": consular.form_progress(s),
                     "docs_got": got, "docs_total": total, "passport": passport_state(s), "passport_url": passport_url(s, lang), "started": bool(s.values)})
    cd = case.itin_data
    got, total = doc_counts(case)
    pend = len(pending_originals(case))
    package = None
    if cd and (cd.usps_tracking or cd.irs_mailed_date):
        package = {"tracking": cd.usps_tracking, "mailed": cd.irs_mailed_date, "status": cd.irs_mailing_status, "track_url": usps_url(cd.usps_tracking)}
    return {"applicants": apps, "stage": stage_of(case), "stage_label": stage_label(stage_of(case), lang), "tax_year": cd.tax_year if cd else None, "docs_got": got, "docs_total": total,
            "package": package, "outcome": cd.irs_outcome if cd else None, "outcome_label": (IRS_OUTCOMES.get(cd.irs_outcome, ("", ""))[0 if en else 1] if cd and cd.irs_outcome else ""),
            "outcome_note": cd.irs_note if cd else None, "originals": pend, "delivery_html": w7_text.delivery_html(lang, html_escape) if pend else "",
            "processing_html": w7_text.PROCESSING[0 if en else 1], "disclaimer": w7_text.DISCLAIMER[0 if en else 1]}


def usps_url(tracking):
    t = "".join(ch for ch in (tracking or "") if ch.isalnum())
    return f"https://tools.usps.com/go/TrackConfirmAction?tLabels={t}" if t else None
