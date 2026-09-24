"""Tax Return case services: create / resume, save an interview step, records (dependents, self-employment activities), submit to OG, workflow.

Sending to OG is NEVER filing: OG's tax software prepares, calculates and e-files; this portal collects facts, documents, preferences and workflow.
"""

import hashlib
import re
from datetime import datetime, timedelta

from app import cases as case_svc
from app import persons as pers
from app import secure_store
from app.activity import log_event
from app.extensions import db
from app.models import ActivityEvent, Case, TaxBankInfo, TaxCaseData, TaxRecord, TermsAcceptance
from app.tax import docs, people, pricing
from app.tax.questions import Ctx, coerce, missing_message, pick, routing_ok
from app.tax.registry import CURRENT_YEAR, config_for

def _notify(tax, template_key, lang=None):
    try:
        from app.email_service import send_transactional_email

        student = tax.case.customer
        send_transactional_email(student, template_key, lang or student.preferred_language or "en",
                                 ref={"kind": "tax", "id": tax.id}, related_type="tax_case", related_id=tax.id)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("og_email").exception("[tax] %r email failed to queue", template_key)


CASE_TYPE = "tax_return"
EDITABLE = ("draft", "reopened")
DONE_STATES = ("filed", "accepted", "completed")
CASE_STATUS_OF = {"draft": "open", "submitted": "in_review", "og_review": "in_review", "waiting_client": "waiting_client", "ready_prep": "in_review", "in_prep": "in_review",
                  "client_review": "waiting_client", "ready_file": "in_review", "filed": "in_review", "accepted": "in_review", "completed": "completed", "rejected": "in_review",
                  "amendment": "in_review", "on_hold": "in_review", "closed": "closed", "reopened": "waiting_client"}


# ------------------------------------------------------------------ access
def ctx(tax, lang="en", record=None):
    def bound(scope, bind):
        return people.get_fact(people.owner_for(tax, scope, record if scope == "record" else None), bind)

    return Ctx(tax, config_for(tax.tax_year), lang, record, bound, lambda r: people.info(tax, r))


def owned(student, case_id):
    """The signed-in customer's own tax case (else None): the case id in a URL is only ever looked up THROUGH the customer."""
    case = Case.query.filter_by(id=case_id, customer_id=student.id, case_type=CASE_TYPE).first()
    return case.tax_data if case is not None else None


def owned_record(tax, record_id):
    return next((r for r in tax.records if r.id == record_id), None)


def log(tax, event, meta=None, *, actor="customer", actor_id=None):
    """Meaningful event only. `meta` never carries an identifier, an amount of income or a document's contents."""
    case_svc.case_event(tax.case, event, actor=actor, actor_id=actor_id, meta=dict(meta or {}, year=tax.tax_year))


# ------------------------------------------------------------------ create / resume
def returning_status(student, year):
    """A returning tax customer has an earlier tax return that OG prepared to completion (from OG's own records, never a checkbox)."""
    return (TaxCaseData.query.join(Case, Case.id == TaxCaseData.case_id)
            .filter(Case.customer_id == student.id, TaxCaseData.tax_year < year, TaxCaseData.status.in_(DONE_STATES)).count() > 0)


def active_case(student, year=CURRENT_YEAR):
    return (TaxCaseData.query.join(Case, Case.id == TaxCaseData.case_id)
            .filter(Case.customer_id == student.id, TaxCaseData.tax_year == year, Case.status != "closed", TaxCaseData.status != "closed")
            .order_by(TaxCaseData.id.desc()).first())


def start_or_resume(student, lang, year=CURRENT_YEAR):
    """(tax, created). Never a second active case for the same customer and tax year."""
    tax = active_case(student, year)
    if tax is not None:
        recent = ActivityEvent.query.filter_by(customer_id=student.id, case_id=tax.case_id, event_type="tax_intake_resumed").order_by(ActivityEvent.id.desc()).first()
        if tax.status in EDITABLE and (recent is None or datetime.utcnow() - recent.created_at > timedelta(hours=1)):
            log(tax, "tax_intake_resumed")
        return tax, False
    title = f"Tax Return — {year}" if lang != "es" else f"Declaración de impuestos — {year}"
    case = case_svc.create_case(student, CASE_TYPE, title, origin="auto", lang=lang, quiet=True)
    tax = TaxCaseData(case_id=case.id, tax_year=year, language=lang, is_returning=returning_status(student, year), current_step="intro")
    db.session.add(tax)
    db.session.commit()
    db.session.refresh(case)
    people.case_person(tax, people.self_person(tax), "self")
    db.session.commit()
    log(tax, "tax_case_created", {"title": case.title, "returning": tax.is_returning})
    return tax, True


def set_case_status(tax, status):
    tax.status = status
    tax.case.status = CASE_STATUS_OF.get(status, tax.case.status)
    tax.case.updated_at = datetime.utcnow()


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
    n = keys.index(key) + 1 if key in keys else 1
    return {"step": n, "total": len(keys), "percent": int(round(100 * n / max(1, len(keys))))}


def _questions(step):
    return [q for q in step.questions if q.kind not in ("note", "docs", "records", "person_pick")]


def _store(tax, record, q, value):
    if record is not None and q.key in config_for(tax.tax_year).record_keys:
        d = record.data
        d[q.key] = value
        record.data = d
    else:
        a = tax.answers
        a[q.key] = value
        tax.answers = a


def _existing_bank(tax):
    return tax.bank is not None and bool(tax.bank.account_enc)


def save_step(tax, step, form, lang, record=None, strict=False):
    """Save what the customer posted for one step. Returns (errors: {key: message}, extras). Hidden answers are kept; invalid values are not stored."""
    cfg = config_for(tax.tax_year)
    c = ctx(tax, lang, record)
    markers = set(form.getlist("__q"))
    values, errors, secrets = {}, {}, {}
    for q in _questions(step):
        if q.key not in markers:
            continue
        opts = q.opts(c) if (callable(q.options) or q.after) else None
        v, err = coerce(q, form, lang, opts)
        if q.kind == "secret":
            secrets[q.key] = v
            continue
        if err:
            errors[q.key] = err
            continue
        values[q.key] = v
    bound_writes = []
    for key, v in values.items():
        q = cfg.index()[key]
        if q.bind:
            bound_writes.append((q, v))
        else:
            _store(tax, record, q, v)
    db.session.flush()
    _save_people(tax, step, record, values, bound_writes, form)
    if step.key == "refund":
        _save_bank(tax, form, secrets, errors, lang)
    db.session.commit()
    c2 = ctx(tax, lang, record)
    if strict:
        for q in _questions(step):
            if q.req is True and c2.visible(q.key) and q.key not in errors:
                if q.kind == "secret":
                    if not secrets.get(q.key) and not _existing_bank(tax):
                        errors[q.key] = missing_message(q, lang)
                elif _is_empty(tax, c2, q, values, record):
                    errors[q.key] = missing_message(q, lang)
        if step.kind == "records":
            n = len(c2.deps) if step.record == "dependent" else len(c2.bizs)
            if n == 0:
                errors["_records"] = ("Add at least one person, or go back and change your answer." if step.record == "dependent" else "Add at least one job, or go back and change your answer.") if lang != "es" else (
                    "Agrega al menos a una persona, o regresa y cambia tu respuesta." if step.record == "dependent" else "Agrega al menos un trabajo, o regresa y cambia tu respuesta.")
    return errors


def _is_empty(tax, c, q, values, record):
    if q.kind == "secret":
        return True
    v = c.raw(q.key, "record" if record is not None else "self")
    return v in (None, "", [])


def _save_people(tax, step, record, values, bound_writes, form):
    """Person-bound answers -> the real Person's facts (creating / linking the Person for a spouse or dependent once their names exist)."""
    if not bound_writes:
        return
    scope = step.scope
    given = family = dob = None
    for q, v in bound_writes:
        if q.bind == "given_name":
            given = v
        elif q.bind == "family_name":
            family = v
        elif q.bind == "date_of_birth":
            dob = v
    owner = people.owner_for(tax, scope, record if scope == "record" else None)
    if owner is None:
        c = ctx(tax, "en", record)
        given = given or (c.raw("s_given") if scope == "spouse" else c.raw("d_given"))
        family = family or (c.raw("s_family") if scope == "spouse" else c.raw("d_family"))
        dob = dob or (c.raw("s_dob") if scope == "spouse" else c.raw("d_dob"))
        if given and family:
            if scope == "spouse":
                owner = people.ensure_spouse_person(tax, given, family, dob)
            elif scope == "record":
                owner = people.ensure_dependent_person(tax, record, given, family, dob)
    elif scope == "record" and given and family:
        owner = people.ensure_dependent_person(tax, record, given, family, dob)
    elif scope == "spouse" and given and family:
        owner = people.ensure_spouse_person(tax, given, family, dob)
    if owner is None:
        return
    for q, v in bound_writes:
        if q.bind in ("given_name", "family_name"):
            if q.bind == "given_name":
                owner.given_name = v
            else:
                owner.family_name = v
            for cp in owner.case_people:
                if q.bind == "given_name":
                    cp.given_name = v
                else:
                    cp.family_name = v
        if v not in (None, ""):
            people.set_fact(tax, owner, q.bind, v, q.key)


def _save_bank(tax, form, secrets, errors, lang):
    from app.tax.questions import ERR

    en = lang != "es"
    if (tax.answers.get("dd_want") or "") != "yes":
        if tax.bank is not None:
            db.session.delete(tax.bank)
        return
    routing = re.sub(r"\D", "", secrets.get("dd_routing") or "")
    acct = re.sub(r"\D", "", secrets.get("dd_account") or "")
    acct2 = re.sub(r"\D", "", secrets.get("dd_account2") or "")
    kind = tax.answers.get("dd_type")
    if not (routing or acct or acct2):
        return  # nothing typed: keep what is saved
    if not routing_ok(routing):
        errors["dd_routing"] = ERR["routing"][0 if en else 1]
    if not 4 <= len(acct) <= 17:
        errors["dd_account"] = ERR["account"][0 if en else 1]
    elif acct != acct2:
        errors["dd_account2"] = "The account numbers do not match." if en else "Los números de cuenta no coinciden."
    if errors.get("dd_routing") or errors.get("dd_account") or errors.get("dd_account2"):
        return
    if not secure_store.available():
        errors["dd_routing"] = ("For your safety we cannot save bank details right now. Tell OG you want direct deposit." if en else "Por tu seguridad no podemos guardar datos bancarios ahora. Dile a OG que quieres depósito directo.")
        return
    bank = tax.bank or TaxBankInfo(tax_case_id=tax.id)
    bank.account_type = kind if kind in ("checking", "savings") else None
    bank.routing_enc, bank.account_enc = secure_store.encrypt(routing), secure_store.encrypt(acct)
    bank.routing_last4, bank.account_last4 = routing[-4:], acct[-4:]
    db.session.add(bank)


# ------------------------------------------------------------------ records
def add_record(tax, kind):
    rec = TaxRecord(tax_case_id=tax.id, kind=kind, data_json="{}", sort_order=len([r for r in tax.records if r.kind == kind]))
    db.session.add(rec)
    db.session.commit()
    db.session.refresh(tax)
    return rec


def carry_over(tax, person):
    """Bring a dependent from a previous year: the same real Person, stable facts prefilled; every annual fact is asked again."""
    cp = people.case_person(tax, person, "child")
    if any(r.person_id == cp.id for r in tax.records if r.kind == "dependent"):
        return next(r for r in tax.records if r.person_id == cp.id)
    rec = TaxRecord(tax_case_id=tax.id, kind="dependent", person_id=cp.id, data_json="{}", sort_order=len([r for r in tax.records if r.kind == "dependent"]))
    db.session.add(rec)
    db.session.commit()
    db.session.refresh(tax)
    return rec


def remove_record(tax, record):
    db.session.delete(record)
    db.session.commit()
    db.session.refresh(tax)
    docs.sync(tax)


def previous_dependents(tax):
    """Real Persons the customer included as dependents in an EARLIER tax year (offered again, never copied silently)."""
    out, seen = [], {r.person.person_id for r in tax.records if r.kind == "dependent" and r.person is not None}
    q = (TaxRecord.query.join(TaxCaseData, TaxCaseData.id == TaxRecord.tax_case_id).join(Case, Case.id == TaxCaseData.case_id)
         .filter(Case.customer_id == tax.case.customer_id, TaxCaseData.tax_year < tax.tax_year, TaxRecord.kind == "dependent").order_by(TaxRecord.id.desc()).all())
    for r in q:
        if r.person is not None and r.person.person_id not in seen and r.person.person is not None:
            seen.add(r.person.person_id)
            out.append(r.person.person)
    return out


# ------------------------------------------------------------------ completeness
def missing_answers(tax, lang="en"):
    """[{step, record, label, level}] of REQUIRED (True) and soft answers still empty, on the path the answers create."""
    c = ctx(tax, lang)
    cfg = config_for(tax.tax_year)
    out = []
    for step in visible_steps(c):
        if step.kind not in ("form",):
            continue
        for q in _questions(step):
            if not c.visible(q.key) or q.req not in (True, "soft"):
                continue
            if q.kind == "secret":
                if not _existing_bank(tax):
                    out.append({"step": step.key, "record": None, "label": pick(q.label, lang), "level": "required" if q.req is True else "soft"})
                continue
            if c.raw(q.key) in (None, "", []):
                out.append({"step": step.key, "record": None, "label": pick(q.label, lang), "level": "required" if q.req is True else "soft"})
    for kind, flow in cfg.record_flows.items():
        for r in (c.deps if kind == "dependent" else c.bizs):
            if kind == "dependent" and not any(s.key == "deps" for s in visible_steps(c)):
                continue
            if kind == "business" and not any(s.key == "business" for s in visible_steps(c)):
                continue
            rc = ctx(tax, lang, r)
            for st in flow:
                for q in _questions(st):
                    if not rc.visible(q.key) or q.req not in (True, "soft"):
                        continue
                    if rc.raw(q.key, "record") in (None, "", []):
                        who = (people.info(tax, r).get("given") if kind == "dependent" else (r.data.get("b_desc") or "")) or f"#{r.id}"
                        out.append({"step": st.key, "record": r.id, "label": f"{who}: {pick(q.label, lang)}", "level": "required" if q.req is True else "soft"})
    return out


def required_missing(tax, lang="en"):
    return [m for m in missing_answers(tax, lang) if m["level"] == "required"]


def missing_info(tax, lang="en"):
    """Everything that keeps the case from being READY FOR PREPARATION (never a reason to block sending to OG)."""
    items = [{"kind": "answer", **m} for m in missing_answers(tax, lang)]
    for r in docs.missing_required(tax):
        title, _msg = docs.req_text(r, lang)
        items.append({"kind": "doc", "label": title, "level": "required", "step": "documents", "record": None, "req": r.id})
    return items


# ------------------------------------------------------------------ submit
def submit(tax, student, lang, certified, terms_ok, meta):
    """(ok, error_key). Sends the information to OG. It is NOT a filing."""
    if tax.status not in EDITABLE:
        return False, "state"
    if not (certified and terms_ok):
        return False, "accept"
    if required_missing(tax, lang):
        return False, "incomplete"
    from app.tax import terms

    salt = "og-terms"
    iph = hashlib.sha256((salt + (meta.get("ip") or "")).encode()).hexdigest() if meta.get("ip") else None
    acc = TermsAcceptance(customer_id=student.id, case_id=tax.case_id, terms_key=terms.TERMS_KEY, version=terms.version_for(tax.tax_year), language=lang, certification_accepted=True,
                          terms_accepted=True, ip_hash=iph, user_agent=(meta.get("ua") or "")[:200])
    db.session.add(acc)
    db.session.flush()
    tax.terms_id = acc.id
    docs.sync(tax, ctx(tax, "en"))
    was_reopened = tax.status == "reopened"
    quote, created = pricing.snapshot(tax, ctx(tax, "en"))
    tax.language = lang
    tax.submitted_at = datetime.utcnow()
    tax.reopen_message = None
    if was_reopened:
        tax.resubmit_count = (tax.resubmit_count or 0) + 1
        from app import case_revisions

        case_revisions.close_revision(tax.case, config_for(tax.tax_year), case_revisions.snapshot_answers(config_for(tax.tax_year), ctx(tax, "en")), lang)
    set_case_status(tax, "submitted")
    db.session.commit()
    log(tax, "tax_resubmitted" if was_reopened else "tax_submitted")
    _notify(tax, "service_submitted", lang)
    if created:
        log(tax, "tax_price_calculated", {"mode": quote.mode, "revision": quote.revision})
        if quote.discount_cents:
            log(tax, "tax_discount_applied", {"percent": quote.discount_percent})
    return True, None


# ------------------------------------------------------------------ workflow (staff)
def readiness(tax, lang="en"):
    """Blockers for Ready for Preparation: required information and documents still missing. Sending to OG is never blocked by these."""
    return [m for m in missing_info(tax, lang) if m["level"] == "required"]


def set_status(tax, status, staff, *, message=None, when=None, note=None, force=False):
    from app.models import TAX_STATUS_EN

    if status not in TAX_STATUS_EN or status in ("draft",):
        return False, "Choose a status from the list."
    if status == "ready_prep" and not force and readiness(tax):
        return False, "Not ready yet: " + "; ".join(m["label"] for m in readiness(tax)[:8])
    if status in ("in_prep", "client_review", "ready_file", "filed") and tax.price_status != "confirmed" and not force:
        return False, "Confirm the preparation fee first."
    before = tax.status
    if status == "waiting_client" and message:
        tax.customer_message = message.strip()[:2000]
    if status == "filed":
        tax.filed_at = when or datetime.utcnow().date()
        tax.filing_note = (note or "")[:300] or tax.filing_note
    if status == "accepted":
        tax.accepted_at = when or datetime.utcnow().date()
    set_case_status(tax, status)
    db.session.commit()
    if before != status:
        from app.models import TAX_STATUS_EN as EN

        log(tax, "tax_completed" if status == "completed" else "tax_status_changed", {"from_label": EN.get(before, before), "to_label": EN.get(status, status)}, actor="admin")
        if status == "completed":
            _notify(tax, "service_completed")
    return True, None


def request_info(tax, message, staff):
    if not (message or "").strip():
        return False, "Write what you need from the customer."
    tax.customer_message = message.strip()[:2000]
    set_case_status(tax, "waiting_client")
    db.session.commit()
    log(tax, "tax_info_requested", actor="admin")
    _notify(tax, "info_needed")
    return True, None


def reopen(tax, message, staff, actor_id=None):
    if tax.status in ("draft", "reopened"):
        return False, "The customer can already edit this."
    from app import case_revisions

    tax.reopen_message = (message or "").strip()[:2000] or None
    tax.reopened_at = datetime.utcnow()
    set_case_status(tax, "reopened")
    case_revisions.open_revision(tax.case, tax.reopen_message, actor="admin", actor_id=actor_id,
                                 before_answers=case_revisions.snapshot_answers(config_for(tax.tax_year), ctx(tax, "en")))
    db.session.commit()
    log(tax, "tax_reopened", actor="admin")
    return True, None
