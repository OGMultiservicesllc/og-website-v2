import os

from flask import abort, flash, redirect, render_template, request, send_file, url_for

from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.models import Inquiry
from app.uploads import course_media_full_path


@admin_bp.route("/inquiries")
@admin_required
def inquiries_list():
    status = request.args.get("status", "")
    query = Inquiry.query
    if status:
        query = query.filter_by(status=status)
    inquiries = query.order_by(Inquiry.created_at.desc()).all()
    counts = {
        "new": Inquiry.query.filter_by(status="new").count(),
        "contacted": Inquiry.query.filter_by(status="contacted").count(),
        "closed": Inquiry.query.filter_by(status="closed").count(),
    }
    return render_template("admin/inquiries_list.html", inquiries=inquiries, status=status, counts=counts)


@admin_bp.route("/inquiries/<int:inquiry_id>")
@admin_required
def inquiry_detail(inquiry_id):
    inquiry = Inquiry.query.get_or_404(inquiry_id)
    return render_template("admin/inquiry_detail.html", inquiry=inquiry)


@admin_bp.route("/inquiries/<int:inquiry_id>/status", methods=["POST"])
@admin_required
def inquiry_status(inquiry_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    inquiry = Inquiry.query.get_or_404(inquiry_id)
    new_status = request.form.get("status")
    if new_status in ("new", "contacted", "closed"):
        inquiry.status = new_status
        db.session.commit()
        flash("Status updated.", "success")
    return redirect(url_for("admin.inquiry_detail", inquiry_id=inquiry.id))


@admin_bp.route("/inquiries/<int:inquiry_id>/file")
@admin_required
def inquiry_file(inquiry_id):
    inquiry = Inquiry.query.get_or_404(inquiry_id)
    if not inquiry.file_filename:
        abort(404)
    full_path = course_media_full_path(inquiry.file_filename)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path, conditional=True)
