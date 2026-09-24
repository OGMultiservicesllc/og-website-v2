"""Form I-751 derived values — pure functions over an application's answers.

Nothing here decides eligibility, timeliness, good faith, hardship or whether a waiver applies. The filing basis (Part 3) is stored exactly as the
customer (or OG) gave it, possibly with several waiver bases at once, or "not sure — OG will review". This module only derives:

  route / basis            what the customer chose (joint | waiver | unsure) and the list of printed boxes (1.a ... 1.g)
  part8_applies            whether the Part 8 statement of the Part 4 spouse/individual is asked (joint filing)
  p4_role                  the Person role of the Part 4 individual (spouse | former_spouse | parent_spouse), time-aware
  children_split           the children the printed form has room for (5) and the ones that go to Part 11
  additional_entries       Part 11 entries OG must write because the structured answers exceed the printed space
  history_ok               whether the residence history covers the period since the customer became a resident
"""

import json
from datetime import date

from app import business_info
from app.intake_records import field_config, parse_date, parse_records, since_from_answers
from app.intake_records import analyze as analyze_records

ROUTES = ("joint", "waiver", "unsure")
WAIVER_BOXES = ("1c", "1d", "1e", "1f", "1g")
SENSITIVE_BOXES = ("1e", "1f", "1g")  # abuse / extreme-cruelty / hardship bases: kept private (never shown outside the customer and OG)
FORM_ROOM_CHILDREN = 5  # Part 5 prints Child 1-5; the rest go to Part 11
FORM_ROOM_OTHER_NAMES = 2  # Part 1 Items 2 and 3


def _list(value):
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str) and value[:1] == "[":
        try:
            data = json.loads(value)
            return [str(v) for v in data] if isinstance(data, list) else []
        except ValueError:
            return []
    return [value] if value else []


def route(a):
    r = str(a.get("b_route") or "")
    return r if r in ROUTES else ""


def basis(a):
    """The printed Part 3 boxes the customer chose: ['1a'] | ['1b'] | any of 1c-1g | []. 'unsure' is reported separately."""
    r = route(a)
    if r == "joint":
        return [a["b_joint"]] if a.get("b_joint") in ("1a", "1b") else []
    if r == "waiver":
        return [b for b in WAIVER_BOXES if b in _list(a.get("b_waiver"))]
    return []


def waiver_unsure(a):
    return route(a) == "unsure" or (route(a) == "waiver" and "unsure" in _list(a.get("b_waiver")))


def sensitive_basis(a):
    return any(b in SENSITIVE_BOXES for b in basis(a))


def part8_applies(a):
    """The form's note ties the Part 8 statement to Box 1.a (joint petition with the spouse). Box 1.b (parent's spouse) is a joint petition too, so the
    contact details are collected but OG confirms whether the rest of Part 8 applies. Every waiver / individual filing: no."""
    return "yes" if route(a) == "joint" and a.get("b_joint") in ("1a", "1b") else "no"


def marriage_ended(a):
    return a.get("r_marriage_ended") == "yes"


def p4_role(a):
    rel = a.get("p4_rel")
    if rel == "parent_spouse":
        return "parent_spouse"
    if rel == "spouse":
        return "former_spouse" if marriage_ended(a) or "1c" in basis(a) or "1d" in basis(a) else "spouse"
    return ""


def since(a):
    d = parse_date(a.get("r_resident_since"))
    return d if d and d <= date.today() else None


def children(a):
    return [r for r in (a.get("k_children") if isinstance(a.get("k_children"), list) else parse_records(a.get("k_children"))) if isinstance(r, dict)] if a.get("k_has") == "yes" else []


def child_name(rec):
    return " ".join(x for x in (rec.get("given"), rec.get("middle"), rec.get("family")) if x) or "(linked person)"


def children_split(a):
    kids = children(a)
    return kids[:FORM_ROOM_CHILDREN], kids[FORM_ROOM_CHILDREN:]


def applying_children(a):
    return [k for k in children(a) if k.get("applying") == "yes"]


def _fmt(d):
    return d.strftime("%m/%d/%Y") if d else "?"


def _period(rec):
    a, b = parse_date(rec.get("from")), parse_date(rec.get("to"))
    return f"{_fmt(a)} – {'Present' if rec.get('present') else _fmt(b)}"


def _addr(rec):
    parts = [rec.get("street"), rec.get("city")]
    parts += [f"{rec.get('state', '')} {rec.get('zip', '')}".strip()] if rec.get("is_us") == "yes" else [rec.get("province"), rec.get("postal_code"), rec.get("country")]
    return ", ".join(p for p in parts if p)


def _name(rec):
    return " ".join(x for x in (rec.get("given"), rec.get("middle"), rec.get("family")) if x)


def history_records(a):
    return parse_records(a.get("r_history")) if a.get("r_other_addr") == "yes" else []


def additional_entries(a):
    """[{page, part, item, text, kind, private}] Part 11 entries implied by the structured answers (more than the printed form has room for, or a
    Yes answer that the form says to explain in Part 11) plus what the customer wrote. The customer is never asked for a page, part or item number."""
    out = []

    def add(page, part, item, kind, text, private=False):
        out.append({"page": page, "part": part, "item": item, "kind": kind, "text": text, "private": private})

    names = [r for r in parse_records(a.get("r_other_names")) if r.get("given") or r.get("family")]
    if len(names) > FORM_ROOM_OTHER_NAMES:
        add(1, 1, "2-3", "other_names", "Additional other names used (aliases, maiden name, nicknames): " + "; ".join(_name(r) for r in names[FORM_ROOM_OTHER_NAMES:]) + ".")
    for key, item, label in (("q18_details", "18", "removal, deportation, or rescission proceedings"), ("q19_details", "19", "fee paid to someone other than an attorney"),
                             ("q20_details", "20", "arrests, detentions, charges or similar"), ("q21_details", "21", "a different marriage than the one that gave conditional residence"),
                             ("q23_details", "23", "spouse or parent's spouse serving outside the United States")):
        yn = {"q18_details": "q18", "q19_details": "q19", "q20_details": "q20", "q21_details": "q21", "q23_details": "q23"}[key]
        if a.get(yn) == "yes" and str(a.get(key) or "").strip():
            add(2, 1, item, "explanation", f"Item {item} ({label}): " + str(a[key]).strip(), private=(key in ("q18_details", "q20_details")))
    hist = history_records(a)
    if hist:
        lines = [f"{_addr(r)} ({_period(r)})" for r in sorted(hist, key=lambda r: r.get("from") or "")]
        add(2, 1, "22", "residence_history", "Addresses where I have resided since becoming a permanent resident, with dates: " + "; ".join(lines) + ".")
    _first, extra = children_split(a)
    for i, kid in enumerate(extra, FORM_ROOM_CHILDREN + 1):
        where = {"with_me": "lives with the petitioner", "us": "lives at another U.S. address", "abroad": "lives outside the United States"}.get(kid.get("where"), "")
        addr = "" if kid.get("where") in (None, "with_me") else f" Address: {_addr(dict(kid, is_us='yes' if kid.get('where') == 'us' else 'no'))}."
        add(5, 5, f"Child {i}", "child", f"Child {i}: {child_name(kid)}. Date of birth: {_fmt(parse_date(kid.get('dob')))}. A-Number: {kid.get('a_number') or 'none'}. "
            f"Living with petitioner: {'Yes' if kid.get('where') == 'with_me' else 'No'} ({where}). Applying with petitioner: {'Yes' if kid.get('applying') == 'yes' else 'No'}.{addr}")
    if str(a.get("acc_persons") or "").strip():
        add(5, 6, "4", "accommodation", "Accommodation information for each person: " + str(a["acc_persons"]).strip(), private=True)
    if str(a.get("additional_information") or "").strip():
        add(None, None, None, "petitioner", str(a["additional_information"]).strip())
    return out


def entry_label(e, lang="en"):
    if e.get("page") is None:
        return "Petitioner's additional information (OG assigns the reference)" if lang != "es" else "Información adicional del peticionario (OG asigna la referencia)"
    return f"Page {e['page']}, Part {e['part']}, Item {e['item']}" if lang != "es" else f"Página {e['page']}, Parte {e['part']}, Ítem {e['item']}"


def preparer_statement():
    """(item, extends) from the CENTRAL OG configuration: Part 10 Item 7.a (not an attorney or accredited representative) or 7.b."""
    status = getattr(business_info, "PREPARER_STATUS", "not_attorney")
    if status in ("attorney", "accredited"):
        return "7.b", getattr(business_info, "PREPARER_REPRESENTATION_EXTENDS", "") or ""
    return "7.a", ""


def history_status(a, field=None, today=None):
    """('ok' | 'gaps' | 'none' | 'na', analysis) for the residence history since the customer became a resident. 'na' when Item 22 is No."""
    if a.get("r_other_addr") != "yes":
        return "na", None
    records = parse_records(a.get("r_history"))
    if not records:
        return "none", None
    cfg = {"record": "address", "max": 20, "timeline": {"years": 5, "gap_days": 3, "overlap_days": 31, "since_field": "r_resident_since"}}
    if field is not None:
        cfg = field_config(field)
    result = analyze_records(cfg, records, "en", today=today, since=since_from_answers(cfg, a))
    return ("ok" if result["complete"] else "gaps"), result


def calculated(a, submission=None):
    field = None
    if submission is not None:
        field = next((f for f in submission.form.all_fields if f.internal_name == "r_history"), None)
    item, extends = preparer_statement()
    status, _ = history_status(a, field)
    first, extra = children_split(a)
    return {
        "c_route": route(a),
        "c_basis": json.dumps(basis(a)),
        "c_part8": part8_applies(a),
        "c_p4_role": p4_role(a),
        "c_kids": str(len(first) + len(extra)),
        "c_kids_applying": str(len(applying_children(a))),
        "c_hist": status,
        "c_addl": json.dumps(additional_entries(a), ensure_ascii=False),
        "prep_status": item,
        "prep_extends": extends,
    }
