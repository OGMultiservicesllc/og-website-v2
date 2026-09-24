from datetime import datetime

from app.extensions import db

FIELD_TYPES = ["text", "email", "tel", "textarea", "select", "checkbox"]


class CustomForm(db.Model):
    __tablename__ = "custom_forms"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    name_admin = db.Column(db.String(200), nullable=False)  # internal label, admin-only

    title_en = db.Column(db.String(200), nullable=False)
    title_es = db.Column(db.String(200), nullable=False)
    intro_en = db.Column(db.Text)
    intro_es = db.Column(db.Text)
    submit_label_en = db.Column(db.String(80), nullable=False, default="Send")
    submit_label_es = db.Column(db.String(80), nullable=False, default="Enviar")

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    fields = db.relationship(
        "CustomFormField", backref="form", order_by="CustomFormField.sort_order", cascade="all, delete-orphan"
    )

    def title(self, lang):
        return self.title_es if lang == "es" and self.title_es else self.title_en

    def intro(self, lang):
        return (self.intro_es if lang == "es" else self.intro_en) or ""

    def submit_label(self, lang):
        return self.submit_label_es if lang == "es" and self.submit_label_es else self.submit_label_en


class CustomFormField(db.Model):
    __tablename__ = "custom_form_fields"

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey("custom_forms.id"), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    field_type = db.Column(db.String(20), nullable=False, default="text")
    label_en = db.Column(db.String(200), nullable=False)
    label_es = db.Column(db.String(200), nullable=False)
    placeholder_en = db.Column(db.String(200))
    placeholder_es = db.Column(db.String(200))
    options_en = db.Column(db.Text)  # one option per line, "select" fields only
    options_es = db.Column(db.Text)
    required = db.Column(db.Boolean, nullable=False, default=True)

    def label(self, lang):
        return self.label_es if lang == "es" and self.label_es else self.label_en

    def placeholder(self, lang):
        return (self.placeholder_es if lang == "es" else self.placeholder_en) or ""

    def options(self, lang):
        raw = (self.options_es if lang == "es" else self.options_en) or ""
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def input_name(self):
        return f"field_{self.id}"
