"""People of a tax case: the taxpayer, the spouse and each potential dependent are REAL Persons (reused across cases and years). Their stable facts (name, date of birth,
SSN / ITIN, contact, address) live on the Person; year-specific facts live in the tax case. The customer explicitly types or confirms every value in the interview, so a
value that differs from the Person's confirmed fact is an intentional update (recorded with history), not a silent overwrite.

Matching is conservative: a Person is only re-used when the customer picks one, or when first + last name AND date of birth are exactly the same as a Person the customer
already has.
"""

from datetime import datetime

from app import cases as case_svc
from app import persons as pers
from app.extensions import db
from app.models import CasePerson, Person

SOURCE_REF = "Tax Return {year}"
ADDRESS_KEYS = {"street": "street", "unit_number": "unit_number", "city": "city", "state": "state", "zip": "zip"}


def _norm(text):
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


def self_person(tax):
    return pers.self_person(tax.case.customer)


def case_person(tax, person, relationship="other"):
    cp = pers.case_person_for(tax.case, person, relationship_key=relationship)
    db.session.flush()
    return cp


def spouse_person(tax):
    pid = tax.answers.get("_spouse_pid")
    return db.session.get(Person, pid) if pid and db.session.get(Person, pid) is not None and db.session.get(Person, pid).customer_id == tax.case.customer_id else None


def owner_for(tax, scope, record=None):
    if scope == "self":
        return self_person(tax)
    if scope == "spouse":
        return spouse_person(tax)
    if scope == "record" and record is not None and record.person is not None:
        return pers.owner_of(record.person)
    return None


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


def has_fact(owner, bind):
    return bool(get_fact(owner, bind))


def set_fact(tax, owner, bind, value, field_name):
    """Write a value the customer typed/confirmed to the Person. New -> claim + confirm; different -> explicit update (history kept); same -> confirm."""
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
    ref = SOURCE_REF.format(year=tax.tax_year)
    if fact is None:
        pers.record_claim(owner, key, value, None, field_name=field_name, source_ref=ref)
        db.session.flush()
        pers.confirm(owner, [key], None, actor="customer")
    elif pers.same(key, pers.fact_value(fact), value):
        if fact.last_confirmed_at is None:
            pers.confirm(owner, [key], None, actor="customer")
    else:
        pers.update(owner, key, value, None, actor="customer", source_field=field_name)


def find_match(customer, given, family, dob):
    """An existing Person of this customer with exactly the same first + last name and date of birth, else None."""
    if not (given and family and dob):
        return None
    g, f = _norm(given), _norm(family)
    for p in Person.query.filter_by(customer_id=customer.id).all():
        if _norm(p.given_name) == g and _norm(p.family_name) == f:
            fact = pers.get_fact(p, "date_of_birth")
            if fact is not None and str(pers.fact_value(fact)) == str(dob):
                return p
    return None


def known_people(tax, exclude_ids=()):
    """The customer's other real people (for the "someone OG already knows" picker)."""
    return [p for p in Person.query.filter_by(customer_id=tax.case.customer_id, is_self=False).order_by(Person.id).all() if p.id not in exclude_ids]


def new_person(tax, given, family, relationship):
    cp = case_svc.add_person(tax.case, given, family, relationship, actor="customer", actor_id=tax.case.customer_id)
    return pers.owner_of(cp), cp


def ensure_dependent_person(tax, record, given, family, dob):
    """Link the dependent record to a real Person (matching or new). Called once names exist."""
    if record.person is not None:
        person = pers.owner_of(record.person)
        if person.given_name != given or person.family_name != family:
            person.given_name, person.family_name = given, family
            record.person.given_name, record.person.family_name = given, family
        return person
    person = find_match(tax.case.customer, given, family, dob)
    if person is not None:
        cp = case_person(tax, person, "child")
    else:
        person, cp = new_person(tax, given, family, "child")
    record.person_id = cp.id
    db.session.flush()
    db.session.refresh(record)
    return person


def ensure_spouse_person(tax, given, family, dob, picked_id=None):
    answers = tax.answers
    pid = answers.get("_spouse_pid")
    person = spouse_person(tax)
    if person is None:
        if picked_id:
            person = Person.query.filter_by(id=picked_id, customer_id=tax.case.customer_id, is_self=False).first()
        if person is None:
            person = find_match(tax.case.customer, given, family, dob)
        if person is None:
            person, _cp = new_person(tax, given, family, "spouse")
        else:
            case_person(tax, person, "spouse")
        answers["_spouse_pid"] = person.id
        tax.answers = answers
    elif pid == person.id and (person.given_name != given or person.family_name != family):
        person.given_name, person.family_name = given, family
    return person


def info(tax, record):
    """{given, family, dob(date)} of a dependent record (from its Person), for age rules and household lists."""
    from app.tax.questions import parse_date

    owner = owner_for(tax, "record", record)
    if owner is None:
        return {"given": None, "family": None, "dob": None}
    dob = get_fact(owner, "date_of_birth")
    try:
        dob = parse_date(dob) if dob else None
    except ValueError:
        dob = None
    return {"given": owner.given_name, "family": owner.family_name, "dob": dob}


def mask_ssn(value):
    d = "".join(ch for ch in str(value or "") if ch.isdigit())
    return f"•••-••-{d[-4:]}" if len(d) >= 4 else ""
