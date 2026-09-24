"""Tax Return case layer (Individual & Family Tax Preparation) on top of the case architecture. Additive: new tables only.

  TaxCaseData      one row per TAX RETURN case (`Case.case_type == "tax_return"`): tax year, workflow status, the interview answers (year-specific facts), the customer's
                   document choices (upload later / can't find), the terms acceptance and the price / payment state. The stable identity facts of the people stay on Person.
  TaxRecord        a repeating thing inside one tax year: a potential dependent (linked to a real Person) or a self-employment activity.
  TaxPriceRule     the DATA-DRIVEN price configuration of a tax year (base prices, add-ons, discount, thresholds, manual-review triggers). Edited in Admin.
  TaxPriceQuote    every price the case ever had (revisions): the system estimate with its rule snapshot, the returning discount, and OG's confirmed fee.
  TermsAcceptance  a versioned, auditable acceptance of OG's tax preparation terms.
  TaxBankInfo      refund direct-deposit details, encrypted at rest; only the last digits are ever shown.
"""

import json
from datetime import datetime

from app.extensions import db

TAX_STATUSES = (
    ("draft", "Draft", "Borrador"),
    ("submitted", "Submitted to OG", "Enviado a OG"),
    ("og_review", "OG Review", "En revisión por OG"),
    ("waiting_client", "Waiting for Client", "Esperando tu información"),
    ("ready_prep", "Ready for Preparation", "Listo para preparar"),
    ("in_prep", "In Preparation", "En preparación"),
    ("client_review", "Ready for Client Review / Signature", "Listo para tu revisión y firma"),
    ("ready_file", "Ready to File", "Listo para presentar"),
    ("filed", "Filed", "Presentado"),
    ("accepted", "Accepted", "Aceptado"),
    ("completed", "Completed", "Completado"),
    ("rejected", "IRS/State Rejected", "Rechazado por el IRS o el estado"),
    ("amendment", "Amendment Needed", "Se necesita una enmienda"),
    ("on_hold", "On Hold", "En pausa"),
    ("closed", "Closed", "Cerrado"),
    ("reopened", "Reopened for Customer Editing", "Reabierto para que lo edites"),
)
TAX_STATUS_EN = {k: en for k, en, _es in TAX_STATUSES}
TAX_STATUS_ES = {k: es for k, _en, es in TAX_STATUSES}


class TaxCaseData(db.Model):
    __tablename__ = "tax_case_data"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, unique=True)
    tax_year = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="draft", server_default="draft")
    language = db.Column(db.String(2))
    is_returning = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    answers_json = db.Column(db.Text)
    doc_choices_json = db.Column(db.Text)  # {rule_key: "later" | "cant_find" | "dont_have"}
    current_step = db.Column(db.String(40))
    submitted_at = db.Column(db.DateTime)
    reopened_at = db.Column(db.DateTime)
    reopen_message = db.Column(db.Text)
    resubmit_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    terms_id = db.Column(db.Integer, db.ForeignKey("terms_acceptances.id", name="fk_tax_terms"))
    customer_message = db.Column(db.Text)  # what OG asked the customer (shown in My Account while "Waiting for Client")
    price_status = db.Column(db.String(12), nullable=False, default="none", server_default="none")  # none | estimated | manual | confirmed
    payment_status = db.Column(db.String(12), nullable=False, default="not_started", server_default="not_started")
    payment_reference = db.Column(db.String(80))
    filed_at = db.Column(db.Date)
    accepted_at = db.Column(db.Date)
    filing_note = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = db.relationship("Case", backref=db.backref("tax_data", uselist=False, cascade="all, delete-orphan"))
    records = db.relationship("TaxRecord", backref="tax", order_by="TaxRecord.sort_order, TaxRecord.id", cascade="all, delete-orphan")
    quotes = db.relationship("TaxPriceQuote", backref="tax", order_by="TaxPriceQuote.revision", cascade="all, delete-orphan")
    terms = db.relationship("TermsAcceptance", foreign_keys=[terms_id])
    bank = db.relationship("TaxBankInfo", uselist=False, backref="tax", cascade="all, delete-orphan")

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
    def current_quote(self):
        live = [q for q in self.quotes if q.status != "superseded"]
        return live[-1] if live else (self.quotes[-1] if self.quotes else None)


class TaxRecord(db.Model):
    __tablename__ = "tax_records"

    id = db.Column(db.Integer, primary_key=True)
    tax_case_id = db.Column(db.Integer, db.ForeignKey("tax_case_data.id"), nullable=False, index=True)
    kind = db.Column(db.String(16), nullable=False)  # dependent | business
    person_id = db.Column(db.Integer, db.ForeignKey("case_people.id"))  # dependent: the CasePerson (a real Person)
    data_json = db.Column(db.Text)
    complete = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    person = db.relationship("CasePerson")

    @property
    def data(self):
        try:
            return json.loads(self.data_json) if self.data_json else {}
        except ValueError:
            return {}

    @data.setter
    def data(self, value):
        self.data_json = json.dumps(value, ensure_ascii=False)


class TaxPriceRule(db.Model):
    __tablename__ = "tax_price_rules"
    __table_args__ = (db.UniqueConstraint("tax_year", "code", name="uq_tax_price_rule"),)

    id = db.Column(db.Integer, primary_key=True)
    tax_year = db.Column(db.Integer, nullable=False, index=True)
    code = db.Column(db.String(40), nullable=False)
    kind = db.Column(db.String(10), nullable=False)  # base | addon | discount | setting | trigger
    label_en = db.Column(db.String(160), nullable=False)
    label_es = db.Column(db.String(160), nullable=False)
    amount_cents = db.Column(db.Integer)
    percent = db.Column(db.Float)
    active = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    params_json = db.Column(db.Text)  # e.g. {"included": 3} (W-2s / dependents included in the base) or {"stackable": false}
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.String(120))

    @property
    def params(self):
        try:
            return json.loads(self.params_json) if self.params_json else {}
        except ValueError:
            return {}


class TaxPriceQuote(db.Model):
    __tablename__ = "tax_price_quotes"

    id = db.Column(db.Integer, primary_key=True)
    tax_case_id = db.Column(db.Integer, db.ForeignKey("tax_case_data.id"), nullable=False, index=True)
    revision = db.Column(db.Integer, nullable=False, default=1)
    source = db.Column(db.String(8), nullable=False, default="system")  # system | admin
    mode = db.Column(db.String(8), nullable=False, default="auto")  # auto | manual
    category = db.Column(db.String(16))  # single | mfj | hoh | mfj_family | qss (pricing category, NOT a filing-status conclusion)
    lines_json = db.Column(db.Text)
    system_estimate_cents = db.Column(db.Integer)
    discount_percent = db.Column(db.Float)
    discount_cents = db.Column(db.Integer, nullable=False, default=0)
    estimated_final_cents = db.Column(db.Integer)
    final_fee_cents = db.Column(db.Integer)  # OG's fee once staff set it
    previous_fee_cents = db.Column(db.Integer)
    status = db.Column(db.String(12), nullable=False, default="estimated")  # estimated | confirmed | revised | superseded
    reason = db.Column(db.String(400))
    staff = db.Column(db.String(120))
    config_json = db.Column(db.Text)  # the rules used (snapshot: later price changes never rewrite this case)
    flags_json = db.Column(db.Text)
    needs_ack = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    acknowledged_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def lines(self):
        try:
            return json.loads(self.lines_json) if self.lines_json else []
        except ValueError:
            return []

    @property
    def flags(self):
        try:
            return json.loads(self.flags_json) if self.flags_json else []
        except ValueError:
            return []


class TermsAcceptance(db.Model):
    __tablename__ = "terms_acceptances"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), index=True)
    terms_key = db.Column(db.String(30), nullable=False)  # tax_preparation
    version = db.Column(db.String(30), nullable=False)
    language = db.Column(db.String(2))
    certification_accepted = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    terms_accepted = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    accepted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ip_hash = db.Column(db.String(64))  # salted hash, never the address
    user_agent = db.Column(db.String(200))


class TaxBankInfo(db.Model):
    __tablename__ = "tax_bank_info"

    id = db.Column(db.Integer, primary_key=True)
    tax_case_id = db.Column(db.Integer, db.ForeignKey("tax_case_data.id"), nullable=False, unique=True)
    account_type = db.Column(db.String(10))  # checking | savings
    routing_enc = db.Column(db.Text)
    account_enc = db.Column(db.Text)
    routing_last4 = db.Column(db.String(4))
    account_last4 = db.Column(db.String(4))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
