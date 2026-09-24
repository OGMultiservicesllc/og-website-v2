"""My OG Account: one customer identity for applications, documents, courses and
profile. (The Overview lives in routes.py as `account.dashboard`.)"""

import os
from datetime import datetime

from flask import abort, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.activity import log_event
from app.auth import validate_csrf
from app.blueprints.account.routes import account_bp
from app.extensions import db
from app.i18n import get_text
from app.intake_engine import load_snapshot, progress_for, status_key, status_label
from app.models import Certificate, Enrollment, FormSubmission, LessonProgress, Student, SubmissionFile
from app.progress import course_lessons, course_progress, unlocked_lesson_ids
from app.student_auth import current_student, student_required
from app.uploads import course_media_full_path, delete_course_media


# ------------------------------------------------------------------ helpers (also used by the Overview)
def card_title(sub, lang):
    """The application's title; a W-7 is one per person, so it names its applicant (a household's applications must not look identical)."""
    title = sub.service.title(lang) if sub.service else sub.form.title(lang)
    if sub.form.source_form_name == "W-7" and sub.case_id:
        from app import cases as case_svc

        cp = case_svc.role_person(sub, "itin_applicant")
        if cp is not None:
            title = f"{title} — {cp.full_name}"
    return title


def application_cards(student, lang, limit=None):
    """Drafts first (most recently saved), then submitted work."""
    submissions = (
        FormSubmission.query.filter_by(student_id=student.id)
        .order_by(FormSubmission.is_complete.asc(), FormSubmission.updated_at.desc(), FormSubmission.id.desc())
        .all()
    )
    cards = []
    for sub in submissions[: limit or len(submissions)]:
        form = sub.form
        reopened = sub.status == "reopened" and not sub.is_complete
        percent = 100 if (sub.is_complete or reopened) else progress_for(form, sub)["percent"]
        cards.append({
            "submission": sub,
            "title": card_title(sub, lang),
            "form_title": form.source_form_name and f"Form {form.source_form_name}" or form.title(lang),
            "status": status_key(sub),
            "label": status_label(sub, lang),
            "percent": percent,
            "updated_at": sub.updated_at or sub.submitted_at,
            "is_draft": not sub.is_complete,
            "reopened": reopened,
            "message": sub.reopen_message if reopened else None,
            "continue_url": (url_for("public.og_form_review", lang=lang, slug=form.slug, t=sub.resume_token) if reopened
                             else url_for("public.og_form_view", lang=lang, slug=form.slug, page=sub.current_page, t=sub.resume_token)) if not sub.is_complete else None,
            "view_url": url_for("account.application_detail", lang=lang, submission_id=sub.id),
        })
    return cards


def course_cards(student, lang):
    enrollments = Enrollment.query.filter_by(student_id=student.id).order_by(Enrollment.enrolled_at.desc()).all()
    certificates = {c.course_id: c for c in Certificate.query.filter_by(student_id=student.id).all()}
    cards = []
    for e in enrollments:
        course = e.course
        progress = course_progress(student, course)
        lessons = course_lessons(course)
        done_ids = {p.lesson_id for p in LessonProgress.query.filter_by(student_id=student.id, is_completed=True).all()}
        unlocked = unlocked_lesson_ids(student, course)
        target = next((l for l in lessons if l.id not in done_ids and l.id in unlocked), None)
        cert = certificates.get(course.id)
        cards.append({
            "enrollment": e, "course": course, "progress": progress, "certificate": cert,
            "continue_url": url_for("public.lesson_view", lang=lang, slug=course.slug, lesson_id=target.id) if target and e.is_active else url_for("public.course_detail", lang=lang, slug=course.slug),
            "status": "revoked" if e.is_revoked else ("expired" if e.is_expired else ("completed" if progress["is_complete"] else "in_progress")),
        })
    return cards


def document_rows(student):
    return (
        SubmissionFile.query.join(FormSubmission, SubmissionFile.submission_id == FormSubmission.id)
        .filter(FormSubmission.student_id == student.id)
        .order_by(SubmissionFile.uploaded_at.desc(), SubmissionFile.id.desc())
        .all()
    )


# ------------------------------------------------------------------ applications
@account_bp.route("/applications")
@student_required
def applications(lang):
    return render_template("account/applications.html", cards=application_cards(current_student(), lang), section="applications")


@account_bp.route("/applications/<int:submission_id>")
@student_required
def application_detail(lang, submission_id):
    student = current_student()
    sub = FormSubmission.query.filter_by(id=submission_id, student_id=student.id).first()
    if not sub:  # someone else's id looks exactly like a missing one
        abort(404)
    form = sub.form
    snapshot = load_snapshot(sub)
    sections = []
    if snapshot:
        for section in snapshot["sections"]:
            items = []
            for it in section["items"]:
                value = it["display_es"] if lang == "es" else it["display_en"]
                if it.get("private") and value:  # a private filing basis / health answer is never shown in later customer views
                    value = "Private — shared only with OG" if lang != "es" else "Privado — solo compartido con OG"
                elif it.get("sensitive") and value:
                    value = "•" * max(len(str(value)) - 4, 0) + str(value)[-4:]
                items.append({"label": it["label_es"] if lang == "es" else it["label_en"], "value": value, "files": it.get("files", [])})
            sections.append({"title": section["title_es"] if lang == "es" and section["title_es"] else section["title_en"], "items": items})
    messages = [n for n in sub.notes if n.is_customer_visible]
    return render_template(
        "account/application_detail.html", sub=sub, form=form, sections=sections, files=sub.files, messages=messages,
        card=application_cards_single(sub, lang), status=status_key(sub), label=status_label(sub, lang), section="applications",
    )


def application_cards_single(sub, lang):
    form = sub.form
    reopened = sub.status == "reopened" and not sub.is_complete
    if sub.is_complete:
        url = None
    elif reopened:
        url = url_for("public.og_form_review", lang=lang, slug=form.slug, t=sub.resume_token)
    else:
        url = url_for("public.og_form_view", lang=lang, slug=form.slug, page=sub.current_page, t=sub.resume_token)
    return {
        "title": card_title(sub, lang),
        "percent": 100 if (sub.is_complete or reopened) else progress_for(form, sub)["percent"],
        "continue_url": url, "reopened": reopened,
    }


# ------------------------------------------------------------------ services (unified: cases + case-less drafts, replaces the old separate Applications/Cases tabs in the nav)
@account_bp.route("/services")
@student_required
def services(lang):
    from app import account_dashboard

    return render_template("account/services.html", section="services", **account_dashboard.services_data(current_student(), lang))


# ------------------------------------------------------------------ documents (the Document Vault across every case, plus files attached inside applications)
@account_bp.route("/documents")
@student_required
def documents(lang):
    from app import account_dashboard

    return render_template("account/documents.html", section="documents", **account_dashboard.documents_data(current_student(), lang))


# ------------------------------------------------------------------ messages (read-only: customer-visible notes and case messages, already stored elsewhere)
@account_bp.route("/messages")
@student_required
def messages(lang):
    from app import account_dashboard

    return render_template("account/messages.html", section="messages", messages=account_dashboard.messages_data(current_student(), lang))


@account_bp.route("/files/<int:file_id>")
@student_required
def document_file(lang, file_id):
    """A customer's own uploaded document. Ownership is decided here, on the server,
    from the signed-in customer — never from anything in the URL."""
    student = current_student()
    file = SubmissionFile.query.filter_by(id=file_id).first()
    if not file or file.submission.student_id != student.id:
        abort(404)
    path = course_media_full_path(file.stored_filename)
    if not os.path.isfile(path):
        abort(404)
    inline = request.args.get("inline") == "1" and (file.mime_type or "") in ("application/pdf", "image/jpeg", "image/png", "image/webp")
    response = send_file(path, mimetype=file.mime_type or "application/octet-stream", as_attachment=not inline, download_name=file.original_filename, conditional=True)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@account_bp.route("/og-files/<int:file_id>")
@student_required
def og_file_download(lang, file_id):
    """A file OG sent TO the customer (see app/customer_files.py). Ownership decided here from the signed-in
    customer, and only a PUBLISHED file is ever returned — never another customer's, never an admin draft.
    `?inline=1` powers the Files from OG "View" button for a PDF/image (item A15); anything else always downloads."""
    from app import customer_files as cf_service

    student = current_student()
    f = cf_service.owned(student, file_id)
    if f is None:
        abort(404)
    path = course_media_full_path(f.stored_filename)
    if not os.path.isfile(path):
        abort(404)
    cf_service.mark_downloaded(f)
    inline = request.args.get("inline") == "1" and (f.mime_type or "") in ("application/pdf", "image/jpeg", "image/png", "image/webp")
    response = send_file(path, mimetype=f.mime_type or "application/octet-stream", as_attachment=not inline, download_name=f.original_filename, conditional=True)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


# ------------------------------------------------------------------ Files from OG (dedicated page — item A3; the OG -> customer digital file vault)
@account_bp.route("/files-from-og")
@student_required
def files_from_og(lang):
    from app import account_dashboard

    category = request.args.get("category") or "all"
    q = request.args.get("q") or ""
    return render_template("account/files_from_og.html", section="files_from_og",
                           **account_dashboard.files_from_og_data(current_student(), lang, category=category, q=q))


# ------------------------------------------------------------------ courses
@account_bp.route("/courses")
@student_required
def courses(lang):
    return render_template("account/courses.html", cards=course_cards(current_student(), lang), section="courses")


# ------------------------------------------------------------------ profile
@account_bp.route("/profile", methods=["GET", "POST"])
@student_required
def profile(lang):
    student = current_student()
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        action = request.form.get("action")
        if action == "password":
            current = request.form.get("current_password", "")
            new = request.form.get("new_password", "")
            if not check_password_hash(student.password_hash, current):
                flash(get_text(lang, "acct_password_wrong"), "error")
            elif len(new) < 8:
                flash(get_text(lang, "flash_password_short"), "error")
            else:
                student.password_hash = generate_password_hash(new)
                db.session.commit()
                keep = {"csrf_token": session.get("csrf_token")}
                session.clear()  # invalidate the old session id after a credential change
                session.update(keep)
                session["student_id"] = student.id
                log_event(student.id, "password_changed")
                flash(get_text(lang, "acct_password_changed"), "success")
        else:
            name = request.form.get("name", "").strip()
            if not name:
                flash(get_text(lang, "flash_name_required"), "error")
            else:
                student.name = name[:200]
                student.phone = request.form.get("phone", "").strip()[:40] or None
                pref = request.form.get("preferred_language", "")
                student.preferred_language = pref if pref in ("en", "es") else None
                db.session.commit()
                log_event(student.id, "profile_updated")
                flash(get_text(lang, "acct_profile_saved"), "success")
        return redirect(url_for("account.profile", lang=lang))
    return render_template("account/profile.html", section="profile")


# ------------------------------------------------------------------ profile photo (same secure upload storage as course/case media)
@account_bp.route("/profile/photo", methods=["POST"])
@student_required
def profile_photo(lang):
    from app.media_library import _save_verified_image

    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    student = current_student()
    f = request.files.get("photo")
    if not f or not f.filename:
        flash(get_text(lang, "acct_photo_choose"), "error")
        return redirect(url_for("account.profile", lang=lang))
    try:
        stored = _save_verified_image(f)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("account.profile", lang=lang))
    old = student.photo_filename
    student.photo_filename = stored
    db.session.commit()
    if old:
        delete_course_media(old)
    log_event(student.id, "profile_updated")
    flash(get_text(lang, "acct_photo_saved"), "success")
    return redirect(url_for("account.profile", lang=lang))


@account_bp.route("/profile/photo/remove", methods=["POST"])
@student_required
def profile_photo_remove(lang):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    student = current_student()
    if student.photo_filename:
        delete_course_media(student.photo_filename)
        student.photo_filename = None
        db.session.commit()
        log_event(student.id, "profile_updated")
    return redirect(url_for("account.profile", lang=lang))


@account_bp.route("/photo")
@student_required
def photo(lang):
    """The signed-in customer's OWN profile photo. There is no id in this URL — it can only ever be
    'my own photo', so there is nothing for one customer to guess their way into seeing another's."""
    student = current_student()
    if not student.photo_filename:
        abort(404)
    path = course_media_full_path(student.photo_filename)
    if not os.path.isfile(path):
        abort(404)
    response = send_file(path, conditional=True)
    response.headers["Cache-Control"] = "private, max-age=86400"
    return response
