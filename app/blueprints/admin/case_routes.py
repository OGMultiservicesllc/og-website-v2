from flask import abort, flash, redirect, render_template, request, url_for

from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp, _next_sort_order, _swap_sort_order
from app.extensions import db
from app.models import (
    CaseSimulation,
    CaseSimulationDocument,
    CaseSimulationTask,
    CaseSimulationTaskAcceptedAnswer,
    CaseSimulationTaskOption,
    Lesson,
    TASK_TYPES,
)
from app.uploads import delete_course_media, duplicate_course_media, save_course_media

CASE_DOC_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp"}

TASK_TYPE_LABELS = {
    "multiple_choice": "Multiple Choice",
    "multi_select": "Multi-Select (checklist)",
    "short_answer": "Short Answer",
    "free_response": "Free Response",
}


# ---------------------------------------------------------------- case

@admin_bp.route("/lessons/<int:lesson_id>/case", methods=["GET", "POST"])
@admin_required
def case_edit(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.lesson_type != "case_simulation":
        abort(404)
    case = lesson.case_simulation
    if not case:
        case = CaseSimulation(lesson_id=lesson.id, title_en=lesson.title_en, title_es=lesson.title_es)
        db.session.add(case)
        db.session.commit()

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        title_en = request.form.get("title_en", "").strip()
        title_es = request.form.get("title_es", "").strip()
        if not title_en or not title_es:
            flash("Case title (EN and ES) is required.", "error")
            return render_template("admin/case_edit.html", lesson=lesson, case=case)

        case.title_en = title_en
        case.title_es = title_es
        case.description_en = request.form.get("description_en", "").strip() or None
        case.description_es = request.form.get("description_es", "").strip() or None
        case.client_profile_en = request.form.get("client_profile_en", "").strip() or None
        case.client_profile_es = request.form.get("client_profile_es", "").strip() or None
        case.instructions_en = request.form.get("instructions_en", "").strip() or None
        case.instructions_es = request.form.get("instructions_es", "").strip() or None

        passing_score = request.form.get("passing_score", "").strip()
        case.passing_score = int(passing_score) if passing_score.isdigit() else None
        max_attempts = request.form.get("max_attempts", "").strip()
        case.max_attempts = int(max_attempts) if max_attempts.isdigit() else None
        case.is_active = request.form.get("is_active") == "on"

        db.session.commit()
        flash("Case updated.", "success")
        return redirect(url_for("admin.case_edit", lesson_id=lesson.id))

    return render_template("admin/case_edit.html", lesson=lesson, case=case)


@admin_bp.route("/cases/<int:case_id>/duplicate", methods=["POST"])
@admin_required
def case_duplicate(case_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    source_case = CaseSimulation.query.get_or_404(case_id)
    source_lesson = source_case.lesson
    section = source_lesson.section

    new_lesson = Lesson(
        section_id=section.id,
        lesson_type="case_simulation",
        title_en=f"{source_lesson.title_en} (Copy)",
        title_es=f"{source_lesson.title_es} (Copia)",
        is_preview=False,
        sort_order=_next_sort_order(section.lessons),
    )
    db.session.add(new_lesson)
    db.session.flush()

    new_case = CaseSimulation(
        lesson_id=new_lesson.id,
        title_en=f"{source_case.title_en} (Copy)",
        title_es=f"{source_case.title_es} (Copia)",
        description_en=source_case.description_en,
        description_es=source_case.description_es,
        client_profile_en=source_case.client_profile_en,
        client_profile_es=source_case.client_profile_es,
        instructions_en=source_case.instructions_en,
        instructions_es=source_case.instructions_es,
        passing_score=source_case.passing_score,
        max_attempts=source_case.max_attempts,
        is_active=source_case.is_active,
    )
    for doc in source_case.documents:
        new_case.documents.append(CaseSimulationDocument(
            label_en=doc.label_en, label_es=doc.label_es, doc_type=doc.doc_type,
            file_filename=duplicate_course_media(doc.file_filename) or doc.file_filename,
            sort_order=doc.sort_order, is_active=doc.is_active,
        ))
    for task in source_case.tasks:
        new_task = CaseSimulationTask(
            task_type=task.task_type, prompt_en=task.prompt_en, prompt_es=task.prompt_es,
            explanation_en=task.explanation_en, explanation_es=task.explanation_es,
            points=task.points, requires_justification=task.requires_justification,
            sort_order=task.sort_order, is_active=task.is_active,
            expected_response_en=task.expected_response_en, expected_response_es=task.expected_response_es,
            rubric_notes_en=task.rubric_notes_en, rubric_notes_es=task.rubric_notes_es,
        )
        for opt in task.options:
            new_task.options.append(CaseSimulationTaskOption(
                text_en=opt.text_en, text_es=opt.text_es, is_correct=opt.is_correct, sort_order=opt.sort_order,
            ))
        for ans in task.accepted_answers:
            new_task.accepted_answers.append(CaseSimulationTaskAcceptedAnswer(answer_en=ans.answer_en, answer_es=ans.answer_es))
        new_case.tasks.append(new_task)

    db.session.add(new_case)
    db.session.commit()
    flash(f"Duplicated as \"{new_lesson.title_en}\". Student attempts were not copied.", "success")
    return redirect(url_for("admin.case_edit", lesson_id=new_lesson.id))


@admin_bp.route("/cases/<int:case_id>/preview")
@admin_required
def case_preview(case_id):
    case = CaseSimulation.query.get_or_404(case_id)
    return render_template("account/case_attempt.html", case=case, attempt=None, preview=True, lang="en")


# ---------------------------------------------------------------- documents

@admin_bp.route("/cases/<int:case_id>/documents/new", methods=["POST"])
@admin_required
def document_new(case_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    case = CaseSimulation.query.get_or_404(case_id)

    label_en = request.form.get("label_en", "").strip()
    label_es = request.form.get("label_es", "").strip()
    uploaded = request.files.get("file")
    if not label_en or not label_es:
        flash("Document label (EN and ES) is required.", "error")
        return redirect(url_for("admin.case_edit", lesson_id=case.lesson_id))
    if not uploaded or not uploaded.filename:
        flash("Choose a PDF or image file to upload.", "error")
        return redirect(url_for("admin.case_edit", lesson_id=case.lesson_id))

    ext = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
    if ext not in CASE_DOC_EXTENSIONS:
        flash("Case documents must be a PDF or an image (JPG, PNG, WEBP).", "error")
        return redirect(url_for("admin.case_edit", lesson_id=case.lesson_id))

    try:
        file_filename = save_course_media(uploaded, "document")
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin.case_edit", lesson_id=case.lesson_id))

    db.session.add(CaseSimulationDocument(
        case_simulation_id=case.id, label_en=label_en, label_es=label_es,
        doc_type=request.form.get("doc_type", "").strip() or None,
        file_filename=file_filename, sort_order=_next_sort_order(case.documents),
    ))
    db.session.commit()
    flash("Document added.", "success")
    return redirect(url_for("admin.case_edit", lesson_id=case.lesson_id))


@admin_bp.route("/documents/<int:document_id>/edit", methods=["POST"])
@admin_required
def document_edit(document_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    doc = CaseSimulationDocument.query.get_or_404(document_id)

    label_en = request.form.get("label_en", "").strip()
    label_es = request.form.get("label_es", "").strip()
    if label_en and label_es:
        doc.label_en = label_en
        doc.label_es = label_es
        doc.doc_type = request.form.get("doc_type", "").strip() or None
        doc.is_active = request.form.get("is_active") == "on"

        uploaded = request.files.get("file")
        if uploaded and uploaded.filename:
            ext = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
            if ext not in CASE_DOC_EXTENSIONS:
                flash("Case documents must be a PDF or an image (JPG, PNG, WEBP).", "error")
                return redirect(url_for("admin.case_edit", lesson_id=doc.case.lesson_id))
            try:
                new_filename = save_course_media(uploaded, "document")
            except ValueError as exc:
                flash(str(exc), "error")
                return redirect(url_for("admin.case_edit", lesson_id=doc.case.lesson_id))
            delete_course_media(doc.file_filename)
            doc.file_filename = new_filename

        db.session.commit()
        flash("Document updated.", "success")
    return redirect(url_for("admin.case_edit", lesson_id=doc.case.lesson_id))


@admin_bp.route("/documents/<int:document_id>/delete", methods=["POST"])
@admin_required
def document_delete(document_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    doc = CaseSimulationDocument.query.get_or_404(document_id)
    lesson_id = doc.case.lesson_id
    delete_course_media(doc.file_filename)
    db.session.delete(doc)
    db.session.commit()
    flash("Document removed.", "success")
    return redirect(url_for("admin.case_edit", lesson_id=lesson_id))


@admin_bp.route("/documents/<int:document_id>/move", methods=["POST"])
@admin_required
def document_move(document_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    doc = CaseSimulationDocument.query.get_or_404(document_id)
    direction = request.form.get("direction")
    siblings = list(
        CaseSimulationDocument.query.filter_by(case_simulation_id=doc.case_simulation_id)
        .order_by(CaseSimulationDocument.sort_order).all()
    )
    _swap_sort_order(siblings, doc, direction)
    return redirect(url_for("admin.case_edit", lesson_id=doc.case.lesson_id))


# ---------------------------------------------------------------- tasks

def _task_fields_from_form(form):
    points_raw = form.get("points", "1").strip()
    return dict(
        task_type=form.get("task_type", "multiple_choice"),
        prompt_en=form.get("prompt_en", "").strip(),
        prompt_es=form.get("prompt_es", "").strip(),
        explanation_en=form.get("explanation_en", "").strip() or None,
        explanation_es=form.get("explanation_es", "").strip() or None,
        points=max(1, int(points_raw)) if points_raw.isdigit() and int(points_raw) > 0 else 1,
        requires_justification=form.get("requires_justification") == "on",
        expected_response_en=form.get("expected_response_en", "").strip() or None,
        expected_response_es=form.get("expected_response_es", "").strip() or None,
        rubric_notes_en=form.get("rubric_notes_en", "").strip() or None,
        rubric_notes_es=form.get("rubric_notes_es", "").strip() or None,
    )


def _apply_task_options(task, form):
    task.options.clear()
    en_values = form.getlist("option_en")
    es_values = form.getlist("option_es")
    correct_indices = {int(i) for i in form.getlist("option_correct") if i.isdigit()}
    for i, (en, es) in enumerate(zip(en_values, es_values)):
        en, es = en.strip(), es.strip()
        if not en:
            continue
        task.options.append(CaseSimulationTaskOption(text_en=en, text_es=es or en, is_correct=i in correct_indices, sort_order=i))


def _apply_accepted_answers(task, form):
    task.accepted_answers.clear()
    en_values = form.getlist("answer_en")
    es_values = form.getlist("answer_es")
    for en, es in zip(en_values, es_values):
        en, es = en.strip(), es.strip()
        if not en:
            continue
        task.accepted_answers.append(CaseSimulationTaskAcceptedAnswer(answer_en=en, answer_es=es or None))


def _validate_and_apply_task(task, form):
    """Returns an error message string, or None on success."""
    fields = _task_fields_from_form(form)
    if fields["task_type"] not in TASK_TYPES:
        return "Invalid task type."
    if not fields["prompt_en"] or not fields["prompt_es"]:
        return "Task prompt (EN and ES) is required."

    for key, value in fields.items():
        setattr(task, key, value)

    if fields["task_type"] in ("multiple_choice", "multi_select"):
        _apply_task_options(task, form)
        if len(task.options) < 2:
            return "Add at least 2 options."
        if not any(o.is_correct for o in task.options):
            return "Mark at least one option as correct."
        task.accepted_answers.clear()
    elif fields["task_type"] == "short_answer":
        _apply_accepted_answers(task, form)
        if not task.accepted_answers:
            return "Add at least 1 accepted answer."
        task.options.clear()
    else:  # free_response
        if not fields["expected_response_en"]:
            return "A model expected answer (English) is required so the AI has something to grade against."
        task.options.clear()
        task.accepted_answers.clear()
    return None


@admin_bp.route("/cases/<int:case_id>/tasks/new", methods=["GET", "POST"])
@admin_required
def task_new(case_id):
    case = CaseSimulation.query.get_or_404(case_id)

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        task = CaseSimulationTask(case_simulation_id=case.id, task_type="multiple_choice", prompt_en="", prompt_es="",
                                   sort_order=_next_sort_order(case.tasks))
        error = _validate_and_apply_task(task, request.form)
        if error:
            flash(error, "error")
            return render_template("admin/case_task_form.html", case=case, task=None, task_types=TASK_TYPES, task_type_labels=TASK_TYPE_LABELS)

        db.session.add(task)
        db.session.commit()
        flash("Task added.", "success")
        return redirect(url_for("admin.case_edit", lesson_id=case.lesson_id))

    return render_template("admin/case_task_form.html", case=case, task=None, task_types=TASK_TYPES, task_type_labels=TASK_TYPE_LABELS)


@admin_bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@admin_required
def task_edit(task_id):
    task = CaseSimulationTask.query.get_or_404(task_id)
    case = task.case

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        error = _validate_and_apply_task(task, request.form)
        if error:
            flash(error, "error")
            return render_template("admin/case_task_form.html", case=case, task=task, task_types=TASK_TYPES, task_type_labels=TASK_TYPE_LABELS)

        db.session.commit()
        flash("Task updated.", "success")
        return redirect(url_for("admin.case_edit", lesson_id=case.lesson_id))

    return render_template("admin/case_task_form.html", case=case, task=task, task_types=TASK_TYPES, task_type_labels=TASK_TYPE_LABELS)


@admin_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@admin_required
def task_delete(task_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    task = CaseSimulationTask.query.get_or_404(task_id)
    lesson_id = task.case.lesson_id
    db.session.delete(task)
    db.session.commit()
    flash("Task removed.", "success")
    return redirect(url_for("admin.case_edit", lesson_id=lesson_id))


@admin_bp.route("/tasks/<int:task_id>/move", methods=["POST"])
@admin_required
def task_move(task_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    task = CaseSimulationTask.query.get_or_404(task_id)
    direction = request.form.get("direction")
    siblings = list(
        CaseSimulationTask.query.filter_by(case_simulation_id=task.case_simulation_id)
        .order_by(CaseSimulationTask.sort_order).all()
    )
    _swap_sort_order(siblings, task, direction)
    return redirect(url_for("admin.case_edit", lesson_id=task.case.lesson_id))


@admin_bp.route("/tasks/<int:task_id>/duplicate", methods=["POST"])
@admin_required
def task_duplicate(task_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    task = CaseSimulationTask.query.get_or_404(task_id)
    case = task.case

    new_task = CaseSimulationTask(
        case_simulation_id=case.id, task_type=task.task_type,
        prompt_en=f"{task.prompt_en} (Copy)", prompt_es=f"{task.prompt_es} (Copia)",
        explanation_en=task.explanation_en, explanation_es=task.explanation_es,
        points=task.points, requires_justification=task.requires_justification,
        sort_order=_next_sort_order(case.tasks), is_active=task.is_active,
        expected_response_en=task.expected_response_en, expected_response_es=task.expected_response_es,
        rubric_notes_en=task.rubric_notes_en, rubric_notes_es=task.rubric_notes_es,
    )
    for opt in task.options:
        new_task.options.append(CaseSimulationTaskOption(text_en=opt.text_en, text_es=opt.text_es, is_correct=opt.is_correct, sort_order=opt.sort_order))
    for ans in task.accepted_answers:
        new_task.accepted_answers.append(CaseSimulationTaskAcceptedAnswer(answer_en=ans.answer_en, answer_es=ans.answer_es))

    db.session.add(new_task)
    db.session.commit()
    flash("Task duplicated.", "success")
    return redirect(url_for("admin.case_edit", lesson_id=case.lesson_id))
