"""The auditable W-7 map: what OG holds for each printed line of Form W-7 (Rev. December 2024), in W-7 order, with where each value came from and whether it is confirmed.

Nothing is submitted, signed or decided here. Lines the online workflow does not collect say so (`not_collected`). Staff read the values here and prepare the paper form;
the W-7 signature is never collected by the intake.
"""

from app import business_info as biz
from app import cases as case_svc
from app import w7_calc
from app import w7_docs as D
from app import w7_passport as PP
from app.itin_admin import SIGNATURE_STATES
from app.intake_records import parse_date

STATUS_TEXT = {"confirmed": "Confirmed", "customer": "Customer answer", "candidate": "Candidate (staff must confirm)", "missing": "Missing", "pending": "Pending passport verification",
               "review": "OG REVIEW — ADDITIONAL W-7 INFORMATION REQUIRED", "not_collected": "Not collected by the online workflow", "config": "OG configuration", "staff": "Recorded by staff"}
_PASSPORT_BACKED = ("a_family", "a_given", "a_middle", "a_dob", "a_sex", "a_birth_city", "a_birth_country", "a_nationality", "a_pp_number", "a_pp_country", "a_pp_issued", "a_pp_expiry")
_SOURCE_TEXT = {"mrz_ocr": "passport read automatically", "staff_read": "passport read by OG staff", "customer_typed": "typed by the customer from the passport"}


def _d(text):
    d = parse_date(text)
    return d.strftime("%m/%d/%Y") if d else (text or "")


def mask(value, keep=4):
    v = str(value or "")
    return ("•" * max(len(v) - keep, 0) + v[-keep:]) if v else ""


def build(submission, reveal=True):
    """{sections: [{title, rows: [{line, label, value, status, source, sensitive, note}]}], flags, reason, counts}"""
    a = case_svc.answers_by_name(submission)
    cd = submission.case.itin_data if submission.case is not None else None
    w = submission.w7
    ps = D.passport_state(submission)
    ext = PP.latest(submission, statuses=("confirmed",))
    when = ext.confirmed_at.strftime("%b %d, %Y") if ext is not None and ext.confirmed_at else ""
    fl, cand = w7_calc.flags(a, submission)
    rows_by_section = []

    def sec(title):
        rows = []
        rows_by_section.append({"title": title, "rows": rows})
        return rows

    def row(rows, line, label, value, *, status=None, source="", sensitive=False, note=""):
        shown = value if (reveal or not sensitive) else mask(value)
        if status is None:
            status = "customer" if value else "missing"
        rows.append({"line": line, "label": label, "value": shown, "status": status, "source": source, "sensitive": sensitive, "note": note})

    def pp_row(rows, line, label, name, value=None, sensitive=False):
        raw = a.get(name) if value is None else value
        if ps["confirmed"] and raw:
            row(rows, line, label, raw, status="confirmed", source=f"Passport ({_SOURCE_TEXT.get(ext.source, 'passport')}), confirmed by the customer {when}", sensitive=sensitive)
        elif raw:
            row(rows, line, label, raw, status="pending" if ps["applies"] else "customer", source=("Application answer" + (" — passport not confirmed yet" if ps["applies"] else "")), sensitive=sensitive)
        else:
            row(rows, line, label, "", status="pending" if ps["applies"] else "missing", source="Passport photo page" if ps["applies"] else "Application answer", sensitive=sensitive)

    r = sec("Application type and reason")
    kind_word = {"new": "Apply for a new ITIN", "renew": "Renew an existing ITIN", "unsure": "Customer is not sure — OG decides"}.get(cd.request_kind if cd else "", "")
    row(r, "Application type", "Type (check one box)", kind_word, source="ITIN case setup", status="customer" if kind_word else "missing")
    reason_txt = dict(w7_calc.REASONS).get(w.reason_confirmed) if (w is not None and w.reason_confirmed) else ""
    if reason_txt:
        row(r, "Reason", "Reason you are submitting Form W-7", reason_txt, status="staff", source=f"Confirmed by {w.reason_confirmed_by} on {w.reason_confirmed_at.strftime('%b %d, %Y')}" if w.reason_confirmed_at else "Confirmed by staff",
            note=(w.reason_note or ""))
    else:
        row(r, "Reason", "Reason you are submitting Form W-7 (candidate)", w7_calc.REASON_LABEL.get(cand, ("", ""))[0], status="candidate", source="Derived from the applicant type and the taxpayer's status; the customer never chooses it")
    row(r, "d / e", "Relationship (d) and name / SSN-ITIN of the U.S. citizen or resident alien (d or e)",
        ((a.get("dep_rel") or "") + (" — SSN/ITIN " + (a.get("taxpayer_ssn_itin") if reveal else mask(a.get("taxpayer_ssn_itin"))) if a.get("taxpayer_ssn_itin") else "")) if cand in ("d", "e") else "",
        status=("customer" if (cand in ("d", "e") and a.get("taxpayer_ssn_itin")) else ("review" if cand in ("d", "e") else "not_collected")), source="Application answer (only when reason d or e applies)", sensitive=True)
    row(r, "a / f / h", "Treaty country and article; student/professor/researcher; Other", "", status="not_collected", source="Reasons a and f, and ITIN Exceptions 1–5, are NOT IMPLEMENTED BY CURRENT OG ONLINE WORKFLOW")

    r = sec("Name and address")
    first = " ".join(x for x in (a.get("a_given"), a.get("a_middle")) if x)
    pp_row(r, "1a", "First and middle name", "a_given", value=first)
    pp_row(r, "1a", "Last name(s)", "a_family")
    row(r, "1b", "Name at birth, if different", a.get("a_birth_name"), status="customer" if a.get("a_birth_name") else "confirmed", source="Application answer (blank = same name)")
    street = " ".join(x for x in (a.get("ua_street"), (a.get("ua_unit_type") or "").title(), a.get("ua_unit_number")) if x)
    row(r, "2", "Mailing address (U.S.)", street, source="Application answer / confirmed shared address")
    row(r, "2", "City, state, ZIP", ", ".join(x for x in (a.get("ua_city"), " ".join(x for x in (a.get("ua_state"), a.get("ua_zip")) if x)) if x), source="Application answer / confirmed shared address")
    row(r, "3", "Foreign (non-U.S.) address", a.get("a_prior_country") and f"Country only: {a.get('a_prior_country')}",
        status="review" if any(f["code"] in ("line3_foreign_address", "foreign_residence") for f in fl) else "customer", source="Application answer (country of last residence only)",
        note="OG REVIEW — ADDITIONAL W-7 INFORMATION REQUIRED when the full foreign address is needed." if any(f["code"] in ("line3_foreign_address", "foreign_residence") for f in fl) else "")

    r = sec("Birth information")
    pp_row(r, "4", "Date of birth", "a_dob", value=_d(a.get("a_dob")) if a.get("a_dob") else "")
    pp_row(r, "4", "Country of birth", "a_birth_country")
    pp_row(r, "4", "City and state or province of birth", "a_birth_city")
    pp_row(r, "5", "Sex", "a_sex", value=(a.get("a_sex") or "").title())

    r = sec("Other information")
    pp_row(r, "6a", "Country(ies) of citizenship", "a_nationality")
    row(r, "6b", "Foreign tax I.D. number (if any)", a.get("a_foreign_tin"), status="customer" if a.get("a_foreign_tin") else "confirmed", source="Application answer (blank = none)", sensitive=True)
    visa = " · ".join(x for x in (a.get("visa_class"), a.get("visa_number") if reveal else mask(a.get("visa_number")), _d(a.get("visa_expiry")) if a.get("visa_expiry") else "") if x)
    row(r, "6c", "Type of U.S. visa (if any), number, expiration date", visa if a.get("visa_entered") == "yes" else ("No visa" if a.get("visa_entered") == "no" else ""),
        status="customer" if a.get("visa_entered") in ("yes", "no") else "missing", source="Application answer; visa page in the vault", sensitive=True,
        note="Visa details incomplete: read them from the visa page." if any(f["code"] == "visa_details" for f in fl) else "")
    if a.get("pp_status") == "none":
        docs = ", ".join(D.R.ALL_DOC_LABELS[k][0].split(" (")[0] for k in D.R.NO_PASSPORT_CHOICES if k in (a.get("alt_docs") or [])) if isinstance(a.get("alt_docs"), list) else ""
        row(r, "6d", "Identification document(s) submitted", docs, source="Customer says they have these; OG reviews the originals", note="No passport: at least two document types are needed (see coverage).")
    else:
        pp_row(r, "6d", "Passport — issued by", "a_pp_country")
        pp_row(r, "6d", "Passport — number", "a_pp_number", sensitive=True)
        pp_row(r, "6d", "Passport — expiration date", "a_pp_expiry", value=_d(a.get("a_pp_expiry")) if a.get("a_pp_expiry") else "")
    row(r, "6d", "Date of entry into the United States", _d(a.get("a_entry_date")) if a.get("a_entry_date") else "", source="Application answer / confirmed shared entry date")
    prev = {"yes": "Yes — complete line 6f", "no": "No", "unsure": "Don't know — skip line 6f"}.get(a.get("hist_itin"), "")
    row(r, "6e", "Previously received an ITIN or IRSN?", prev, source="Application answer")
    row(r, "6f", "ITIN and/or IRSN and name under which it was issued", ((a.get("hist_itin_num") if reveal else mask(a.get("hist_itin_num"))) or "") + (f" — {a.get('hist_itin_name')}" if a.get("hist_itin_name") else "") if a.get("hist_itin") == "yes" else "",
        status="customer" if a.get("hist_itin") == "yes" and a.get("hist_itin_num") else ("missing" if a.get("hist_itin") == "yes" else "not_collected"), source="Application answer", sensitive=True)
    row(r, "6g", "College/university or company; city and state; length of stay", "", status="not_collected", source="Only for reasons f/h and Exceptions — NOT IMPLEMENTED BY CURRENT OG ONLINE WORKFLOW")

    r = sec("Sign here")
    row(r, "Signature", "Applicant's signature / date", "", status="not_collected", source="Never collected by the intake; the W-7 is signed separately",
        note=f"Signature status recorded by staff: {dict(SIGNATURE_STATES).get(w.signature_state, '—') if w else '—'}")
    row(r, "Phone", "Phone number", a.get("a_phone"), source="Application answer / confirmed shared contact")

    r = sec("Acceptance agent's use only (OG configuration)")
    cfg = [("Name of company", biz.CAA_COMPANY), ("EIN", biz.CAA_EIN), ("PTIN", biz.CAA_PTIN), ("Office code", biz.CAA_OFFICE_CODE), ("Phone", biz.CAA_PHONE), ("Fax", biz.CAA_FAX)]
    for label, value in cfg:
        row(r, "Agent", label, value, status="config" if value else "missing", source="OG configuration (app/business_info.py)", note="" if value else "Staff enter this in OG's configuration; it is never guessed.")
    row(r, "Agent", "Signature, date, name and title", "", status="not_collected", source="Signed by OG staff on the paper form; CAA verification is recorded in this system by explicit staff action")
    counts = {"missing": 0, "pending": 0, "review": 0}
    for s in rows_by_section:
        for x in s["rows"]:
            if x["status"] in counts:
                counts[x["status"]] += 1
    return {"sections": rows_by_section, "flags": fl, "candidate": cand, "counts": counts}
