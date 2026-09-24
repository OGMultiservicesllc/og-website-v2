import json
from datetime import datetime

from app.extensions import db


class Inquiry(db.Model):
    __tablename__ = "inquiries"

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(30), nullable=False, default="contact")  # contact | translation_quote | chat | custom_form
    language = db.Column(db.String(2), nullable=False, default="en")

    # Nullable because custom_form submissions may not ask for a name/email in
    # this exact shape — their real content lives in extra_data instead.
    name = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50))
    message = db.Column(db.Text)

    # translation_quote-specific
    target_language = db.Column(db.String(100))
    file_filename = db.Column(db.String(255))

    # custom_form-specific
    form_id = db.Column(db.Integer, db.ForeignKey("custom_forms.id"), nullable=True)
    extra_data = db.Column(db.Text)  # JSON-encoded {field label: submitted value}

    status = db.Column(db.String(20), nullable=False, default="new")  # new | contacted | closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    form = db.relationship("CustomForm")

    def extra_items(self):
        if not self.extra_data:
            return []
        try:
            data = json.loads(self.extra_data)
        except ValueError:
            return []
        return list(data.items())
