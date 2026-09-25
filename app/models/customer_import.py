"""Wix customer migration (2026-09-25): a CSV import (Admin -> Customers -> Import / Invitations) that
reuses the existing `Student` identity unchanged — an imported customer is a REAL `Student` row from the
moment it's created, just one with `needs_activation=True` (an unusable random password_hash, never a
real one, and never emailed) until they complete the Activate My Account flow (app/account_invitations.py)
and set their own password. No second identity/auth system is introduced.

Two audit tables: `ImportBatch` (one CSV upload) and `ImportRow` (one CSV row's outcome, always created —
even for an invalid/duplicate/errored row — so Admin can see exactly what happened to every line). The
raw CSV text is kept on the batch (a small business's contact list; simplest correct approach — no
temp-file lifecycle to manage between the preview and import steps) so every later step always reprocesses
the exact bytes the admin previewed and mapped, never a re-upload.

Validate and Import are two SEPARATE, explicit actions (2026-09-25 refinement): "Validate Contacts"
(`ImportBatch.status` mapping -> validated) parses the WHOLE file, classifies every row, and writes
`ImportRow`s — but creates NO `Student` rows. "Import X Customers" (status validated -> imported) is the
only action that ever writes to the customer table, and only for rows whose `result == "ready"` that
haven't been imported yet (`ImportRow.imported`), so clicking it twice — or re-running it after a
partial failure — can never create a duplicate account (idempotent by construction).

`AccountInvitation` mirrors `PasswordResetToken`'s exact security shape (SHA-256 hash of a high-entropy
token, expiring, single-use) but adds the extra states a bulk migration needs: `queued` (created, no
token yet — nothing has been emailed) -> `sent` (token minted + emailed) -> `activated` | `failed`. A row
is deliberately created as `queued` WITHOUT a token, because a `token_hash` only makes sense once we are
about to email the plaintext token, never speculatively for something that might not be sent yet."""

from datetime import datetime

from app.extensions import db

#: Every ImportRow.result value. "ready" = passed validation, not yet written to the customer table.
#: "existing" = the email already belongs to a real Student (from before this import). "duplicate_in_csv"
#: = this exact email already appeared on an EARLIER row of the SAME file. Distinct from "existing" so
#: Admin can tell "already our customer" apart from "you typed/exported this person twice."
IMPORT_RESULTS = ("ready", "existing", "missing_email", "invalid_email", "duplicate_in_csv", "error")
INVITATION_STATUSES = ("queued", "sent", "activated", "failed")


class ImportBatch(db.Model):
    __tablename__ = "import_batches"

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(30), nullable=False, default="wix")
    original_filename = db.Column(db.String(255))
    raw_csv = db.Column(db.Text, nullable=False)
    column_mapping_json = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="mapping")  # mapping -> validated -> imported
    total_rows = db.Column(db.Integer, nullable=False, default=0)
    ready_count = db.Column(db.Integer, nullable=False, default=0)
    existing_count = db.Column(db.Integer, nullable=False, default=0)
    missing_email_count = db.Column(db.Integer, nullable=False, default=0)
    invalid_email_count = db.Column(db.Integer, nullable=False, default=0)
    duplicate_count = db.Column(db.Integer, nullable=False, default=0)
    error_count = db.Column(db.Integer, nullable=False, default=0)
    imported_count = db.Column(db.Integer, nullable=False, default=0)  # only set once "Import Customers" runs
    uploaded_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    validated_at = db.Column(db.DateTime)
    imported_at = db.Column(db.DateTime)

    rows = db.relationship("ImportRow", backref="batch", cascade="all, delete-orphan")


class ImportRow(db.Model):
    __tablename__ = "import_rows"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("import_batches.id"), nullable=False, index=True)
    row_number = db.Column(db.Integer, nullable=False)
    first_name = db.Column(db.String(200))
    last_name = db.Column(db.String(200))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(60))
    address_street = db.Column(db.String(255))
    address_city = db.Column(db.String(120))
    address_state = db.Column(db.String(60))
    address_zip = db.Column(db.String(20))
    address_country = db.Column(db.String(80))
    result = db.Column(db.String(20), nullable=False)
    error_message = db.Column(db.String(300))
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    imported = db.Column(db.Boolean, nullable=False, default=False, server_default="0")

    student = db.relationship("Student")

    @property
    def display_address(self):
        parts = []
        if self.address_street:
            parts.append(self.address_street)
        if self.address_city:
            parts.append(self.address_city)
        state_zip = " ".join(p for p in (self.address_state, self.address_zip) if p)
        if state_zip:
            parts.append(state_zip)
        if self.address_country:
            parts.append(self.address_country)
        return ", ".join(parts)


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
