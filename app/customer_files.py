"""Files from OG: service layer for `CustomerFile` (see app/models/customer_files.py for the "why a separate
model" reasoning). Every lookup goes THROUGH the signed-in customer's own id — never trusts an id from a URL —
the same discipline as `case_svc.owned_case` / `vault.owned_document` elsewhere in this app."""

import os
from datetime import datetime

from app.extensions import db
from app.models import CustomerFile, FILE_CATEGORY_KEYS
from app.uploads import course_media_full_path, save_course_media

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp", "doc", "docx"}
MAX_UPLOAD_MB = 15


def validate_upload(file_storage, lang="en"):
    from app.blueprints.public.routes import _matches_extension, _probe_upload

    name = (file_storage.filename or "").strip() if file_storage else ""
    if not name:
        return "Choose a file to upload." if lang == "en" else "Elige un archivo para subir."
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXTENSIONS:
        return f"Unsupported file type: .{ext}" if lang == "en" else f"Tipo de archivo no admitido: .{ext}"
    size, head = _probe_upload(file_storage)
    if size <= 0:
        return "The file is empty." if lang == "en" else "El archivo está vacío."
    if size > MAX_UPLOAD_MB * 1024 * 1024:
        return f"Each file must be {MAX_UPLOAD_MB} MB or smaller." if lang == "en" else f"Cada archivo debe pesar {MAX_UPLOAD_MB} MB o menos."
    if ext in ("pdf", "jpg", "jpeg", "png", "webp") and not _matches_extension(ext, head):
        return f"“{name}” doesn't look like a real .{ext} file." if lang == "en" else f"“{name}” no parece un archivo .{ext} válido."
    return None


def create(customer, file_storage, *, title, description=None, case=None, person=None, category="other",
           related_service=None, tax_year=None, admin_id=None, publish=False):
    from app.blueprints.public.routes import _guess_mime, _probe_upload

    _size, head = _probe_upload(file_storage)
    stored = save_course_media(file_storage, "document")
    path = course_media_full_path(stored)
    safe_name = os.path.basename(file_storage.filename or "file")[:200]
    now = datetime.utcnow()
    f = CustomerFile(customer_id=customer.id, case_id=case.id if case else None, person_id=person.id if person else None,
                     category=category if category in FILE_CATEGORY_KEYS else "other",
                     related_service=(related_service or "").strip()[:120] or None, tax_year=tax_year,
                     title=(title or safe_name)[:200], description=(description or "").strip()[:1000] or None,
                     stored_filename=stored, original_filename=safe_name, mime_type=_guess_mime(safe_name, head),
                     size_bytes=os.path.getsize(path) if os.path.isfile(path) else 0, uploaded_by_admin_id=admin_id,
                     released_by_admin_id=admin_id if publish else None, published_at=now if publish else None)
    db.session.add(f)
    db.session.commit()
    if publish:
        _notify_published(f)
    return f


def _notify_published(f):
    try:
        from app.email_service import send_transactional_email

        student = f.customer
        send_transactional_email(student, "file_available", student.preferred_language or "en",
                                 ref={"file_id": f.id}, related_type="customer_file", related_id=f.id,
                                 dedupe_key=f"file_available:{f.id}")
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("og_email").exception("[customer_files] file_available email failed to queue")


def publish(f, admin_id=None):
    if f.published_at is None:
        f.published_at = datetime.utcnow()
        f.released_by_admin_id = admin_id
        db.session.commit()
        _notify_published(f)
    return f


def unpublish(f):
    f.published_at = None
    db.session.commit()
    return f


def for_customer(customer, *, published_only=True):
    q = CustomerFile.query.filter_by(customer_id=customer.id)
    if published_only:
        q = q.filter(CustomerFile.published_at.isnot(None))
    return q.order_by(CustomerFile.published_at.desc().nullslast(), CustomerFile.created_at.desc()).all()


def counts_by_category(customer):
    """{category: count} across the customer's own PUBLISHED files — used for the filter tabs and the Home summary."""
    out = {k: 0 for k in FILE_CATEGORY_KEYS}
    for f in for_customer(customer):
        out[f.category if f.category in FILE_CATEGORY_KEYS else "other"] += 1
    return out


def search(customer, *, category=None, q=None):
    """Item A13: category + free-text search over the customer's own published files. `q` matches display
    name, category label, related service, tax year and description — never the physical filename."""
    rows = for_customer(customer)
    if category and category != "all":
        rows = [f for f in rows if f.category == category]
    q = (q or "").strip().lower()
    if q:
        from app.models import category_label

        def hit(f):
            hay = " ".join(str(x) for x in (f.title, f.description, f.related_service, f.tax_year,
                                             category_label(f.category, "en"), category_label(f.category, "es"),
                                             f.person.full_name if f.person else "") if x)
            return q in hay.lower()

        rows = [f for f in rows if hit(f)]
    return rows


def owned(customer, file_id):
    """The customer's own PUBLISHED file, or None — never another customer's, never a draft."""
    return CustomerFile.query.filter_by(id=file_id, customer_id=customer.id).filter(CustomerFile.published_at.isnot(None)).first()


def mark_downloaded(f):
    f.downloaded_at = datetime.utcnow()
    db.session.commit()
