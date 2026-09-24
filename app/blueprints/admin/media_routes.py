from flask import abort, flash, jsonify, redirect, render_template, request, url_for

from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.media_library import create_asset, delete_asset, media_url, replace_asset_file, usages
from app.models import MediaAsset


def _asset_json(asset):
    return {
        "id": asset.id,
        "title": asset.display_title,
        "alt_en": asset.alt_en or "",
        "url": media_url(asset, 480) or "",
        "width": asset.width,
        "height": asset.height,
        "tag": asset.tag or "",
    }


def _filtered(q, tag):
    query = MediaAsset.query
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            db.or_(MediaAsset.title.ilike(like), MediaAsset.original_filename.ilike(like), MediaAsset.alt_en.ilike(like), MediaAsset.alt_es.ilike(like), MediaAsset.tag.ilike(like))
        )
    if tag:
        query = query.filter(MediaAsset.tag == tag)
    return query.order_by(MediaAsset.created_at.desc(), MediaAsset.id.desc())


def _all_tags():
    return [t for (t,) in db.session.query(MediaAsset.tag).filter(MediaAsset.tag.isnot(None)).distinct().order_by(MediaAsset.tag)]


@admin_bp.route("/media")
@admin_required
def media_library():
    q = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()
    assets = _filtered(q, tag).all()
    return render_template("admin/media_library.html", assets=assets, q=q, tag=tag, tags=_all_tags(), media_url=media_url)


@admin_bp.route("/media/upload", methods=["POST"])
@admin_required
def media_upload():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    tag = request.form.get("tag", "")
    added, errors = 0, []
    for file in request.files.getlist("files"):
        if not file or not file.filename:
            continue
        try:
            if create_asset(file, tag=tag):
                added += 1
        except ValueError as exc:
            errors.append(f"{file.filename}: {exc}")
    db.session.commit()
    if added:
        flash(f"Uploaded {added} image{'s' if added != 1 else ''}.", "success")
    for message in errors:
        flash(message, "error")
    if not added and not errors:
        flash("Choose at least one image to upload.", "error")
    return redirect(url_for("admin.media_library"))


@admin_bp.route("/media/<int:asset_id>", methods=["GET", "POST"])
@admin_required
def media_detail(asset_id):
    asset = MediaAsset.query.get_or_404(asset_id)
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        asset.title = request.form.get("title", "").strip() or None
        asset.alt_en = request.form.get("alt_en", "").strip() or None
        asset.alt_es = request.form.get("alt_es", "").strip() or None
        asset.tag = request.form.get("tag", "").strip() or None
        db.session.commit()
        flash("Image details saved.", "success")
        return redirect(url_for("admin.media_detail", asset_id=asset.id))
    return render_template("admin/media_detail.html", asset=asset, usage=usages(asset.id), tags=_all_tags(), media_url=media_url)


@admin_bp.route("/media/<int:asset_id>/replace", methods=["POST"])
@admin_required
def media_replace(asset_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    asset = MediaAsset.query.get_or_404(asset_id)
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Choose an image to replace it with.", "error")
    else:
        try:
            replace_asset_file(asset, file)
            db.session.commit()
            flash("Image replaced everywhere it is used.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    return redirect(url_for("admin.media_detail", asset_id=asset.id))


@admin_bp.route("/media/<int:asset_id>/delete", methods=["POST"])
@admin_required
def media_delete(asset_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    asset = MediaAsset.query.get_or_404(asset_id)
    ok, message = delete_asset(asset)
    if ok:
        db.session.commit()
        flash("Image deleted.", "success")
        return redirect(url_for("admin.media_library"))
    flash(message, "error")
    return redirect(url_for("admin.media_detail", asset_id=asset.id))


# ---- JSON endpoints used by the reusable image picker on every editor
@admin_bp.route("/media/picker.json")
@admin_required
def media_picker_json():
    q = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()
    return jsonify({"assets": [_asset_json(a) for a in _filtered(q, tag).limit(120).all()], "tags": _all_tags()})


@admin_bp.route("/media/upload.json", methods=["POST"])
@admin_required
def media_upload_json():
    if not validate_csrf(request.headers.get("X-CSRFToken")):
        return jsonify({"error": "Session expired — reload the page."}), 400
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file received."}), 400
    try:
        asset = create_asset(file, tag=request.form.get("tag", ""))
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify({"asset": _asset_json(asset)})
