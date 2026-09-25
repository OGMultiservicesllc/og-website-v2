"""Admin -> Customers -> Import / Invitations: Wix CSV migration + bulk account-activation invitations.
Every route here is @admin_required (customers can never reach any of this) and CSRF-protected on POST."""
from flask import abort, flash, redirect, render_template, request, session, url_for

from app import account_invitations, customer_import
from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.models import AccountInvitation, ImportBatch, ImportRow, Student


@admin_bp.route("/customers/import")
@admin_required
def customer_import_list():
    batches = ImportBatch.query.order_by(ImportBatch.uploaded_at.desc()).all()
    return render_template("admin/customer_import_list.html", batches=batches)


@admin_bp.route("/customers/import/upload", methods=["GET", "POST"])
@admin_required
def customer_import_upload():
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        file_storage = request.files.get("csv_file")
        if not file_storage or not file_storage.filename:
            flash("Choose a CSV file to upload.", "error")
            return render_template("admin/customer_import_upload.html")
        try:
            filename, raw_text, headers = customer_import.read_upload(file_storage)
        except customer_import.ImportFileError as exc:
            flash(str(exc), "error")
            return render_template("admin/customer_import_upload.html")
        batch = customer_import.create_batch(filename, raw_text, headers, session.get("admin_user_id"))
        return redirect(url_for("admin.customer_import_map", batch_id=batch.id))
    return render_template("admin/customer_import_upload.html")


@admin_bp.route("/customers/import/<int:batch_id>/map", methods=["GET", "POST"])
@admin_required
def customer_import_map(batch_id):
    batch = ImportBatch.query.get_or_404(batch_id)
    if batch.status != "mapping":
        return redirect(url_for("admin.customer_import_detail", batch_id=batch.id))

    import csv as _csv
    import io as _io

    headers = next(_csv.reader(_io.StringIO(batch.raw_csv)), [])
    preview = customer_import.preview_rows(batch.raw_csv)

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        mapping = {h: request.form.get(f"map_{i}", "ignore") for i, h in enumerate(headers)}
        if "email" not in mapping.values():
            flash("Map at least one column to Email — an account can't be created without one.", "error")
            return render_template("admin/customer_import_map.html", batch=batch, headers=headers, preview=preview,
                                  mapping=customer_import.guess_mapping(headers), fields=customer_import.TARGET_FIELDS)
        counts = customer_import.run_import(batch, mapping, session.get("admin_user_id"))
        flash(f"Import complete — {counts['imported']} imported, {counts['existing']} already existed, "
              f"{counts['invalid']} invalid, {counts['missing_email']} missing email, {counts['error']} errors.", "success")
        return redirect(url_for("admin.customer_import_detail", batch_id=batch.id))

    mapping = customer_import.guess_mapping(headers)
    return render_template("admin/customer_import_map.html", batch=batch, headers=headers, preview=preview,
                          mapping=mapping, fields=customer_import.TARGET_FIELDS)


@admin_bp.route("/customers/import/<int:batch_id>")
@admin_required
def customer_import_detail(batch_id):
    batch = ImportBatch.query.get_or_404(batch_id)
    rows = ImportRow.query.filter_by(batch_id=batch.id).order_by(ImportRow.row_number).all()
    result_filter = request.args.get("result", "")
    if result_filter:
        rows = [r for r in rows if r.result == result_filter]

    imported_students = Student.query.filter_by(import_batch_id=batch.id).order_by(Student.name).all()
    invite_rows = [{"student": s, "status": account_invitations.status_of(s), "eligible": account_invitations.eligible_for_invite(s)} for s in imported_students]
    progress = {
        "imported": len(imported_students),
        "invited": sum(1 for r in invite_rows if r["status"] in ("queued", "sent")),
        "activated": sum(1 for r in invite_rows if r["status"] == "activated"),
        "failed": sum(1 for r in invite_rows if r["status"] == "failed"),
        "not_invited": sum(1 for r in invite_rows if r["status"] == "not_invited"),
        "queued": AccountInvitation.query.filter_by(batch_id=batch.id, status="queued").count(),
    }
    return render_template("admin/customer_import_detail.html", batch=batch, rows=rows, result_filter=result_filter,
                          invite_rows=invite_rows, progress=progress)


@admin_bp.route("/customers/import/<int:batch_id>/invite", methods=["POST"])
@admin_required
def customer_import_invite(batch_id):
    """"Send Account Invitations" for the students checked in the batch detail page — queues them all
    instantly, then sends the first controlled batch right away (see app/account_invitations.py)."""
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    batch = ImportBatch.query.get_or_404(batch_id)
    ids = [int(x) for x in request.form.getlist("student_ids") if x.isdigit()]
    students = Student.query.filter(Student.id.in_(ids), Student.import_batch_id == batch.id).all() if ids else []
    if not students:
        flash("Select at least one customer to invite.", "error")
        return redirect(url_for("admin.customer_import_detail", batch_id=batch.id))
    queued = account_invitations.queue_invitations(students, batch_id=batch.id, admin_id=session.get("admin_user_id"))
    result = account_invitations.process_queue(batch_id=batch.id)
    flash(f"Queued {len(queued)} invitation(s) — sent {result['sent']}, failed {result['failed']}"
          + (f", {result['remaining']} still queued (click Send Next Batch to continue)." if result["remaining"] else "."), "success")
    return redirect(url_for("admin.customer_import_detail", batch_id=batch.id))


@admin_bp.route("/customers/import/<int:batch_id>/invite/process", methods=["POST"])
@admin_required
def customer_import_process_queue(batch_id):
    """"Send Next Batch" — processes the next controlled chunk of already-queued invitations."""
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    batch = ImportBatch.query.get_or_404(batch_id)
    result = account_invitations.process_queue(batch_id=batch.id)
    flash(f"Sent {result['sent']}, failed {result['failed']}"
          + (f", {result['remaining']} still queued." if result["remaining"] else " — queue is empty."), "success")
    return redirect(url_for("admin.customer_import_detail", batch_id=batch.id))


@admin_bp.route("/customers/<int:student_id>/resend-invite", methods=["POST"])
@admin_required
def customer_resend_invite(student_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    student = Student.query.get_or_404(student_id)
    if not student.needs_activation:
        flash(f"{student.name} already has an active account — nothing to resend.", "error")
        return redirect(request.referrer or url_for("admin.customers_list"))
    inv = account_invitations.resend_invitation(student, batch_id=student.import_batch_id, admin_id=session.get("admin_user_id"))
    flash(f"Invitation {'sent' if inv.status == 'sent' else ('queued' if inv.status == 'queued' else 'failed')} for {student.name}.",
          "success" if inv.status in ("sent", "queued") else "error")
    return redirect(request.referrer or url_for("admin.customers_list"))
