"""Customer-facing steps of a service intake that come after the questions:
review, final submission and removing an uploaded document. All of them act only
on the signed-in customer's own draft."""

from datetime import datetime

from flask import abort, flash, jsonify, redirect, render_template, request, url_for

from app.activity import log_event
from app.auth import validate_csrf
from app.blueprints.public.routes import (
    _form_login_redirect,
    _service_title,
    _upsert_submission_value,
    public_bp,
)
from app.extensions import db
from app.forms_engine import queue_form_notifications
from app.i18n import get_text
from app.intake import owned_submission, purge_hidden_values
from app.reopen import is_reopened, record_resubmission
from app.intake_engine import answers_for, build_snapshot, context_map, problems, progress_for, review_sections
from app.intake_shared import set_name_tokens, supplement_map
from app.models import Form, SubmissionFile
from app.student_auth import current_student
from app.uploads import delete_course_media


def _intake_form(slug):
    form = Form.query.filter_by(slug=slug, status="published").first_or_404()
    if not form.is_service_intake:
        abort(404)
    return form


def _owned_draft_or_redirect(form, lang):
    """(submission, None) for the signed-in owner's draft; (None, redirect) to sign in."""
    student = current_student()
    if not student:
        return None, _form_login_redirect(lang, form.slug)
    submission = owned_submission(form, student, request.values.get("t", "").strip() or request.values.get("resume_token", "").strip())
    if not submission:
        abort(404)
    from app.case_setup import needs_setup

    if needs_setup(submission) and not submission.is_complete:
        return None, redirect(url_for("public.og_form_setup", lang=lang, slug=form.slug, t=submission.resume_token))
    return submission, None


def _docs_block(form, submission, lang):
    from app.intake_shared import documents_block_html

    html_ = documents_block_html(form, submission, lang)
    title = next((s["title"][lang] for s in (form.features.get("sections") or []) if s["key"] == "documents"), "Documents")
    return {"title": title, "html": html_} if html_ else None


def _review_groups(form, lang):
    """{group_key: {title, tag}} when the form asks for group headings on Review (features["review_groups"]: {group: {"en": tag, "es": tag} | None}); else None."""
    rg = (form.features or {}).get("review_groups")
    if not rg:
        return None
    return {s["key"]: {"title": s["title"][lang], "tag": ((rg.get(s["key"]) or {}).get(lang) if isinstance(rg, dict) else None)} for s in (form.features.get("sections") or [])}


@public_bp.route("/f/<slug>/review")
def og_form_review(lang, slug):
    form = _intake_form(slug)
    submission, response = _owned_draft_or_redirect(form, lang)
    if response is not None:
        return response
    if submission.is_complete:
        return redirect(url_for("public.og_form_view", lang=lang, slug=slug, t=submission.resume_token))

    set_name_tokens(form, submission)
    purge_hidden_values(form, submission, answers_for(submission))
    db.session.commit()
    sections = review_sections(form, submission, lang, reveal=False)
    blockers = problems(sections)
    progress = progress_for(form, submission, form.pages[-1])
    return render_template(
        "public/intake_review.html", form=form, submission=submission, service=submission.service,
        sections=sections, blockers=blockers, blocker_labels=[i["label"] for _s, i in blockers][:6], progress=progress,
        back_page=(form.pages.index(progress["path"][-1]) + 1) if progress["path"] else 1,
        contexts=context_map(form, submission, lang), supplements=supplement_map(form, lang),
        check_url=(url_for("public.og_form_check", lang=lang, slug=slug, t=submission.resume_token) if form.features.get("completeness_check") else None),
        page_number=len(form.pages), total_pages=len(form.pages), group_titles=_review_groups(form, lang),
        docs_block=(_docs_block(form, submission, lang) if (form.features or {}).get("review_documents") else None),
    )


@public_bp.route("/f/<slug>/check")
def og_form_check(lang, slug):
    """Completeness Check: what is finished and what still needs attention, before the
    final review. Only for intakes that enable it."""
    from app.intake_completeness import completeness_report

    form = _intake_form(slug)
    if not form.features.get("completeness_check"):
        abort(404)
    submission, response = _owned_draft_or_redirect(form, lang)
    if response is not None:
        return response
    if submission.is_complete:
        return redirect(url_for("public.og_form_view", lang=lang, slug=slug, t=submission.resume_token))
    set_name_tokens(form, submission)
    purge_hidden_values(form, submission, answers_for(submission))
    db.session.commit()
    report = completeness_report(form, submission, lang)
    progress = progress_for(form, submission, form.pages[-1])
    first_issue = next((i for g in report["groups"] for i in g["issues"]), None)
    return render_template(
        "public/intake_check.html", form=form, submission=submission, service=submission.service, report=report, progress=progress,
        first_issue=first_issue, back_page=(form.pages.index(progress["path"][-1]) + 1) if progress["path"] else 1,
    )


@public_bp.route("/f/<slug>/finalize", methods=["POST"])
def og_form_finalize(lang, slug):
    """Final submission to OG: validate everything again on the server, freeze a
    snapshot, and mark the application Submitted."""
    form = _intake_form(slug)
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    submission, response = _owned_draft_or_redirect(form, lang)
    if response is not None:
        return response
    if submission.is_complete:
        return redirect(url_for("public.og_form_view", lang=lang, slug=slug, t=submission.resume_token))

    set_name_tokens(form, submission)
    purge_hidden_values(form, submission, answers_for(submission))
    sections = review_sections(form, submission, lang, reveal=False)
    blockers = problems(sections)
    if blockers:
        db.session.commit()
        flash(get_text(lang, "intake_review_incomplete"), "error")
        return redirect(url_for("public.og_form_review", lang=lang, slug=slug, t=submission.resume_token))

    was_reopened = is_reopened(submission)
    previous_snapshot = submission.snapshot_json
    submission.snapshot_json = build_snapshot(form, submission)
    if not was_reopened:  # a reopened application keeps its ORIGINAL form version, edition and submitted date
        submission.form_version = form.version
        submission.source_edition_snapshot = form.source_edition
        submission.submitted_at = datetime.utcnow()
    submission.language = lang
    submission.is_complete = True
    submission.status = "new"
    submission.updated_at = datetime.utcnow()
    submission.current_page = len(form.pages)
    if was_reopened:
        record_resubmission(submission, previous_snapshot, submission.snapshot_json)
    db.session.commit()
    try:
        from app.cases import harvest_facts

        harvest_facts(submission)  # offer the mapped person facts to the case (never overwrites another application's value)
    except Exception:  # noqa: BLE001
        db.session.rollback()
    log_event(submission.student_id, "application_resubmitted" if was_reopened else "application_submitted",
              entity=("submission", submission.id), meta={"service": _service_title(submission)})
    queue_form_notifications(form, submission)
    return redirect(url_for("public.og_form_view", lang=lang, slug=slug, t=submission.resume_token))


@public_bp.route("/f/<slug>/files/<int:file_id>/remove", methods=["POST"])
def og_form_file_remove(lang, slug, file_id):
    form = _intake_form(slug)
    student = current_student()
    if not student:
        return jsonify({"error": "auth"}), 401
    if not validate_csrf(request.headers.get("X-CSRFToken") or request.form.get("csrf_token")):
        return jsonify({"error": "csrf"}), 400
    file = db.session.get(SubmissionFile, file_id)
    submission = file.submission if file else None
    # Ownership is decided by the signed-in customer, never by ids in the request.
    if not file or submission.form_id != form.id or submission.student_id != student.id or submission.is_complete:
        return jsonify({"error": "not_found"}), 404

    name, field_id = file.original_filename, file.field_id
    delete_course_media(file.stored_filename)
    db.session.delete(file)
    db.session.flush()
    remaining = [f.original_filename for f in submission.files if f.field_id == field_id and f.id != file_id]
    field = next((f for f in form.all_fields if f.id == field_id), None)
    if field is not None:
        _upsert_submission_value(submission, field, lang, ", ".join(remaining) or None, ", ".join(remaining))
    submission.updated_at = datetime.utcnow()
    db.session.commit()
    log_event(student.id, "document_removed", entity=("submission", submission.id), meta={"filename": name, "service": _service_title(submission)})
    return jsonify({"ok": True})


@public_bp.route("/f/<slug>/files/upload", methods=["POST"])
def og_form_file_upload(lang, slug):
    """Instant upload for a document field: validated (type, real content, size,
    count) and stored the moment it is chosen, so the customer sees it saved."""
    from app.blueprints.public.routes import _extract_field_value, _persist_field
    from app.intake_engine import validate_value  # noqa: F401  (keeps imports honest for readers)

    form = _intake_form(slug)
    student = current_student()
    if not student:
        return jsonify({"error": "auth"}), 401
    if not validate_csrf(request.headers.get("X-CSRFToken") or request.form.get("csrf_token")):
        return jsonify({"error": "csrf"}), 400
    from app.ratelimit import allow

    if not allow(f"upload:{student.id}", 60, 300):
        return jsonify({"error": "rate", "message": get_text(lang, "flash_too_many")}), 429

    submission = owned_submission(form, student, request.form.get("resume_token", "").strip())
    if not submission or submission.is_complete:
        return jsonify({"error": "not_found"}), 404
    field = next((f for f in form.all_fields if f.id == request.form.get("field_id", type=int)), None)
    if field is None or field.field_type != "file_upload":
        return jsonify({"error": "bad_field"}), 400
    from app.forms_engine import compute_field_effects

    if not compute_field_effects(form, answers_for(submission)).get(field.id, {}).get("visible", True):
        return jsonify({"error": "bad_field"}), 400  # a document the answers say isn't needed

    original_required = field.required
    field.required = False
    try:
        _value, _display, error, files = _extract_field_value(field, lang)
    finally:
        field.required = original_required
    if not error and files and (field.max_files or 1) > 1:
        already = SubmissionFile.query.filter_by(submission_id=submission.id, field_id=field.id).count()
        if already + len(files) > field.max_files:
            error = (f"You can upload up to {field.max_files} files here." if lang == "en" else f"Puedes subir hasta {field.max_files} archivos aquí.")
    if error:
        return jsonify({"error": "invalid", "message": error}), 422
    if not files:
        return jsonify({"error": "empty", "message": get_text(lang, "flash_form_required")}), 422

    _persist_field(submission, field, lang, None, None, files)
    submission.updated_at = datetime.utcnow()
    db.session.commit()
    stored = SubmissionFile.query.filter_by(submission_id=submission.id, field_id=field.id).order_by(SubmissionFile.id).all()
    return jsonify({"ok": True, "files": [
        {"id": f.id, "name": f.original_filename, "size": f.size_bytes or 0, "mime": f.mime_type or "",
         "view": url_for("account.document_file", lang=lang, file_id=f.id, inline=1),
         "remove": url_for("public.og_form_file_remove", lang=lang, slug=slug, file_id=f.id)} for f in stored]})


@public_bp.route("/f/<slug>/passport", methods=["GET", "POST"])
def og_form_passport(lang, slug):
    """ITIN / W-7 passport step: upload the photo page (now or later), see what was found on it and CONFIRM or CORRECT it. Works for a draft and for an application that is
    already with OG (a passport uploaded later). Nothing becomes a confirmed Person fact before the customer confirms."""
    from app import case_documents as vault
    from app import w7_docs, w7_views
    from app.ratelimit import allow

    form = _intake_form(slug)
    if form.source_form_name != "W-7":
        abort(404)
    student = current_student()
    if not student:
        return _form_login_redirect(lang, form.slug)
    submission = owned_submission(form, student, request.values.get("t", "").strip())
    if not submission or submission.case_id is None:
        abort(404)
    req = w7_docs.passport_requirement(submission)
    if req is None:
        abort(404)
    errors, posted, notice = {}, None, None
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        if not allow(f"w7-passport:{student.id}", 30, 300):
            abort(429)
        action = request.form.get("action")
        if action == "upload":
            f = request.files.get("file")
            error = vault.validate_upload(f, lang) if f and f.filename else get_text(lang, "case_choose_file")
            if error:
                notice = ("error", error)
            elif req.status not in vault.CUSTOMER_CAN_UPLOAD:
                notice = ("error", get_text(lang, "case_cannot_upload"))
            else:
                doc = vault.upload_for_requirement(req, f, uploaded_by="customer", uploaded_by_id=student.id)
                w7_views.after_upload(req, doc)
                log_event(student.id, "w7_passport_uploaded", entity=("submission", submission.id), meta={"application": submission.code})
                return redirect(url_for("public.og_form_passport", lang=lang, slug=slug, t=submission.resume_token, _anchor="confirm"))
        elif action == "confirm":
            answers, errors = w7_views.validate_passport(request.form, lang)
            posted = request.form
            if not errors:
                w7_views.save_passport(submission, answers, lang)
                return redirect(url_for("public.og_form_passport", lang=lang, slug=slug, t=submission.resume_token, saved=1))
        elif action == "remove":
            doc = req.current_document
            if doc is None or not vault.customer_can_remove(req, doc):
                notice = ("error", get_text(lang, "case_cannot_upload"))
            else:
                w7_views.remove_passport(submission, req, doc, actor_id=student.id)
                return redirect(url_for("public.og_form_passport", lang=lang, slug=slug, t=submission.resume_token, removed=1))
    values, pending = w7_views.form_values(submission)
    state = w7_docs.passport_state(submission)
    return render_template(
        "public/intake_passport.html", form=form, submission=submission, service=submission.service, fields=w7_views.PASSPORT_FIELDS, values=(posted or values), errors=errors,
        pending=pending, state=state, req=req, doc=req.current_document, can_upload=req.status in vault.CUSTOMER_CAN_UPLOAD, can_remove=vault.customer_can_remove(req, req.current_document),
        notice=notice, saved=request.args.get("saved") == "1", removed=request.args.get("removed") == "1", ocr=w7_views.PP.ocr_available(),
        back_url=url_for("public.og_form_view", lang=lang, slug=slug, t=submission.resume_token, page=submission.current_page),
    )


@public_bp.route("/f/<slug>/records/analyze", methods=["POST"])
def og_form_records_analyze(lang, slug):
    """Coverage / gap / overlap / totals for a record_list field, computed on the server
    so the builder, the review and Admin all agree. Stateless: it reads nothing from
    any submission, so it cannot expose anyone's data."""
    from app.intake_records import analyze, field_config, parse_records, sanitize_records
    from app.ratelimit import allow

    form = _intake_form(slug)
    student = current_student()
    if not student:
        return jsonify({"error": "auth"}), 401
    if not validate_csrf(request.headers.get("X-CSRFToken") or request.form.get("csrf_token")):
        return jsonify({"error": "csrf"}), 400
    if not allow(f"records:{student.id}", 300, 60):
        return jsonify({"error": "rate"}), 429
    field = next((f for f in form.all_fields if f.id == request.form.get("field_id", type=int) and f.field_type == "record_list"), None)
    if field is None:
        return jsonify({"error": "bad_field"}), 400
    cfg = field_config(field)
    records = sanitize_records(parse_records(request.form.get("records", "")), cfg)
    if any(r.get("person_id") for r in records):  # a record that points at one of the customer's own people reads as that person (verified; never saved here)
        from app.i864_views import fill_from_people

        fill_from_people(records, student.id, cfg.get("fill_extra"))
    from app.intake_records import parse_date

    return jsonify(analyze(cfg, records, lang, since=parse_date(request.form.get("since"))))
