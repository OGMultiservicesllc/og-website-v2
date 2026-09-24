"""Low-level SMTP transport — stdlib only, no new dependency (`smtplib` + `email.mime`). Titan/Bluehost
SMTP over implicit TLS (port 465). This module knows nothing about templates, logging, or retries; it only
turns a rendered (subject, html, text, to_email) into one SMTP send. `app/email_service.py` is the layer
that adds development safety, the delivery ledger, and dedupe/retry on top of this.

Development safety (item 15): `send()` is a no-op — raising `MailDisabled` rather than attempting a real
connection — unless `MAIL_ENABLED` is explicitly "1". This is checked here, not just by callers, so there
is exactly one place a bug could ever accidentally send real mail from a dev/test run."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from flask import current_app


class MailDisabled(Exception):
    """Raised when MAIL_ENABLED is not "1" — callers treat this as an expected, non-fatal outcome."""


class MailNotConfigured(Exception):
    """Raised when MAIL_ENABLED=1 but SMTP_USERNAME/SMTP_PASSWORD are missing."""


def is_enabled():
    return bool(current_app.config.get("MAIL_ENABLED"))


def send(*, to_email, to_name, subject, html_body, text_body):
    """Sends one email synchronously with a bounded socket timeout, so a slow/unreachable SMTP server can
    never hang a web request indefinitely. Raises on failure — callers (app/email_service.py) are
    responsible for catching this and recording it, never letting it propagate into the business
    transaction that triggered the email."""
    if not is_enabled():
        raise MailDisabled("MAIL_ENABLED is not set to 1 — no SMTP delivery is attempted.")

    cfg = current_app.config
    username = cfg.get("SMTP_USERNAME") or ""
    password = cfg.get("SMTP_PASSWORD") or ""
    if not username or not password:
        raise MailNotConfigured("SMTP_USERNAME/SMTP_PASSWORD are not configured.")

    from_name = cfg.get("MAIL_FROM_NAME") or "OG Multiservices LLC"
    from_email = cfg.get("MAIL_FROM_EMAIL") or username
    reply_to = cfg.get("MAIL_REPLY_TO") or from_email

    real_to_email, real_to_name = to_email, to_name
    dev_redirect = cfg.get("MAIL_DEV_REDIRECT_TO") or ""
    if dev_redirect and cfg.get("APP_ENV") != "production":
        to_email = dev_redirect
        to_name = f"[DEV — was: {real_to_name or real_to_email}]"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = formataddr((to_name or "", to_email))
    msg["Reply-To"] = reply_to
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    host = cfg.get("SMTP_HOST") or "smtp.titan.email"
    port = int(cfg.get("SMTP_PORT") or 465)
    use_ssl = cfg.get("SMTP_USE_SSL", True)

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=10) as server:
            server.login(username, password)
            server.sendmail(from_email, [to_email], msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(username, password)
            server.sendmail(from_email, [to_email], msg.as_string())
