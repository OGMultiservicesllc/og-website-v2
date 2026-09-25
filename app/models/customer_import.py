"""Wix customer migration (2026-09-25): a CSV import (Admin -> Customers -> Import / Invitations) that
reuses the existing `Student` identity unchanged — an imported customer is a REAL `Student` row from the
moment it's created, just one with `needs_activation=True` (an unusable random password_hash, never a
real one, and never emailed) until they complete the Activate My Account flow (app/account_invitations.py)
and set their own password. No second identity/auth system is introduced.

Two audit tables: `ImportBatch` (one CSV upload) and `ImportRow` (one CSV row's outcome, always created —
even for an invalid/duplicate/errored row — so Admin can see exactly what happened to every line). The
raw CSV text is kept on the batch (a small business's contact list; simplest correct approach — no
temp-file lifecycle to manage between the preview and import steps) so "Validate & Import" always reprocesses
the exact bytes the admin previewed and mapped, never a re-upload.

`AccountInvitation` mirrors `PasswordResetToken`'s exact security shape (SHA-256 hash of a high-entropy
token, expiring, single-use) but adds the extra states a bulk migration needs: `queued` (created, no
token yet — nothing has been emailed) -> `sent` (token minted + emailed) -> `activated` | `failed`. A row
is deliberately created as `queued` WITHOUT a token, because a `token_hash` only makes sense once we are
about to email the plaintext token, never speculatively for something that might not be sent yet."""

from datetime import datetime

from app.extensions import db

IMPORT_RESULTS = ("imported", "existing", "invalid", "missing_email", "error")
INVITATION_STATUSES = ("queued", "sent", "activated", "failed")


class ImportBatch(db.Model):
    __tablename__ = "import_batches"

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(30), nullable=False, default="wix")
    original_filename = db.Column(db.String(255))
    raw_csv = db.Column(db.Text, nullable=False)
    column_mapping_json = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="mapping")  # mapping -> imported
    total_rows = db.Column(db.Integer, nullable=False, default=0)
    imported_count = db.Column(db.Integer, nullable=False, default=0)
    existing_count = db.Column(db.Integer, nullable=False, default=0)
    invalid_count = db.Column(db.Integer, nullable=False, default=0)
    missing_email_count = db.Column(db.Integer, nullable=False, default=0)
    error_count = db.Column(db.Integer, nullable=False, default=0)
    uploaded_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    imported_at = db.Column(db.DateTime)

    rows = db.relationship("ImportRow", backref="batch", cascade="all, delete-orphan")


class ImportRow(db.Model):
    __tablename__ = "import_rows"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("import_batches.id"), nullable=False, index=True)
    row_number = db.Column(db.Integer, nullable=False)
    first_name = db.Column(db.String(120))
    last_name = db.Column(db.String(120))
    full_name = db.Column(db.String(200))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(60))
    result = db.Column(db.String(20), nullable=False)
    error_message = db.Column(db.String(300))
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))

    student = db.relationship("Student")


class AccountInvitation(db.Model):
    __tablename__ = "account_invitations"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("import_batches.id"))
    token_hash = db.Column(db.String(64), index=True)  # null while status="queued" — no token minted yet
    status = db.Column(db.String(20), nullable=False, default="queued", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)
    activated_at = db.Column(db.DateTime)
    failed_reason = db.Column(db.String(300))
    invited_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"))
    resend_count = db.Column(db.Integer, nullable=False, default=0)

    student = db.relationship("Student")
    batch = db.relationship("ImportBatch")

    @property
    def is_active(self):
        return self.status in ("queued", "sent") and (self.expires_at is None or self.expires_at > datetime.utcnow())
