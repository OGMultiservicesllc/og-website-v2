"""Visitor-facing rendering of service categories and services from the CMS
records (ServiceCategory / Service). Keeps route functions tiny and makes the
"what does the Get Started button do" decision in exactly one place.
"""

from flask import abort, render_template, url_for

from app import business_info as biz
from app.i18n import get_text
from app.media_library import media_url
from app.models import Service, ServiceCategory


def get_category(slug):
    cat = ServiceCategory.query.filter_by(slug=slug).first()
    if not cat or not cat.is_published:
        abort(404)
    return cat


def _absolute_cta_url(cat, url):
    """A category's '#quote'-style anchors only work on the category page itself;
    from a service page they must point back to it."""
    if url and url.startswith("#"):
        return url_for(cat.endpoint, lang=_lang(), _external=False) + url
    return url


def _lang():
    from flask import request

    return (request.view_args or {}).get("lang", "en")


def _resolve_target(mode, url, cat, lang, from_service):
    """-> (href, external, variant) for a CTA mode, or None for 'inherit'."""
    if mode == "whatsapp":
        return biz.WHATSAPP_LINK, True, "whatsapp"
    if mode == "contact":
        return url_for("public.contact", lang=lang), False, "primary"
    if mode == "url" and url:
        href = _absolute_cta_url(cat, url) if from_service else url
        return href, href.startswith(("http://", "https://")), "primary"
    return None


def category_cta(cat, lang, from_service=False):
    if cat.slug == "nj-driver-license":
        # The old category-level CTA ("Get the Document Checklist" -> WhatsApp) predates the guided intake and
        # is a redundant/dead-end path now that one exists; route straight into it instead, same as the service
        # page's own CTA (`service_cta`), so the category hub and the service page never disagree.
        from app.driver_license import service as dl_service
        from app.student_auth import current_student

        student = current_student()
        active = student and dl_service.active_case(student)
        label = ("Continuar Mi Proceso" if lang == "es" else "Continue My Process") if active is not None else (
            "Ver qué necesito" if lang == "es" else "Check What I Need")
        return {"label": label, "href": url_for("public.dl_start", lang=lang), "external": False, "variant": "primary"}
    label = cat.cta_label(lang) or get_text(lang, "nav_get_started")
    target = _resolve_target(cat.cta_mode, cat.cta_url, cat, lang, from_service)
    href, external, variant = target or (url_for("public.contact", lang=lang), False, "primary")
    return {"label": label, "href": href, "external": external, "variant": variant}


def service_cta(svc, lang):
    """The primary button of a service page: intake if one is live, otherwise the
    service's own choice, otherwise the category's."""
    cat = svc.category
    from app.tax.registry import SERVICE_SLUG

    if svc.slug == SERVICE_SLUG and svc.cta_mode == "default":
        from app.tax import service as tax_service
        from app.student_auth import current_student

        student = current_student()
        active = student and tax_service.active_case(student)
        label = svc.cta_label(lang) or ("Empezar mi declaración" if lang == "es" else "Start my tax return")
        if active is not None:
            label = "Continuar tu declaración 2025" if lang == "es" else "Continue Your 2025 Tax Return"
        return {"label": label, "href": url_for("public.tax_start", lang=lang), "external": False, "variant": "primary"}
    from app.driver_license.seed import SERVICE_SLUG as DL_SERVICE_SLUG

    if svc.slug == DL_SERVICE_SLUG and svc.cta_mode == "default":
        from app.driver_license import service as dl_service
        from app.student_auth import current_student

        student = current_student()
        active = student and dl_service.active_case(student)
        label = svc.cta_label(lang) or ("Comenzar" if lang == "es" else "Get Started")
        if active is not None:
            label = "Continuar Mi Proceso" if lang == "es" else "Continue My Process"
        return {"label": label, "href": url_for("public.dl_start", lang=lang), "external": False, "variant": "primary"}
    from app.consent_travel.seed import SERVICE_SLUG as CT_SERVICE_SLUG

    if svc.slug == CT_SERVICE_SLUG and svc.cta_mode == "default":
        from app.consent_travel import service as ct_service
        from app.student_auth import current_student

        student = current_student()
        active = student and ct_service.active_case(student)
        label = svc.cta_label(lang) or ("Comenzar" if lang == "es" else "Get Started")
        if active is not None:
            label = "Continuar Mi Solicitud" if lang == "es" else "Continue My Application"
        return {"label": label, "href": url_for("public.ct_start", lang=lang), "external": False, "variant": "primary"}
    wants_intake = svc.cta_mode == "intake" or (svc.cta_mode == "default" and svc.has_intake)
    if wants_intake and svc.has_intake:
        from app.intake import find_draft
        from app.student_auth import current_student

        student = current_student()
        draft = student and find_draft(student, svc.form, svc)
        label = svc.cta_label(lang) or get_text(lang, "svc_cta_intake")
        if draft:
            label = get_text(lang, "acct_continue_editing" if draft.status == "reopened" else "svc_cta_continue")
        return {
            "label": label,
            "href": url_for("public.service_start", lang=lang, category_slug=cat.slug, service_slug=svc.slug),
            "external": False,
            "variant": "primary",
        }
    target = _resolve_target(svc.cta_mode, svc.cta_url, cat, lang, True)
    if target:
        href, external, variant = target
        return {"label": svc.cta_label(lang) or cat.cta_label(lang) or get_text(lang, "nav_get_started"), "href": href, "external": external, "variant": variant}
    inherited = category_cta(cat, lang, from_service=True)
    if svc.cta_label(lang):
        inherited["label"] = svc.cta_label(lang)
    return inherited


def _img(asset, width):
    return media_url(asset, width) if asset else None


def service_card(svc, lang, width=960):
    cat = svc.category
    return {
        "title": svc.title(lang),
        "text": svc.short(lang),
        "icon": svc.icon or cat.icon,
        "badge": svc.badge(lang),
        "url": url_for(cat.subpage_endpoint, lang=lang, slug=svc.slug) if cat.subpage_endpoint else url_for(cat.endpoint, lang=lang),
        "image": _img(svc.card_image, width),
        "focus": svc.card_focus,
        "featured": svc.is_featured,
        "category_title": cat.title(lang),
    }


def category_card(cat, lang, width=960):
    return {
        "title": cat.title(lang),
        "text": cat.short(lang),
        "icon": cat.icon,
        "url": url_for(cat.endpoint, lang=lang),
        "image": _img(cat.card_image, width),
        "focus": cat.card_focus,
        "featured": cat.is_featured,
    }


def _faq_jsonld(items, lang):
    return [
        {"@type": "Question", "name": i.title(lang), "acceptedAnswer": {"@type": "Answer", "text": i.body(lang)}}
        for i in items
        if i.body(lang)
    ]


def paragraphs(text):
    return [p.strip() for p in (text or "").replace("\r\n", "\n").split("\n\n") if p.strip()]


def category_secondary_cta(cat, lang):
    """Mirrors `service_secondary_cta` for a category hub page (currently only NJ Driver License's free
    Knowledge Test practice link)."""
    if cat.slug == "nj-driver-license":
        return {"label": ("Practicar el Examen Teórico — Gratis" if lang == "es" else "Practice Knowledge Test — Free"),
                "href": url_for("public.dl_practice_home", lang=lang), "icon": "check", "external": False}
    return None


def category_context(lang, cat):
    cards = [service_card(s, lang) for s in cat.published_services]
    faq = cat.items_of("faq")
    hero_url = _img(cat.hero_image, 1600)
    social = cat.social_image or cat.hero_image
    return {
        "category": cat,
        "cards": cards,
        "cta": category_cta(cat, lang),
        "secondary_cta": category_secondary_cta(cat, lang),
        "hero_url": hero_url,
        "hero_mobile_url": _img(cat.hero_mobile_image, 960),
        "overview_url": _img(cat.overview_image, 1600),
        "steps": cat.items_of("step"),
        "features": cat.items_of("feature"),
        "checklist": cat.items_of("checklist"),
        "included": cat.items_of("included"),
        "faq": faq,
        "faq_jsonld": _faq_jsonld(faq, lang),
        "content_paragraphs": paragraphs(cat.content(lang)),
        "page_description": cat.seo_description(lang),
        "page_title": cat.seo_title(lang),
        "page_image": url_for("media_asset", asset_id=social.id, name="share.webp", w=1600, _external=True) if social else None,
    }


def render_category(lang, slug, template="public/service_category.html", **extra):
    cat = get_category(slug)
    context = category_context(lang, cat)
    context.update(extra)
    return render_template(template, **context)


def legacy_subpage_links(lang, cat):
    """Shape the older per-category templates expect."""
    return [
        {
            "url": url_for(cat.subpage_endpoint, lang=lang, slug=s.slug),
            "title": s.title(lang),
            "icon": s.icon,
            "meta_description": s.short(lang),
        }
        for s in cat.published_services
    ]


def customer_application(svc, lang):
    """The signed-in customer's most relevant application for this service (open draft
    first, otherwise the latest submitted), shaped for the "Your application" panel."""
    if not svc.has_intake:
        return None
    from app.intake_engine import progress_for, status_key, status_label
    from app.models import FormSubmission
    from app.student_auth import current_student

    student = current_student()
    if not student:
        return None
    sub = (
        FormSubmission.query.filter_by(student_id=student.id, service_id=svc.id)
        .order_by(FormSubmission.is_complete.asc(), FormSubmission.updated_at.desc(), FormSubmission.id.desc())
        .first()
    )
    if not sub:
        return None
    if sub.is_complete:
        return {
            "draft": False, "status": status_key(sub), "label": status_label(sub, lang), "percent": 100,
            "updated_at": sub.updated_at or sub.submitted_at,
            "url": url_for("account.application_detail", lang=lang, submission_id=sub.id),
        }
    reopened = sub.status == "reopened"
    return {
        "draft": True, "status": status_key(sub), "label": status_label(sub, lang),
        "percent": 100 if reopened else progress_for(sub.form, sub)["percent"],
        "updated_at": sub.updated_at,
        "url": url_for("public.service_start", lang=lang, category_slug=svc.category.slug, service_slug=svc.slug),
    }


def service_secondary_cta(svc, lang):
    """An optional third hero button beyond the primary CTA and WhatsApp — currently only the NJ Driver License page's
    free Knowledge Test practice link. Public and does not require an account; starting practice itself does."""
    from app.driver_license.seed import SERVICE_SLUG as DL_SERVICE_SLUG

    if svc.slug == DL_SERVICE_SLUG:
        return {"label": ("Practicar el Examen Teórico — Gratis" if lang == "es" else "Practice Knowledge Test — Free"),
                "href": url_for("public.dl_practice_home", lang=lang), "icon": "check", "external": False}
    return None


def service_context(lang, cat, svc):
    area_served = []
    if svc.nj_in_person:
        area_served += [{"@type": "City", "name": f"{c}, NJ"} for c in biz.NJ_SERVICE_CITIES]
    if svc.tx_in_person:
        area_served += [{"@type": "City", "name": f"{c}, TX"} for c in biz.TX_SERVICE_CITIES]
    if svc.remote_nationwide:
        area_served.append({"@type": "Country", "name": "United States"})

    faq = svc.items_of("faq")
    related = [r for r in svc.related if r.is_published and r.category.is_published]
    social = svc.social_image or svc.hero_image or cat.social_image
    disclaimer = svc.disclaimer(lang) or cat.disclaimer(lang)
    return {
        "category": cat,
        "svc": svc,
        "cta": service_cta(svc, lang),
        "secondary_cta": service_secondary_cta(svc, lang),
        "application": customer_application(svc, lang),
        "hero_url": _img(svc.hero_image or cat.hero_image, 1600),
        "hero_mobile_url": _img(svc.hero_mobile_image or cat.hero_mobile_image, 960),
        "hero_focus": (svc.hero_focus if svc.hero_image else cat.hero_focus),
        "overview_url": _img(svc.overview_image, 1600),
        "when_needed": svc.items_of("when_needed"),
        "included": svc.items_of("included"),
        "faq": faq,
        "faq_jsonld": _faq_jsonld(faq, lang),
        "related_cards": [service_card(r, lang) for r in related],
        "content_paragraphs": paragraphs(svc.content(lang)),
        "disclaimer": disclaimer,
        "area_served_json": area_served,
        "scope_note": svc.scope_note(lang),
        "category_url": url_for(cat.endpoint, lang=lang, _external=True),
        "page_title": svc.seo_title(lang),
        "page_description": svc.seo_description(lang),
        "page_image": url_for("media_asset", asset_id=social.id, name="share.webp", w=1600, _external=True) if social else None,
        "whatsapp_enabled": svc.whatsapp_enabled,
    }


def render_service(lang, category_slug, service_slug):
    cat = get_category(category_slug)
    svc = Service.query.filter_by(category_id=cat.id, slug=service_slug).first()
    if not svc or not svc.is_published:
        abort(404)
    return render_template("public/service_detail.html", **service_context(lang, cat, svc))


def services_in_scope(lang, flag):
    """[{title, url}] of published services offered under a scope flag
    ('nj_in_person' | 'tx_in_person' | 'remote_nationwide')."""
    rows = (
        Service.query.join(ServiceCategory)
        .filter(Service.is_published.is_(True), ServiceCategory.is_published.is_(True), getattr(Service, flag).is_(True))
        .order_by(ServiceCategory.sort_order, Service.sort_order)
        .all()
    )
    return [{"title": s.title(lang), "url": url_for(s.category.subpage_endpoint, lang=lang, slug=s.slug)} for s in rows if s.category.subpage_endpoint]


def home_context(lang):
    """Everything the Home page needs, all from the CMS records."""
    from app.models import Course

    categories = ServiceCategory.query.filter_by(is_published=True).order_by(ServiceCategory.sort_order, ServiceCategory.id).all()
    popular = (
        Service.query.join(ServiceCategory)
        .filter(Service.is_published.is_(True), Service.is_featured.is_(True), ServiceCategory.is_published.is_(True))
        .order_by(ServiceCategory.sort_order, Service.sort_order)
        .all()
    )
    return {
        "featured": [category_card(c, lang) for c in categories if c.is_featured],
        "more": [category_card(c, lang) for c in categories if not c.is_featured],
        "popular": [service_card(s, lang) for s in popular],
        "courses": Course.query.filter_by(is_published=True).order_by(Course.sort_order, Course.id).limit(2).all(),
    }
