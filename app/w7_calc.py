"""W-7 derived values — over ONE application's answers plus its case. Nothing here is an IRS determination: the W-7 reason is only a CANDIDATE that staff must confirm.

  age / band          from the date of birth (a dependent's is given at setup, an adult's comes from the confirmed passport)
  passport flags      uploaded / how it was read / confirmed by the customer
  reason candidate    b_or_c (primary) | e or b_c_g (spouse) | d, d_or_g or review (dependent); the customer never sees the reason letters
  flags               OG-review flags with a code and a neutral text (no legal conclusion, no accusation)
"""

import json

from app import w7_docs as D
from app import w7_rules as R
from app import w7_text as T
from app.extensions import db

REASON_LABEL = {
    "b_or_c": ("b or c — nonresident alien filing a U.S. return, or U.S. resident alien (days present) filing a return; OG decides from the days present",
               "b o c — extranjero no residente que presenta una declaración, o extranjero residente (días de presencia) que la presenta; OG decide según los días de presencia"),
    "b_c_g": ("b, c or g — OG decides from the taxpayer's status and the days present", "b, c o g — OG decide según el estatus del contribuyente y los días de presencia"),
    "e": ("e — spouse of a U.S. citizen or resident alien (needs the taxpayer's name and SSN/ITIN)", "e — cónyuge de un ciudadano o residente de EE. UU. (necesita el nombre y SSN/ITIN del contribuyente)"),
    "d": ("d — dependent of a U.S. citizen or resident alien (needs the relationship and the taxpayer's name and SSN/ITIN)", "d — dependiente de un ciudadano o residente de EE. UU. (necesita la relación y el nombre y SSN/ITIN del contribuyente)"),
    "d_or_g": ("d or g — dependent of a U.S. resident alien, or of a nonresident alien with a U.S. visa; OG decides from the taxpayer's status", "d o g — dependiente de un residente extranjero, o de un extranjero no residente con visa; OG decide según el estatus del contribuyente"),
    "review": ("OG to determine (the taxpayer's status is not known yet)", "OG determina (aún no se conoce el estatus del contribuyente)"),
}
# W-7 reason letters the STAFF may confirm (Instructions p. 1-3); "h" = other. Exceptions 1-5 (which sit under some reasons) are NOT implemented.
REASONS = [("a", "a — Nonresident alien required to get an ITIN to claim tax treaty benefit"), ("b", "b — Nonresident alien filing a U.S. tax return and not eligible for an SSN"),
           ("c", "c — U.S. resident alien (based on days present in the U.S.) filing a U.S. tax return and not eligible for an SSN"), ("d", "d — Dependent of a U.S. citizen/resident alien"),
           ("e", "e — Spouse of a U.S. citizen/resident alien"), ("f", "f — Nonresident alien student, professor or researcher filing a U.S. tax return or claiming an exception"),
           ("g", "g — Dependent/spouse of a nonresident alien holding a U.S. visa"), ("h", "h — Other")]


def reason_candidate(kind, tp_status):
    if kind == "primary":
        return "b_or_c"
    if kind == "spouse":
        return "e" if tp_status == "yes" else "b_c_g"
    if kind == "dependent":
        return "d" if tp_status == "yes" else ("d_or_g" if tp_status == "no" else "review")
    return "review"


def _case_data(submission):
    return submission.case.itin_data if submission.case is not None else None


def flags(a, submission):
    """([{code, en, es}], candidate) — OG review flags for this application (never a legal conclusion)."""
    out = []

    def add(code, en, es):
        out.append({"code": code, "en": en, "es": es})

    cd = _case_data(submission)
    kind = D.kind_of(a)
    ps = D.passport_state(submission)
    pp = a.get("pp_status") or "have"
    if ps["applies"] and not ps["uploaded"]:
        add("passport_needed", "PASSPORT — NEEDED", "PASAPORTE — SE NECESITA")
    if ps["applies"] and ps["uploaded"] and not ps["confirmed"]:
        add("passport_unconfirmed", "Passport information is waiting for the customer's confirmation", "La información del pasaporte espera la confirmación del cliente")
    if pp != "none" and not ps["confirmed"]:
        add("identity_pending", "PERSONAL DATA — PENDING PASSPORT VERIFICATION", "DATOS PERSONALES — PENDIENTES DE VERIFICAR CON EL PASAPORTE")
    if a.get("inc_type") in ("employee", "both") and a.get("inc_w2_ssn") in ("yes", "unsure"):
        add("w2_identifier", "W-2 / taxpayer identifier requires OG review", "El W-2 / identificador de contribuyente requiere revisión de OG")
    if a.get("ssn_status") in ("have", "applied", "unsure"):
        add("ssn_status", "Social Security number status requires OG review (Form W-7: do not submit if the applicant has, is eligible for, or has applied for an SSN)",
            "El estado del número de Seguro Social requiere revisión de OG (Formulario W-7: no presentar si el solicitante tiene, es elegible para o ha solicitado un SSN)")
    cp = D.case_svc.role_person(submission, "itin_applicant")
    if cp is not None:
        from app import persons as pers

        if any(any(c.submission_id == submission.id and not c.resolved for c in f.claims) for f in pers.open_conflicts(person=pers.owner_of(cp))):
            add("person_conflict", "Passport details differ from information OG already had for this person — review on the Person page",
                "Los datos del pasaporte difieren de la información que OG ya tenía de esta persona — revisar en la página de la persona")
    tp = (cd.taxpayer_us_status if cd is not None else None) or "unsure"
    cand = reason_candidate(kind, tp)
    if kind == "primary" and tp == "yes":
        add("taxpayer_us_status", "The taxpayer says they are a U.S. citizen or permanent resident; those individuals generally use an SSN, not an ITIN — OG to review",
            "El contribuyente dice ser ciudadano o residente permanente de EE. UU.; esas personas generalmente usan un SSN, no un ITIN — OG debe revisar")
    if cand in ("d", "e") and not a.get("taxpayer_ssn_itin"):
        add("taxpayer_id_missing", T.OG_REVIEW_W7[0] + " — name and SSN/ITIN of the U.S. citizen/resident alien (W-7 reason d/e)", T.OG_REVIEW_W7[1] + " — nombre y SSN/ITIN del ciudadano o residente de EE. UU. (motivo d/e del W-7)")
    if cand == "d" and not a.get("dep_rel"):
        add("relationship_missing", T.OG_REVIEW_W7[0] + " — relationship to the U.S. citizen/resident alien (reason d)", T.OG_REVIEW_W7[1] + " — relación con el ciudadano o residente de EE. UU. (motivo d)")
    if cand in ("b_or_c", "b_c_g"):
        add("line3_foreign_address", T.OG_REVIEW_W7[0] + " — if reason b is confirmed, W-7 line 3 needs the complete foreign address of the most recent residence (OG collects only the country)",
            T.OG_REVIEW_W7[1] + " — si se confirma el motivo b, la línea 3 del W-7 necesita la dirección extranjera completa de la última residencia (OG solo recopila el país)")
    if a.get("a_foreign_res") in ("yes", "unsure"):
        add("foreign_residence", T.OG_REVIEW_W7[0] + " — the applicant may still have a foreign residence: W-7 line 3 needs its full address", T.OG_REVIEW_W7[1] + " — el solicitante podría conservar una residencia en el extranjero: la línea 3 del W-7 necesita su dirección completa")
    if a.get("visa_entered") == "yes" and not (a.get("visa_class") and a.get("visa_number") and a.get("visa_expiry")):
        add("visa_details", "U.S. visa details incomplete (W-7 line 6c): OG reads them from the visa page", "Detalles de la visa incompletos (línea 6c del W-7): OG los lee de la página de la visa")
    if (cd.request_kind if cd is not None else "new") == "renew" and a.get("hist_itin") != "yes":
        add("renew_itin_missing", "Renewal: the previous ITIN and the name it was issued under are needed (W-7 lines 6e/6f)", "Renovación: se necesita el ITIN anterior y el nombre con el que se emitió (líneas 6e/6f del W-7)")
    if kind == "dependent":
        age = D.age_of(a)
        _req, note = R.needs_us_residency(kind, age, a.get("a_nationality"))
        if note == "canada_mexico":
            add("canada_mexico", "Canada/Mexico dependent: whether proof of U.S. residency is required depends on the tax benefit claimed — OG to review",
                "Dependiente de Canadá/México: si se requiere prueba de residencia depende del beneficio fiscal reclamado — OG debe revisar")
        if age is None:
            add("dob_missing", "Date of birth needed to decide which documents apply", "Se necesita la fecha de nacimiento para decidir qué documentos aplican")
        elif D.coverage_for(submission, planned=True)["residency"] is False:
            add("residency_open", "Proof of U.S. residency not yet identified for this dependent", "Aún no se identifica la prueba de residencia en EE. UU. de este dependiente")
    return out, cand


def calculated(a, submission):
    age = D.age_of(a)
    ps = D.passport_state(submission)
    fl, cand = flags(a, submission)
    return {"c_age": "" if age is None else str(age), "c_band": R.age_band(age), "c_student_q": "yes" if (age is not None and 6 <= age < 24) else "no",
            "c_pp_uploaded": "yes" if ps["uploaded"] else "no", "c_pp_confirmed": "yes" if ps["confirmed"] else "no", "c_pp_extract": ps["source"] or "none",
            "c_reason": cand, "c_flags": json.dumps([f["code"] for f in fl]), "ua_is_us": "yes"}


def sync_case_tax(submission, a):
    """The primary taxpayer's income answers are the case's basic tax information (a future Tax Return case reuses them)."""
    cd = _case_data(submission)
    if cd is None or D.kind_of(a) != "primary":
        return
    cd.income_type = a.get("inc_type") or cd.income_type
    cd.work_activity = a.get("self_activity") or cd.work_activity
    cd.occupation = a.get("self_occupation") or cd.occupation
    cd.gross_income = str(a.get("self_gross") or cd.gross_income or "") or None


def write(form, submission, fields=None):
    from app import cases as case_svc
    from app.intake_shared import _set

    fields = fields or {f.internal_name: f for f in form.all_fields}
    a = case_svc.answers_by_name(submission)
    for name, value in calculated(a, submission).items():
        _set(form, submission, fields, name, value)
    sync_case_tax(submission, a)
    db.session.flush()
