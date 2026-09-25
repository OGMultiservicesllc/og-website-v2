import os
import re
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import generate_password_hash

from app.activity import log_event
from app.auth import admin_required, check_admin_credentials, is_admin_logged_in, safe_admin_next, validate_csrf
from app.extensions import db
from app.models import (
    CaseSimulation,
    Certificate,
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    LessonResource,
    LessonSlide,
    QuizAttempt,
    QuizQuestion,
    QuizQuestionAcceptedAnswer,
    QuizQuestionOption,
    Student,
    Submission,
)
from app.models import (
    CERTIFICATE_TEMPLATES,
    CERTIFICATE_TRIGGERS,
    QUIZ_QUESTION_TYPES,
)
from app.certificates import build_cert_context, is_certificate_eligible
from app.progress import course_progress, get_or_create_certificate, mark_lesson_complete
from app.quiz_scoring import compute_attempt_totals
from app.uploads import course_media_full_path, delete_course_media, duplicate_course_media, save_course_media

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _next_sort_order(items):
    return (max((i.sort_order for i in items), default=0)) + 1


def _slugify(value):
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "course"


def _unique_slug(base_slug, course_id=None):
    slug = base_slug
    n = 2
    while True:
        query = Course.query.filter_by(slug=slug)
        if course_id:
            query = query.filter(Course.id != course_id)
        if not query.first():
            return slug
        slug = f"{base_slug}-{n}"
        n += 1


# ---------------------------------------------------------------- auth

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if is_admin_logged_in():
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        user = check_admin_credentials(email, password)
        if user:
            session["admin_logged_in"] = True
            session["admin_user_id"] = user.id
            session["admin_email"] = user.email
            session["admin_name"] = user.name
            next_url = safe_admin_next(request.args.get("next")) or url_for("admin.dashboard")
            return redirect(next_url)
        flash("Invalid email or password.", "error")

    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_user_id", None)
    session.pop("admin_email", None)
    session.pop("admin_name", None)
    return redirect(url_for("admin.login"))


# Case type -> the service group it's shown under, both in the sidebar and the Dashboard's "Cases by
# Service" chart. Real values only (app/itin.py, app/tax/service.py, app/consular.py, app/case_types.py,
# app/consent_travel/service.py, app/driver_license/service.py) — never invented.
SERVICE_GROUPS = {
    "itin_application": "Taxes & ITIN", "tax_return": "Taxes & ITIN",
    "green_card_renewal": "Immigration", "naturalization": "Immigration", "family_petition": "Immigration",
    "adjustment_of_status": "Immigration", "employment_authorization": "Immigration",
    "removal_of_conditions": "Immigration", "consular_processing": "Immigration",
    "consent_travel": "Notary Public",
    "nj_driver_license": "NJ Driver License",
    "general_service": "Other Services",
}
SERVICE_GROUP_COLORS = {
    "Taxes & ITIN": "#0d9488", "Immigration": "#dc2626", "Notary Public": "#d97706",
    "NJ Driver License": "#2563eb", "Other Services": "#7c3aed", "Other": "#64748b",
}


@admin_bp.route("/")
@admin_required
def dashboard():
    from datetime import timedelta

    from app.activity import describe
    from app.case_types import type_title
    from app.models import ActivityEvent, MANUAL_METHODS, Case, Inquiry, Payment

    course_count = Course.query.count()
    published_count = Course.query.filter_by(is_published=True).count()
    student_count = Student.query.count()
    enrollment_count = Enrollment.query.count()
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_students_week = Student.query.filter(Student.created_at >= week_ago).count()
    new_enrollments_week = Enrollment.query.filter(Enrollment.enrolled_at >= week_ago).count()

    open_case_rows = Case.query.filter(Case.status.in_(("open", "in_review", "waiting_client"))).order_by(Case.created_at.desc()).all()
    open_cases = len(open_case_rows)
    new_cases_today = sum(1 for c in open_case_rows if c.created_at and c.created_at.date() == datetime.utcnow().date())
    # Shared with the Notification Center (app/notifications.py needs_attention_counts) so Dashboard and
    # Notifications can never independently disagree about what needs OG's attention.
    from app import notifications as notif

    attention = notif.needs_attention_counts()
    pending_manual_payments = attention["pending_manual_payments"]
    pending_by_method = {}
    for p in Payment.query.filter(Payment.status == "pending", Payment.method.in_(MANUAL_METHODS)).all():
        pending_by_method[p.method] = pending_by_method.get(p.method, 0) + 1
    open_inquiries = Inquiry.query.filter_by(status="new").count()

    by_service = {}
    for c in open_case_rows:
        label = SERVICE_GROUPS.get(c.case_type, "Other")
        by_service[label] = by_service.get(label, 0) + 1
    cases_by_service = sorted(by_service.items(), key=lambda x: -x[1])

    recent_cases = [
        {"case": c, "type_title": type_title(c.case_type, "en"), "service": SERVICE_GROUPS.get(c.case_type, "Other")}
        for c in Case.query.order_by(Case.updated_at.desc()).limit(6).all()
    ]
    recent_customers = Student.query.order_by(Student.created_at.desc()).limit(5).all()
    recent_enrollments = Enrollment.query.order_by(Enrollment.enrolled_at.desc()).limit(4).all()
    recent_payments = Payment.query.filter(Payment.status.in_(("completed", "pending"))).order_by(Payment.created_at.desc()).limit(5).all()

    notifications = []
    for e in ActivityEvent.query.order_by(ActivityEvent.created_at.desc()).limit(8).all():
        group, sentence = describe(e)
        notifications.append({"event": e, "group": group, "sentence": sentence, "customer": e.customer})

    return render_template(
        "admin/dashboard.html",
        today=datetime.utcnow(),
        course_count=course_count,
        published_count=published_count,
        student_count=student_count,
        enrollment_count=enrollment_count,
        new_students_week=new_students_week,
        new_enrollments_week=new_enrollments_week,
        open_cases=open_cases,
        new_cases_today=new_cases_today,
        pending_manual_payments=pending_manual_payments,
        pending_by_method=pending_by_method,
        open_inquiries=open_inquiries,
        cases_by_service=cases_by_service,
        service_colors=SERVICE_GROUP_COLORS,
        recent_cases=recent_cases,
        recent_customers=recent_customers,
        recent_enrollments=recent_enrollments,
        recent_payments=recent_payments,
        notifications=notifications,
        attention=attention,
    )


@admin_bp.route("/search")
@admin_required
def global_search():
    """A real, simple search across the few things staff actually look up by name/number — no external
    search engine, no new dependency, just the existing tables' own columns."""
    from app.models import Case, Payment

    q = (request.args.get("q") or "").strip()
    results = {"customers": [], "cases": [], "payments": [], "courses": []}
    if q:
        like = f"%{q}%"
        results["customers"] = Student.query.filter(db.or_(Student.name.ilike(like), Student.email.ilike(like))).order_by(Student.name).limit(10).all()
        results["cases"] = (Case.query.join(Student, Student.id == Case.customer_id)
                            .filter(db.or_(Case.case_number.ilike(like), Case.title.ilike(like), Student.name.ilike(like), Student.email.ilike(like)))
                            .order_by(Case.updated_at.desc()).limit(10).all())
        results["payments"] = Payment.query.filter(Payment.receipt_number.ilike(like)).order_by(Payment.created_at.desc()).limit(10).all()
        results["courses"] = Course.query.filter(db.or_(Course.title_en.ilike(like), Course.title_es.ilike(like))).order_by(Course.title_en).limit(10).all()
    from app.case_types import type_title as _tt

    return render_template("admin/search_results.html", q=q, results=results, type_title=_tt)


# ---------------------------------------------------------------- courses

@admin_bp.route("/courses")
@admin_required
def courses_list():
    courses = Course.query.order_by(Course.sort_order, Course.id).all()
    return render_template("admin/courses_list.html", courses=courses)


@admin_bp.route("/courses/new", methods=["GET", "POST"])
@admin_required
def course_new():
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        title_en = request.form.get("title_en", "").strip()
        title_es = request.form.get("title_es", "").strip()
        if not title_en or not title_es:
            flash("Title (EN and ES) is required.", "error")
            return render_template("admin/course_form.html", course=None, existing_categories=_existing_categories())

        cover = request.files.get("cover_image")
        cover_filename = None
        if cover and cover.filename:
            try:
                cover_filename = save_course_media(cover, "image")
            except ValueError as exc:
                flash(str(exc), "error")
                return render_template("admin/course_form.html", course=None, existing_categories=_existing_categories())

        slug = _unique_slug(_slugify(title_en))
        course = Course(
            slug=slug,
            title_en=title_en,
            title_es=title_es,
            category=request.form.get("category", "").strip() or None,
            subtitle_en=request.form.get("subtitle_en", "").strip(),
            subtitle_es=request.form.get("subtitle_es", "").strip(),
            description_en=request.form.get("description_en", "").strip(),
            description_es=request.form.get("description_es", "").strip(),
            cover_image=cover_filename,
            sort_order=_next_sort_order(Course.query.all()),
            access_duration_days=_parse_access_duration(request.form.get("access_duration_days")),
            accent_color=_parse_accent_color(request.form.get("accent_color")),
            price_cents=_parse_price(request.form.get("price")),
        )
        try:
            _apply_certificate_fields(course, request.form, request.files)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("admin/course_form.html", course=None, existing_categories=_existing_categories())

        db.session.add(course)
        db.session.commit()
        flash("Course created. Now add sections and lessons below.", "success")
        if request.form.get("action") == "preview":
            return redirect(url_for("admin.certificate_preview", course_id=course.id))
        return redirect(url_for("admin.course_builder", course_id=course.id))

    return render_template("admin/course_form.html", course=None, existing_categories=_existing_categories())


def _existing_categories():
    return sorted({c.category for c in Course.query.all() if c.category})


def _parse_access_duration(raw):
    raw = (raw or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        return None
    return int(raw)


def _parse_accent_color(raw):
    raw = (raw or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", raw):
        return raw
    return None


def _parse_price(raw):
    from app.payments import parse_dollars_to_cents

    cents = parse_dollars_to_cents(raw)
    return cents if cents and cents > 0 else None


def _apply_certificate_fields(course, form, files):
    course.certificate_enabled = form.get("certificate_enabled") == "on"

    trigger = form.get("certificate_trigger", "course_completion")
    course.certificate_trigger = trigger if trigger in CERTIFICATE_TRIGGERS else "course_completion"

    template = form.get("certificate_template", "classic")
    course.certificate_template = template if template in CERTIFICATE_TEMPLATES else "classic"

    course.certificate_title = form.get("certificate_title", "").strip() or None
    course.certificate_issuer_name = form.get("certificate_issuer_name", "").strip() or None
    course.certificate_issuer_subtitle = form.get("certificate_issuer_subtitle", "").strip() or None
    course.certificate_signatory_name = form.get("certificate_signatory_name", "").strip() or None
    course.certificate_signatory_title = form.get("certificate_signatory_title", "").strip() or None
    course.certificate_show_qr = form.get("certificate_show_qr") == "on"
    course.certificate_show_id = form.get("certificate_show_id") == "on"

    logo = files.get("certificate_logo_file")
    if logo and logo.filename:
        new_filename = save_course_media(logo, "image")
        old_filename = course.certificate_logo_image
        course.certificate_logo_image = new_filename
        if old_filename:
            delete_course_media(old_filename)
    elif form.get("remove_certificate_logo") and course.certificate_logo_image:
        delete_course_media(course.certificate_logo_image)
        course.certificate_logo_image = None

    signature = files.get("certificate_signature_file")
    if signature and signature.filename:
        new_filename = save_course_media(signature, "image")
        old_filename = course.certificate_signature_image
        course.certificate_signature_image = new_filename
        if old_filename:
            delete_course_media(old_filename)
    elif form.get("remove_certificate_signature") and course.certificate_signature_image:
        delete_course_media(course.certificate_signature_image)
        course.certificate_signature_image = None


@admin_bp.route("/courses/<int:course_id>/students")
@admin_required
def course_students(course_id):
    """Item B8: who has access to this course, how they got it, and where they stand — filterable by
    Active/Expired/Completed/access source, without duplicating the per-student courses tab."""
    from app.models import ACCESS_SOURCES, access_source_label as access_source_label_fn
    from app.progress import course_progress

    course = Course.query.get_or_404(course_id)
    status_filter = request.args.get("status", "all")
    source_filter = request.args.get("source", "all")
    rows = []
    for e in Enrollment.query.filter_by(course_id=course.id).order_by(Enrollment.granted_at.desc().nullslast(), Enrollment.enrolled_at.desc()).all():
        progress = course_progress(e.student, course)
        status = "revoked" if e.is_revoked else ("expired" if e.is_expired else ("completed" if progress["is_complete"] else "active"))
        rows.append({"e": e, "student": e.student, "progress": progress, "status": status})
    if status_filter != "all":
        rows = [r for r in rows if r["status"] == status_filter]
    if source_filter != "all":
        rows = [r for r in rows if r["e"].access_source == source_filter]
    return render_template("admin/course_students.html", course=course, rows=rows, status_filter=status_filter, source_filter=source_filter,
                           access_sources=ACCESS_SOURCES, access_source_label=lambda s: access_source_label_fn(s, "en"))


@admin_bp.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
@admin_required
def course_edit(course_id):
    course = Course.query.get_or_404(course_id)

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        title_en = request.form.get("title_en", "").strip()
        title_es = request.form.get("title_es", "").strip()
        if not title_en or not title_es:
            flash("Title (EN and ES) is required.", "error")
            return render_template("admin/course_form.html", course=course, existing_categories=_existing_categories())

        cover = request.files.get("cover_image")
        if cover and cover.filename:
            try:
                new_cover = save_course_media(cover, "image")
            except ValueError as exc:
                flash(str(exc), "error")
                return render_template("admin/course_form.html", course=course, existing_categories=_existing_categories())
            if course.cover_image:
                delete_course_media(course.cover_image)
            course.cover_image = new_cover

        course.title_en = title_en
        course.title_es = title_es
        course.category = request.form.get("category", "").strip() or None
        course.subtitle_en = request.form.get("subtitle_en", "").strip()
        course.subtitle_es = request.form.get("subtitle_es", "").strip()
        course.description_en = request.form.get("description_en", "").strip()
        course.description_es = request.form.get("description_es", "").strip()
        course.is_published = request.form.get("is_published") == "on"
        course.access_duration_days = _parse_access_duration(request.form.get("access_duration_days"))
        course.accent_color = _parse_accent_color(request.form.get("accent_color"))
        course.price_cents = _parse_price(request.form.get("price"))
        try:
            _apply_certificate_fields(course, request.form, request.files)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("admin/course_form.html", course=course, existing_categories=_existing_categories())

        db.session.commit()
        flash("Course updated.", "success")
        if request.form.get("action") == "preview":
            return redirect(url_for("admin.certificate_preview", course_id=course.id))
        return redirect(url_for("admin.course_builder", course_id=course.id))

    return render_template("admin/course_form.html", course=course, existing_categories=_existing_categories())


@admin_bp.route("/courses/<int:course_id>/cover/delete", methods=["POST"])
@admin_required
def course_cover_delete(course_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    course = Course.query.get_or_404(course_id)
    if course.cover_image:
        delete_course_media(course.cover_image)
        course.cover_image = None
        db.session.commit()
        flash("Cover image removed.", "success")
    return redirect(url_for("admin.course_edit", course_id=course.id))


@admin_bp.route("/courses/<int:course_id>/delete", methods=["POST"])
@admin_required
def course_delete(course_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    course = Course.query.get_or_404(course_id)

    for section in course.sections:
        for lesson in section.lessons:
            _delete_lesson_files(lesson)

    db.session.delete(course)
    db.session.commit()
    flash("Course deleted.", "success")
    return redirect(url_for("admin.courses_list"))


@admin_bp.route("/courses/<int:course_id>")
@admin_required
def course_builder(course_id):
    course = Course.query.get_or_404(course_id)
    return render_template("admin/course_builder.html", course=course)


# ---------------------------------------------------------------- reports

@admin_bp.route("/reports")
@admin_required
def reports():
    courses = Course.query.order_by(Course.sort_order, Course.id).all()
    rows = []
    for course in courses:
        enrollments = Enrollment.query.filter_by(course_id=course.id).all()
        enrolled_count = len(enrollments)
        completed_count = sum(
            1 for e in enrollments if course_progress(e.student, course)["is_complete"]
        )
        completion_rate = round((completed_count / enrolled_count) * 100) if enrolled_count else 0
        rows.append(
            {
                "course": course,
                "enrolled_count": enrolled_count,
                "completed_count": completed_count,
                "completion_rate": completion_rate,
            }
        )
    return render_template("admin/reports.html", rows=rows)


# ---------------------------------------------------------------- certificates

@admin_bp.route("/certificates")
@admin_required
def certificates_list():
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    query = Certificate.query.join(Student, Certificate.student_id == Student.id).join(Course, Certificate.course_id == Course.id)
    if status in ("valid", "revoked"):
        query = query.filter(Certificate.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Certificate.code.ilike(like), Student.name.ilike(like), Student.email.ilike(like), Course.title_en.ilike(like)))
    certificates = query.order_by(Certificate.issued_at.desc()).all()
    return render_template("admin/certificates_list.html", certificates=certificates, status=status, q=q)


# ---------------------------------------------------------------- students

@admin_bp.route("/students")
@admin_required
def students_list():
    """OG Academy view of the SAME customer accounts: people enrolled in at least one
    course (or everyone, with ?all=1). The account and profile are the Customers ones."""
    query = request.args.get("q", "").strip()
    show_all = request.args.get("all") == "1"
    enrollment_counts = dict(
        db.session.query(Enrollment.student_id, db.func.count(Enrollment.id)).group_by(Enrollment.student_id).all()
    )
    students_query = Student.query
    if not show_all:
        students_query = students_query.filter(Student.id.in_(list(enrollment_counts) or [0]))
    if query:
        like = f"%{query}%"
        students_query = students_query.filter(db.or_(Student.name.ilike(like), Student.email.ilike(like), Student.phone.ilike(like)))
    students = students_query.order_by(Student.created_at.desc()).all()
    return render_template(
        "admin/students_list.html", students=students, enrollment_counts=enrollment_counts, query=query, show_all=show_all
    )


CUSTOMER_TABS = (
    ("overview", "Overview"),
    ("applications", "Applications"),
    ("cases", "Cases"),
    ("documents", "Documents"),
    ("files", "Files from OG"),
    ("payments", "Payments"),
    ("courses", "Courses"),
    ("emails", "Emails"),
    ("activity", "Activity"),
    ("notes", "Notes"),
)


@admin_bp.route("/students/<int:student_id>")
@admin_required
def student_detail_legacy(student_id):
    """Old URL of the customer profile (Students and Customers are one identity)."""
    return redirect(url_for("admin.customer_detail", student_id=student_id, **request.args))


@admin_bp.route("/customers/<int:student_id>")
@admin_required
def customer_detail(student_id):
    from app.activity import FILTER_GROUPS, timeline
    from app.intake_engine import progress_for, status_key, status_label
    from app.models import CustomerNote, FormSubmission, SubmissionFile

    student = Student.query.get_or_404(student_id)
    tab = request.args.get("tab", "overview")
    if tab not in dict(CUSTOMER_TABS):
        tab = "overview"

    enrollments = (
        Enrollment.query.filter_by(student_id=student.id)
        .join(Course)
        .order_by(Enrollment.enrolled_at.desc())
        .all()
    )
    progress_by_course = {e.course_id: course_progress(student, e.course) for e in enrollments}
    enrolled_course_ids = {e.course_id for e in enrollments}
    available_courses = (
        Course.query.filter(~Course.id.in_(enrolled_course_ids)).order_by(Course.title_en).all()
        if enrolled_course_ids
        else Course.query.order_by(Course.title_en).all()
    )
    certificates_by_course = {
        c.course_id: c for c in Certificate.query.filter_by(student_id=student.id).all()
    }

    submissions = (
        FormSubmission.query.filter_by(student_id=student.id)
        .order_by(FormSubmission.is_complete.asc(), FormSubmission.updated_at.desc())
        .all()
    )
    applications = []
    for sub in submissions:
        applications.append({
            "sub": sub,
            "title": sub.service.title_en if sub.service else sub.form.name_admin,
            "key": status_key(sub),
            "label": status_label(sub),
            "percent": 100 if (sub.is_complete or sub.status == "reopened") else (progress_for(sub.form, sub)["percent"] if sub.form.is_service_intake else None),
        })
    files = (
        SubmissionFile.query.join(FormSubmission, SubmissionFile.submission_id == FormSubmission.id)
        .filter(FormSubmission.student_id == student.id)
        .order_by(SubmissionFile.uploaded_at.desc())
        .all()
    )
    group = request.args.get("group", "all")
    if group not in dict(FILTER_GROUPS):
        group = "all"
    events = timeline(student.id, group, 300) if tab == "activity" else timeline(student.id, "all", 6)
    latest = timeline(student.id, "all", 1)
    open_requests = sum(1 for a in applications if a["key"] in ("reopened", "waiting_client"))
    seen = [d for d in (student.last_login_at, latest[0][0].created_at if latest else None) if d]
    last_activity = max(seen) if seen else student.created_at
    notes = CustomerNote.query.filter_by(customer_id=student.id).order_by(CustomerNote.created_at.desc()).all()
    from app import case_documents as _vault
    from app.case_types import type_title as _type_title
    from app.models import Case

    cases = [{"c": c, "type": _type_title(c.case_type), "apps": len(c.applications), "open_docs": len(_vault.open_customer_actions(c))}
             for c in Case.query.filter_by(customer_id=student.id).order_by(Case.id.desc()).all()]
    from app.models import CustomerFile, FILE_CATEGORIES, category_label, ACCESS_SOURCES
    from app.models import access_source_label as access_source_label_fn

    og_files = CustomerFile.query.filter_by(customer_id=student.id).order_by(CustomerFile.created_at.desc()).all()
    from app import payments as pay_svc
    from app.models import Charge, MANUAL_METHODS, PAYMENT_METHODS

    charges = Charge.query.filter_by(customer_id=student.id).order_by(Charge.created_at.desc()).all()
    charge_rows = [{"c": c, "status": pay_svc.status_of(c), "total": pay_svc.format_cents(c.total_cents), "paid": pay_svc.format_cents(pay_svc.paid_cents(c)),
                    "balance": pay_svc.format_cents(pay_svc.balance_cents(c)), "balance_cents": pay_svc.balance_cents(c), "open_req": pay_svc.open_request(c)} for c in charges]
    from app.models import EmailLog

    email_logs = EmailLog.query.filter_by(student_id=student.id).order_by(EmailLog.created_at.desc()).all() if tab == "emails" else []
    return render_template(
        "admin/student_detail.html", cases=cases,
        student=student, tab=tab, tabs=CUSTOMER_TABS,
        enrollments=enrollments,
        progress_by_course=progress_by_course,
        available_courses=available_courses,
        certificates_by_course=certificates_by_course,
        applications=applications, files=files, og_files=og_files, events=events, groups=FILTER_GROUPS, group=group, notes=notes,
        open_requests=open_requests, last_activity=last_activity, persons=student.persons, file_categories=FILE_CATEGORIES,
        file_category_label=lambda c: category_label(c, "en"), access_sources=ACCESS_SOURCES,
        access_source_label=lambda s: access_source_label_fn(s, "en"),
        charge_rows=charge_rows, manual_methods=MANUAL_METHODS, payment_methods=PAYMENT_METHODS,
        email_logs=email_logs,
    )


@admin_bp.route("/customers/<int:student_id>/files", methods=["POST"])
@admin_required
def customer_file_upload(student_id):
    from app import customer_files as cf_service
    from app.models import Case, Person

    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    student = Student.query.get_or_404(student_id)
    f = request.files.get("file")
    error = cf_service.validate_upload(f) if f and f.filename else "Choose a file to upload."
    if error:
        flash(error, "error")
        return redirect(url_for("admin.customer_detail", student_id=student.id, tab="files"))
    case_id = request.form.get("case_id", type=int)
    case = Case.query.filter_by(id=case_id, customer_id=student.id).first() if case_id else None
    person_id = request.form.get("person_id", type=int)
    person = Person.query.filter_by(id=person_id, customer_id=student.id).first() if person_id else None
    admin_id = session.get("admin_user_id")
    cf_service.create(student, f, title=request.form.get("title", ""), description=request.form.get("description", ""),
                      case=case, person=person, category=request.form.get("category", "other"),
                      related_service=request.form.get("related_service", ""), tax_year=request.form.get("tax_year", type=int),
                      admin_id=admin_id, publish=request.form.get("publish") == "1")
    flash("File is now available to the customer." if request.form.get("publish") == "1" else "File saved as a draft — not visible to the customer yet.", "success")
    return redirect(url_for("admin.customer_detail", student_id=student.id, tab="files"))


@admin_bp.route("/customers/<int:student_id>/files/<int:file_id>/publish", methods=["POST"])
@admin_required
def customer_file_publish(student_id, file_id):
    from app import customer_files as cf_service
    from app.models import CustomerFile

    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    f = CustomerFile.query.filter_by(id=file_id, customer_id=student_id).first_or_404()
    if request.form.get("action") == "unpublish":
        cf_service.unpublish(f)
        flash("File is now hidden from the customer.", "success")
    else:
        cf_service.publish(f, admin_id=session.get("admin_user_id"))
        flash("File is now available to the customer.", "success")
    return redirect(url_for("admin.customer_detail", student_id=student_id, tab="files"))


@admin_bp.route("/customers/<int:student_id>/files/<int:file_id>/download")
@admin_required
def customer_file_download(student_id, file_id):
    import os

    from flask import send_file

    from app.models import CustomerFile
    from app.uploads import course_media_full_path

    f = CustomerFile.query.filter_by(id=file_id, customer_id=student_id).first_or_404()
    path = course_media_full_path(f.stored_filename)
    if not os.path.isfile(path):
        abort(404)
    response = send_file(path, mimetype=f.mime_type or "application/octet-stream", as_attachment=True, download_name=f.original_filename, conditional=True)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@admin_bp.route("/customers/<int:student_id>/notes", methods=["POST"])
@admin_required
def student_note_add(student_id):
    from app.activity import log_event
    from app.models import CustomerNote

    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    student = Student.query.get_or_404(student_id)
    body = request.form.get("body", "").strip()
    if body:
        db.session.add(CustomerNote(customer_id=student.id, body=body, author_name="OG team"))
        db.session.commit()
        log_event(student.id, "admin_note_added", actor="admin", entity=("customer", student.id), meta={"where": "customer"})
        flash("Internal note added (never shown to the customer).", "success")
    return redirect(url_for("admin.customer_detail", student_id=student.id, tab="notes"))


@admin_bp.route("/customers/<int:student_id>/notes/<int:note_id>/delete", methods=["POST"])
@admin_required
def student_note_delete(student_id, note_id):
    from app.models import CustomerNote

    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    note = CustomerNote.query.filter_by(id=note_id, customer_id=student_id).first_or_404()
    db.session.delete(note)
    db.session.commit()
    flash("Note deleted.", "success")
    return redirect(url_for("admin.customer_detail", student_id=student_id, tab="notes"))


def _duration_kwargs(form):
    """Item B4: Default duration / 30 / 60 / 90 / Custom expiration / No expiration (never a default) —
    shared by Grant and Extend so both offer the identical set of choices."""
    mode = form.get("duration_mode", "default")
    if mode == "no_expiration":
        return {"no_expiration": True}
    if mode == "custom":
        raw = form.get("custom_expires_at", "")
        try:
            return {"expires_at": datetime.strptime(raw, "%Y-%m-%d")}
        except ValueError:
            return {"duration_days": None}  # falls back to the course default below
    if mode in ("30", "60", "90"):
        return {"duration_days": int(mode)}
    return {"duration_days": None}  # "default" — grant_access() falls back to course.access_duration_days


@admin_bp.route("/students/<int:student_id>/enroll", methods=["POST"])
@admin_required
def student_enroll(student_id):
    from app import academy_access

    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    student = Student.query.get_or_404(student_id)
    course_id = request.form.get("course_id", type=int)
    course = Course.query.get_or_404(course_id) if course_id else abort(400)
    access_source = request.form.get("access_source") or "paid_new_site"
    kwargs = _duration_kwargs(request.form)
    enrollment, status = academy_access.grant_access(
        student, course, access_source=access_source, admin_id=session.get("admin_user_id"),
        migration_reference=request.form.get("migration_reference", ""), internal_note=request.form.get("internal_note", ""), **kwargs)
    if status == "already_active":
        flash(f"{student.name} already has access to {course.title_en} (until "
              f"{enrollment.expires_at.strftime('%b %d, %Y') if enrollment.expires_at else 'no expiration'}). Use Extend Access or Change Expiration below instead.", "error")
    elif status == "created":
        flash(f"Access granted: {student.name} can now see {course.title_en} in My Account. No payment was involved.", "success")
    elif status == "restored_revoked":
        flash(f"Access restored and renewed for {student.name} on {course.title_en}.", "success")
    else:
        flash(f"Renewed {student.name}'s access to {course.title_en}.", "success")
    return redirect(url_for("admin.customer_detail", student_id=student.id, tab="courses"))


@admin_bp.route("/students/<int:student_id>/enrollment/<int:enrollment_id>/extend", methods=["POST"])
@admin_required
def enrollment_extend(student_id, enrollment_id):
    from app import academy_access

    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    enrollment = Enrollment.query.filter_by(id=enrollment_id, student_id=student_id).first_or_404()
    kwargs = _duration_kwargs(request.form)
    academy_access.extend_access(enrollment, admin_id=session.get("admin_user_id"), reason=request.form.get("reason", ""), **kwargs)
    flash(f"Access to {enrollment.course.title_en} extended.", "success")
    return redirect(url_for("admin.customer_detail", student_id=student_id, tab="courses"))


@admin_bp.route("/students/<int:student_id>/unenroll/<int:course_id>", methods=["POST"])
@admin_required
def student_unenroll(student_id, course_id):
    """Item B9: "Revoke Access" — kept at the historical URL/endpoint name so nothing else needs to change,
    but this no longer deletes the row (that would lose the grant/access-source history); it soft-revokes
    (`revoked_at`) instead. Progress/quiz/certificate history is untouched either way (see
    app/academy_access.py's docstring — none of it is keyed by enrollment id)."""
    from app import academy_access

    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    enrollment = Enrollment.query.filter_by(student_id=student_id, course_id=course_id).first_or_404()
    academy_access.revoke_access(enrollment, admin_id=session.get("admin_user_id"), reason=request.form.get("reason", ""))
    flash(f"Access to {enrollment.course.title_en} revoked. Progress and certificate history are preserved.", "success")
    return redirect(url_for("admin.customer_detail", student_id=student_id, tab="courses"))


@admin_bp.route("/students/<int:student_id>/enrollment/<int:enrollment_id>/restore", methods=["POST"])
@admin_required
def enrollment_restore(student_id, enrollment_id):
    from app import academy_access

    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    enrollment = Enrollment.query.filter_by(id=enrollment_id, student_id=student_id).first_or_404()
    academy_access.restore_access(enrollment, admin_id=session.get("admin_user_id"))
    flash(f"Access to {enrollment.course.title_en} restored.", "success")
    return redirect(url_for("admin.customer_detail", student_id=student_id, tab="courses"))


@admin_bp.route("/students/<int:student_id>/toggle-active", methods=["POST"])
@admin_required
def student_toggle_active(student_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    student = Student.query.get_or_404(student_id)
    student.is_active = not student.is_active
    db.session.commit()
    flash(f"{student.name} is now {'active' if student.is_active else 'inactive'}.", "success")
    return redirect(url_for("admin.customer_detail", student_id=student.id))


@admin_bp.route("/students/<int:student_id>/reset-password", methods=["POST"])
@admin_required
def student_reset_password(student_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    student = Student.query.get_or_404(student_id)
    password = request.form.get("password", "")

    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("admin.customer_detail", student_id=student.id))

    student.password_hash = generate_password_hash(password)
    db.session.commit()
    flash(f"Password updated for {student.name}.", "success")
    return redirect(url_for("admin.customer_detail", student_id=student.id))


@admin_bp.route("/students/<int:student_id>/courses/<int:course_id>/certificate", methods=["POST"])
@admin_required
def certificate_upload(student_id, course_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    student = Student.query.get_or_404(student_id)
    course = Course.query.get_or_404(course_id)
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        flash("Choose a file to upload.", "error")
        return redirect(url_for("admin.customer_detail", student_id=student.id, tab="courses"))

    cert = get_or_create_certificate(student, course)
    try:
        new_filename = save_course_media(uploaded, "document")
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin.customer_detail", student_id=student.id, tab="courses"))

    if cert.file_filename:
        delete_course_media(cert.file_filename)
    cert.file_filename = new_filename
    db.session.commit()
    flash(f"Certificate uploaded for {student.name} — {course.title_en}.", "success")
    return redirect(url_for("admin.customer_detail", student_id=student.id, tab="courses"))


@admin_bp.route("/students/<int:student_id>/courses/<int:course_id>/certificate/delete", methods=["POST"])
@admin_required
def certificate_delete(student_id, course_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    cert = Certificate.query.filter_by(student_id=student_id, course_id=course_id).first_or_404()
    if cert.file_filename:
        delete_course_media(cert.file_filename)
        cert.file_filename = None
        db.session.commit()
        flash("Uploaded certificate file removed — the auto-generated certificate is still available.", "success")
    return redirect(url_for("admin.customer_detail", student_id=student_id, tab="courses"))


@admin_bp.route("/students/<int:student_id>/courses/<int:course_id>/certificate/regenerate", methods=["POST"])
@admin_required
def certificate_regenerate(student_id, course_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    student = Student.query.get_or_404(student_id)
    course = Course.query.get_or_404(course_id)

    cert = Certificate.query.filter_by(student_id=student.id, course_id=course.id).first()
    if not cert and not is_certificate_eligible(student, course):
        flash(f"{student.name} hasn't met this course's certificate trigger yet.", "error")
        return redirect(url_for("admin.customer_detail", student_id=student.id, tab="courses"))

    if not cert:
        cert = get_or_create_certificate(student, course)

    if cert.file_filename:
        delete_course_media(cert.file_filename)
        cert.file_filename = None
    cert.status = "valid"
    cert.revoked_at = None
    db.session.commit()
    flash(f"Certificate regenerated for {student.name} — back to the auto-generated {course.certificate_template} template.", "success")
    return redirect(url_for("admin.customer_detail", student_id=student.id, tab="courses"))


@admin_bp.route("/students/<int:student_id>/courses/<int:course_id>/certificate/revoke", methods=["POST"])
@admin_required
def certificate_revoke(student_id, course_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    cert = Certificate.query.filter_by(student_id=student_id, course_id=course_id).first_or_404()
    cert.status = "revoked"
    cert.revoked_at = datetime.utcnow()
    db.session.commit()
    log_event(student_id, "certificate_revoked", actor="admin", entity=("course", course_id), meta={"course": cert.course.title_en})
    flash("Certificate revoked.", "success")
    return redirect(url_for("admin.customer_detail", student_id=student_id, tab="courses"))


@admin_bp.route("/students/<int:student_id>/courses/<int:course_id>/certificate/reissue", methods=["POST"])
@admin_required
def certificate_reissue(student_id, course_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    cert = Certificate.query.filter_by(student_id=student_id, course_id=course_id).first_or_404()
    cert.status = "valid"
    cert.revoked_at = None
    db.session.commit()
    log_event(student_id, "certificate_reissued", actor="admin", entity=("course", course_id), meta={"course": cert.course.title_en})
    flash("Certificate reissued — it's valid again.", "success")
    return redirect(url_for("admin.customer_detail", student_id=student_id, tab="courses"))


@admin_bp.route("/courses/<int:course_id>/certificate-preview")
@admin_required
def certificate_preview(course_id):
    course = Course.query.get_or_404(course_id)
    template = request.args.get("template")
    if template not in CERTIFICATE_TEMPLATES:
        template = course.certificate_template
    cert = build_cert_context(course, "en")
    return render_template("admin/certificate_preview.html", course=course, cert=cert, template=template)


# ---------------------------------------------------------------- sections

@admin_bp.route("/courses/<int:course_id>/sections/new", methods=["POST"])
@admin_required
def section_new(course_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    course = Course.query.get_or_404(course_id)

    title_en = request.form.get("title_en", "").strip()
    title_es = request.form.get("title_es", "").strip()
    if not title_en or not title_es:
        flash("Section title (EN and ES) is required.", "error")
        return redirect(url_for("admin.course_builder", course_id=course.id))

    section = CourseSection(
        course_id=course.id,
        title_en=title_en,
        title_es=title_es,
        sort_order=_next_sort_order(course.sections),
    )
    db.session.add(section)
    db.session.commit()
    flash("Section added.", "success")
    return redirect(url_for("admin.course_builder", course_id=course.id))


@admin_bp.route("/sections/<int:section_id>/edit", methods=["POST"])
@admin_required
def section_edit(section_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    section = CourseSection.query.get_or_404(section_id)

    title_en = request.form.get("title_en", "").strip()
    title_es = request.form.get("title_es", "").strip()
    if title_en and title_es:
        section.title_en = title_en
        section.title_es = title_es
        db.session.commit()
        flash("Section updated.", "success")
    return redirect(url_for("admin.course_builder", course_id=section.course_id))


@admin_bp.route("/sections/<int:section_id>/delete", methods=["POST"])
@admin_required
def section_delete(section_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    section = CourseSection.query.get_or_404(section_id)
    course_id = section.course_id

    for lesson in section.lessons:
        _delete_lesson_files(lesson)

    db.session.delete(section)
    db.session.commit()
    flash("Section deleted.", "success")
    return redirect(url_for("admin.course_builder", course_id=course_id))


@admin_bp.route("/sections/<int:section_id>/move", methods=["POST"])
@admin_required
def section_move(section_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    section = CourseSection.query.get_or_404(section_id)
    direction = request.form.get("direction")
    siblings = list(
        CourseSection.query.filter_by(course_id=section.course_id)
        .order_by(CourseSection.sort_order)
        .all()
    )
    _swap_sort_order(siblings, section, direction)
    return redirect(url_for("admin.course_builder", course_id=section.course_id))


# ---------------------------------------------------------------- lessons

@admin_bp.route("/sections/<int:section_id>/lessons/new", methods=["GET", "POST"])
@admin_required
def lesson_new(section_id):
    section = CourseSection.query.get_or_404(section_id)

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        lesson_type = request.form.get("lesson_type", "text")

        lesson = Lesson(
            section_id=section.id,
            lesson_type=lesson_type,
            title_en=request.form.get("title_en", "").strip(),
            title_es=request.form.get("title_es", "").strip(),
            is_preview=request.form.get("is_preview") == "on",
            sort_order=_next_sort_order(section.lessons),
        )
        if not lesson.title_en or not lesson.title_es:
            flash("Lesson title (EN and ES) is required.", "error")
            return render_template("admin/lesson_form.html", section=section, lesson=None)

        try:
            _apply_lesson_type_fields(lesson, request.form, request.files)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("admin/lesson_form.html", section=section, lesson=None)

        db.session.add(lesson)
        db.session.flush()
        db.session.commit()
        flash("Lesson added.", "success")
        if lesson.lesson_type == "case_simulation":
            return redirect(url_for("admin.case_edit", lesson_id=lesson.id))
        if lesson.lesson_type in ("presentation", "quiz"):
            return redirect(url_for("admin.lesson_edit", lesson_id=lesson.id))
        return redirect(url_for("admin.course_builder", course_id=section.course_id))

    return render_template("admin/lesson_form.html", section=section, lesson=None)


@admin_bp.route("/lessons/<int:lesson_id>/edit", methods=["GET", "POST"])
@admin_required
def lesson_edit(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    section = lesson.section

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        title_en = request.form.get("title_en", "").strip()
        title_es = request.form.get("title_es", "").strip()
        if not title_en or not title_es:
            flash("Lesson title (EN and ES) is required.", "error")
            return render_template("admin/lesson_form.html", section=section, lesson=lesson)

        lesson_type = request.form.get("lesson_type", lesson.lesson_type)
        lesson.title_en = title_en
        lesson.title_es = title_es
        lesson.is_preview = request.form.get("is_preview") == "on"

        try:
            _apply_lesson_type_fields(lesson, request.form, request.files)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("admin/lesson_form.html", section=section, lesson=lesson)

        db.session.commit()
        flash("Lesson updated.", "success")
        if lesson.lesson_type == "case_simulation":
            return redirect(url_for("admin.case_edit", lesson_id=lesson.id))
        if lesson.lesson_type in ("presentation", "quiz"):
            return redirect(url_for("admin.lesson_edit", lesson_id=lesson.id))
        return redirect(url_for("admin.course_builder", course_id=section.course_id))

    submissions = []
    if lesson.lesson_type == "assignment":
        submissions = (
            Submission.query.filter_by(lesson_id=lesson.id)
            .order_by(Submission.submitted_at.desc())
            .all()
        )

    return render_template(
        "admin/lesson_form.html", section=section, lesson=lesson, submissions=submissions,
    )


@admin_bp.route("/lessons/<int:lesson_id>/delete", methods=["POST"])
@admin_required
def lesson_delete(lesson_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    lesson = Lesson.query.get_or_404(lesson_id)
    course_id = lesson.section.course_id

    _delete_lesson_files(lesson)
    if lesson.case_simulation:
        db.session.delete(lesson.case_simulation)
    db.session.delete(lesson)
    db.session.commit()
    flash("Lesson deleted.", "success")
    return redirect(url_for("admin.course_builder", course_id=course_id))


@admin_bp.route("/lessons/<int:lesson_id>/move", methods=["POST"])
@admin_required
def lesson_move(lesson_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    lesson = Lesson.query.get_or_404(lesson_id)
    direction = request.form.get("direction")
    siblings = list(
        Lesson.query.filter_by(section_id=lesson.section_id).order_by(Lesson.sort_order).all()
    )
    _swap_sort_order(siblings, lesson, direction)
    return redirect(url_for("admin.course_builder", course_id=lesson.section.course_id))


def _apply_lesson_type_fields(lesson, form, files):
    lesson_type = form.get("lesson_type", lesson.lesson_type)
    lesson.lesson_type = lesson_type

    if lesson_type in ("text", "assignment"):
        lesson.content_en = form.get("content_en", "").strip()
        lesson.content_es = form.get("content_es", "").strip()

    elif lesson_type == "video":
        video_source = form.get("video_source", "external")
        lesson.video_source = video_source
        if video_source == "external":
            lesson.video_external_url = form.get("video_external_url", "").strip()
        else:
            uploaded = files.get("video_file")
            if uploaded and uploaded.filename:
                if lesson.video_filename:
                    delete_course_media(lesson.video_filename)
                lesson.video_filename = save_course_media(uploaded, "video")
            elif form.get("remove_video") == "on" and lesson.video_filename:
                delete_course_media(lesson.video_filename)
                lesson.video_filename = None
            lesson.video_external_url = None

    elif lesson_type == "quiz":
        lesson.quiz_kind = "formative" if form.get("quiz_kind") == "formative" else "final"

        try:
            lesson.quiz_passing_percentage = max(1, min(100, int(form.get("quiz_passing_percentage", 70))))
        except (TypeError, ValueError):
            lesson.quiz_passing_percentage = 70

        max_attempts = form.get("quiz_max_attempts", "").strip()
        lesson.quiz_max_attempts = int(max_attempts) if max_attempts.isdigit() and int(max_attempts) > 0 else None
        lesson.quiz_allow_retry = form.get("quiz_allow_retry") == "on"
        lesson.quiz_show_results = form.get("quiz_show_results") == "on"
        lesson.quiz_show_correct_answers = form.get("quiz_show_correct_answers") == "on"

        try:
            lesson.quiz_questions_per_page = max(1, int(form.get("quiz_questions_per_page", 8)))
        except (TypeError, ValueError):
            lesson.quiz_questions_per_page = 8


# ---------------------------------------------------------------- slides (presentation lessons)

@admin_bp.route("/lessons/<int:lesson_id>/slides/new", methods=["POST"])
@admin_required
def slide_new(lesson_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    lesson = Lesson.query.get_or_404(lesson_id)

    image_en = request.files.get("image_en_file")
    image_es = request.files.get("image_es_file")
    if not (image_en and image_en.filename) and not (image_es and image_es.filename):
        flash("At least one slide image (English or Español) is required.", "error")
        return redirect(url_for("admin.lesson_edit", lesson_id=lesson.id))

    try:
        image_en_filename = save_course_media(image_en, "image")
        audio_en_filename = save_course_media(request.files.get("audio_en_file"), "audio")
        image_es_filename = save_course_media(image_es, "image")
        audio_es_filename = save_course_media(request.files.get("audio_es_file"), "audio")
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin.lesson_edit", lesson_id=lesson.id))

    slide = LessonSlide(
        lesson_id=lesson.id,
        image_en=image_en_filename,
        audio_en=audio_en_filename,
        image_es=image_es_filename,
        audio_es=audio_es_filename,
        sort_order=_next_sort_order(lesson.slides),
    )
    db.session.add(slide)
    db.session.commit()
    flash("Slide added.", "success")
    return redirect(url_for("admin.lesson_edit", lesson_id=lesson.id))


@admin_bp.route("/slides/<int:slide_id>/update", methods=["POST"])
@admin_required
def slide_update(slide_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    slide = LessonSlide.query.get_or_404(slide_id)
    fields = [("image_en", "image"), ("audio_en", "audio"), ("image_es", "image"), ("audio_es", "audio")]

    try:
        new_files = {}
        for field, kind in fields:
            uploaded = request.files.get(f"{field}_file")
            if uploaded and uploaded.filename:
                new_files[field] = save_course_media(uploaded, kind)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin.lesson_edit", lesson_id=slide.lesson_id))

    resulting_image_en = new_files.get("image_en", None if request.form.get("remove_image_en") else slide.image_en)
    resulting_image_es = new_files.get("image_es", None if request.form.get("remove_image_es") else slide.image_es)
    if not resulting_image_en and not resulting_image_es:
        for filename in new_files.values():
            delete_course_media(filename)
        flash("A slide needs at least one image (English or Español).", "error")
        return redirect(url_for("admin.lesson_edit", lesson_id=slide.lesson_id))

    for field, _kind in fields:
        old_filename = getattr(slide, field)
        if field in new_files:
            setattr(slide, field, new_files[field])
            if old_filename:
                delete_course_media(old_filename)
        elif request.form.get(f"remove_{field}") and old_filename:
            setattr(slide, field, None)
            delete_course_media(old_filename)

    db.session.commit()
    flash("Slide updated.", "success")
    return redirect(url_for("admin.lesson_edit", lesson_id=slide.lesson_id))


@admin_bp.route("/slides/<int:slide_id>/delete", methods=["POST"])
@admin_required
def slide_delete(slide_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    slide = LessonSlide.query.get_or_404(slide_id)
    lesson_id = slide.lesson_id

    delete_course_media(slide.image_en)
    delete_course_media(slide.audio_en)
    delete_course_media(slide.image_es)
    delete_course_media(slide.audio_es)
    db.session.delete(slide)
    db.session.commit()
    flash("Slide removed.", "success")
    return redirect(url_for("admin.lesson_edit", lesson_id=lesson_id))


@admin_bp.route("/slides/<int:slide_id>/move", methods=["POST"])
@admin_required
def slide_move(slide_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    slide = LessonSlide.query.get_or_404(slide_id)
    direction = request.form.get("direction")
    siblings = list(
        LessonSlide.query.filter_by(lesson_id=slide.lesson_id).order_by(LessonSlide.sort_order).all()
    )
    _swap_sort_order(siblings, slide, direction)
    return redirect(url_for("admin.lesson_edit", lesson_id=slide.lesson_id))


# ---------------------------------------------------------------- quiz questions

QUIZ_TYPE_LABELS = {
    "single_choice": "Single Choice",
    "multi_select": "Multiple Select",
    "true_false": "True / False",
    "short_answer": "Short Answer",
    "number": "Number",
    "long_answer": "Long Answer",
    "image_choice": "Image Choice",
    "file_upload": "File Upload",
}


def _quiz_question_fields_from_form(form):
    points_raw = form.get("points", "1").strip()
    return dict(
        question_type=form.get("question_type", "single_choice"),
        question_en=form.get("question_en", "").strip(),
        question_es=form.get("question_es", "").strip(),
        points=max(1, int(points_raw)) if points_raw.isdigit() and int(points_raw) > 0 else 1,
        required=form.get("required") == "on",
        feedback_correct_en=form.get("feedback_correct_en", "").strip() or None,
        feedback_correct_es=form.get("feedback_correct_es", "").strip() or None,
        feedback_incorrect_en=form.get("feedback_incorrect_en", "").strip() or None,
        feedback_incorrect_es=form.get("feedback_incorrect_es", "").strip() or None,
    )


def _apply_quiz_options(question, form):
    question.options.clear()
    en_values = form.getlist("option_en")
    es_values = form.getlist("option_es")
    correct_indices = {int(i) for i in form.getlist("option_correct") if i.isdigit()}
    for i, (en, es) in enumerate(zip(en_values, es_values)):
        en, es = en.strip(), es.strip()
        if not en:
            continue
        question.options.append(QuizQuestionOption(text_en=en, text_es=es or en, is_correct=i in correct_indices, sort_order=i))


def _apply_true_false_options(question, form):
    question.options.clear()
    correct = form.get("true_false_correct", "true")
    question.options.append(QuizQuestionOption(text_en="True", text_es="Verdadero", is_correct=correct == "true", sort_order=0))
    question.options.append(QuizQuestionOption(text_en="False", text_es="Falso", is_correct=correct == "false", sort_order=1))


def _apply_quiz_accepted_answers(question, form):
    question.accepted_answers.clear()
    en_values = form.getlist("answer_en")
    es_values = form.getlist("answer_es")
    for en, es in zip(en_values, es_values):
        en, es = en.strip(), es.strip()
        if not en:
            continue
        question.accepted_answers.append(QuizQuestionAcceptedAnswer(answer_en=en, answer_es=es or None))


def _apply_image_choice_options(question, form, files):
    """Rebuilds the option list from parallel arrays; keeps an existing
    image when no replacement is uploaded for that row, uploads/replaces
    otherwise, and cleans up files for rows the admin removed."""
    existing_list = form.getlist("image_option_existing")
    label_en_list = form.getlist("image_option_label_en")
    label_es_list = form.getlist("image_option_label_es")
    image_files = files.getlist("image_option_file")
    correct_index = form.get("image_option_correct", type=int)

    old_filenames = {o.image_filename for o in question.options if o.image_filename}
    kept_filenames = set()
    new_options = []
    count = max(len(existing_list), len(label_en_list), len(image_files))
    for i in range(count):
        existing_filename = existing_list[i] if i < len(existing_list) else ""
        label_en = label_en_list[i].strip() if i < len(label_en_list) else ""
        label_es = label_es_list[i].strip() if i < len(label_es_list) else ""
        uploaded = image_files[i] if i < len(image_files) else None
        filename = existing_filename or None
        if uploaded and uploaded.filename:
            filename = save_course_media(uploaded, "image")
            if existing_filename:
                delete_course_media(existing_filename)
        if not filename:
            continue
        kept_filenames.add(filename)
        new_options.append(QuizQuestionOption(
            text_en=label_en or None, text_es=label_es or None, image_filename=filename,
            is_correct=(i == correct_index), sort_order=i,
        ))

    for old_filename in old_filenames - kept_filenames:
        delete_course_media(old_filename)

    question.options.clear()
    for opt in new_options:
        question.options.append(opt)
    return len(new_options)


def _validate_and_apply_quiz_question(question, form, files):
    """Returns an error message string, or None on success."""
    fields = _quiz_question_fields_from_form(form)
    if fields["question_type"] not in QUIZ_QUESTION_TYPES:
        return "Invalid question type."
    if not fields["question_en"] or not fields["question_es"]:
        return "Question text (EN and ES) is required."

    for key, value in fields.items():
        setattr(question, key, value)
    qtype = fields["question_type"]

    if qtype in ("single_choice", "multi_select"):
        _apply_quiz_options(question, form)
        if len(question.options) < 2:
            return "Add at least 2 options."
        correct_count = sum(1 for o in question.options if o.is_correct)
        if qtype == "single_choice" and correct_count != 1:
            return "Single Choice needs exactly one correct option."
        if qtype == "multi_select" and correct_count < 1:
            return "Mark at least one option as correct."
        question.accepted_answers.clear()
        question.correct_number = None
    elif qtype == "true_false":
        _apply_true_false_options(question, form)
        question.accepted_answers.clear()
        question.correct_number = None
    elif qtype == "short_answer":
        _apply_quiz_accepted_answers(question, form)
        if not question.accepted_answers:
            return "Add at least 1 accepted answer."
        question.options.clear()
        question.correct_number = None
    elif qtype == "number":
        try:
            question.correct_number = float(form.get("correct_number", "").strip())
        except ValueError:
            return "Enter a valid correct number."
        tolerance_raw = form.get("number_tolerance", "").strip()
        try:
            question.number_tolerance = float(tolerance_raw) if tolerance_raw else 0
        except ValueError:
            question.number_tolerance = 0
        question.options.clear()
        question.accepted_answers.clear()
    elif qtype == "image_choice":
        count = _apply_image_choice_options(question, form, files)
        if count < 2:
            return "Add at least 2 image options."
        if not any(o.is_correct for o in question.options):
            return "Mark one image as correct."
        question.accepted_answers.clear()
        question.correct_number = None
    else:  # long_answer, file_upload — no correct-answer configuration at all
        question.options.clear()
        question.accepted_answers.clear()
        question.correct_number = None
    return None


@admin_bp.route("/lessons/<int:lesson_id>/questions/new", methods=["GET", "POST"])
@admin_required
def question_new(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        question = QuizQuestion(lesson_id=lesson.id, question_type="single_choice", question_en="", question_es="",
                                 sort_order=_next_sort_order(lesson.quiz_questions))
        error = _validate_and_apply_quiz_question(question, request.form, request.files)
        if error:
            flash(error, "error")
            return render_template("admin/quiz_question_form.html", lesson=lesson, question=None,
                                    question_types=QUIZ_QUESTION_TYPES, type_labels=QUIZ_TYPE_LABELS)

        db.session.add(question)
        db.session.commit()
        flash("Question added.", "success")
        return redirect(url_for("admin.lesson_edit", lesson_id=lesson.id))

    return render_template("admin/quiz_question_form.html", lesson=lesson, question=None,
                            question_types=QUIZ_QUESTION_TYPES, type_labels=QUIZ_TYPE_LABELS)


@admin_bp.route("/questions/<int:question_id>/edit", methods=["GET", "POST"])
@admin_required
def question_edit(question_id):
    question = QuizQuestion.query.get_or_404(question_id)
    lesson = question.lesson

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        error = _validate_and_apply_quiz_question(question, request.form, request.files)
        if error:
            flash(error, "error")
            return render_template("admin/quiz_question_form.html", lesson=lesson, question=question,
                                    question_types=QUIZ_QUESTION_TYPES, type_labels=QUIZ_TYPE_LABELS)

        db.session.commit()
        flash("Question updated.", "success")
        return redirect(url_for("admin.lesson_edit", lesson_id=lesson.id))

    return render_template("admin/quiz_question_form.html", lesson=lesson, question=question,
                            question_types=QUIZ_QUESTION_TYPES, type_labels=QUIZ_TYPE_LABELS)


@admin_bp.route("/questions/<int:question_id>/duplicate", methods=["POST"])
@admin_required
def question_duplicate(question_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    question = QuizQuestion.query.get_or_404(question_id)
    lesson = question.lesson

    new_question = QuizQuestion(
        lesson_id=lesson.id, question_type=question.question_type,
        question_en=f"{question.question_en} (Copy)", question_es=f"{question.question_es} (Copia)",
        points=question.points, required=question.required,
        feedback_correct_en=question.feedback_correct_en, feedback_correct_es=question.feedback_correct_es,
        feedback_incorrect_en=question.feedback_incorrect_en, feedback_incorrect_es=question.feedback_incorrect_es,
        correct_number=question.correct_number, number_tolerance=question.number_tolerance,
        sort_order=_next_sort_order(lesson.quiz_questions),
    )
    for opt in question.options:
        image_filename = duplicate_course_media(opt.image_filename) if opt.image_filename else None
        new_question.options.append(QuizQuestionOption(
            text_en=opt.text_en, text_es=opt.text_es, image_filename=image_filename,
            is_correct=opt.is_correct, sort_order=opt.sort_order,
        ))
    for ans in question.accepted_answers:
        new_question.accepted_answers.append(QuizQuestionAcceptedAnswer(answer_en=ans.answer_en, answer_es=ans.answer_es))

    db.session.add(new_question)
    db.session.commit()
    flash("Question duplicated.", "success")
    return redirect(url_for("admin.lesson_edit", lesson_id=lesson.id))


@admin_bp.route("/questions/<int:question_id>/delete", methods=["POST"])
@admin_required
def question_delete(question_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    question = QuizQuestion.query.get_or_404(question_id)
    lesson_id = question.lesson_id
    for opt in question.options:
        if opt.image_filename:
            delete_course_media(opt.image_filename)
    db.session.delete(question)
    db.session.commit()
    flash("Question removed.", "success")
    return redirect(url_for("admin.lesson_edit", lesson_id=lesson_id))


@admin_bp.route("/questions/<int:question_id>/move", methods=["POST"])
@admin_required
def question_move(question_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    question = QuizQuestion.query.get_or_404(question_id)
    direction = request.form.get("direction")
    siblings = list(
        QuizQuestion.query.filter_by(lesson_id=question.lesson_id).order_by(QuizQuestion.sort_order).all()
    )
    _swap_sort_order(siblings, question, direction)
    return redirect(url_for("admin.lesson_edit", lesson_id=question.lesson_id))


# ---------------------------------------------------------------- quiz attempt review (long_answer / file_upload)

@admin_bp.route("/lessons/<int:lesson_id>/quiz-attempts")
@admin_required
def quiz_attempts_review(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    attempts = (
        QuizAttempt.query.filter_by(lesson_id=lesson.id)
        .order_by(QuizAttempt.submitted_at.desc())
        .all()
    )
    return render_template("admin/quiz_attempts_review.html", lesson=lesson, attempts=attempts)


@admin_bp.route("/quiz-attempts/<int:attempt_id>/grade", methods=["GET", "POST"])
@admin_required
def quiz_attempt_grade(attempt_id):
    attempt = QuizAttempt.query.get_or_404(attempt_id)
    lesson = attempt.lesson
    pending_responses = [
        r for r in attempt.responses if r.question.question_type in ("long_answer", "file_upload")
    ]

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        for response in pending_responses:
            decision = request.form.get(f"decision_{response.id}")
            if decision not in ("correct", "incorrect"):
                continue
            points_raw = request.form.get(f"points_{response.id}", "").strip()
            max_points = response.question.points
            try:
                points = max(0, min(max_points, int(points_raw)))
            except ValueError:
                points = max_points if decision == "correct" else 0
            response.is_correct = decision == "correct"
            response.points_awarded = points
            response.admin_feedback = request.form.get(f"feedback_{response.id}", "").strip() or None
            response.reviewed_by_admin = True
            response.reviewed_at = datetime.utcnow()

        db.session.flush()
        still_pending = any(
            r.question.question_type in ("long_answer", "file_upload") and not r.reviewed_by_admin
            for r in attempt.responses
        )
        points_by_question_id = {r.question_id: r.points_awarded for r in attempt.responses}
        score_percent, score_points, max_score_points = compute_attempt_totals(lesson, points_by_question_id)
        attempt.score_percent = score_percent
        attempt.score_points = score_points
        attempt.max_score_points = max_score_points

        if still_pending:
            attempt.status = "needs_review"
            attempt.passed = None
        elif lesson.quiz_kind == "formative":
            attempt.status = "graded"
            attempt.passed = None
            mark_lesson_complete(attempt.student, lesson)
        else:
            attempt.status = "graded"
            attempt.passed = score_percent >= lesson.quiz_passing_percentage
            if attempt.passed:
                mark_lesson_complete(attempt.student, lesson)

        db.session.commit()
        flash("Review saved.", "success")
        return redirect(url_for("admin.quiz_attempts_review", lesson_id=lesson.id))

    return render_template("admin/quiz_attempt_grade.html", attempt=attempt, lesson=lesson, pending_responses=pending_responses)


# ---------------------------------------------------------------- lesson resources

@admin_bp.route("/lessons/<int:lesson_id>/resources/new", methods=["POST"])
@admin_required
def resource_new(lesson_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    lesson = Lesson.query.get_or_404(lesson_id)

    title_en = request.form.get("title_en", "").strip()
    title_es = request.form.get("title_es", "").strip()
    external_url = request.form.get("external_url", "").strip()
    uploaded = request.files.get("file")

    if not title_en or not title_es:
        flash("Resource title (EN and ES) is required.", "error")
        return redirect(url_for("admin.lesson_edit", lesson_id=lesson.id))
    if not external_url and not (uploaded and uploaded.filename):
        flash("Provide either a file or a URL for the resource.", "error")
        return redirect(url_for("admin.lesson_edit", lesson_id=lesson.id))

    try:
        file_filename = save_course_media(uploaded, "document") if uploaded and uploaded.filename else None
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin.lesson_edit", lesson_id=lesson.id))

    resource = LessonResource(
        lesson_id=lesson.id,
        title_en=title_en,
        title_es=title_es,
        file_filename=file_filename,
        external_url=external_url or None,
        sort_order=_next_sort_order(lesson.resources),
    )
    db.session.add(resource)
    db.session.commit()
    flash("Resource added.", "success")
    return redirect(url_for("admin.lesson_edit", lesson_id=lesson.id))


@admin_bp.route("/resources/<int:resource_id>/delete", methods=["POST"])
@admin_required
def resource_delete(resource_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    resource = LessonResource.query.get_or_404(resource_id)
    lesson_id = resource.lesson_id
    if resource.file_filename:
        delete_course_media(resource.file_filename)
    db.session.delete(resource)
    db.session.commit()
    flash("Resource removed.", "success")
    return redirect(url_for("admin.lesson_edit", lesson_id=lesson_id))


# ---------------------------------------------------------------- assignment submissions

@admin_bp.route("/lessons/<int:lesson_id>/submissions/<int:submission_id>/review", methods=["POST"])
@admin_required
def submission_review(lesson_id, submission_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    submission = Submission.query.get_or_404(submission_id)
    if submission.lesson_id != lesson_id:
        abort(404)

    decision = request.form.get("decision")
    submission.feedback = request.form.get("feedback", "").strip()
    submission.reviewed_at = datetime.utcnow()

    if decision == "approve":
        submission.status = Submission.STATUS_APPROVED
        mark_lesson_complete(submission.student, submission.lesson)
        flash(f"Approved {submission.student.name}'s submission.", "success")
    else:
        submission.status = Submission.STATUS_NEEDS_REVISION
        flash(f"Requested revision from {submission.student.name}.", "success")

    db.session.commit()
    return redirect(url_for("admin.lesson_edit", lesson_id=lesson_id))


# ---------------------------------------------------------------- media serving (admin preview)

@admin_bp.route("/uploads/editor-image", methods=["POST"])
@admin_required
def editor_image_upload():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    image = request.files.get("image")
    try:
        stored_path = save_course_media(image, "image")
    except ValueError as exc:
        return {"error": str(exc)}, 400
    if not stored_path:
        return {"error": "No image provided."}, 400
    return {"url": url_for("public.blog_content_image", lang="en", stored_path=stored_path)}


@admin_bp.route("/media/<path:stored_path>")
@admin_required
def media(stored_path):
    full_path = course_media_full_path(stored_path)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path, conditional=True)


# ---------------------------------------------------------------- helpers

def _swap_sort_order(siblings, item, direction):
    index = siblings.index(item)
    if direction == "up" and index > 0:
        other = siblings[index - 1]
    elif direction == "down" and index < len(siblings) - 1:
        other = siblings[index + 1]
    else:
        return
    item.sort_order, other.sort_order = other.sort_order, item.sort_order
    db.session.commit()


def _delete_lesson_files(lesson):
    if lesson.video_filename:
        delete_course_media(lesson.video_filename)
    for slide in lesson.slides:
        delete_course_media(slide.image_en)
        delete_course_media(slide.audio_en)
        delete_course_media(slide.image_es)
        delete_course_media(slide.audio_es)
    for resource in lesson.resources:
        delete_course_media(resource.file_filename)
    for submission in lesson.submissions:
        delete_course_media(submission.file_filename)
    if lesson.case_simulation:
        for document in lesson.case_simulation.documents:
            delete_course_media(document.file_filename)
    for question in lesson.quiz_questions:
        for opt in question.options:
            if opt.image_filename:
                delete_course_media(opt.image_filename)
    for attempt in QuizAttempt.query.filter_by(lesson_id=lesson.id).all():
        for response in attempt.responses:
            if response.file_filename:
                delete_course_media(response.file_filename)
