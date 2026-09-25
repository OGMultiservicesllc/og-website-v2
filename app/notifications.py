"""OG Admin Notification Center — the single, reusable event/notification service every module routes
through (task: "OG ADMIN NOTIFICATION CENTER + EMAIL ALERTS", 2026-09-24). Models in
`app/models/notifications.py`.

`notify(event_key, ...)` is the ONE function every hook site in the app calls — never raises (same
contract as `app.email_service.send_transactional_email`, which it calls internally for the email half).
It:
  1. Short-circuits on a `dedupe_key` match (idempotency for Square webhook retries, duplicate call
     sites, etc.) — checked BEFORE any row is created, so a retried event never creates a second bell
     entry or sends a second email.
  2. Always creates an `AdminNotification` row for audit, even when the Admin-bell toggle for that event
     is off (pre-marked read + `admin_visible=False` so it never surfaces in the UI).
  3. Sends the admin email (reusing `send_transactional_email`, `student=None`, `recipient_email=` the
     configured recipient) only when the Email toggle for that event is on.
"""
import logging

from app.extensions import db
from app.models import AdminNotification, NOTIFICATION_EVENTS, NotificationSetting, SiteSettings

logger = logging.getLogger("og_notifications")


def safe_url(endpoint, **kwargs):
    """`url_for`, but never raises — every notify() call site builds its `link_url` with this instead of
    a bare `url_for`, so a hook ever invoked outside an HTTP request (a future CLI/cron path) degrades to
    "no direct link" instead of crashing the caller's own transaction."""
    try:
        from flask import url_for

        return url_for(endpoint, **kwargs)
    except Exception:  # noqa: BLE001
        return None


def ensure_seed():
    """Idempotent — same pattern as every other seeder in this project (app/seed_content.py). Only
    INSERTS rows that don't exist yet; never overwrites an Admin-edited setting on a later app start."""
    existing = {s.event_key for s in NotificationSetting.query.all()}
    for key, (_label, _group, admin_default, email_default) in NOTIFICATION_EVENTS.items():
        if key in existing:
            continue
        db.session.add(NotificationSetting(event_key=key, admin_enabled=admin_default, email_enabled=email_default))
    db.session.commit()


def get_setting(event_key):
    return NotificationSetting.query.filter_by(event_key=event_key).first()


def recipient_email():
    settings = SiteSettings.get()
    email = (settings.notification_recipient_email or "").strip()
    if email:
        return email
    from app import business_info

    return business_info.EMAIL


def _existing_for_dedupe(dedupe_key):
    if not dedupe_key:
        return None
    return AdminNotification.query.filter_by(dedupe_key=dedupe_key).first()


def notify(event_key, *, title, body=None, entity_type=None, entity_id=None, link_url=None,
           case_id=None, customer_id=None, dedupe_key=None):
    """Never raises — a notification failure must never break the business transaction that triggered
    it (same contract this project already applies to every transactional-email call site)."""
    try:
        existing = _existing_for_dedupe(dedupe_key)
        if existing is not None:
            return existing

        if event_key not in NOTIFICATION_EVENTS:
            logger.warning("[notifications] unknown event_key %r", event_key)
            return None
        _label, group_key, _ad, _em = NOTIFICATION_EVENTS[event_key]
        setting = get_setting(event_key)
        admin_on = setting.admin_enabled if setting else True
        email_on = setting.email_enabled if setting else True

        n = AdminNotification(
            event_key=event_key, group_key=group_key, title=title[:300], body=(body or "")[:500] or None,
            entity_type=entity_type, entity_id=entity_id, link_url=link_url, case_id=case_id, customer_id=customer_id,
            dedupe_key=dedupe_key, admin_visible=bool(admin_on),
        )
        if not admin_on:
            from datetime import datetime

            n.read_at = datetime.utcnow()
        db.session.add(n)
        db.session.commit()

        if email_on:
            _send_email(n)
        return n
    except Exception:  # noqa: BLE001
        logger.exception("[notifications] notify(%r) failed", event_key)
        return None


def _send_email(notification):
    """Reuses the existing transactional-email seam entirely — no new SMTP code. `student=None` +
    `recipient_email=` is an explicitly supported call shape (see app/email_service.py)."""
    to_email = recipient_email()
    notification.email_attempted = True
    notification.email_recipient = to_email
    try:
        from app.email_render import EmailContent
        from app.email_service import send_transactional_email

        content = EmailContent(
            subject=notification.title,
            heading=notification.title,
            paragraphs=[p for p in [notification.body] if p],
            cta_label="View in Admin" if notification.link_url else None,
            cta_url=notification.link_url,
        )
        log = send_transactional_email(
            None, f"admin_{notification.event_key}", "en", content=content,
            recipient_email=to_email, recipient_name="OG Multiservices Admin",
            related_type=notification.entity_type, related_id=notification.entity_id,
            dedupe_key=(f"admin_email:{notification.dedupe_key}" if notification.dedupe_key else None),
        )
        notification.email_status = "sent" if (log and log.status == "sent") else "failed"
    except Exception:  # noqa: BLE001
        logger.exception("[notifications] admin email for %r failed to send", notification.event_key)
        notification.email_status = "failed"
    db.session.commit()


# ------------------------------------------------------------------ Notification Center queries (bell + full page)
def visible_query():
    return AdminNotification.query.filter_by(admin_visible=True)


def unread_count():
    return visible_query().filter(AdminNotification.read_at.is_(None)).count()


def recent(limit=8):
    return visible_query().order_by(AdminNotification.created_at.desc()).limit(limit).all()


def list_for_center(group=None, unread_only=False, limit=50):
    q = visible_query()
    if group:
        q = q.filter_by(group_key=group)
    if unread_only:
        q = q.filter(AdminNotification.read_at.is_(None))
    return q.order_by(AdminNotification.created_at.desc()).limit(limit).all()


def mark_read(notification_id):
    from datetime import datetime

    n = AdminNotification.query.get(notification_id)
    if n and n.read_at is None:
        n.read_at = datetime.utcnow()
        db.session.commit()
    return n


def mark_all_read():
    from datetime import datetime

    visible_query().filter(AdminNotification.read_at.is_(None)).update({"read_at": datetime.utcnow()}, synchronize_session=False)
    db.session.commit()


# ------------------------------------------------------------------ Needs Attention (shared with Dashboard — one
# set of queries so Dashboard and the Notification Center can never disagree, per the task's explicit requirement)
def needs_attention_counts():
    from app.models import Case, DocumentRequirement, MANUAL_METHODS, Payment

    open_cases_review = Case.query.filter(Case.status == "in_review").count()
    pending_manual_payments = Payment.query.filter(Payment.status == "pending", Payment.method.in_(MANUAL_METHODS)).count()
    documents_awaiting_review = DocumentRequirement.query.filter_by(status="uploaded").count()
    return {
        "cases_awaiting_review": open_cases_review,
        "pending_manual_payments": pending_manual_payments,
        "documents_awaiting_review": documents_awaiting_review,
    }
