"""Master customer directory and the cross-form Applications list.

There is exactly ONE public identity in the system: `Student` (the customer account).
Applications, documents, enrollments, certificates, activity and notes all hang off
that one row, so a person who has an I-90, an N-400 and an Academy course appears
once. OG staff logins (`AdminUser`) are a separate table and never listed here.
"""

from flask import render_template, request


from app.auth import admin_required
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.intake_engine import status_key, status_label
from app.models import ActivityEvent, Enrollment, Form, FormSubmission, Student, SubmissionFile

CUSTOMER_FILTERS = (
    ("all", "All"),
    ("applications", "Has applications"),
    ("courses", "Has courses"),
    ("documents", "Has documents"),
    ("activated", "Activated Accounts"),
    ("needs_activation", "Needs Activation (Imported)"),
    ("inactive", "Inactive"),
)


def _grouped(query):
    return dict(query.all())


def customer_stats():
    """{student_id: value} maps for the directory columns, each from one grouped query."""
    apps = _grouped(
        db.session.query(FormSubmission.student_id, db.func.count(FormSubmission.id))
        .filter(FormSubmission.student_id.isnot(None)).group_by(FormSubmission.student_id)
    )
    open_apps = _grouped(
        db.session.query(FormSubmission.student_id, db.func.count(FormSubmission.id))
        .filter(FormSubmission.student_id.isnot(None), FormSubmission.status.in_(("reopened", "waiting_client")))
        .group_by(FormSubmission.student_id)
    )
    docs = _grouped(
        db.session.query(FormSubmission.student_id, db.func.count(SubmissionFile.id))
        .join(SubmissionFile, SubmissionFile.submission_id == FormSubmission.id)
        .filter(FormSubmission.student_id.isnot(None), SubmissionFile.original_filename != "signature.png")
        .group_by(FormSubmission.student_id)
    )
    courses = _grouped(db.session.query(Enrollment.student_id, db.func.count(Enrollment.id)).group_by(Enrollment.student_id))
    last_event = _grouped(db.session.query(ActivityEvent.customer_id, db.func.max(ActivityEvent.created_at)).group_by(ActivityEvent.customer_id))
    return apps, open_apps, docs, courses, last_event


@admin_bp.route("/customers")
@admin_required
def customers_list():
    q = request.args.get("q", "").strip()
    flt = request.args.get("filter", "all")
    if flt not in dict(CUSTOMER_FILTERS):
        flt = "all"
    apps, open_apps, docs, courses, last_event = customer_stats()

    query = Student.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Student.name.ilike(like), Student.email.ilike(like), Student.phone.ilike(like)))
    if flt == "activated":
        query = query.filter(Student.is_active.is_(True), Student.needs_activation.is_(False))
    elif flt == "inactive":
        query = query.filter(Student.is_active.is_(False))
    elif flt == "needs_activation":
        query = query.filter(Student.needs_activation.is_(True))
    people = query.order_by(Student.created_at.desc()).all()
    if flt == "applications":
        people = [p for p in people if apps.get(p.id)]
    elif flt == "courses":
        people = [p for p in people if courses.get(p.id)]
    elif flt == "documents":
        people = [p for p in people if docs.get(p.id)]

    from app import account_invitations

    rows = []
    for p in people:
        seen = [d for d in (last_event.get(p.id), p.last_login_at, p.created_at) if d]
        rows.append({
            "p": p, "apps": apps.get(p.id, 0), "open": open_apps.get(p.id, 0), "docs": docs.get(p.id, 0),
            "courses": courses.get(p.id, 0), "last_activity": max(seen) if seen else None,
            "account_status": account_invitations.account_status(p),
        })
    return render_template("admin/customers_list.html", rows=rows, q=q, flt=flt, filters=CUSTOMER_FILTERS, total=Student.query.count())


@admin_bp.route("/applications")
@admin_required
def applications_list():
    """Every Smart Intake application, across all forms/services, newest activity first."""
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    form_id = request.args.get("form", type=int)
    query = (
        FormSubmission.query.join(Form, Form.id == FormSubmission.form_id)
        .filter(Form.form_type == "service_intake", FormSubmission.student_id.isnot(None))
    )
    if form_id:
        query = query.filter(FormSubmission.form_id == form_id)
    if q:
        like = f"%{q}%"
        query = query.join(Student, Student.id == FormSubmission.student_id).filter(
            db.or_(Student.name.ilike(like), Student.email.ilike(like), FormSubmission.code.ilike(like))
        )
    subs = query.order_by(FormSubmission.updated_at.desc()).all()
    from app.intake_shared import supplement_status

    rows = [{"s": s, "key": status_key(s), "label": status_label(s),
             "sup": supplement_status(s.form, s) if (s.form.features or {}).get("supplements") else None} for s in subs]
    if status:
        rows = [r for r in rows if r["key"] == status]
    forms = Form.query.filter_by(form_type="service_intake").order_by(Form.name_admin).all()
    status_options = [("draft", "Draft"), ("new", "Submitted"), ("in_review", "In Review"), ("waiting_client", "Waiting for Client"),
                      ("reopened", "Reopened for Editing"), ("completed", "Completed"), ("archived", "Archived")]
    return render_template("admin/applications_list.html", rows=rows, q=q, status=status, form_id=form_id, forms=forms, status_options=status_options)
