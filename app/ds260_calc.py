"""DS-260 derived values — pure functions over one application's answers.

Nothing here decides admissibility, eligibility or a waiver. It derives: the applicant's age, the start of the address-history window (age 16),
the 2019-sample SECTION VISIBILITY HINTS (which CEAC sections the 2019 sample showed to which applicant: recorded as UNVERIFIED for the current
system and used only as an admin hint, never to hide a question from the customer), the number of Security & Background answers that need OG's
review, the FGM/C country flag and the central preparer defaults.
"""

import json
import unicodedata
from datetime import date

from app import business_info
from app import ds260_text as T
from app.intake_records import parse_date

PREV_WORK_NATIONALITIES = {"burma", "china", "cuba", "india", "iran", "north korea", "pakistan", "saudi arabia", "sudan", "syria", "stateless"}
ADDITIONAL_LIST = {"afghanistan"} | PREV_WORK_NATIONALITIES
PREV_WORK_VISA_CLASSES = {"E11", "E12", "E13", "E21", "E31", "E32", "EW3", "SD1", "SR1", "SE1", "C51", "T51", "SI1", "SQ1", "SF1", "SG1", "SH1", "SJ1", "SK1", "SN1", "R51", "I51", "DV-1", "DV1"}


def norm(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower().strip()
    return " ".join(text.replace("-", " ").replace(".", "").split())


def age_on(dob, today=None):
    today = today or date.today()
    d = parse_date(dob)
    if d is None or d > today:
        return None
    return today.year - d.year - ((today.month, today.day) < (d.month, d.day))


def turned(dob, years):
    d = parse_date(dob)
    if d is None:
        return None
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 February
        return d.replace(year=d.year + years, day=28)


def nationalities(a):
    out = {norm(a.get("a_nationality"))}
    if a.get("a_other_nat") == "yes":
        out.add(norm(a.get("a_other_nat_country")))
    return {n for n in out if n}


def hints(a, submission=None, today=None):
    """[{section, shown, why}] — what the 2019 DOS sample would show this applicant. UNVERIFIED for the current system; a hint only."""
    today = today or date.today()
    age = age_on(a.get("a_dob"), today)
    nats = nationalities(a)
    male = a.get("a_sex") == "male"
    occ = a.get("w_occ")
    role = None
    visa_class = ""
    if submission is not None:
        row = getattr(submission, "ds260", None)
        role = row.applicant_role if row is not None else None
        cd = getattr(getattr(submission, "case", None), "consular_data", None)
        visa_class = (cd.visa_class or "").upper() if cd is not None else ""
    out = []
    over14 = age is not None and age >= 14
    out.append({"section": "Work/Education/Training: Present", "shown": over14 if age is not None else None, "why": "2019 sample: applicants over the age of 14"})
    reasons = []
    if male and age is not None and 14 <= age <= 60:
        reasons.append("male aged 14 to 60")
    if over14 and nats & PREV_WORK_NATIONALITIES:
        reasons.append("nationality on the 2019 list")
    if occ in ("retired", "not_employed", "homemaker"):
        reasons.append("retired, not employed or homemaker")
    if role == "principal" and visa_class in PREV_WORK_VISA_CLASSES:
        reasons.append("principal applicant, visa class on the 2019 list")
    out.append({"section": "Work/Education/Training: Previous", "shown": bool(reasons) if age is not None else None, "why": "2019 sample: " + ("; ".join(reasons) if reasons else "no 2019 criterion met")})
    add_reasons = []
    if male and age is not None and 14 <= age <= 60 and not (nats & (ADDITIONAL_LIST | {"iraq"})):
        add_reasons.append("male aged 14 to 60, nationality not on the list")
    if over14 and nats & (ADDITIONAL_LIST | {"iraq"}):
        add_reasons.append("nationality on the 2019 list")
    out.append({"section": "Work/Education/Training: Additional (extra questions)", "shown": bool(add_reasons) if age is not None else None,
                "why": "2019 sample: " + ("; ".join(add_reasons) if add_reasons else "the extra organization/skills/languages questions were shown only to some applicants")})
    fg = nats & T.FGMC_2019
    out.append({"section": "Sign and Submit: FGM/C fact-sheet certification", "shown": bool(fg), "why": ("2019 sample list includes " + ", ".join(sorted(fg))) if fg else "no nationality on the 2019 FGM/C list"})
    return out


def security_counts(a):
    """{group: number of answers OG must review} — a Yes (or, for the inverted vaccination question, a No). Never a conclusion."""
    out = {}
    for gkey, _sec, _en, _es, questions in T.SECURITY_GROUPS:
        n = 0
        for key, _qen, _qes, polarity in questions:
            value = a.get(key)
            if value == ("yes" if polarity == "yes" else "no"):
                n += 1
        out[gkey] = n
    return out


def review_flags(a):
    """Workflow flags for OG: which sections have answers to look at with the applicant. Names only; no content, no conclusion."""
    counts = security_counts(a)
    flags = [k for k, v in counts.items() if v]
    for key in ("t_refused", "aw_skills", "aw_para", "aw_mil"):
        if a.get(key) == "yes":
            flags.append(key)
    return flags


def preparer_defaults():
    return {"surname": business_info.PREPARER_LAST_NAME, "given": business_info.PREPARER_FIRST_NAME, "org": business_info.PREPARER_ORG, "street": business_info.OFFICE_STREET,
            "unit": f"{business_info.OFFICE_UNIT_TYPE} {business_info.OFFICE_UNIT_NUMBER}".strip(), "city": business_info.OFFICE_CITY, "state": business_info.OFFICE_STATE,
            "zip": business_info.OFFICE_ZIP, "country": "United States", "relationship": "Document preparation service (OG Multiservices LLC)"}


def calculated(a, submission=None, today=None):
    today = today or date.today()
    age = age_on(a.get("a_dob"), today)
    out = {"c_age": "" if age is None else str(age),
           "c_age14": "" if age is None else ("yes" if age >= 14 else "no"),
           "c_age16": "" if age is None else ("yes" if age >= 16 else "no")}
    sixteen = turned(a.get("a_dob"), 16)
    out["c_since16"] = sixteen.isoformat() if (sixteen is not None and age is not None and age >= 16) else ""
    out["c_rules"] = json.dumps(hints(a, submission, today), ensure_ascii=False)
    out["c_sec_flags"] = json.dumps(security_counts(a))
    out["c_prep"] = json.dumps(preparer_defaults(), ensure_ascii=False)
    out["c_fgmc"] = "yes" if nationalities(a) & T.FGMC_2019 else "no"
    return out
