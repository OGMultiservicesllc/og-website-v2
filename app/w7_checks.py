"""Completeness / consistency prompts for the ITIN / W-7 intake ("please review", never an IRS or eligibility conclusion).

Documents that are still to come (passport later, visa page, marriage certificate, originals) show up here as things OG is waiting for; they never stop the customer from
sending the application to OG. The same list feeds the customer's Completeness Check and the Admin application view."""

from app import w7_calc
from app import w7_docs as D
from app import w7_text as T


def run(a, lang="en", submission=None):
    en = lang != "es"
    out = []

    def add(group, fields, msg_en, msg_es):
        out.append({"group": group, "fields": fields, "message": msg_en if en else msg_es})

    if submission is None:
        return out
    fl, _cand = w7_calc.flags(a, submission)
    codes = {f["code"] for f in fl}
    if "passport_needed" in codes:
        add("passport", ["pp_status"], "PASSPORT — NEEDED. Upload it any time from My Account; you can keep going without it.", "PASAPORTE — SE NECESITA. Súbelo cuando quieras desde Mi Cuenta; puedes seguir sin él.")
    if "passport_unconfirmed" in codes:
        add("passport", ["pp_status"], "Confirm the passport information we found (or correct it).", "Confirma la información del pasaporte que encontramos (o corrígela).")
    if "identity_pending" in codes and "passport_needed" in codes:
        add("about", ["pp_status"], "PERSONAL DATA — PENDING PASSPORT VERIFICATION", "DATOS PERSONALES — PENDIENTES DE VERIFICAR CON EL PASAPORTE")
    if "w2_identifier" in codes:
        add("income", ["inc_type"], T.W2_REVIEW[0], T.W2_REVIEW[1])
    if "ssn_status" in codes:
        add("itin", ["ssn_status"], T.SSN_NOTE[0], T.SSN_NOTE[1])
    if "renew_itin_missing" in codes:
        add("itin", ["hist_itin"], "This is a renewal: OG needs the previous ITIN and the name it was issued under.", "Esta es una renovación: OG necesita el ITIN anterior y el nombre con el que se emitió.")
    for code, fields in (("foreign_residence", ["a_foreign_res"]), ("taxpayer_id_missing", ["pp_status"]), ("relationship_missing", ["pp_status"])):
        hit = next((f for f in fl if f["code"] == code), None)
        if hit is not None:
            add("family" if code != "foreign_residence" else "entry", fields, hit["en"], hit["es"])
    if "residency_open" in codes:
        add("family", ["pp_status"], "Proof of U.S. residency: OG will tell you which document fits this child's age.", "Prueba de residencia en EE. UU.: OG te dirá qué documento sirve según la edad de este menor.")
    if "dob_missing" in codes:
        add("family", ["pp_status"], "The date of birth is needed to know which documents apply.", "Se necesita la fecha de nacimiento para saber qué documentos aplican.")
    case = submission.case
    if case is not None and (case.itin_data is None or not case.itin_data.tax_year):
        add("start", ["pp_status"], "The tax year for this case is not set yet.", "Aún no se ha definido el año fiscal de este caso.")
    for r in D.requirements_of(submission):
        t = r.itin_track
        if t is not None and t.original_required and t.original_state in ("required", "will_mail", "will_bring", "in_transit"):
            title_en, title_es = D.req_text(r, "en")[0], D.req_text(r, "es")[0]
            add("documents", ["pp_status"], f"Original still to give OG: {title_en}", f"Original que aún debes entregar a OG: {title_es}")
    return out


run.wants_submission = True
