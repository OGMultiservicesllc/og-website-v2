"""Mandatory email verification screens (item 4/5/6). NOT decorated with @student_required — that
decorator itself redirects an unverified student HERE, so using it on these routes would loop. Instead
each view checks `current_student()` directly (must be signed in) and bounces away once verified."""

from flask import abort, flash, redirect, render_template, request, url_for

from app import verification
from app.auth import validate_csrf
from app.blueprints.account.routes import _safe_next, account_bp
from app.i18n import get_text
from app.models import Student
from app.student_auth import current_student

ERROR_KEYS = {
    "expired": "verify_error_expired",
    "too_many_attempts": "verify_error_too_many",
    "wrong_code": "verify_error_wrong",
    "rate_limited": "flash_too_many",
}


@account_bp.route("/verify-email", methods=["GET", "POST"])
def verify_email(lang):
    student = current_student()
    if not student:
        return redirect(url_for("account.login", lang=lang, next=request.path))
    if student.is_email_verified:
        return redirect(_safe_next(lang, request.args.get("next")))

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        ok, error = verification.verify_code(student, "verify", request.form.get("code", ""))
        if ok:
            flash(get_text(lang, "verify_success"), "success")
            return redirect(_safe_next(lang, request.form.get("next") or request.args.get("next")))
        flash(get_text(lang, ERROR_KEYS.get(error, "verify_error_wrong")), "error")

    return render_template(
        "account/verify_email.html", masked_email=verification.masked_target_email(student, "verify"),
        next=request.args.get("next"), purpose="verify",
        show_change_email=True,
    )


@account_bp.route("/verify-email/resend", methods=["POST"])
def verify_email_resend(lang):
    student = current_student()
    if not student:
        return redirect(url_for("account.login", lang=lang))
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    purpose = request.form.get("purpose", "verify")
    if purpose not in ("verify", "change_email"):
        purpose = "verify"
    if student.is_email_verified and purpose == "verify":
        return redirect(url_for("account.dashboard", lang=lang))

    ok, reason = verification.can_resend(student, purpose)
    if ok:
        pending = verification.active_code(student, "change_email")
        pending_email = pending.pending_email if (purpose == "change_email" and pending) else None
        verification.issue_code(student, purpose, lang=lang, pending_email=pending_email)
        flash(get_text(lang, "verify_resent"), "success")
    elif reason == "cooldown":
        flash(get_text(lang, "verify_error_cooldown"), "error")
    else:
        flash(get_text(lang, "flash_too_many"), "error")

    next_url = request.form.get("next")
    target = "account.verify_email_pending_change" if purpose == "change_email" else "account.verify_email"
    return redirect(url_for(target, lang=lang, next=next_url) if next_url else url_for(target, lang=lang))


@account_bp.route("/verify-email/change", methods=["GET", "POST"])
def verify_email_change(lang):
    """One shared "enter a new email + verify it" flow used by BOTH item 6 (fix a mistyped address before
    ever verifying) and item 7 (Profile & Settings > Change Email, for an already-verified customer) — the
    mechanics are identical (a code sent to the candidate address, confirmed before it replaces the old
    one); only the destination after success differs, via `next` (Profile passes its own URL explicitly —
    see the "Change" link in account/profile.html)."""
    student = current_student()
    if not student:
        return redirect(url_for("account.login", lang=lang))

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        new_email = request.form.get("email", "").strip().lower()
        if not new_email or "@" not in new_email:
            flash(get_text(lang, "flash_email_invalid"), "error")
        elif Student.query.filter(Student.email == new_email, Student.id != student.id).first():
            flash(get_text(lang, "flash_email_taken"), "error")
        else:
            ok, reason = verification.can_resend(student, "change_email")
            if not ok:
                flash(get_text(lang, "verify_error_cooldown" if reason == "cooldown" else "flash_too_many"), "error")
            else:
                verification.issue_code(student, "change_email", lang=lang, pending_email=new_email)
                next_url = request.form.get("next")
                return redirect(url_for("account.verify_email_pending_change", lang=lang, next=next_url) if next_url else url_for("account.verify_email_pending_change", lang=lang))

    return render_template("account/verify_email_change.html", current_email=student.email, next=request.args.get("next"))


@account_bp.route("/verify-email/pending-change", methods=["GET", "POST"])
def verify_email_pending_change(lang):
    student = current_student()
    if not student:
        return redirect(url_for("account.login", lang=lang))
    row = verification.active_code(student, "change_email")
    if row is None:
        return redirect(url_for("account.verify_email_change", lang=lang))

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        ok, error = verification.verify_code(student, "change_email", request.form.get("code", ""))
        if ok:
            flash(get_text(lang, "verify_email_changed_success"), "success")
            dest = request.form.get("next") or request.args.get("next")
            return redirect(_safe_next(lang, dest))
        flash(get_text(lang, ERROR_KEYS.get(error, "verify_error_wrong")), "error")

    return render_template(
        "account/verify_email.html", masked_email=verification.masked_target_email(student, "change_email"),
        next=request.args.get("next"), purpose="change_email", show_change_email=False,
    )
