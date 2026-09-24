from datetime import datetime

from app.extensions import db

# Fixed marketing sections a page can nest under in the site nav, in addition
# to (or instead of) nesting under another dynamic Page via parent_page_id.
NAV_SECTIONS = {
    "services": "Services",
    "translations": "Translations",
    "taxes_itin": "Taxes & ITIN",
    "academy": "OG Academy",
    "resources": "Resources",
}


class Page(db.Model):
    __tablename__ = "pages"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)

    title_en = db.Column(db.String(200), nullable=False)
    title_es = db.Column(db.String(200), nullable=False)
    content_en = db.Column(db.Text)
    content_es = db.Column(db.Text)

    seo_title_en = db.Column(db.String(200))
    seo_title_es = db.Column(db.String(200))
    seo_description_en = db.Column(db.String(300))
    seo_description_es = db.Column(db.String(300))

    # Nesting: either a parent Page, or a fixed marketing section, or neither
    # (a standalone top-level page). Never both.
    parent_page_id = db.Column(db.Integer, db.ForeignKey("pages.id"), nullable=True)
    parent_section = db.Column(db.String(30), nullable=True)  # key from NAV_SECTIONS

    show_in_menu = db.Column(db.Boolean, nullable=False, default=True)
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    children = db.relationship(
        "Page",
        backref=db.backref("parent_page", remote_side=[id]),
        order_by="Page.sort_order",
    )

    def title(self, lang):
        return self.title_es if lang == "es" and self.title_es else self.title_en

    def content(self, lang):
        return (self.content_es if lang == "es" else self.content_en) or ""

    def seo_title(self, lang):
        value = self.seo_title_es if lang == "es" else self.seo_title_en
        return value or self.title(lang)

    def seo_description(self, lang):
        return (self.seo_description_es if lang == "es" else self.seo_description_en) or ""
