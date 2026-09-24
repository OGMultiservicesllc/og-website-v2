"""Password reset (item 8) — did not exist anywhere in this project before. Secure, random, single-use,
expiring token; never reveals whether an email belongs to an account; only ever sent to an already-verified
account email (never to an address that hasn't been confirmed yet)."""

import hashlib
import secrets
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from app.activity import log_event
from app.email_render import abs_url
from app.email_service import send_transactional_email
from app.email_templates import build_password_reset
from app.extensions import db
from app.models import PasswordResetToken, Student
from app.ratelimit import allow

TOKEN_EXPIRY_MINUTES = 30


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def request_reset(email, lang, *, ip):
    """Always call this for any submitted email; the CALLER shows the identical generic response either
    way. Only actually sends when an account exists, is active, and has a verified email (item 8: "must
    only operate through verified account emails")."""
    if not allow(f"forgot_pw_ip:{ip}", 8, 3600):
        return
    email_norm = (email or "").strip().lower()
    if not email_norm or not allow(f"forgot_pw_email:{email_norm}", 4, 3600):
        return

    student = Student.query.filter_by(email=email_norm).first()
    if not student or not student.is_active or not student.is_email_verified:
        return

    now = datetime.utcnow()
    # A new request invalidates any still-outstanding token for this account, same principle as a new
    # verification code invalidating the previous one.
    PasswordResetToken.query.filter_by(student_id=student.id, used_at=None).update({"used_at": now}, synchronize_session=False)

    token = secrets.token_urlsafe(32)
    row = PasswordResetToken(student_id=student.id, token_hash=_hash_token(token), created_at=now, expires_at=now + timedelta(minutes=TOKEN_EXPIRY_MINUTES))
    db.session.add(row)
    db.session.commit()

    reset_url = abs_url("account.reset_password", lang, token=token)
    content = build_password_reset(lang, reset_url)
    send_transactional_email(student, "password_reset", lang, content=content)
    log_event(student.id, "password_reset_requested")


def find_active_token(token):
    if not token:
        return None
    row = PasswordResetToken.query.filter_by(token_hash=_hash_token(token)).first()
    return row if (row is not None and row.is_active) else None


def complete_reset(row, new_password):
    student = row.student
    now = datetime.utcnow()
    student.password_hash = generate_password_hash(new_password)
    row.used_at = now
    PasswordResetToken.query.filter_by(student_id=student.id, used_at=None).update({"used_at": now}, synchronize_session=False)
    db.session.commit()
    log_event(student.id, "password_reset_completed")
    return student
