"""The CEAC-ready layer and the Admin CEAC Preparation View for one DS-260 application.

The customer may answer in Spanish, but the Department of State requires English and English characters. For every answer this module keeps, side by side:
  customer_display  what the customer entered / confirmed (their language)
  canonical         the stored value
  ceac_ready        the English, CEAC-formatted value staff type into CEAC (never auto-translated: proper names and native names are only ASCII-folded, and
                    free text that looks like Spanish is FLAGGED "needs English text" until staff enters or approves an English version)
  provenance        where the value came from (typed, confirmed shared data, linked Person, source form/date)
  confirmation      confirmed / updated / typed / conflict / unconfirmed
plus the CEAC section and question, the source snapshot, and review flags. Nothing here fills, submits or automates CEAC; it only prepares what a person types.
"""

import json
import unicodedata
from collections import OrderedDict
from datetime import datetime

from app import cases as case_svc
from app import persons as pers
from app.extensions import db
from app.intake_engine import review_sections
from app.intake_records import RECORD_TYPES, field_config, parse_date, parse_records
from app.models import Ds260CeacOverride

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
CEAC_SECTIONS = [
    "Personal 1", "Personal 2", "Address and Phone", "Mailing / Permanent", "Family: Parents", "Family: Spouse", "Family: Previous Spouse", "Family: Children", "Previous U.S. Travel",
    "Work/Education/Training: Present", "Work/Education/Training: Previous", "Work/Education/Training: Additional", "Petitioner",
    "Security and Background: Medical and Health", "Security and Background: Criminal", "Security and Background: Security 1", "Security and Background: Security 2",
    "Security and Background: Immigration Law Violations 1", "Security and Background: Immigration Law Violations 2", "Security and Background: Miscellaneous 1",
    "Security and Background: Miscellaneous 2", "Social Security Number", "Sign and Submit (preparer of application)",
]
PRIVATE_PREFIX = "Security and Background"
_SPANISH = {"el", "la", "los", "las", "de", "del", "que", "con", "por", "para", "una", "un", "y", "en", "mi", "su", "fue", "hace", "porque", "pero", "muy", "tengo", "tuve", "trabajo", "trabajé"}


def fold(text):
    """(ASCII text, changed?) — accents and ñ folded the way CEAC expects (Muñoz -> Munoz). Nothing is translated."""
    text = str(text or "")
    out = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return out, out != text


def looks_spanish(text):
    words = [w.strip(".,;:!?¿¡()\"'").lower() for w in str(text or "").split()]
    return sum(1 for w in words if w in _SPANISH) >= 2 or any(ord(ch) > 127 and ch.isalpha() for ch in str(text or ""))


def ceac_date(value, month_year=False):
    d = parse_date(value)
    if d is None:
        return str(value or "")
    return f"{MONTHS[d.month - 1]}-{d.year}" if month_year else f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year}"


def _option_label(field_or_options, value):
    for v, en, _es in field_or_options:
        if v == value:
            return en
    return str(value or "")


def _mask(value, keep=4):
    value = str(value or "")
    return ("•" * max(len(value) - keep, 0) + value[-keep:]) if len(value) > keep else ("•" * len(value))


def transform(t, raw, options=None, *, lang="en", sensitive=False):
    """(ceac_ready value, [flags]) for one raw answer with transform key `t`."""
    flags = []
    raw = "" if raw is None else raw
    if t in ("yn",):
        return {"yes": "Yes", "no": "No"}.get(str(raw), str(raw)), flags
    if t == "choice":
        if isinstance(raw, list):
            return "; ".join(_option_label(options or [], v) for v in raw), flags
        return _option_label(options or [], raw), flags
    if t == "date":
        return ceac_date(raw), flags
    if t == "month_year":
        return ceac_date(raw, month_year=True), flags
    if t == "ssn":
        return "".join(ch for ch in str(raw) if ch.isdigit()), flags
    if t in ("phone", "raw"):
        return str(raw), flags
    if t == "native":
        return str(raw), (["native"] if raw else [])
    text, changed = fold(raw)
    if changed:
        flags.append("chars")
    if t == "name":
        return text.upper(), flags
    if t == "free" and raw and (looks_spanish(raw) or lang == "es"):
        flags.append("translate")
    return text, flags


def _field_options(field):
    return [(o.value, o.label_en, o.label_es) for o in field.options] if field is not None else []


def _override_map(submission):
    return {o.field_key: o for o in submission.ceac_overrides}


def set_override(submission, key, value, staff_name):
    row = next((o for o in submission.ceac_overrides if o.field_key == key), None)
    if row is None:
        row = Ds260CeacOverride(submission_id=submission.id, field_key=key)
        db.session.add(row)
    row.value_text = value
    row.reviewed_by = staff_name
    row.reviewed_at = datetime.utcnow()
    db.session.commit()
    return row


def clear_override(submission, key):
    for o in list(submission.ceac_overrides):
        if o.field_key == key:
            db.session.delete(o)
    db.session.commit()


def _fact_map(form):
    from app.case_types import FORM_CASE_CONFIG

    out = {}
    for fact_key, target in FORM_CASE_CONFIG["DS-260"]["facts"]["applicant"].items():
        if isinstance(target, str):
            out[target] = fact_key
        elif isinstance(target, dict) and "address_prefix" in target:
            out[target["address_prefix"] + "_"] = fact_key
    return out


def _fact_for_field(facts, name):
    if name in facts:
        return facts[name]
    for prefix, key in facts.items():
        if prefix.endswith("_") and name.startswith(prefix):
            return key
    return None


def _confirmation(cfgj, stored, name, conflicts, fact_key):
    block = cfgj.get("block")
    if fact_key and fact_key in conflicts:
        return "conflict"
    if block:
        choice = stored.get(block)
        if choice in ("correct", "edit"):
            return {"correct": "confirmed", "edit": "updated"}[choice]
        return "unconfirmed" if stored.get(f"{block}_avail") == "yes" else "typed"  # only reused data waits for a confirmation; typed data is the customer's own
    return "typed"


def _prov(person, fact_key, cfgj, stored):
    bits = []
    block = cfgj.get("block")
    if block:
        choice = stored.get(block)
        bits.append({"correct": "Shared data — customer confirmed it", "edit": "Shared data — customer changed it"}.get(choice, "Shared data — not yet confirmed"))
    if person is not None and fact_key:
        fact = pers.get_fact(person, fact_key)
        if fact is not None:
            src = getattr(fact, "source_form", None) or ""
            when = getattr(fact, "last_confirmed_at", None)
            bits.append("first recorded from " + (src or "another application") + (f", last confirmed {when.strftime('%Y-%m-%d')}" if when else ", never confirmed"))
    return "; ".join(bits)


def build(submission, lang="en"):
    """{"sections": [{title, rows, private, flags}], "source", "counts", "blockers", "warnings"} for the Admin CEAC Preparation View."""
    from app.case_types import FORM_CASE_CONFIG  # noqa: F401
    from app.intake_engine import answers_for

    form = submission.form
    ceac = (form.features or {}).get("ceac") or {}
    stored = case_svc.answers_by_name(submission)
    overrides = _override_map(submission)
    applicant = case_svc.role_person(submission, "visa_applicant")
    owner = pers.owner_of(applicant) if applicant is not None else None
    conflicts = {f.fact_key for f in pers.open_conflicts(person=owner)} if owner is not None else set()
    facts = _fact_map(form)
    es_session = (submission.language or "en") == "es"
    entries = []
    for section in review_sections(form, submission, "en", reveal=True):
        for it in section["items"]:
            field = it["field"]
            meta = ceac.get(field.internal_name)
            if not meta or meta.get("hide"):
                continue
            entries.append((meta, field, it))
    entries.sort(key=lambda e: e[0].get("n", 0))
    grouped = OrderedDict((title, []) for title in CEAC_SECTIONS)
    for meta, field, it in entries:
        name = field.internal_name
        cfgj = json.loads(field.config_json) if field.config_json else {}
        fact_key = _fact_for_field(facts, name)
        confirm = _confirmation(cfgj, stored, name, conflicts, fact_key)
        prov = _prov(owner, fact_key, cfgj, stored)
        raw = stored.get(name)
        sensitive = bool(field.is_sensitive)
        base_flags = []
        if meta.get("unv"):
            base_flags.append("unverified")
        if meta.get("sec_key"):
            base_flags.append("review") if raw == ("yes" if meta.get("polarity", "yes") == "yes" else "no") else None
        rows = []
        if field.field_type == "record_list":
            rows.extend(_record_rows(submission, field, meta, raw, base_flags, confirm, prov, overrides, es_session, sensitive))
        else:
            options = _field_options(field)
            blank = raw in (None, "", [])
            key = name
            ov = overrides.get(key)
            if blank:
                if meta.get("dna"):
                    value, flags = "Does Not Apply", ["dna"]
                elif meta.get("dk"):
                    value, flags = "Do Not Know", ["dk"]
                elif it["required"]:
                    value, flags = "", ["missing"]
                else:
                    continue
            else:
                value, flags = transform(meta.get("t", "raw"), raw, options, lang="es" if es_session else "en", sensitive=sensitive)
            if name == "ssn_number" and stored.get("ssn_dk") == ["dk"]:
                value, flags = "Do Not Know", ["dk"]
            flags = base_flags + flags
            if ov is not None:
                value, flags = ov.value_text or "", [f for f in flags if f != "translate"] + ["override"]
            rows.append(_row(key, meta, it, value, raw, flags, confirm, prov, sensitive, ov, options))
        for r in rows:
            grouped.setdefault(meta["sec"], []).append(r)
    sections = []
    for title, rows in grouped.items():
        if not rows:
            continue
        sections.append({"title": title, "rows": rows, "private": title.startswith(PRIVATE_PREFIX), "flags": sum(1 for r in rows if r["flags"] and set(r["flags"]) & {"missing", "translate", "conflict", "review", "unconfirmed"})})
    counts = {"rows": sum(len(s["rows"]) for s in sections),
              "missing": sum(1 for s in sections for r in s["rows"] if "missing" in r["flags"]),
              "translate": sum(1 for s in sections for r in s["rows"] if "translate" in r["flags"]),
              "conflict": sum(1 for s in sections for r in s["rows"] if r["confirm"] == "conflict"),
              "unconfirmed": sum(1 for s in sections for r in s["rows"] if r["confirm"] == "unconfirmed"),
              "review": sum(1 for s in sections for r in s["rows"] if "review" in r["flags"])}
    row = submission.ds260
    src = row.source if row is not None else None
    blockers, warnings = [], []
    if not submission.is_complete:
        blockers.append("The customer has not sent this DS-260 to OG yet.")
    if counts["missing"]:
        blockers.append(f"{counts['missing']} answer(s) are still missing.")
    if counts["conflict"]:
        blockers.append(f"{counts['conflict']} value(s) conflict with different information in a previous OG application (resolve it first).")
    if counts["translate"]:
        warnings.append(f"{counts['translate']} free-text answer(s) need an English version approved by staff.")
    if counts["unconfirmed"]:
        warnings.append(f"{counts['unconfirmed']} reused value(s) were not confirmed by the customer.")
    return {"sections": sections, "counts": counts, "blockers": blockers, "warnings": warnings,
            "source": {"code": src.code, "label": src.source_label, "sample": src.sample_date, "verified": src.verified_at, "hash": (src.schema_hash or "")[:12]} if src is not None else None}


def _row(key, meta, it, value, raw, flags, confirm, prov, sensitive, ov, options, sub=None):
    display = it["value"] if it is not None else ""
    return {"key": key, "q": meta.get("label"), "customer": display if not sensitive else _mask(display), "canonical": str(raw if not isinstance(raw, (list, dict)) else json.dumps(raw, ensure_ascii=False)) if not sensitive else _mask(raw),
            "ceac": value, "flags": flags, "confirm": confirm, "prov": prov, "source": it["field"].source_ref if it is not None else "", "sensitive": sensitive,
            "override": ({"by": ov.reviewed_by, "at": ov.reviewed_at} if ov is not None else None), "copy": bool(value) and value != "MISSING", "sub": sub}


def _record_rows(submission, field, meta, raw, base_flags, confirm, prov, overrides, es_session, sensitive):
    cfg = field_config(field)
    spec = RECORD_TYPES[cfg["record"]]
    records = parse_records(raw)
    rows = []
    label = meta.get("label")
    if not records:
        return rows
    dk_ok = set(meta.get("dk") or [])
    for i, rec in enumerate(records, 1):
        for f in spec["fields"]:
            if f.get("internal") or f["name"] == "person_id":
                continue
            show = f.get("show_if")
            if show and rec.get(show["field"]) not in show["values"]:
                continue
            value_raw = rec.get(f["name"])
            key = f"{field.internal_name}#{i}.{f['name']}"
            ov = overrides.get(key)
            flags = list(base_flags)
            if value_raw in (None, ""):
                if f["name"] in dk_ok:
                    value, flags = "Do Not Know", flags + ["dk"]
                elif f["required"]:
                    value, flags = "", flags + ["missing"]
                else:
                    continue
            elif f["type"] == "date":
                value = ceac_date(value_raw)
            elif f["type"] in ("select", "choice"):
                value = _option_label(f["options"], value_raw)
            else:
                value, fl = transform("proper", value_raw)
                flags += fl
            if ov is not None:
                value, flags = ov.value_text or "", [x for x in flags if x != "translate"] + ["override"]
            title = f"{label} #{i} — {f['label']['en']}" if len(records) > 1 else f"{label} — {f['label']['en']}"
            rows.append({"key": key, "q": title, "customer": str(value_raw or ""), "canonical": str(value_raw or ""), "ceac": value, "flags": flags, "confirm": confirm if rec.get("person_id") or confirm != "typed" else "typed",
                         "prov": ("Linked to an existing Person" if rec.get("person_id") else prov), "source": field.source_ref, "sensitive": sensitive, "copy": bool(value),
                         "override": ({"by": ov.reviewed_by, "at": ov.reviewed_at} if ov is not None else None), "sub": None})
    return rows


def readiness(submission):
    data = build(submission)
    return {"blockers": data["blockers"], "warnings": data["warnings"], "ready": not data["blockers"]}
