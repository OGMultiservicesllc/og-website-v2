import os
import re
from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, session, url_for
from sqlalchemy.exc import IntegrityError

from app.activity import log_event
from app.auth import validate_csrf
from app.extensions import db
from app.i18n import get_text, valid_language
from app.models import (
    Certificate,
    Course,
    Enrollment,
    FormSubmission,
    Lesson,
    QuizAttempt,
    QuizResponse,
    QuizResponseOption,
    Student,
    Submission,
)
from app.certificates import build_cert_context, is_certificate_eligible
from app.ratelimit import allow, client_ip
from app.progress import course_progress, get_or_create_certificate, is_lesson_unlocked, mark_lesson_complete
from app.quiz_scoring import compute_attempt_totals, grade_multi_select, grade_number, grade_short_answer, grade_single_choice
from app.student_auth import authenticate_student, current_student, register_student, student_required
from app.uploads import course_media_full_path, delete_course_media, save_course_media

account_bp = Blueprint("account", __name__, url_prefix="/<lang>/account")


@account_bp.url_value_preprocessor
def check_lang(endpoint, values):
    if not valid_language(values.get("lang")):
        abort(404)


def _safe_next(lang, next_url):
    """Where to go after signing in. Only a same-site path is accepted (never a
    full URL or protocol-relative //host), and it is rewritten to the language the
    customer is using now, so switching language mid-way doesn't undo their journey."""
    if (
        next_url
        and next_url.startswith("/")
        and not next_url.startswith("//")
        and "\\" not in next_url
        and "://" not in next_url
        and ".." not in next_url
    ):
        match = re.match(r"^/(en|es)(/.*)?$", next_url)
        if match:
            return f"/{lang}{match.group(2) or '/'}"
    return url_for("account.dashboard", lang=lang)


def _wants_intake(next_url):
    return bool(next_url and ("/start" in next_url or "/f/" in next_url))


@account_bp.route("/register", methods=["GET", "POST"])
def register(lang):
    if current_student():
        return redirect(url_for("account.dashboard", lang=lang))

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not allow(f"register:{client_ip()}", 10, 3600):
            flash(get_text(lang, "flash_too_many"), "error")
            return render_template("account/register.html", wants_intake=_wants_intake(request.args.get("next")))

        error = None
        if not name:
            error = get_text(lang, "flash_name_required")
        elif not email or "@" not in email:
            error = get_text(lang, "flash_email_invalid")
        elif len(password) < 8:
            error = get_text(lang, "flash_password_short")

        if not error:
            student = register_student(email, password, name)
            db.session.add(student)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error = get_text(lang, "flash_email_taken")

        if error:
            flash(error, "error")
            return render_template("account/register.html", wants_intake=_wants_intake(request.args.get("next")))

        student.preferred_language = lang
        db.session.commit()
        session.clear()  # new session on sign-up: never reuse a pre-login session id
        session["student_id"] = student.id
        log_event(student.id, "account_created")
        from app import verification

        verification.issue_code(student, "verify", lang=lang)
        next_url = request.args.get("next")
        return redirect(url_for("account.verify_email", lang=lang, next=next_url) if next_url else url_for("account.verify_email", lang=lang))

    return render_template("account/register.html", wants_intake=_wants_intake(request.args.get("next")))


@account_bp.route("/login", methods=["GET", "POST"])
def login(lang):
    if current_student():
        return redirect(url_for("account.dashboard", lang=lang))

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        if not allow(f"login:{client_ip()}", 12, 300):
            flash(get_text(lang, "flash_too_many"), "error")
            return render_template("account/login.html", wants_intake=_wants_intake(request.args.get("next")))
        student = authenticate_student(email, password)
        if not student:
            flash(get_text(lang, "flash_login_invalid"), "error")
            return render_template("account/login.html", wants_intake=_wants_intake(request.args.get("next")))

        session.clear()  # session fixation: issue a fresh session on every sign-in
        session["student_id"] = student.id
        student.last_login_at = datetime.utcnow()
        db.session.commit()
        log_event(student.id, "login")
        next_url = request.form.get("next") or request.args.get("next")
        return redirect(_safe_next(lang, next_url))

    return render_template("account/login.html", wants_intake=_wants_intake(request.args.get("next")))


@account_bp.route("/logout")
def logout(lang):
    session.pop("student_id", None)
    return redirect(url_for("public.home", lang=lang))


@account_bp.route("/dashboard")
@student_required
def dashboard(lang):
    """My OG Account — Home. Built entirely from `app.account_dashboard.home_data`: the aggregation layer
    that reads the existing Case / Tax / ITIN / Document Vault architecture, so this route stays a thin view."""
    from app import account_dashboard
    from app.blueprints.account.portal_routes import course_cards

    student = current_student()
    hour = datetime.now().hour
    greeting = "acct_good_morning" if hour < 12 else ("acct_good_afternoon" if hour < 18 else "acct_good_evening")
    data = account_dashboard.home_data(student, lang)
    active_course = next((c for c in course_cards(student, lang) if c["status"] == "in_progress"), None)
    return render_template("account/dashboard.html", section="overview", greeting=greeting, active_course=active_course, **data)


def _new_expiry(course):
    if not course.access_duration_days:
        return None
    return datetime.utcnow() + timedelta(days=course.access_duration_days)


@account_bp.route("/courses/<int:course_id>/enroll", methods=["POST"])
@student_required
def enroll(lang, course_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    course = Course.query.get_or_404(course_id)
    if not course.is_published:
        abort(404)

    student = current_student()
    existing = Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first()
    if not existing:
        db.session.add(Enrollment(student_id=student.id, course_id=course.id, expires_at=_new_expiry(course)))
        db.session.commit()
        log_event(student.id, "course_enrolled", entity=("course", course.id), meta={"course": course.title_en})
        flash(get_text(lang, "flash_enrolled"), "success")
    elif existing.is_revoked:
        pass  # Admin revoked this on purpose — a customer re-clicking "Enroll" must never silently reinstate it.
    elif existing.is_expired:
        existing.enrolled_at = datetime.utcnow()
        existing.expires_at = _new_expiry(course)
        db.session.commit()
        flash(get_text(lang, "flash_access_renewed"), "success")

    return redirect(url_for("public.course_detail", lang=lang, slug=course.slug))


def _require_enrollment(student, lesson):
    course = lesson.section.course
    enrollment = Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first()
    if not enrollment and not lesson.is_preview:
        abort(403)
    if enrollment and not enrollment.is_active:
        abort(403)
    if enrollment and not is_lesson_unlocked(student, course, lesson):
        abort(403)
    return course


@account_bp.route("/lessons/<int:lesson_id>/complete", methods=["POST"])
@student_required
def lesson_complete(lang, lesson_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    lesson = Lesson.query.get_or_404(lesson_id)
    student = current_student()
    course = _require_enrollment(student, lesson)

    mark_lesson_complete(student, lesson)
    flash(get_text(lang, "flash_lesson_complete"), "success")

    next_lesson_id = request.form.get("next_lesson_id", type=int)
    if next_lesson_id:
        next_lesson = Lesson.query.get(next_lesson_id)
        if next_lesson and next_lesson.section.course_id == course.id and is_lesson_unlocked(student, course, next_lesson):
            return redirect(url_for("public.lesson_view", lang=lang, slug=course.slug, lesson_id=next_lesson.id))

    return redirect(url_for("public.lesson_view", lang=lang, slug=course.slug, lesson_id=lesson.id))


@account_bp.route("/lessons/<int:lesson_id>/quiz-submit", methods=["POST"])
@student_required
def quiz_submit(lang, lesson_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.lesson_type != "quiz":
        abort(404)
    student = current_student()
    course = _require_enrollment(student, lesson)

    is_formative = lesson.quiz_kind == "formative"
    if not is_formative:
        existing_attempts = QuizAttempt.query.filter_by(student_id=student.id, lesson_id=lesson.id).count()
        if not lesson.quiz_allow_retry and existing_attempts >= 1:
            abort(403)
        if lesson.quiz_max_attempts is not None and existing_attempts >= lesson.quiz_max_attempts:
            abort(403)

    attempt = QuizAttempt(student_id=student.id, lesson_id=lesson.id, score_percent=0, status="graded")
    db.session.add(attempt)
    db.session.flush()

    points_by_question_id = {}
    any_pending = False

    for question in lesson.quiz_questions:
        response = QuizResponse(attempt_id=attempt.id, question_id=question.id)
        qtype = question.question_type

        if qtype in ("single_choice", "true_false", "image_choice"):
            selected = request.form.get(f"question_{question.id}", type=int)
            response.selected_option_id = selected
            response.is_correct, response.points_awarded = grade_single_choice(question, selected)

        elif qtype == "multi_select":
            selected_ids = [int(v) for v in request.form.getlist(f"question_{question.id}") if v.isdigit()]
            response.is_correct, response.points_awarded = grade_multi_select(question, selected_ids)
            db.session.add(response)
            db.session.flush()
            for option_id in selected_ids:
                db.session.add(QuizResponseOption(response_id=response.id, option_id=option_id))
            points_by_question_id[question.id] = response.points_awarded
            continue

        elif qtype == "short_answer":
            text = request.form.get(f"question_{question.id}", "").strip()
            response.response_text = text or None
            response.is_correct, response.points_awarded = grade_short_answer(question, text)

        elif qtype == "number":
            raw = request.form.get(f"question_{question.id}", "").strip()
            try:
                value = float(raw) if raw else None
            except ValueError:
                value = None
            response.response_number = value
            response.is_correct, response.points_awarded = grade_number(question, value)

        elif qtype == "long_answer":
            text = request.form.get(f"question_{question.id}", "").strip()
            response.response_text = text or None
            response.points_awarded = 0
            any_pending = True

        else:  # file_upload
            uploaded = request.files.get(f"question_{question.id}")
            if uploaded and uploaded.filename:
                try:
                    response.file_filename = save_course_media(uploaded, "document")
                except ValueError:
                    response.file_filename = None
            response.points_awarded = 0
            any_pending = True

        db.session.add(response)
        points_by_question_id[question.id] = response.points_awarded

    score_percent, score_points, max_score_points = compute_attempt_totals(lesson, points_by_question_id)
    attempt.score_percent = score_percent
    attempt.score_points = score_points
    attempt.max_score_points = max_score_points

    if is_formative:
        attempt.status = "needs_review" if any_pending else "graded"
        attempt.passed = None
        mark_lesson_complete(student, lesson)
    elif any_pending:
        attempt.status = "needs_review"
        attempt.passed = None
    else:
        attempt.status = "graded"
        attempt.passed = score_percent >= lesson.quiz_passing_percentage
        if attempt.passed:
            mark_lesson_complete(student, lesson)

    db.session.commit()

    if not lesson.quiz_show_results:
        flash(get_text(lang, "flash_quiz_submitted"), "success")
        return redirect(url_for("public.lesson_view", lang=lang, slug=course.slug, lesson_id=lesson.id))

    return redirect(url_for("account.quiz_result", lang=lang, attempt_id=attempt.id))


@account_bp.route("/quiz-attempts/<int:attempt_id>/result")
@student_required
def quiz_result(lang, attempt_id):
    student = current_student()
    attempt = QuizAttempt.query.get_or_404(attempt_id)
    if attempt.student_id != student.id:
        abort(403)
    lesson = attempt.lesson
    course = lesson.section.course
    progress = course_progress(student, course)
    certificate = (
        Certificate.query.filter_by(student_id=student.id, course_id=course.id).first()
        if course.certificate_enabled else None
    )
    responses_by_question_id = {r.question_id: r for r in attempt.responses}
    correct_count = sum(1 for r in attempt.responses if r.is_correct)
    return render_template(
        "account/quiz_result.html", attempt=attempt, lesson=lesson, course=course, progress=progress,
        certificate=certificate, responses_by_question_id=responses_by_question_id, correct_count=correct_count,
    )


@account_bp.route("/lessons/<int:lesson_id>/assignment-submit", methods=["POST"])
@student_required
def assignment_submit(lang, lesson_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.lesson_type != "assignment":
        abort(404)
    student = current_student()
    course = _require_enrollment(student, lesson)

    text_response = request.form.get("text_response", "").strip()
    uploaded = request.files.get("file")

    submission = Submission.query.filter_by(student_id=student.id, lesson_id=lesson.id).first()
    if not submission:
        submission = Submission(student_id=student.id, lesson_id=lesson.id)
        db.session.add(submission)

    submission.text_response = text_response or None
    if uploaded and uploaded.filename:
        if submission.file_filename:
            delete_course_media(submission.file_filename)
        try:
            submission.file_filename = save_course_media(uploaded, "document")
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("public.lesson_view", lang=lang, slug=course.slug, lesson_id=lesson.id))

    submission.status = Submission.STATUS_SUBMITTED
    submission.submitted_at = datetime.utcnow()
    submission.reviewed_at = None
    db.session.commit()

    flash(get_text(lang, "flash_assignment_submitted"), "success")
    return redirect(url_for("public.lesson_view", lang=lang, slug=course.slug, lesson_id=lesson.id))


@account_bp.route("/courses/<slug>/certificate")
@student_required
def certificate(lang, slug):
    course = Course.query.filter_by(slug=slug, is_published=True).first_or_404()
    student = current_student()

    enrolled = Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first()
    if not enrolled:
        abort(403)
    if not course.certificate_enabled:
        abort(404)

    cert = Certificate.query.filter_by(student_id=student.id, course_id=course.id).first()
    if not cert:
        if not is_certificate_eligible(student, course):
            flash(get_text(lang, "flash_certificate_locked"), "error")
            return redirect(url_for("public.course_detail", lang=lang, slug=course.slug))
        cert = get_or_create_certificate(student, course)

    cert_context = build_cert_context(course, lang, student=student, certificate=cert)
    return render_template(
        "account/certificate.html", certificate=cert, course=course, student=student, cert=cert_context,
    )


@account_bp.route("/courses/<slug>/certificate/file")
@student_required
def certificate_file(lang, slug):
    course = Course.query.filter_by(slug=slug, is_published=True).first_or_404()
    student = current_student()
    cert = Certificate.query.filter_by(student_id=student.id, course_id=course.id).first_or_404()
    if not cert.file_filename:
        abort(404)
    full_path = course_media_full_path(cert.file_filename)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path, conditional=True)
