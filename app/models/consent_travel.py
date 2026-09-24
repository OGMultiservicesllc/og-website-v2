"""Consent to Travel Authorization for Minors — a dedicated service on top of the existing Case architecture
(additive: new tables only). Mirrors the shape of `app/models/tax.py` / `app/models/driver_license.py`.

  ConsentTravelCaseData   one row per `Case.case_type == "consent_travel"`: the guided-intake answers,
                          workflow status, notarization location, price/payment state. Stable identity facts
                          (name, address) of every person involved live on their own real Person, same as
                          every other intake.
  ConsentTravelRecord     a repeating thing inside one case: a traveling child ("child"), or an auto-synced
                          consenting-adult entry ("adult" — mother and/or a specific father, only for the
                          adults who actually need to sign; never customer add/remove, only the interview
                          itself creates/withdraws these as child answers change).
  ConsentTravelPriceRule  DATA-DRIVEN price configuration (base document fee, additional-child fee). Edited
                          in Admin — never hardcoded in the pricing function.
  ConsentTravelQuote      every price the case ever had (revisions): the system estimate, and OG's confirmed
                          total once approved. Payment is never requestable before a quote is "confirmed".

Terms acceptance reuses the existing `TermsAcceptance` model (terms_key="consent_travel") — no new table.
"""

import json
from datetime import datetime

from app.extensions import db

CT_STATUSES = (
    ("draft", "Draft", "Borrador"),
    ("submitted", "Submitted — Pending OG Review", "Enviado — Pendiente de revisión por OG"),
    ("waiting_client", "Waiting for Client", "Esperando tu información"),
    ("approved", "Approved by OG", "Aprobado por OG"),
    ("in_progress", "In Progress", "En progreso"),
    ("completed", "Completed", "Completado"),
    ("on_hold", "On Hold", "En pausa"),
    ("closed", "Closed", "Cerrado"),
    ("reopened", "Reopened for Customer Editing", "Reabierto para que lo edites"),
)
CT_STATUS_EN = {k: en for k, en, _es in CT_STATUSES}
CT_STATUS_ES = {k: es for k, _en, es in CT_STATUSES}

LOCATIONS = {
    "nj": {
        "en": "New Jersey — Paterson", "es": "Nueva Jersey — Paterson",
        "address": "OG Multiservices LLC, 145 Presidential Blvd, STE 2, Paterson, NJ 07522",
    },
    "tx": {
        "en": "Texas — Spring", "es": "Texas — Spring",
        "address": "OG Multiservices LLC, 17014 Colony Creek Dr, Spring, TX 77379",
    },
}


class ConsentTravelCaseData(db.Model):
    __tablename__ = "consent_travel_case_data"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, unique=True)
    status = db.Column(db.String(16), nullable=False, default="draft", server_default="draft")
    language = db.Column(db.String(2))
    answers_json = db.Column(db.Text)
    doc_choices_json = db.Column(db.Text)  # {rule_key: "later" | "dont_have"}
    current_step = db.Column(db.String(40))
    submitted_at = db.Column(db.DateTime)
    reopened_at = db.Column(db.DateTime)
    reopen_message = db.Column(db.Text)
    resubmit_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    terms_id = db.Column(db.Integer, db.ForeignKey("terms_acceptances.id", name="fk_ct_terms"))
    customer_message = db.Column(db.Text)  # what OG asked the customer (shown in My Account while "Waiting for Client")
    approved_at = db.Column(db.DateTime)
    approved_by_admin_id = db.Column(db.Integer)
    price_status = db.Column(db.String(12), nullable=False, default="none", server_default="none")  # none | estimated | confirmed
    payment_status = db.Column(db.String(12), nullable=False, default="not_started", server_default="not_started")
    payment_reference = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = db.relationship("Case", backref=db.backref("consent_travel_data", uselist=False, cascade="all, delete-orphan"))
    records = db.relationship("ConsentTravelRecord", backref="ct", order_by="ConsentTravelRecord.sort_order, ConsentTravelRecord.id", cascade="all, delete-orphan")
    quotes = db.relationship("ConsentTravelQuote", backref="ct", order_by="ConsentTravelQuote.revision", cascade="all, delete-orphan")
    terms = db.relationship("TermsAcceptance", foreign_keys=[terms_id])

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

    @property
    def children(self):
        return [r for r in self.records if r.kind == "child"]

    @property
    def adult_records(self):
        return [r for r in self.records if r.kind == "adult"]


class ConsentTravelRecord(db.Model):
    __tablename__ = "consent_travel_records"

    id = db.Column(db.Integer, primary_key=True)
    ct_case_id = db.Column(db.Integer, db.ForeignKey("consent_travel_case_data.id"), nullable=False, index=True)
    kind = db.Column(db.String(16), nullable=False)  # child | adult
    person_id = db.Column(db.Integer, db.ForeignKey("case_people.id"))  # the real Person (child, or the consenting adult)
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


class ConsentTravelPriceRule(db.Model):
    __tablename__ = "consent_travel_price_rules"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False, unique=True)
    label_en = db.Column(db.String(160), nullable=False)
    label_es = db.Column(db.String(160), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.String(120))


class ConsentTravelQuote(db.Model):
    __tablename__ = "consent_travel_quotes"

    id = db.Column(db.Integer, primary_key=True)
    ct_case_id = db.Column(db.Integer, db.ForeignKey("consent_travel_case_data.id"), nullable=False, index=True)
    revision = db.Column(db.Integer, nullable=False, default=1)
    source = db.Column(db.String(8), nullable=False, default="system")  # system | admin
    lines_json = db.Column(db.Text)  # [{doc_index, children:[names], consenting:[names], amount_cents}]
    system_estimate_cents = db.Column(db.Integer)
    final_total_cents = db.Column(db.Integer)  # OG's confirmed total once approved
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
