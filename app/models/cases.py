"""Case architecture: Customer -> Cases -> People / Applications / Shared data / Document vault.

  CASE         the customer's overall matter ("Adjustment of Status", "Naturalization"). OGC-000123.
  APPLICATION  one Smart Intake / official form inside a case (the existing FormSubmission, OGF-...).
  PERSON       a real person taking part in a case. Only the CUSTOMER has an OG login; the others
               (spouse, sponsor, child...) never do and gain no access by being listed.
  ROLE         what a person is in ONE application (Juan = petitioner in the I-130, sponsor in a
               future I-864). Roles are mappings, never duplicate people.
  FACT         a canonical fact about a person (legal name, date of birth, A-Number, current address)
               with provenance: where it came from, where it is used, when it was last confirmed.
               Form-specific answers stay in the application; only facts that are the same real-world
               fact are shared, and only through app/case_types.py's explicit mapping.
  DOCUMENT     an uploaded file stored ONCE in the case vault.
  REQUIREMENT  something OG needs; separate from the document that satisfies it. One requirement can
               serve several applications, and one document can satisfy several requirements.

Additive by design: existing applications, answers, files, notes and activity are untouched; the only
change to an existing table is the nullable `form_submissions.case_id` / `activity_events.case_id`.
"""

from datetime import datetime

from app.extensions import db

CASE_STATUSES = (
    ("open", "Open"),
    ("in_review", "In Review"),
    ("waiting_client", "Waiting for Client"),
    ("completed", "Completed"),
    ("closed", "Closed"),
)
CASE_STATUS_LABELS = dict(CASE_STATUSES)

REQUIREMENT_STATUSES = (
    ("needed", "Needed"),
    ("requested", "Requested"),
    ("uploaded", "Uploaded"),
    ("under_review", "Under Review"),
    ("accepted", "Accepted"),
    ("needs_replacement", "Needs Replacement"),
)
REQUIREMENT_STATUS_LABELS = dict(REQUIREMENT_STATUSES)


class Case(db.Model):
    __tablename__ = "cases"

    id = db.Column(db.Integer, primary_key=True)
    case_number = db.Column(db.String(20), unique=True)  # "OGC-000123", assigned right after the row exists
    customer_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    case_type = db.Column(db.String(40), nullable=False, default="other", server_default="other")
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open", server_default="open")
    preferred_language = db.Column(db.String(2))
    origin = db.Column(db.String(10), nullable=False, default="auto", server_default="auto")  # auto | admin | migrated
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = db.Column(db.DateTime)

    customer = db.relationship("Student", backref=db.backref("cases", cascade="all, delete-orphan"))  # deleting a customer removes their cases like the rest of their data
    applications = db.relationship("FormSubmission", backref="case", order_by="FormSubmission.id")
    people = db.relationship("CasePerson", backref="case", order_by="CasePerson.id", cascade="all, delete-orphan")
    notes = db.relationship("CaseNote", backref="case", order_by="CaseNote.created_at", cascade="all, delete-orphan")
    requirements = db.relationship("DocumentRequirement", backref="case", order_by="DocumentRequirement.id", cascade="all, delete-orphan")
    documents = db.relationship("CaseDocument", backref="case", order_by="CaseDocument.id", cascade="all, delete-orphan")

    @property
    def status_label(self):
        return CASE_STATUS_LABELS.get(self.status, self.status)


class Person(db.Model):
    """A REAL person inside ONE customer's data domain. It exists once and may take part in many cases (as a `CasePerson`);
    the canonical, reusable person facts belong to it. Only the customer's own Person (`is_self`) is tied to an OG login;
    every other Person is a record about someone else and grants that someone nothing."""

    __tablename__ = "persons"
    __table_args__ = (db.Index("uq_person_self", "customer_id", unique=True, sqlite_where=db.text("is_self = 1")),)

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    is_self = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    given_name = db.Column(db.String(120))
    family_name = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    customer = db.relationship("Student", backref=db.backref("persons", cascade="all, delete-orphan"))
    facts = db.relationship("PersonFact", backref="owner", order_by="PersonFact.id", cascade="all, delete-orphan", foreign_keys="PersonFact.real_person_id")

    @property
    def full_name(self):
        return " ".join(x for x in (self.given_name, self.family_name) if x) or "(unnamed)"


class CasePerson(db.Model):
    """A person in a case. `student_id` is set only for the customer (the OG account holder)."""

    __tablename__ = "case_people"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    person_id = db.Column(db.Integer, db.ForeignKey("persons.id", name="fk_case_people_person"), index=True)  # the real person this CasePerson represents
    is_customer = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    relationship_key = db.Column(db.String(30), nullable=False, default="other", server_default="other")  # relation to the customer
    given_name = db.Column(db.String(120))
    family_name = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    roles = db.relationship("ApplicationRole", backref="person", cascade="all, delete-orphan")
    person = db.relationship("Person", backref=db.backref("case_people", order_by="CasePerson.id"))

    @property
    def facts(self):
        """The reusable facts of the REAL person this CasePerson represents (they follow the person across cases)."""
        return self.person.facts if self.person is not None else []

    @property
    def full_name(self):
        return " ".join(x for x in (self.given_name, self.family_name) if x) or "(unnamed)"


class ApplicationRole(db.Model):
    """What a case person is in ONE application (petitioner, beneficiary, applicant, sponsor...)."""

    __tablename__ = "case_application_roles"
    __table_args__ = (db.UniqueConstraint("submission_id", "person_id", "role_key", name="uq_case_role"),)

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"), nullable=False, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("case_people.id"), nullable=False, index=True)
    role_key = db.Column(db.String(40), nullable=False)

    submission = db.relationship("FormSubmission", backref=db.backref("case_roles", cascade="all, delete-orphan"))


class PersonFact(db.Model):
    """One canonical fact about a person, with provenance. The value is JSON so a fact can be a
    string, a date or a small record (an address)."""

    __tablename__ = "case_person_facts"
    __table_args__ = (db.UniqueConstraint("person_id", "fact_key", name="uq_person_fact"),
                      db.UniqueConstraint("real_person_id", "fact_key", name="uq_person_fact_owner"))

    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("case_people.id"), index=True)  # the CasePerson it was first recorded through (history only)
    real_person_id = db.Column(db.Integer, db.ForeignKey("persons.id", name="fk_person_fact_owner"), index=True)  # the REAL person it belongs to
    fact_key = db.Column(db.String(40), nullable=False)
    value_json = db.Column(db.Text)
    is_sensitive = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    source_submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"))  # where the value ORIGINATED
    source_form = db.Column(db.String(20))
    source_field = db.Column(db.String(100))
    source_ref = db.Column(db.String(120))
    needs_review = db.Column(db.Boolean, nullable=False, default=False, server_default="0")  # a later application gave a different value
    first_recorded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_confirmed_at = db.Column(db.DateTime)
    confirmed_by = db.Column(db.String(120))

    source_submission = db.relationship("FormSubmission", foreign_keys=[source_submission_id])
    origin = db.relationship("CasePerson", foreign_keys=[person_id])
    claims = db.relationship("PersonFactClaim", backref="fact", order_by="PersonFactClaim.id", cascade="all, delete-orphan")
    uses = db.relationship("PersonFactUse", backref="fact", cascade="all, delete-orphan")
    events = db.relationship("PersonFactEvent", backref="fact", order_by="PersonFactEvent.id", cascade="all, delete-orphan")


class PersonFactUse(db.Model):
    """An application that reads this fact (so we know where a value is being used)."""

    __tablename__ = "case_person_fact_uses"
    __table_args__ = (db.UniqueConstraint("fact_id", "submission_id", "field_name", name="uq_fact_use"),)

    id = db.Column(db.Integer, primary_key=True)
    fact_id = db.Column(db.Integer, db.ForeignKey("case_person_facts.id"), nullable=False, index=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"), nullable=False)
    field_name = db.Column(db.String(100))
    last_used_at = db.Column(db.DateTime, default=datetime.utcnow)

    submission = db.relationship("FormSubmission")


class PersonFactEvent(db.Model):
    """Small provenance history (not event sourcing): recorded / updated / confirmed / differs."""

    __tablename__ = "case_person_fact_events"

    id = db.Column(db.Integer, primary_key=True)
    fact_id = db.Column(db.Integer, db.ForeignKey("case_person_facts.id"), nullable=False, index=True)
    kind = db.Column(db.String(12), nullable=False)
    old_value_json = db.Column(db.Text)
    new_value_json = db.Column(db.Text)
    submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"))
    actor = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    submission = db.relationship("FormSubmission")


class PersonFactClaim(db.Model):
    """What ONE application states for a fact (its provenance, kept even when the canonical value later changes).
    Historical application answers are never rewritten: the claim is a record of what was provided, when, and in which state
    of the source application (draft / submitted / reopened). `resolved` = a customer/OG conflict decision already covers it."""

    __tablename__ = "case_person_fact_claims"
    __table_args__ = (db.UniqueConstraint("fact_id", "submission_id", name="uq_fact_claim"),)

    id = db.Column(db.Integer, primary_key=True)
    fact_id = db.Column(db.Integer, db.ForeignKey("case_person_facts.id"), nullable=False, index=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"), index=True)  # None = entered directly in a resolution
    source_form = db.Column(db.String(20))
    source_field = db.Column(db.String(100))
    source_ref = db.Column(db.String(120))
    value_json = db.Column(db.Text)
    state = db.Column(db.String(12), nullable=False, default="draft", server_default="draft")  # draft | submitted | reopened | manual
    resolved = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    submission = db.relationship("FormSubmission", foreign_keys=[submission_id])


class ApplicationLink(db.Model):
    """Two applications of one case that belong together (e.g. an I-485 and the I-130 it is based on)."""

    __tablename__ = "case_application_links"
    __table_args__ = (db.UniqueConstraint("submission_id", "related_submission_id", "kind", name="uq_app_link"),)

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"), nullable=False, index=True)
    related_submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"), nullable=False, index=True)
    kind = db.Column(db.String(30), nullable=False, default="underlying_petition", server_default="underlying_petition")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    submission = db.relationship("FormSubmission", foreign_keys=[submission_id], backref=db.backref("links_out", cascade="all, delete-orphan"))
    related = db.relationship("FormSubmission", foreign_keys=[related_submission_id], backref=db.backref("links_in", cascade="all, delete-orphan"))


class CaseNote(db.Model):
    """Internal, case-level note. Never shown to the customer."""

    __tablename__ = "case_notes"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    author_name = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class CaseDocument(db.Model):
    """A file in the case vault, stored once. What it satisfies is recorded by attachments."""

    __tablename__ = "case_documents"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("case_people.id"))
    category = db.Column(db.String(40), nullable=False, default="other", server_default="other")
    title = db.Column(db.String(200))
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    size_bytes = db.Column(db.Integer, default=0)
    mime_type = db.Column(db.String(80))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    uploaded_by = db.Column(db.String(10), nullable=False, default="customer", server_default="customer")  # customer | admin
    uploaded_by_id = db.Column(db.Integer)
    replaces_id = db.Column(db.Integer, db.ForeignKey("case_documents.id"))  # the earlier version this one replaced
    superseded_at = db.Column(db.DateTime)  # set when a replacement took over; the file itself is kept
    reused_from_id = db.Column(db.Integer)  # a document brought over from another case of the same customer (same stored file; never copied twice)

    person = db.relationship("CasePerson")
    replaces = db.relationship("CaseDocument", remote_side=[id], foreign_keys=[replaces_id])

    @property
    def is_current(self):
        return self.superseded_at is None


class DocumentRequirement(db.Model):
    """Something OG needs from the customer. Separate from the document that satisfies it."""

    __tablename__ = "case_document_requirements"
    __table_args__ = (db.Index("ix_req_case_rule", "case_id", "rule_key"),)

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("case_people.id"))
    category = db.Column(db.String(40), nullable=False, default="other", server_default="other")
    title = db.Column(db.String(200), nullable=False)
    customer_message = db.Column(db.Text)
    internal_note = db.Column(db.Text)  # never shown to the customer
    source = db.Column(db.String(10), nullable=False, default="admin", server_default="admin")  # system | admin
    rule_key = db.Column(db.String(100))  # stable key so a rule can create/withdraw exactly its own requirement
    source_key = db.Column(db.String(60))  # the rule set / application that owns a system requirement
    status = db.Column(db.String(20), nullable=False, default="requested", server_default="requested")
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_at = db.Column(db.DateTime)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.String(120))
    review_message = db.Column(db.Text)  # customer-facing reason for a replacement request
    accepted_at = db.Column(db.DateTime)
    withdrawn_at = db.Column(db.DateTime)
    reused_at = db.Column(db.DateTime)  # set when an existing vault document already satisfied this requirement
    doc_basis = db.Column(db.String(12))  # source | workflow | answer | admin: why OG asks (never claims a USCIS requirement OG cannot cite)
    created_by = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    person = db.relationship("CasePerson")
    application_links = db.relationship("RequirementApplication", backref="requirement", cascade="all, delete-orphan")
    attachments = db.relationship("DocumentAttachment", backref="requirement", order_by="DocumentAttachment.id", cascade="all, delete-orphan")

    @property
    def status_label(self):
        return REQUIREMENT_STATUS_LABELS.get(self.status, self.status)

    @property
    def applications(self):
        return [l.submission for l in self.application_links]

    @property
    def current_attachment(self):
        live = [a for a in self.attachments if a.superseded_at is None]
        return live[-1] if live else None

    @property
    def current_document(self):
        a = self.current_attachment
        return a.document if a else None


class RequirementApplication(db.Model):
    """The applications a requirement serves (one passport requirement can serve I-130, I-485, I-765)."""

    __tablename__ = "case_requirement_applications"

    requirement_id = db.Column(db.Integer, db.ForeignKey("case_document_requirements.id"), primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"), primary_key=True)

    submission = db.relationship("FormSubmission")


class DocumentAttachment(db.Model):
    """A document filling a requirement. History is kept: a replacement supersedes, never deletes."""

    __tablename__ = "case_document_attachments"

    id = db.Column(db.Integer, primary_key=True)
    requirement_id = db.Column(db.Integer, db.ForeignKey("case_document_requirements.id"), nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey("case_documents.id"), nullable=False, index=True)
    attached_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    superseded_at = db.Column(db.DateTime)
    superseded_reason = db.Column(db.String(30))  # replaced | needs_replacement | removed

    document = db.relationship("CaseDocument", backref=db.backref("attachments", cascade="all, delete-orphan"))


class CaseRevision(db.Model):
    """One reopen -> resubmit cycle for a CASE-LEVEL intake (Tax, NJ Driver License — anything that keeps its own
    case-data row instead of a `FormSubmission`). Mirrors `SubmissionRevision` (the generic Forms-engine intakes'
    equivalent) so Admin sees the same shape of change history everywhere, just keyed by `case_id` instead of
    `submission_id`. `reopened_by` distinguishes an Admin-initiated reopen from a customer's own self-service
    correction (NJ Driver License only) — both produce the identical audit trail."""

    __tablename__ = "case_revisions"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    reopened_at = db.Column(db.DateTime)
    reopened_by = db.Column(db.String(10), nullable=False, default="admin", server_default="admin")  # admin | customer
    reopened_by_id = db.Column(db.Integer)  # AdminUser.id or Student.id, matching `reopened_by`
    reopen_message = db.Column(db.Text)  # snapshot of the message shown to the customer, kept even after it's cleared
    resubmitted_at = db.Column(db.DateTime)
    changes_json = db.Column(db.Text)  # [{"label", "before", "after"}]
    before_json = db.Column(db.Text)  # full answers snapshot at reopen time (diagnostic; changes_json is what Admin reads)
    after_json = db.Column(db.Text)

    case = db.relationship("Case", backref=db.backref("revisions", order_by="CaseRevision.id", cascade="all, delete-orphan"))


# ---------------------------------------------------------------- every CasePerson is linked to a real Person at creation
from sqlalchemy import event, insert, select, update  # noqa: E402
from sqlalchemy.orm.attributes import set_committed_value  # noqa: E402


@event.listens_for(CasePerson, "after_insert")
def _link_case_person_to_person(mapper, connection, target):
    """The customer's own CasePerson (in ANY case) links to the customer's single self Person; anyone else gets their own Person
    (linking two different CasePeople is always an explicit decision, never a name match)."""
    if target.person_id is not None:
        return
    cases, persons = Case.__table__, Person.__table__
    customer_id = connection.execute(select(cases.c.customer_id).where(cases.c.id == target.case_id)).scalar()
    is_self = bool(target.is_customer) or (target.student_id is not None and target.student_id == customer_id)
    pid = None
    if is_self:
        pid = connection.execute(select(persons.c.id).where(persons.c.customer_id == customer_id, persons.c.is_self == True)).scalar()  # noqa: E712
    if pid is None:
        res = connection.execute(insert(persons).values(customer_id=customer_id, is_self=is_self, given_name=target.given_name,
                                                        family_name=target.family_name, created_at=datetime.utcnow()))
        pid = res.inserted_primary_key[0]
    connection.execute(update(CasePerson.__table__).where(CasePerson.__table__.c.id == target.id).values(person_id=pid))
    set_committed_value(target, "person_id", pid)
