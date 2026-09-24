from flask import abort, flash, redirect, render_template, request, url_for

from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.i18n import get_text
from app.models import MediaAsset
from app.site_content import SITE_PAGES, all_fields, save_site_fields, site_asset, site_value


@admin_bp.route("/website")
@admin_required
def website_home():
    return redirect(url_for("admin.site_page_edit", page_key="home"))


@admin_bp.route("/website/<page_key>", methods=["GET", "POST"])
@admin_required
def site_page_edit(page_key):
    page = SITE_PAGES.get(page_key)
    if not page:
        abort(404)
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        form = request.form.copy()
        # Only accept image ids that exist in the library.
        for field in all_fields(page_key):
            if field["type"] == "image":
                raw = (form.get(f"{field['key']}__en") or "").strip()
                if raw and not (raw.isdigit() and db.session.get(MediaAsset, int(raw))):
                    form[f"{field['key']}__en"] = ""
        save_site_fields(page_key, form)
        flash("Saved.", "success")
        return redirect(url_for("admin.site_page_edit", page_key=page_key, tab=request.form.get("tab") or None))

    # Current override (or empty) plus the built-in default to show as a placeholder.
    values, defaults, assets = {}, {}, {}
    from app.models import PageBlock

    blocks = {b.key: b for b in PageBlock.query.filter(PageBlock.key.in_([f["key"] for f in all_fields(page_key)])).all()}
    for field in all_fields(page_key):
        key = field["key"]
        block = blocks.get(key)
        values[key] = {"en": (block.content_en if block else "") or "", "es": (block.content_es if block else "") or ""}
        if field["type"] in ("text", "textarea"):
            defaults[key] = {"en": get_text("en", key), "es": get_text("es", key)}
        if field["type"] == "image":
            assets[key] = site_asset(key) if site_value(key) else None
    return render_template(
        "admin/site_page_form.html", page_key=page_key, page=page, pages=SITE_PAGES, values=values,
        defaults=defaults, assets=assets, tabs=[(sec["id"], sec["label"]) for sec in page["sections"]], tab=request.args.get("tab", page["sections"][0]["id"]),
    )


@admin_bp.route("/content")
@admin_required
def legacy_content_redirect():
    """Old bookmark for the retired "Flagship Page Text" screen."""
    flash("That screen has moved: page text is now edited under Services and Website.", "success")
    return redirect(url_for("admin.services_list"))
