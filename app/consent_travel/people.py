"""People of a Consent to Travel case: every child and every adult involved is a REAL Person (reused across
cases). The account holder is not assumed to be any particular adult — `your_role` (asked in the interview)
says whether the customer themself IS the mother / the traveling father / the accompanying third person, in
which case that adult's own Person (self) is reused; otherwise a new/named Person is created for them, the
same "self vs. a named person" resolution Tax already uses for a spouse.

Scopes this module resolves (`owner_for`):
  "mother"          — always relevant (traveler, or an always-consenting reference point, or a consenting
                       parent), self-resolved when your_role == "mother".
  "father_traveler" — only when traveling_with == "father" (he IS the traveler), self-resolved when
                       your_role == "father".
  "third_traveler"  — only when traveling_with == "other" (the accompanying adult), self-resolved when
                       your_role == "accompanying".
  "record"          — a child (given/family/dob bound the same way Tax binds a dependent) or a synced
                       consenting-adult record (whose owner is simply the Person already linked to it).
A per-child father (only relevant when traveling_with in mother/other) is resolved separately — see
`ensure_child_father` — because a case can have more than one distinct father across different children.
"""

from app import cases as case_svc
from app import persons as pers
from app.extensions import db
from app.models import CasePerson, Person

SOURCE_REF = "Consent to Travel"
ADDRESS_KEYS = {"street": "street", "unit_number": "unit_number", "city": "city", "state": "state", "zip": "zip"}


def _norm(text):
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


def self_person(ct):
    return pers.self_person(ct.case.customer)


def case_person(ct, person, relationship="other"):
    cp = pers.case_person_for(ct.case, person, relationship_key=relationship)
    db.session.flush()
    return cp


def _named_person(ct, key, given, family, relationship):
    """A case-level named adult (mother / father_traveler / third_traveler) — resolved once, reused on every
    later save. `key` is the answers dict slot used to remember which Person we picked/created ("_mother_pid" etc.)."""
    answers = ct.answers
    pid = answers.get(f"_{key}_pid")
    if pid:
        p = Person.query.filter_by(id=pid, customer_id=ct.case.customer_id).first()
        if p is not None:
            if given and family and (p.given_name != given or p.family_name != family):
                p.given_name, p.family_name = given, family
            return p
    if not (given and family):
        return None
    match = find_match(ct.case.customer, given, family, None)
    if match is not None:
        case_person(ct, match, "other")
        person = match
    else:
        cp = case_svc.add_person(ct.case, given, family, relationship, actor="customer", actor_id=ct.case.customer_id)
        person = pers.owner_of(cp)
    answers[f"_{key}_pid"] = person.id
    ct.answers = answers
    return person


def owner_for(ct, scope, record=None):
    if scope == "mother":
        if ct.answers.get("your_role") == "mother":
            return self_person(ct)
        return _named_person(ct, "mother", ct.answers.get("mo_given"), ct.answers.get("mo_family"), "parent")
    if scope == "father_traveler":
        if ct.answers.get("your_role") == "father":
            return self_person(ct)
        return _named_person(ct, "father", ct.answers.get("fa_given"), ct.answers.get("fa_family"), "parent")
    if scope == "third_traveler":
        if ct.answers.get("your_role") == "accompanying":
            return self_person(ct)
        return _named_person(ct, "third", ct.answers.get("th_given"), ct.answers.get("th_family"), "other")
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


def set_fact(ct, owner, bind, value, field_name):
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
        db.session.flush()
        pers.confirm(owner, [key], None, actor="customer")
    elif pers.same(key, pers.fact_value(fact), value):
        if fact.last_confirmed_at is None:
            pers.confirm(owner, [key], None, actor="customer")
    else:
        pers.update(owner, key, value, None, actor="customer", source_field=field_name)


def find_match(customer, given, family, dob):
    if not (given and family):
        return None
    g, f = _norm(given), _norm(family)
    for p in Person.query.filter_by(customer_id=customer.id).all():
        if _norm(p.given_name) == g and _norm(p.family_name) == f:
            if dob:
                fact = pers.get_fact(p, "date_of_birth")
                if fact is None or str(pers.fact_value(fact)) != str(dob):
                    continue
            return p
    return None


def new_person(ct, given, family, relationship):
    cp = case_svc.add_person(ct.case, given, family, relationship, actor="customer", actor_id=ct.case.customer_id)
    return pers.owner_of(cp), cp


def ensure_child_person(ct, record, given, family, dob):
    """Link a child record to a real Person (matching or new). Mirrors `tax.people.ensure_dependent_person`."""
    if record.person is not None:
        person = pers.owner_of(record.person)
        if person.given_name != given or person.family_name != family:
            person.given_name, person.family_name = given, family
            record.person.given_name, record.person.family_name = given, family
        return person
    person = find_match(ct.case.customer, given, family, dob)
    if person is not None:
        cp = case_person(ct, person, "child")
    else:
        person, cp = new_person(ct, given, family, "child")
    record.person_id = cp.id
    db.session.flush()
    db.session.refresh(record)
    return person


def known_fathers(ct, exclude_child_id=None):
    """[{person_id, name}] — the distinct fathers already identified on OTHER children in this same case, so
    a second child with the same father is never asked to re-type his name (item: parentage evaluated per
    child, but siblings normally share a father)."""
    seen, out = {}, []
    for r in ct.children:
        if r.id == exclude_child_id:
            continue
        fpid = r.data.get("father_pid")
        if fpid and fpid not in seen:
            p = Person.query.filter_by(id=fpid, customer_id=ct.case.customer_id).first()
            if p is not None:
                seen[fpid] = True
                out.append({"person_id": fpid, "name": f"{p.given_name} {p.family_name}".strip()})
    return out


def ensure_child_father(ct, record, *, reuse_pid=None, given=None, family=None):
    """The per-child father Person (only when this child's father is on the certificate). Reused across
    siblings via `reuse_pid` (an id `known_fathers` offered), or created new from a typed name."""
    if reuse_pid:
        p = Person.query.filter_by(id=reuse_pid, customer_id=ct.case.customer_id).first()
        if p is not None:
            case_person(ct, p, "parent")
            d = record.data
            d["father_pid"] = p.id
            record.data = d
            return p
    if not (given and family):
        return None
    match = find_match(ct.case.customer, given, family, None)
    if match is not None:
        case_person(ct, match, "parent")
        person = match
    else:
        person, _cp = new_person(ct, given, family, "parent")
    d = record.data
    d["father_pid"] = person.id
    record.data = d
    return person


def info(ct, record):
    """{given, family} of a child record (from its Person)."""
    owner = owner_for(ct, "record", record)
    if owner is None:
        return {"given": None, "family": None}
    return {"given": owner.given_name, "family": owner.family_name}


def person_by_id(ct, pid):
    return Person.query.filter_by(id=pid, customer_id=ct.case.customer_id).first() if pid else None
