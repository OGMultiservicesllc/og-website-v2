from flask import abort, redirect, render_template, request, url_for

from app import notifications as notif
from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.models import NOTIFICATION_GROUPS


@admin_bp.route("/notifications")
@admin_required
def notifications_center():
    group = request.args.get("group") or None
    if group not in NOTIFICATION_GROUPS:
        group = None
    unread_only = request.args.get("filter") == "unread"
    items = notif.list_for_center(group=group, unread_only=unread_only, limit=100)
    return render_template(
        "admin/notifications.html", items=items, group=group, unread_only=unread_only,
        groups=NOTIFICATION_GROUPS, unread_count=notif.unread_count(),
    )


@admin_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@admin_required
def notification_mark_read(notification_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    n = notif.mark_read(notification_id)
    next_url = request.form.get("next") or (n.link_url if n and n.link_url else url_for("admin.notifications_center"))
    return redirect(next_url)


@admin_bp.route("/notifications/mark-all-read", methods=["POST"])
@admin_required
def notifications_mark_all_read():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    notif.mark_all_read()
    return redirect(request.form.get("next") or url_for("admin.notifications_center"))
