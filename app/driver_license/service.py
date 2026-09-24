"""NJ Driver License Assistance case services: create / resume, save an interview step, submit to OG (never an MVC application), milestones, workflow.

Creating an OG account never creates a Driver License Case (see `app.driver_license.quiz` for the account-only Knowledge Test practice path);
a case exists only once the customer actually starts this intake (`start_or_resume`, called from the "Get Started" route)."""

import hashlib
from datetime import datetime, timedelta

from app import cases as case_svc
from app.activity import log_event
from app.extensions import db
from app.models import ActivityEvent, Case, DlCaseData, TermsAcceptance
from app.driver_license import docs, people, pricing, rules
from app.driver_license.config import CONFIG
from app.tax.questions import Ctx, coerce, missing_message, pick

def _notify(dl, template_key, lang=None):
    try:
        from app.email_service import send_transactional_email

        student = dl.case.customer
        send_transactional_email(student, template_key, lang or student.preferred_language or "en",
                                 ref={"kind": "dl", "id": dl.id}, related_type="dl_case", related_id=dl.id)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("og_email").exception("[driver_license] %r email failed to queue", template_key)


CASE_TYPE = "nj_driver_license"
EDITABLE = ("draft", "reopened")
CASE_STATUS_OF = {"draft": "open", "submitted": "in_review", "og_review": "in_review", "waiting_client": "waiting_client",
                  "in_progress": "in_review", "completed": "completed", "on_hold": "in_review", "closed": "closed", "reopened": "waiting_client"}


# ------------------------------------------------------------------ access
def ctx(dl, lang="en"):
    def bound(scope, bind):
        return people.get_fact(people.self_person(dl), bind)

    return Ctx(dl, CONFIG, lang, None, bound, None)


def owned(student, case_id):
    case = Case.query.filter_by(id=case_id, customer_id=student.id, case_type=CASE_TYPE).first()
    return case.dl_data if case is not None else None


def owned_current(student=None):
    """The signed-in customer's Driver License case (there is only ever one, editable or not — unlike Tax/Immigration, this
    service never needs a case id in its URLs)."""
    from app.student_auth import current_student

    student = student or current_student()
    if student is None:
        return None
    return (DlCaseData.query.join(Case, Case.id == DlCaseData.case_id)
            .filter(Case.customer_id == student.id).order_by(DlCaseData.updated_at.desc(), DlCaseData.id.desc()).first())


def log(dl, event, meta=None, *, actor="customer", actor_id=None):
    case_svc.case_event(dl.case, event, actor=actor, actor_id=actor_id, meta=meta or {})


# ------------------------------------------------------------------ create / resume
def active_case(student):
    return (DlCaseData.query.join(Case, Case.id == DlCaseData.case_id)
            .filter(Case.customer_id == student.id, Case.status != "closed", DlCaseData.status != "closed")
            .order_by(DlCaseData.id.desc()).first())


def start_or_resume(student, lang):
    """(dl, created). Never a second active Driver License case for the same customer."""
    dl = active_case(student)
    if dl is not None:
        recent = ActivityEvent.query.filter_by(customer_id=student.id, case_id=dl.case_id, event_type="dl_intake_resumed").order_by(ActivityEvent.id.desc()).first()
        if dl.status in EDITABLE and (recent is None or datetime.utcnow() - recent.created_at > timedelta(hours=1)):
            log(dl, "dl_intake_resumed")
        return dl, False
    title = "NJ Driver License" if lang != "es" else "Licencia de Conducir de NJ"
    case = case_svc.create_case(student, CASE_TYPE, title, origin="auto", lang=lang, quiet=True)
    dl = DlCaseData(case_id=case.id, language=lang, current_step="intro")
    db.session.add(dl)
    db.session.commit()
    case_svc.ensure_customer_person(case)
    db.session.commit()
    log(dl, "dl_case_created", {"title": case.title})
    return dl, True


def set_case_status(dl, status):
    dl.status = status
    dl.case.status = CASE_STATUS_OF.get(status, dl.case.status)
    dl.case.updated_at = datetime.utcnow()


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
    return [q for q in step.questions if q.kind not in ("note", "docs")]


def save_step(dl, step, form, lang, strict=False):
    """Save what the customer posted for one step. Returns errors: {key: message}."""
    c = ctx(dl, lang)
    markers = set(form.getlist("__q"))
    values, errors, bound_writes = {}, {}, []
    for q in _questions(step):
        if q.key not in markers:
            continue
        opts = q.opts(c) if (callable(q.options) or q.after) else None
        v, err = coerce(q, form, lang, opts)
        if err:
            errors[q.key] = err
            continue
        values[q.key] = v
    for key, v in values.items():
        q = CONFIG.index()[key]
        if q.bind:
            bound_writes.append((q, v))
        else:
            answers = dl.answers
            answers[key] = v
            dl.answers = answers
    db.session.flush()
    if bound_writes:
        owner = people.self_person(dl)
        for q, v in bound_writes:
            if v not in (None, ""):
                people.set_fact(owner, q.bind, v, q.key)
    db.session.commit()
    docs.sync(dl)
    c2 = ctx(dl, lang)
    if strict:
        for q in _questions(step):
            if q.req is True and c2.visible(q.key) and q.key not in errors:
                v = c2.raw(q.key)
                if v in (None, "", []):
                    errors[q.key] = missing_message(q, lang)
    return errors


# ------------------------------------------------------------------ completeness
def missing_answers(dl, lang="en"):
    c = ctx(dl, lang)
    out = []
    for step in visible_steps(c):
        if step.kind != "form":
            continue
        for q in _questions(step):
            if not c.visible(q.key) or q.req is not True:
                continue
            if c.raw(q.key) in (None, "", []):
                out.append({"step": step.key, "label": pick(q.label, lang)})
    return out


def missing_info(dl, lang="en"):
    items = [{"kind": "answer", **m} for m in missing_answers(dl, lang)]
    for r in docs.missing_required(dl):
        title, _msg = docs.req_text(r, lang)
        items.append({"kind": "doc", "label": title, "step": "documents_vault"})
    return items


def readiness(dl, lang="en"):
    return missing_info(dl, lang)


# ------------------------------------------------------------------ documents assessment (rules engine snapshot)
def assess(dl, c=None):
    c = c or ctx(dl, "en")
    return rules.assess(c.v("documents") or [], c.v("ssn_itin_path"), c.v("address_doc"), c.v("fl_valid"))


# ------------------------------------------------------------------ submit
def submit(dl, student, lang, certified, terms_ok, meta):
    if dl.status not in EDITABLE:
        return False, "state"
    if not (certified and terms_ok):
        return False, "accept"
    if missing_answers(dl, lang):
        return False, "incomplete"
    from app.driver_license import terms

    salt = "og-terms"
    iph = hashlib.sha256((salt + (meta.get("ip") or "")).encode()).hexdigest() if meta.get("ip") else None
    acc = TermsAcceptance(customer_id=student.id, case_id=dl.case_id, terms_key=terms.TERMS_KEY, version=terms.version_for(), language=lang,
                          certification_accepted=True, terms_accepted=True, ip_hash=iph, user_agent=(meta.get("ua") or "")[:200])
    db.session.add(acc)
    db.session.flush()
    dl.terms_id = acc.id
    c = ctx(dl, "en")
    docs.sync(dl, c)
    a = assess(dl, c)
    dl.rules_version = a["rules_version"]
    was_reopened = dl.status == "reopened"
    quote, created = pricing.snapshot(dl, c)
    dl.language = lang
    dl.submitted_at = datetime.utcnow()
    dl.reopen_message = None
    if was_reopened:
        dl.resubmit_count = (dl.resubmit_count or 0) + 1
        from app import case_revisions

        case_revisions.close_revision(dl.case, CONFIG, case_revisions.snapshot_answers(CONFIG, c), lang)
    set_case_status(dl, "submitted")
    db.session.commit()
    log(dl, "dl_resubmitted" if was_reopened else "dl_submitted")
    if created:
        log(dl, "dl_price_calculated", {"mode": quote.status})
    _notify(dl, "service_submitted", lang)
    return True, None


# ------------------------------------------------------------------ workflow (staff)
def set_status(dl, status, staff, *, message=None, force=False):
    from app.models import DL_STATUS_EN

    if status not in DL_STATUS_EN or status == "draft":
        return False, "Choose a status from the list."
    before = dl.status
    if status == "waiting_client" and message:
        dl.customer_message = message.strip()[:2000]
    set_case_status(dl, status)
    db.session.commit()
    if before != status:
        log(dl, "dl_completed" if status == "completed" else "dl_status_changed", {"from_label": DL_STATUS_EN.get(before, before), "to_label": DL_STATUS_EN.get(status, status)}, actor="admin")
        if status == "completed":
            _notify(dl, "service_completed")
    return True, None


def request_info(dl, message, staff):
    if not (message or "").strip():
        return False, "Write what you need from the customer."
    dl.customer_message = message.strip()[:2000]
    set_case_status(dl, "waiting_client")
    db.session.commit()
    log(dl, "dl_info_requested", actor="admin")
    _notify(dl, "info_needed")
    return True, None


def reopen(dl, message, staff, actor="admin", actor_id=None):
    """`actor`: "admin" (staff reopens from the Admin panel) or "customer" (NJ Driver License self-edit —
    see `start_self_edit`). Both produce the identical `CaseRevision` audit trail; only who gets credit differs."""
    if dl.status in ("draft", "reopened"):
        return False, "The customer can already edit this."
    from app import case_revisions

    dl.reopen_message = (message or "").strip()[:2000] or None
    dl.reopened_at = datetime.utcnow()
    set_case_status(dl, "reopened")
    case_revisions.open_revision(dl.case, dl.reopen_message, actor=actor, actor_id=actor_id,
                                 before_answers=case_revisions.snapshot_answers(CONFIG, ctx(dl, "en")))
    db.session.commit()
    log(dl, "dl_reopened", actor=actor, actor_id=actor_id)
    return True, None


# ------------------------------------------------------------------ NJ Driver License self-service correction (customer-initiated, no Admin wait)
# Intentionally more flexible than every other Smart Intake (see CLAUDE.md "NJ Driver License self-edit"): once the
# customer has SENT their information, they may still notice a mistake and correct it themselves. Blocked once the
# case is done (nothing left to correct) or already mid-edit (no double reopen) — matches `EDITABLE`/`reopen()`'s
# own guard, just phrased for the customer-facing eligibility check.
SELF_EDIT_BLOCKED_STATUSES = ("draft", "reopened", "completed", "closed")
SELF_EDIT_BLOCKED_MILESTONES = ("license_obtained", "completed")


def can_self_edit(dl):
    return dl.status not in SELF_EDIT_BLOCKED_STATUSES and dl.milestone not in SELF_EDIT_BLOCKED_MILESTONES


def start_self_edit(dl, student):
    """The customer's own "Edit My Information" — reuses `reopen()` unchanged except `actor="customer"`, so the
    SAME `CaseRevision` audit trail, the SAME step flow, and the SAME resubmit path as an Admin reopen. Never a
    new Case, Person or Driver License service."""
    if not can_self_edit(dl):
        return False, "not_eligible"
    ok, err = reopen(dl, None, None, actor="customer", actor_id=student.id)
    if ok:
        log(dl, "dl_self_edit_started", actor="customer", actor_id=student.id)
    return ok, err


def discard_self_edit(dl, student, lang="en"):
    """Item 52: throws away an in-progress SELF-edit (never an Admin-initiated reopen — staff use "Reopen" /
    "Lock again" instead) by restoring every answer (including bound Person facts) to the snapshot taken the
    moment the customer chose "Edit My Information", then closing that revision with before==after so it reads
    to Admin as "0 answers changed" rather than leaving a dangling open revision."""
    import json

    from app import case_revisions

    rev = next((r for r in reversed(dl.case.revisions) if r.resubmitted_at is None), None)
    if rev is None or rev.reopened_by != "customer" or dl.status != "reopened":
        return False, "nothing_to_discard"
    before = json.loads(rev.before_json or "{}")
    owner = people.self_person(dl)
    for key, value in before.items():
        q = CONFIG.index().get(key)
        if q is None:
            continue
        if q.bind:
            if value not in (None, ""):
                people.set_fact(owner, q.bind, value, key)
        else:
            answers = dl.answers
            answers[key] = value
            dl.answers = answers
    dl.status = "submitted"
    dl.case.status = CASE_STATUS_OF.get("submitted", dl.case.status)
    dl.reopen_message = None
    db.session.commit()
    docs.sync(dl)
    case_revisions.close_revision(dl.case, CONFIG, before, lang)
    log(dl, "dl_self_edit_discarded", actor="customer", actor_id=student.id)
    return True, None


def set_milestone(dl, milestone, staff):
    from app.models import DL_MILESTONE_ORDER

    if milestone not in DL_MILESTONE_ORDER:
        return False, "Choose a milestone from the list."
    before = dl.milestone
    dl.milestone = milestone
    db.session.commit()
    if before != milestone:
        from app.models import DL_MILESTONE_EN

        log(dl, "dl_milestone_changed", {"from_label": DL_MILESTONE_EN.get(before, before), "to_label": DL_MILESTONE_EN.get(milestone, milestone)}, actor="admin")
    return True, None


def set_sub_status(dl, field, value, staff, *, valid=()):
    if valid and value not in valid:
        return False, "Choose a valid status."
    setattr(dl, field, value)
    db.session.commit()
    log(dl, "dl_milestone_changed", {"field": field, "value": value}, actor="admin")
    return True, None
