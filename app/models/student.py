from datetime import datetime

from app.extensions import db


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    phone = db.Column(db.String(40))
    preferred_language = db.Column(db.String(2))
    last_login_at = db.Column(db.DateTime)
    photo_filename = db.Column(db.String(255))  # stored the same way as course/case media (app/uploads.py); never a raw path in the UI

    # Mandatory email verification (Transactional Email system, 2026-09-22). Null = unverified — same
    # "presence means done" idiom as CustomerFile.published_at. See app/verification.py for the 6-digit
    # code flow and app/student_auth.py for where this is enforced (student_required).
    email_verified_at = db.Column(db.DateTime)

    # Wix customer migration (2026-09-25): True only for an account CREATED by the CSV import with a
    # random, unusable placeholder password (never emailed) — cleared the moment the customer completes
    # Activate My Account and sets a real password. False for every normal self-registered account,
    # by default, so this never affects the existing registration/login flow.
    needs_activation = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    import_batch_id = db.Column(db.Integer, db.ForeignKey("import_batches.id"))

    @property
    def is_email_verified(self):
        return self.email_verified_at is not None

    @property
    def initials(self):
        parts = [p for p in (self.name or "").split() if p]
        letters = (parts[0][0] if parts else "") + (parts[-1][0] if len(parts) > 1 else "")
        return letters.upper() or "?"

    enrollments = db.relationship(
        "Enrollment", backref="student", cascade="all, delete-orphan"
    )


#: Structured access-source values (item B2) — a Wix student already paid OG, so they are
#: "migrated_wix", never "admin_complimentary"/free. `paid_new_site` is the default for the
#: existing self-service checkout flow; everything else is an explicit Admin choice.
ACCESS_SOURCES = [
    ("paid_new_site", ("Paid on New Website", "Pagado en el nuevo sitio web")),
    ("migrated_wix", ("Migrated from Wix", "Migrado desde Wix")),
    ("admin_complimentary", ("Admin Complimentary", "Cortesía del administrador")),
    ("promotion", ("Promotion", "Promoción")),
    ("staff_test", ("Staff/Test", "Personal/Prueba")),
    ("other", ("Other", "Otro")),
]


def access_source_label(source, lang):
    for key, (en, es) in ACCESS_SOURCES:
        if key == source:
            return es if lang == "es" else en
    return source or ""


class Enrollment(db.Model):
    __tablename__ = "enrollments"
    __table_args__ = (db.UniqueConstraint("student_id", "course_id", name="uq_student_course"),)

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)  # null = unlimited access

    # Item B1-B10: who granted access, how, and why — the SAME row is reused for renew/extend
    # (the unique constraint above already prevents a second enrollment row for one student+course).
    access_source = db.Column(db.String(30), nullable=False, default="paid_new_site", server_default="paid_new_site")
    granted_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id", name="fk_enrollments_granted_by"))  # null = the student's own checkout
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)
    migration_reference = db.Column(db.String(120))  # e.g. a Wix order id, optional
    internal_note = db.Column(db.Text)  # never shown to the customer
    revoked_at = db.Column(db.DateTime)  # null = active; set by Admin "Revoke Access" (B9) — never a row delete
    revoked_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id", name="fk_enrollments_revoked_by"))

    course = db.relationship("Course")
    granted_by = db.relationship("AdminUser", foreign_keys=[granted_by_admin_id])
    revoked_by = db.relationship("AdminUser", foreign_keys=[revoked_by_admin_id])

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at < datetime.utcnow())

    @property
    def is_revoked(self):
        return self.revoked_at is not None

    @property
    def is_active(self):
        return not self.is_expired and not self.is_revoked
