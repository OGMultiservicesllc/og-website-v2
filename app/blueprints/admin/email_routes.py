"""Admin visibility into the transactional email system (item 13) + the Admin-only SMTP test tool
(item 16). Deliberately small — a retry action and a troubleshooting list, not a new Email CRM. Every
route requires @admin_required; nothing here ever displays a verification code, a reset token, or the
SMTP password (the customer-facing "Emails" tab on the profile page, admin/student_detail.html, is the
per-customer view — this module is the cross-customer troubleshooting list + the test tool)."""

from flask import flash, redirect, render_template, request, url_for

from app import email_service
from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.models import EmailLog

STATUS_FILTERS = ("all", "sent", "pending", "sending", "failed")


@admin_bp.route("/emails")
@admin_required
def emails_list():
    status = request.args.get("status", "all")
    if status not in STATUS_FILTERS:
        status = "all"
    q = EmailLog.query
    if status != "all":
        q = q.filter(EmailLog.status == status)
    logs = q.order_by(EmailLog.created_at.desc()).limit(200).all()
    counts = {s: EmailLog.query.filter_by(status=s).count() for s in ("sent", "pending", "sending", "failed")}
    return render_template("admin/emails_list.html", logs=logs, status=status, counts=counts)


@admin_bp.route("/emails/<int:email_log_id>/retry", methods=["POST"])
@admin_required
def email_retry(email_log_id):
    from flask import session

    if not validate_csrf(request.form.get("csrf_token")):
        from flask import abort

        abort(400)
    log, error = email_service.retry(email_log_id, admin_id=session.get("admin_user_id"))
    if log is None:
        flash("Email not found.", "error")
    elif error:
        flash(error, "error")
    else:
        flash("Email sent." if log.status == "sent" else f"Retry attempted — status: {log.status}.", "success" if log.status == "sent" else "error")
    next_url = request.form.get("next") or request.referrer
    if next_url:
        return redirect(next_url)
    return redirect(url_for("admin.emails_list"))


@admin_bp.route("/emails/test", methods=["GET", "POST"])
@admin_required
def email_test():
    """Admin-only SMTP connectivity test (item 16) — never a public endpoint. Sends a clearly-labeled
    "OG TEST EMAIL" to an Admin-chosen recipient and records the attempt as an ordinary EmailLog row
    (student_id left null — it isn't tied to any customer) so its own success/failure is visible right
    here, the same way every other transactional email's is."""
    result = None
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            from flask import abort

            abort(400)
        to_email = (request.form.get("email") or "").strip()
        if not to_email or "@" not in to_email:
            flash("Enter a valid email address to send the test to.", "error")
        else:
            from app.email_render import EmailContent

            content = EmailContent(
                subject="OG TEST EMAIL",
                heading="OG TEST EMAIL",
                paragraphs=["This is a test message confirming the SMTP configuration for OG Multiservices LLC is working.",
                            "If you received this, outbound transactional email is correctly configured."],
            )
            log = EmailLog(student_id=None, recipient_email=to_email, recipient_name="OG Admin Test", template_key="admin_test",
                           language="en", subject=content.subject, status="pending")
            db.session.add(log)
            db.session.commit()
            email_service.deliver(log, content, "en")
            result = log
            if log.status == "sent":
                flash(f"Test email sent to {to_email}.", "success")
            else:
                flash(f"Test email failed: {log.failure_reason}", "error")
    return render_template("admin/email_test.html", result=result)
