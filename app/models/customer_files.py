"""Files from OG: the INVERSE direction of the Document Vault (customer -> OG). This is OG delivering a file TO a
customer (a certified translation, an affidavit, a receipt) — separate from `CaseDocument`/`DocumentRequirement`,
which are what the customer sends OG. Same secure-storage convention (`app.uploads.save_course_media`, a random
server filename, never the original filename on disk) and the same private, ownership-checked download pattern
used everywhere else in this app.

A file is a DRAFT until an admin explicitly publishes it (`published_at` set) — never visible to the customer,
and never counted in "Files from OG", until then. `title` doubles as the customer-facing display name (e.g.
"2025 Federal Tax Return", "Certified Translation — Driver License") — the physical filename never needs to
match it. `category`/`tax_year`/`related_service`/`person_id` are presentation metadata for the dedicated
Files from OG page (app/customer_files.py); they never change where or how the file is physically stored."""

from datetime import datetime

from app.extensions import db

# Presentation categories only (item A4) — never a separate storage system.
FILE_CATEGORIES = [
    ("taxes", ("Taxes", "Impuestos")),
    ("immigration", ("Immigration", "Inmigración")),
    ("translations", ("Translations", "Traducciones")),
    ("nj_driver_license", ("NJ Driver License", "Licencia de Conducir de NJ")),
    ("other", ("Other Documents", "Otros Documentos")),
]
FILE_CATEGORY_KEYS = [k for k, _ in FILE_CATEGORIES]


def category_label(category, lang):
    for key, (en, es) in FILE_CATEGORIES:
        if key == category:
            return es if lang == "es" else en
    return category or ""


class CustomerFile(db.Model):
    __tablename__ = "customer_files"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"))  # optional: which service/case this belongs to
    person_id = db.Column(db.Integer, db.ForeignKey("persons.id", name="fk_customer_files_person"))  # optional: which family member this is about
    category = db.Column(db.String(30), nullable=False, default="other", server_default="other")
    related_service = db.Column(db.String(120))  # free-text customer-facing label, e.g. "NJ Driver License"
    tax_year = db.Column(db.Integer)  # only meaningful for category == "taxes"
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    stored_filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(80))
    size_bytes = db.Column(db.Integer, default=0)
    uploaded_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"))
    released_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id", name="fk_customer_files_released_by"))  # who clicked Publish (may differ from who uploaded)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    published_at = db.Column(db.DateTime)  # null = draft/"Internal Only", not visible to the customer
    downloaded_at = db.Column(db.DateTime)  # last time the customer opened it (staff visibility only)

    customer = db.relationship("Student")
    case = db.relationship("Case")
    person = db.relationship("Person")
    uploaded_by = db.relationship("AdminUser", foreign_keys=[uploaded_by_admin_id])
    released_by = db.relationship("AdminUser", foreign_keys=[released_by_admin_id])

    @property
    def is_published(self):
        return self.published_at is not None
