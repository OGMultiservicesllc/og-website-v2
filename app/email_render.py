"""Renders one `EmailContent` (built by a template function in `app/email_templates.py`) into an HTML body
(via the shared `emails/base.html` layout) and a plain-text fallback (built in plain Python — trivial
enough that a second Jinja template would only add indirection). One shared layout means every
transactional email looks consistent without copy-pasting markup per email type."""

from dataclasses import dataclass, field
from typing import List, Optional

from flask import current_app, render_template, url_for

from app import business_info


def mask_email(email):
    """m•••••@gmail.com — item 5: never disclose a full address on a screen an unauthenticated visitor
    could see (the verification screen shows this, not the real address)."""
    email = (email or "").strip()
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        masked = local + "•••"
    else:
        masked = local[0] + "•" * max(3, len(local) - 1)
    return f"{masked}@{domain}"


def abs_url(endpoint, lang, **kwargs):
    """A link whose ORIGIN always comes from the configured APP_PUBLIC_URL (never the request's own host,
    and never hardcoded) and whose PATH comes from Flask's normal routing — see item 12 of the transactional
    email spec. Works inside any request context (every real trigger point in this app runs inside one)."""
    public_url = (current_app.config.get("APP_PUBLIC_URL") or "http://localhost:5001").rstrip("/")
    path = url_for(endpoint, lang=lang, **kwargs)
    return public_url + path


@dataclass
class EmailContent:
    subject: str
    heading: str
    paragraphs: List[str] = field(default_factory=list)
    code: Optional[str] = None  # large 6-digit verification code display
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None
    footnote: Optional[str] = None


def render_email(content: EmailContent, lang: str, *, public_url: str):
    from app.branding import email_logo_abs_url

    html = render_template(
        "emails/base.html",
        lang=lang,
        subject=content.subject,
        heading=content.heading,
        paragraphs=content.paragraphs,
        code=content.code,
        cta_label=content.cta_label,
        cta_url=content.cta_url,
        footnote=content.footnote,
        biz=business_info,
        site_url=public_url,
        logo_url=email_logo_abs_url(public_url),
    )

    lines = [content.heading, ""]
    lines.extend(content.paragraphs)
    if content.code:
        lines.append("")
        lines.append(content.code)
    if content.cta_label and content.cta_url:
        lines.append("")
        lines.append(f"{content.cta_label}: {content.cta_url}")
    if content.footnote:
        lines.append("")
        lines.append(content.footnote)
    lines.append("")
    lines.append("—")
    lines.append(business_info.BUSINESS_NAME)
    lines.append(f"{business_info.PHONE_DISPLAY} · WhatsApp: {business_info.WHATSAPP_DISPLAY}")
    lines.append(business_info.EMAIL)
    lines.append(public_url)
    text = "\n".join(lines)

    return content.subject, html, text
