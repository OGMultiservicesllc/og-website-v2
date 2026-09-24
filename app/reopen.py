"""Reopen a submitted Smart Intake so the customer can edit and resubmit it.

Generic: it works on any FormSubmission of a service-intake form (I-90, N-400, ...).
The submission stays the SAME record. Its id, answers, documents, notes, activity,
form version and source edition are untouched; only its state changes:

    Submitted --(OG reopens)--> Reopened for Editing --(customer resubmits)--> Submitted

Rules:
  * Only staff reach `reopen_submission` (the admin route is `admin_required`).
  * `submitted_at` is always the ORIGINAL submission time; the cycle is recorded in
    a `SubmissionRevision` (reopened/resubmitted timestamps + what changed).
  * While reopened, the customer edits through the normal intake screens, guarded by
    the same ownership checks as any draft (`intake.owned_submission`).
"""

import json
from datetime import datetime

from app.activity import log_event
from app.extensions import db
from app.intake_engine import load_snapshot, mask
from app.models import SubmissionRevision

REOPENED = "reopened"


def is_reopened(submission):
    return (not submission.is_complete) and submission.status == REOPENED


def _service_title(submission):
    return submission.service.title_en if submission.service else submission.form.name_admin


def reopen_submission(submission, message=None, actor_id=None):
    """Unlock a submitted intake for customer editing. Returns False if it is not
    a submitted service intake (nothing to reopen)."""
    if not submission.is_complete or not submission.form.is_service_intake:
        return False
    now = datetime.utcnow()
    submission.is_complete = False
    submission.status = REOPENED
    submission.reopened_at = now
    submission.reopen_message = (message or "").strip() or None
    submission.reopen_count = (submission.reopen_count or 0) + 1
    submission.updated_at = now
    db.session.add(SubmissionRevision(submission_id=submission.id, reopened_at=now))
    from app import persons as _pers

    _pers.refresh_states(submission)  # its claims are "reopened" now, no longer plain "submitted"
    if submission.form.source_form_name == "DS-260" and submission.ds260 is not None:  # a reopened OG record is not "ready for CEAC" any more (OG reopening never reopens CEAC)
        submission.ds260.ready_for_ceac_at = submission.ds260.ready_for_ceac_by = None
    db.session.commit()
    if submission.student_id:
        log_event(submission.student_id, "application_reopened", actor="admin", actor_id=actor_id,
                  entity=("submission", submission.id), meta={"service": _service_title(submission), "has_message": bool(submission.reopen_message)})
    return True


def lock_again(submission, actor_id=None):
    """Staff closes a reopened intake without waiting for the customer to resubmit."""
    if not is_reopened(submission):
        return False
    submission.is_complete = True
    submission.status = "new"
    submission.updated_at = datetime.utcnow()
    submission.reopen_message = None
    from app import persons as _pers

    _pers.refresh_states(submission)
    db.session.commit()
    if submission.student_id:
        log_event(submission.student_id, "application_relocked", actor="admin", actor_id=actor_id,
                  entity=("submission", submission.id), meta={"service": _service_title(submission)})
    return True


def diff_snapshots(before, after):
    """[{label, before, after, ref}] for every answer that changed between two
    snapshots (built by intake_engine.build_snapshot). Sensitive values are masked."""
    def flat(snapshot):
        out = {}
        for section in (snapshot or {}).get("sections", []):
            for item in section["items"]:
                value = item.get("display_en") or ""
                if item.get("sensitive") and value:
                    value = mask(value)
                out[item["internal_name"]] = (item.get("label_en") or item["internal_name"], value, item.get("source_ref"))
        return out

    old, new = flat(before), flat(after)
    changes = []
    for name in list(new) + [n for n in old if n not in new]:
        b = old.get(name, (None, "", None))
        a = new.get(name, (None, "", None))
        if b[1] != a[1]:
            changes.append({"label": a[0] or b[0], "before": b[1], "after": a[1], "ref": a[2] or b[2]})
    return changes


def record_resubmission(submission, previous_snapshot_json, new_snapshot_json):
    """Close the open revision with the timestamp and the change list. Called by the
    final submit when the intake was reopened."""
    now = datetime.utcnow()
    try:
        before = json.loads(previous_snapshot_json) if previous_snapshot_json else None
        after = json.loads(new_snapshot_json) if new_snapshot_json else None
    except ValueError:
        before = after = None
    changes = diff_snapshots(before, after) if before and after else []
    revision = next((r for r in reversed(submission.revisions) if r.resubmitted_at is None), None)
    if revision is None:
        revision = SubmissionRevision(submission_id=submission.id, reopened_at=submission.reopened_at)
        db.session.add(revision)
    revision.resubmitted_at = now
    revision.changes_json = json.dumps(changes, ensure_ascii=False)
    submission.resubmitted_at = now
    submission.reopen_message = None
    return revision, changes


def revision_changes(revision):
    try:
        return json.loads(revision.changes_json or "[]")
    except ValueError:
        return []
