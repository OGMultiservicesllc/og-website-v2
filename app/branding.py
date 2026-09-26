"""Centralized branding-asset resolution (2026-09-26) — see docs/BRANDING.md for the full audit
this was built from.

`SiteSettings.logo_filename` (the pre-existing "Primary Website Logo" setting, unchanged by this
module) covers the public header/footer/mobile-nav/OG-image/JSON-LD via the existing `logo_url()`
global in `app/__init__.py`. Everything else this app actually shows a logo/icon in — the Admin
dashboard/login, the favicon, transactional emails, and a dedicated social/Organization image — was
either hardcoded to the same static file or (for email) not shown at all. This module is the one
place each of those now resolves its own asset, each falling back to the primary logo (or the same
static default the primary logo itself falls back to) when its own setting is unset, so leaving a
new field blank is visually identical to today.

Every function here is safe to call with no request context EXCEPT `email_logo_abs_url`, which is
specifically for transactional emails and therefore builds an ABSOLUTE url from `APP_PUBLIC_URL`
(never the current request's host) — the same reasoning as `app/email_render.py`'s `abs_url()`.
"""
from flask import current_app, url_for

from app.extensions import db


def _asset(asset_id):
    if not asset_id:
        return None
    from app.models import MediaAsset

    return db.session.get(MediaAsset, asset_id)


def _static_default(external=False):
    return url_for("static", filename="img/logo.png", _external=external)


def primary_logo_url(external=False):
    """Identical to the existing `logo_url()` global — kept here too so every other function in
    this module can share one definition of "the primary logo, resolved"."""
    from app.models import SiteSettings

    settings = SiteSettings.get()
    if settings.logo_filename:
        return url_for("site_logo", _external=external)
    return _static_default(external)


def admin_logo_url(external=False):
    """Admin dashboard sidebar/header + Admin login page. Was hardcoded to the static default
    before this task; now configurable, falling back to the PRIMARY logo (not the bare static
    default) when unset, since an admin who only ever set the one logo most likely wants it
    everywhere."""
    from app.models import SiteSettings

    from app.media_library import media_url

    settings = SiteSettings.get()
    asset = _asset(settings.admin_logo_media_id)
    if asset:
        return media_url(asset, 240)
    return primary_logo_url(external)


def favicon_url(external=False):
    """The browser-tab icon — was hardcoded to the full-size static logo PNG on every page type
    (public/admin/intake) via partials/tailwind_head.html. Falls back to that exact same static
    file when unset, so nothing changes until an admin picks a dedicated favicon image."""
    from app.models import SiteSettings

    from app.media_library import media_url

    settings = SiteSettings.get()
    asset = _asset(settings.favicon_media_id)
    if asset:
        return media_url(asset, 64)
    return _static_default(external)


def social_logo_url(external=True):
    """Open Graph image / Organization + BlogPosting JSON-LD `logo`/`image`. These already used
    the primary logo dynamically (never hardcoded) — this just adds the option of a DIFFERENT,
    dedicated asset (e.g. a square mark vs. a wide header logo) without disturbing the existing
    correct default of "use the primary logo". ALWAYS absolute (`external=True` by default) —
    both Open Graph and JSON-LD image URLs are required to be absolute per spec, exactly like the
    `logo_url(external=True)` call this replaced."""
    from flask import request

    from app.models import SiteSettings

    from app.media_library import media_url

    settings = SiteSettings.get()
    asset = _asset(settings.social_logo_media_id)
    if asset:
        path = media_url(asset, 1200)
        return (request.url_root.rstrip("/") + path) if external else path
    return primary_logo_url(external)


def email_logo_abs_url(public_url):
    """Transactional emails had NO logo image at all before this task (text-only header). Takes
    `public_url` from the CALLER (app/email_render.py already resolves this from APP_PUBLIC_URL,
    never `request.url_root`, for every link in an email) rather than re-reading config here, so
    there is exactly one place that decides what "the site" means for an email. Falls back to the
    primary logo, then the static default, so an email sent before anyone configures a dedicated
    email logo still shows something coherent rather than nothing."""
    from app.models import SiteSettings

    from app.media_library import media_url

    public_url = (public_url or "http://localhost:5001").rstrip("/")
    settings = SiteSettings.get()
    asset = _asset(settings.email_logo_media_id)
    if asset:
        return public_url + media_url(asset, 240)
    if settings.logo_filename:
        return public_url + url_for("site_logo")
    return public_url + url_for("static", filename="img/logo.png")
