import re

from flask import abort, flash, redirect, render_template, request, url_for

from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.models import (
    CTA_MODES,
    Form,
    MEDIA_FOCUS,
    MediaAsset,
    Service,
    ServiceCategory,
    ServiceContentItem,
)

CATEGORY_TEXT_FIELDS = (
    "title", "short", "hero_badge", "hero_title", "hero_text", "intro_title", "intro_body", "contact_note",
    "info_title", "info_body", "content", "disclaimer", "final_cta_title", "final_cta_body", "cta_label",
    "checklist_title", "features_title", "included_title",
    "seo_title", "seo_description",
)
SERVICE_TEXT_FIELDS = (
    "title", "short", "hero_text", "content_title", "content", "disclaimer", "cta_label", "badge",
    "scope_note", "seo_title", "seo_description",
)
IMAGE_SLOT_COLUMNS = ("hero_image_id", "hero_mobile_image_id", "card_image_id", "overview_image_id", "social_image_id")

CATEGORY_ITEM_KINDS = (
    ("faq", "Common questions (FAQ)", "Question", "Answer"),
    ("step", "Process steps", "Step title", "Description"),
    ("feature", "Feature cards", "Title", "Description"),
    ("checklist", "Checklist / chips", "Item", None),
    ("included", "What's included", "Item", None),
)
SERVICE_ITEM_KINDS = (
    ("when_needed", "When you need this", "Situation", None),
    ("included", "What's included", "Item", None),
    ("faq", "Common questions (FAQ)", "Question", "Answer"),
)
ICON_CHOICES = (
    "immigration", "taxes", "translations", "notary", "apostille", "license", "officiant", "documents",
    "academy", "resources", "blog", "briefcase", "heart", "globe", "camera", "printer", "shield", "user",
    "star", "clock", "calendar", "mail", "phone", "pin", "edit",
)


def _slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-") or "service"


def _text(name):
    return (request.form.get(name) or "").strip()


def _apply_text_fields(obj, fields):
    for field in fields:
        for lang in ("en", "es"):
            setattr(obj, f"{field}_{lang}", _text(f"{field}_{lang}") or None)


def _apply_images(obj):
    for column in IMAGE_SLOT_COLUMNS:
        raw = _text(column)
        asset_id = int(raw) if raw.isdigit() else None
        if asset_id is not None and not db.session.get(MediaAsset, asset_id):
            asset_id = None
        setattr(obj, column, asset_id)
    for column in ("hero_focus", "card_focus"):
        value = _text(column)
        setattr(obj, column, value if value in MEDIA_FOCUS else "center")


def _apply_cta(obj):
    mode = _text("cta_mode")
    obj.cta_mode = mode if mode in CTA_MODES else "default"
    url = _text("cta_url")
    if url and not (url.startswith(("#", "/", "https://", "http://", "tel:", "mailto:")) and "javascript:" not in url.lower()):
        raise ValueError("Button link must start with #, /, https://, tel: or mailto:.")
    obj.cta_url = url or None
    obj.whatsapp_enabled = request.form.get("whatsapp_enabled") == "on"


def _apply_content_items(owner, kinds):
    """Rebuild the owner's repeating rows from the submitted arrays. Rows are
    posted in visual order; blank rows are skipped."""
    if request.form.get("items_present") != "1":
        return  # the lists weren't part of this submission; never wipe them by accident
    allowed = {k[0] for k in kinds}
    owner.items[:] = [i for i in owner.items if i.kind not in allowed]
    kind_list = request.form.getlist("item_kind")
    t_en = request.form.getlist("item_title_en")
    t_es = request.form.getlist("item_title_es")
    b_en = request.form.getlist("item_body_en")
    b_es = request.form.getlist("item_body_es")
    counters = {}
    for idx, kind in enumerate(kind_list):
        if kind not in allowed:
            continue
        title_en = (t_en[idx] if idx < len(t_en) else "").strip()
        title_es = (t_es[idx] if idx < len(t_es) else "").strip()
        if not title_en and not title_es:
            continue
        counters[kind] = counters.get(kind, 0) + 1
        body_en = (b_en[idx] if idx < len(b_en) else "").strip() or None
        body_es = (b_es[idx] if idx < len(b_es) else "").strip() or None
        owner.items.append(
            ServiceContentItem(
                kind=kind, sort_order=counters[kind], title_en=title_en or title_es, title_es=title_es or title_en,
                body_en=body_en or body_es, body_es=body_es or body_en,
            )
        )


def _swap(items, item, direction):
    index = items.index(item)
    other_index = index - 1 if direction == "up" else index + 1
    if other_index < 0 or other_index >= len(items):
        return
    other = items[other_index]
    item.sort_order, other.sort_order = other.sort_order, item.sort_order
    db.session.commit()


# ------------------------------------------------------------------ overview
@admin_bp.route("/services")
@admin_required
def services_list():
    categories = ServiceCategory.query.order_by(ServiceCategory.sort_order, ServiceCategory.id).all()
    return render_template("admin/services_list.html", categories=categories)


# ------------------------------------------------------------------ categories
@admin_bp.route("/services/categories/<int:category_id>", methods=["GET", "POST"])
@admin_required
def service_category_edit(category_id):
    cat = ServiceCategory.query.get_or_404(category_id)
    error = None
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        try:
            _apply_text_fields(cat, CATEGORY_TEXT_FIELDS)
            if not cat.title_en or not cat.title_es:
                raise ValueError("Title is required in English and Spanish.")
            cat.is_published = request.form.get("is_published") == "on"
            cat.show_in_nav = request.form.get("show_in_nav") == "on"
            cat.is_featured = request.form.get("is_featured") == "on"
            icon = _text("icon")
            cat.icon = icon if icon in ICON_CHOICES else cat.icon
            _apply_images(cat)
            _apply_cta(cat)
            _apply_content_items(cat, CATEGORY_ITEM_KINDS)
            db.session.commit()
            flash("Saved.", "success")
            return redirect(url_for("admin.service_category_edit", category_id=cat.id, tab=request.form.get("tab") or None))
        except ValueError as exc:
            db.session.rollback()
            error = str(exc)
            flash(error, "error")
    return render_template(
        "admin/service_category_form.html", cat=cat, item_kinds=CATEGORY_ITEM_KINDS, icons=ICON_CHOICES,
        cta_modes=CTA_MODES, tab=request.args.get("tab", "general"),
    )


# ------------------------------------------------------------------ services
def _form_choices():
    return Form.query.filter(Form.status != "archived", Form.form_type == "service_intake").order_by(Form.name_admin).all()


@admin_bp.route("/services/categories/<int:category_id>/new", methods=["POST"])
@admin_required
def service_new(category_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    cat = ServiceCategory.query.get_or_404(category_id)
    if not cat.subpage_endpoint:
        flash("This category is a single page and has no separate services.", "error")
        return redirect(url_for("admin.services_list"))
    title = _text("title_en")
    if not title:
        flash("Give the new service a name.", "error")
        return redirect(url_for("admin.services_list"))
    base = _slugify(title)
    slug, n = base, 2
    while Service.query.filter_by(category_id=cat.id, slug=slug).first():
        slug, n = f"{base}-{n}", n + 1
    service = Service(
        category_id=cat.id, slug=slug, admin_name=title, icon=cat.icon, title_en=title, title_es=_text("title_es") or title,
        is_published=False, sort_order=(max((s.sort_order for s in cat.services), default=0) + 10),
    )
    db.session.add(service)
    db.session.commit()
    flash("Service created as a draft. Fill it in, then publish.", "success")
    return redirect(url_for("admin.service_edit", service_id=service.id))


@admin_bp.route("/services/<int:service_id>", methods=["GET", "POST"])
@admin_required
def service_edit(service_id):
    svc = Service.query.get_or_404(service_id)
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        try:
            _apply_text_fields(svc, SERVICE_TEXT_FIELDS)
            if not svc.title_en or not svc.title_es:
                raise ValueError("Title is required in English and Spanish.")
            svc.admin_name = _text("admin_name") or svc.title_en
            svc.is_published = request.form.get("is_published") == "on"
            svc.is_featured = request.form.get("is_featured") == "on"
            icon = _text("icon")
            svc.icon = icon if icon in ICON_CHOICES else svc.icon

            if request.form.get("change_slug") == "on":
                new_slug = _slugify(_text("slug"))
                clash = Service.query.filter(Service.category_id == svc.category_id, Service.slug == new_slug, Service.id != svc.id).first()
                if clash:
                    raise ValueError("Another service in this category already uses that URL.")
                svc.slug = new_slug

            svc.nj_in_person = request.form.get("nj_in_person") == "on"
            svc.tx_in_person = request.form.get("tx_in_person") == "on"
            svc.remote_nationwide = request.form.get("remote_nationwide") == "on"

            _apply_images(svc)
            _apply_cta(svc)

            svc.requires_intake = request.form.get("requires_intake") == "on"
            form_id = _text("form_id")
            chosen = db.session.get(Form, int(form_id)) if form_id.isdigit() else None
            svc.form_id = chosen.id if chosen and chosen.form_type == "service_intake" else None
            svc.requires_account = request.form.get("requires_account") == "on"
            if svc.requires_intake and not svc.form_id:
                raise ValueError("Choose which form this service starts, or turn off \"Requires intake\".")

            related_ids = [int(v) for v in request.form.getlist("related_ids") if v.isdigit() and int(v) != svc.id]
            svc.related = Service.query.filter(Service.id.in_(related_ids)).all() if related_ids else []

            _apply_content_items(svc, SERVICE_ITEM_KINDS)
            db.session.commit()
            flash("Saved.", "success")
            return redirect(url_for("admin.service_edit", service_id=svc.id, tab=request.form.get("tab") or None))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
            svc = Service.query.get_or_404(service_id)
    siblings = Service.query.filter(Service.id != svc.id).order_by(Service.category_id, Service.sort_order).all()
    return render_template(
        "admin/service_form.html", svc=svc, item_kinds=SERVICE_ITEM_KINDS, icons=ICON_CHOICES, cta_modes=CTA_MODES,
        forms=_form_choices(), all_services=siblings, tab=request.args.get("tab", "general"),
    )


@admin_bp.route("/services/<int:service_id>/publish", methods=["POST"])
@admin_required
def service_toggle_publish(service_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    svc = Service.query.get_or_404(service_id)
    svc.is_published = not svc.is_published
    db.session.commit()
    flash(f"“{svc.title_en}” is now {'published' if svc.is_published else 'hidden (draft)'}.", "success")
    return redirect(url_for("admin.services_list") + f"#cat-{svc.category_id}")


@admin_bp.route("/services/<int:service_id>/move", methods=["POST"])
@admin_required
def service_move(service_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    svc = Service.query.get_or_404(service_id)
    siblings = Service.query.filter_by(category_id=svc.category_id).order_by(Service.sort_order, Service.id).all()
    for i, s in enumerate(siblings, 1):  # normalise so swaps always change order
        s.sort_order = i * 10
    db.session.flush()
    _swap(siblings, svc, request.form.get("direction"))
    return redirect(url_for("admin.services_list") + f"#cat-{svc.category_id}")


@admin_bp.route("/services/categories/<int:category_id>/move", methods=["POST"])
@admin_required
def service_category_move(category_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    cat = ServiceCategory.query.get_or_404(category_id)
    siblings = ServiceCategory.query.order_by(ServiceCategory.sort_order, ServiceCategory.id).all()
    for i, c in enumerate(siblings, 1):
        c.sort_order = i * 10
    db.session.flush()
    _swap(siblings, cat, request.form.get("direction"))
    return redirect(url_for("admin.services_list"))


@admin_bp.route("/services/<int:service_id>/delete", methods=["POST"])
@admin_required
def service_delete(service_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    svc = Service.query.get_or_404(service_id)
    category_id = svc.category_id
    svc.related = []
    for other in Service.query.filter(Service.related.any(Service.id == svc.id)).all():
        other.related.remove(svc)
    db.session.delete(svc)
    db.session.commit()
    flash("Service deleted.", "success")
    return redirect(url_for("admin.services_list") + f"#cat-{category_id}")
