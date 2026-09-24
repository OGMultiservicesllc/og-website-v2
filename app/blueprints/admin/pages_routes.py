import re

from flask import abort, flash, redirect, render_template, request, url_for

from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.models import BLOCK_TYPES, CustomForm, NAV_SECTIONS, Page, PageSection
from app.uploads import delete_course_media, save_course_media


def _slugify(value):
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "page"


def _unique_slug(base_slug, page_id=None):
    slug = base_slug
    n = 2
    while True:
        query = Page.query.filter_by(slug=slug)
        if page_id:
            query = query.filter(Page.id != page_id)
        if not query.first():
            return slug
        slug = f"{base_slug}-{n}"
        n += 1


def _next_sort_order(items):
    return (max((i.sort_order for i in items), default=0)) + 1


def _parse_parent(value):
    """value is 'section:<key>', 'page:<id>', or '' (no parent)."""
    if not value:
        return None, None
    kind, _, raw = value.partition(":")
    if kind == "section" and raw in NAV_SECTIONS:
        return None, raw
    if kind == "page" and raw.isdigit():
        return int(raw), None
    return None, None


def _parent_value(page):
    if page.parent_section:
        return f"section:{page.parent_section}"
    if page.parent_page_id:
        return f"page:{page.parent_page_id}"
    return ""


def _siblings(page):
    if page.parent_page_id:
        return list(Page.query.filter_by(parent_page_id=page.parent_page_id).order_by(Page.sort_order).all())
    if page.parent_section:
        return list(
            Page.query.filter_by(parent_section=page.parent_section, parent_page_id=None)
            .order_by(Page.sort_order)
            .all()
        )
    return list(
        Page.query.filter_by(parent_page_id=None, parent_section=None).order_by(Page.sort_order).all()
    )


def _swap_sort_order(siblings, item, direction):
    index = siblings.index(item)
    if direction == "up" and index > 0:
        other = siblings[index - 1]
    elif direction == "down" and index < len(siblings) - 1:
        other = siblings[index + 1]
    else:
        return
    item.sort_order, other.sort_order = other.sort_order, item.sort_order
    db.session.commit()


def _page_choices(exclude_id=None):
    """Flat list of (depth, page) for building an indented <select>, excluding
    a page and its descendants (to prevent cycles when picking a parent)."""
    all_pages = Page.query.order_by(Page.sort_order).all()
    by_parent = {}
    for p in all_pages:
        by_parent.setdefault(p.parent_page_id, []).append(p)

    excluded = set()
    if exclude_id:
        def collect(pid):
            excluded.add(pid)
            for child in by_parent.get(pid, []):
                collect(child.id)
        collect(exclude_id)

    choices = []

    def walk(parent_id, depth):
        for p in by_parent.get(parent_id, []):
            if p.id in excluded:
                continue
            choices.append((depth, p))
            walk(p.id, depth + 1)

    walk(None, 0)
    return choices


@admin_bp.route("/pages")
@admin_required
def pages_list():
    top_level = (
        Page.query.filter_by(parent_page_id=None, parent_section=None).order_by(Page.sort_order).all()
    )
    by_section = {
        key: Page.query.filter_by(parent_section=key, parent_page_id=None).order_by(Page.sort_order).all()
        for key in NAV_SECTIONS
    }
    return render_template(
        "admin/pages_list.html",
        top_level=top_level,
        by_section=by_section,
        nav_sections=NAV_SECTIONS,
    )


@admin_bp.route("/pages/new", methods=["GET", "POST"])
@admin_required
def page_new():
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        title_en = request.form.get("title_en", "").strip()
        title_es = request.form.get("title_es", "").strip()
        if not title_en or not title_es:
            flash("Title (EN and ES) is required.", "error")
            return render_template("admin/page_form.html", page=None, page_choices=_page_choices(), nav_sections=NAV_SECTIONS)

        parent_page_id, parent_section = _parse_parent(request.form.get("parent", ""))
        slug = _unique_slug(_slugify(title_en))

        page = Page(
            slug=slug,
            title_en=title_en,
            title_es=title_es,
            content_en=request.form.get("content_en", "").strip(),
            content_es=request.form.get("content_es", "").strip(),
            seo_title_en=request.form.get("seo_title_en", "").strip(),
            seo_title_es=request.form.get("seo_title_es", "").strip(),
            seo_description_en=request.form.get("seo_description_en", "").strip(),
            seo_description_es=request.form.get("seo_description_es", "").strip(),
            parent_page_id=parent_page_id,
            parent_section=parent_section,
            show_in_menu=request.form.get("show_in_menu") == "on",
            is_published=request.form.get("is_published") == "on",
        )
        siblings_query = (
            Page.query.filter_by(parent_page_id=parent_page_id)
            if parent_page_id
            else Page.query.filter_by(parent_section=parent_section, parent_page_id=None)
        )
        page.sort_order = _next_sort_order(siblings_query.all())

        db.session.add(page)
        db.session.commit()
        flash("Page created.", "success")
        return redirect(url_for("admin.pages_list"))

    return render_template("admin/page_form.html", page=None, page_choices=_page_choices(), nav_sections=NAV_SECTIONS)


def _linkable_pages(exclude_id=None):
    query = Page.query.order_by(Page.title_en)
    if exclude_id:
        query = query.filter(Page.id != exclude_id)
    return query.all()


@admin_bp.route("/pages/<int:page_id>/edit", methods=["GET", "POST"])
@admin_required
def page_edit(page_id):
    page = Page.query.get_or_404(page_id)

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        title_en = request.form.get("title_en", "").strip()
        title_es = request.form.get("title_es", "").strip()
        if not title_en or not title_es:
            flash("Title (EN and ES) is required.", "error")
            return render_template(
                "admin/page_form.html", page=page, page_choices=_page_choices(exclude_id=page.id), nav_sections=NAV_SECTIONS,
                linkable_pages=_linkable_pages(exclude_id=page.id), block_types=BLOCK_TYPES,
                forms=CustomForm.query.order_by(CustomForm.name_admin).all(),
            )

        parent_page_id, parent_section = _parse_parent(request.form.get("parent", ""))
        if parent_page_id == page.id:
            flash("A page can't be its own parent.", "error")
            return render_template(
                "admin/page_form.html", page=page, page_choices=_page_choices(exclude_id=page.id), nav_sections=NAV_SECTIONS,
                linkable_pages=_linkable_pages(exclude_id=page.id), block_types=BLOCK_TYPES,
                forms=CustomForm.query.order_by(CustomForm.name_admin).all(),
            )

        page.title_en = title_en
        page.title_es = title_es
        page.content_en = request.form.get("content_en", "").strip()
        page.content_es = request.form.get("content_es", "").strip()
        page.seo_title_en = request.form.get("seo_title_en", "").strip()
        page.seo_title_es = request.form.get("seo_title_es", "").strip()
        page.seo_description_en = request.form.get("seo_description_en", "").strip()
        page.seo_description_es = request.form.get("seo_description_es", "").strip()
        page.parent_page_id = parent_page_id
        page.parent_section = parent_section
        page.show_in_menu = request.form.get("show_in_menu") == "on"
        page.is_published = request.form.get("is_published") == "on"
        db.session.commit()
        flash("Page updated.", "success")
        return redirect(url_for("admin.pages_list"))

    return render_template(
        "admin/page_form.html", page=page, page_choices=_page_choices(exclude_id=page.id), nav_sections=NAV_SECTIONS,
        linkable_pages=_linkable_pages(exclude_id=page.id), block_types=BLOCK_TYPES,
        forms=CustomForm.query.order_by(CustomForm.name_admin).all(),
    )


@admin_bp.route("/pages/<int:page_id>/duplicate", methods=["POST"])
@admin_required
def page_duplicate(page_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    original = Page.query.get_or_404(page_id)

    copy = Page(
        slug=_unique_slug(_slugify(original.title_en + "-copy")),
        title_en=original.title_en + " (Copy)",
        title_es=original.title_es + " (Copia)",
        content_en=original.content_en,
        content_es=original.content_es,
        seo_title_en=original.seo_title_en,
        seo_title_es=original.seo_title_es,
        seo_description_en=original.seo_description_en,
        seo_description_es=original.seo_description_es,
        parent_page_id=original.parent_page_id,
        parent_section=original.parent_section,
        show_in_menu=original.show_in_menu,
        is_published=False,
    )
    copy.sort_order = _next_sort_order(_siblings(original))
    db.session.add(copy)
    db.session.commit()
    flash("Page duplicated as a draft.", "success")
    return redirect(url_for("admin.pages_list"))


@admin_bp.route("/pages/<int:page_id>/delete", methods=["POST"])
@admin_required
def page_delete(page_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    page = Page.query.get_or_404(page_id)

    if page.children:
        flash("Move or delete this page's sub-pages first.", "error")
        return redirect(url_for("admin.pages_list"))

    db.session.delete(page)
    db.session.commit()
    flash("Page deleted.", "success")
    return redirect(url_for("admin.pages_list"))


@admin_bp.route("/pages/<int:page_id>/move", methods=["POST"])
@admin_required
def page_move(page_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    page = Page.query.get_or_404(page_id)
    direction = request.form.get("direction")
    _swap_sort_order(_siblings(page), page, direction)
    return redirect(url_for("admin.pages_list"))


# ---------------------------------------------------------------- page sections (elements)

def _apply_section_fields(section, form, files):
    block_type = form.get("block_type", "text")
    if block_type not in BLOCK_TYPES:
        block_type = "text"
    section.block_type = block_type

    section.heading_en = form.get("heading_en", "").strip()
    section.heading_es = form.get("heading_es", "").strip()
    section.button_label_en = form.get("button_label_en", "").strip()
    section.button_label_es = form.get("button_label_es", "").strip()

    link_page_id = form.get("link_page_id", "").strip()
    section.link_page_id = int(link_page_id) if link_page_id.isdigit() else None
    section.link_url = form.get("link_url", "").strip() or None

    custom_form_id = form.get("custom_form_id", "").strip()
    section.custom_form_id = int(custom_form_id) if custom_form_id.isdigit() else None

    if block_type == "image":
        section.text_en = form.get("image_caption_en", "").strip()
        section.text_es = form.get("image_caption_es", "").strip()
        uploaded = files.get("image_file")
        if uploaded and uploaded.filename:
            if section.image_filename:
                delete_course_media(section.image_filename)
            section.image_filename = save_course_media(uploaded, "image")
    else:
        section.text_en = form.get("text_en", "").strip()
        section.text_es = form.get("text_es", "").strip()


@admin_bp.route("/pages/<int:page_id>/sections/new", methods=["POST"])
@admin_required
def page_section_new(page_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    page = Page.query.get_or_404(page_id)

    section = PageSection(page_id=page.id, sort_order=_next_sort_order(page.sections))
    try:
        _apply_section_fields(section, request.form, request.files)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin.page_edit", page_id=page.id))

    db.session.add(section)
    db.session.commit()
    flash("Element added.", "success")
    return redirect(url_for("admin.page_edit", page_id=page.id))


@admin_bp.route("/pages/sections/<int:section_id>/edit", methods=["POST"])
@admin_required
def page_section_edit(section_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    section = PageSection.query.get_or_404(section_id)

    try:
        _apply_section_fields(section, request.form, request.files)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin.page_edit", page_id=section.page_id))

    db.session.commit()
    flash("Element updated.", "success")
    return redirect(url_for("admin.page_edit", page_id=section.page_id))


@admin_bp.route("/pages/sections/<int:section_id>/delete", methods=["POST"])
@admin_required
def page_section_delete(section_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    section = PageSection.query.get_or_404(section_id)
    page_id = section.page_id
    if section.image_filename:
        delete_course_media(section.image_filename)
    db.session.delete(section)
    db.session.commit()
    flash("Element removed.", "success")
    return redirect(url_for("admin.page_edit", page_id=page_id))


@admin_bp.route("/pages/sections/<int:section_id>/move", methods=["POST"])
@admin_required
def page_section_move(section_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    section = PageSection.query.get_or_404(section_id)
    direction = request.form.get("direction")
    siblings = list(PageSection.query.filter_by(page_id=section.page_id).order_by(PageSection.sort_order).all())
    _swap_sort_order(siblings, section, direction)
    return redirect(url_for("admin.page_edit", page_id=section.page_id))
