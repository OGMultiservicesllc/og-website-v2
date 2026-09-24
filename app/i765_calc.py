"""Form I-765 derived values — pure functions over an application's answers.

Nothing here decides eligibility. In particular the eligibility category (Part 2 Item 27) is STORED exactly as the customer or OG gave it:
this module only normalizes its syntax (letter, number, optional third part) and reports which of the source's category-specific
questions (Items 28-31) apply to it. It never suggests, derives or evaluates a category.

  category_parts / category_text   the three printed boxes  "( )( )( )"  -> "(c)(3)(C)"
  branch                           which category-specific follow-up (source Items 28-31) the category triggers
  abc_relevant                     whether the ABC settlement question (Part 3 Item 6) is worth asking (Salvadoran / Guatemalan)
  additional_entries               Part 6 entries OG must write because the structured answers exceed the printed space
  calculated                       the values written back as hidden calculated answers
"""

import json
import re
import unicodedata

from app import business_info

BRANCHES = {"c3c": "(c)(3)(C)", "c26": "(c)(26)", "c8": "(c)(8)", "c35": "(c)(35)", "c36": "(c)(36)"}

_LETTER = re.compile(r"^[A-Za-z]$")
_NUMBER = re.compile(r"^\d{1,2}$")
_THIRD = re.compile(r"^[A-Za-z]{1,4}$")


def _clean(text):
    return str(text or "").strip().strip("()").strip()


def category_parts(a):
    """(letter, number, third) as entered (blank strings when empty)."""
    return _clean(a.get("e_cat_a")), _clean(a.get("e_cat_b")), _clean(a.get("e_cat_c"))


def category_valid(a):
    """True when the entered category has the printed syntax: a letter, a number and (optionally) a third part. Says nothing about eligibility."""
    letter, number, third = category_parts(a)
    return bool(_LETTER.match(letter) and _NUMBER.match(number) and (not third or _THIRD.match(third)))


def category_text(a):
    """'(c)(3)(C)' — letter lower-cased, number without leading zeros, the third part exactly as entered. '' when incomplete or malformed."""
    if not category_valid(a):
        return ""
    letter, number, third = category_parts(a)
    out = f"({letter.lower()})({int(number)})"
    return out + (f"({third})" if third else "")


def branch(a):
    """Key of the category-specific questions that apply ('' for every other category). Only an exact, well-formed category triggers a branch."""
    if a.get("e_known") != "known" or not category_valid(a):
        return ""
    letter, number, third = category_parts(a)
    letter, number = letter.lower(), int(number)
    if letter == "c" and number == 3 and third == "C":
        return "c3c"
    if third:
        return ""
    if letter == "c" and number in (26, 8, 35, 36):
        return f"c{number}"
    return ""


def _fold(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", text)


def countries(a):
    """Every country of citizenship or nationality the applicant gave, in order (Item 14.a first)."""
    out = []
    first = str(a.get("a_citizenship") or "").strip()
    if first:
        out.append(first)
    if a.get("a_more_countries") == "yes":
        for r in (a.get("a_countries_more") if isinstance(a.get("a_countries_more"), list) else []):
            c = str((r or {}).get("country") or "").strip()
            if c:
                out.append(c)
    return out


def abc_relevant(a):
    """'yes' when the ABC settlement checkbox (Part 3 Item 6) is worth asking: a country of citizenship or birth reads as El Salvador or Guatemala.
    This only decides whether to ASK; it never concludes that the applicant is eligible for anything."""
    for c in countries(a) + [str(a.get("a_birth_country") or "")]:
        f = _fold(c)
        if "salvador" in f or "guatemal" in f:
            return "yes"
    return "no"


def _name(rec):
    return " ".join(x for x in (rec.get("given"), rec.get("middle"), rec.get("family")) if x)


def additional_entries(a):
    """[{page, part, item, text, kind}] Part 6 entries implied by the structured answers (more than the printed form has room for) plus what the
    applicant wrote. The customer is never asked for a page, part or item number."""
    out = []
    names = [r for r in (a.get("a_other_names") if isinstance(a.get("a_other_names"), list) else []) if isinstance(r, dict) and (r.get("given") or r.get("family"))]
    if len(names) > 3:
        out.append({"page": 1, "part": 2, "item": "4", "kind": "other_names",
                    "text": "Additional other names used (aliases, maiden name, nicknames): " + "; ".join(_name(r) for r in names[3:]) + "."})
    cs = countries(a)
    if len(cs) > 2:
        out.append({"page": 2, "part": 2, "item": "14.b", "kind": "countries", "text": "Additional countries where I am currently a citizen or national: " + ", ".join(cs[2:]) + "."})
    if a.get("p_prior") == "yes" and str(a.get("p_prior_details") or "").strip():
        out.append({"page": 2, "part": 2, "item": "12", "kind": "prior_i765", "text": str(a["p_prior_details"]).strip()})
    for key, item in (("x_c8_details", "30"), ("x_c3536_details", "31.b")):
        if str(a.get(key) or "").strip():
            out.append({"page": 3, "part": 2, "item": item, "kind": "arrest", "text": str(a[key]).strip()})
    if str(a.get("additional_information") or "").strip():
        out.append({"page": None, "part": None, "item": None, "kind": "applicant", "text": str(a["additional_information"]).strip()})
    return out


def entry_label(e, lang="en"):
    if e.get("page") is None:
        return "Applicant's additional information (OG assigns the reference)" if lang != "es" else "Información adicional del solicitante (OG asigna la referencia)"
    return f"Page {e['page']}, Part {e['part']}, Item {e['item']}" if lang != "es" else f"Página {e['page']}, Parte {e['part']}, Ítem {e['item']}"


def preparer_statement():
    """(item, extends) from the CENTRAL OG configuration: Part 5 Item 7.a (not an attorney or accredited representative) or 7.b."""
    status = getattr(business_info, "PREPARER_STATUS", "not_attorney")
    if status in ("attorney", "accredited"):
        return "7.b", getattr(business_info, "PREPARER_REPRESENTATION_EXTENDS", "") or ""
    return "7.a", ""


def calculated(a):
    item, extends = preparer_statement()
    return {
        "c_category": category_text(a) if a.get("e_known") == "known" else "",
        "c_branch": branch(a),
        "c_abc_rel": abc_relevant(a),
        "c_addl": json.dumps(additional_entries(a), ensure_ascii=False),
        "prep_status": item,
        "prep_extends": extends,
    }
