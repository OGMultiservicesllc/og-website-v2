"""Transactional Email system (2026-09-22): 6-digit email verification, password reset, and the
delivery ledger. Reuses the customer identity (`Student`) and activity log (`app.activity`) already in
this project — these are the only new tables the feature needs.

Security note: `EmailVerificationCode.code_hash` and `PasswordResetToken.token_hash` never store the
plaintext code/token — see `app/verification.py` and `app/password_reset.py` for the hashing scheme
(the 6-digit code uses the same slow `werkzeug.security` hash as passwords, since it is low-entropy;
the reset token is high-entropy so a fast SHA-256 lookup hash is appropriate, same reasoning as any
opaque bearer token)."""

from datetime import datetime

from app.extensions import db

EMAIL_VERIFICATION_PURPOSES = ("verify", "change_email")


class EmailVerificationCode(db.Model):
    __tablename__ = "email_verification_codes"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", name="fk_email_verification_codes_student"), nullable=False, index=True)
    purpose = db.Column(db.String(20), nullable=False)  # "verify" (registration / current email) | "change_email" (a candidate new address)
    pending_email = db.Column(db.String(255))  # only set for purpose="change_email" — the NOT-YET-verified candidate address
    code_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    consumed_at = db.Column(db.DateTime)  # set once the correct code is entered — a used code can never be reused
    invalidated_at = db.Column(db.DateTime)  # set when a newer code for the same (student, purpose) supersedes this one

    student = db.relationship("Student")

    @property
    def is_active(self):
        return self.consumed_at is None and self.invalidated_at is None and self.expires_at > datetime.utcnow()

    @property
    def is_expired(self):
        return self.expires_at <= datetime.utcnow()


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", name="fk_password_reset_tokens_student"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, index=True)  # SHA-256 hex digest of a high-entropy random token
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)

    student = db.relationship("Student")

    @property
    def is_active(self):
        return self.used_at is None and self.expires_at > datetime.utcnow()


EMAIL_LOG_STATUSES = ("pending", "sending", "sent", "failed")


class EmailLog(db.Model):
    """One row per transactional email attempt. `ref_json` stores only SAFE, non-sensitive reference ids
    (e.g. {"payment_id": 5}) — never rendered content, never PII beyond the recipient address itself — so
    a retry can re-render the email from current data rather than replaying a stale snapshot."""

    __tablename__ = "email_logs"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", name="fk_email_logs_student"), index=True)
    recipient_email = db.Column(db.String(255), nullable=False)
    recipient_name = db.Column(db.String(200))
    template_key = db.Column(db.String(60), nullable=False, index=True)
    language = db.Column(db.String(2), nullable=False, default="en")
    subject = db.Column(db.String(255), nullable=False)
    related_type = db.Column(db.String(40))  # e.g. "payment", "case", "customer_file", "enrollment", "certificate"
    related_id = db.Column(db.Integer)
    ref_json = db.Column(db.Text)  # safe reference ids used to re-render on retry, e.g. '{"payment_id": 5}'
    status = db.Column(db.String(20), nullable=False, default="pending", server_default="pending", index=True)
    attempt_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    last_attempt_at = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)
    failed_at = db.Column(db.DateTime)
    failure_reason = db.Column(db.String(500))
    dedupe_key = db.Column(db.String(160), index=True)  # prevents a duplicate send for the same business event
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("Student")
