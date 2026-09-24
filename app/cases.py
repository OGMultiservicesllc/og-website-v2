"""Case services: creating cases, attaching applications, people + roles, canonical person facts.

Everything here is additive and defensive: it reads the answers of an application, never rewrites
them, and never gives a non-customer person any access. Facts are shared ONLY through the explicit
mapping in app/case_types.py, and a fact that a later application reports differently is never
overwritten silently: it is flagged `needs_review` so a customer-confirmation step can resolve it.
"""

import json
from datetime import datetime

from app.activity import log_event
from app.case_types import FACTS, FORM_CASE_CONFIG, RELATIONSHIPS, config_for, type_title
import app.case_types as _ct
from app.extensions import db
from app import persons as pers
from app.models import (
    ActivityEvent,
    ApplicationLink,
    ApplicationRole,
    Case,
    CasePerson,
    FormSubmission,
    PersonFact,
    PersonFactEvent,
    PersonFactUse,
    Person,
    PersonFactClaim,
)


# ------------------------------------------------------------------ small helpers
def _norm(value):
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def answers_by_name(submission):
    """{internal_name: str | list} from the saved answers (read only)."""
    out = {}
    for v in submission.values:
        raw = v.value_text
        try:
            parsed = json.loads(raw) if raw and raw[:1] in "[{" else raw
        except ValueError:
            parsed = raw
        out[v.field_internal_name] = parsed
    return out


def split_name(full):
    parts = (full or "").strip().split()
    if not parts:
        return "", ""
    return parts[0], " ".join(parts[1:])


def case_event(case, event_type, *, actor="customer", actor_id=None, meta=None, commit=True):
    """A meaningful case-level event (never page views or keystrokes)."""
    return log_event(case.customer_id, event_type, actor=actor, actor_id=actor_id, entity=("case", case.id),
                     meta=dict(meta or {}, case=case.case_number), commit=commit, case_id=case.id)


# ------------------------------------------------------------------ cases
def create_case(customer, case_type="other", title=None, *, origin="auto", actor="customer", actor_id=None, lang=None, created_at=None, quiet=False):
    case = Case(customer_id=customer.id, case_type=case_type if case_type else "other", title=(title or type_title(case_type))[:200], origin=origin,
                preferred_language=lang or customer.preferred_language)
    if created_at:
        case.created_at = created_at
    db.session.add(case)
    db.session.flush()
    case.case_number = f"OGC-{case.id:06d}"
    ensure_customer_person(case)
    db.session.commit()
    if not quiet:
        case_event(case, "case_created", actor=actor, actor_id=actor_id, meta={"title": case.title})
    return case


def ensure_customer_person(case):
    person = next((p for p in case.people if p.is_customer), None)
    if person is None:
        given, family = split_name(case.customer.name)
        person = CasePerson(case_id=case.id, student_id=case.customer_id, is_customer=True, relationship_key="self", given_name=given, family_name=family)
        db.session.add(person)
        db.session.flush()
        case.people.append(person)
    return person


def add_person(case, given_name, family_name, relationship_key="other", *, actor="admin", actor_id=None, link_to=None):
    """A participant who is NOT the customer: no login, no access. `link_to` (a Person of the SAME customer) explicitly declares that
    this participant is a real person the customer already has in another case; without it a new Person is created (no name matching)."""
    if relationship_key not in RELATIONSHIPS or relationship_key == "self":
        relationship_key = "other"
    if link_to is not None:
        if link_to.customer_id != case.customer_id:
            raise ValueError("A person can only be linked inside one customer's data.")
        person = pers.case_person_for(case, link_to, relationship_key=relationship_key)
        db.session.commit()
        case_event(case, "case_person_added", actor=actor, actor_id=actor_id, meta={"person": person.full_name})
        return person
    person = CasePerson(case_id=case.id, given_name=(given_name or "").strip()[:120], family_name=(family_name or "").strip()[:120], relationship_key=relationship_key)
    db.session.add(person)
    db.session.commit()
    case_event(case, "case_person_added", actor=actor, actor_id=actor_id, meta={"person": person.full_name})
    return person


def find_open_case(customer, case_type):
    return (Case.query.filter(Case.customer_id == customer.id, Case.case_type == case_type, Case.status != "closed")
            .order_by(Case.id.desc()).first())


def ensure_case_for_submission(submission, *, origin="auto", quiet=False):
    """The case an application belongs to: its own, else the customer's open case of the same type,
    else a new one. Anonymous inquiries (no customer) are never attached."""
    if submission.case_id or not submission.student_id:
        return submission.case
    from app.case_setup import needs_setup

    if needs_setup(submission) and not submission.is_complete:
        return None  # its applicant + case are chosen by the customer first (I-485); never auto-attached, not even by the backfill
    cfg = config_for(submission.form)
    case_type = cfg["case_type"] if cfg else "other"
    customer = submission.student
    case = find_open_case(customer, case_type)
    if case is None:
        title = type_title(case_type) if cfg else (submission.service.title_en if submission.service else submission.form.name_admin)
        created = min([d for d in (submission.submitted_at, submission.updated_at) if d], default=None) if origin == "migrated" else None
        case = create_case(customer, case_type, title, origin=origin, lang=submission.language, created_at=created, quiet=quiet, actor="system" if origin == "migrated" else "customer")
    attach_application(case, submission, actor="system" if origin == "migrated" else "customer", quiet=quiet)
    return case


class IncompatibleCase(ValueError):
    """The application's form cannot live in that type of case (see app/case_types.py `case_types`)."""


def attach_application(case, submission, *, actor="admin", actor_id=None, quiet=False):
    """Put an application in a case. Only the same customer's applications may join, and only into a compatible case type; moving one
    keeps its id, answers, files and history (only the grouping changes) and keeps WHO each person is: every role moves to the
    CasePerson that represents the same real Person in the new case."""
    if submission.student_id != case.customer_id:
        raise ValueError("An application can only join a case of the same customer.")
    form_name = submission.form.source_form_name
    if not _ct.is_compatible(form_name, case.case_type):
        raise IncompatibleCase(f"Form {form_name} cannot be added to a {type_title(case.case_type)} case. It belongs to: "
                               + ", ".join(type_title(t) for t in _ct.compatible_case_types(form_name)) + ".")
    if submission.case_id == case.id:
        return submission
    moved_from = submission.case_id
    carried = []
    if moved_from:
        for role in ApplicationRole.query.filter_by(submission_id=submission.id).all():
            carried.append((role.role_key, pers.owner_of(role.person), role.person))
            db.session.delete(role)
        db.session.flush()
    # Grouping is not an edit: keep `updated_at` exactly as it was (the column has an on-update default).
    FormSubmission.query.filter_by(id=submission.id).update({"case_id": case.id, "updated_at": FormSubmission.updated_at}, synchronize_session=False)
    db.session.commit()
    db.session.refresh(submission)
    for role_key, person, old_cp in carried:
        cp = pers.case_person_for(case, person, template=old_cp)
        db.session.add(ApplicationRole(case_id=case.id, submission_id=submission.id, person_id=cp.id, role_key=role_key))
    db.session.commit()
    sync_people(submission)
    if moved_from:
        close_if_empty(db.session.get(Case, moved_from), actor=actor, actor_id=actor_id)
    if not quiet:
        case_event(case, "application_added_to_case", actor=actor, actor_id=actor_id, meta={
            "application": submission.code, "form": submission.form.source_form_name or submission.form.name_admin, "moved": bool(moved_from)})
    return submission


def close_if_empty(case, *, actor="system", actor_id=None):
    """A case that OG/the system created automatically and that no longer holds anything (its only application
    moved elsewhere) is closed, not deleted. Cases made by hand, or holding documents/notes/other people, stay."""
    if case is None or case.status == "closed" or case.origin == "admin":
        return False
    if case.applications or case.requirements or case.documents or case.notes or any(not p.is_customer for p in case.people):
        return False
    case.status, case.closed_at = "closed", datetime.utcnow()
    db.session.commit()
    case_event(case, "case_status_changed", actor=actor, actor_id=actor_id, meta={"from_label": "Open", "to_label": "Closed (empty)"})
    return True


# ------------------------------------------------------------------ people + roles
def _named_person_spec_values(spec, answers):
    given, family = (str(answers.get(f) or "").strip() for f in spec["names"])
    return given, family


def sync_people(submission):
    """Make sure the people and roles of one application exist in its case. Roles are mappings: the same
    real person keeps ONE case person across applications and only gains roles."""
    case = submission.case
    cfg = config_for(submission.form)
    if case is None or cfg is None:
        return []
    answers = answers_by_name(submission)
    people = []
    for spec in cfg["people"]:
        person = None
        if spec["who"] == "customer":
            person = ensure_customer_person(case)
        elif spec["who"] == "chosen":
            existing = ApplicationRole.query.filter_by(submission_id=submission.id, role_key=spec["roles"][0]).first()
            if existing is not None:
                person = existing.person
                given, family = _named_person_spec_values(spec, answers)
                if not person.is_customer and (given or family):
                    person.given_name, person.family_name = given or person.given_name, family or person.family_name
            else:
                given, family = _named_person_spec_values(spec, answers)
                if given or family:  # "someone else": a new case person, named by the applicant's own answers
                    person = CasePerson(case_id=case.id, given_name=given[:120], family_name=family[:120], relationship_key="other")
                    db.session.add(person)
                    db.session.flush()
                    case.people.append(person)
                    case_event(case, "case_person_added", actor="system", meta={"person": person.full_name}, commit=False)
                else:
                    person = ensure_customer_person(case)
        else:
            given, family = _named_person_spec_values(spec, answers)
            existing = (ApplicationRole.query.filter_by(submission_id=submission.id, role_key=spec["roles"][0]).first())
            if existing is not None:
                person = existing.person
                if given or family:
                    person.given_name, person.family_name = given or person.given_name, family or person.family_name
            elif given or family:
                a_num = _norm(answers.get(spec.get("a_number_field") or "")) if spec.get("a_number_field") else ""
                for cand in case.people:
                    if cand.is_customer:
                        continue
                    if a_num and any(f.fact_key == "a_number" and _norm(json.loads(f.value_json or '""')) == a_num for f in cand.facts):
                        person = cand
                        break
                    if _norm(cand.given_name) == _norm(given) and _norm(cand.family_name) == _norm(family):
                        person = cand
                        break
                if person is None:
                    rel = answers.get(spec.get("relationship_field") or "")
                    person = CasePerson(case_id=case.id, given_name=given[:120], family_name=family[:120], relationship_key=rel if rel in RELATIONSHIPS else "other")
                    db.session.add(person)
                    db.session.flush()
                    case.people.append(person)
                    case_event(case, "case_person_added", actor="system", meta={"person": person.full_name}, commit=False)
        if person is None:
            continue
        people.append(person)
        wanted = list(spec["roles"])
        for extra in spec.get("extra_roles", []):
            field, value = extra["when"]
            if answers.get(field) == value:
                wanted.append(extra["role"])
        wanted = list(dict.fromkeys(wanted))
        have = {r.role_key: r for r in ApplicationRole.query.filter_by(submission_id=submission.id, person_id=person.id).all()}
        for role in wanted:
            if role not in have:
                db.session.add(ApplicationRole(case_id=case.id, submission_id=submission.id, person_id=person.id, role_key=role))
        for role, row in have.items():
            if role not in wanted:
                db.session.delete(row)
    _sync_record_people(submission, cfg, answers, people)
    db.session.commit()
    return people


def _person_dob(cand):
    return next((_load(f.value_json) for f in cand.facts if f.fact_key == "date_of_birth"), None)


def _find_case_person(case, given, family, a_number=None, exclude_ids=(), dob=None, taken=None):
    """The existing case person this name/A-number describes (customer included), so nobody is duplicated.
    With `dob` (forms that ask it for every listed person) a name match is REJECTED when the candidate's known date of birth differs, or when
    another entry of the same list already took that candidate with a different date of birth: two children with one name stay two people."""
    a_num = _norm(a_number)
    for cand in case.people:
        if cand.id in exclude_ids:
            continue
        if a_num and any(f.fact_key == "a_number" and _norm(json.loads(f.value_json or '""')) == a_num for f in cand.facts):
            return cand
        if _norm(cand.given_name) == _norm(given) and _norm(cand.family_name) == _norm(family) and _norm(given):
            if dob:
                known = _person_dob(cand)
                if known and str(known) != str(dob):
                    continue
                if taken is not None and cand.id in taken and taken[cand.id] != dob:
                    continue
            return cand
    return None


def _sync_record_people(submission, cfg, answers, people):
    """People named inside an application (spouse, children, parents) become case people with a role, or are matched to
    a person the case already has (the spouse who is already the I-130 petitioner). No login is ever created."""
    specs = cfg.get("record_people") or []
    if not specs:
        return
    case = submission.case
    applicant_ids = {p.id for p in people}
    keep_by_role = {}
    for spec in specs:
        if spec["kind"] == "scalar":
            entries = [{"given": answers.get(spec["given"]), "family": answers.get(spec["family"]), "a_number": answers.get(spec.get("a_number")), "dob": answers.get(spec.get("dob")),
                        "person_id": answers.get(spec["person_link"]) if spec.get("person_link") else None}]
        else:
            recs = answers.get(spec["field"])
            entries = [r for r in (recs if isinstance(recs, list) else []) if isinstance(r, dict)]
            entries = [{"given": r.get(spec["given"]), "family": r.get(spec["family"]), "a_number": r.get(spec.get("a_number")) if spec.get("a_number") else None,
                        "dob": r.get(spec["dob"]) if spec.get("dob_match") and spec.get("dob") else None,
                        "person_id": r.get(spec["person_link"]) if spec.get("person_link") else None} for r in entries]
        keep = set()
        taken = {}
        for e in entries:
            given, family = str(e.get("given") or "").strip(), str(e.get("family") or "").strip()
            person = None
            if e.get("person_id"):
                # an explicit link to a real Person of THIS customer (never trusted from the form on its own)
                try:
                    owner = Person.query.filter_by(id=int(e["person_id"]), customer_id=case.customer_id).first()
                except (TypeError, ValueError):
                    owner = None
                if owner is not None:
                    person = pers.case_person_for(case, owner, relationship_key=spec["relationship"])
            if person is None and not (given and family):
                continue
            if person is None:
                person = _find_case_person(case, given, family, e.get("a_number"), exclude_ids=(set() if spec.get("match_core") else applicant_ids),
                                           dob=e.get("dob"), taken=taken if spec.get("dob_match") else None)
            if person is None and spec["role"] == "spouse":
                # the spouse the applicant's other applications already know (the I-130 petitioner): the SAME real Person, linked explicitly
                related = person_related(submission, (cfg.get("blocks") or {}).get("sb_spouse", {}).get("related") or {"via": ("beneficiary", "spouse_beneficiary"), "to": "petitioner"})
                if related is not None:
                    owner = pers.owner_of(related)
                    if _norm(owner.given_name) == _norm(given) and _norm(owner.family_name) == _norm(family):
                        person = pers.case_person_for(case, owner, template=related, relationship_key=spec["relationship"])
            if person is None:
                person = CasePerson(case_id=case.id, given_name=given[:120], family_name=family[:120], relationship_key=spec["relationship"])
                db.session.add(person)
                db.session.flush()
                case.people.append(person)
                case_event(case, "case_person_added", actor="system", meta={"person": person.full_name}, commit=False)
            keep.add(person.id)
            keep_by_role.setdefault(spec["role"], set()).add(person.id)
            if spec.get("dob_match") and e.get("dob"):
                taken[person.id] = e["dob"]
                if spec.get("dob_claim"):  # the date of birth the customer typed is remembered for this person, so later syncs tell same-named people apart
                    pers.record_claim(person, "date_of_birth", e["dob"], submission, field_name=spec["field"])
            if not ApplicationRole.query.filter_by(submission_id=submission.id, person_id=person.id, role_key=spec["role"]).first():
                db.session.add(ApplicationRole(case_id=case.id, submission_id=submission.id, person_id=person.id, role_key=spec["role"]))
        keep_by_role.setdefault(spec["role"], set())
    for role_key, keep in keep_by_role.items():  # decided after every spec: several specs (father, mother) may share one role
        for row in ApplicationRole.query.filter_by(submission_id=submission.id, role_key=role_key).all():
            if row.person_id not in keep:
                db.session.delete(row)


def role_person(submission, role_key):
    row = ApplicationRole.query.filter_by(submission_id=submission.id, role_key=role_key).first()
    return row.person if row else None


def person_related(submission, spec):
    """The CasePerson connected to this application's applicant through ANOTHER application of the same real person, in ANY of the
    customer's cases: e.g. the petitioner of the I-130 in which the applicant is the beneficiary. Identity comes from the shared
    Person, never from the case: the two applications do not have to live in one case. None when nothing links them."""
    applicant = role_person(submission, "applicant")
    if applicant is None:
        return None
    owner = pers.owner_of(applicant)
    cp_ids = [cp.id for cp in owner.case_people]
    rows = (ApplicationRole.query.filter(ApplicationRole.person_id.in_(cp_ids), ApplicationRole.submission_id != submission.id,
                                         ApplicationRole.role_key.in_(list(spec["via"]))).order_by(ApplicationRole.id).all())
    for row in rows:
        if row.submission is None or row.submission.student_id != submission.student_id:
            continue  # never cross into another customer's data
        other = ApplicationRole.query.filter_by(submission_id=row.submission_id, role_key=spec["to"]).first()
        if other is not None and pers.owner_of(other.person).id != owner.id:
            return other.person
    return None


def link_applications(case, submission, related, kind="underlying_petition"):
    if submission.case_id != case.id or related.case_id != case.id or submission.id == related.id:
        raise ValueError("Applications can only be linked inside one case.")
    if not ApplicationLink.query.filter_by(submission_id=submission.id, related_submission_id=related.id, kind=kind).first():
        db.session.add(ApplicationLink(case_id=case.id, submission_id=submission.id, related_submission_id=related.id, kind=kind))
        db.session.commit()


def unlink_applications(submission, kind="underlying_petition"):
    for link in ApplicationLink.query.filter_by(submission_id=submission.id, kind=kind).all():
        db.session.delete(link)
    db.session.commit()


def related_applications(submission):
    """[(other application, how it relates)] for the admin view: explicit links first, then the rest of the case."""
    out, seen = [], set()
    for link in ApplicationLink.query.filter_by(submission_id=submission.id).all():
        out.append((link.related, link.kind))
        seen.add(link.related_submission_id)
    for link in ApplicationLink.query.filter_by(related_submission_id=submission.id).all():
        out.append((link.submission, "is based on this"))
        seen.add(link.submission_id)
    if submission.case is not None:
        for s in submission.case.applications:
            if s.id != submission.id and s.id not in seen:
                out.append((s, "same case"))
    return out


def person_for(submission, key):
    """The case person playing the role spec `key` (e.g. "petitioner") in this application."""
    cfg = config_for(submission.form)
    if cfg is None:
        return None
    spec = next((s for s in cfg["people"] if s["key"] == key), None)
    if spec is None:
        return None
    role = ApplicationRole.query.filter_by(submission_id=submission.id, role_key=spec["roles"][0]).first()
    return role.person if role else None


# ------------------------------------------------------------------ canonical person facts
def _address_from_prefix(answers, prefix):
    keys = ("is_us", "street", "unit_type", "unit_number", "city", "state", "zip", "province", "postal_code", "country")
    rec = {k: str(answers.get(f"{prefix}_{k}") or "").strip() for k in keys}
    rec = {k: v for k, v in rec.items() if v}
    return rec if rec.get("street") or rec.get("city") else None


def extract_fact(spec, answers):
    if isinstance(spec, dict):
        if "address_prefix" in spec:
            return _address_from_prefix(answers, spec["address_prefix"])
        if "compose" in spec:  # several answers that together state ONE fact ("Newark" + "NJ" -> "Newark, NJ")
            parts = [str(answers.get(n) or "").strip() for n in spec["compose"]]
            return spec.get("sep", " ").join(x for x in parts if x) or None
        if "first_of" in spec:
            return next((str(answers.get(n)).strip() for n in spec["first_of"] if str(answers.get(n) or "").strip()), None)
        if "record_present" in spec:
            records = answers.get(spec["record_present"])
            records = records if isinstance(records, list) else []
            cur = next((r for r in records if isinstance(r, dict) and r.get("present")), None)
            if not cur:
                return None
            keep = ("is_us", "street", "unit_type", "unit_number", "city", "state", "zip", "province", "postal_code", "country")
            return {k: cur[k] for k in keep if cur.get(k)} or None
        return None
    value = answers.get(spec)
    if isinstance(value, str):
        value = value.strip()
    return value or None


def _rec_sig(recs):
    out = []
    for r in (recs or []):
        if isinstance(r, dict):
            out.append(tuple(sorted((k, _norm(v)) for k, v in r.items() if v not in ("", None, False) and k in
                                    ("street", "city", "zip", "country", "from", "to", "present", "name", "type", "family", "given", "dob", "occupation"))))
    return sorted(out)


def _same(key, a, b):
    if FACTS.get(key, {}).get("kind") == "records":
        return _rec_sig(a) == _rec_sig(b)
    if FACTS.get(key, {}).get("kind") == "address":
        ka = ("street", "city", "zip", "country", "state", "province")
        return all(_norm((a or {}).get(k)) == _norm((b or {}).get(k)) for k in ka)
    return _norm(a) == _norm(b)


def _dump(value):
    return json.dumps(value, ensure_ascii=False)


def _load(raw):
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return raw


def fact_value(fact):
    return _load(fact.value_json)


def record_use(fact, submission, field_name=None):
    pers.record_use(fact, submission, field_name)


def record_fact(person, key, value, submission, field_name=None, source_ref=None):
    """One application states a fact about a person. It becomes a CLAIM on the real Person's fact (with provenance and the state of
    the application); the canonical value is never overwritten silently and a different value is flagged as a conflict."""
    return pers.record_claim(person, key, value, submission, field_name, source_ref)


def harvest_facts(submission):
    """Offer the facts an application states about its people to the canonical layer (explicit mapping
    only). Called when an application is submitted and when existing cases are migrated."""
    cfg = config_for(submission.form)
    if cfg is None or submission.case_id is None:
        return 0
    sync_people(submission)
    answers = answers_by_name(submission)
    fields = {f.internal_name: f for f in submission.form.all_fields}
    n = 0
    for key, mapping in cfg["facts"].items():
        person = person_for(submission, key)
        if person is None:
            continue
        for fact_key, spec in mapping.items():
            value = extract_fact(spec, answers)
            field_name = spec if isinstance(spec, str) else (spec.get("record_present") or spec.get("address_prefix") or ",".join(spec.get("compose") or spec.get("first_of") or []))
            ref = fields[spec].source_ref if isinstance(spec, str) and spec in fields else None
            if record_fact(person, fact_key, value, submission, field_name, ref):
                n += 1
    pers.refresh_states(submission)
    db.session.commit()
    return n


def sync_claims(submission):
    """Keep the shared layer current while an application is a DRAFT / reopened / submitted: the facts the customer has explicitly
    entered become available for reuse (with the application's state in their provenance) before it is submitted. Never
    raises: a shared-layer problem must not break the intake."""
    try:
        if submission is None or submission.case_id is None or config_for(submission.form) is None:
            return 0
        return harvest_facts(submission)
    except Exception:  # noqa: BLE001
        db.session.rollback()
        import logging

        logging.getLogger(__name__).exception("claim sync failed for %s", getattr(submission, "code", "?"))
        return 0


def display_fact_value(key, value, lang="en", reveal=False):
    if value in (None, "", {}):
        return ""
    kind = FACTS.get(key, {}).get("kind")
    if kind == "records":
        from app.intake_records import card_for

        rtype = FACTS[key].get("record", "address")
        lines = []
        for rec in value if isinstance(value, list) else []:
            title, sub = card_for(rtype, rec, lang)
            lines.append(f"{title} ({sub})" if sub else title)
        return "\n".join(lines)
    if kind == "address":
        parts = [value.get("street", "") + (f" {value.get('unit_number')}" if value.get("unit_number") else ""), value.get("city", "")]
        parts += [f"{value.get('state', '')} {value.get('zip', '')}".strip()] if value.get("is_us", "yes") == "yes" else [value.get("province", ""), value.get("postal_code", ""), value.get("country", "")]
        return ", ".join(p for p in parts if p)
    if kind == "date":
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").strftime("%m/%d/%Y")
        except ValueError:
            return str(value)
    if kind == "list":
        opts = FACTS[key].get("options", {})
        items = value if isinstance(value, list) else [value]
        return ", ".join((opts[v][1] if lang == "es" else opts[v][0]) if v in opts else str(v) for v in items)
    if kind == "choice":
        pair = FACTS[key].get("options", {}).get(value)
        return (pair[1] if lang == "es" else pair[0]) if pair else str(value)
    text = str(value)
    if FACTS.get(key, {}).get("sensitive") and not reveal and len(text) > 4:
        return "•" * (len(text) - 4) + text[-4:]
    return text


def facts_for_review(person, keys=None, lang="en", reveal=False):
    """What Admin (and any review screen) shows for a person: one row per fact of the REAL person, with provenance, scope and state.
    -> [{key, label, value, display, status, scope, source_form, source_code, last_confirmed_at, used_by, pending, claims, fact}]"""
    owner = pers.owner_of(person)
    by_key = {f.fact_key: f for f in owner.facts}
    rows = []
    for key in (keys or FACT_ORDER_KEYS):
        fact = by_key.get(key)
        if fact is None:
            continue
        value = fact_value(fact)
        pending = None
        if fact.needs_review:
            pending = [display_fact_value(key, _load(c.value_json), lang, reveal) for c in pers.claims_of(fact) if not _same(key, _load(c.value_json), value)]
        status = "needs_review" if fact.needs_review else ("confirmed" if fact.last_confirmed_at else "unconfirmed")
        rows.append({
            "key": key, "label": FACTS[key][lang if lang in ("en", "es") else "en"], "value": value, "display": display_fact_value(key, value, lang, reveal),
            "status": status, "scope": _ct.scope_of(key), "source_form": fact.source_form, "source_code": fact.source_submission.code if fact.source_submission else None,
            "source_field": fact.source_field, "last_confirmed_at": fact.last_confirmed_at, "confirmed_by": fact.confirmed_by,
            "used_by": sorted({u.submission.code for u in fact.uses if u.submission}), "pending": ", ".join(pending) if pending else None,
            "sensitive": fact.is_sensitive, "fact": fact,
            "claims": [{"form": c.source_form, "code": c.submission.code if c.submission else None, "state": c.state, "resolved": c.resolved,
                        "display": display_fact_value(key, _load(c.value_json), lang, reveal), "at": c.updated_at or c.recorded_at} for c in pers.claims_of(fact)],
        })
    return rows


FACT_ORDER_KEYS = list(FACTS)


def confirm_facts(person, keys=None, submission=None, actor="customer"):
    """The person (or OG on their behalf) confirmed these facts are still correct."""
    return pers.confirm(person, keys, submission, actor)


def update_fact(person, key, value, submission=None, actor="customer"):
    """The value was corrected during a review: keep the ORIGINAL source, record who changed it and when."""
    return pers.update(person, key, value, submission, actor)


# ------------------------------------------------------------------ timeline / summaries
def case_timeline(case, limit=300):
    from app.activity import describe

    ids = [s.id for s in case.applications]
    query = ActivityEvent.query.filter(db.or_(ActivityEvent.case_id == case.id,
                                             db.and_(ActivityEvent.entity_type == "submission", ActivityEvent.entity_id.in_(ids or [-1]))))
    events = query.order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc()).limit(limit).all()
    return [(e, describe(e)[1]) for e in events]


def last_activity(case):
    rows = case_timeline(case, 1)
    return rows[0][0].created_at if rows else case.updated_at or case.created_at


def owned_case(student, case_id):
    """The case only if it belongs to this signed-in customer (404 otherwise, like every other portal object)."""
    if student is None:
        return None
    return Case.query.filter_by(id=case_id, customer_id=student.id).first()


# ------------------------------------------------------------------ migration of existing data
def backfill_persons():
    """Link every existing CasePerson to a REAL Person and move the facts under that Person. Idempotent, additive.

    * the customer's own CasePerson (any case) links to the customer's single self Person (the Student relationship is the evidence);
    * every other CasePerson gets its own Person: NO name matching ever merges people;
    * facts recorded through different CasePeople of one Person merge into one fact; every differing value stays as a claim, so a real
      difference becomes a visible conflict instead of being dropped or silently chosen;
    * nothing is deleted except the now-redundant duplicate fact rows (their events, uses and values are carried over).
    """
    n = 0
    for cp in CasePerson.query.filter(CasePerson.person_id.is_(None)).order_by(CasePerson.id).all():
        pers.ensure_person(cp)
        n += 1
    db.session.flush()
    touched = []
    for f in PersonFact.query.filter(PersonFact.real_person_id.is_(None)).order_by(PersonFact.id).all():
        cp = db.session.get(CasePerson, f.person_id) if f.person_id else None
        if cp is None:
            continue
        owner = pers.owner_of(cp)
        keeper = PersonFact.query.filter(PersonFact.real_person_id == owner.id, PersonFact.fact_key == f.fact_key, PersonFact.id != f.id).first()
        seen = {}
        if f.source_submission_id:
            seen[f.source_submission_id] = (f.value_json, f.first_recorded_at)
        for e in f.events:
            if e.submission_id and e.kind in ("recorded", "differs", "updated") and e.new_value_json:
                seen[e.submission_id] = (e.new_value_json, e.created_at)
        if keeper is None:
            f.real_person_id = owner.id
            target = f
        else:
            target = keeper
            for ev in list(f.events):
                ev.fact_id = target.id
            for use in list(f.uses):
                if PersonFactUse.query.filter_by(fact_id=target.id, submission_id=use.submission_id, field_name=use.field_name).first():
                    db.session.delete(use)
                else:
                    use.fact_id = target.id
            if f.last_confirmed_at and (target.last_confirmed_at is None) and _same(f.fact_key, _load(f.value_json), _load(target.value_json)):
                target.last_confirmed_at, target.confirmed_by = f.last_confirmed_at, f.confirmed_by
        for sid, (val, at) in seen.items():
            if PersonFactClaim.query.filter_by(fact_id=target.id, submission_id=sid).first():
                continue
            sub = db.session.get(FormSubmission, sid)
            db.session.add(PersonFactClaim(fact_id=target.id, submission_id=sid, source_form=sub.form.source_form_name if sub else None, source_field=f.source_field,
                                           source_ref=f.source_ref if sid == f.source_submission_id else None, value_json=val, state=pers.sub_state(sub),
                                           recorded_at=at or datetime.utcnow(), updated_at=at or datetime.utcnow()))
        db.session.flush()
        if keeper is not None:
            db.session.expire(f)
            db.session.delete(f)
            db.session.flush()
        touched.append(target)
        n += 1
    db.session.flush()
    for fact in {t.id: t for t in touched}.values():
        db.session.expire(fact, ["claims"])
        pers.evaluate(fact)
    db.session.commit()
    return n


def fix_incompatible_placements():
    """An application that sits in a case type its form does not belong to (the I-485 that was allowed into a Naturalization case) is
    moved to a compatible case (the customer's open one, else a new one). Answers, roles, people identity, files, notes, activity and
    timestamps are preserved (`attach_application`). Idempotent."""
    moved = []
    for sub in FormSubmission.query.filter(FormSubmission.case_id.isnot(None), FormSubmission.student_id.isnot(None)).order_by(FormSubmission.id).all():
        name = sub.form.source_form_name
        if not name or sub.case is None or _ct.is_compatible(name, sub.case.case_type):
            continue
        wanted = _ct.compatible_case_types(name)[0]
        target = find_open_case(sub.student, wanted)
        if target is None:
            target = create_case(sub.student, wanted, None, origin="migrated", lang=sub.language, actor="system")
        attach_application(target, sub, actor="system")
        moved.append((sub.code, target.case_number))
    return moved


def backfill_cases():
    """Attach every existing customer application to a case, without touching the application:
    same id, answers, files, notes, statuses, timestamps and history. Idempotent."""
    backfill_persons()
    subs = (FormSubmission.query.filter(FormSubmission.student_id.isnot(None), FormSubmission.case_id.is_(None))
            .order_by(FormSubmission.id).all())
    subs = [s for s in subs if s.form.is_service_intake]
    for sub in subs:
        ensure_case_for_submission(sub, origin="migrated", quiet=False)
        if sub.is_complete:
            harvest_facts(sub)
    refresh = FormSubmission.query.filter(FormSubmission.case_id.isnot(None), FormSubmission.is_complete.is_(True)).all()
    for sub in refresh:  # new fact mappings reach applications submitted before they existed (idempotent, read-only on the application)
        if sub.id not in {s.id for s in subs} and config_for(sub.form) and not any(f.source_submission_id == sub.id for p in sub.case.people for f in p.facts if f.fact_key in ("address_history", "parents", "last_arrival_date")):
            harvest_facts(sub)
    fix_incompatible_placements()
    for sub in FormSubmission.query.filter(FormSubmission.case_id.isnot(None), FormSubmission.student_id.isnot(None)).all():
        if config_for(sub.form) and not PersonFactClaim.query.filter_by(submission_id=sub.id).first():
            sync_claims(sub)  # drafts / reopened applications feed the shared layer too (with their state in the provenance)
    return len(subs)
