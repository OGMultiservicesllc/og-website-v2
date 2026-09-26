from flask import abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.models import AdminUser, MediaAsset, NOTIFICATION_EVENTS, NotificationSetting, SiteSettings
from app.uploads import delete_course_media, save_course_media

#: The 4 new branding slots (2026-09-26, see docs/BRANDING.md) — each a nullable MediaAsset
#: reference, submitted by the shared image_slot()/_media_modal.html picker as a hidden input
#: named "<field>". Listed once here so the POST handler and the GET render context can never
#: drift apart on which fields exist.
BRANDING_MEDIA_FIELDS = ("admin_logo_media_id", "favicon_media_id", "email_logo_media_id", "social_logo_media_id")


def _branding_assets(settings):
    """{field_name: MediaAsset or None} for the current settings row — passed to settings.html so
    each image_slot() can render its own preview."""
    ids = {f: getattr(settings, f) for f in BRANDING_MEDIA_FIELDS}
    assets = {a.id: a for a in MediaAsset.query.filter(MediaAsset.id.in_([v for v in ids.values() if v])).all()}
    return {f: assets.get(v) for f, v in ids.items()}


def _notification_settings_rows():
    """Every event's setting row, seeded already by app.notifications.ensure_seed() at startup — this
    just orders them for display, so a fresh-install DB (seed not yet run) never 500s on Settings."""
    from app import notifications as notif

    notif.ensure_seed()
    rows = {s.event_key: s for s in NotificationSetting.query.all()}
    return [(key, label, group, rows.get(key)) for key, (label, group, _ad, _em) in NOTIFICATION_EVENTS.items()]


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
                return render_template("admin/settings.html", settings=settings, admin_users=AdminUser.query.order_by(AdminUser.created_at).all(),
                                      notification_rows=_notification_settings_rows(), branding_assets=_branding_assets(settings))
            if settings.logo_filename:
                delete_course_media(settings.logo_filename)
            settings.logo_filename = new_logo

        for field in BRANDING_MEDIA_FIELDS:
            setattr(settings, field, request.form.get(field, type=int) or None)

        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("admin.settings"))

    return render_template("admin/settings.html", settings=settings, admin_users=AdminUser.query.order_by(AdminUser.created_at).all(),
                          notification_rows=_notification_settings_rows(), branding_assets=_branding_assets(settings))


@admin_bp.route("/settings/notifications", methods=["POST"])
@admin_required
def notification_settings():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)

    settings = SiteSettings.get()
    settings.notification_recipient_email = request.form.get("notification_recipient_email", "").strip() or None

    rows = {s.event_key: s for s in NotificationSetting.query.all()}
    for key in NOTIFICATION_EVENTS:
        row = rows.get(key)
        if row is None:
            continue
        row.admin_enabled = request.form.get(f"admin_{key}") == "on"
        row.email_enabled = request.form.get(f"email_{key}") == "on"

    db.session.commit()
    flash("Notification settings saved.", "success")
    return redirect(url_for("admin.settings"))


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
