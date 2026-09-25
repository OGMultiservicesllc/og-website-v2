"""Wix customer CSV import — service layer for Admin -> Customers -> Import / Invitations.
Upload -> Preview -> Map Columns -> Validate -> Import -> Review Results, all against the ONE existing
`Student` identity (see app/models/customer_import.py for why no second account system exists here).

Security: the upload is validated as real CSV text (never executed, never treated as a spreadsheet
formula) and size/row-capped before it is ever stored; every cell is sanitized so a value starting with
=, +, - or @ can never be interpreted as a formula if this data is later opened in a spreadsheet (CSV
injection). One bad row is quarantined as "error"/"invalid" — it can never abort the rest of the batch.
"""
import csv
import io
import json
import re
import secrets
from datetime import datetime

from werkzeug.security import generate_password_hash

from app.activity import log_event
from app.extensions import db
from app.models import ImportBatch, ImportRow, Student

MAX_CSV_BYTES = 5 * 1024 * 1024  # 5MB — comfortably covers a multi-thousand-row Wix contacts export
MAX_ROWS = 20000
PREVIEW_ROWS = 8

FIELD_ALIASES = {
    "first_name": ("first name", "firstname", "first", "given name"),
    "last_name": ("last name", "lastname", "last", "surname", "family name"),
    "name": ("name", "full name", "contact name", "display name", "nickname"),
    "email": ("email", "email address", "login email", "contact email", "e-mail", "e-mail address"),
    "phone": ("phone", "phone number", "mobile", "mobile phone", "contact phone", "cell", "cell phone"),
}
TARGET_FIELDS = ["first_name", "last_name", "name", "email", "phone", "ignore"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FORMULA_PREFIXES = ("=", "+", "-", "@")


class ImportFileError(ValueError):
    pass


def _norm_header(h):
    return re.sub(r"[^a-z0-9]+", " ", (h or "").strip().lower()).strip()


def guess_mapping(headers):
    """{csv_header: target_field}, best-effort — Admin can override every one of these in Map Columns."""
    mapping = {}
    for h in headers:
        nh = _norm_header(h)
        matched = "ignore"
        for field, aliases in FIELD_ALIASES.items():
            if nh == field.replace("_", " ") or nh in aliases:
                matched = field
                break
        mapping[h] = matched
    return mapping


def _sanitize_cell(value):
    v = (value or "").strip()
    if v and v[0] in FORMULA_PREFIXES:
        v = "'" + v  # neutralizes CSV/formula injection if this value is ever opened in a spreadsheet
    return v


def read_upload(file_storage):
    """Validates a Werkzeug FileStorage as a real, small, CSV-shaped text file. Never trusts the
    extension alone — content is parsed as CSV and must yield a header row and at least one data row."""
    filename = (file_storage.filename or "").strip()
    if not filename.lower().endswith(".csv"):
        raise ImportFileError("Please upload a .csv file (export your Wix contacts/members list as CSV).")
    raw = file_storage.read()
    if len(raw) > MAX_CSV_BYTES:
        raise ImportFileError(f"That file is too large ({len(raw) // 1024} KB). The limit is {MAX_CSV_BYTES // 1024 // 1024} MB.")
    if not raw:
        raise ImportFileError("That file is empty.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise ImportFileError("Could not read this file as text — is it really a CSV export?") from exc
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except csv.Error as exc:
        raise ImportFileError(f"Could not parse this as CSV: {exc}") from exc
    if len(rows) < 2:
        raise ImportFileError("This CSV needs a header row plus at least one data row.")
    if len(rows) - 1 > MAX_ROWS:
        raise ImportFileError(f"That's {len(rows) - 1:,} rows — the limit per import is {MAX_ROWS:,}. Split the file and import in batches.")
    return filename, text, rows[0]


def preview_rows(raw_text, limit=PREVIEW_ROWS):
    reader = csv.reader(io.StringIO(raw_text))
    rows = list(reader)
    return rows[1:1 + limit] if rows else []


def create_batch(filename, raw_text, headers, admin_id):
    total_rows = sum(1 for _ in csv.reader(io.StringIO(raw_text))) - 1
    batch = ImportBatch(source="wix", original_filename=filename[:255], raw_csv=raw_text, status="mapping",
                        total_rows=max(0, total_rows), uploaded_by_admin_id=admin_id, uploaded_at=datetime.utcnow())
    db.session.add(batch)
    db.session.commit()
    return batch


def _normalize_email(v):
    return (v or "").strip().lower()


def run_import(batch, mapping, admin_id):
    """mapping: {csv_header: target_field}. Idempotent-safe to call only once per batch — the caller
    (the route) enforces batch.status == "mapping" before calling this. Every row gets an ImportRow,
    whatever its outcome, so Admin can see exactly what happened to every line of the file."""
    reversed_map = {v: k for k, v in mapping.items() if v and v != "ignore"}
    counts = {r: 0 for r in ("imported", "existing", "invalid", "missing_email", "error")}
    reader = csv.DictReader(io.StringIO(batch.raw_csv))
    for i, raw_row in enumerate(reader, start=1):
        # A SAVEPOINT per row (not a rollback of the whole session): one malformed row's failure can
        # never discard every OTHER row already staged in this same import — only its own changes.
        try:
            with db.session.begin_nested():
                first = _sanitize_cell(raw_row.get(reversed_map.get("first_name", ""), ""))
                last = _sanitize_cell(raw_row.get(reversed_map.get("last_name", ""), ""))
                full = _sanitize_cell(raw_row.get(reversed_map.get("name", ""), ""))
                email_raw = (raw_row.get(reversed_map.get("email", ""), "") or "").strip()
                phone = _sanitize_cell(raw_row.get(reversed_map.get("phone", ""), ""))
                name = full or " ".join(p for p in (first, last) if p) or None
                email_norm = _normalize_email(email_raw)

                student_id, err = None, None
                if not email_raw:
                    result = "missing_email"
                    err = "No email in this row"
                elif not EMAIL_RE.match(email_raw):
                    result = "invalid"
                    err = "Not a valid email address"
                elif not name:
                    result = "invalid"
                    err = "No name in this row"
                else:
                    existing = Student.query.filter_by(email=email_norm).first()
                    if existing:
                        result = "existing"
                        student_id = existing.id
                    else:
                        student = Student(
                            email=email_norm, name=name[:200], phone=(phone or None)[:40] if phone else None,
                            password_hash=generate_password_hash(secrets.token_urlsafe(32)),
                            needs_activation=True, import_batch_id=batch.id,
                        )
                        db.session.add(student)
                        db.session.flush()
                        result, student_id = "imported", student.id
                counts[result] += 1
                db.session.add(ImportRow(
                    batch_id=batch.id, row_number=i, first_name=first or None, last_name=last or None,
                    full_name=full or None, email=email_raw or None, phone=phone or None,
                    result=result, error_message=err, student_id=student_id,
                ))
            if result == "imported":
                log_event(student_id, "account_created_via_import", actor="admin", actor_id=admin_id,
                          meta={"batch_id": batch.id, "source": "wix"})
        except Exception as exc:  # noqa: BLE001 — one malformed row must never abort the whole import
            counts["error"] += 1
            db.session.add(ImportRow(batch_id=batch.id, row_number=i, result="error", error_message=str(exc)[:300]))

    batch.status = "imported"
    batch.imported_at = datetime.utcnow()
    batch.imported_count = counts["imported"]
    batch.existing_count = counts["existing"]
    batch.invalid_count = counts["invalid"]
    batch.missing_email_count = counts["missing_email"]
    batch.error_count = counts["error"]
    batch.column_mapping_json = json.dumps(mapping)
    db.session.commit()
    return counts
