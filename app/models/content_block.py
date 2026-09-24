from datetime import datetime

from app.extensions import db


class PageBlock(db.Model):
    """A small, admin-editable chunk of bilingual text tied to a fixed key,
    used to make specific pieces of otherwise hand-built pages (like the
    Translations page) editable without turning the whole page into a
    generic CMS Page and losing its custom layout."""

    __tablename__ = "page_blocks"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    content_en = db.Column(db.Text)
    content_es = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
