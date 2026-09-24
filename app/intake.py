"""Service-intake logic: who owns a draft, starting vs resuming, and keeping
conditionally-hidden answers out of the saved record.

Rules that hold everywhere in this module:
  * A draft belongs to exactly one signed-in customer (FormSubmission.student_id).
  * A customer never gets a second draft for the same form + service; the open
    one is resumed instead.
  * Ownership is always checked against the session's student, never trusted
    from a URL, hidden field or id.
"""

import secrets

from datetime import datetime, timedelta

from app.activity import log_event
from app.extensions import db
from app.forms_engine import compute_field_effects, generate_submission_code
from app.models import ActivityEvent, FormSubmission, SubmissionFile, SubmissionValue
from app.uploads import delete_course_media


def link_to_case(submission):
    """Every customer application lives in a case. Failure here must never break the customer's intake."""
    try:
        from app.case_setup import needs_setup
        from app.cases import ensure_case_for_submission

        if needs_setup(submission):
            return  # an application that needs its applicant + case chosen first (I-485) is attached by the setup step
        ensure_case_for_submission(submission)
    except Exception:  # noqa: BLE001
        db.session.rollback()
        import logging

        logging.getLogger(__name__).exception("could not link application %s to a case", getattr(submission, "id", "?"))


def multi_draft(form):
    """A form with one application per PERSON (DS-260: one per visa applicant) allows several open drafts at once."""
    from app.case_types import config_for

    return bool((config_for(form) or {}).get("multi_draft"))


def find_draft(student, form, service=None, new=False):
    """The customer's open draft. For a service, any version of its form counts, so a
    draft begun on an earlier version is resumed rather than duplicated. `new` (multi-draft forms only) asks for ANOTHER application: it still resumes a
    draft that has not picked its applicant/case yet, so a customer never leaves an empty orphan draft behind."""
    query = FormSubmission.query.filter_by(student_id=student.id, is_complete=False)
    if new and multi_draft(form):
        query = query.filter(FormSubmission.case_id.is_(None))
    query = query.filter_by(service_id=service.id) if service is not None else query.filter_by(form_id=form.id)
    return query.order_by(FormSubmission.updated_at.desc(), FormSubmission.id.desc()).first()


def owned_submission(form, student, token):
    """The submission for `token`, only if it is this customer's. Anything else
    (unknown token, someone else's draft) is None so callers answer 404."""
    if not student or not token:
        return None
    return FormSubmission.query.filter_by(resume_token=token, form_id=form.id, student_id=student.id).first()


def start_or_resume(form, student, lang, service=None, new=False):
    """Resume the customer's open draft for this form/service, or start one (`new`: another application of a multi-draft form)."""
    draft = find_draft(student, form, service, new=new)
    title = (draft.service.title_en if draft and draft.service else (service.title_en if service else form.name_admin))
    if draft:
        # One "continued" entry per sitting, not one per click.
        recent = ActivityEvent.query.filter(
            ActivityEvent.customer_id == student.id, ActivityEvent.event_type.in_(("application_continued", "application_editing_resumed")),
            ActivityEvent.entity_id == draft.id, ActivityEvent.created_at > datetime.utcnow() - timedelta(minutes=30),
        ).first()
        if draft.case_id is None:
            link_to_case(draft)
        if not recent:
            reopened = draft.status == "reopened"
            log_event(student.id, "application_editing_resumed" if reopened else "application_continued",
                      entity=("submission", draft.id), meta={"service": title})
        return draft
    draft = FormSubmission(
        form_id=form.id,
        code=generate_submission_code(),
        resume_token=secrets.token_urlsafe(32),
        language=lang,
        student_id=student.id,
        service_id=service.id if service else None,
        current_page=1,
        display_name=student.name,
        display_email=student.email,
        form_version=form.version,
        source_edition_snapshot=form.source_edition,
    )
    db.session.add(draft)
    db.session.commit()
    link_to_case(draft)
    log_event(student.id, "application_started", entity=("submission", draft.id), meta={"service": title})
    return draft


def purge_hidden_values(form, submission, answers):
    """Delete saved answers/files for fields the rules now hide, and for every field
    on a page the current answers skip, so a change of answer never leaves stale
    information from an abandoned branch in the record."""
    from app.intake_engine import path_pages

    from app.shared_blocks import is_kept

    effects = compute_field_effects(form, answers)
    hidden_ids = {fid for fid, e in effects.items() if not e.get("visible", True)}
    on_path = {p.id for p in path_pages(form, answers)}
    for page in form.pages:
        if page.id not in on_path:
            hidden_ids.update(f.id for f in page.fields)
    kept = {f.id for f in form.all_fields if is_kept(f)}  # confirmed copies of shared facts + system flags
    hidden_ids -= kept
    if not hidden_ids:
        return
    for value in list(submission.values):
        if value.field_id in hidden_ids:
            db.session.delete(value)
    for f in list(submission.files):
        if f.field_id in hidden_ids:
            delete_course_media(f.stored_filename)
            db.session.delete(f)
