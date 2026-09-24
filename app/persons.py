"""Real-person identity, fact claims, conflicts and reuse offers.

  Customer -> Person (a real human, once per customer) -> CasePerson (that person in ONE case) -> ApplicationRole (what they do in ONE application)

Facts belong to the Person, so they can follow the same human across cases. Each application that states a fact leaves a CLAIM
(value + provenance + the state of the source application). The canonical fact keeps its own confirmation history; historical
application answers are never rewritten.

Scopes (app/case_types.py FACT_SCOPE):
  stable       identity facts. Different values from different sources are a CONFLICT that is never resolved silently.
  situational  address / phone / employment / I-94 ...: reusable with their date, always confirmed again, a newer value is not a conflict.

Reuse is always offered, never copied blindly: `offer()` says what could be reused for ONE application (never its own claims),
and the application's shared-data step asks the customer to confirm, edit, or resolve a conflict.
"""

import json
from datetime import datetime, timedelta

from app.case_types import FACTS, STALE_DAYS, conflict_capable, scope_of
from app.extensions import db
from app.models import CasePerson, Person, PersonFact, PersonFactClaim, PersonFactEvent, PersonFactUse


# ------------------------------------------------------------------ helpers
def _dump(value):
    return json.dumps(value, ensure_ascii=False)


def _load(raw):
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return raw


def same(key, a, b):
    from app.cases import _same

    return _same(key, a, b)


def fact_value(fact):
    return _load(fact.value_json)


def sub_state(submission):
    if submission is None:
        return "manual"
    if submission.is_complete:
        return "submitted"
    if submission.status == "reopened":
        return "reopened"
    return "draft"


STATE_LABELS = {
    "draft": ("unfinished application", "solicitud sin terminar"), "submitted": ("submitted application", "solicitud enviada"),
    "reopened": ("application reopened for editing", "solicitud reabierta para edición"), "manual": ("entered by you", "ingresado por ti"),
}


# ------------------------------------------------------------------ identity
def self_person(customer, given=None, family=None):
    """The customer's own real-person record (created once)."""
    person = Person.query.filter_by(customer_id=customer.id, is_self=True).first()
    if person is None:
        if not (given or family):
            from app.cases import split_name

            given, family = split_name(customer.name)
        person = Person(customer_id=customer.id, is_self=True, given_name=given, family_name=family)
        db.session.add(person)
        db.session.flush()
    return person


def ensure_person(case_person):
    """The real Person a CasePerson represents (linked at creation; this is the safety net for anything older)."""
    if case_person.person_id is not None and case_person.person is not None:
        return case_person.person
    case = case_person.case
    if case_person.is_customer or (case_person.student_id and case_person.student_id == case.customer_id):
        person = self_person(case.customer, case_person.given_name, case_person.family_name)
    else:
        person = Person(customer_id=case.customer_id, given_name=case_person.given_name, family_name=case_person.family_name)
        db.session.add(person)
        db.session.flush()
    case_person.person = person
    db.session.flush()
    return person


def owner_of(who):
    return who if isinstance(who, Person) else ensure_person(who)


def case_person_for(case, person, *, template=None, relationship_key=None):
    """The CasePerson representing `person` in `case` (created and LINKED to that person when the case has none yet).
    The link is explicit: a Person is never matched to a CasePerson by name."""
    for cp in case.people:
        if cp.person_id == person.id:
            return cp
    is_self = bool(person.is_self)
    cp = CasePerson(case_id=case.id, person_id=person.id, is_customer=is_self, student_id=case.customer_id if is_self else None,
                    relationship_key=("self" if is_self else (relationship_key or (template.relationship_key if template is not None else "other"))),
                    given_name=person.given_name, family_name=person.family_name)
    db.session.add(cp)
    db.session.flush()
    case.people.append(cp)
    return cp


def link_case_person(case_person, person):
    """Explicitly declare that this CasePerson IS `person` (same customer only). Existing facts of both merge into the Person."""
    if person.customer_id != case_person.case.customer_id:
        raise ValueError("A person can only be linked inside one customer's data.")
    old = case_person.person
    if old is not None and old.id == person.id:
        return person
    if old is not None and old.is_self != person.is_self and (old.is_self or person.is_self):
        raise ValueError("The customer's own person cannot be merged with someone else.")
    case_person.person = person
    db.session.flush()
    if old is not None and not old.case_people and old.id != person.id:
        merge_facts(old, person)
        db.session.delete(old)
    db.session.commit()
    return person


def merge_facts(src, dst):
    """Move every fact of `src` into `dst`, keeping BOTH sides' claims (a difference becomes a conflict, never a silent choice)."""
    for fact in list(src.facts):
        target = PersonFact.query.filter_by(real_person_id=dst.id, fact_key=fact.fact_key).first()
        if target is None:
            fact.real_person_id = dst.id
            continue
        for claim in list(fact.claims):
            existing = PersonFactClaim.query.filter_by(fact_id=target.id, submission_id=claim.submission_id).first() if claim.submission_id else None
            if existing is None:
                claim.fact_id = target.id
            else:
                db.session.delete(claim)
        for ev in list(fact.events):
            ev.fact_id = target.id
        for use in list(fact.uses):
            dup = PersonFactUse.query.filter_by(fact_id=target.id, submission_id=use.submission_id, field_name=use.field_name).first()
            if dup is None:
                use.fact_id = target.id
            else:
                db.session.delete(use)
        db.session.flush()
        db.session.expire(fact)
        db.session.delete(fact)
        db.session.flush()
        evaluate(target)


# ------------------------------------------------------------------ facts + claims
def get_fact(owner, key):
    return PersonFact.query.filter_by(real_person_id=owner.id, fact_key=key).first()


def record_use(fact, submission, field_name=None):
    if submission is None:
        return
    use = PersonFactUse.query.filter_by(fact_id=fact.id, submission_id=submission.id, field_name=field_name).first()
    if use is None:
        db.session.add(PersonFactUse(fact_id=fact.id, submission_id=submission.id, field_name=field_name))
    else:
        use.last_used_at = datetime.utcnow()


def _event(fact, kind, submission, actor, old=None, new=None):
    db.session.add(PersonFactEvent(fact_id=fact.id, kind=kind, old_value_json=old, new_value_json=new,
                                   submission_id=submission.id if submission is not None else None, actor=actor))


def record_claim(who, key, value, submission, field_name=None, source_ref=None):
    """One application states a fact for the real person behind `who`. Provenance is kept per application; the canonical value
    never silently changes to a different value once someone confirmed it."""
    if value in (None, "", {}, []):
        return None
    owner = owner_of(who)
    form_name = submission.form.source_form_name if submission is not None else None
    origin = who if isinstance(who, CasePerson) else None
    fact = get_fact(owner, key)
    if fact is None:
        fact = PersonFact(person_id=origin.id if origin is not None else None, real_person_id=owner.id, fact_key=key, value_json=_dump(value),
                          is_sensitive=bool(FACTS[key].get("sensitive")), source_submission_id=submission.id if submission is not None else None,
                          source_form=form_name, source_field=field_name, source_ref=source_ref)
        db.session.add(fact)
        db.session.flush()
        _event(fact, "recorded", submission, submission.code if submission is not None else "system", new=fact.value_json)
    claim = (PersonFactClaim.query.filter_by(fact_id=fact.id, submission_id=submission.id).first() if submission is not None else None)
    now = datetime.utcnow()
    if claim is None:
        db.session.add(PersonFactClaim(fact_id=fact.id, submission_id=submission.id if submission is not None else None, source_form=form_name,
                                       source_field=field_name, source_ref=source_ref, value_json=_dump(value), state=sub_state(submission),
                                       recorded_at=now, updated_at=now))
    else:
        if not same(key, _load(claim.value_json), value):
            claim.value_json, claim.updated_at, claim.resolved = _dump(value), now, False
        claim.state = sub_state(submission)
    db.session.flush()
    db.session.expire(fact, ["claims"])
    evaluate(fact, submission)
    record_use(fact, submission, field_name)
    return fact


def refresh_states(submission):
    """Application state changed (submitted / reopened / resubmitted): its claims carry the new state."""
    state = sub_state(submission)
    n = 0
    for claim in PersonFactClaim.query.filter_by(submission_id=submission.id).all():
        if claim.state != state:
            claim.state = state
            n += 1
    return n


def _groups(key, claims):
    out = []
    for c in sorted(claims, key=lambda c: (c.updated_at or c.recorded_at), reverse=True):
        v = _load(c.value_json)
        for g in out:
            if same(key, g["value"], v):
                g["claims"].append(c)
                break
        else:
            out.append({"value": v, "claims": [c]})
    return out


def evaluate(fact, submission=None):
    """Recompute whether the fact is settled or in conflict, and follow a single unconfirmed source. Never overwrites a
    confirmed value."""
    key = fact.fact_key
    claims = list(fact.claims)
    if not claims:
        return
    latest = max(claims, key=lambda c: (c.updated_at or c.recorded_at))
    if fact.last_confirmed_at is None:
        groups = _groups(key, claims) if conflict_capable(key) else [{"value": _load(latest.value_json), "claims": claims}]
        if len(groups) <= 1:
            new = latest.value_json
            if not same(key, _load(fact.value_json), _load(new)):
                _event(fact, "updated", submission, submission.code if submission is not None else "system", old=fact.value_json, new=new)
                fact.value_json = new
            fact.needs_review = False
        else:
            fact.needs_review = True
            for g in groups:
                dumped = _dump(g["value"])
                if not any(e.kind == "differs" and e.new_value_json == dumped for e in fact.events):
                    _event(fact, "differs", g["claims"][0].submission, g["claims"][0].source_form or "system", old=fact.value_json, new=dumped)
    else:
        if conflict_capable(key):
            conf = _load(fact.value_json)
            open_claims = [c for c in claims if (not c.resolved) and not same(key, _load(c.value_json), conf)]
            fact.needs_review = bool(open_claims)
            for c in open_claims:
                dumped = c.value_json
                if not any(e.kind == "differs" and e.new_value_json == dumped and e.submission_id == c.submission_id for e in fact.events):
                    _event(fact, "differs", c.submission, c.source_form or "system", old=fact.value_json, new=dumped)
        else:
            fact.needs_review = False


# ------------------------------------------------------------------ offers (what could be reused for ONE application)
def _src(c, fact):
    return {"form": c.source_form, "code": c.submission.code if c.submission is not None else None, "state": c.state,
            "at": c.updated_at or c.recorded_at, "ref": c.source_ref, "claim_id": c.id}


def offer(who, key, submission):
    """None | {status: single|conflict, value, options:[{value, sources}], confirmed, confirmed_at, scope, stale, draft_only, fact}
    Never uses the application's OWN claims (they are not something to "reuse")."""
    owner = owner_of(who)
    fact = get_fact(owner, key)
    if fact is None:
        return None
    others = [c for c in fact.claims if submission is None or c.submission_id != submission.id]
    conf = fact.last_confirmed_at
    own_confirmed = submission is not None and fact.confirmed_by == submission.code
    if not others and (not conf or own_confirmed):
        return None
    value = fact_value(fact)
    scope = scope_of(key)
    now = datetime.utcnow()
    groups = []
    if scope == "stable" and conflict_capable(key):
        if conf:
            base = {"value": value, "sources": [{"form": fact.source_form, "code": fact.source_submission.code if fact.source_submission else None,
                                                  "state": "confirmed", "at": conf, "ref": fact.source_ref, "claim_id": None}]}
            groups.append(base)
            pool = [c for c in others if not c.resolved]
        else:
            pool = others
        for g in _groups(key, pool):
            for existing in groups:
                if same(key, existing["value"], g["value"]):
                    existing["sources"] += [_src(c, fact) for c in g["claims"]]
                    break
            else:
                groups.append({"value": g["value"], "sources": [_src(c, fact) for c in g["claims"]]})
        if not conf and not groups:
            return None
        status = "conflict" if len(groups) >= 2 else "single"
        chosen = groups[0]
        stamp = conf or max((s["at"] for s in chosen["sources"] if s["at"]), default=None)
    else:
        latest = max(others, key=lambda c: (c.updated_at or c.recorded_at)) if others else None
        if latest is not None and (not conf or (latest.updated_at or latest.recorded_at) > conf):
            chosen = {"value": _load(latest.value_json), "sources": [_src(latest, fact)]}
            stamp = latest.updated_at or latest.recorded_at
            conf_ok = False
        else:
            chosen = {"value": value, "sources": [{"form": fact.source_form, "code": fact.source_submission.code if fact.source_submission else None,
                                                    "state": "confirmed", "at": conf, "ref": fact.source_ref, "claim_id": None}]}
            stamp = conf
        groups, status = [chosen], "single"
    is_conf = bool(conf) and status == "single" and same(key, chosen["value"], value)
    draft_only = all(s["state"] in ("draft", "reopened") for s in chosen["sources"]) and not is_conf
    return {"status": status, "value": chosen["value"], "options": groups, "confirmed": is_conf, "confirmed_at": conf if is_conf else None,
            "stamp": stamp, "scope": scope, "stale": scope == "situational" and stamp is not None and (now - stamp) > timedelta(days=STALE_DAYS),
            "draft_only": draft_only, "fact": fact}


# ------------------------------------------------------------------ decisions by the customer / OG
def confirm(who, keys, submission=None, actor="customer"):
    """The value currently stored is confirmed as still correct."""
    owner = owner_of(who)
    now = datetime.utcnow()
    n = 0
    for fact in owner.facts:
        if keys is not None and fact.fact_key not in keys:
            continue
        fact.last_confirmed_at, fact.confirmed_by = now, (submission.code if submission is not None else actor)
        for c in fact.claims:
            if same(fact.fact_key, _load(c.value_json), fact_value(fact)):
                c.resolved = True
        evaluate(fact, submission)
        _event(fact, "confirmed", submission, actor, new=fact.value_json)
        record_use(fact, submission)
        n += 1
    db.session.commit()
    return n


def update(who, key, value, submission=None, actor="customer", source_field=None):
    """The customer corrected/changed the value on purpose while looking at it: keep the ORIGINAL source, remember the old value
    (as a claim and in the history), settle earlier claims."""
    owner = owner_of(who)
    fact = get_fact(owner, key)
    if fact is None:
        return record_claim(who, key, value, submission, source_field)
    old = fact.value_json
    fact.value_json = _dump(value)
    fact.last_confirmed_at, fact.confirmed_by = datetime.utcnow(), (submission.code if submission is not None else actor)
    for c in fact.claims:
        c.resolved = True
    fact.needs_review = False
    _event(fact, "updated", submission, actor, old=old, new=fact.value_json)
    record_use(fact, submission)
    db.session.flush()
    if submission is not None:
        record_claim(who, key, value, submission, source_field)
        for c in PersonFactClaim.query.filter_by(fact_id=fact.id).all():
            c.resolved = True
    db.session.commit()
    return fact


def accept_offer(who, key, offered_value, submission, actor="customer"):
    """The customer confirmed the value we offered: identical to the canonical value -> confirm; a newer situational value -> it
    becomes the confirmed value."""
    owner = owner_of(who)
    fact = get_fact(owner, key)
    if fact is None:
        return None
    if same(key, fact_value(fact), offered_value):
        confirm(owner, [key], submission, actor)
    else:
        update(owner, key, offered_value, submission, actor)
    return get_fact(owner, key)


def resolve_conflict(who, key, submission, *, option_index=None, custom_value=None, actor="customer"):
    """The customer decided which value is correct (one of the sources, or a different one). Both historical values keep their
    provenance as claims; nothing in any application is rewritten."""
    owner = owner_of(who)
    fact = get_fact(owner, key)
    off = offer(owner, key, submission)
    if fact is None or off is None or off["status"] != "conflict":
        return None
    if custom_value not in (None, ""):
        value, custom = custom_value, True
    else:
        if option_index is None or not 0 <= option_index < len(off["options"]):
            raise ValueError("Choose one of the options.")
        value, custom = off["options"][option_index]["value"], False
    old = fact.value_json
    fact.value_json = _dump(value)
    fact.last_confirmed_at, fact.confirmed_by, fact.needs_review = datetime.utcnow(), (submission.code if submission is not None else actor), False
    if custom:
        db.session.add(PersonFactClaim(fact_id=fact.id, submission_id=None, source_form=submission.form.source_form_name if submission is not None else None,
                                       source_field="conflict resolution", value_json=fact.value_json, state="manual", resolved=True))
    for c in fact.claims:
        c.resolved = True
    _event(fact, "resolved", submission, actor, old=old, new=fact.value_json)
    record_use(fact, submission)
    db.session.commit()
    return fact


# ------------------------------------------------------------------ views for Admin
def open_conflicts(person=None, customer_id=None):
    q = PersonFact.query.filter(PersonFact.needs_review.is_(True))
    if person is not None:
        q = q.filter(PersonFact.real_person_id == person.id)
    elif customer_id is not None:
        q = q.join(Person, Person.id == PersonFact.real_person_id).filter(Person.customer_id == customer_id)
    return [f for f in q.order_by(PersonFact.id).all() if conflict_capable(f.fact_key)]


def claims_of(fact):
    return sorted(fact.claims, key=lambda c: (c.updated_at or c.recorded_at))
