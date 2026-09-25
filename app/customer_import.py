"""Wix customer CSV import — service layer for Admin -> Customers -> Import / Invitations.

Upload -> Map Fields -> Preview (paginated, mapping-aware) -> Validate Contacts (classifies every row,
writes NO customers) -> Review Results -> Import Customers (writes only the "ready" rows, idempotent) ->
later, separately, Send Invitations. All against the ONE existing `Student` identity (see
app/models/customer_import.py for why no second account system exists here).

Security: the upload is validated as real CSV text (never executed, never treated as a spreadsheet
formula) and size/row-capped before it is ever stored; every cell is sanitized so a value starting with
=, +, - or @ can never be interpreted as a formula if this data is later opened in a spreadsheet (CSV
injection). One bad row is quarantined as "error"/"invalid_email"/etc — it can never abort the batch.
"""
import csv
import io
import json
import re
import secrets
import unicodedata
from datetime import datetime

from werkzeug.security import generate_password_hash

from app.activity import log_event
from app.extensions import db
from app.models import ImportBatch, ImportRow, Student

MAX_CSV_BYTES = 5 * 1024 * 1024  # 5MB — comfortably covers a multi-thousand-row Wix contacts export
MAX_ROWS = 20000
PREVIEW_PAGE_SIZE = 20

# Customer field -> the Wix/CSV header names (already accent/case/punctuation-folded, see _norm_header)
# it's automatically matched against. Includes the REAL Spanish Wix export headers from the actual
# 260-contact/29-column file this was built against (Nombre, Apellido, Email 1, Teléfono 1, Dirección 1 -
# Calle/Ciudad/Estado-Región/Código postal/País) alongside the generic English variants this project's
# own forms/other exports might use. Only "Dirección 1" (primary) is auto-mapped — "Dirección 2", company,
# tags, subscriber status, activity, source, language and every other Wix metadata column is left
# unmapped ("ignore") by default, exactly as requested; nothing in the source file is altered.
FIELD_ALIASES = {
    "first_name": ("first name", "firstname", "first", "given name", "nombre"),
    "last_name": ("last name", "lastname", "last", "surname", "family name", "apellido"),
    "name": ("name", "full name", "contact name", "display name", "nickname"),
    "email": ("email", "email address", "login email", "contact email", "e-mail", "e-mail address", "email 1"),
    "phone": ("phone", "phone number", "mobile", "mobile phone", "contact phone", "cell", "cell phone", "telefono 1"),
    "address_street": ("address", "street", "street address", "direccion 1 calle", "address 1 street"),
    "address_city": ("city", "direccion 1 ciudad", "address 1 city"),
    "address_state": ("state", "state region", "state province", "direccion 1 estado region", "address 1 state region"),
    "address_zip": ("zip", "zip code", "postal code", "direccion 1 codigo postal", "address 1 zip code", "address 1 postal code"),
    "address_country": ("country", "direccion 1 pais", "address 1 country"),
}
TARGET_FIELDS = ["first_name", "last_name", "name", "email", "phone",
                  "address_street", "address_city", "address_state", "address_zip", "address_country"]
# The order + labels of the compact "Customer Field | Wix CSV Column" mapping table.
MAPPING_ROWS = [
    ("first_name", "First Name"), ("last_name", "Last Name"), ("email", "Email"), ("phone", "Phone"),
    ("address_street", "Street"), ("address_city", "City"), ("address_state", "State/Region"),
    ("address_zip", "ZIP"), ("address_country", "Country"),
]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FORMULA_PREFIXES = ("=", "+", "-", "@")


class ImportFileError(ValueError):
    pass


def _fold(s):
    """Strips accents (á->a, é->e, ñ->n, ...) so 'Dirección' and 'Direccion' compare equal."""
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")


def _norm_header(h):
    return re.sub(r"[^a-z0-9]+", " ", _fold(h).lower()).strip()


def guess_mapping(headers):
    """{target_field: csv_header} — best-effort, matched on the exact normalized header text (never a
    substring guess, so "Dirección 2 - Calle" never matches the "Dirección 1" alias and stays unmapped).
    Admin can override every one of these in Map Fields."""
    norm_to_header = {_norm_header(h): h for h in headers}
    mapping = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in norm_to_header:
                mapping[field] = norm_to_header[alias]
                break
    return mapping


def _sanitize_cell(value):
    v = (value or "").strip()
    if v and v[0] in FORMULA_PREFIXES:
        v = "'" + v  # neutralizes CSV/formula injection if this value is ever opened in a spreadsheet
    return v


def _sanitize_phone(value):
    """Phone gets ONLY whitespace trimming — never the formula-prefix guard `_sanitize_cell` applies,
    because a leading "+" is a legitimate, common international dialing prefix (e.g. "+1 830-360-6824"),
    not a spreadsheet formula risk worth corrupting real phone numbers over. Never reformatted/assumed
    to be a US number — preserved exactly as exported."""
    return (value or "").strip()


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


def create_batch(filename, raw_text, admin_id):
    total_rows = sum(1 for _ in csv.reader(io.StringIO(raw_text))) - 1
    batch = ImportBatch(source="wix", original_filename=filename[:255], raw_csv=raw_text, status="mapping",
                        total_rows=max(0, total_rows), uploaded_by_admin_id=admin_id, uploaded_at=datetime.utcnow())
    db.session.add(batch)
    db.session.commit()
    return batch


def headers_of(batch):
    return next(csv.reader(io.StringIO(batch.raw_csv)), [])


def _extract_row(raw_row, mapping):
    """mapping: {target_field: csv_header}. Returns the sanitized values for one CSV row, independent of
    whether this is for a preview page or a real validation pass — so both always agree exactly."""
    def cell(field):
        header = mapping.get(field)
        return _sanitize_cell(raw_row.get(header, "")) if header else ""

    first = cell("first_name")
    last = cell("last_name")
    full = cell("name")
    email_raw = (raw_row.get(mapping.get("email", ""), "") or "").strip()
    # Phone is preserved exactly as exported — Wix contains US, bare-digit and international formats
    # (some starting with "+"); reformatting risks corrupting a number we can't safely reinterpret, so
    # only whitespace trimming is applied, never digit reshaping, an assumed country code, or the
    # formula-prefix guard (a leading "+" is a real phone prefix here, not a spreadsheet-injection risk).
    phone_header = mapping.get("phone")
    phone = _sanitize_phone(raw_row.get(phone_header, "")) if phone_header else ""
    street = cell("address_street")
    city = cell("address_city")
    state = cell("address_state")
    zip_code = cell("address_zip")
    country = cell("address_country")
    # Never split/guess a name: "Kenneth Micheal White" with a blank Apellido stays exactly that as
    # first_name, with last_name blank — no attempt to infer which word is the surname.
    first_name = full or first or None
    return {
        "first_name": first_name, "last_name": (last or None), "email_raw": email_raw,
        "phone": (phone or None), "street": (street or None), "city": (city or None),
        "state": (state or None), "zip": (zip_code or None), "country": (country or None),
    }


def display_address(street, city, state, zip_code, country):
    parts = []
    if street:
        parts.append(street)
    if city:
        parts.append(city)
    state_zip = " ".join(p for p in (state, zip_code) if p)
    if state_zip:
        parts.append(state_zip)
    if country:
        parts.append(country)
    return ", ".join(parts)


def preview_page(batch, mapping, page=1, page_size=PREVIEW_PAGE_SIZE):
    """(rows, total_rows, total_pages) — `rows` is a list of the 5 display columns (Name, Last Name,
    Email, Phone, Address) for ONE page, computed with the CURRENT (possibly still unconfirmed) mapping.
    Never touches the database — pure read-only preview over the stored raw CSV text."""
    reader = csv.DictReader(io.StringIO(batch.raw_csv))
    total = batch.total_rows
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    rows = []
    for i, raw_row in enumerate(reader):
        if i < start:
            continue
        if i >= start + page_size:
            break
        v = _extract_row(raw_row, mapping)
        rows.append({
            "first_name": v["first_name"] or "—", "last_name": v["last_name"] or "—",
            "email": v["email_raw"] or "—", "phone": v["phone"] or "—",
            "address": display_address(v["street"], v["city"], v["state"], v["zip"], v["country"]) or "—",
        })
    return rows, total, total_pages, page


def _normalize_email(v):
    return (v or "").strip().lower()


def validate_batch(batch, mapping, admin_id):
    """Classifies every row of the FULL file (regardless of which preview page was showing) and writes
    ImportRow records — creates NO Student rows. Safe to re-run: clears any previous ImportRows for this
    batch first (a batch is only ever "validated" once in the normal flow, but re-validating after
    changing the mapping must never leave stale rows behind)."""
    ImportRow.query.filter_by(batch_id=batch.id).delete(synchronize_session=False)
    db.session.commit()

    seen_emails = {}  # normalized email -> first row_number seen in THIS file
    counts = {r: 0 for r in ("ready", "existing", "missing_email", "invalid_email", "duplicate_in_csv", "error")}
    reader = csv.DictReader(io.StringIO(batch.raw_csv))
    for i, raw_row in enumerate(reader, start=1):
        try:
            v = _extract_row(raw_row, mapping)
            email_norm = _normalize_email(v["email_raw"])
            err = None
            if not v["email_raw"]:
                result = "missing_email"
                err = "No email in this row"
            elif not EMAIL_RE.match(v["email_raw"]):
                result = "invalid_email"
                err = "Not a valid email address"
            elif email_norm in seen_emails:
                result = "duplicate_in_csv"
                err = f"Same email as row {seen_emails[email_norm]}"
            else:
                seen_emails[email_norm] = i
                existing = Student.query.filter_by(email=email_norm).first()
                result = "existing" if existing else "ready"
            db.session.add(ImportRow(
                batch_id=batch.id, row_number=i, first_name=v["first_name"], last_name=v["last_name"],
                email=v["email_raw"] or None, phone=v["phone"], address_street=v["street"], address_city=v["city"],
                address_state=v["state"], address_zip=v["zip"], address_country=v["country"],
                result=result, error_message=err,
            ))
            counts[result] += 1
        except Exception as exc:  # noqa: BLE001 — one malformed row must never abort the whole validation
            counts["error"] += 1
            db.session.add(ImportRow(batch_id=batch.id, row_number=i, result="error", error_message=str(exc)[:300]))

    batch.status = "validated"
    batch.validated_at = datetime.utcnow()
    batch.ready_count = counts["ready"]
    batch.existing_count = counts["existing"]
    batch.missing_email_count = counts["missing_email"]
    batch.invalid_email_count = counts["invalid_email"]
    batch.duplicate_count = counts["duplicate_in_csv"]
    batch.error_count = counts["error"]
    batch.column_mapping_json = json.dumps(mapping)
    db.session.commit()
    return counts


def import_batch(batch, admin_id):
    """Writes Student rows for every "ready" ImportRow not yet imported — idempotent: re-running this
    (double-click, retry after a partial failure) only ever processes rows still marked imported=False,
    and re-checks email-existence fresh in case something else created that account in the meantime."""
    rows = ImportRow.query.filter_by(batch_id=batch.id, result="ready", imported=False).all()
    imported = 0
    for row in rows:
        try:
            with db.session.begin_nested():
                email_norm = _normalize_email(row.email)
                existing = Student.query.filter_by(email=email_norm).first()
                if existing is not None:
                    # Someone else created this account between Validate and Import — never duplicate it.
                    row.result = "existing"
                    row.student_id = existing.id
                    continue
                name = " ".join(p for p in (row.first_name, row.last_name) if p) or email_norm
                student = Student(
                    email=email_norm, name=name[:200], phone=row.phone[:40] if row.phone else None,
                    password_hash=generate_password_hash(secrets.token_urlsafe(32)),
                    needs_activation=True, import_batch_id=batch.id,
                    address_street=row.address_street, address_city=row.address_city,
                    address_state=row.address_state, address_zip=row.address_zip, address_country=row.address_country,
                )
                db.session.add(student)
                db.session.flush()
                row.student_id = student.id
                row.imported = True
            if row.imported:
                imported += 1
                log_event(row.student_id, "account_created_via_import", actor="admin", actor_id=admin_id,
                          meta={"batch_id": batch.id, "source": "wix"})
        except Exception as exc:  # noqa: BLE001 — one row's failure must never abort the rest of the import
            row.result = "error"
            row.error_message = f"Import failed: {str(exc)[:250]}"
            db.session.add(row)

    batch.imported_count = ImportRow.query.filter_by(batch_id=batch.id, imported=True).count()
    batch.status = "imported"
    batch.imported_at = datetime.utcnow()
    db.session.commit()
    return imported
