"""Admin Notification Center (2026-09-24) — a single, reusable event/notification system every module
routes real activity through, instead of ad-hoc per-module alerts. See app/notifications.py for the
service layer (notify(), settings, dedup) that writes/reads these two tables.

`AdminNotification.read_at` is a single GLOBAL flag, not per-admin-user — every `AdminUser` in this app
already sees the same data everywhere else (no roles/permissions split), so a per-admin read-state table
would be new, unrequested complexity.

`dedupe_key` is checked BEFORE a row is even created (see `notifications.notify()`), so a retried Square
webhook or a duplicate call site can never create a second row — this is the same idempotency pattern
already proven for `EmailLog.dedupe_key` in the Transactional Email system.
"""
from datetime import datetime

from app.extensions import db

# event_key -> (label, group_key, default_admin_enabled, default_email_enabled)
# Defaults match the table the user specified verbatim in the task brief. Admin can change every one of
# these from Admin -> Settings -> Notifications; this is only the INITIAL seed (app/notifications.py
# ensure_seed(), same idempotent-seed convention as every other seeder in this project).
NOTIFICATION_EVENTS = {
    "new_account": ("New customer account created", "customers", True, False),
    "imported_account_activated": ("Imported Account Activated", "customers", True, True),
    "case_submitted": ("New case / intake submitted", "cases", True, True),
    "case_needs_review": ("Case requires OG review", "cases", True, True),
    "documents_uploaded": ("Client uploads documents", "documents", True, True),
    "payment_received": ("Payment received", "payments", True, True),
    "payment_pending": ("Manual payment awaiting confirmation", "payments", True, True),
    "payment_error": ("Payment failed / error", "payments", True, True),
    "course_purchased": ("Course purchased", "academy", True, True),
}

NOTIFICATION_GROUPS = ["customers", "cases", "documents", "payments", "academy", "system"]


class NotificationSetting(db.Model):
    """One row per event_key (seeded from NOTIFICATION_EVENTS) — Admin -> Settings -> Notifications edits
    these two booleans; the recipient email lives on SiteSettings (`notification_recipient_email`), the
    existing Settings system, per the task's explicit instruction not to invent a new settings table for it."""

    __tablename__ = "notification_settings"

    id = db.Column(db.Integer, primary_key=True)
    event_key = db.Column(db.String(50), unique=True, nullable=False)
    admin_enabled = db.Column(db.Boolean, nullable=False, default=True)
    email_enabled = db.Column(db.Boolean, nullable=False, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AdminNotification(db.Model):
    """One row per notification. Always created (even when the Admin-bell toggle is off) so a
    `dedupe_key` match can still block a later duplicate — see `notifications.notify()`. When the
    Admin-bell toggle for that event was off at creation time, `admin_visible=False` and `read_at` is
    pre-filled so it never surfaces in the bell/Notification Center, while the row still exists for
    audit and for future dedup checks."""

    __tablename__ = "admin_notifications"

    id = db.Column(db.Integer, primary_key=True)
    event_key = db.Column(db.String(50), nullable=False, index=True)
    group_key = db.Column(db.String(30), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    body = db.Column(db.String(500))
    entity_type = db.Column(db.String(40))
    entity_id = db.Column(db.Integer)
    link_url = db.Column(db.String(500))
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    dedupe_key = db.Column(db.String(150), index=True)
    admin_visible = db.Column(db.Boolean, nullable=False, default=True)
    read_at = db.Column(db.DateTime)
    email_attempted = db.Column(db.Boolean, nullable=False, default=False)
    email_status = db.Column(db.String(20))  # None (not applicable) | "sent" | "failed" | "skipped"
    email_recipient = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    case = db.relationship("Case")
    customer = db.relationship("Student")

    @property
    def is_unread(self):
        return self.read_at is None
