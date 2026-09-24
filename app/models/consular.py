"""Consular processing (Department of State / CEAC) layer on top of the case architecture. Additive: four new tables, nothing existing changes.

  Ds260Source          a versioned SOURCE SNAPSHOT of the DS-260 question schema (agency, system, official name, reference, verification date,
                       schema hash). Each DS-260 application records the snapshot it was created under, so a later change of the official form
                       never silently rewrites a historical application. DS-260 is an ONLINE Department of State form: it has no USCIS-style edition.
  ConsularCaseData     matter data of a Consular Processing case (NVC case number, invoice ID, priority date, post...). Sensitive case credentials:
                       masked everywhere they are shown, never in a URL, log or public metadata. CEAC passwords are never stored.
  Ds260Application     one row per DS-260 application (one visa applicant): source snapshot, principal/derivative role, the CEAC status recorded by
                       staff (separate from the OG status) and the "Ready for CEAC" mark.
  Ds260CeacOverride    a staff-reviewed CEAC-ready value that replaces the automatic one (for example an English translation of a free-text answer).
"""

from datetime import datetime

from app.extensions import db

CEAC_STATUSES = (
    ("not_started", "Not started"),
    ("incomplete", "Incomplete"),
    ("submitted", "Submitted / completed in CEAC"),
    ("reopened", "Re-opened"),
)
CEAC_STATUS_LABELS = dict(CEAC_STATUSES)


class Ds260Source(db.Model):
    __tablename__ = "ds260_sources"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(60), unique=True, nullable=False)
    agency = db.Column(db.String(80), nullable=False, default="U.S. Department of State")
    system = db.Column(db.String(40), nullable=False, default="CEAC")
    form_name = db.Column(db.String(20), nullable=False, default="DS-260")
    official_name = db.Column(db.String(200), nullable=False, default="Immigrant Visa and Alien Registration Application")
    # Text, not a bounded VARCHAR: a bibliographic-style citation whose length
    # varies with the source description -- confirmed over 200 chars during
    # the PostgreSQL VARCHAR(200) audit, 2026-09-23 (see migration 363aeea03c7f).
    source_label = db.Column(db.Text)  # e.g. "Bureau of Consular Affairs DS-260 IV Application SAMPLE, October 2019 (111 pp)"
    reference = db.Column(db.Text)  # official URLs / Federal Register citations, one per line
    sample_date = db.Column(db.String(20))
    verified_at = db.Column(db.Date)
    schema_hash = db.Column(db.String(64))
    registry_json = db.Column(db.Text)  # {canonical question id: {section, label, type}} frozen with the snapshot, so snapshot A can be diffed against B
    notes = db.Column(db.Text)
    is_current = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ConsularCaseData(db.Model):
    __tablename__ = "consular_case_data"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, unique=True)
    nvc_case_number = db.Column(db.String(40))
    invoice_id = db.Column(db.String(40))
    petition_type = db.Column(db.String(60))
    priority_date = db.Column(db.Date)
    post = db.Column(db.String(120))
    country = db.Column(db.String(80))
    visa_class = db.Column(db.String(20))
    nvc_status = db.Column(db.String(120))
    dq_date = db.Column(db.Date)
    interview_date = db.Column(db.Date)
    petitioner_person_id = db.Column(db.Integer, db.ForeignKey("persons.id"))
    underlying_submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = db.relationship("Case", backref=db.backref("consular_data", uselist=False, cascade="all, delete-orphan"))
    petitioner_person = db.relationship("Person", foreign_keys=[petitioner_person_id])
    underlying_submission = db.relationship("FormSubmission", foreign_keys=[underlying_submission_id])


class Ds260Application(db.Model):
    __tablename__ = "ds260_applications"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"), nullable=False, unique=True)
    source_id = db.Column(db.Integer, db.ForeignKey("ds260_sources.id"))
    applicant_role = db.Column(db.String(12), nullable=False, default="principal", server_default="principal")  # principal | derivative
    ceac_status = db.Column(db.String(20), nullable=False, default="not_started", server_default="not_started")
    ceac_status_at = db.Column(db.DateTime)
    ceac_status_by = db.Column(db.String(120))
    ceac_note = db.Column(db.Text)  # internal, never shown to the customer
    ready_for_ceac_at = db.Column(db.DateTime)
    ready_for_ceac_by = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    submission = db.relationship("FormSubmission", backref=db.backref("ds260", uselist=False, cascade="all, delete-orphan"))
    source = db.relationship("Ds260Source")


class Ds260CeacOverride(db.Model):
    __tablename__ = "ds260_ceac_overrides"
    __table_args__ = (db.UniqueConstraint("submission_id", "field_key", name="uq_ds260_override"),)

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"), nullable=False, index=True)
    field_key = db.Column(db.String(80), nullable=False)
    value_text = db.Column(db.Text)
    reviewed_by = db.Column(db.String(120))
    reviewed_at = db.Column(db.DateTime, default=datetime.utcnow)

    submission = db.relationship("FormSubmission", backref=db.backref("ceac_overrides", cascade="all, delete-orphan"))
