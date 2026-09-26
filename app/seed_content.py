"""One-time, idempotent seeding of the structured Services CMS from the content that
already existed on the site (Python service data, i18n strings and any admin
overrides stored through the old "Flagship Page Text" key/value table).

It only runs when there are no service categories yet, so it can never overwrite
what an administrator has since edited. Nothing is deleted from the sources; they
simply stop being the place to edit.
"""

from app.legacy_block_defaults import get_block
from app.extensions import db
from app.i18n import get_text
from app.models import Service, ServiceCategory, ServiceContentItem
from app.service_areas import get_scope
from app.service_pages import CATEGORY_META, SUBPAGES


def _t(key):
    return get_text("en", key), get_text("es", key)


def _b(key):
    return get_block(key, "en"), get_block(key, "es")


def _loc(value):
    """service_pages.py stores {en, es} dicts."""
    if isinstance(value, dict):
        return value.get("en"), value.get("es") or value.get("en")
    return value, value


# Services shown as "Popular requests" on Home until an administrator changes it.
FEATURED_SERVICE_SLUGS = {
    "tax-preparation", "itin-application", "i-130-petition", "green-card-renewal",
    "naturalization-citizenship", "certified-birth-certificate-translation", "notarization",
}

# slug -> spec. Each *_key is an i18n key, each *_block a former Flagship block key.
CATEGORY_SPECS = [
    dict(
        slug="taxes-itin", endpoint="public.taxes_itin", subpage_endpoint="public.taxes_subpage", icon="taxes",
        sort=10, featured=True, short_key="home_core_taxes_desc",
        title_block="tx_title", hero_text_block="tx_hero_subtitle", cta_key="tx_hero_cta",
        cta_mode="contact", cta_url=None, whatsapp=True,
        final_cta=("tx_cta_title", "tx_cta_body"),
        faq=[("tx_faq_q1", "tx_faq_a1"), ("tx_faq_q2", "tx_faq_a2"), ("tx_faq_q3", "tx_faq_a3")],
        steps=[(f"tx_step{i}_title", f"tx_step{i}_desc") for i in range(1, 5)],
        features=[
            ("tx_taxes_title", "tx_taxes_body", True, [f"tx_taxes_who{i}" for i in range(1, 7)]),
            ("tx_itin_title", "tx_itin_body", True, [f"tx_itin_service{i}" for i in range(1, 7)]),
        ],
    ),
    dict(
        slug="certified-translations", endpoint="public.translations", subpage_endpoint="public.translation_subpage", icon="translations",
        sort=20, featured=True, short_key="home_core_translations_desc",
        title_key="tr_title", hero_text_key="tr_hero_subtitle", cta_key="tr_hero_cta",
        cta_mode="url", cta_url="#quote", whatsapp=True,
        intro_block="translations_intro", contact_note_block="translations_whatsapp_note",
        final_cta=("tr_cta_title", "tr_cta_body"),
        faq=[("tr_faq_q1", "tr_faq_a1"), ("tr_faq_q2", "tr_faq_a2"), ("tr_faq_q3", "tr_faq_a3")],
        steps=[(f"tr_step{i}_title", f"tr_step{i}_desc") for i in range(1, 5)],
        headings=dict(checklist="tr_what_title", features="tr_used_title"),
        features=[(k, None, False, []) for k in ("tr_used_uscis", "tr_used_dmv", "tr_used_schools", "tr_used_eval", "tr_used_courts", "tr_used_gov")],
        checklist=[
            "tr_doc_birth", "tr_doc_marriage", "tr_doc_divorce", "tr_doc_death", "tr_doc_license", "tr_doc_id",
            "tr_doc_passport", "tr_doc_transcript", "tr_doc_diploma", "tr_doc_legal", "tr_doc_immigration",
            "tr_doc_court", "tr_doc_medical", "tr_doc_financial", "tr_doc_other",
        ],
    ),
    dict(
        slug="immigration", endpoint="public.immigration", subpage_endpoint="public.immigration_subpage", icon="immigration",
        sort=30, featured=True, short_key="home_core_immigration_desc",
        title_block="sv_immigration_title", hero_text_block="ig_hero_subtitle", cta_key="ig_hero_cta",
        cta_mode="url", cta_url="#inquiry", whatsapp=True,
        disclaimer_key="sv_immigration_disclaimer",
        faq=[("ig_faq_q1", "ig_faq_a1"), ("ig_faq_q2", "ig_faq_a2"), ("ig_faq_q3", "ig_faq_a3")],
        steps=[(f"ig_step{i}_title", f"ig_step{i}_desc") for i in range(1, 5)],
    ),
    dict(
        slug="notary", endpoint="public.notary", subpage_endpoint="public.notary_subpage", icon="notary",
        sort=40, featured=True, short_key="home_core_notary_desc",
        title_block="sv_notary_title", hero_text_block="sv_notary_body", cta_block="sv_notary_cta",
        cta_mode="contact", cta_url=None, whatsapp=True,
        final_cta=("nt_cta_title", "nt_cta_body"),
        faq=[("nt_faq_q1", "nt_faq_a1"), ("nt_faq_q2", "nt_faq_a2"), ("nt_faq_q3", "nt_faq_a3")],
    ),
    dict(
        slug="nj-driver-license", endpoint="public.nj_driver_license", subpage_endpoint=None, icon="license",
        sort=50, featured=True, short_key="home_core_license_desc",
        title_block="sv_license_title", hero_text_block="sv_license_body", cta_block="sv_license_cta",
        cta_mode="whatsapp", cta_url=None, whatsapp=True,
        info=("dl_checklist_title", "dl_checklist_intro"),
        final_cta=("dl_cta_title", "dl_cta_body"),
        faq=[("dl_faq_q1", "dl_faq_a1"), ("dl_faq_q2", "dl_faq_a2"), ("dl_faq_q3", "dl_faq_a3")],
        checklist=[f"dl_point{i}" for i in range(1, 7)],
        headings=dict(included="dl_services_title"),
        included=[f"dl_service{i}" for i in range(1, 4)],
    ),
    dict(
        slug="apostille", endpoint="public.apostille", subpage_endpoint="public.apostille_subpage", icon="apostille",
        sort=60, featured=False, short_key="home_add_apostille_desc",
        title_block="sv_apostille_title", hero_text_block="sv_apostille_body", cta_block="sv_apostille_cta",
        cta_mode="whatsapp", cta_url=None, whatsapp=True,
        final_cta=("ap_cta_title", "ap_cta_body"),
        faq=[("ap_faq_q1", "ap_faq_a1"), ("ap_faq_q2", "ap_faq_a2"), ("ap_faq_q3", "ap_faq_a3")],
    ),
    dict(
        slug="wedding-officiant", endpoint="public.wedding_officiant", subpage_endpoint=None, icon="officiant",
        sort=70, featured=False, short_key="home_add_wedding_desc",
        title_block="sv_officiant_title", hero_text_block="sv_officiant_body", cta_block="sv_officiant_cta",
        cta_mode="whatsapp", cta_url=None, whatsapp=True,
        final_cta=("wo_cta_title", "wo_cta_body"),
        faq=[("wo_faq_q1", "wo_faq_a1"), ("wo_faq_q2", "wo_faq_a2"), ("wo_faq_q3", "wo_faq_a3")],
        headings=dict(included="wo_services_title"),
        included=[f"wo_service{i}" for i in range(1, 4)],
    ),
    dict(
        slug="document-office-services", endpoint="public.document_office_services",
        subpage_endpoint="public.document_office_subpage", icon="documents",
        sort=80, featured=False, short_key="home_add_docs_desc",
        title_block="sv_docs_title", hero_text_block="sv_docs_body", cta_block="sv_docs_cta",
        cta_mode="contact", cta_url=None, whatsapp=True,
        final_cta=("do_cta_title", "do_cta_body"),
        faq=[("do_faq_q1", "do_faq_a1"), ("do_faq_q2", "do_faq_a2"), ("do_faq_q3", "do_faq_a3")],
    ),
]


def _set_pair(obj, field, pair):
    en, es = pair
    setattr(obj, f"{field}_en", en or None)
    setattr(obj, f"{field}_es", (es or en) or None)


def _seed_category(spec):
    cat = ServiceCategory(
        slug=spec["slug"], endpoint=spec["endpoint"], subpage_endpoint=spec["subpage_endpoint"],
        icon=spec["icon"], sort_order=spec["sort"], is_featured=spec["featured"], is_published=True,
        show_in_nav=True, cta_mode=spec["cta_mode"], cta_url=spec["cta_url"],
        whatsapp_enabled=spec["whatsapp"], title_en="", title_es="",
    )
    title = _b(spec["title_block"]) if "title_block" in spec else _t(spec["title_key"])
    _set_pair(cat, "title", title)
    cat.title_en, cat.title_es = title[0], title[1] or title[0]
    _set_pair(cat, "hero_title", title)
    _set_pair(cat, "short", _t(spec["short_key"]))
    hero_text = _b(spec["hero_text_block"]) if "hero_text_block" in spec else _t(spec["hero_text_key"])
    _set_pair(cat, "hero_text", hero_text)
    if "cta_block" in spec:
        _set_pair(cat, "cta_label", _b(spec["cta_block"]))
    elif "cta_key" in spec:
        _set_pair(cat, "cta_label", _t(spec["cta_key"]))
    if "intro_block" in spec:
        _set_pair(cat, "intro_body", _b(spec["intro_block"]))
    if "contact_note_block" in spec:
        _set_pair(cat, "contact_note", _b(spec["contact_note_block"]))
    if "disclaimer_key" in spec:
        _set_pair(cat, "disclaimer", _t(spec["disclaimer_key"]))
    if "info" in spec:
        _set_pair(cat, "info_title", _t(spec["info"][0]))
        _set_pair(cat, "info_body", _t(spec["info"][1]))
    if "final_cta" in spec:
        _set_pair(cat, "final_cta_title", _t(spec["final_cta"][0]))
        _set_pair(cat, "final_cta_body", _t(spec["final_cta"][1]))
    _set_pair(cat, "seo_description", hero_text)
    for kind, key in spec.get("headings", {}).items():
        _set_pair(cat, f"{kind}_title", _t(key))

    def add(kind, order, title_pair, body_pair=(None, None)):
        item = ServiceContentItem(kind=kind, sort_order=order, title_en=title_pair[0] or "", title_es=title_pair[1] or title_pair[0] or "")
        item.body_en, item.body_es = body_pair[0], (body_pair[1] or body_pair[0])
        cat.items.append(item)

    for i, (q, a) in enumerate(spec.get("faq", []), 1):
        add("faq", i, _t(q), _t(a))
    for i, (tk, dk) in enumerate(spec.get("steps", []), 1):
        add("step", i, _t(tk), _t(dk))
    for i, feature in enumerate(spec.get("features", []), 1):
        tk, bk, is_block, bullet_keys = feature
        pick = _b if is_block else _t
        if bk:
            body = pick(bk)
            if bullet_keys:  # keep the old bullet lists inside the card so nothing is lost
                bullets_en = "\n".join("• " + _t(k)[0] for k in bullet_keys)
                bullets_es = "\n".join("• " + _t(k)[1] for k in bullet_keys)
                body = (body[0] + "\n" + bullets_en, (body[1] or body[0]) + "\n" + bullets_es)
            add("feature", i, pick(tk), body)
        else:
            add("feature", i, _t(tk))
    for i, key in enumerate(spec.get("checklist", []), 1):
        add("checklist", i, _t(key))
    for i, key in enumerate(spec.get("included", []), 1):
        add("included", i, _t(key))
    return cat


def _seed_services(cat, pages):
    by_slug = {}
    for order, page in enumerate(pages, 1):
        svc = Service(
            slug=page["slug"], icon=page.get("icon") or cat.icon, sort_order=order * 10, is_published=page.get("is_published", True),
            title_en="", title_es="", admin_name=_loc(page["title"])[0],
        )
        title = _loc(page["title"])
        svc.title_en, svc.title_es = title
        _set_pair(svc, "short", _loc(page["meta_description"]))
        _set_pair(svc, "seo_description", _loc(page["meta_description"]))
        _set_pair(svc, "hero_text", _loc(page["hero_text"]))
        _set_pair(svc, "content_title", _loc(page["what_is_title"]))
        _set_pair(svc, "content", _loc(page["what_is_body"]))
        scope = get_scope(cat.slug, page["slug"])
        svc.is_featured = page["slug"] in FEATURED_SERVICE_SLUGS
        svc.nj_in_person = bool(scope["nj_in_person"])
        svc.tx_in_person = bool(scope["tx_in_person"])
        svc.remote_nationwide = bool(scope["remote_nationwide"])
        if scope.get("note"):
            _set_pair(svc, "scope_note", _loc(scope["note"]))

        def add(kind, order, title_pair, body_pair=(None, None)):
            item = ServiceContentItem(kind=kind, sort_order=order, title_en=title_pair[0] or "", title_es=title_pair[1] or title_pair[0] or "")
            item.body_en, item.body_es = body_pair[0], (body_pair[1] or body_pair[0])
            svc.items.append(item)

        for i, entry in enumerate(page.get("when_needed", []), 1):
            add("when_needed", i, _loc(entry))
        for i, entry in enumerate(page.get("included", []), 1):
            add("included", i, _loc(entry))
        for i, entry in enumerate(page.get("faq", []), 1):
            add("faq", i, _loc(entry["q"]), _loc(entry["a"]))
        cat.services.append(svc)
        by_slug[page["slug"]] = (svc, page)

    db.session.flush()
    for svc, page in by_slug.values():
        for rel_slug in page.get("related", []):
            if rel_slug in by_slug:
                svc.related.append(by_slug[rel_slug][0])


def seed_service_content(force=False):
    """Creates the categories and services. Returns True if it seeded."""
    if not force and ServiceCategory.query.count() > 0:
        return False
    for spec in CATEGORY_SPECS:
        cat = _seed_category(spec)
        db.session.add(cat)
        db.session.flush()
        _seed_services(cat, SUBPAGES.get(spec["slug"], []))
    db.session.commit()
    return True


def seed_navigation():
    from app.models import NavItem

    if NavItem.query.count() > 0:
        return False
    for order, key in enumerate(("home", "services", "about", "academy", "blog", "contact"), 1):
        db.session.add(NavItem(kind="system", system_key=key, sort_order=order * 10, is_visible=True))
    db.session.commit()
    return True


def ensure_about_nav_item():
    """Backfill (2026-09-23): adds the "About OG" nav item, between Services and OG Academy, for a
    database that was already seeded before this item existed — idempotent, a no-op once it's there."""
    from app.models import NavItem

    if NavItem.query.filter_by(system_key="about").first():
        return False
    services_item = NavItem.query.filter_by(system_key="services").first()
    sort_order = (services_item.sort_order + 5) if services_item else 25
    db.session.add(NavItem(kind="system", system_key="about", sort_order=sort_order, is_visible=True))
    db.session.commit()
    return True


def ensure_blog_categories():
    """One-time data reconciliation, safe to re-run: the ITIN articles were filed under 'Taxes' back when
    the Admin blog form only had a free-text category box (no real selector). Content/EN/ES/images are
    never touched — only the `category` column, and only when it isn't already a valid, closed-list value."""
    from app.models import BLOG_CATEGORIES, BlogPost

    by_lower = {c.lower(): c for c in BLOG_CATEGORIES}
    changed = False
    for post in BlogPost.query.all():
        is_itin = "itin" in (post.slug or "").lower() or "itin" in (post.title_en or "").lower()
        if is_itin:
            new_cat = "ITIN"  # was generically filed under Taxes before Admin had a real category selector
        elif post.category in BLOG_CATEGORIES:
            continue  # already a valid, non-ITIN category — leave as the admin set it
        elif (post.category or "").strip().lower() in by_lower:
            new_cat = by_lower[(post.category or "").strip().lower()]  # e.g. "taxes"/"Tax " -> the canonical spelling
        else:
            new_cat = "General"
        if post.category == new_cat:
            continue
        post.category = new_cat
        changed = True
    if changed:
        db.session.commit()
    return changed


def ensure_seeded():
    """Safe to call on every start: a no-op once categories exist, and silent
    if the tables haven't been created yet (migration not run)."""
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        seeded = seed_service_content()
        seeded = seed_navigation() or seeded
        seeded = ensure_about_nav_item() or seeded
        from app.seed_forms import ensure_i90_shell
        from app.seed_i90 import ensure_i90_intake, ensure_prepared_intakes
        from app.seed_i90_refine import ensure_i90_refinements
        from app.seed_i130 import ensure_i130_intake
        from app.seed_i130a import ensure_i130a_supplement
        from app.seed_i485 import ensure_i485_intake, ensure_i485_shared_data
        from app.seed_n400 import ensure_n400_intake

        seeded = ensure_i90_shell() or seeded
        seeded = ensure_i90_intake() or seeded
        seeded = ensure_i90_refinements() or seeded
        seeded = ensure_prepared_intakes() or seeded
        seeded = ensure_n400_intake() or seeded
        seeded = ensure_i130_intake() or seeded
        seeded = ensure_i130a_supplement() or seeded
        seeded = ensure_i485_intake() or seeded
        seeded = ensure_i485_shared_data() or seeded
        from app.seed_i864 import ensure_i864_intake, ensure_i864_refinements
        from app.seed_i765 import ensure_i765_intake
        from app.seed_i751 import ensure_i751_intake

        seeded = ensure_i864_intake() or seeded
        seeded = ensure_i864_refinements() or seeded
        seeded = ensure_i765_intake() or seeded
        seeded = ensure_i751_intake() or seeded
        from app.seed_ds260 import ensure_ds260_intake

        seeded = ensure_ds260_intake() or seeded
        from app.seed_w7 import ensure_w7_intake, ensure_w7_refinements

        seeded = ensure_w7_intake() or seeded
        seeded = ensure_w7_refinements() or seeded
        from app.itin_pricing import ensure_seed as ensure_itin_pricing

        seeded = bool(ensure_itin_pricing()) or seeded
        from app.tax.seed import ensure_service as ensure_tax_service
        from app.tax.pricing import ensure_seed as ensure_tax_pricing
        from app.tax.registry import CURRENT_YEAR

        seeded = ensure_tax_service() or seeded
        seeded = ensure_tax_pricing(CURRENT_YEAR) or seeded
        from app.driver_license.seed import ensure_all as ensure_dl

        seeded = ensure_dl() or seeded
        from app.consent_travel.seed import ensure_all as ensure_ct

        seeded = ensure_ct() or seeded
        seeded = ensure_blog_categories() or seeded
        from app.seed_seo_fixes import ensure_seo_fixes

        seeded = ensure_seo_fixes() or seeded
        from app import notifications as notif

        notif.ensure_seed()
        from app.cases import backfill_cases

        return bool(backfill_cases()) or seeded
    except (OperationalError, ProgrammingError):
        db.session.rollback()
        return False
    except Exception:  # seeding must never stop the site from starting
        import logging

        logging.getLogger(__name__).exception("Content seeding failed")
        db.session.rollback()
        return False
