"""Structured editing for the site's standalone hand-composed pages (Home, the
Services hub). Each page declares its editable sections/fields here; values are
stored in the existing bilingual key/value table (PageBlock), keyed by the same
i18n key the template already uses, so a field with no override simply shows its
built-in default text.

Service categories and services do NOT live here; they are real records
(ServiceCategory / Service) edited under Admin -> Services.
"""

from flask import g

from app.extensions import db
from app.i18n import get_text
from app.models import MediaAsset, PageBlock

# field types: text | textarea | image | focus
SITE_PAGES = {
    "home": {
        "label": "Home",
        "endpoint": "public.home",
        "sections": [
            {
                "id": "hero", "label": "Hero",
                "help": "The first screen. Keep the headline short; the highlighted words use the accent colour.",
                "fields": [
                    {"key": "home_eyebrow", "label": "Badge", "type": "text"},
                    {"key": "home_title_prefix", "label": "Headline (start)", "type": "text"},
                    {"key": "home_title_accent", "label": "Headline (highlighted words)", "type": "text"},
                    {"key": "home_subtitle", "label": "Subheadline", "type": "textarea"},
                    {"key": "home_cta_start", "label": "Primary button (Get Started)", "type": "text"},
                    {"key": "home_cta_primary", "label": "WhatsApp button", "type": "text"},
                    {"key": "home_stat_year", "label": "Highlight 1 — value", "type": "text"},
                    {"key": "home_stat_year_label", "label": "Highlight 1 — label", "type": "text"},
                    {"key": "home_stat_lang", "label": "Highlight 2 — value", "type": "text"},
                    {"key": "home_stat_lang_label", "label": "Highlight 2 — label", "type": "text"},
                    {"key": "home_stat_mode", "label": "Highlight 3 — value", "type": "text"},
                    {"key": "home_stat_mode_label", "label": "Highlight 3 — label", "type": "text"},
                    {"key": "home_hero_image", "label": "Hero Image", "type": "image", "ratio": "16:9"},
                    {"key": "home_hero_mobile_image", "label": "Mobile Hero Image (optional)", "type": "image", "ratio": "4:3"},
                    {"key": "home_hero_focus", "label": "Image focus", "type": "focus"},
                ],
            },
            {
                "id": "launcher", "label": "Service launcher",
                "help": "The \"How can we help?\" block. Its entries are your featured Services categories (Admin -> Services).",
                "fields": [
                    {"key": "home_card_title", "label": "Title", "type": "text"},
                    {"key": "home_card_subtitle", "label": "Subtitle", "type": "text"},
                    {"key": "home_card_view_all", "label": "\"View all\" link", "type": "text"},
                ],
            },
            {
                "id": "services", "label": "Services sections",
                "fields": [
                    {"key": "home_popular_title", "label": "Popular requests — title", "type": "text"},
                    {"key": "home_popular_subtitle", "label": "Popular requests — subtitle", "type": "text"},
                    {"key": "home_more_title", "label": "More services — title", "type": "text"},
                ],
            },
            {
                "id": "trust", "label": "Trust indicators",
                "fields": [{"key": "trust_title", "label": "Section title", "type": "text"}]
                + [
                    field
                    for key in ("bilingual", "confidential", "caa", "certified", "local", "experience")
                    for field in (
                        {"key": f"trust_{key}", "label": f"{key.title()} — title", "type": "text"},
                        {"key": f"trust_{key}_desc", "label": f"{key.title()} — description", "type": "text"},
                    )
                ],
            },
            {
                "id": "academy", "label": "OG Academy promo",
                "fields": [
                    {"key": "academy_promo_title", "label": "Title", "type": "text"},
                    {"key": "academy_promo_body", "label": "Text", "type": "textarea"},
                    {"key": "academy_promo_cta", "label": "Button", "type": "text"},
                    {"key": "home_academy_image", "label": "Academy Image", "type": "image", "ratio": "3:2"},
                ],
            },
            {
                "id": "seo", "label": "SEO",
                "fields": [
                    {"key": "home_meta_description", "label": "Meta description", "type": "textarea"},
                    {"key": "home_social_image", "label": "Social / SEO Image", "type": "image", "ratio": "1200×630"},
                ],
            },
        ],
    },
    "about": {
        "label": "About Page",
        "endpoint": "public.about",
        "sections": [
            {
                "id": "hero", "label": "Hero image",
                "help": "A business/office image for the About page hero — NOT the founder portrait (that's below). Until one is uploaded, a neutral placeholder is shown.",
                "fields": [
                    {"key": "about_hero_image", "label": "About Hero Image", "type": "image", "ratio": "16:9"},
                    {"key": "about_hero_image_focus", "label": "Image focus", "type": "focus"},
                ],
            },
            {
                "id": "founder", "label": "Founder",
                "help": "One photo, reused on the Home page, the About page and (later) OG Academy — replace it here and every place it appears updates automatically.",
                "fields": [
                    {"key": "founder_photo", "label": "Founder Photo", "type": "image", "ratio": "1:1"},
                    {"key": "founder_photo_focus", "label": "Photo focus", "type": "focus"},
                ],
            },
        ],
    },
    "services-hub": {
        "label": "Other Services page",
        "endpoint": "public.services",
        "sections": [
            {
                "id": "hero", "label": "Header",
                "fields": [
                    {"key": "sv_title", "label": "Title", "type": "text"},
                    {"key": "sv_subtitle", "label": "Subtitle", "type": "textarea"},
                    {"key": "sv_secondary_title", "label": "\"More ways we help\" heading", "type": "text"},
                ],
            },
        ],
    },
}


def all_fields(page_key):
    for section in SITE_PAGES[page_key]["sections"]:
        for field in section["fields"]:
            yield field


# --------------------------------------------------------------------- reading
def _blocks():
    cache = getattr(g, "_site_blocks", None)
    if cache is None:
        cache = {b.key: b for b in PageBlock.query.all()}
        g._site_blocks = cache
    return cache


def site_text(key, lang):
    """Admin override if set, otherwise the built-in default for the language."""
    block = _blocks().get(key)
    if block:
        value = block.content_es if lang == "es" else block.content_en
        if value:
            return value
    return get_text(lang, key)


def site_value(key):
    block = _blocks().get(key)
    return (block.content_en or "").strip() if block else ""


def site_asset(key):
    raw = site_value(key)
    if raw.isdigit():
        return db.session.get(MediaAsset, int(raw))
    return None


def site_focus(key, default="center"):
    value = site_value(key)
    return value if value in ("center", "top", "bottom", "left", "right") else default


def site_image_usages(asset_id):
    from flask import url_for

    found = []
    for page_key, page in SITE_PAGES.items():
        image_keys = {f["key"] for f in all_fields(page_key) if f["type"] == "image"}
        for block in PageBlock.query.filter(PageBlock.key.in_(image_keys)).all():
            if (block.content_en or "").strip() == str(asset_id):
                found.append((f"{page['label']} page ({block.key.replace('_', ' ')})", url_for("admin.site_page_edit", page_key=page_key)))
    return found


# --------------------------------------------------------------------- writing
def save_site_fields(page_key, form):
    """Persist every field of a page from a submitted form. Empty text falls back
    to the built-in default (the override row is removed)."""
    changed = 0
    for field in all_fields(page_key):
        key, kind = field["key"], field["type"]
        block = PageBlock.query.filter_by(key=key).first()
        if kind in ("image", "focus"):
            value_en = (form.get(f"{key}__en") or "").strip()
            value_es = None
        else:
            value_en = (form.get(f"{key}__en") or "").strip()
            value_es = (form.get(f"{key}__es") or "").strip()
        if not value_en and not value_es:
            if block:
                db.session.delete(block)
                changed += 1
            continue
        if not block:
            block = PageBlock(key=key)
            db.session.add(block)
        block.content_en = value_en or None
        block.content_es = value_es or None
        changed += 1
    db.session.commit()
    if hasattr(g, "_site_blocks"):
        del g._site_blocks
    return changed
