import json
import os
import re
import secrets
from datetime import datetime

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, send_file, url_for

from app.extensions import db
from app.i18n import get_text, valid_language
from app.models import (
    BlogPost,
    Certificate,
    Course,
    CustomForm,
    Enrollment,
    Inquiry,
    Lesson,
    LessonProgress,
    Page,
    PageSection,
    QuizAttempt,
    Submission,
)
from app.auth import is_admin_logged_in, validate_csrf
from app.certificates import build_cert_context
from app.forms_engine import (
    OG_SERVICES,
    compute_field_effects,
    compute_page_effects,
    field_input_kind as _field_input_kind,
    generate_submission_code,
    is_valid_email,
    is_valid_phone,
    queue_form_notifications,
    resolve_next_page,
)
from app.activity import log_event
from app.intake import owned_submission, purge_hidden_values, start_or_resume
from app.intake_engine import validate_value
from app.models import Form, FormField, FormSubmission, Service, ServiceCategory, SubmissionFile, SubmissionValue
from app.ratelimit import allow
from app.progress import course_progress, is_lesson_completed, unlocked_lesson_ids
from app.seo import noindex_if_service_intake, noindex_page
from app.student_auth import current_student
from app.uploads import course_media_full_path, delete_course_media, save_course_media, save_data_url_image
from app.video_embed import to_embed_url

public_bp = Blueprint("public", __name__, url_prefix="/<lang>")


@public_bp.url_value_preprocessor
def check_lang(endpoint, values):
    if not valid_language(values.get("lang")):
        abort(404)


from app.service_public import get_category, home_context, render_category, render_service, services_in_scope


@public_bp.route("/")
def home(lang):
    return render_template("public/home.html", **home_context(lang))


@public_bp.route("/services/other-services")
def services(lang):
    ctx = home_context(lang)
    return render_template("public/services.html", featured=ctx["featured"], more=ctx["more"])


@public_bp.route("/services/certified-translations")
def translations(lang):
    return render_category(lang, "certified-translations")


@public_bp.route("/services/certified-translations/<slug>")
def translation_subpage(lang, slug):
    return render_service(lang, "certified-translations", slug)


@public_bp.route("/services/taxes-itin")
def taxes_itin(lang):
    return render_category(lang, "taxes-itin")


@public_bp.route("/services/taxes-itin/<slug>")
def taxes_subpage(lang, slug):
    return render_service(lang, "taxes-itin", slug)


@public_bp.route("/services/nj-driver-license")
def nj_driver_license(lang):
    return render_category(lang, "nj-driver-license")


@public_bp.route("/services/nj-driver-license/<slug>")
def nj_driver_license_subpage(lang, slug):
    return render_service(lang, "nj-driver-license", slug)


@public_bp.route("/services/notary")
def notary(lang):
    return render_category(lang, "notary")


@public_bp.route("/services/notary/<slug>")
def notary_subpage(lang, slug):
    return render_service(lang, "notary", slug)


@public_bp.route("/services/immigration")
def immigration(lang):
    return render_category(lang, "immigration")


@public_bp.route("/services/immigration/<slug>")
def immigration_subpage(lang, slug):
    return render_service(lang, "immigration", slug)


@public_bp.route("/services/apostille")
def apostille(lang):
    return render_category(lang, "apostille")


@public_bp.route("/services/apostille/<slug>")
def apostille_subpage(lang, slug):
    return render_service(lang, "apostille", slug)


@public_bp.route("/services/wedding-officiant")
def wedding_officiant(lang):
    return render_category(lang, "wedding-officiant")


@public_bp.route("/services/document-office-services")
def document_office_services(lang):
    return render_category(lang, "document-office-services")


@public_bp.route("/services/document-office-services/<slug>")
def document_office_subpage(lang, slug):
    return render_service(lang, "document-office-services", slug)


@public_bp.route("/locations")
def locations_hub(lang):
    return render_template("public/locations_hub.html")


@public_bp.route("/locations/paterson-nj")
def location_paterson(lang):
    return render_template("public/location_paterson.html", services=services_in_scope(lang, "nj_in_person"))


@public_bp.route("/locations/spring-tx")
def location_spring(lang):
    return render_template("public/location_spring.html", services=services_in_scope(lang, "tx_in_person"))


@public_bp.route("/services/immigration/inquiry", methods=["POST"])
def immigration_inquiry(lang):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    error = None
    if not name:
        error = get_text(lang, "flash_name_required")
    elif not email or "@" not in email:
        error = get_text(lang, "flash_email_invalid")

    if error:
        flash(error, "error")
        return redirect(url_for("public.immigration", lang=lang) + "#inquiry")

    db.session.add(
        Inquiry(
            source="immigration",
            language=lang,
            name=name,
            email=email,
            phone=request.form.get("phone", "").strip(),
            target_language=request.form.get("service", "").strip(),
            message=request.form.get("message", "").strip(),
        )
    )
    db.session.commit()
    flash(get_text(lang, "flash_contact_sent"), "success")
    return redirect(url_for("public.immigration", lang=lang) + "#inquiry")


@public_bp.route("/resources")
def resources(lang):
    # A small, curated set of the categories a visitor looking for "resources/guides" is most
    # likely to actually need — real ServiceCategory records (title/url stay in sync with Admin
    # automatically), never a full duplicate of the Services hub.
    slugs = ["taxes-itin", "certified-translations", "immigration", "notary", "nj-driver-license"]
    cats = [c for slug in slugs for c in [ServiceCategory.query.filter_by(slug=slug, is_published=True).first()] if c]
    return render_template("public/resources.html", resource_categories=cats)


@public_bp.route("/courses")
def courses(lang):
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    courses_query = Course.query.filter_by(is_published=True)
    if category:
        courses_query = courses_query.filter(Course.category == category)
    if query:
        like = f"%{query}%"
        courses_query = courses_query.filter(
            db.or_(
                Course.title_en.ilike(like),
                Course.title_es.ilike(like),
                Course.subtitle_en.ilike(like),
                Course.subtitle_es.ilike(like),
            )
        )
    courses = courses_query.order_by(Course.sort_order, Course.id).all()

    categories = sorted(
        {
            c.category
            for c in Course.query.filter_by(is_published=True).all()
            if c.category
        }
    )

    return render_template(
        "public/courses.html", courses=courses, categories=categories, query=query, active_category=category
    )


@public_bp.route("/courses/<slug>")
def course_detail(lang, slug):
    course = Course.query.filter_by(slug=slug, is_published=True).first_or_404()

    student = current_student()
    is_enrolled = False
    enrollment = None
    progress = None
    completed_lesson_ids = set()
    unlocked_ids = set()
    continue_lesson = None
    certificate = None
    cert_context = None
    all_lessons = [l for section in course.sections for l in section.lessons]

    if student:
        enrollment = next((e for e in student.enrollments if e.course_id == course.id), None)
        is_enrolled = bool(enrollment)
        if is_enrolled:
            progress = course_progress(student, course)
            completed_lesson_ids = {
                row.lesson_id
                for row in LessonProgress.query.filter_by(student_id=student.id, is_completed=True).all()
            }
            unlocked_ids = unlocked_lesson_ids(student, course)
            continue_lesson = next((l for l in all_lessons if l.id not in completed_lesson_ids), None)
            if course.certificate_enabled:
                certificate = Certificate.query.filter_by(student_id=student.id, course_id=course.id).first()
                if certificate:
                    cert_context = build_cert_context(course, lang, student=student, certificate=certificate)

    visible_lessons = all_lessons if is_enrolled else [l for l in all_lessons if l.is_preview]
    course_resources = [
        (lesson, resource) for lesson in visible_lessons for resource in lesson.resources
    ]

    return render_template(
        "public/course_detail.html",
        course=course,
        is_enrolled=is_enrolled,
        enrollment=enrollment,
        progress=progress,
        completed_lesson_ids=completed_lesson_ids,
        unlocked_lesson_ids=unlocked_ids,
        continue_lesson=continue_lesson,
        course_resources=course_resources,
        certificate=certificate,
        cert=cert_context,
    )


def _load_lesson_with_access(lang, slug, lesson_id):
    """Returns (course, lesson, student, is_enrolled), or raises/redirects on denied access."""
    course = Course.query.filter_by(slug=slug, is_published=True).first_or_404()
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.section.course_id != course.id:
        abort(404)

    student = current_student()
    enrollment = (
        Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first() if student else None
    )
    is_enrolled = bool(enrollment)

    if not lesson.is_preview and not is_enrolled:
        if not student:
            return None, None, None, None, redirect(url_for("account.login", lang=lang, next=request.path))
        abort(403)

    if enrollment and not enrollment.is_active:
        flash(get_text(lang, "flash_access_expired"), "error")
        return None, None, None, None, redirect(url_for("public.course_detail", lang=lang, slug=course.slug))

    if enrollment and lesson.id not in unlocked_lesson_ids(student, course):
        flash(get_text(lang, "flash_lesson_locked"), "error")
        return None, None, None, None, redirect(url_for("public.course_detail", lang=lang, slug=course.slug))

    return course, lesson, student, is_enrolled, None


@public_bp.route("/courses/<slug>/lessons/<int:lesson_id>")
def lesson_view(lang, slug, lesson_id):
    course, lesson, student, is_enrolled, denied = _load_lesson_with_access(lang, slug, lesson_id)
    if denied:
        return denied

    all_lessons = [l for section in course.sections for l in section.lessons]
    index = all_lessons.index(lesson)
    prev_lesson = all_lessons[index - 1] if index > 0 else None
    next_lesson = all_lessons[index + 1] if index < len(all_lessons) - 1 else None

    completed = is_lesson_completed(student, lesson) if student else False

    latest_attempt = None
    can_attempt_quiz = True
    if lesson.lesson_type == "quiz" and student:
        latest_attempt = (
            QuizAttempt.query.filter_by(student_id=student.id, lesson_id=lesson.id)
            .order_by(QuizAttempt.submitted_at.desc())
            .first()
        )
        if latest_attempt and lesson.quiz_kind != "formative":
            attempts_used = QuizAttempt.query.filter_by(student_id=student.id, lesson_id=lesson.id).count()
            if not lesson.quiz_allow_retry:
                can_attempt_quiz = False
            elif lesson.quiz_max_attempts is not None and attempts_used >= lesson.quiz_max_attempts:
                can_attempt_quiz = False

    submission = None
    if lesson.lesson_type == "assignment" and student:
        submission = Submission.query.filter_by(student_id=student.id, lesson_id=lesson.id).first()

    completed_lesson_ids = set()
    unlocked_ids = set()
    if student:
        completed_lesson_ids = {
            row.lesson_id
            for row in LessonProgress.query.filter_by(student_id=student.id, is_completed=True).all()
        }
        if is_enrolled:
            unlocked_ids = unlocked_lesson_ids(student, course)

    slides_json = "[]"
    if lesson.lesson_type == "presentation":
        slides_json = json.dumps(
            [
                {
                    "image": url_for(
                        "public.lesson_asset", lang=lang, slug=course.slug, lesson_id=lesson.id, stored_path=s.image(lang)
                    )
                    if s.image(lang)
                    else None,
                    "audio": url_for(
                        "public.lesson_asset", lang=lang, slug=course.slug, lesson_id=lesson.id, stored_path=s.audio(lang)
                    )
                    if s.audio(lang)
                    else None,
                }
                for s in lesson.slides
            ]
        )

    return render_template(
        "public/lesson_player.html",
        course=course,
        lesson=lesson,
        is_enrolled=is_enrolled,
        completed=completed,
        prev_lesson=prev_lesson,
        next_lesson=next_lesson,
        latest_attempt=latest_attempt,
        can_attempt_quiz=can_attempt_quiz,
        video_embed_url=to_embed_url(lesson.video_external_url) if lesson.video_source == "external" else None,
        completed_lesson_ids=completed_lesson_ids,
        unlocked_lesson_ids=unlocked_ids,
        slides_json=slides_json,
        submission=submission,
    )


@public_bp.route("/courses/<slug>/lessons/<int:lesson_id>/asset/<path:stored_path>")
def lesson_asset(lang, slug, lesson_id, stored_path):
    course, lesson, student, is_enrolled, denied = _load_lesson_with_access(lang, slug, lesson_id)
    if denied:
        return denied

    valid_paths = (
        {lesson.video_filename}
        | {s.image_en for s in lesson.slides}
        | {s.audio_en for s in lesson.slides}
        | {s.image_es for s in lesson.slides}
        | {s.audio_es for s in lesson.slides}
        | {r.file_filename for r in lesson.resources}
    )
    if lesson.case_simulation:
        valid_paths |= {d.file_filename for d in lesson.case_simulation.documents}
    if student:
        own_submission = Submission.query.filter_by(student_id=student.id, lesson_id=lesson.id).first()
        if own_submission and own_submission.file_filename:
            valid_paths.add(own_submission.file_filename)

    if stored_path not in valid_paths:
        abort(404)

    full_path = course_media_full_path(stored_path)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path, conditional=True)


@public_bp.route("/certificates/verify/<code>")
def certificate_verify(lang, code):
    certificate = Certificate.query.filter_by(code=code).first()
    return render_template("public/certificate_verify.html", certificate=certificate, code=code)


@public_bp.route("/page/<slug>")
def page_view(lang, slug):
    page = Page.query.filter_by(slug=slug, is_published=True).first_or_404()
    breadcrumbs = []
    node = page.parent_page
    while node:
        breadcrumbs.insert(0, node)
        node = node.parent_page
    return render_template("public/page.html", page=page, breadcrumbs=breadcrumbs)


@public_bp.route("/page-asset/<int:section_id>/<path:stored_path>")
def page_section_asset(lang, section_id, stored_path):
    section = PageSection.query.get_or_404(section_id)
    if not section.page or not section.page.is_published or stored_path != section.image_filename:
        abort(404)
    full_path = course_media_full_path(stored_path)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path, conditional=True)


@public_bp.route("/forms/<slug>")
@noindex_page(follow=True)
def form_view(lang, slug):
    custom_form = CustomForm.query.filter_by(slug=slug, is_active=True).first_or_404()
    return render_template("public/custom_form.html", form=custom_form)


@public_bp.route("/forms/<slug>/submit", methods=["POST"])
def form_submit(lang, slug):
    custom_form = CustomForm.query.filter_by(slug=slug, is_active=True).first_or_404()
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)

    data = {}
    for field in custom_form.fields:
        value = request.form.get(field.input_name(), "").strip()
        if field.field_type == "checkbox":
            value = "Yes" if value else "No"
        if field.required and not value and field.field_type != "checkbox":
            flash(get_text(lang, "flash_form_required"), "error")
            return redirect(url_for("public.form_view", lang=lang, slug=slug))
        data[field.label(lang)] = value

    db.session.add(
        Inquiry(
            source="custom_form",
            language=lang,
            form_id=custom_form.id,
            extra_data=json.dumps(data),
        )
    )
    db.session.commit()
    flash(get_text(lang, "flash_form_sent"), "success")
    return redirect(url_for("public.form_view", lang=lang, slug=slug))


# ---------------------------------------------------------------- OG Forms Builder (new engine)

_MAGIC = {
    "pdf": (b"%PDF",),
    "jpg": (b"\xff\xd8",),
    "jpeg": (b"\xff\xd8",),
    "png": (b"\x89PNG",),
    "webp": (b"RIFF",),
    "gif": (b"GIF8",),
}


def _probe_upload(file_storage):
    """(size in bytes, first bytes) of an upload without consuming it."""
    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    head = stream.read(12)
    stream.seek(0)
    return size, head


def _matches_extension(ext, head):
    """A cheap content check so a renamed executable/script can't pass as a PDF or
    image. Office/text types have no reliable single signature and are left to the
    extension allow-list."""
    signatures = _MAGIC.get(ext)
    return True if not signatures else any(head.startswith(sig) for sig in signatures)


def _extract_field_value(field, lang, lenient=False):
    """Reads one field's submitted value(s) out of the current request.
    Returns (value_for_storage, display_value, error_message_or_None,
    [(FileStorage, ...)] for file fields)."""
    kind = _field_input_kind(field.field_type)
    name = field.input_name()
    error = None

    if kind == "file":
        uploaded = request.files.getlist(name + "[]") or request.files.getlist(name)
        uploaded = [f for f in uploaded if f and f.filename]
        if field.required and not uploaded:
            error = field.validation_message(lang) or get_text(lang, "flash_form_required")
            return None, "", error, []
        if field.max_files and len(uploaded) > field.max_files:
            error = f"Please upload no more than {field.max_files} file(s)." if lang == "en" else f"Sube un máximo de {field.max_files} archivo(s)."
            return None, "", error, []
        for f in uploaded:
            ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
            if field.allowed_extensions and ext not in field.allowed_extensions:
                error = f"Unsupported file type: .{ext}" if lang == "en" else f"Tipo de archivo no admitido: .{ext}"
                return None, "", error, []
            size, head = _probe_upload(f)
            limit_mb = field.max_file_size_mb or 25
            if size > limit_mb * 1024 * 1024:
                error = f"Each file must be {limit_mb} MB or smaller." if lang == "en" else f"Cada archivo debe pesar {limit_mb} MB o menos."
                return None, "", error, []
            if not _matches_extension(ext, head):
                error = f"“{f.filename}” doesn't look like a real .{ext} file." if lang == "en" else f"“{f.filename}” no parece un archivo .{ext} válido."
                return None, "", error, []
        return None, ", ".join(f.filename for f in uploaded), None, uploaded

    if kind == "signature":
        data_url = request.form.get(name, "").strip()
        if field.required and not data_url:
            error = field.validation_message(lang) or get_text(lang, "flash_form_required")
            return None, "", error, []
        return (data_url or None), ("signed" if data_url else ""), None, []

    if kind in ("checkbox_group", "multiselect") or field.field_type == "service_multi":
        values = request.form.getlist(name)
        if field.required and not values:
            error = field.validation_message(lang) or get_text(lang, "flash_form_required")
            return None, "", error, []
        display = ", ".join(values)
        return (json.dumps(values) if values else None), display, None, []

    if field.field_type == "appointment":
        date_val = request.form.get(name + "_date", "").strip()
        time_val = request.form.get(name + "_time", "").strip()
        if field.required and not (date_val and time_val):
            error = field.validation_message(lang) or get_text(lang, "flash_form_required")
            return None, "", error, []
        combined = f"{date_val} {time_val}".strip()
        return (combined or None), combined, None, []

    if kind == "records":
        from app.intake_records import display_records, field_config, parse_records, records_error, sanitize_records

        records = sanitize_records(parse_records(request.form.get(name, "")), field_config(field))
        if any(r.get("person_id") for r in records):  # a record that points at one of the customer's OWN people reads as that person (verified; a foreign id is dropped)
            from app.i864_views import fill_from_people

            fill_from_people(records, current_student().id if current_student() else None, field_config(field).get("fill_extra"))
        if not lenient:
            error = records_error(field, records, lang)
            if error:
                return (json.dumps(records, ensure_ascii=False) if records else None), "", error, []
        return (json.dumps(records, ensure_ascii=False) if records else None), display_records(field, records, lang), None, []

    if kind == "consent":
        checked = request.form.get(name) == "accepted"
        if field.required and not checked:
            error = field.validation_message(lang) or get_text(lang, "flash_form_required")
            return None, "", error, []
        return ("accepted" if checked else "declined"), ("Yes" if checked else "No"), None, []

    # everything else: a single text-ish value
    value = request.form.get(name, "").strip()

    if not value:
        if field.required:
            error = field.validation_message(lang) or get_text(lang, "flash_form_required")
        return (None if not value else value), value, error, []

    error = validate_value(field, value, lang)

    return value, value, error, []


def _prior_values_json(submission, page, override_form=None):
    """Maps input_name -> previously-saved value (JSON string for multi-value
    fields) for every field, so the browser can re-populate inputs when the
    visitor navigates back to a page, switches language, or a page they just
    submitted comes back with a validation error. `override_form` (the
    just-POSTed, possibly-invalid request.form) takes priority for the
    current page so a validation error never erases what was just typed."""
    values = {}
    named = None
    for field in page.fields:  # starting values; a saved answer (even an emptied one) replaces them
        default = field.default
        if default and not field.is_content_only:
            values[field.input_name()] = json.dumps([default]) if field.is_multi_value else default
        if field.field_type == "record_list" and submission is not None and field.config_json and "default_from" in field.config_json:
            from app.intake_completeness import named_answers
            from app.intake_records import default_records

            named = named if named is not None else named_answers(submission.form, submission)
            starting = default_records(field, named)
            if starting:
                values[field.input_name()] = json.dumps(starting)
    if submission is not None and submission.case_id:
        from app.shared_blocks import prefill_values

        values.update(prefill_values(submission, page))  # what the case already knows; a saved answer still wins below
    if submission:
        for v in submission.values:
            values[f"field_{v.field_id}"] = v.value_text or ""
    if override_form is not None:
        for field in page.fields:
            name = field.input_name()
            if field.is_multi_value:
                selected = override_form.getlist(name)
                if selected:
                    values[name] = json.dumps(selected)
            else:
                raw = override_form.get(name)
                if raw is not None:
                    values[name] = raw
    return json.dumps(values)


def _answers_for_submission(submission):
    answers = {}
    for v in submission.values:
        raw = v.value_text
        try:
            parsed = json.loads(raw)
            answers[v.field_id] = parsed if isinstance(parsed, list) else raw
        except (TypeError, ValueError):
            answers[v.field_id] = raw
    return answers


def _upsert_submission_value(submission, field, lang, value_for_storage, display_value):
    existing = SubmissionValue.query.filter_by(submission_id=submission.id, field_id=field.id).first()
    if existing:
        existing.value_text = value_for_storage
    else:
        db.session.add(SubmissionValue(
            submission_id=submission.id, field_id=field.id,
            field_label_snapshot=field.label(lang) or field.internal_name,
            field_internal_name=field.internal_name, field_type_snapshot=field.field_type,
            value_text=value_for_storage,
        ))

    if field.internal_name in ("email",) or field.field_type == "email":
        submission.display_email = display_value or submission.display_email
    if field.field_type == "phone":
        submission.display_phone = display_value or submission.display_phone
    if field.field_type in ("full_name", "first_name"):
        submission.display_name = display_value or submission.display_name


def _page_rules_json(form, page):
    """Rules that target a field on this page, for live show/hide in the browser.
    The server stays authoritative (it recomputes on every save); this only makes
    the page respond instantly to the customer's own answers."""
    field_ids = {f.id for f in page.fields}
    rules = []
    for rule in form.rules:
        if rule.action not in ("show_field", "hide_field", "require_field", "optional_field"):
            continue
        if rule.target_field_id not in field_ids:
            continue
        rules.append({
            "action": rule.action, "target": rule.target_field_id, "match": rule.match_type,
            "conditions": [{"field": c.field_id, "op": c.operator, "value": c.value} for c in rule.conditions],
        })
    return json.dumps(rules)


def _other_answers_json(submission, page):
    """Saved answers to fields NOT on this page (those a rule on this page may
    depend on); fields on this page are read live from the inputs."""
    on_page = {f.id for f in page.fields}
    answers = {str(fid): v for fid, v in (_answers_for_submission(submission).items() if submission else []) if fid not in on_page}
    return json.dumps(answers)


def _existing_files_json(form, page, submission, lang):
    """Files already stored for this page's upload fields, so the browser can show
    them (name, size, view, remove) instead of an empty picker."""
    if not submission:
        return "{}"
    on_page = {f.id: f for f in page.fields}
    out = {}
    for f in submission.files:
        field = on_page.get(f.field_id)
        if not field or field.field_type == "signature":
            continue
        out.setdefault(field.input_name(), []).append({
            "id": f.id, "name": f.original_filename, "size": f.size_bytes or 0, "mime": f.mime_type or "",
            "view": url_for("account.document_file", lang=lang, file_id=f.id, inline=1),
            "remove": url_for("public.og_form_file_remove", lang=lang, slug=form.slug, file_id=f.id),
        })
    return json.dumps(out)


def _prev_page_number(form, submission, page):
    """Previous step ON THE ACTIVE PATH (skipped steps are not revisited)."""
    from app.intake_engine import answers_for, path_pages

    path = path_pages(form, answers_for(submission))
    if page in path:
        i = path.index(page)
        return form.pages.index(path[i - 1]) + 1 if i > 0 else None
    lower = [p for p in path if form.pages.index(p) < form.pages.index(page)]
    return form.pages.index(lower[-1]) + 1 if lower else None


def _render_form(form, page, page_number, pages, submission, field_effects, errors, prior_values_json, from_review=False):
    if form.is_service_intake and submission is not None and submission.student_id and form.source_form_name in ("I-864", "I-751", "DS-260"):
        from flask import g

        from app.i864_views import person_options

        g.person_options = person_options(submission.student)  # only THIS customer's own people
    from app.intake_engine import context_map
    from app.intake_shared import dynamic_blocks, set_name_tokens

    rlang = (request.view_args or {}).get("lang", "en")
    if form.is_service_intake:
        set_name_tokens(form, submission)
    context = dict(
        contexts=context_map(form, submission, rlang) if form.is_service_intake else {},
        dynamic_blocks=dynamic_blocks(form, page, submission, rlang) if form.is_service_intake else {},
        return_to=(request.args.get("return") or request.form.get("return_to") or ""),
        form=form, page=page, page_number=page_number, total_pages=len(pages),
        submission=submission, field_effects=field_effects, og_services=OG_SERVICES, errors=errors,
        prior_values_json=prior_values_json, page_rules_json=_page_rules_json(form, page),
        other_answers_json=_other_answers_json(submission, page),
        autosave_enabled=bool(form.is_service_intake and submission),
    )
    if not form.is_service_intake:
        return render_template("public/og_form.html", **context)

    from app.intake_engine import progress_for

    context.update(
        progress=progress_for(form, submission, page),
        prev_page_number=_prev_page_number(form, submission, page),
        existing_files_json=_existing_files_json(form, page, submission, request.view_args.get("lang", "en")),
        from_review=from_review,
        service=submission.service if submission else None,
    )
    return render_template("public/intake_step.html", **context)


def _merged_answers(prior_answers, page, lang):
    """Prior answers plus what is being submitted on this page right now, so a
    rule may depend on another question on the same page."""
    merged = dict(prior_answers)
    for field in page.fields:
        if field.is_content_only:
            continue
        kind = _field_input_kind(field.field_type)
        if kind in ("file", "signature"):
            continue
        original_required = field.required
        field.required = False
        try:
            value, display, error, files = _extract_field_value(field, lang, lenient=True)
        finally:
            field.required = original_required
        if error:
            continue
        if field.is_multi_value or kind == "records":
            merged[field.id] = json.loads(value) if value else []
        else:
            merged[field.id] = value or ""
    return merged


def _form_login_redirect(lang, slug, page=None):
    """Send an anonymous visitor to sign in and bring them straight back. The
    return address never carries the resume token."""
    target = url_for("public.og_form_view", lang=lang, slug=slug, page=page)
    return redirect(url_for("account.login", lang=lang, next=target))


def _intake_submission(form, lang, token):
    """Resolve the submission a request is acting on.

    Returns (submission, response). `response` is a redirect/abort-worthy result
    the caller must return immediately (sign-in needed, or a fresh draft whose
    token should be in the URL). For service-intake forms the draft is looked up
    by the SIGNED-IN customer; a token belonging to anyone else is a 404.
    """
    student = current_student()
    if form.is_service_intake:
        if not student:
            return None, _form_login_redirect(lang, form.slug, request.args.get("page", type=int))
        if token:
            submission = owned_submission(form, student, token)
            if not submission:
                abort(404)
            from app.case_setup import needs_setup

            if needs_setup(submission) and not submission.is_complete:
                return None, redirect(url_for("public.og_form_setup", lang=lang, slug=form.slug, t=submission.resume_token))
            return submission, None
        if not allow(f"intake-start:{student.id}", 30, 60):
            abort(429)
        submission = start_or_resume(form, student, lang)
        from app.case_setup import needs_setup

        if needs_setup(submission):
            return submission, redirect(url_for("public.og_form_setup", lang=lang, slug=form.slug, t=submission.resume_token))
        return submission, redirect(
            url_for("public.og_form_view", lang=lang, slug=form.slug, page=submission.current_page, t=submission.resume_token)
        )
    submission = FormSubmission.query.filter_by(resume_token=token, form_id=form.id).first() if token else None
    return submission, None


@public_bp.route("/f/<slug>")
@noindex_if_service_intake
def og_form_view(lang, slug):
    form = Form.query.filter_by(slug=slug, status="published").first_or_404()
    if not form.pages:
        abort(404)

    submission, response = _intake_submission(form, lang, request.args.get("t", ""))
    if response is not None:
        return response
    if submission and submission.is_complete:
        return _completed_response(form, submission)

    pages = form.pages
    page_number = request.args.get("page", 1, type=int) or 1
    page_number = max(1, min(page_number, len(pages)))
    page = pages[page_number - 1]

    if form.is_service_intake and submission is not None and submission.case_id:
        from app.shared_blocks import prime_blocks

        prime_blocks(submission)
    answers = _answers_for_submission(submission) if submission else {}
    if form.is_service_intake and submission is not None:
        from app.intake_engine import path_pages

        path = path_pages(form, answers)
        if path and page not in path:  # a page the current answers skip: go to the next one that applies
            later = next((p for p in path if p.sort_order > page.sort_order), path[-1])
            return redirect(url_for("public.og_form_view", lang=lang, slug=slug, page=pages.index(later) + 1, t=submission.resume_token,
                                    review=request.args.get("review") if request.args.get("review") == "1" else None))
    if form.is_service_intake and submission is not None and submission.case_id:
        conflict_block = _block_with_conflicts(form, submission, page)
        if conflict_block:  # a stable fact is stated differently by different sources: resolve it before anything is confirmed
            return redirect(url_for("public.og_form_conflicts", lang=lang, slug=slug, t=submission.resume_token, block=conflict_block,
                                    review=request.args.get("review") if request.args.get("review") == "1" else None))
    field_effects = compute_field_effects(form, answers)
    prior_values_json = _prior_values_json(submission, page)

    return _render_form(form, page, page_number, pages, submission, field_effects, {}, prior_values_json, request.args.get("review") == "1")


@public_bp.route("/f/<slug>/media/<path:stored_path>")
def og_form_asset(lang, slug, stored_path):
    """Serves an OG Form's layout-image and image-choice option thumbnails to
    anonymous visitors. Only files actually attached to a field/option of this
    published form are served — submission uploads live in the same storage
    dir but stay behind the admin-only `admin.media` route."""
    form = Form.query.filter_by(slug=slug, status="published").first_or_404()
    valid_paths = set()
    for field in form.all_fields:
        if field.image_filename:
            valid_paths.add(field.image_filename)
        valid_paths.update(o.image_filename for o in field.options if o.image_filename)
    if stored_path not in valid_paths:
        abort(404)
    full_path = course_media_full_path(stored_path)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path, conditional=True)


def _guess_mime(filename, head):
    import mimetypes

    guessed = mimetypes.guess_type(filename)[0]
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG"):
        return "image/png"
    return guessed or "application/octet-stream"


def _service_title(submission):
    if submission.service:
        return submission.service.title_en
    return submission.form.name_admin


def _persist_field(submission, field, lang, value, display, files):
    """Write one already-validated field answer (and any uploaded files)."""
    if files:
        existing = SubmissionFile.query.filter_by(submission_id=submission.id, field_id=field.id).all()
        limit = field.max_files or 1
        if limit == 1:  # a single-file field: the new upload replaces the old one
            for ef in existing:
                delete_course_media(ef.stored_filename)
                db.session.delete(ef)
                log_event(submission.student_id, "document_removed", entity=("submission", submission.id),
                          meta={"filename": ef.original_filename, "service": _service_title(submission)}, commit=False) if submission.student_id else None
            existing = []
        room = max(limit - len(existing), 0)
        for f in files[:room]:
            _, head = _probe_upload(f)
            try:
                stored = save_course_media(f, "document")
            except ValueError:
                continue
            full_path = course_media_full_path(stored)
            size = os.path.getsize(full_path) if os.path.isfile(full_path) else 0
            safe_name = re.sub(r"[\x00-\x1f\\/]+", "_", os.path.basename(f.filename or "document"))[:200]
            db.session.add(SubmissionFile(
                submission_id=submission.id, field_id=field.id, original_filename=safe_name, stored_filename=stored,
                size_bytes=size, mime_type=_guess_mime(safe_name, head), uploaded_at=datetime.utcnow(),
            ))
            existing.append(type("F", (), {"original_filename": safe_name}))
            if submission.student_id:
                log_event(submission.student_id, "document_uploaded", entity=("submission", submission.id),
                          meta={"filename": safe_name, "service": _service_title(submission)}, commit=False)
        names = ", ".join(e.original_filename for e in existing)
        _upsert_submission_value(submission, field, lang, names or None, names)
    elif field.field_type == "signature" and value:
        stored = save_data_url_image(value)
        if stored:
            existing_file = SubmissionFile.query.filter_by(submission_id=submission.id, field_id=field.id).first()
            if existing_file:
                delete_course_media(existing_file.stored_filename)
                db.session.delete(existing_file)
            db.session.add(SubmissionFile(
                submission_id=submission.id, field_id=field.id, original_filename="signature.png",
                stored_filename=stored, size_bytes=0, mime_type="image/png", uploaded_at=datetime.utcnow(),
            ))
        _upsert_submission_value(submission, field, lang, "signed", "signed")
    else:
        _upsert_submission_value(submission, field, lang, value, display)


def _save_page_lenient(form, page, submission, lang, include_files):
    """Store whatever the customer has answered so far on this page, without
    requiring anything. Fields that currently hold an invalid value (an email
    half typed) are skipped rather than saved. Used by autosave and Save & Exit."""
    effects = compute_field_effects(form, _merged_answers(_answers_for_submission(submission), page, lang))
    for field in page.fields:
        if field.is_content_only or not effects.get(field.id, {}).get("visible", True):
            continue
        kind = _field_input_kind(field.field_type)
        if kind == "signature" or (kind == "file" and not include_files):
            continue
        original_required = field.required
        field.required = False
        try:
            value, display, error, files = _extract_field_value(field, lang, lenient=True)
        finally:
            field.required = original_required
        if error:
            continue
        if kind == "file" and not files:
            continue
        value = value if value is None else value[:20000]
        _persist_field(submission, field, lang, value, display, files)
    submission.updated_at = datetime.utcnow()


@public_bp.route("/f/<slug>/submit", methods=["POST"])
def og_form_submit(lang, slug):
    form = Form.query.filter_by(slug=slug, status="published").first_or_404()
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)

    pages = form.pages
    page_number = request.form.get("page_number", 1, type=int) or 1
    page_number = max(1, min(page_number, len(pages)))
    page = pages[page_number - 1]

    resume_token = request.form.get("resume_token", "").strip()
    submission, response = _intake_submission(form, lang, resume_token)
    if response is not None:
        return response
    if submission and submission.is_complete:
        return _completed_response(form, submission)
    resume_token = submission.resume_token if submission else resume_token
    from_review = request.form.get("from_review") == "1"
    if form.is_service_intake and submission is not None:
        from app.intake_shared import set_name_tokens

        set_name_tokens(form, submission)

    nav = request.form.get("nav")
    if nav == "back" and page_number > 1:
        if form.is_service_intake and submission is not None:
            target = _prev_page_number(form, submission, page) or max(page_number - 1, 1)
        else:
            target = page_number - 1
        return redirect(url_for("public.og_form_view", lang=lang, slug=slug, page=target, t=resume_token or None))

    if nav == "exit" and submission is not None and form.is_service_intake:
        _save_page_lenient(form, page, submission, lang, include_files=True)
        submission.current_page = page_number
        db.session.commit()
        flash(get_text(lang, "intake_saved_exit"), "success")
        return redirect(url_for("account.applications", lang=lang))

    if form.is_service_intake and submission is not None and submission.case_id and nav != "back":
        conflict_block = _block_with_conflicts(form, submission, page)
        if conflict_block:
            return redirect(url_for("public.og_form_conflicts", lang=lang, slug=slug, t=submission.resume_token, block=conflict_block))

    is_new_submission = submission is None
    if is_new_submission:
        submission = FormSubmission(
            form_id=form.id, code=generate_submission_code(), resume_token=secrets.token_urlsafe(32), language=lang,
            form_version=form.version, source_edition_snapshot=form.source_edition,
        )

    prior_answers = _answers_for_submission(submission) if not is_new_submission else {}
    field_effects = compute_field_effects(form, _merged_answers(prior_answers, page, lang))
    existing_file_fields = {f.field_id for f in submission.files} if not is_new_submission else set()

    # Phase 1 — validate every visible field on this page. No DB writes yet,
    # so a validation error never leaves a half-saved page behind.
    errors = {}
    to_persist = []  # (field, value_for_storage, display_value, files)
    for field in page.fields:
        if field.is_content_only:
            continue
        visible = field_effects.get(field.id, {}).get("visible", True)
        if not visible:
            continue
        required_override = field_effects.get(field.id, {}).get("required")
        original_required = field.required
        if required_override is not None:
            field.required = required_override
        if field.field_type == "file_upload" and field.id in existing_file_fields:
            field.required = False  # already satisfied by a previous upload
        try:
            value, display, error, files = _extract_field_value(field, lang)
        finally:
            field.required = original_required

        if not error and files and (field.max_files or 1) > 1:
            already = SubmissionFile.query.filter_by(submission_id=submission.id, field_id=field.id).count() if submission.id else 0
            if already + len(files) > field.max_files:
                error = (f"You can upload up to {field.max_files} files here." if lang == "en"
                         else f"Puedes subir hasta {field.max_files} archivos aquí.")
        if error:
            errors[field.id] = error
            continue
        to_persist.append((field, value, display, files))

    if errors:
        prior_values_json = _prior_values_json(submission, page, override_form=request.form)
        return _render_form(form, page, page_number, pages, submission if not is_new_submission else None, field_effects, errors, prior_values_json, from_review)

    # Phase 2 — every field on this page is valid; now persist for real.
    if is_new_submission:
        db.session.add(submission)
        db.session.flush()

    for field, value, display, files in to_persist:
        _persist_field(submission, field, lang, value, display, files)

    db.session.commit()

    if form.is_service_intake:
        from app.intake_shared import sync_after_save

        sync_after_save(form, submission, page)  # keep facts that live in two places identical
        try:
            from app.cases import sync_claims, sync_people

            if submission.case_id:
                sync_people(submission)  # people + roles of this application inside its case
                sync_claims(submission)  # explicit stable facts become reusable (with this application's state) before it is submitted
        except Exception:  # noqa: BLE001
            db.session.rollback()
    all_answers = _answers_for_submission(submission)
    purge_hidden_values(form, submission, all_answers)
    next_page = resolve_next_page(form, page, all_answers)

    if form.is_service_intake:
        if next_page is not None:
            submission.current_page = form.pages.index(next_page) + 1
        else:
            submission.current_page = len(pages)
        submission.updated_at = datetime.utcnow()
        db.session.commit()
        if from_review and request.form.get("return_to") == "check" and form.features.get("completeness_check"):
            return redirect(url_for("public.og_form_check", lang=lang, slug=slug, t=submission.resume_token))
        if from_review and next_page is not None:
            from app.shared_blocks import edit_followup

            if edit_followup(form, page, next_page, all_answers):  # "I need to change something" on a shared block: go on to its edit step
                return redirect(url_for("public.og_form_view", lang=lang, slug=slug, page=submission.current_page, t=submission.resume_token, review=1))
        if from_review or next_page is None:
            if next_page is None and not from_review and form.features.get("completeness_check"):
                return redirect(url_for("public.og_form_check", lang=lang, slug=slug, t=submission.resume_token))
            return redirect(url_for("public.og_form_review", lang=lang, slug=slug, t=submission.resume_token))
        return redirect(url_for("public.og_form_view", lang=lang, slug=slug, page=submission.current_page, t=submission.resume_token))

    if next_page is None:
        submission.is_complete = True
        submission.status = "new"
        submission.submitted_at = datetime.utcnow()
        submission.updated_at = datetime.utcnow()
        db.session.commit()
        queue_form_notifications(form, submission)
        if form.success_action == "redirect" and form.redirect_url:
            return redirect(form.redirect_url)
        return render_template("public/og_form_success.html", form=form, submission=submission)

    next_index = pages.index(next_page) + 1
    submission.current_page = next_index
    submission.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("public.og_form_view", lang=lang, slug=slug, page=next_index, t=submission.resume_token))


def _completed_response(form, submission):
    if form.is_service_intake:
        return render_template("public/intake_done.html", form=form, submission=submission, service=submission.service)
    return render_template("public/og_form_success.html", form=form, submission=submission)


@public_bp.route("/f/<slug>/autosave", methods=["POST"])
def og_form_autosave(lang, slug):
    """Debounced background save while a signed-in customer fills a service
    intake. Lenient by design (nothing is required yet) but scoped to the
    customer's own open draft."""
    form = Form.query.filter_by(slug=slug, status="published").first_or_404()
    if not form.is_service_intake:
        abort(404)
    student = current_student()
    if not student:
        return jsonify({"error": "auth"}), 401
    if not validate_csrf(request.headers.get("X-CSRFToken") or request.form.get("csrf_token")):
        return jsonify({"error": "csrf"}), 400
    if not allow(f"autosave:{student.id}", 240, 60):
        return jsonify({"error": "rate"}), 429

    submission = owned_submission(form, student, request.form.get("resume_token", "").strip())
    if not submission or submission.is_complete:
        return jsonify({"error": "not_found"}), 404
    from app.case_setup import needs_setup

    if needs_setup(submission):
        return jsonify({"error": "setup"}), 409

    pages = form.pages
    page_number = request.form.get("page_number", 1, type=int) or 1
    page_number = max(1, min(page_number, len(pages)))
    _save_page_lenient(form, pages[page_number - 1], submission, lang, include_files=False)
    submission.current_page = page_number
    db.session.commit()
    from app.cases import sync_claims

    sync_claims(submission)
    return jsonify({"saved": True, "at": submission.updated_at.isoformat() + "Z"})


def _block_with_conflicts(form, submission, page):
    """The shared-data block whose review step is `page`, when a stable fact of it is in conflict (else None)."""
    from app.shared_blocks import blocks_for, pending_conflicts

    blocks = blocks_for(form)
    for f in page.fields:
        if f.internal_name in blocks:
            from app.shared_blocks import prime_blocks

            prime_blocks(submission)
            stored = {v.field_internal_name: v.value_text for v in submission.values}
            if stored.get(f"{f.internal_name}_avail") == "yes" and pending_conflicts(submission, f.internal_name):
                return f.internal_name
    return None


@public_bp.route("/f/<slug>/conflicts", methods=["GET", "POST"])
@noindex_if_service_intake
def og_form_conflicts(lang, slug):
    """WE FOUND DIFFERENT INFORMATION: the customer chooses which value is correct (or types another). Nothing is pre-selected and
    no application answer is rewritten; both sources keep their provenance."""
    from datetime import date as _date

    from app import cases as case_svc
    from app import persons as pers
    from app.activity import log_event
    from app.case_types import FACTS
    from app.intake_shared import set_name_tokens
    from app.shared_blocks import block_offers, blocks_for

    form = Form.query.filter_by(slug=slug, status="published").first_or_404()
    if not form.is_service_intake:
        abort(404)
    student = current_student()
    if not student:
        return _form_login_redirect(lang, form.slug)
    submission = owned_submission(form, student, request.values.get("t", "").strip())
    if not submission or submission.case_id is None:
        abort(404)
    block_key = request.values.get("block", "")
    block = blocks_for(form).get(block_key)
    if not block:
        abort(404)
    if submission.is_complete:
        return redirect(url_for("public.og_form_view", lang=lang, slug=slug, t=submission.resume_token))
    set_name_tokens(form, submission)
    review_page = next((i for i, p in enumerate(form.pages, 1) if any(f.internal_name == block_key for f in p.fields)), 1)
    back = url_for("public.og_form_view", lang=lang, slug=slug, page=review_page, t=submission.resume_token, review=request.values.get("review") if request.values.get("review") == "1" else None)
    person, offers = block_offers(submission, block)
    conflicts = [(k, o) for k, o in offers.items() if o["status"] == "conflict"]
    if person is None or not conflicts:
        return redirect(back)
    errors = {}
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        if not allow(f"intake-conflict:{student.id}", 60, 60):
            abort(429)
        plan = []
        for fact_key, off in conflicts:
            choice = request.form.get(f"c_{fact_key}", "")
            if choice.startswith("opt:") and choice[4:].isdigit() and int(choice[4:]) < len(off["options"]):
                plan.append((fact_key, int(choice[4:]), None))
            elif choice == "custom":
                raw = (request.form.get(f"v_{fact_key}") or "").strip()[:120]
                kind = FACTS[fact_key].get("kind")
                if not raw:
                    errors[fact_key] = "Enter the correct value." if lang == "en" else "Escribe el valor correcto."
                elif kind == "date":
                    try:
                        d = _date.fromisoformat(raw)
                        if d > _date.today():
                            raise ValueError
                        plan.append((fact_key, None, d.isoformat()))
                    except ValueError:
                        errors[fact_key] = "Enter a valid date in the past." if lang == "en" else "Escribe una fecha válida en el pasado."
                elif kind == "choice" and raw not in FACTS[fact_key].get("options", {}):
                    errors[fact_key] = "Choose one of the options." if lang == "en" else "Elige una de las opciones."
                else:
                    plan.append((fact_key, None, raw))
            else:
                errors[fact_key] = "Choose one option." if lang == "en" else "Elige una opción."
        if not errors:
            for fact_key, idx, custom in plan:
                pers.resolve_conflict(person, fact_key, submission, option_index=idx, custom_value=custom, actor="customer")
                log_event(student.id, "person_conflict_resolved", entity=("submission", submission.id), meta={"fact": FACTS[fact_key]["en"], "application": submission.code})
            return redirect(back)
    rows = []
    for fact_key, off in conflicts:
        rows.append({"key": fact_key, "label": FACTS[fact_key]["en" if lang == "en" else "es"], "kind": FACTS[fact_key].get("kind"),
                     "options": [{"display": case_svc.display_fact_value(fact_key, o["value"], lang, reveal=False),
                                  "sources": [{"form": s["form"], "code": s["code"], "state": s["state"], "at": s["at"]} for s in o["sources"]]} for o in off["options"]],
                     "choice": request.form.get(f"c_{fact_key}", ""), "custom": request.form.get(f"v_{fact_key}", ""), "error": errors.get(fact_key),
                     "choices": FACTS[fact_key].get("options", {})})
    return render_template("public/intake_conflicts.html", form=form, submission=submission, service=submission.service, rows=rows, back=back,
                           block_key=block_key, person_name=person.given_name or "", today=_date.today().isoformat())


@public_bp.route("/f/<slug>/setup", methods=["GET", "POST"])
@noindex_if_service_intake
def og_form_setup(lang, slug):
    """Who is this application for, and in which case? (forms whose applicant is chosen, like Form I-485)"""
    from datetime import date

    from app import case_setup

    form = Form.query.filter_by(slug=slug, status="published").first_or_404()
    if not form.is_service_intake:
        abort(404)
    student = current_student()
    if not student:
        return _form_login_redirect(lang, form.slug)
    submission = owned_submission(form, student, request.values.get("t", "").strip())
    if not submission:
        abort(404)
    if not case_setup.needs_setup(submission) or submission.is_complete:
        return redirect(url_for("public.og_form_view", lang=lang, slug=slug, t=submission.resume_token, page=submission.current_page))
    error, selected, new_given, new_family = None, "", "", ""
    kind = case_setup.setup_kind(submission)
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        if not allow(f"intake-setup:{student.id}", 30, 60):
            abort(429)
        if kind == "itin_case":
            from app import itin

            ok, key = itin.apply_setup(student, submission, request.form, lang)
            if not ok:
                error = itin.ERRORS[key][0 if lang == "en" else 1]
                return render_template("public/intake_setup_itin.html", form=form, submission=submission, service=submission.service, student=student,
                                       opts=itin.setup_options(student, lang), error=error, f=request.form, today=date.today().isoformat())
            return redirect(url_for("public.og_form_view", lang=lang, slug=slug, page=1, t=submission.resume_token))
        if kind == "visa_applicant":
            from app import consular

            ok, key = consular.apply(student, submission, request.form, lang)
            if not ok:
                error = consular.ERRORS[key][0 if lang == "en" else 1]
                return render_template("public/intake_setup_ds260.html", form=form, submission=submission, service=submission.service, student=student,
                                       opts=consular.options(student, submission, lang), error=error, f=request.form)
        elif kind in ("sponsor_principal", "resident_spouse"):
            ok, key = case_setup.apply_i864(student, submission, request.form, lang)
        else:
            selected, new_given, new_family = request.form.get("choice", ""), request.form.get("new_given", ""), request.form.get("new_family", "")
            ok, key = case_setup.apply(student, submission, selected, new_given, new_family, lang)
        if ok:
            return redirect(url_for("public.og_form_view", lang=lang, slug=slug, page=1, t=submission.resume_token))
        error = case_setup.ERRORS[key][0 if lang == "en" else 1]
    if kind == "itin_case":
        from app import itin

        return render_template("public/intake_setup_itin.html", form=form, submission=submission, service=submission.service, student=student,
                               opts=itin.setup_options(student, lang), error=error, f={}, today=date.today().isoformat())
    if kind == "visa_applicant":
        from app import consular

        return render_template("public/intake_setup_ds260.html", form=form, submission=submission, service=submission.service, student=student,
                               opts=consular.options(student, submission, lang), error=error, f=request.form if request.method == "POST" else {})
    if kind in ("sponsor_principal", "resident_spouse"):
        return render_template("public/intake_setup_i864.html", form=form, submission=submission, service=submission.service, student=student,
                               opts=case_setup.options_i864(student, submission, lang), error=error, f=request.form if request.method == "POST" else {})
    return render_template("public/intake_setup.html", form=form, submission=submission, service=submission.service, student=student,
                           groups=case_setup.options(student, submission, lang), new_choices=case_setup.new_case_choices(student, submission, lang),
                           error=error, selected=selected, new_given=new_given, new_family=new_family)


@public_bp.route("/services/<category_slug>/<service_slug>/start")
def service_start(lang, category_slug, service_slug):
    """Get Started for a service that has a smart intake: sign in if needed (and
    come straight back here), then start the customer's application or resume
    the one they already have."""
    cat = get_category(category_slug)
    svc = Service.query.filter_by(category_id=cat.id, slug=service_slug).first_or_404()
    if not svc.is_published or not svc.has_intake:
        abort(404)
    form = svc.form
    student = current_student()
    needs_account = svc.requires_account or form.is_service_intake
    if needs_account and not student:
        return redirect(url_for("account.login", lang=lang, next=url_for("public.service_start", lang=lang, category_slug=cat.slug, service_slug=svc.slug)))
    if not student:  # a guest-friendly form: nothing to resume
        return redirect(url_for("public.og_form_view", lang=lang, slug=form.slug))
    if not allow(f"intake-start:{student.id}", 30, 60):
        abort(429)
    submission = start_or_resume(form, student, lang, service=svc, new=request.args.get("new") == "1")
    from app.case_setup import needs_setup

    if needs_setup(submission):
        return redirect(url_for("public.og_form_setup", lang=lang, slug=submission.form.slug, t=submission.resume_token))
    if submission.status == "reopened":  # OG unlocked it for editing: land on the review, where every section has Edit
        return redirect(url_for("public.og_form_review", lang=lang, slug=submission.form.slug, t=submission.resume_token))
    return redirect(url_for("public.og_form_view", lang=lang, slug=submission.form.slug, page=submission.current_page, t=submission.resume_token))


@public_bp.route("/blog")
def blog(lang):
    category = request.args.get("category", "").strip()
    query = BlogPost.query.filter_by(is_published=True)
    if category:
        query = query.filter_by(category=category)
    posts = query.order_by(BlogPost.published_at.desc()).all()
    categories = sorted({p.category for p in BlogPost.query.filter_by(is_published=True).all() if p.category})
    return render_template("public/blog_list.html", posts=posts, categories=categories, active_category=category)


@public_bp.route("/blog/5-documents-you-need-for-an-itin-application")
def blog_post_redirect_itin_slug(lang):
    """Temporary/internal redirect for this new site's OWN pre-launch slug correction (see
    app/seed_seo_fixes.py ensure_itin_blog_slug_fix — the old slug never matched the post's real
    title/content) — NOT a legacy Wix redirect, do not add this pattern to app/legacy_redirects.py."""
    return redirect(url_for("public.blog_post", lang=lang, slug="what-is-an-itin-and-who-needs-one"), code=301)


@public_bp.route("/blog/<slug>")
def blog_post(lang, slug):
    post = BlogPost.query.filter_by(slug=slug, is_published=True).first_or_404()
    related = (
        BlogPost.query.filter(BlogPost.id != post.id, BlogPost.is_published.is_(True))
        .order_by(BlogPost.published_at.desc())
        .limit(3)
        .all()
    )
    return render_template("public/blog_post.html", post=post, related=related)


@public_bp.route("/blog/media/<int:post_id>/<path:stored_path>")
def blog_asset(lang, post_id, stored_path):
    post = BlogPost.query.filter_by(id=post_id, is_published=True).first_or_404()
    valid_paths = {post.cover_image} | {m.filename for m in post.media}
    if stored_path not in valid_paths:
        abort(404)
    full_path = course_media_full_path(stored_path)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path, conditional=True)


@public_bp.route("/blog/content-image/<path:stored_path>")
def blog_content_image(lang, stored_path):
    if not stored_path.startswith("images/"):
        abort(404)
    if not is_admin_logged_in():
        match = BlogPost.query.filter(
            BlogPost.is_published.is_(True),
            db.or_(
                BlogPost.content_en.contains(stored_path),
                BlogPost.content_es.contains(stored_path),
            ),
        ).first()
        if not match:
            abort(404)
    full_path = course_media_full_path(stored_path)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path, conditional=True)


@public_bp.route("/courses/media/<int:course_id>/<path:stored_path>")
def course_asset(lang, course_id, stored_path):
    course = Course.query.filter_by(id=course_id, is_published=True).first_or_404()
    if stored_path != course.cover_image:
        abort(404)
    full_path = course_media_full_path(stored_path)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path, conditional=True)


@public_bp.route("/courses/certificate-media/<int:course_id>/<path:stored_path>")
def certificate_asset(lang, course_id, stored_path):
    """Serves a course's certificate logo/signature image — publicly
    accessible with no login, since these appear on the public certificate
    verification page as well as the student's own certificate view."""
    course = Course.query.filter_by(id=course_id, is_published=True).first_or_404()
    if stored_path not in {course.certificate_logo_image, course.certificate_signature_image}:
        abort(404)
    full_path = course_media_full_path(stored_path)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path, conditional=True)


@public_bp.route("/about")
def about(lang):
    return render_template("public/about.html")


@public_bp.route("/contact", methods=["GET", "POST"])
def contact(lang):
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        error = None
        if not name:
            error = get_text(lang, "flash_name_required")
        elif not email or "@" not in email:
            error = get_text(lang, "flash_email_invalid")

        if error:
            flash(error, "error")
            return render_template("public/contact.html")

        db.session.add(
            Inquiry(
                source="contact",
                language=lang,
                name=name,
                email=email,
                phone=request.form.get("phone", "").strip(),
                message=request.form.get("message", "").strip(),
            )
        )
        db.session.commit()
        flash(get_text(lang, "flash_contact_sent"), "success")
        return redirect(url_for("public.contact", lang=lang))

    return render_template("public/contact.html")


@public_bp.route("/translations/quote", methods=["POST"])
def translation_quote(lang):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    error = None
    if not name:
        error = get_text(lang, "flash_name_required")
    elif not email or "@" not in email:
        error = get_text(lang, "flash_email_invalid")

    if error:
        flash(error, "error")
        return redirect(url_for("public.translations", lang=lang))

    uploaded = request.files.get("file")
    file_filename = None
    if uploaded and uploaded.filename:
        try:
            file_filename = save_course_media(uploaded, "document")
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("public.translations", lang=lang))

    db.session.add(
        Inquiry(
            source="translation_quote",
            language=lang,
            name=name,
            email=email,
            phone=request.form.get("phone", "").strip(),
            target_language=request.form.get("target_language", "").strip(),
            message=request.form.get("message", "").strip(),
            file_filename=file_filename,
        )
    )
    db.session.commit()
    flash(get_text(lang, "flash_quote_sent"), "success")
    return redirect(url_for("public.translations", lang=lang))


@public_bp.route("/chat/message", methods=["POST"])
def chat_message(lang):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    if not name or not email or "@" not in email:
        return {"ok": False}, 400

    db.session.add(
        Inquiry(
            source="chat",
            language=lang,
            name=name,
            email=email,
            phone=request.form.get("phone", "").strip(),
            message=request.form.get("message", "").strip(),
        )
    )
    db.session.commit()
    return {"ok": True}
