"""ITIN / Form W-7 layer (Tax & ITIN Services) on top of the case architecture. Additive: four new tables, nothing existing changes.

  ItinCaseData     the ITIN case's tax context (tax year, scope answers, income type for the associated return) and OG's package / IRS tracking. Reusable by a
                   future Tax Return case (people, documents and this basic tax information already live at case level).
  W7Application    one row per W-7 application (one per ITIN applicant Person): applicant kind, W-7 reason candidate (derived) and the reason CONFIRMED by staff,
                   signature status recorded by staff, CAA verification (explicit staff action only).
  ItinDocTrack     the physical-original / CAA side of ONE document requirement (a digital upload never satisfies it).
  PassportExtraction  what was read from an uploaded passport/visa page (by a machine, by staff, or typed by the customer) and whether the customer confirmed it.
"""

from datetime import datetime

from app.extensions import db

ITIN_STAGES = (
    ("intake_started", "Intake Started", "Intake iniciado"),
    ("waiting_docs", "Waiting for Documents", "Esperando documentos"),
    ("waiting_originals", "Waiting for Original Documents", "Esperando documentos originales"),
    ("ready_review", "Ready for OG Review", "Listo para revisión de OG"),
    ("og_reviewing", "OG Reviewing", "OG está revisando"),
    ("tax_preparation", "Tax Preparation", "Preparación de impuestos"),
    ("ready_signature", "Ready for Signature", "Listo para firma"),
    ("ready_irs", "Ready for IRS", "Listo para el IRS"),
    ("sent_irs", "Sent to IRS", "Enviado al IRS"),
    ("irs_processing", "IRS Processing", "En proceso en el IRS"),
    ("irs_response", "IRS Response Received", "Respuesta del IRS recibida"),
    ("completed", "Completed", "Completado"),
)
STAGE_EN = {k: en for k, en, _es in ITIN_STAGES}
STAGE_ES = {k: es for k, _en, es in ITIN_STAGES}
ORIGINAL_STATES = (
    ("none", "Not required", "No se requiere"),
    ("required", "Original required", "Se requiere el original"),
    ("will_mail", "Customer will mail it", "El cliente lo enviará por correo"),
    ("will_bring", "Customer will bring it", "El cliente lo traerá en persona"),
    ("in_transit", "Original in transit", "Original en camino"),
    ("received", "Original received by OG", "Original recibido por OG"),
    ("caa_verified", "CAA verified", "Verificado por el CAA"),
    ("ready_to_return", "Ready to return", "Listo para devolver"),
    ("returned", "Returned to client", "Devuelto al cliente"),
)
ORIGINAL_EN = {k: en for k, en, _es in ORIGINAL_STATES}
ORIGINAL_ES = {k: es for k, _en, es in ORIGINAL_STATES}


class ItinCaseData(db.Model):
    __tablename__ = "itin_case_data"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, unique=True)
    tax_year = db.Column(db.Integer)
    request_kind = db.Column(db.String(10))  # new | renew | unsure
    preparing_return = db.Column(db.String(10))  # yes | not_sure
    taxpayer_us_status = db.Column(db.String(10))  # yes (U.S. citizen / permanent resident) | no | unsure
    stage = db.Column(db.String(20))  # set by staff; empty = derived from the intake and documents
    income_type = db.Column(db.String(20))  # employee | self | both | other | unsure (the case's primary taxpayer)
    work_activity = db.Column(db.String(200))
    occupation = db.Column(db.String(120))
    gross_income = db.Column(db.String(30))
    tax_return_ready_at = db.Column(db.DateTime)
    w7_ready_at = db.Column(db.DateTime)
    docs_ready_at = db.Column(db.DateTime)
    ready_for_irs_at = db.Column(db.DateTime)
    ready_for_irs_by = db.Column(db.String(120))
    usps_tracking = db.Column(db.String(60))
    irs_mailed_date = db.Column(db.Date)
    irs_delivered_date = db.Column(db.Date)
    irs_mailing_status = db.Column(db.String(120))
    irs_outcome = db.Column(db.String(20))  # itin_issued | irs_notice | other (recorded by staff; never inferred)
    irs_outcome_at = db.Column(db.Date)
    irs_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = db.relationship("Case", backref=db.backref("itin_data", uselist=False, cascade="all, delete-orphan"))


class W7Application(db.Model):
    __tablename__ = "w7_applications"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"), nullable=False, unique=True)
    applicant_kind = db.Column(db.String(12), nullable=False, default="primary", server_default="primary")  # primary | spouse | dependent
    application_type = db.Column(db.String(10), default="new")  # new | renew | unsure
    reason_candidate = db.Column(db.String(40))
    reason_confirmed = db.Column(db.String(4))  # a-h, confirmed by staff before Ready for IRS
    reason_confirmed_by = db.Column(db.String(120))
    reason_confirmed_at = db.Column(db.DateTime)
    reason_note = db.Column(db.Text)
    signature_state = db.Column(db.String(16), default="not_started", server_default="not_started")  # not_started | needs_signature | signed_recorded (by staff)
    signature_note = db.Column(db.String(200))
    caa_status = db.Column(db.String(12), default="not_reviewed", server_default="not_reviewed")  # not_reviewed | verified
    caa_verified_by = db.Column(db.String(120))
    caa_verified_at = db.Column(db.DateTime)
    caa_note = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    submission = db.relationship("FormSubmission", backref=db.backref("w7", uselist=False, cascade="all, delete-orphan"))


class ItinDocTrack(db.Model):
    __tablename__ = "itin_doc_tracks"

    id = db.Column(db.Integer, primary_key=True)
    requirement_id = db.Column(db.Integer, db.ForeignKey("case_document_requirements.id"), nullable=False, unique=True)
    doc_key = db.Column(db.String(30))
    original_required = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    caa_route = db.Column(db.String(12), default="none")  # caa (OG can verify) | irs_original (goes to the IRS with the package) | none
    original_state = db.Column(db.String(16), default="none", server_default="none")
    delivery_choice = db.Column(db.String(10))  # mail | in_person
    mailed_date = db.Column(db.Date)
    inbound_tracking = db.Column(db.String(60))
    received_date = db.Column(db.Date)
    received_by = db.Column(db.String(120))
    caa_verified_by = db.Column(db.String(120))
    caa_verified_at = db.Column(db.DateTime)
    caa_document_id = db.Column(db.Integer)  # the vault document version that was verified
    return_method = db.Column(db.String(20))
    returned_date = db.Column(db.Date)
    outbound_tracking = db.Column(db.String(60))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    requirement = db.relationship("DocumentRequirement", backref=db.backref("itin_track", uselist=False, cascade="all, delete-orphan"))


class PassportExtraction(db.Model):
    __tablename__ = "w7_extractions"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"), nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey("case_documents.id"))
    kind = db.Column(db.String(10), default="passport")  # passport | visa
    source = db.Column(db.String(14))  # mrz_ocr | staff_read | customer_typed
    values_json = db.Column(db.Text)
    status = db.Column(db.String(12), default="pending")  # pending | confirmed | superseded
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at = db.Column(db.DateTime)
    confirmed_by = db.Column(db.String(20))  # customer

    submission = db.relationship("FormSubmission", backref=db.backref("extractions", cascade="all, delete-orphan"))
