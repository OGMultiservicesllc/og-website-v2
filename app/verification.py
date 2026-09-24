"""Mandatory 6-digit email verification (item 4/5). Covers TWO purposes with the same mechanics:
"verify" (the account's current email, at registration or resend) and "change_email" (a candidate NEW
address, used both by the pre-verification "Change Email" link and the post-verification Profile flow —
see item 7). The old/current email is never replaced until the new one is actually verified.

Conservative limits (item 5, documented here since the spec asked to choose and document them):
- code expires after 10 minutes
- max 5 attempts per code (a 6th wrong guess invalidates the code — request a new one)
- resend cooldown: 1 per 60 seconds
- resend cap: 5 per hour per account
- verify-attempt rate limit: 10 attempts per 15 minutes per account (defense in depth beyond the
  per-code attempt counter, since a customer could otherwise request many fresh codes to reset it)
"""

import secrets
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from app.activity import log_event
from app.email_render import mask_email
from app.email_service import send_transactional_email
from app.email_templates import build_email_changed, build_email_verification
from app.extensions import db
from app.models import EmailVerificationCode
from app.ratelimit import allow

CODE_EXPIRY_MINUTES = 10
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60
RESEND_MAX_PER_HOUR = 5
VERIFY_ATTEMPT_MAX = 10
VERIFY_ATTEMPT_WINDOW = 900


def _generate_code():
    return "".join(str(secrets.randbelow(10)) for _ in range(6))


def active_code(student, purpose):
    return (
        EmailVerificationCode.query.filter_by(student_id=student.id, purpose=purpose, consumed_at=None, invalidated_at=None)
        .order_by(EmailVerificationCode.id.desc())
        .first()
    )


def target_email(student, purpose):
    row = active_code(student, purpose)
    if row and row.pending_email:
        return row.pending_email
    return student.email


def masked_target_email(student, purpose):
    return mask_email(target_email(student, purpose))


def can_resend(student, purpose):
    """(allowed, reason_key). Checked BEFORE issuing a code, never after."""
    if not allow(f"verify_resend_cd:{student.id}:{purpose}", 1, RESEND_COOLDOWN_SECONDS):
        return False, "cooldown"
    if not allow(f"verify_resend_hr:{student.id}:{purpose}", RESEND_MAX_PER_HOUR, 3600):
        return False, "too_many"
    return True, None


def issue_code(student, purpose, *, lang, pending_email=None):
    """Invalidates any existing active code for this (student, purpose) — issuing a new code always
    invalidates the previous one (item 5) — then creates and sends a fresh one."""
    now = datetime.utcnow()
    EmailVerificationCode.query.filter_by(student_id=student.id, purpose=purpose, consumed_at=None, invalidated_at=None).update(
        {"invalidated_at": now}, synchronize_session=False
    )
    code = _generate_code()
    row = EmailVerificationCode(
        student_id=student.id, purpose=purpose, pending_email=pending_email,
        code_hash=generate_password_hash(code), created_at=now, expires_at=now + timedelta(minutes=CODE_EXPIRY_MINUTES),
    )
    db.session.add(row)
    db.session.commit()

    to_email = pending_email or student.email
    content = build_email_verification(lang, code, to_email)
    send_transactional_email(student, "email_verification", lang, content=content, recipient_email=to_email, recipient_name=student.name)
    return row


def verify_code(student, purpose, submitted_code):
    """(ok, error_key). error_key in: rate_limited | expired | too_many_attempts | wrong_code | None."""
    if not allow(f"verify_attempt:{student.id}:{purpose}", VERIFY_ATTEMPT_MAX, VERIFY_ATTEMPT_WINDOW):
        return False, "rate_limited"

    row = active_code(student, purpose)
    if row is None or row.is_expired:
        return False, "expired"
    if row.attempts >= MAX_ATTEMPTS:
        row.invalidated_at = datetime.utcnow()
        db.session.commit()
        return False, "too_many_attempts"

    row.attempts += 1
    db.session.commit()

    submitted = (submitted_code or "").strip()
    if not submitted.isdigit() or len(submitted) != 6 or not check_password_hash(row.code_hash, submitted):
        return False, "wrong_code"

    now = datetime.utcnow()
    row.consumed_at = now
    if purpose == "verify":
        student.email_verified_at = now
        db.session.commit()
        log_event(student.id, "email_verified")
    elif purpose == "change_email":
        old_email = student.email
        new_email = row.pending_email
        student.email = new_email
        student.email_verified_at = now  # still verified — just at the new, now-confirmed address
        db.session.commit()
        log_event(student.id, "email_changed", meta={"new_email": mask_email(new_email)})
        lang = student.preferred_language or "en"
        content = build_email_changed(lang, new_email)
        send_transactional_email(student, "email_changed", lang, content=content, recipient_email=old_email, recipient_name=student.name)
    return True, None
