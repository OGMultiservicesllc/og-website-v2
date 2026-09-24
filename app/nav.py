from app.models import Page


def pages_for_section(section_key):
    return (
        Page.query.filter_by(
            parent_section=section_key, parent_page_id=None, is_published=True, show_in_menu=True
        )
        .order_by(Page.sort_order)
        .all()
    )


def standalone_top_pages():
    return (
        Page.query.filter_by(parent_page_id=None, parent_section=None, is_published=True, show_in_menu=True)
        .order_by(Page.sort_order)
        .all()
    )


# ---------------------------------------------------------------- header menu (Admin -> Website -> Navigation)
SYSTEM_ITEMS = {
    "home": ("public.home", "nav_home"),
    "services": (None, "nav_services"),  # dropdown of service categories
    "about": ("public.about", "nav_about"),
    "academy": ("public.courses", "nav_courses"),
    "blog": ("public.blog", "nav_blog"),
    "contact": ("public.contact", "nav_contact"),
}


def main_nav(lang):
    """The visible header entries, in order, ready to render:
    [{key, label, href, kind, external}]. `kind` is home|services|academy|page|link."""
    from flask import url_for

    from app.i18n import get_text
    from app.models import NavItem

    entries = []
    for item in NavItem.query.filter_by(is_visible=True).order_by(NavItem.sort_order, NavItem.id).all():
        if item.kind == "system":
            endpoint, default_key = SYSTEM_ITEMS.get(item.system_key, (None, None))
            if not default_key:
                continue
            href = url_for(endpoint, lang=lang) if endpoint else None
            entries.append({"key": item.system_key, "label": item.label(lang) or get_text(lang, default_key), "href": href, "kind": item.system_key, "external": False})
        elif item.kind == "page":
            if not item.page or not item.page.is_published:
                continue
            entries.append({"key": f"page-{item.id}", "label": item.label(lang) or item.page.title(lang), "href": url_for("public.page_view", lang=lang, slug=item.page.slug), "kind": "link", "external": False})
        else:
            if not item.url:
                continue
            entries.append({"key": f"url-{item.id}", "label": item.label(lang), "href": item.url, "kind": "link", "external": item.url.startswith(("http://", "https://"))})
    return entries


def nav_categories(lang):
    """Published service categories that appear in the Services menu."""
    from flask import url_for

    from app.models import ServiceCategory

    return [
        {"title": c.title(lang), "icon": c.icon, "href": url_for(c.endpoint, lang=lang)}
        for c in ServiceCategory.query.filter_by(is_published=True, show_in_nav=True).order_by(ServiceCategory.sort_order, ServiceCategory.id).all()
    ]
