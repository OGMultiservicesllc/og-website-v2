"""Admin side of the DS-260 workflow: the CEAC Preparation View, "Ready for CEAC", the CEAC status recorded by staff, per-value English overrides and the
consular case data. Nothing here talks to CEAC: staff read a value here and type it in CEAC themselves. "Ready for CEAC" never means submitted.
"""

from datetime import datetime

from flask import abort, flash, redirect, render_template, request, session, url_for

from app import consular, ds260_ceac
from app import ds260_views
from app.activity import log_event
from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.models import CEAC_STATUS_LABELS, Case, FormSubmission

AFTER_SUBMIT_WARNING = ("This OG record can be updated, but the submitted CEAC application may require reopening by the appropriate government office before changes can be entered there.")


def _staff():
    return session.get("admin_name") or session.get("admin_email") or "OG team"


def _ds260_or_404(submission_id):
    submission = db.session.get(FormSubmission, submission_id)
    if submission is None or submission.form.source_form_name != "DS-260":
        abort(404)
    return submission


def _csrf():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)


def _title(submission):
    return submission.service.title_en if submission.service else submission.form.name_admin


def _back(submission, endpoint="admin.ds260_prep"):
    return redirect(url_for(endpoint, submission_id=submission.id))


@admin_bp.route("/ds260/<int:submission_id>/ceac")
@admin_required
def ds260_prep(submission_id):
    submission = _ds260_or_404(submission_id)
    row = consular.ds260_row(submission)
    data = ds260_ceac.build(submission)
    return render_template("admin/ds260_prep.html", submission=submission, form=submission.form, data=data, ds=ds260_views.admin_summary(submission), row=row,
                           ceac_statuses=CEAC_STATUS_LABELS, after_submit_warning=AFTER_SUBMIT_WARNING)


@admin_bp.route("/ds260/<int:submission_id>/ready", methods=["POST"])
@admin_required
def ds260_ready(submission_id):
    _csrf()
    submission = _ds260_or_404(submission_id)
    row = consular.ds260_row(submission)
    prep = ds260_ceac.readiness(submission)
    if prep["blockers"]:
        flash("Not ready yet: " + " ".join(prep["blockers"]), "error")
        return _back(submission)
    if prep["warnings"] and not request.form.get("ack"):
        flash("Tick “I reviewed these warnings” to mark it ready: " + " ".join(prep["warnings"]), "error")
        return _back(submission)
    row.ready_for_ceac_at, row.ready_for_ceac_by = datetime.utcnow(), _staff()
    submission.status = "ready_for_ceac"
    db.session.commit()
    if submission.student_id:
        log_event(submission.student_id, "ds260_ready_for_ceac", actor="admin", entity=("submission", submission.id), meta={"service": _title(submission)})
    flash("Marked Ready for CEAC. This does not mean it was submitted: staff still enter it in CEAC and the applicant signs and submits there.", "success")
    if row.ceac_status == "submitted":
        flash(AFTER_SUBMIT_WARNING, "error")
    return _back(submission)


@admin_bp.route("/ds260/<int:submission_id>/not-ready", methods=["POST"])
@admin_required
def ds260_not_ready(submission_id):
    _csrf()
    submission = _ds260_or_404(submission_id)
    row = consular.ds260_row(submission)
    row.ready_for_ceac_at = row.ready_for_ceac_by = None
    if submission.status == "ready_for_ceac":
        submission.status = "in_review"
    db.session.commit()
    flash("Back to In Review.", "success")
    return _back(submission)


@admin_bp.route("/ds260/<int:submission_id>/ceac-status", methods=["POST"])
@admin_required
def ds260_ceac_status(submission_id):
    """The CEAC status is recorded by staff only. It is separate from OG's status and OG cannot read or change CEAC."""
    _csrf()
    submission = _ds260_or_404(submission_id)
    row = consular.ds260_row(submission)
    status = request.form.get("ceac_status", "")
    if status not in CEAC_STATUS_LABELS:
        flash("Choose one of the CEAC statuses.", "error")
        return _back(submission)
    before = row.ceac_status
    row.ceac_status, row.ceac_status_at, row.ceac_status_by = status, datetime.utcnow(), _staff()
    note = (request.form.get("ceac_note") or "").strip()
    row.ceac_note = note[:2000] or row.ceac_note
    db.session.commit()
    if submission.student_id and before != status:
        log_event(submission.student_id, "ds260_ceac_status", actor="admin", entity=("submission", submission.id),
                  meta={"status_label": CEAC_STATUS_LABELS[status], "service": _title(submission)})
    flash("CEAC status recorded (it is a note by staff, not something OG can read from CEAC).", "success")
    if status == "submitted":
        flash(AFTER_SUBMIT_WARNING, "error")
    return _back(submission)


@admin_bp.route("/ds260/<int:submission_id>/override", methods=["POST"])
@admin_required
def ds260_override(submission_id):
    """A staff-approved English value for ONE CEAC answer (for example the English version of free text the customer wrote in Spanish)."""
    _csrf()
    submission = _ds260_or_404(submission_id)
    row = consular.ds260_row(submission)
    key = request.form.get("key", "")
    valid = {r["key"] for s in ds260_ceac.build(submission)["sections"] for r in s["rows"]}
    if key not in valid:
        abort(400)
    if request.form.get("action") == "clear":
        ds260_ceac.clear_override(submission, key)
        flash("Override removed.", "success")
    else:
        value, changed = ds260_ceac.fold(request.form.get("value", "").strip()[:3000])
        if not value:
            flash("Enter the English text.", "error")
        else:
            ds260_ceac.set_override(submission, key, value, _staff())
            flash("English value saved" + (" (accents and special characters were converted to English characters)." if changed else "."), "success")
    if row.ceac_status == "submitted":
        flash(AFTER_SUBMIT_WARNING, "error")
    return redirect(url_for("admin.ds260_prep", submission_id=submission.id) + "#row-" + key.replace("#", "_").replace(".", "_"))


@admin_bp.route("/ds260/<int:submission_id>/case-data", methods=["POST"])
@admin_required
def ds260_case_data(submission_id):
    """Consular case data (NVC case number, invoice ID, post, visa class...). Sensitive values are never logged or put in a URL."""
    _csrf()
    submission = _ds260_or_404(submission_id)
    case = submission.case
    if case is None:
        abort(404)
    cd = consular.case_data(case, create=True)
    nvc, inv = (request.form.get("nvc_case_number") or "").strip(), (request.form.get("invoice_id") or "").strip()
    if not (consular._SAFE.match(nvc) and consular._SAFE.match(inv)):
        flash(consular.ERRORS["credentials"][0], "error")
        return _back(submission, "admin.form_submission_detail")
    if nvc:
        cd.nvc_case_number = nvc
    if inv:
        cd.invoice_id = inv
    for name, limit in (("post", 120), ("country", 80), ("nvc_status", 120)):
        value = (request.form.get(name) or "").strip()[:limit]
        if value or request.form.get(name) is not None and request.form.get(name) == "":
            setattr(cd, name, value or None)
    cd.visa_class = ((request.form.get("visa_class") or "").strip().upper()[:20]) or cd.visa_class
    for name in ("priority_date", "dq_date", "interview_date"):
        raw = (request.form.get(name) or "").strip()
        if raw:
            parsed, ok = consular._date(raw)
            if not ok:
                flash(consular.ERRORS["date"][0], "error")
                return _back(submission, "admin.form_submission_detail")
            setattr(cd, name, parsed)
    db.session.commit()
    if submission.student_id:
        log_event(submission.student_id, "ds260_case_data_updated", actor="admin", entity=("case", case.id), meta={"service": _title(submission)})
    flash("Consular case data updated.", "success")
    return _back(submission, "admin.form_submission_detail")


@admin_bp.route("/ds260/snapshots")
@admin_required
def ds260_snapshots():
    from app import ds260_source
    from app.models import Ds260Source

    rows = Ds260Source.query.order_by(Ds260Source.id.desc()).all()
    diffs = [(rows[i + 1], rows[i], ds260_source.diff(rows[i + 1], rows[i])) for i in range(len(rows) - 1)]
    counts = dict(db.session.query(consular.Ds260Application.source_id, db.func.count(consular.Ds260Application.id)).group_by(consular.Ds260Application.source_id).all())
    return render_template("admin/ds260_snapshots.html", rows=rows, diffs=diffs, counts=counts)
