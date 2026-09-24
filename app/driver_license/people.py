"""The NJ Driver License applicant is always the customer themself (no dependents/spouse in this service). Stable facts (name, date of
birth, phone, email, NJ address) live on the customer's own Person — same real-person layer every other intake uses — so this service
never asks for something OG already has current, and any correction here is recorded as an explicit update, never a silent overwrite."""

from app import persons as pers

ADDRESS_KEYS = {"street": "street", "unit_number": "unit_number", "city": "city", "state": "state", "zip": "zip"}
SOURCE_REF = "NJ Driver License"


def self_person(dl):
    return pers.self_person(dl.case.customer)


def get_fact(owner, bind):
    if owner is None:
        return None
    key, _, sub = bind.partition(".")
    fact = pers.get_fact(owner, "current_address" if key == "address" else key)
    if fact is None:
        return None
    val = pers.fact_value(fact)
    if key == "address":
        return (val or {}).get(ADDRESS_KEYS.get(sub, sub)) if isinstance(val, dict) else None
    return val


def set_fact(owner, bind, value, field_name):
    if owner is None or value in (None, ""):
        return
    key, _, sub = bind.partition(".")
    if key == "address":
        fact = pers.get_fact(owner, "current_address")
        current = dict(pers.fact_value(fact)) if fact is not None and isinstance(pers.fact_value(fact), dict) else {}
        if current.get(ADDRESS_KEYS.get(sub, sub)) == value:
            return
        current[ADDRESS_KEYS.get(sub, sub)] = value
        current["is_us"] = "yes"
        current["country"] = "United States"
        key, value = "current_address", current
    fact = pers.get_fact(owner, key)
    if fact is None:
        pers.record_claim(owner, key, value, None, field_name=field_name, source_ref=SOURCE_REF)
        from app.extensions import db

        db.session.flush()
        pers.confirm(owner, [key], None, actor="customer")
    elif pers.same(key, pers.fact_value(fact), value):
        if fact.last_confirmed_at is None:
            pers.confirm(owner, [key], None, actor="customer")
    else:
        pers.update(owner, key, value, None, actor="customer", source_field=field_name)


def mask_ssn(value):
    d = "".join(ch for ch in str(value or "") if ch.isdigit())
    return f"•••-••-{d[-4:]}" if len(d) >= 4 else ""
