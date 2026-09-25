"""Account invitations for imported (Wix-migrated) customers — mirrors app/password_reset.py's exact
security shape (SHA-256 hash of a high-entropy token, expiring, single-use), plus the extra states a
BULK migration needs: queued -> sent -> activated | failed. See app/models/customer_import.py for why a
"queued" row deliberately has no token yet.

Sending is a controlled, rate-limited BATCH, never an unbounded blast: `queue_invitations()` only ever
creates rows (fast, no email); `process_queue()` is the one place that actually mints tokens and calls
the existing transactional-email seam, capped at SEND_BATCH_LIMIT per call and gated by the shared
app.ratelimit limiter — so one admin click can never fire hundreds of SMTP sends inside one request
(this project's single Gunicorn worker request has a 60s timeout, and Titan SMTP's real throughput was
never assumed). Whatever doesn't fit in one call stays "queued"; "Send Next Batch" calls it again.
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from app.activity import log_event
from app.extensions import db
from app.models import AccountInvitation
from app.ratelimit import allow

TOKEN_EXPIRY_DAYS = 7
SEND_BATCH_LIMIT = 20
RATE_LIMIT_KEY = "account_invitation_send"
RATE_LIMIT_PER_MINUTE = 30  # matches SEND_BATCH_LIMIT with headroom for a resend here and there


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def eligible_for_invite(student):
    """"only when appropriate" (spec): a customer who already has a real, usable account is never
    re-invited — only one imported with a placeholder password and no account activation yet."""
    if not student.needs_activation:
        return False
    return not AccountInvitation.query.filter_by(student_id=student.id).filter(AccountInvitation.status.in_(("queued", "sent"))).first()


def queue_invitations(students, *, batch_id=None, admin_id=None):
    """Creates queued rows only — never sends email itself. Skips a student who already has an active
    (queued/sent) invitation, so re-clicking "Send Invitations" can never create duplicate invites."""
    created = []
    for s in students:
        if not eligible_for_invite(s):
            continue
        inv = AccountInvitation(student_id=s.id, batch_id=batch_id, status="queued", created_at=datetime.utcnow(), invited_by_admin_id=admin_id)
        db.session.add(inv)
        created.append(inv)
    db.session.commit()
    return created


def _send(inv):
    from app.email_render import abs_url
    from app.email_service import send_transactional_email
    from app.email_templates import build_account_invitation

    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    inv.token_hash = _hash_token(token)
    inv.expires_at = now + timedelta(days=TOKEN_EXPIRY_DAYS)
    db.session.commit()

    student = inv.student
    activate_url = abs_url("account.activate", "en", token=token)
    content = build_account_invitation(activate_url, student.name)
    log = send_transactional_email(
        student, "account_invitation", "en", content=content,
        related_type="account_invitation", related_id=inv.id, dedupe_key=f"account_invitation:{inv.id}",
    )
    if log is not None and log.status == "sent":
        inv.status = "sent"
        inv.sent_at = now
    else:
        inv.status = "failed"
        inv.failed_reason = (log.failure_reason if log else "Email delivery failed")[:300] if (log and log.failure_reason) else "Email delivery failed"
    db.session.commit()
    log_event(student.id, "account_invitation_sent" if inv.status == "sent" else "account_invitation_failed",
              actor="admin", actor_id=inv.invited_by_admin_id, entity=("account_invitation", inv.id))
    return inv


def process_queue(*, batch_id=None, limit=SEND_BATCH_LIMIT):
    """Sends up to `limit` still-queued invitations in THIS request. Returns a summary dict; whatever
    doesn't fit stays "queued" for the next call."""
    q = AccountInvitation.query.filter_by(status="queued")
    if batch_id is not None:
        q = q.filter_by(batch_id=batch_id)
    rows = q.order_by(AccountInvitation.created_at).limit(limit).all()
    sent, failed, rate_limited = 0, 0, 0
    for inv in rows:
        if not allow(RATE_LIMIT_KEY, RATE_LIMIT_PER_MINUTE, 60):
            rate_limited += 1
            continue
        _send(inv)
        if inv.status == "sent":
            sent += 1
        else:
            failed += 1
    remaining = AccountInvitation.query.filter_by(status="queued")
    if batch_id is not None:
        remaining = remaining.filter_by(batch_id=batch_id)
    return {"sent": sent, "failed": failed, "rate_limited": rate_limited, "remaining": remaining.count()}


def resend_invitation(student, *, batch_id=None, admin_id=None):
    """A single, deliberate admin action — always sent right away (not queued), since it's one email,
    not a bulk blast. Invalidates any still-outstanding invitation for this student first (same
    "a new request supersedes the old one" rule password reset already uses)."""
    now = datetime.utcnow()
    outstanding = AccountInvitation.query.filter_by(student_id=student.id).filter(AccountInvitation.status.in_(("queued", "sent"))).all()
    for old in outstanding:
        old.status = "failed"
        old.failed_reason = "Superseded by a resend"
    inv = AccountInvitation(student_id=student.id, batch_id=batch_id, status="queued", created_at=now, invited_by_admin_id=admin_id, resend_count=len(outstanding))
    db.session.add(inv)
    db.session.commit()
    if not allow(RATE_LIMIT_KEY, RATE_LIMIT_PER_MINUTE, 60):
        return inv  # stays queued — the rate limiter is protecting real SMTP capacity, even for a single resend
    return _send(inv)


def find_active_token(token):
    if not token:
        return None
    row = AccountInvitation.query.filter_by(token_hash=_hash_token(token)).first()
    return row if (row is not None and row.is_active) else None


def activate(inv, new_password):
    """The ONE place `Student.needs_activation` ever flips True -> False for an imported account — the
    exact transition `account_status()` uses to decide "Activated" and the ONLY place the
    `imported_account_activated` admin notification/email fires (2026-09-25). Fired here, not on
    login/password-reset/resend, so it can only ever happen once per account: a consumed token can never
    reach this function again (find_active_token() already refuses it), and resend_invitation() refuses
    an account that no longer needs_activation."""
    student = inv.student
    now = datetime.utcnow()
    student.password_hash = generate_password_hash(new_password)
    student.needs_activation = False
    if not student.email_verified_at:
        # Possessing the token that was emailed to this exact address IS proof of ownership — the same
        # reasoning password reset already relies on (only ever sent to an already-verified address);
        # here the invitation email itself is the first, and only, verification step this account needs.
        student.email_verified_at = now
    inv.status = "activated"
    inv.activated_at = now
    db.session.commit()
    log_event(student.id, "account_activated")

    from app import notifications as notif

    notif.notify(
        "imported_account_activated", title=f"Customer Account Activated — {student.name}",
        body=f"{student.name} ({student.email}) has activated their OG Multiservices account. Activated {now.strftime('%b %d, %Y %I:%M %p UTC')}.",
        entity_type="student", entity_id=student.id, customer_id=student.id,
        link_url=notif.safe_url("admin.customer_detail", student_id=student.id),
        dedupe_key=f"imported_account_activated:{student.id}",
    )
    return student


def account_status(student):
    """The single source of truth for "has this customer actually activated their account" — used by
    BOTH the Admin Customers list/filters AND (via `activate()` above) the notification that must fire
    exactly on this same transition, so the UI and the Notification Center can never disagree.

    Deliberately NOT inferred from last_login/recent activity — `is_active` (an admin enable/disable
    flag, unrelated to activation) and `needs_activation` (set only by the CSV import, cleared only by
    `activate()` above) are the actual stored account-activation state."""
    if not student.is_active:
        return "inactive"
    if student.needs_activation:
        return "needs_activation"
    return "activated"


def status_of(student):
    """The single most-recent invitation's status, or "not_invited" — used by the Admin list/detail UI."""
    if not student.needs_activation and student.import_batch_id is not None:
        return "activated"
    inv = AccountInvitation.query.filter_by(student_id=student.id).order_by(AccountInvitation.created_at.desc()).first()
    return inv.status if inv else "not_invited"
