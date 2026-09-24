from app.extensions import db

BLOCK_TYPES = ["heading", "text", "image", "button", "divider", "form"]


class PageSection(db.Model):
    __tablename__ = "page_sections"

    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer, db.ForeignKey("pages.id"), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    block_type = db.Column(db.String(20), nullable=False, default="text")

    heading_en = db.Column(db.String(200))
    heading_es = db.Column(db.String(200))
    text_en = db.Column(db.Text)
    text_es = db.Column(db.Text)
    image_filename = db.Column(db.String(255))
    button_label_en = db.Column(db.String(150))
    button_label_es = db.Column(db.String(150))
    link_page_id = db.Column(db.Integer, db.ForeignKey("pages.id"), nullable=True)
    link_url = db.Column(db.String(500))
    custom_form_id = db.Column(db.Integer, db.ForeignKey("custom_forms.id"), nullable=True)

    page = db.relationship(
        "Page",
        foreign_keys=[page_id],
        backref=db.backref("sections", order_by="PageSection.sort_order", cascade="all, delete-orphan"),
    )
    link_page = db.relationship("Page", foreign_keys=[link_page_id])
    custom_form = db.relationship("CustomForm")

    def heading(self, lang):
        return (self.heading_es if lang == "es" else self.heading_en) or self.heading_en or ""

    def text(self, lang):
        return (self.text_es if lang == "es" and self.text_es else self.text_en) or ""

    def button_label(self, lang):
        return (self.button_label_es if lang == "es" and self.button_label_es else self.button_label_en) or ""
