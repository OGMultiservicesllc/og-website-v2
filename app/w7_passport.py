"""Passport data: extraction, staff reading and the customer's confirmation.

There is NO document-reading (OCR / vision) service in this platform and no customer document is ever sent to a third party from here. What exists:

  * `parse_mrz`      a pure-Python ICAO 9303 (TD3 passport, 2 x 44) machine-readable-zone parser with check-digit validation. Used when a reading backend returns the
                     MRZ text, and by staff who paste the two MRZ lines shown on the passport photo.
  * `extract`        tries the OPTIONAL local backends (`pytesseract` + a tesseract binary) on an uploaded image; returns None when none is installed or nothing reliable
                     was read. It never raises and never calls a network service.
  * staff reading    Admin can enter (or paste the MRZ of) what the uploaded passport page shows; the values are stored with source "staff_read".
  * the customer     always confirms or corrects before anything becomes a confirmed Person fact (provenance: source document, extraction source, customer_confirmed, date).

An extraction is never trusted blindly: `confirm_typed` only writes Person facts after the customer says the values are right (or types the corrected ones), and a value that
differs from what OG already holds for that Person becomes a visible CLAIM (conflict), never a silent overwrite.
"""

import json
import re
from datetime import date, datetime

from app import persons as pers
from app.extensions import db
from app.models import PassportExtraction

# ICAO 3-letter codes -> English country names (the countries OG's customers most often come from + common others). An unknown code is returned as-is and flagged.
COUNTRY = {
    "ARG": "Argentina", "BOL": "Bolivia", "BRA": "Brazil", "CHL": "Chile", "COL": "Colombia", "CRI": "Costa Rica", "CUB": "Cuba", "DOM": "Dominican Republic", "ECU": "Ecuador",
    "SLV": "El Salvador", "GTM": "Guatemala", "HND": "Honduras", "HTI": "Haiti", "MEX": "Mexico", "NIC": "Nicaragua", "PAN": "Panama", "PRY": "Paraguay", "PER": "Peru",
    "URY": "Uruguay", "VEN": "Venezuela", "CAN": "Canada", "ESP": "Spain", "PRT": "Portugal", "ITA": "Italy", "FRA": "France", "DEU": "Germany", "D": "Germany", "GBR": "United Kingdom",
    "IND": "India", "PAK": "Pakistan", "BGD": "Bangladesh", "CHN": "China", "PHL": "Philippines", "VNM": "Vietnam", "KOR": "South Korea", "JPN": "Japan", "NGA": "Nigeria", "GHA": "Ghana",
    "ETH": "Ethiopia", "EGY": "Egypt", "UKR": "Ukraine", "RUS": "Russia", "POL": "Poland", "ROU": "Romania", "TUR": "Turkey", "JAM": "Jamaica", "TTO": "Trinidad and Tobago", "GUY": "Guyana",
    "BLZ": "Belize", "IDN": "Indonesia", "THA": "Thailand", "NPL": "Nepal", "LKA": "Sri Lanka", "MAR": "Morocco", "DZA": "Algeria", "SEN": "Senegal", "KEN": "Kenya", "ZAF": "South Africa",
    "IRL": "Ireland", "AUS": "Australia", "NZL": "New Zealand", "BRB": "Barbados", "BHS": "Bahamas", "ALB": "Albania", "ARM": "Armenia", "GEO": "Georgia", "UZB": "Uzbekistan",
}
_WEIGHTS = (7, 3, 1)
_VAL = {**{str(i): i for i in range(10)}, **{chr(65 + i): 10 + i for i in range(26)}, "<": 0}


def _check(field):
    return sum(_VAL.get(ch, 0) * _WEIGHTS[i % 3] for i, ch in enumerate(field)) % 10


def _cd_ok(field, digit):
    return digit.isdigit() and _check(field) == int(digit)


def _date(yymmdd, kind, today=None):
    today = today or date.today()
    if not re.fullmatch(r"\d{6}", yymmdd or ""):
        return None
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:])
    if kind == "dob":
        year = 1900 + yy if 2000 + yy > today.year else 2000 + yy
    else:  # expiry: within the 2000s
        year = 2000 + yy
    try:
        return date(year, mm, dd).isoformat()
    except ValueError:
        return None


def _name(part):
    return " ".join(x for x in part.replace("<", " ").split())


def parse_mrz(text):
    """{"ok", "values", "flags", "errors"} from the two MRZ lines of a TD3 passport (44 characters each). `flags` lists what the customer must look at."""
    lines = [re.sub(r"\s+", "", ln).upper() for ln in str(text or "").splitlines() if len(re.sub(r"\s+", "", ln)) >= 30]
    if len(lines) < 2:
        return {"ok": False, "values": {}, "flags": [], "errors": ["Two MRZ lines are needed."]}
    l1, l2 = lines[-2].ljust(44, "<")[:44], lines[-1].ljust(44, "<")[:44]
    errors, flags = [], []
    if not l1.startswith("P"):
        return {"ok": False, "values": {}, "flags": [], "errors": ["This does not look like a passport MRZ (TD3)."]}
    issuing = l1[2:5].replace("<", "")
    surname, _, given = l1[5:].partition("<<")
    number, ncd = l2[0:9], l2[9]
    nationality = l2[10:13].replace("<", "")
    dob, dcd = l2[13:19], l2[19]
    sex = l2[20]
    exp, ecd = l2[21:27], l2[27]
    for label, field, digit in (("passport number", number, ncd), ("date of birth", dob, dcd), ("expiration date", exp, ecd)):
        if not _cd_ok(field, digit):
            errors.append(f"The {label} check digit does not match: the reading may be wrong.")
    values = {
        "family": _name(surname), "given": _name(given), "pp_number": number.replace("<", ""), "pp_country": COUNTRY.get(issuing, issuing), "nationality": COUNTRY.get(nationality, nationality),
        "dob": _date(dob, "dob"), "sex": {"M": "male", "F": "female"}.get(sex, ""), "pp_expiry": _date(exp, "exp"),
    }
    if issuing not in COUNTRY or nationality not in COUNTRY:
        flags.append("country_code")
    if not values["dob"] or not values["pp_expiry"]:
        errors.append("A date could not be read.")
    return {"ok": not errors, "values": {k: v for k, v in values.items() if v}, "flags": flags, "errors": errors}


def _mrz_from_ocr_text(text):
    cands = [re.sub(r"[^A-Z0-9<]", "", ln.upper()) for ln in str(text or "").splitlines()]
    cands = [c for c in cands if len(c) >= 40]
    for i in range(len(cands) - 1):
        if cands[i].startswith("P"):
            return cands[i] + "\n" + cands[i + 1]
    return None


def ocr_available():
    try:
        import pytesseract  # type: ignore

        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001
        return False


def extract(path):
    """Values read from an uploaded image, or None. Optional LOCAL backend only (tesseract); never a network call, never raises."""
    if not ocr_available():
        return None
    try:
        import pytesseract  # type: ignore
        from PIL import Image

        img = Image.open(path).convert("L")
        w, h = img.size
        text = pytesseract.image_to_string(img.crop((0, int(h * 0.62), w, h)), config="--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<")
        mrz = _mrz_from_ocr_text(text)
        parsed = parse_mrz(mrz) if mrz else None
        return parsed["values"] if parsed and parsed["ok"] else None
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------ stored extractions
def values_of(row):
    try:
        return json.loads(row.values_json or "{}")
    except ValueError:
        return {}


def latest(submission, kind="passport", statuses=("pending", "confirmed")):
    rows = [r for r in submission.extractions if r.kind == kind and r.status in statuses]
    return max(rows, key=lambda r: r.id) if rows else None


def add_extraction(submission, document, source, values, kind="passport"):
    for r in submission.extractions:
        if r.kind == kind and r.status == "pending":
            r.status = "superseded"
    row = PassportExtraction(submission_id=submission.id, document_id=document.id if document is not None else None, kind=kind, source=source,
                             values_json=json.dumps(values or {}, ensure_ascii=False), status="pending")
    db.session.add(row)
    db.session.commit()
    return row


# ------------------------------------------------------------------ confirmation -> answers + Person facts
_ANSWER_OF = {"family": "a_family", "given": "a_given", "middle": "a_middle", "dob": "a_dob", "sex": "a_sex", "birth_city": "a_birth_city", "birth_country": "a_birth_country",
              "nationality": "a_nationality", "pp_number": "a_pp_number", "pp_country": "a_pp_country", "pp_issued": "a_pp_issued", "pp_expiry": "a_pp_expiry"}
_FACT_OF = {"a_family": "family_name", "a_given": "given_name", "a_middle": "middle_name", "a_dob": "date_of_birth", "a_sex": "sex", "a_birth_city": "birth_city",
            "a_birth_country": "birth_country", "a_nationality": "nationality", "a_pp_number": "passport_number", "a_pp_country": "document_country",
            "a_pp_issued": "passport_issue_date", "a_pp_expiry": "document_expiry"}
SOURCE_REF = {"mrz_ocr": "Passport (read automatically, confirmed by the customer)", "staff_read": "Passport (read by OG staff, confirmed by the customer)",
              "customer_typed": "Passport (typed by the customer from the document)"}


def record_facts(submission, answers, source):
    """Confirmed passport values -> canonical Person facts with provenance. A fact OG already holds with a DIFFERENT value gets a claim only (a visible conflict),
    never a silent overwrite; a new or identical fact is confirmed. Returns the list of fact keys that now conflict."""
    from app import cases as case_svc

    cp = case_svc.role_person(submission, "itin_applicant")
    if cp is None:
        return []
    owner = pers.owner_of(cp)
    conflicts = []
    for ans, key in _FACT_OF.items():
        value = answers.get(ans)
        if value in (None, ""):
            continue
        fact = pers.get_fact(owner, key)
        ref = SOURCE_REF.get(source, "Passport")
        if fact is not None and fact.last_confirmed_at is not None and not pers.same(key, pers.fact_value(fact), value):
            pers.record_claim(owner, key, value, submission, field_name=ans, source_ref=ref)
            pers.evaluate(pers.get_fact(owner, key), submission)
            conflicts.append(key)
            continue
        pers.record_claim(owner, key, value, submission, field_name=ans, source_ref=ref)
        fact = pers.get_fact(owner, key)
        if fact is not None:
            fact.value_json = pers._dump(value)  # noqa: SLF001  (the customer-confirmed value becomes the canonical one when nothing confirmed it differently before)
            pers.confirm(owner, [key], submission, actor="customer")
    db.session.commit()
    return conflicts


def confirm_typed(submission, answers):
    """The customer confirmed (or corrected) the passport details shown in the form: `answers` are answer-keyed. When every value the reading found is still present
    unchanged the source stays the reading (automatic / staff), otherwise the customer's typing. Returns (answers, conflicting fact keys, source)."""
    row = latest(submission, statuses=("pending",))
    answers = {k: v for k, v in answers.items() if v}
    source = "customer_typed"
    if row is not None:
        read = values_of(row)
        if read and all(answers.get(_ANSWER_OF[k]) == v for k, v in read.items() if k in _ANSWER_OF):
            source = row.source
    conflicts = record_facts(submission, answers, source)
    if row is None:
        row = add_extraction(submission, None, "customer_typed", {})
    row.status, row.confirmed_at, row.confirmed_by, row.source = "confirmed", datetime.utcnow(), "customer", source
    row.values_json = json.dumps(answers, ensure_ascii=False)
    db.session.commit()
    return answers, conflicts, source
