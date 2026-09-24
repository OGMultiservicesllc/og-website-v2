from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for

from app.auth import validate_csrf
from app.blueprints.account.routes import account_bp
from app.case_scoring import (
    compute_attempt_totals,
    grade_multi_select,
    grade_multiple_choice,
    grade_short_answer,
    points_from_free_response_fraction,
)
from app.extensions import db
from app.forensic_ai import evaluate_free_response
from app.i18n import get_text
from app.models import (
    CaseSimulation,
    CaseSimulationAttempt,
    CaseSimulationResponse,
    CaseSimulationResponseOption,
    Enrollment,
    Lesson,
)
from app.progress import mark_lesson_complete
from app.student_auth import current_student, student_required


def _load_case_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.lesson_type != "case_simulation" or not lesson.case_simulation:
        abort(404)
    course = lesson.section.course
    student = current_student()
    is_enrolled = bool(student and Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first())
    if not lesson.is_preview and not is_enrolled:
        abort(403)
    return lesson, course, lesson.case_simulation


@account_bp.route("/case/<int:lesson_id>")
@student_required
def case_lesson(lang, lesson_id):
    lesson, course, case = _load_case_lesson(lesson_id)
    student = current_student()

    attempts = (
        CaseSimulationAttempt.query.filter_by(case_simulation_id=case.id, student_id=student.id)
        .order_by(CaseSimulationAttempt.started_at.desc())
        .all()
    )
    in_progress = next((a for a in attempts if a.status == "in_progress"), None)
    attempts_used = len(attempts)
    can_start = case.max_attempts is None or attempts_used < case.max_attempts

    return render_template(
        "account/case_lesson.html",
        lesson=lesson, course=course, case=case,
        attempts=[a for a in attempts if a.status != "in_progress"],
        in_progress=in_progress, can_start=can_start, attempts_used=attempts_used,
    )


@account_bp.route("/case/<int:lesson_id>/start", methods=["POST"])
@student_required
def case_start(lang, lesson_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    lesson, course, case = _load_case_lesson(lesson_id)
    student = current_student()

    existing = CaseSimulationAttempt.query.filter_by(
        case_simulation_id=case.id, student_id=student.id, status="in_progress"
    ).first()
    if existing:
        return redirect(url_for("account.case_attempt", lang=lang, attempt_id=existing.id))

    if case.max_attempts is not None:
        used = CaseSimulationAttempt.query.filter_by(case_simulation_id=case.id, student_id=student.id).count()
        if used >= case.max_attempts:
            flash(get_text(lang, "flash_case_no_attempts_left"), "error")
            return redirect(url_for("account.case_lesson", lang=lang, lesson_id=lesson.id))

    attempt = CaseSimulationAttempt(case_simulation_id=case.id, student_id=student.id, status="in_progress")
    db.session.add(attempt)
    db.session.commit()
    return redirect(url_for("account.case_attempt", lang=lang, attempt_id=attempt.id))


def _load_attempt(attempt_id, student):
    attempt = CaseSimulationAttempt.query.get_or_404(attempt_id)
    if attempt.student_id != student.id:
        abort(403)
    return attempt


@account_bp.route("/case/attempt/<int:attempt_id>")
@student_required
def case_attempt(lang, attempt_id):
    student = current_student()
    attempt = _load_attempt(attempt_id, student)
    if attempt.status != "in_progress":
        return redirect(url_for("account.case_result", lang=lang, attempt_id=attempt.id))
    case = attempt.case
    return render_template("account/case_attempt.html", case=case, attempt=attempt, preview=False, lesson=case.lesson)


@account_bp.route("/case/attempt/<int:attempt_id>/submit", methods=["POST"])
@student_required
def case_submit(lang, attempt_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    student = current_student()
    attempt = _load_attempt(attempt_id, student)
    if attempt.status != "in_progress":
        return redirect(url_for("account.case_result", lang=lang, attempt_id=attempt.id))

    case = attempt.case
    points_by_task_id = {}
    any_pending = False

    for task in case.active_tasks:
        response = CaseSimulationResponse(attempt_id=attempt.id, task_id=task.id)
        if task.requires_justification:
            response.justification_text = request.form.get(f"justification_{task.id}", "").strip() or None

        if task.task_type == "multiple_choice":
            selected = request.form.get(f"option_{task.id}", type=int)
            response.selected_option_id = selected
            response.is_correct, response.points_awarded = grade_multiple_choice(task, selected)

        elif task.task_type == "multi_select":
            selected_ids = [int(v) for v in request.form.getlist(f"option_{task.id}") if v.isdigit()]
            response.is_correct, response.points_awarded = grade_multi_select(task, selected_ids)
            db.session.add(response)
            db.session.flush()
            for option_id in selected_ids:
                db.session.add(CaseSimulationResponseOption(response_id=response.id, option_id=option_id))
            points_by_task_id[task.id] = response.points_awarded
            continue

        elif task.task_type == "short_answer":
            text = request.form.get(f"answer_{task.id}", "").strip()
            response.response_text = text or None
            response.is_correct, response.points_awarded = grade_short_answer(task, text)

        else:  # free_response
            text = request.form.get(f"answer_{task.id}", "").strip()
            response.response_text = text or None
            try:
                result = evaluate_free_response(
                    task.prompt("en"), task.expected_response("en"), task.rubric_notes("en"), text,
                )
                response.points_awarded = points_from_free_response_fraction(task, result["score_fraction"])
                response.ai_feedback_en = result["feedback_en"]
                response.ai_feedback_es = result["feedback_es"]
                response.reviewed_by_ai = True
            except Exception:  # noqa: BLE001 — never lose the response over an API hiccup
                response.points_awarded = 0
                response.reviewed_by_ai = False
                any_pending = True

        db.session.add(response)
        points_by_task_id[task.id] = response.points_awarded

    score, max_score, passed = compute_attempt_totals(case, points_by_task_id)
    attempt.score = score
    attempt.max_score = max_score
    attempt.submitted_at = datetime.utcnow()

    if any_pending:
        attempt.status = "needs_review"
        attempt.passed = None
    else:
        attempt.status = "submitted"
        attempt.passed = passed
        if case.passing_score is None or passed:
            mark_lesson_complete(student, case.lesson)

    db.session.commit()
    flash(get_text(lang, "flash_case_submitted"), "success")
    return redirect(url_for("account.case_result", lang=lang, attempt_id=attempt.id))


@account_bp.route("/case/attempt/<int:attempt_id>/result")
@student_required
def case_result(lang, attempt_id):
    student = current_student()
    attempt = _load_attempt(attempt_id, student)
    if attempt.status == "in_progress":
        return redirect(url_for("account.case_attempt", lang=lang, attempt_id=attempt.id))
    case = attempt.case
    responses_by_task_id = {r.task_id: r for r in attempt.responses}
    return render_template(
        "account/case_result.html", case=case, attempt=attempt, lesson=case.lesson,
        responses_by_task_id=responses_by_task_id,
    )
