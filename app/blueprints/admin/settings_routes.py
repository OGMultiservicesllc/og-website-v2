from flask import abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.models import AdminUser, SiteSettings
from app.uploads import delete_course_media, save_course_media


@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    settings = SiteSettings.get()

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)

        settings.facebook_url = request.form.get("facebook_url", "").strip() or None
        settings.instagram_url = request.form.get("instagram_url", "").strip() or None
        settings.tiktok_url = request.form.get("tiktok_url", "").strip() or None
        settings.youtube_url = request.form.get("youtube_url", "").strip() or None
        settings.linkedin_url = request.form.get("linkedin_url", "").strip() or None

        settings.ga_measurement_id = request.form.get("ga_measurement_id", "").strip() or None
        settings.search_console_verification = request.form.get("search_console_verification", "").strip() or None
        settings.block_search_indexing = request.form.get("block_search_indexing") == "on"

        logo = request.files.get("logo")
        if logo and logo.filename:
            try:
                new_logo = save_course_media(logo, "image")
            except ValueError as exc:
                flash(str(exc), "error")
                return render_template("admin/settings.html", settings=settings, admin_users=AdminUser.query.order_by(AdminUser.created_at).all())
            if settings.logo_filename:
                delete_course_media(settings.logo_filename)
            settings.logo_filename = new_logo

        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("admin.settings"))

    return render_template("admin/settings.html", settings=settings, admin_users=AdminUser.query.order_by(AdminUser.created_at).all())


@admin_bp.route("/settings/logo/remove", methods=["POST"])
@admin_required
def settings_logo_remove():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    settings = SiteSettings.get()
    if settings.logo_filename:
        delete_course_media(settings.logo_filename)
        settings.logo_filename = None
        db.session.commit()
        flash("Custom logo removed — using the default logo again.", "success")
    return redirect(url_for("admin.settings"))


# ---------------------------------------------------------------- admin user accounts

@admin_bp.route("/settings/users/new", methods=["POST"])
@admin_required
def admin_user_new():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not name or not email or not password:
        flash("Name, email, and password are all required.", "error")
        return redirect(url_for("admin.settings"))
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("admin.settings"))
    if AdminUser.query.filter(AdminUser.email.ilike(email)).first():
        flash("An admin account with that email already exists.", "error")
        return redirect(url_for("admin.settings"))

    db.session.add(AdminUser(name=name, email=email, password_hash=generate_password_hash(password)))
    db.session.commit()
    flash(f"Admin account created for {name}.", "success")
    return redirect(url_for("admin.settings"))


@admin_bp.route("/settings/users/<int:user_id>/toggle-active", methods=["POST"])
@admin_required
def admin_user_toggle_active(user_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    user = AdminUser.query.get_or_404(user_id)

    if user.is_active and user.id == session.get("admin_user_id"):
        flash("You can't deactivate your own account while logged in as it.", "error")
        return redirect(url_for("admin.settings"))
    if user.is_active and AdminUser.query.filter_by(is_active=True).count() <= 1:
        flash("At least one admin account must stay active.", "error")
        return redirect(url_for("admin.settings"))

    user.is_active = not user.is_active
    db.session.commit()
    flash(f"{user.name} is now {'active' if user.is_active else 'inactive'}.", "success")
    return redirect(url_for("admin.settings"))


@admin_bp.route("/settings/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_user_delete(user_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    user = AdminUser.query.get_or_404(user_id)

    if user.id == session.get("admin_user_id"):
        flash("You can't delete your own account while logged in as it.", "error")
        return redirect(url_for("admin.settings"))
    if user.is_active and AdminUser.query.filter_by(is_active=True).count() <= 1:
        flash("At least one admin account must stay active.", "error")
        return redirect(url_for("admin.settings"))

    db.session.delete(user)
    db.session.commit()
    flash("Admin account deleted.", "success")
    return redirect(url_for("admin.settings"))


@admin_bp.route("/settings/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def admin_user_reset_password(user_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    user = AdminUser.query.get_or_404(user_id)
    password = request.form.get("password", "")

    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("admin.settings"))

    user.password_hash = generate_password_hash(password)
    db.session.commit()
    flash(f"Password updated for {user.name}.", "success")
    return redirect(url_for("admin.settings"))
