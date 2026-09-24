"""Structured, admin-editable public-site content: the Media Library, service
categories (Immigration, Taxes & ITIN, ...) and the individual services under
them (I-90, I-130, ITIN, ...).

Replaces two things that used to be developer-shaped: hand-built "flagship" pages
whose text was patched through a key/value table, and services that only existed as
Python data. The visitor-facing structure (Category -> Service) is now the same
structure the administrator edits.

Bilingual convention is unchanged: every visitor-facing string is an `_en`/`_es`
column pair with a lang-aware accessor.
"""

from datetime import datetime

from app.extensions import db

MEDIA_FOCUS = ("center", "top", "bottom", "left", "right")

# How a page/service's primary "Get Started" button behaves.
#   default  - the category/site default (contact page, or intake when configured)
#   contact  - the contact page
#   whatsapp - opens WhatsApp
#   intake   - starts/resumes the assigned smart-intake form (services only)
#   url      - a custom internal/external URL
CTA_MODES = ("default", "contact", "whatsapp", "intake", "url")

CONTENT_KINDS = ("when_needed", "included", "faq", "feature", "step", "checklist")

# Image slots the design system defines, with the ratio the layout crops to.
IMAGE_SLOTS = (
    ("hero", "Hero Image", "16:9"),
    ("hero_mobile", "Mobile Hero Image (optional)", "4:3"),
    ("card", "Card Image", "4:3"),
    ("overview", "Overview Image", "3:2"),
    ("social", "Social / SEO Image", "1200×630"),
)


def _pick(lang, es, en):
    return es if lang == "es" and es else en


class MediaAsset(db.Model):
    __tablename__ = "media_assets"

    id = db.Column(db.Integer, primary_key=True)
    stored_path = db.Column(db.String(255), unique=True, nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(200))
    alt_en = db.Column(db.String(300))
    alt_es = db.Column(db.String(300))
    tag = db.Column(db.String(60))
    mime_type = db.Column(db.String(60))
    size_bytes = db.Column(db.Integer)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def display_title(self):
        return self.title or self.original_filename

    def alt(self, lang):
        return _pick(lang, self.alt_es, self.alt_en) or self.display_title


class _ImageSlotsMixin:
    """Focal position for the two crop-sensitive slots (the rest inherit)."""

    hero_focus = db.Column(db.String(10), nullable=False, default="center", server_default="center")
    card_focus = db.Column(db.String(10), nullable=False, default="center", server_default="center")


class ServiceCategory(_ImageSlotsMixin, db.Model):
    __tablename__ = "service_categories"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    # Flask endpoints this category owns. The URLs themselves are unchanged from
    # the original site (SEO), so they are looked up rather than typed.
    endpoint = db.Column(db.String(80), nullable=False)
    subpage_endpoint = db.Column(db.String(80))

    icon = db.Column(db.String(30), nullable=False, default="documents")
    is_published = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    show_in_nav = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    is_featured = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    title_en = db.Column(db.String(200), nullable=False)
    title_es = db.Column(db.String(200), nullable=False)
    short_en = db.Column(db.String(300))
    short_es = db.Column(db.String(300))

    hero_badge_en = db.Column(db.String(120))
    hero_badge_es = db.Column(db.String(120))
    hero_title_en = db.Column(db.String(200))
    hero_title_es = db.Column(db.String(200))
    hero_text_en = db.Column(db.Text)
    hero_text_es = db.Column(db.Text)

    intro_title_en = db.Column(db.String(200))
    intro_title_es = db.Column(db.String(200))
    intro_body_en = db.Column(db.Text)
    intro_body_es = db.Column(db.Text)
    contact_note_en = db.Column(db.Text)
    contact_note_es = db.Column(db.Text)

    info_title_en = db.Column(db.String(200))
    info_title_es = db.Column(db.String(200))
    info_body_en = db.Column(db.Text)
    info_body_es = db.Column(db.Text)
    content_en = db.Column(db.Text)
    content_es = db.Column(db.Text)
    disclaimer_en = db.Column(db.Text)
    disclaimer_es = db.Column(db.Text)

    checklist_title_en = db.Column(db.String(200))
    checklist_title_es = db.Column(db.String(200))
    features_title_en = db.Column(db.String(200))
    features_title_es = db.Column(db.String(200))
    included_title_en = db.Column(db.String(200))
    included_title_es = db.Column(db.String(200))

    final_cta_title_en = db.Column(db.String(200))
    final_cta_title_es = db.Column(db.String(200))
    final_cta_body_en = db.Column(db.Text)
    final_cta_body_es = db.Column(db.Text)

    cta_label_en = db.Column(db.String(120))
    cta_label_es = db.Column(db.String(120))
    cta_mode = db.Column(db.String(20), nullable=False, default="default", server_default="default")
    cta_url = db.Column(db.String(500))
    whatsapp_enabled = db.Column(db.Boolean, nullable=False, default=True, server_default="1")

    seo_title_en = db.Column(db.String(200))
    seo_title_es = db.Column(db.String(200))
    seo_description_en = db.Column(db.String(300))
    seo_description_es = db.Column(db.String(300))

    hero_image_id = db.Column(db.Integer, db.ForeignKey("media_assets.id"))
    hero_mobile_image_id = db.Column(db.Integer, db.ForeignKey("media_assets.id"))
    card_image_id = db.Column(db.Integer, db.ForeignKey("media_assets.id"))
    overview_image_id = db.Column(db.Integer, db.ForeignKey("media_assets.id"))
    social_image_id = db.Column(db.Integer, db.ForeignKey("media_assets.id"))

    hero_image = db.relationship("MediaAsset", foreign_keys=[hero_image_id])
    hero_mobile_image = db.relationship("MediaAsset", foreign_keys=[hero_mobile_image_id])
    card_image = db.relationship("MediaAsset", foreign_keys=[card_image_id])
    overview_image = db.relationship("MediaAsset", foreign_keys=[overview_image_id])
    social_image = db.relationship("MediaAsset", foreign_keys=[social_image_id])

    services = db.relationship(
        "Service", backref="category", cascade="all, delete-orphan", order_by="Service.sort_order, Service.id"
    )
    items = db.relationship(
        "ServiceContentItem",
        primaryjoin="ServiceCategory.id == ServiceContentItem.category_id",
        cascade="all, delete-orphan",
        order_by="ServiceContentItem.sort_order, ServiceContentItem.id"
    )

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def title(self, lang):
        return _pick(lang, self.title_es, self.title_en)

    def short(self, lang):
        return _pick(lang, self.short_es, self.short_en) or ""

    def hero_title(self, lang):
        return _pick(lang, self.hero_title_es, self.hero_title_en) or self.title(lang)

    def hero_text(self, lang):
        return _pick(lang, self.hero_text_es, self.hero_text_en) or ""

    def hero_badge(self, lang):
        return _pick(lang, self.hero_badge_es, self.hero_badge_en) or ""

    def intro_title(self, lang):
        return _pick(lang, self.intro_title_es, self.intro_title_en) or ""

    def intro_body(self, lang):
        return _pick(lang, self.intro_body_es, self.intro_body_en) or ""

    def contact_note(self, lang):
        return _pick(lang, self.contact_note_es, self.contact_note_en) or ""

    def info_title(self, lang):
        return _pick(lang, self.info_title_es, self.info_title_en) or ""

    def info_body(self, lang):
        return _pick(lang, self.info_body_es, self.info_body_en) or ""

    def content(self, lang):
        return _pick(lang, self.content_es, self.content_en) or ""

    def disclaimer(self, lang):
        return _pick(lang, self.disclaimer_es, self.disclaimer_en) or ""

    def checklist_title(self, lang):
        return _pick(lang, self.checklist_title_es, self.checklist_title_en) or ""

    def features_title(self, lang):
        return _pick(lang, self.features_title_es, self.features_title_en) or ""

    def included_title(self, lang):
        return _pick(lang, self.included_title_es, self.included_title_en) or ""

    def final_cta_title(self, lang):
        return _pick(lang, self.final_cta_title_es, self.final_cta_title_en) or ""

    def final_cta_body(self, lang):
        return _pick(lang, self.final_cta_body_es, self.final_cta_body_en) or ""

    def cta_label(self, lang):
        return _pick(lang, self.cta_label_es, self.cta_label_en) or ""

    def seo_title(self, lang):
        return _pick(lang, self.seo_title_es, self.seo_title_en) or self.title(lang)

    def seo_description(self, lang):
        return _pick(lang, self.seo_description_es, self.seo_description_en) or self.hero_text(lang) or self.short(lang)

    def items_of(self, kind):
        return [i for i in self.items if i.kind == kind]

    @property
    def published_services(self):
        return [s for s in self.services if s.is_published]


class Service(_ImageSlotsMixin, db.Model):
    __tablename__ = "services"
    __table_args__ = (db.UniqueConstraint("category_id", "slug", name="uq_service_category_slug"),)

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("service_categories.id"), nullable=False)
    slug = db.Column(db.String(120), nullable=False)
    admin_name = db.Column(db.String(200))

    icon = db.Column(db.String(30), nullable=False, default="documents")
    is_published = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    is_featured = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    badge_en = db.Column(db.String(40))
    badge_es = db.Column(db.String(40))

    title_en = db.Column(db.String(200), nullable=False)
    title_es = db.Column(db.String(200), nullable=False)
    short_en = db.Column(db.String(300))
    short_es = db.Column(db.String(300))
    hero_text_en = db.Column(db.Text)
    hero_text_es = db.Column(db.Text)

    content_title_en = db.Column(db.String(200))
    content_title_es = db.Column(db.String(200))
    content_en = db.Column(db.Text)
    content_es = db.Column(db.Text)
    disclaimer_en = db.Column(db.Text)
    disclaimer_es = db.Column(db.Text)

    cta_label_en = db.Column(db.String(120))
    cta_label_es = db.Column(db.String(120))
    cta_mode = db.Column(db.String(20), nullable=False, default="default", server_default="default")
    cta_url = db.Column(db.String(500))
    whatsapp_enabled = db.Column(db.Boolean, nullable=False, default=True, server_default="1")

    # Smart intake: which Form (from the Forms builder) this service starts.
    requires_intake = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    form_id = db.Column(db.Integer, db.ForeignKey("forms.id"))
    requires_account = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    # Name of the intake this service is expected to get (e.g. "N-400 Client Intake")
    # before its form exists; shown in Admin as NOT YET CONFIGURED.
    intake_label = db.Column(db.String(120))

    # Where the service is offered (see app/service_areas.py for the business rules).
    nj_in_person = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    tx_in_person = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    remote_nationwide = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    scope_note_en = db.Column(db.Text)
    scope_note_es = db.Column(db.Text)

    seo_title_en = db.Column(db.String(200))
    seo_title_es = db.Column(db.String(200))
    seo_description_en = db.Column(db.String(300))
    seo_description_es = db.Column(db.String(300))

    hero_image_id = db.Column(db.Integer, db.ForeignKey("media_assets.id"))
    hero_mobile_image_id = db.Column(db.Integer, db.ForeignKey("media_assets.id"))
    card_image_id = db.Column(db.Integer, db.ForeignKey("media_assets.id"))
    overview_image_id = db.Column(db.Integer, db.ForeignKey("media_assets.id"))
    social_image_id = db.Column(db.Integer, db.ForeignKey("media_assets.id"))

    hero_image = db.relationship("MediaAsset", foreign_keys=[hero_image_id])
    hero_mobile_image = db.relationship("MediaAsset", foreign_keys=[hero_mobile_image_id])
    card_image = db.relationship("MediaAsset", foreign_keys=[card_image_id])
    overview_image = db.relationship("MediaAsset", foreign_keys=[overview_image_id])
    social_image = db.relationship("MediaAsset", foreign_keys=[social_image_id])
    form = db.relationship("Form", foreign_keys=[form_id])

    items = db.relationship(
        "ServiceContentItem",
        primaryjoin="Service.id == ServiceContentItem.service_id",
        cascade="all, delete-orphan",
        order_by="ServiceContentItem.sort_order, ServiceContentItem.id"
    )
    related = db.relationship(
        "Service",
        secondary="service_related",
        primaryjoin="Service.id == service_related.c.service_id",
        secondaryjoin="Service.id == service_related.c.related_service_id",
    )

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def title(self, lang):
        return _pick(lang, self.title_es, self.title_en)

    def short(self, lang):
        return _pick(lang, self.short_es, self.short_en) or ""

    def badge(self, lang):
        return _pick(lang, self.badge_es, self.badge_en) or ""

    def hero_text(self, lang):
        return _pick(lang, self.hero_text_es, self.hero_text_en) or self.short(lang)

    def content_title(self, lang):
        return _pick(lang, self.content_title_es, self.content_title_en) or ""

    def content(self, lang):
        return _pick(lang, self.content_es, self.content_en) or ""

    def disclaimer(self, lang):
        return _pick(lang, self.disclaimer_es, self.disclaimer_en) or ""

    def cta_label(self, lang):
        return _pick(lang, self.cta_label_es, self.cta_label_en) or ""

    def scope_note(self, lang):
        return _pick(lang, self.scope_note_es, self.scope_note_en) or ""

    def seo_title(self, lang):
        return _pick(lang, self.seo_title_es, self.seo_title_en) or self.title(lang)

    def seo_description(self, lang):
        return _pick(lang, self.seo_description_es, self.seo_description_en) or self.short(lang)

    def items_of(self, kind):
        return [i for i in self.items if i.kind == kind]

    @property
    def has_intake(self):
        return bool(self.requires_intake and self.form_id and self.form and self.form.status == "published")

    @property
    def intake_state(self):
        """live | waiting (form exists, not published) | not_configured (an intake is
        planned for this service but no form has been built) | none."""
        if self.has_intake:
            return "live"
        if self.requires_intake and self.form_id:
            return "waiting"
        if self.intake_label:
            return "not_configured"
        return "none"


service_related = db.Table(
    "service_related",
    db.Column("service_id", db.Integer, db.ForeignKey("services.id"), primary_key=True),
    db.Column("related_service_id", db.Integer, db.ForeignKey("services.id"), primary_key=True),
)


class ServiceContentItem(db.Model):
    """One repeating bilingual row belonging to a service or a category: an FAQ
    entry, a "what's included" bullet, a "when you need this" bullet, a feature
    card, a numbered step or a checklist line. `title` is the question/bullet,
    `body` the answer/description (unused for plain bullets)."""

    __tablename__ = "service_content_items"
    __table_args__ = (
        db.CheckConstraint(
            "(service_id IS NOT NULL AND category_id IS NULL) OR (service_id IS NULL AND category_id IS NOT NULL)",
            name="ck_content_item_one_owner",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"))
    category_id = db.Column(db.Integer, db.ForeignKey("service_categories.id"))
    kind = db.Column(db.String(20), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    title_en = db.Column(db.Text, nullable=False)
    title_es = db.Column(db.Text, nullable=False)
    body_en = db.Column(db.Text)
    body_es = db.Column(db.Text)

    def title(self, lang):
        return _pick(lang, self.title_es, self.title_en)

    def body(self, lang):
        return _pick(lang, self.body_es, self.body_en) or ""


NAV_SYSTEM_KEYS = ("home", "services", "about", "academy", "blog", "contact")


class NavItem(db.Model):
    """One entry of the public header menu. `system` items point at fixed routes
    (they can be hidden, renamed and reordered but never deleted, so a critical page
    can't be orphaned); `page` items point at a Custom Page; `url` items are free
    links. The Services dropdown's entries come from the service categories."""

    __tablename__ = "nav_items"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False, default="system")  # system | page | url
    system_key = db.Column(db.String(20))
    page_id = db.Column(db.Integer, db.ForeignKey("pages.id"))
    url = db.Column(db.String(500))
    label_en = db.Column(db.String(80))
    label_es = db.Column(db.String(80))
    is_visible = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    page = db.relationship("Page")

    def label(self, lang):
        return _pick(lang, self.label_es, self.label_en) or ""
