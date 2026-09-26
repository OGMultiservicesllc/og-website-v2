"""One-off, idempotent pre-launch SEO data fixes (2026-09-26) — see the SEO audit report.

Same pattern as every other `ensure_*_refinements()` in this project (e.g. `seed_w7.
ensure_w7_refinements()`): safe to call on every app start, a no-op once applied, and every fix
only ever touches a field that is currently blank/wrong — an admin's own later edit is never
overwritten. Wired into `app/seed_content.py`'s `ensure_seeded()`.
"""
from app.extensions import db


def ensure_nj_dl_hub_seo_title():
    """The NJ Driver License category hub and its one service both showed the identical title
    'NJ Driver License Assistance — OG Multiservices LLC' (ServiceCategory.seo_title falls back to
    the plain category name when blank). Give the HUB its own distinct title; the service page's
    own SEO title is untouched."""
    from app.models import ServiceCategory

    cat = ServiceCategory.query.filter_by(slug="nj-driver-license").first()
    if not cat or cat.seo_title_en:
        return False
    # NOTE: service_category.html's <title> block always appends " — OG Multiservices LLC" itself
    # (`{{ page_title }} — OG Multiservices LLC`), same as every other category's title — the value
    # set here is deliberately just the distinguishing part, not a full "... | OG Multiservices"
    # string, so the brand is never duplicated in the rendered <title>.
    cat.seo_title_en = "New Jersey Driver License Services"
    cat.seo_title_es = "Servicios de Licencia de Conducir de Nueva Jersey"
    db.session.commit()
    return True


def ensure_itin_blog_slug_fix():
    """The post's slug ('5-documents-you-need-for-an-itin-application') never matched its actual
    title/content ('What Is an ITIN and Who Needs One?'). Renamed once, here, before the site's
    first production launch — the old slug gets a small dedicated redirect
    (public.blog_post_redirect_itin_slug in app/blueprints/public/routes.py), never confused with
    the legacy Wix redirect map."""
    from app.models import BlogPost

    old_slug = "5-documents-you-need-for-an-itin-application"
    new_slug = "what-is-an-itin-and-who-needs-one"
    post = BlogPost.query.filter_by(slug=old_slug).first()
    if not post:
        return False
    post.slug = new_slug
    db.session.commit()
    return True


def ensure_home_hero_alt():
    """The Home hero image's alt text had never been set, so `MediaAsset.alt()` fell back to the
    raw uploaded filename ('ChatGPT Image Sep 20, 2026, 01_24_01 PM.png') — meaningless alt text.
    Finds whichever MediaAsset is CURRENTLY assigned as the home hero via the same site_asset()
    lookup the page itself uses (not a hardcoded asset id, which could differ between databases),
    and only fills alt_en/alt_es when they are still blank."""
    from app.models import MediaAsset, PageBlock

    block = PageBlock.query.filter_by(key="home_hero_image").first()
    if not block or not (block.content_en or "").strip().isdigit():
        return False
    asset = db.session.get(MediaAsset, int(block.content_en.strip()))
    if not asset or asset.alt_en or asset.alt_es:
        return False
    asset.alt_en = "Desk with a laptop and documents, representing OG Multiservices' professional tax, translation, and notary services."
    asset.alt_es = "Escritorio con laptop y documentos, que representa los servicios profesionales de impuestos, traducciones y notaría de OG Multiservices."
    db.session.commit()
    return True


def ensure_seo_fixes():
    changed = ensure_nj_dl_hub_seo_title()
    changed = ensure_itin_blog_slug_fix() or changed
    changed = ensure_home_hero_alt() or changed
    return changed
