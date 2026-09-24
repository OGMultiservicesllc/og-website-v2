"""Transactional email — the single seam every business event calls through (`send_transactional_email`).
Synchronous with a bounded SMTP timeout (see app/mailer.py) — the simplest reliable architecture for this
project's single-server Flask deployment, per the spec's explicit instruction not to introduce Redis/
Celery/etc. If volume ever grows enough that this becomes a real bottleneck, this function is the one seam
to swap for a background worker; nothing above it (the 14 call sites in payments.py, case_documents.py,
etc.) would need to change.

Contract every caller relies on: THIS FUNCTION NEVER RAISES. A payment, a document upload, a case status
change must all succeed or fail on their own merits — email is always a side effect, never a dependency."""

import json
import logging
from datetime import datetime

from flask import current_app

from app import mailer
from app.email_render import render_email
from app.email_templates import DIRECT_TEMPLATE_KEYS, TEMPLATES
from app.extensions import db
from app.models import EmailLog

logger = logging.getLogger("og_email")


def _existing_for_dedupe(dedupe_key):
    if not dedupe_key:
        return None
    return (
        EmailLog.query.filter(EmailLog.dedupe_key == dedupe_key, EmailLog.status.in_(("sent", "pending", "sending")))
        .order_by(EmailLog.id.desc())
        .first()
    )


def send_transactional_email(student, template_key, lang, *, ref=None, content=None, related_type=None,
                              related_id=None, dedupe_key=None, recipient_email=None, recipient_name=None):
    """The normal call site shape: `send_transactional_email(student, "payment_received", lang,
    ref={"payment_id": payment.id}, related_type="payment", related_id=payment.id,
    dedupe_key=f"payment_received:{payment.id}")`. Returns the `EmailLog` row (whatever its final status),
    or None if nothing was sent (dedupe hit, or the template builder decided there was nothing to say).
    Never raises — every failure mode is caught and recorded on the row instead."""
    try:
        lang = lang if lang in ("en", "es") else "en"
        existing = _existing_for_dedupe(dedupe_key)
        if existing is not None:
            return existing

        to_email = recipient_email or (student.email if student else None)
        to_name = recipient_name or (student.name if student else None)
        if not to_email:
            return None

        if content is None:
            if template_key not in TEMPLATES:
                logger.warning("[email] unknown template_key %r", template_key)
                return None
            content = TEMPLATES[template_key](lang, ref or {})
            if content is None:
                return None  # the template decided there is nothing to send (record no longer applies)

        log = EmailLog(
            student_id=student.id if student else None, recipient_email=to_email, recipient_name=to_name,
            template_key=template_key, language=lang, subject=content.subject[:255],
            related_type=related_type, related_id=related_id,
            ref_json=json.dumps(ref, ensure_ascii=False) if (ref and template_key not in DIRECT_TEMPLATE_KEYS) else None,
            dedupe_key=dedupe_key, status="pending",
        )
        db.session.add(log)
        db.session.commit()

        _attempt_delivery(log, content, lang)
        _log_activity(log)
        return log
    except Exception:  # noqa: BLE001 — email must never break the caller's own transaction
        logger.exception("[email] send_transactional_email failed for template=%r", template_key)
        try:
            db.session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None


def deliver(log, content, lang):
    """Public wrapper around `_attempt_delivery` for callers that already hold an `EmailLog` row and a
    built `EmailContent` (currently only the Admin SMTP test tool, app/blueprints/admin/email_routes.py)."""
    return _attempt_delivery(log, content, lang)


def _attempt_delivery(log, content, lang):
    """Renders and attempts one SMTP delivery for an already-persisted EmailLog row, updating its status in
    place. Isolated so `retry()` can call the exact same path."""
    public_url = current_app.config.get("APP_PUBLIC_URL") or "http://localhost:5001"
    try:
        subject, html_body, text_body = render_email(content, lang, public_url=public_url)
        log.status = "sending"
        log.attempt_count = (log.attempt_count or 0) + 1
        log.last_attempt_at = datetime.utcnow()
        db.session.commit()

        mailer.send(to_email=log.recipient_email, to_name=log.recipient_name, subject=subject, html_body=html_body, text_body=text_body)

        log.status = "sent"
        log.sent_at = datetime.utcnow()
        log.failure_reason = None
        db.session.commit()
    except mailer.MailDisabled:
        log.status = "failed"
        log.failed_at = datetime.utcnow()
        log.failure_reason = "Email delivery is disabled in this environment (MAIL_ENABLED is not set to 1)."
        db.session.commit()
    except mailer.MailNotConfigured:
        log.status = "failed"
        log.failed_at = datetime.utcnow()
        log.failure_reason = "SMTP is not configured (SMTP_USERNAME/SMTP_PASSWORD missing)."
        db.session.commit()
    except Exception as exc:  # noqa: BLE001 — any SMTP/network error
        log.status = "failed"
        log.failed_at = datetime.utcnow()
        log.failure_reason = str(exc)[:500]
        db.session.commit()
        logger.warning("[email] delivery failed for EmailLog #%s (%s): %s", log.id, log.template_key, str(exc)[:200])


def _log_activity(log):
    """Best-effort Activity tab entry — never blocks/raises (log_event already guarantees that itself)."""
    if not log.student_id:
        return
    from app.activity import log_event

    log_event(
        log.student_id, "email_sent" if log.status == "sent" else "email_failed", actor="system",
        entity=("email_log", log.id), meta={"template": log.template_key, "subject": log.subject},
    )


def retry(email_log_id, *, admin_id=None):
    """Admin-only manual retry (item 17). Reuses the SAME row (never creates a second EmailLog for the
    same attempt, so a retry can never duplicate delivery), re-renders from current data via the SAME
    template registry, and is refused for DIRECT templates (a stale code/reset-link should never be
    resent — the customer/admin should trigger a fresh one instead)."""
    log = db.session.get(EmailLog, email_log_id)
    if log is None:
        return None, "Email not found."
    if log.status != "failed":
        return log, "Only a failed email can be retried."
    if log.template_key in DIRECT_TEMPLATE_KEYS:
        return log, "This type of email can't be resent directly — ask the customer to request a new one."
    builder = TEMPLATES.get(log.template_key)
    if builder is None:
        return log, "Unknown template — cannot retry."
    ref = json.loads(log.ref_json) if log.ref_json else {}
    try:
        content = builder(log.language, ref)
    except Exception as exc:  # noqa: BLE001
        return log, f"Could not rebuild this email: {exc}"
    if content is None:
        return log, "This no longer applies (the underlying record has changed) — nothing to resend."
    _attempt_delivery(log, content, log.language)
    if log.student_id:
        from app.activity import log_event

        log_event(log.student_id, "email_sent" if log.status == "sent" else "email_failed", actor="admin", actor_id=admin_id,
                  entity=("email_log", log.id), meta={"template": log.template_key, "subject": log.subject})
    return log, None
