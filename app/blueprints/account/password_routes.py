"""Password reset (item 8) — a brand-new flow; nothing like it existed in this project before. Never
reveals whether an email belongs to an account (item 8, enumeration protection): forgot_password() always
renders the same "if an account exists…" outcome regardless of what `password_reset.request_reset` did
internally."""

from flask import abort, flash, redirect, render_template, request, url_for

from app import password_reset
from app.auth import validate_csrf
from app.blueprints.account.routes import account_bp
from app.i18n import get_text
from app.ratelimit import client_ip
from app.student_auth import current_student


@account_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password(lang):
    if current_student():
        return redirect(url_for("account.dashboard", lang=lang))
    sent = False
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        password_reset.request_reset(request.form.get("email", ""), lang, ip=client_ip())
        sent = True
    return render_template("account/forgot_password.html", sent=sent)


@account_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(lang, token):
    if current_student():
        return redirect(url_for("account.dashboard", lang=lang))
    row = password_reset.find_active_token(token)
    if row is None:
        return render_template("account/reset_password.html", invalid=True)

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        new_password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(new_password) < 8:
            flash(get_text(lang, "flash_password_short"), "error")
        elif new_password != confirm:
            flash(get_text(lang, "reset_password_mismatch"), "error")
        else:
            password_reset.complete_reset(row, new_password)
            flash(get_text(lang, "reset_password_success"), "success")
            return redirect(url_for("account.login", lang=lang))
    return render_template("account/reset_password.html", invalid=False, token=token)
