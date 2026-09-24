from flask import abort, flash, redirect, render_template, request, url_for

from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.models import NavItem, Page, ServiceCategory
from app.nav import SYSTEM_ITEMS


def _ordered():
    return NavItem.query.order_by(NavItem.sort_order, NavItem.id).all()


def _normalise(items):
    for i, item in enumerate(items, 1):
        item.sort_order = i * 10


@admin_bp.route("/navigation")
@admin_required
def navigation_list():
    from app.i18n import get_text

    items = _ordered()
    defaults = {k: (get_text("en", v[1]), get_text("es", v[1])) for k, v in SYSTEM_ITEMS.items()}
    pages = Page.query.filter_by(is_published=True).order_by(Page.title_en).all()
    categories = ServiceCategory.query.order_by(ServiceCategory.sort_order).all()
    return render_template("admin/navigation.html", items=items, defaults=defaults, pages=pages, categories=categories)


@admin_bp.route("/navigation/<int:item_id>/save", methods=["POST"])
@admin_required
def navigation_save(item_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    item = NavItem.query.get_or_404(item_id)
    item.label_en = request.form.get("label_en", "").strip() or None
    item.label_es = request.form.get("label_es", "").strip() or None
    item.is_visible = request.form.get("is_visible") == "on"
    if item.kind == "url":
        url = request.form.get("url", "").strip()
        if not url.startswith(("/", "https://", "http://", "tel:", "mailto:")) or "javascript:" in url.lower():
            flash("Link must start with /, https://, tel: or mailto:.", "error")
            return redirect(url_for("admin.navigation_list"))
        if not item.label_en:
            flash("A custom link needs a label.", "error")
            return redirect(url_for("admin.navigation_list"))
        item.url = url
    db.session.commit()
    flash("Menu item saved.", "success")
    return redirect(url_for("admin.navigation_list"))


@admin_bp.route("/navigation/<int:item_id>/move", methods=["POST"])
@admin_required
def navigation_move(item_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    item = NavItem.query.get_or_404(item_id)
    items = _ordered()
    _normalise(items)
    index = items.index(item)
    other_index = index - 1 if request.form.get("direction") == "up" else index + 1
    if 0 <= other_index < len(items):
        items[index].sort_order, items[other_index].sort_order = items[other_index].sort_order, items[index].sort_order
    db.session.commit()
    return redirect(url_for("admin.navigation_list"))


@admin_bp.route("/navigation/new", methods=["POST"])
@admin_required
def navigation_new():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    kind = request.form.get("kind")
    order = (max((i.sort_order for i in _ordered()), default=0)) + 10
    if kind == "page":
        page = db.session.get(Page, int(request.form.get("page_id", 0) or 0))
        if not page:
            flash("Choose a page.", "error")
            return redirect(url_for("admin.navigation_list"))
        db.session.add(NavItem(kind="page", page_id=page.id, sort_order=order))
    elif kind == "url":
        url = request.form.get("url", "").strip()
        label_en = request.form.get("label_en", "").strip()
        if not label_en or not url.startswith(("/", "https://", "http://", "tel:", "mailto:")) or "javascript:" in url.lower():
            flash("Give the link a label and a valid address (starting with /, https://, tel: or mailto:).", "error")
            return redirect(url_for("admin.navigation_list"))
        db.session.add(NavItem(kind="url", url=url, label_en=label_en, label_es=request.form.get("label_es", "").strip() or label_en, sort_order=order))
    else:
        abort(400)
    db.session.commit()
    flash("Menu item added.", "success")
    return redirect(url_for("admin.navigation_list"))


@admin_bp.route("/navigation/<int:item_id>/delete", methods=["POST"])
@admin_required
def navigation_delete(item_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    item = NavItem.query.get_or_404(item_id)
    if item.kind == "system":
        flash("Built-in menu items can be hidden or renamed, but not deleted.", "error")
        return redirect(url_for("admin.navigation_list"))
    db.session.delete(item)
    db.session.commit()
    flash("Menu item removed.", "success")
    return redirect(url_for("admin.navigation_list"))
