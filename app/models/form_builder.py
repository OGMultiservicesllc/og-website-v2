"""OG Forms Builder — a bilingual, multi-page, no-code form engine.

This is a NEW system alongside the older CustomForm/CustomFormField (kept
untouched — see app/models/custom_form.py) and the shared Inquiry "leads"
table (also untouched, still used by contact/translation-quote/chat).
Forms built here use their own dedicated submission tables so a form with
file uploads, structured per-field values, and a status workflow never has
to be shoehorned into Inquiry's single JSON blob.

Every form is ONE bilingual record — never two parallel EN/ES forms. Every
translatable property is a pair of columns (`_en` / `_es`); everything that
must stay stable across languages (option values, internal field names,
conditional-rule targets) is a single untranslated column.
"""
import json
from datetime import datetime

from app.extensions import db


def _tok(text, lang, escape=False):
    """Replace name tokens such as {ben} (see app/intake_shared.py); a no-op for plain text."""
    if "{" not in text:
        return text
    from app.intake_shared import apply_tokens

    return apply_tokens(text, lang, escape=escape)

FORM_STATUSES = ("draft", "published", "archived")
# inquiry: public, no account (Contact Us, quote request, callback).
# service_intake: a structured client workflow for a specific OG service; needs a
# signed-in customer, autosaves, and can be resumed.
FORM_TYPES = ("inquiry", "service_intake")

# What customers and admins call each state of an application. "draft" is not a
# stored status: it is a submission that has not been completed yet.
SUBMISSION_STATUS_LABELS = {
    "draft": "Draft",
    "reopened": "Reopened for Editing",
    "new": "Submitted",
    "in_review": "In Review",
    "waiting_client": "Waiting for Client",
    "ready_for_ceac": "Ready for CEAC",
    "completed": "Completed",
    "archived": "Archived",
}
SUBMISSION_STATUS_LABELS_ES = {
    "draft": "Borrador",
    "reopened": "Reabierto para edición",
    "new": "Enviada",
    "in_review": "En revisión",
    "waiting_client": "Esperando al cliente",
    "ready_for_ceac": "Lista para CEAC",
    "completed": "Completada",
    "archived": "Archivada",
}
SUBMISSION_STATUSES = ("new", "in_review", "waiting_client", "ready_for_ceac", "completed", "archived")
CEAC_ONLY_STATUSES = ("ready_for_ceac",)  # only the DS-260 workflow uses these; the generic status dropdown never offers them for other forms

# (category_key, category_label, [field_type, ...]) — drives the field-library
# sidebar in the builder; app/forms_engine.py carries the per-type metadata.
FIELD_CATEGORIES = (
    ("contact", "Contact", (
        "first_name", "last_name", "full_name", "email", "phone",
        "address", "address_multiline", "company", "job_title",
    )),
    ("general", "General", (
        "short_answer", "long_answer", "number", "url", "file_upload", "record_list",
        "signature", "rating", "hidden",
    )),
    ("choices", "Choices", (
        "single_choice", "multi_choice", "dropdown", "multi_dropdown",
        "image_choice", "yes_no", "consent",
    )),
    ("dates", "Dates", ("date", "datetime", "time")),
    ("services", "Services", ("service_single", "service_multi", "appointment")),
    ("pricing", "Payments / Pricing", ("price_fixed", "price_custom", "donation", "product")),
    ("layout", "Layout / Content", (
        "heading_h1", "heading_h2", "heading_h3", "paragraph", "divider", "spacer", "image",
    )),
)

FIELD_TYPES = tuple(ft for _, _, types in FIELD_CATEGORIES for ft in types)

# Field types that never collect a value (pure layout/content) — excluded
# from required-ness, conditional targets-as-value-source, and submission storage.
CONTENT_ONLY_TYPES = ("heading_h1", "heading_h2", "heading_h3", "paragraph", "divider", "spacer", "image")

# Field types whose options come from FieldOption rows.
OPTION_BASED_TYPES = ("single_choice", "multi_choice", "dropdown", "multi_dropdown", "image_choice")

# Field types that accept more than one selected/entered value.
MULTI_VALUE_TYPES = ("multi_choice", "multi_dropdown", "service_multi")

CONDITION_OPERATORS = (
    "equals", "not_equals", "contains", "not_contains",
    "greater_than", "less_than", "is_empty", "is_not_empty",
    "selected", "not_selected",
)

RULE_ACTIONS = (
    "show_field", "hide_field", "require_field", "optional_field",
    "show_page", "skip_page", "goto_page", "end_form",
)


class Form(db.Model):
    __tablename__ = "forms"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    name_admin = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="draft", server_default="draft")
    form_type = db.Column(db.String(20), nullable=False, default="inquiry", server_default="inquiry")

    # Government forms change. A service intake records which official form and
    # edition it was built from, and its own version number, so historical
    # submissions stay tied to what was actually asked.
    source_form_name = db.Column(db.String(40))      # e.g. "I-90"
    source_edition = db.Column(db.String(40))         # e.g. "01/20/25"
    version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    published_at = db.Column(db.DateTime)
    previous_version_id = db.Column(db.Integer, db.ForeignKey("forms.id"))
    # Optional engine features for this intake, e.g. {"completeness_check": true}.
    features_json = db.Column(db.Text)

    title_en = db.Column(db.String(200), nullable=False)
    title_es = db.Column(db.String(200), nullable=False)
    description_en = db.Column(db.Text)
    description_es = db.Column(db.Text)
    submit_label_en = db.Column(db.String(80), nullable=False, default="Submit", server_default="Submit")
    submit_label_es = db.Column(db.String(80), nullable=False, default="Enviar", server_default="Enviar")

    # submission behavior
    success_action = db.Column(db.String(20), nullable=False, default="message", server_default="message")  # message | redirect
    success_message_en = db.Column(db.Text)
    success_message_es = db.Column(db.Text)
    redirect_url = db.Column(db.String(500))

    # notifications
    notify_admin_enabled = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    notify_admin_emails = db.Column(db.String(500))  # comma-separated
    notify_client_enabled = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    confirmation_subject_en = db.Column(db.String(200))
    confirmation_subject_es = db.Column(db.String(200))
    confirmation_body_en = db.Column(db.Text)
    confirmation_body_es = db.Column(db.Text)

    # styling — inherits OG site look unless overridden
    accent_color = db.Column(db.String(7))
    button_style = db.Column(db.String(20), nullable=False, default="solid", server_default="solid")  # solid | outline
    border_radius = db.Column(db.String(20), nullable=False, default="rounded", server_default="rounded")  # sharp | rounded | pill
    spacing = db.Column(db.String(20), nullable=False, default="comfortable", server_default="comfortable")  # compact | comfortable
    background_style = db.Column(db.String(20), nullable=False, default="card", server_default="card")  # card | transparent
    show_progress = db.Column(db.Boolean, nullable=False, default=True, server_default="1")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pages = db.relationship(
        "FormPage", backref="form", order_by="FormPage.sort_order", cascade="all, delete-orphan",
    )
    rules = db.relationship(
        "ConditionalRule", backref="form", order_by="ConditionalRule.sort_order", cascade="all, delete-orphan",
    )
    submissions = db.relationship(
        "FormSubmission", backref="form", order_by="FormSubmission.submitted_at.desc()", cascade="all, delete-orphan",
    )

    @property
    def is_service_intake(self):
        return self.form_type == "service_intake"

    @property
    def features(self):
        """Optional engine features of this intake (see app/intake_completeness.py)."""
        try:
            return json.loads(self.features_json) if self.features_json else {}
        except ValueError:
            return {}

    def title(self, lang):
        return self.title_es if lang == "es" and self.title_es else self.title_en

    def description(self, lang):
        return (self.description_es if lang == "es" else self.description_en) or ""

    def submit_label(self, lang):
        return self.submit_label_es if lang == "es" and self.submit_label_es else self.submit_label_en

    def success_message(self, lang):
        return (self.success_message_es if lang == "es" else self.success_message_en) or ""

    def confirmation_subject(self, lang):
        return (self.confirmation_subject_es if lang == "es" else self.confirmation_subject_en) or ""

    def confirmation_body(self, lang):
        return (self.confirmation_body_es if lang == "es" else self.confirmation_body_en) or ""

    @property
    def all_fields(self):
        return [f for page in self.pages for f in page.fields]

    @property
    def notify_admin_email_list(self):
        return [e.strip() for e in (self.notify_admin_emails or "").split(",") if e.strip()]


class FormPage(db.Model):
    __tablename__ = "form_pages"

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey("forms.id"), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    title_en = db.Column(db.String(200))
    title_es = db.Column(db.String(200))
    description_en = db.Column(db.Text)
    description_es = db.Column(db.Text)
    group_key = db.Column(db.String(40))  # review / completeness section this step belongs to
    context_key = db.Column(db.String(30))  # who this step is about (e.g. petitioner / beneficiary); see Form.features["contexts"]

    fields = db.relationship(
        "FormField", backref="page", order_by="FormField.sort_order", cascade="all, delete-orphan",
    )

    def title(self, lang):
        return _tok((self.title_es if lang == "es" else self.title_en) or "", lang)

    def description(self, lang):
        return _tok((self.description_es if lang == "es" else self.description_en) or "", lang)


class FormField(db.Model):
    __tablename__ = "form_fields"

    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer, db.ForeignKey("form_pages.id"), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    field_type = db.Column(db.String(30), nullable=False, default="short_answer")
    internal_name = db.Column(db.String(100), nullable=False)  # stable key, unique per form

    # Text, not a bounded VARCHAR: most labels are short, but several official
    # source forms (DS-260 Security & Background, I-751/I-485 certification
    # checkboxes) use the full verbatim question/attestation text as the
    # field's label -- confirmed up to 516 chars during the PostgreSQL
    # VARCHAR(300) audit, 2026-09-23 (see migration 363aeea03c7f).
    label_en = db.Column(db.Text)
    label_es = db.Column(db.Text)
    placeholder_en = db.Column(db.String(300))
    placeholder_es = db.Column(db.String(300))
    help_text_en = db.Column(db.Text)
    help_text_es = db.Column(db.Text)
    validation_message_en = db.Column(db.String(300))
    validation_message_es = db.Column(db.String(300))

    required = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    default_value = db.Column(db.String(500))
    width = db.Column(db.String(10), nullable=False, default="full", server_default="full")  # full | half | third

    min_value = db.Column(db.Float)
    max_value = db.Column(db.Float)
    min_length = db.Column(db.Integer)
    max_length = db.Column(db.Integer)

    allowed_file_types = db.Column(db.String(200))  # comma-separated extensions, no dots
    max_file_size_mb = db.Column(db.Integer, default=10, server_default="10")
    max_files = db.Column(db.Integer, default=1, server_default="1")

    content_en = db.Column(db.Text)  # heading/paragraph text, consent label rich text
    content_es = db.Column(db.Text)
    image_filename = db.Column(db.String(255))  # "image" layout field

    price_amount = db.Column(db.Float)
    price_currency = db.Column(db.String(10), default="USD", server_default="USD")

    service_source = db.Column(db.String(20), default="og_services", server_default="og_services")  # og_services | custom

    admin_notes = db.Column(db.Text)

    # Smart-intake support
    # Text, not a bounded VARCHAR: usually a short "Part 1, Item 3.a"-style
    # reference, but DS-260's Security & Background section instead uses the
    # full verbatim question text (prefixed with its section name) as the
    # traceability reference, since that source has no short Part/Item
    # citation scheme -- confirmed up to 302 chars during the PostgreSQL
    # VARCHAR(120) audit, 2026-09-23 (see migration 363aeea03c7f).
    source_ref = db.Column(db.Text)    # admin-only traceability, e.g. "Part 1, Item 3.a"
    source_note = db.Column(db.Text)          # admin-only mapping notes
    source_form = db.Column(db.String(20))    # form `source_ref` belongs to when it is not the intake's own (e.g. "I-130A")
    source_edition = db.Column(db.String(20))
    source_extra_json = db.Column(db.Text)    # more official-form mappings for the SAME answer: [{"form","edition","ref"}]
    is_sensitive = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    pattern = db.Column(db.String(200))       # server-side regex the value must fully match
    date_rule = db.Column(db.String(10))      # past | future
    help_detail_en = db.Column(db.Text)       # longer "Need help?" explanation
    help_detail_es = db.Column(db.Text)
    config_json = db.Column(db.Text)          # settings for record/timeline field types (see app/intake_records.py)
    help_where_en = db.Column(db.Text)        # "Where can I find this?" — where the customer can look the answer up
    help_where_es = db.Column(db.Text)

    options = db.relationship(
        "FieldOption", backref="field", order_by="FieldOption.sort_order", cascade="all, delete-orphan",
    )

    def label(self, lang):
        return _tok((self.label_es if lang == "es" else self.label_en) or "", lang)

    def placeholder(self, lang):
        return _tok((self.placeholder_es if lang == "es" else self.placeholder_en) or "", lang)

    def help_text(self, lang):
        return _tok((self.help_text_es if lang == "es" else self.help_text_en) or "", lang)

    def help_detail(self, lang):
        return _tok((self.help_detail_es if lang == "es" else self.help_detail_en) or "", lang)

    def help_where(self, lang):
        return _tok((self.help_where_es if lang == "es" else self.help_where_en) or "", lang)

    def validation_message(self, lang):
        return (self.validation_message_es if lang == "es" else self.validation_message_en) or ""

    def content(self, lang):
        return _tok((self.content_es if lang == "es" else self.content_en) or "", lang, escape=True)

    def input_name(self):
        return f"field_{self.id}"

    def sources(self, form=None):
        """Every official-form mapping of this one answer: [{"form","edition","ref"}].
        The first is the primary (`source_ref`, the intake's own form unless `source_form`
        says otherwise); `source_extra_json` adds forms that reuse the same answer."""
        form = form or (self.page.form if self.page else None)
        out = []
        if self.source_ref:
            out.append({"form": self.source_form or (form.source_form_name if form else None),
                        "edition": self.source_edition or (form.source_edition if form else None), "ref": self.source_ref})
        try:
            extra = json.loads(self.source_extra_json) if self.source_extra_json else []
        except ValueError:
            extra = []
        out += [x for x in extra if isinstance(x, dict) and x.get("ref")]
        return out

    @property
    def default(self):
        """The starting value shown for this field. "@biz:NAME" resolves to a constant in
        app/business_info.py, so business details are configured in one place."""
        raw = self.default_value
        if raw and raw.startswith("@biz:"):
            from app import business_info

            return str(getattr(business_info, raw[5:], "") or "")
        return raw

    @property
    def is_content_only(self):
        return self.field_type in CONTENT_ONLY_TYPES

    @property
    def is_multi_value(self):
        return self.field_type in MULTI_VALUE_TYPES

    @property
    def allowed_extensions(self):
        return [e.strip().lower() for e in (self.allowed_file_types or "").split(",") if e.strip()]

    @property
    def accept_attr(self):
        return ",".join(f".{ext}" for ext in self.allowed_extensions)


class FieldOption(db.Model):
    __tablename__ = "form_field_options"

    id = db.Column(db.Integer, primary_key=True)
    field_id = db.Column(db.Integer, db.ForeignKey("form_fields.id"), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    value = db.Column(db.String(100), nullable=False)  # stable internal value, shared across EN/ES
    # Text, not a bounded VARCHAR: most options are short ("Yes"/"No"), but
    # several forms use a long certification/attestation sentence as a
    # single checkbox option's label -- confirmed up to 673 chars during the
    # PostgreSQL VARCHAR(200) audit, 2026-09-23 (see migration 363aeea03c7f).
    label_en = db.Column(db.Text, nullable=False)
    label_es = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(255))

    def label(self, lang):
        return self.label_es if lang == "es" and self.label_es else self.label_en


class ConditionalRule(db.Model):
    __tablename__ = "form_conditional_rules"

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey("forms.id"), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    match_type = db.Column(db.String(10), nullable=False, default="all", server_default="all")  # all | any
    action = db.Column(db.String(20), nullable=False)
    target_field_id = db.Column(db.Integer, db.ForeignKey("form_fields.id"))
    target_page_id = db.Column(db.Integer, db.ForeignKey("form_pages.id"))

    target_field = db.relationship("FormField", foreign_keys=[target_field_id])
    target_page = db.relationship("FormPage", foreign_keys=[target_page_id])
    conditions = db.relationship(
        "RuleCondition", backref="rule", order_by="RuleCondition.id", cascade="all, delete-orphan",
    )


class RuleCondition(db.Model):
    __tablename__ = "form_rule_conditions"

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("form_conditional_rules.id"), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey("form_fields.id"), nullable=False)
    operator = db.Column(db.String(20), nullable=False, default="equals", server_default="equals")
    value = db.Column(db.String(300))

    field = db.relationship("FormField", foreign_keys=[field_id])


class FormSubmission(db.Model):
    __tablename__ = "form_submissions"

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey("forms.id"), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)  # "OGF-000123", shown to admins
    resume_token = db.Column(db.String(64), unique=True, nullable=False)  # carries an in-progress multi-page submission between page POSTs; also the future "save & resume" link token — never shown in admin UI as the public identifier
    is_complete = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    language = db.Column(db.String(2), nullable=False, default="en")
    status = db.Column(db.String(20), nullable=False, default="new", server_default="new")

    display_name = db.Column(db.String(200))
    display_email = db.Column(db.String(255))
    display_phone = db.Column(db.String(50))

    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Service-intake ownership: the signed-in customer who started it, and which
    # service it was started from. Both stay empty for anonymous inquiries.
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"))
    current_page = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), index=True)  # the customer's case this application belongs to (see models/cases.py)

    form_version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    source_edition_snapshot = db.Column(db.String(40))
    snapshot_json = db.Column(db.Text)  # frozen answers at submission (see app/intake_engine.py)

    # Reopen-for-editing: the SAME submission is unlocked by staff and later resubmitted.
    # `submitted_at` always stays the ORIGINAL submission time.
    reopened_at = db.Column(db.DateTime)
    reopen_message = db.Column(db.Text)  # optional note from OG, shown to the customer
    resubmitted_at = db.Column(db.DateTime)
    reopen_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    student = db.relationship("Student", foreign_keys=[student_id])
    service = db.relationship("Service", foreign_keys=[service_id])

    values = db.relationship(
        "SubmissionValue", backref="submission", order_by="SubmissionValue.id", cascade="all, delete-orphan",
    )
    files = db.relationship(
        "SubmissionFile", backref="submission", cascade="all, delete-orphan",
    )
    notes = db.relationship(
        "SubmissionNote", backref="submission", order_by="SubmissionNote.created_at", cascade="all, delete-orphan",
    )


class SubmissionRevision(db.Model):
    """One reopen -> resubmit cycle: when it was reopened/resubmitted and which answers
    changed in between (a lightweight change log, not document version control)."""

    __tablename__ = "submission_revisions"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"), nullable=False)
    reopened_at = db.Column(db.DateTime)
    resubmitted_at = db.Column(db.DateTime)
    changes_json = db.Column(db.Text)  # [{"label", "before", "after", "ref"}]
    submission = db.relationship("FormSubmission", backref=db.backref("revisions", order_by="SubmissionRevision.id", cascade="all, delete-orphan"))


class SubmissionValue(db.Model):
    __tablename__ = "form_submission_values"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey("form_fields.id"))
    field_label_snapshot = db.Column(db.String(300), nullable=False)
    field_internal_name = db.Column(db.String(100), nullable=False)
    field_type_snapshot = db.Column(db.String(30), nullable=False)
    value_text = db.Column(db.Text)  # plain text, or JSON array string for multi-value fields

    field = db.relationship("FormField")


class SubmissionFile(db.Model):
    __tablename__ = "form_submission_files"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey("form_fields.id"))
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    size_bytes = db.Column(db.Integer, default=0)
    mime_type = db.Column(db.String(80))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    field = db.relationship("FormField")


class SubmissionNote(db.Model):
    __tablename__ = "form_submission_notes"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("form_submissions.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    author_name = db.Column(db.String(120))
    # Internal notes are never shown to the customer. A note the admin writes as a
    # request for more information is flagged customer-visible on purpose.
    is_customer_visible = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
