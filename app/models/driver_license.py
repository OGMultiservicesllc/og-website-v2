"""NJ Driver License Assistance — a dedicated service on top of the existing Case architecture (additive: new tables only, no existing
table changes). Mirrors the shape of `app/models/tax.py`.

  DlCaseData        one row per `Case.case_type == "nj_driver_license"`: the guided-intake answers, the milestone the customer is on,
                     the SSN/ITIN/affidavit path, the three preferred MVC locations, and the price/terms state. Stable identity facts
                     (name, DOB, phone, address) stay on the customer's Person, same as every other intake.
  DlPriceRule        DATA-DRIVEN price configuration (translation prices by document+language, appointment assistance fee). Edited in Admin.
  DlPriceQuote       every price the case ever had (revisions): the estimate with its rule snapshot and OG's confirmed total.
  MvcLocation        the Admin-managed list of MVC agency locations offered as 1st/2nd/3rd choice for appointment assistance.
  DlQuestion / DlQuestionOption   the original NJ Knowledge Test practice question bank (topic-tagged, EN/ES, versioned).
  DlAttempt / DlAttemptResponse   one practice/simulation attempt and its per-question responses (score, topic performance, history).

Terms acceptance reuses the existing `TermsAcceptance` model (terms_key="nj_driver_license") — no new table needed for that.
"""

import json
from datetime import datetime

from app.extensions import db

DL_MILESTONES = (
    ("documents", "Document Preparation", "Preparación de Documentos"),
    ("initial_permit", "Initial Permit", "Permiso Inicial"),
    ("knowledge_test", "Knowledge Test", "Examen Teórico"),
    ("road_test", "Road Test", "Examen Práctico"),
    ("license_obtained", "License Obtained", "Licencia Obtenida"),
    ("completed", "Completed", "Completado"),
)
DL_MILESTONE_EN = {k: en for k, en, _es in DL_MILESTONES}
DL_MILESTONE_ES = {k: es for k, _en, es in DL_MILESTONES}
DL_MILESTONE_ORDER = [k for k, _en, _es in DL_MILESTONES]

# Case-level workflow status (parallels TAX_STATUSES/TAX_STATUS_EN pattern)
DL_STATUSES = (
    ("draft", "Draft", "Borrador"),
    ("submitted", "Submitted to OG", "Enviado a OG"),
    ("og_review", "OG Review", "En revisión por OG"),
    ("waiting_client", "Waiting for Client", "Esperando tu información"),
    ("in_progress", "In Progress", "En progreso"),
    ("completed", "Completed", "Completado"),
    ("on_hold", "On Hold", "En pausa"),
    ("closed", "Closed", "Cerrado"),
    ("reopened", "Reopened for Customer Editing", "Reabierto para que lo edites"),
)
DL_STATUS_EN = {k: en for k, en, _es in DL_STATUSES}
DL_STATUS_ES = {k: es for k, _en, es in DL_STATUSES}

# Sub-statuses for the three test-taking milestones (Admin sets these explicitly; never inferred from a foreign license or similar)
INITIAL_PERMIT_STATES = ("not_started", "appointment_needed", "appointment_requested", "scheduled", "obtained")
KNOWLEDGE_TEST_STATES = ("not_started", "ready_to_practice", "appointment_requested", "scheduled", "passed", "failed")
ROAD_TEST_STATES = ("to_be_determined", "required", "not_required", "appointment_needed", "scheduled", "passed", "failed")


class DlCaseData(db.Model):
    __tablename__ = "dl_case_data"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, unique=True)
    status = db.Column(db.String(16), nullable=False, default="draft", server_default="draft")
    language = db.Column(db.String(2))
    answers_json = db.Column(db.Text)
    doc_choices_json = db.Column(db.Text)  # {rule_key: "later" | "dont_have"}
    current_step = db.Column(db.String(40))
    milestone = db.Column(db.String(20), nullable=False, default="documents", server_default="documents")
    initial_permit_state = db.Column(db.String(20), nullable=False, default="not_started", server_default="not_started")
    knowledge_test_state = db.Column(db.String(20), nullable=False, default="not_started", server_default="not_started")
    road_test_state = db.Column(db.String(20), nullable=False, default="to_be_determined", server_default="to_be_determined")
    appointment_json = db.Column(db.Text)  # {location_id, date, note} recorded by staff once scheduled — informational only, never a guarantee
    rules_version = db.Column(db.String(20))  # the app.driver_license.rules RULES_VERSION in effect when documents were last assessed
    submitted_at = db.Column(db.DateTime)
    reopened_at = db.Column(db.DateTime)
    reopen_message = db.Column(db.Text)
    resubmit_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    terms_id = db.Column(db.Integer, db.ForeignKey("terms_acceptances.id", name="fk_dl_terms"))
    customer_message = db.Column(db.Text)
    price_status = db.Column(db.String(12), nullable=False, default="none", server_default="none")  # none | estimated | manual | confirmed
    loc1_id = db.Column(db.Integer, db.ForeignKey("mvc_locations.id"))
    loc2_id = db.Column(db.Integer, db.ForeignKey("mvc_locations.id"))
    loc3_id = db.Column(db.Integer, db.ForeignKey("mvc_locations.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = db.relationship("Case", backref=db.backref("dl_data", uselist=False, cascade="all, delete-orphan"))
    quotes = db.relationship("DlPriceQuote", backref="dl", order_by="DlPriceQuote.revision", cascade="all, delete-orphan")
    terms = db.relationship("TermsAcceptance", foreign_keys=[terms_id])
    loc1 = db.relationship("MvcLocation", foreign_keys=[loc1_id])
    loc2 = db.relationship("MvcLocation", foreign_keys=[loc2_id])
    loc3 = db.relationship("MvcLocation", foreign_keys=[loc3_id])

    @property
    def answers(self):
        try:
            return json.loads(self.answers_json) if self.answers_json else {}
        except ValueError:
            return {}

    @answers.setter
    def answers(self, value):
        self.answers_json = json.dumps(value, ensure_ascii=False)

    @property
    def doc_choices(self):
        try:
            return json.loads(self.doc_choices_json) if self.doc_choices_json else {}
        except ValueError:
            return {}

    @doc_choices.setter
    def doc_choices(self, value):
        self.doc_choices_json = json.dumps(value, ensure_ascii=False)

    @property
    def appointment(self):
        try:
            return json.loads(self.appointment_json) if self.appointment_json else {}
        except ValueError:
            return {}

    @appointment.setter
    def appointment(self, value):
        self.appointment_json = json.dumps(value, ensure_ascii=False)

    @property
    def current_quote(self):
        live = [q for q in self.quotes if q.status != "superseded"]
        return live[-1] if live else (self.quotes[-1] if self.quotes else None)


class DlPriceRule(db.Model):
    __tablename__ = "dl_price_rules"
    __table_args__ = (db.UniqueConstraint("code", name="uq_dl_price_rule"),)

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False)
    kind = db.Column(db.String(14), nullable=False)  # translation | appointment | setting
    doc_key = db.Column(db.String(40))  # which document type this translation price applies to (rules.DOCUMENT_TYPES key)
    lang_key = db.Column(db.String(10))  # source language this price applies to ("es", "pt", "fr", "other")
    label_en = db.Column(db.String(160), nullable=False)
    label_es = db.Column(db.String(160), nullable=False)
    amount_cents = db.Column(db.Integer)
    requires_review = db.Column(db.Boolean, nullable=False, default=False, server_default="0")  # price cannot be quoted automatically (e.g. complex birth certificate)
    active = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    params_json = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.String(120))

    @property
    def params(self):
        try:
            return json.loads(self.params_json) if self.params_json else {}
        except ValueError:
            return {}


class DlPriceQuote(db.Model):
    __tablename__ = "dl_price_quotes"

    id = db.Column(db.Integer, primary_key=True)
    dl_case_id = db.Column(db.Integer, db.ForeignKey("dl_case_data.id"), nullable=False, index=True)
    revision = db.Column(db.Integer, nullable=False, default=1)
    source = db.Column(db.String(8), nullable=False, default="system")  # system | admin
    lines_json = db.Column(db.Text)  # [{code, label_en, label_es, amount_cents, requires_review}]
    system_estimate_cents = db.Column(db.Integer)
    has_review_item = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    final_total_cents = db.Column(db.Integer)  # OG's confirmed total once staff set it
    previous_total_cents = db.Column(db.Integer)
    status = db.Column(db.String(12), nullable=False, default="estimated")  # estimated | confirmed | revised | superseded
    reason = db.Column(db.String(400))
    staff = db.Column(db.String(120))
    needs_ack = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    acknowledged_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def lines(self):
        try:
            return json.loads(self.lines_json) if self.lines_json else []
        except ValueError:
            return []


class MvcLocation(db.Model):
    """Admin-managed MVC agency location list (never scraped/hard-coded into templates)."""

    __tablename__ = "mvc_locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    appointment_types_json = db.Column(db.Text)  # e.g. ["initial_permit", "knowledge_test", "road_test"] — empty/null = all types


# ------------------------------------------------------------------ NJ Knowledge Test practice (its own small question bank — NOT the Academy Quiz system,
# which is one-quiz-per-lesson; this needs topic/difficulty tagging and random draws across a shared bank for three practice modes)
DL_TOPICS = (
    "road_signs", "traffic_signals", "right_of_way", "speed_limits", "parking", "passing", "defensive_driving",
    "dui", "sharing_road", "pedestrians", "school_buses", "emergency_vehicles", "seat_belts", "driving_conditions",
    "vehicle_safety", "nj_laws",
)


class DlQuestion(db.Model):
    __tablename__ = "dl_questions"

    id = db.Column(db.Integer, primary_key=True)
    concept_key = db.Column(db.String(60), nullable=False, unique=True)  # stable, language-independent id (e.g. "stop_sign_full_stop")
    topic = db.Column(db.String(30), nullable=False)
    difficulty = db.Column(db.String(10), nullable=False, default="medium", server_default="medium")  # easy | medium | hard
    question_en = db.Column(db.Text, nullable=False)
    question_es = db.Column(db.Text, nullable=False)
    explanation_en = db.Column(db.Text)
    explanation_es = db.Column(db.Text)
    source_ref = db.Column(db.String(200))  # where in the NJ Driver Manual this concept is covered, when known
    version = db.Column(db.String(20), nullable=False, default="v1", server_default="v1")
    active = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    options = db.relationship("DlQuestionOption", backref="question", order_by="DlQuestionOption.sort_order", cascade="all, delete-orphan")

    def text(self, lang):
        return self.question_es if lang == "es" and self.question_es else self.question_en

    def explanation(self, lang):
        return (self.explanation_es if lang == "es" else self.explanation_en) or ""


class DlQuestionOption(db.Model):
    __tablename__ = "dl_question_options"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("dl_questions.id"), nullable=False)
    text_en = db.Column(db.String(300), nullable=False)
    text_es = db.Column(db.String(300), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def text(self, lang):
        return self.text_es if lang == "es" and self.text_es else self.text_en


class DlAttempt(db.Model):
    __tablename__ = "dl_attempts"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    dl_case_id = db.Column(db.Integer, db.ForeignKey("dl_case_data.id"))  # set only if the student also has a Driver License case; never required
    mode = db.Column(db.String(10), nullable=False)  # quick | topic | full
    topic_filter = db.Column(db.String(30))  # set only for mode == "topic"
    language = db.Column(db.String(2), nullable=False, default="en", server_default="en")
    total = db.Column(db.Integer, nullable=False)
    correct = db.Column(db.Integer)
    percent = db.Column(db.Integer)
    passed = db.Column(db.Boolean)  # null until completed; pass target is a setting (default 80%), not hard-coded here
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime)

    responses = db.relationship("DlAttemptResponse", backref="attempt", order_by="DlAttemptResponse.sort_order", cascade="all, delete-orphan")
    student = db.relationship("Student")


class DlAttemptResponse(db.Model):
    __tablename__ = "dl_attempt_responses"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("dl_attempts.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("dl_questions.id"), nullable=False)
    selected_option_id = db.Column(db.Integer, db.ForeignKey("dl_question_options.id"))
    is_correct = db.Column(db.Boolean)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    question = db.relationship("DlQuestion")
    selected_option = db.relationship("DlQuestionOption")
