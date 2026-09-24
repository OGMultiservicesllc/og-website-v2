"""Consent to Travel case services: create / resume, save an interview step, children + auto-synced
consenting-adult records, document grouping, submit to OG (Pending OG Review — never payable yet), OG
approval (the ONLY thing that makes a payment request possible), workflow.
"""

from datetime import datetime

from app import cases as case_svc
from app.consent_travel import docs, people, pricing
from app.consent_travel import rules as ct_rules
from app.consent_travel.config import CONFIG
from app.extensions import db
from app.models import ActivityEvent, Case, ConsentTravelCaseData, ConsentTravelRecord, TermsAcceptance
from app.tax.questions import Ctx, coerce, missing_message, pick

CASE_TYPE = "consent_travel"
EDITABLE = ("draft", "reopened")
CASE_STATUS_OF = {"draft": "open", "submitted": "in_review", "waiting_client": "waiting_client", "approved": "in_review",
                  "in_progress": "in_review", "completed": "completed", "on_hold": "in_review", "closed": "closed", "reopened": "waiting_client"}


def _notify(ct, template_key, lang=None):
    try:
        from app.email_service import send_transactional_email

        student = ct.case.customer
        send_transactional_email(student, template_key, lang or student.preferred_language or "en", ref={"kind": "consent_travel", "id": ct.id}, related_type="consent_travel_case", related_id=ct.id)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("og_email").exception("[consent_travel] %r email failed to queue", template_key)


# ------------------------------------------------------------------ access
def ctx(ct, lang="en", record=None):
    def bound(scope, bind):
        return people.get_fact(people.owner_for(ct, scope, record if scope == "record" else None), bind)

    return Ctx(ct, CONFIG, lang, record, bound, lambda r: people.info(ct, r))


def owned(student, case_id):
    case = Case.query.filter_by(id=case_id, customer_id=student.id, case_type=CASE_TYPE).first()
    return case.consent_travel_data if case is not None else None


def owned_record(ct, record_id):
    return next((r for r in ct.records if r.id == record_id), None)


def log(ct, event, meta=None, *, actor="customer", actor_id=None):
    case_svc.case_event(ct.case, event, actor=actor, actor_id=actor_id, meta=meta or {})


# ------------------------------------------------------------------ create / resume
def active_case(student):
    return (ConsentTravelCaseData.query.join(Case, Case.id == ConsentTravelCaseData.case_id)
            .filter(Case.customer_id == student.id, Case.status != "closed", ConsentTravelCaseData.status != "closed").order_by(ConsentTravelCaseData.id.desc()).first())


def start_or_resume(student, lang):
    ct = active_case(student)
    if ct is not None:
        recent = ActivityEvent.query.filter_by(customer_id=student.id, case_id=ct.case_id, event_type="consent_travel_resumed").order_by(ActivityEvent.id.desc()).first()
        if ct.status in EDITABLE and recent is None:
            log(ct, "consent_travel_resumed")
        return ct, False
    title = "Consent to Travel Authorization" if lang != "es" else "Autorización de Viaje para Menores"
    case = case_svc.create_case(student, CASE_TYPE, title, origin="auto", lang=lang, quiet=True)
    ct = ConsentTravelCaseData(case_id=case.id, language=lang, current_step="intro")
    db.session.add(ct)
    db.session.commit()
    log(ct, "consent_travel_case_created", {"title": case.title})
    return ct, True


def set_case_status(ct, status):
    ct.status = status
    ct.case.status = CASE_STATUS_OF.get(status, ct.case.status)
    ct.case.updated_at = datetime.utcnow()


# ------------------------------------------------------------------ steps
def visible_steps(c):
    return c.steps()


def step_by_key(c, key):
    return next((s for s in visible_steps(c) if s.key == key), None)


def neighbour(c, key, delta):
    steps = visible_steps(c)
    keys = [s.key for s in steps]
    if key not in keys:
        return steps[0].key if steps else None
    i = keys.index(key) + delta
    return keys[i] if 0 <= i < len(keys) else None


def progress(c, key):
    steps = visible_steps(c)
    keys = [s.key for s in steps]
    if key in keys:
        n, total = keys.index(key) + 1, len(keys)
        return {"step": n, "total": total, "percent": int(round(100 * n / max(1, total)))}
    for kind, flow in CONFIG.record_flows.items():
        fkeys = [s.key for s in flow]
        if key in fkeys:
            anchor = "children" if kind == "child" else "adults"
            base = keys.index(anchor) if anchor in keys else len(keys) - 1
            total = len(keys) + len(flow) - 1
            n = min(base + 1 + fkeys.index(key), total)
            return {"step": n, "total": total, "percent": int(round(100 * n / max(1, total)))}
    return {"step": 1, "total": len(keys), "percent": int(round(100 / max(1, len(keys))))}


def _questions(step):
    return [q for q in step.questions if q.kind not in ("note", "docs", "records", "person_pick")]


def _store(ct, record, q, value):
    if record is not None and q.key in CONFIG.record_keys:
        d = record.data
        d[q.key] = value
        record.data = d
    else:
        a = ct.answers
        a[q.key] = value
        ct.answers = a


def save_step(ct, step, form, lang, record=None, strict=False):
    c = ctx(ct, lang, record)
    markers = set(form.getlist("__q"))
    values, errors = {}, {}
    for q in _questions(step):
        if q.key not in markers:
            continue
        opts = q.opts(c) if (callable(q.options) or q.after) else None
        v, err = coerce(q, form, lang, opts)
        if err:
            errors[q.key] = err
            continue
        values[q.key] = v
    bound_writes = []
    for key, v in values.items():
        q = CONFIG.index()[key]
        if q.bind:
            bound_writes.append((q, v))
        else:
            _store(ct, record, q, v)
    db.session.flush()
    _save_people(ct, step, record, values, bound_writes)
    if step.key == "child_father":
        _save_child_father(ct, record, values)
    db.session.commit()
    # Recomputing which adults consent (and therefore their document requirements) after every save is cheap
    # and correct regardless of WHICH step changed the inputs (traveling_with, a child's name, or the
    # per-child father) — mirrors Tax's own routes.py calling docs.sync() unconditionally after every step.
    sync_adults(ct)
    c2 = ctx(ct, lang, record)
    if strict:
        for q in _questions(step):
            if q.req is True and c2.visible(q.key) and q.key not in errors:
                if _is_empty(c2, q, record):
                    errors[q.key] = missing_message(q, lang)
        if step.kind == "records":
            n = len(c2._records(step.record))  # noqa: SLF001
            if n == 0:
                errors["_records"] = ("Add at least one child, or go back and change your answer." if step.record == "child" else "") if lang != "es" else (
                    "Agrega al menos a un menor, o regresa y cambia tu respuesta." if step.record == "child" else "")
    return errors


def _is_empty(c, q, record):
    v = c.raw(q.key, "record" if record is not None else "self")
    return v in (None, "", [])


def _save_people(ct, step, record, values, bound_writes):
    if not bound_writes:
        return
    scope = step.scope
    if scope == "record":
        given = family = dob = None
        for q, v in bound_writes:
            if q.bind == "given_name":
                given = v
            elif q.bind == "family_name":
                family = v
            elif q.bind == "date_of_birth":
                dob = v
        owner = people.owner_for(ct, "record", record)
        if owner is None and given and family:
            owner = people.ensure_child_person(ct, record, given, family, dob)
        elif given and family:
            owner = people.ensure_child_person(ct, record, given, family, dob)
        if owner is None:
            return
        for q, v in bound_writes:
            if q.bind == "given_name":
                owner.given_name = v
                for cp in owner.case_people:
                    cp.given_name = v
            elif q.bind == "family_name":
                owner.family_name = v
                for cp in owner.case_people:
                    cp.family_name = v
            if v not in (None, ""):
                people.set_fact(ct, owner, q.bind, v, q.key)
        return
    # mother / father_traveler / third_traveler / adult-record address
    if scope in ("mother", "father_traveler", "third_traveler"):
        owner = people.owner_for(ct, scope, None)
    elif scope == "adult":  # kept for clarity; adult address step uses scope="record"
        owner = people.owner_for(ct, "record", record)
    else:
        owner = None
    if owner is None:
        return
    for q, v in bound_writes:
        if v not in (None, ""):
            people.set_fact(ct, owner, q.bind, v, q.key)


def _save_child_father(ct, record, values):
    """father_on_cert / father_pick / f_given / f_family -> the per-child father Person (item: parentage
    evaluated per child, siblings can share or differ)."""
    if record is None:
        return
    d = record.data
    if "father_on_cert" in values:
        d["father_on_cert"] = values["father_on_cert"]
    record.data = d
    if values.get("father_on_cert") != "yes" and "father_on_cert" in values:
        d.pop("father_pid", None)
        record.data = d
        return
    pick_val = values.get("father_pick")
    if pick_val and pick_val != "new":
        people.ensure_child_father(ct, record, reuse_pid=int(pick_val))
    elif values.get("f_given") and values.get("f_family"):
        people.ensure_child_father(ct, record, given=values["f_given"], family=values["f_family"])


# ------------------------------------------------------------------ children (record) management
def add_child(ct):
    rec = ConsentTravelRecord(ct_case_id=ct.id, kind="child", data_json="{}", sort_order=len(ct.children))
    db.session.add(rec)
    db.session.commit()
    db.session.refresh(ct)
    return rec


def remove_child(ct, record):
    db.session.delete(record)
    db.session.commit()
    db.session.refresh(ct)
    sync_adults(ct)
    docs.sync(ct)


def sync_children_docs(ct):
    docs.sync(ct)


# ------------------------------------------------------------------ consenting-adult sync (item: automatic, never customer add/remove)
def groups_for(ct):
    children_info = []
    for r in ct.children:
        if r.person is None:
            continue
        name = f"{r.person.given_name or ''} {r.person.family_name or ''}".strip() or f"Child #{r.id}"
        mother = people.owner_for(ct, "mother")
        tw = ct.answers.get("traveling_with")
        father_pid = r.data.get("father_pid")
        consenting = ct_rules.consenting_parents_for_child(tw, r.data.get("father_on_cert"), mother.id if mother else None, father_pid)
        children_info.append({"id": r.id, "name": name, "consenting": consenting, "needs_review": ct_rules.needs_review_flag(r.data.get("father_on_cert"))})
    return ct_rules.group_documents(children_info)


def sync_adults(ct):
    """One ConsentTravelRecord(kind="adult") per Person who must consent for AT LEAST ONE child — never the
    traveling parent (who needs an ID but no address, handled by `docs._traveler_person`), never customer
    add/remove. Removing an adult whose need disappeared (e.g. the customer removed the only child that
    needed them) is safe: their uploaded documents stay in the vault via the requirement withdrawal path."""
    needed_pids = set()
    for g in groups_for(ct):
        needed_pids |= set(g["consenting"])
    existing = {r.person.person_id: r for r in ct.adult_records if r.person is not None}
    for pid in needed_pids:
        person = people.person_by_id(ct, pid)
        if person is None or pid in existing:
            continue
        cp = people.case_person(ct, person, "parent")
        rec = ConsentTravelRecord(ct_case_id=ct.id, kind="adult", person_id=cp.id, data_json="{}", sort_order=len(ct.adult_records))
        db.session.add(rec)
    for pid, rec in existing.items():
        if pid not in needed_pids:
            db.session.delete(rec)
    db.session.commit()
    db.session.refresh(ct)
    docs.sync(ct)


# ------------------------------------------------------------------ completeness
def missing_answers(ct, lang="en"):
    c = ctx(ct, lang)
    out = []
    for step in visible_steps(c):
        if step.kind != "form":
            continue
        for q in _questions(step):
            if not c.visible(q.key) or q.req is not True:
                continue
            if c.raw(q.key) in (None, "", []):
                out.append({"step": step.key, "record": None, "label": pick(q.label, lang)})
    for kind, flow in CONFIG.record_flows.items():
        for r in c._records(kind):  # noqa: SLF001
            rc = ctx(ct, lang, r)
            for st in flow:
                for q in _questions(st):
                    if not rc.visible(q.key) or q.req is not True:
                        continue
                    if rc.raw(q.key, "record") in (None, "", []):
                        who = (people.info(ct, r).get("given") if kind == "child" else "") or f"#{r.id}"
                        out.append({"step": st.key, "record": r.id, "kind": kind, "label": f"{who}: {pick(q.label, lang)}"})
    return out


def missing_info(ct, lang="en"):
    items = [{"kind": "answer", **m} for m in missing_answers(ct, lang)]
    for r in docs.missing_required(ct):
        title, _msg = docs.req_text(r, lang)
        items.append({"kind": "doc", "label": title, "step": "documents_vault", "record": None, "req": r.id})
    return items


# ------------------------------------------------------------------ submit (Pending OG Review — never payable yet)
def submit(ct, student, lang, certified, terms_ok, meta):
    if ct.status not in EDITABLE:
        return False, "state"
    if not (certified and terms_ok):
        return False, "accept"
    if missing_answers(ct, lang):
        return False, "incomplete"
    if not ct.children:
        return False, "incomplete"
    import hashlib

    from app.consent_travel import terms

    salt = "og-terms"
    iph = hashlib.sha256((salt + (meta.get("ip") or "")).encode()).hexdigest() if meta.get("ip") else None
    acc = TermsAcceptance(customer_id=student.id, case_id=ct.case_id, terms_key=terms.TERMS_KEY, version=terms.VERSION, language=lang, certification_accepted=True,
                          terms_accepted=True, ip_hash=iph, user_agent=(meta.get("ua") or "")[:200])
    db.session.add(acc)
    db.session.flush()
    ct.terms_id = acc.id
    docs.sync(ct)
    was_reopened = ct.status == "reopened"
    quote, _created = pricing.snapshot(ct, groups_for(ct))
    ct.language = lang
    ct.submitted_at = datetime.utcnow()
    ct.reopen_message = None
    if was_reopened:
        ct.resubmit_count = (ct.resubmit_count or 0) + 1
    set_case_status(ct, "submitted")
    db.session.commit()
    log(ct, "consent_travel_resubmitted" if was_reopened else "consent_travel_submitted")
    _notify(ct, "service_submitted", lang)
    return True, None


# ------------------------------------------------------------------ workflow (staff)
def set_status(ct, status, staff, *, message=None):
    from app.models import CT_STATUS_EN

    if status not in CT_STATUS_EN or status in ("draft",):
        return False, "Choose a status from the list."
    before = ct.status
    if status == "waiting_client" and message:
        ct.customer_message = message.strip()[:2000]
    set_case_status(ct, status)
    db.session.commit()
    if before != status:
        log(ct, "consent_travel_completed" if status == "completed" else "consent_travel_status_changed", {"from": before, "to": status}, actor="admin")
        if status == "completed":
            _notify(ct, "service_completed")
    return True, None


def request_info(ct, message, staff):
    if not (message or "").strip():
        return False, "Write what you need from the customer."
    ct.customer_message = message.strip()[:2000]
    set_case_status(ct, "waiting_client")
    db.session.commit()
    log(ct, "consent_travel_info_requested", actor="admin")
    _notify(ct, "info_needed")
    return True, None


def approve(ct, total_cents, staff, admin_id, reason=None):
    """The ONLY action that makes a PaymentRequest possible (item: "Solamente después de aprobación de OG se
    crea/habilita el PaymentRequest"). Confirms the price and moves the case out of "Submitted"."""
    if ct.status not in ("submitted", "waiting_client"):
        return False, "This case is not pending OG review."
    pricing.confirm(ct, total_cents, staff, reason)
    ct.approved_at = datetime.utcnow()
    ct.approved_by_admin_id = admin_id
    set_case_status(ct, "approved")
    db.session.commit()
    log(ct, "consent_travel_approved", {"total": total_cents}, actor="admin", actor_id=admin_id)
    _notify(ct, "service_completed")  # reuse existing "here's an update" template; a dedicated one is future work
    return True, None


def reopen(ct, message, staff, actor_id=None):
    if ct.status in ("draft", "reopened"):
        return False, "The customer can already edit this."
    ct.reopen_message = (message or "").strip()[:2000] or None
    ct.reopened_at = datetime.utcnow()
    set_case_status(ct, "reopened")
    db.session.commit()
    log(ct, "consent_travel_reopened", actor="admin")
    return True, None
