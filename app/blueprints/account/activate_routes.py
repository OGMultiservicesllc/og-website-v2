"""Account activation for Wix-migrated customers (see app/account_invitations.py). No customer
enumeration: an invalid/expired/consumed token always renders the identical "invalid" screen, never a
hint about whether the token ever existed or which account it belonged to."""
from flask import abort, flash, redirect, render_template, request, session, url_for

from app import account_invitations
from app.auth import validate_csrf
from app.blueprints.account.routes import account_bp
from app.i18n import get_text
from app.student_auth import current_student


@account_bp.route("/activate/<token>", methods=["GET", "POST"])
def activate(lang, token):
    if current_student():
        return redirect(url_for("account.dashboard", lang=lang))
    inv = account_invitations.find_active_token(token)
    if inv is None:
        return render_template("account/activate.html", invalid=True)

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        new_password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(new_password) < 8:
            flash(get_text(lang, "flash_password_short"), "error")
        elif new_password != confirm:
            flash(get_text(lang, "activate_mismatch"), "error")
        else:
            student = account_invitations.activate(inv, new_password)
            session.clear()
            session["student_id"] = student.id
            flash(get_text(lang, "activate_success"), "success")
            return redirect(url_for("account.dashboard", lang=lang))
    return render_template("account/activate.html", invalid=False, student=inv.student, token=token)
