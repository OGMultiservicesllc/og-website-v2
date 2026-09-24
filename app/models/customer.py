"""Customer-level records: the activity timeline and admin-only notes.

Activity events are structured (type + actor + entity + metadata) so they can be
filtered and reported on later; the human-readable sentence is rendered from the
structure (see app/activity.py), never stored. They record meaningful account and
workflow events only — no page views, clicks or field values.
"""

from datetime import datetime

from app.extensions import db

ACTOR_TYPES = ("customer", "admin", "system")


class ActivityEvent(db.Model):
    __tablename__ = "activity_events"
    __table_args__ = (db.Index("ix_activity_customer_created", "customer_id", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    actor_type = db.Column(db.String(10), nullable=False, default="customer")
    actor_id = db.Column(db.Integer)
    entity_type = db.Column(db.String(30))
    entity_id = db.Column(db.Integer)
    metadata_json = db.Column(db.Text)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), index=True)  # set for case-level events
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    customer = db.relationship("Student", backref=db.backref("activity_events", lazy="dynamic"))


class CustomerNote(db.Model):
    """An internal note about a customer. Never visible to the customer."""

    __tablename__ = "customer_notes"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    author_name = db.Column(db.String(120))
    author_admin_id = db.Column(db.Integer)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship("Student", backref=db.backref("internal_notes", lazy="dynamic", order_by="CustomerNote.created_at.desc()"))
