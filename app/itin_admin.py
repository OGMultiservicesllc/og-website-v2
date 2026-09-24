"""Staff actions and readiness for the ITIN case. Every action is EXPLICIT and recorded (who, when); nothing here talks to the IRS and nothing infers an IRS outcome.

  * "Ready for IRS" means OG's package is complete and staff believe it can be mailed. It is never a submission.
  * A physical original is only "received" when staff record it; a digital upload never moves it.
  * CAA verification is a staff action that records who, when and which document version was verified.
  * IRS processing is never inferred from USPS delivery; staff record the stage and the IRS response.
"""

from datetime import date, datetime

from app import itin
from app import persons as pers
from app import w7_calc
from app import w7_docs as D
from app.extensions import db
from app.models.itin import ITIN_STAGES, ORIGINAL_STATES

OPTIONAL_KEYS = ("w7.income_records",)  # OG can prepare the package without them; they show as warnings, not blockers
STAFF_STAGES = ("intake_started", "waiting_docs", "waiting_originals", "ready_review", "og_reviewing", "tax_preparation", "ready_signature")
SIGNATURE_STATES = (("not_started", "Not started"), ("needs_signature", "Needs the applicant's signature"), ("signed_recorded", "Signed (recorded by staff)"))
DONE_ORIGINAL = ("received", "caa_verified", "ready_to_return", "returned")
VERIFIED = ("caa_verified", "ready_to_return", "returned")
STAFF_ORIGINAL_STATES = tuple(k for k, _e, _s in ORIGINAL_STATES if k not in ("caa_verified",))


def _parse(text):
    try:
        return datetime.strptime((text or "").strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _log(case, event, staff, meta=None, entity=None):
    itin.log_case_event(case.customer_id, event, case, meta, entity=entity, actor="admin")


# ------------------------------------------------------------------ readiness
def app_blockers(submission):
    """[str] — what still stops THIS applicant's W-7 from being ready."""
    out = []
    w = submission.w7
    a = D.case_svc.answers_by_name(submission)
    name = (a.get("a_given", "") + " " + a.get("a_family", "")).strip() or submission.code
    if not submission.is_complete:
        out.append(f"{name}: the application has not been sent to OG yet")
    st = D.passport_state(submission)
    if st["applies"]:
        if not st["uploaded"]:
            out.append(f"{name}: passport not uploaded")
        elif not st["confirmed"]:
            out.append(f"{name}: passport information not confirmed by the customer")
    else:
        cov = D.coverage_for(submission, planned=False)
        if not cov["ok"]:
            out.append(f"{name}: identification documents do not yet cover identity, foreign status, photo or residency")
    if w is None or not w.reason_confirmed:
        out.append(f"{name}: W-7 reason not confirmed by staff")
    if w is None or w.signature_state != "signed_recorded":
        out.append(f"{name}: W-7 signature not recorded")
    if w is None or w.caa_status != "verified":
        out.append(f"{name}: CAA review not recorded")
    cp = D.case_svc.role_person(submission, "itin_applicant")
    if cp is not None and pers.open_conflicts(person=pers.owner_of(cp)):
        out.append(f"{name}: unresolved differences in this person's information")
    return out


def readiness(case):
    blockers, warnings = [], []
    cd = case.itin_data
    if cd is None or not cd.tax_year:
        blockers.append("Tax year not set")
    apps = itin.applicants(case)
    if not apps:
        blockers.append("No W-7 applications in the case")
    for x in apps:
        blockers += app_blockers(x["submission"])
    for r in case.requirements:
        if r.withdrawn_at is not None:
            continue
        if r.status in ("needed", "requested", "needs_replacement") and r.rule_key in OPTIONAL_KEYS:
            warnings.append(f"Optional document not received: {r.title}" + (f" ({r.person.full_name})" if r.person else ""))
        elif r.status in ("needed", "requested", "needs_replacement"):
            blockers.append(f"Document missing: {r.title}" + (f" ({r.person.full_name})" if r.person else ""))
        elif r.status in ("uploaded", "under_review"):
            warnings.append(f"Not yet accepted: {r.title}" + (f" ({r.person.full_name})" if r.person else ""))
        t = getattr(r, "itin_track", None)
        if t is not None and t.original_required:
            who = f" ({r.person.full_name})" if r.person else ""
            if t.original_state not in DONE_ORIGINAL:
                blockers.append(f"Original not received: {r.title}{who}")
            elif t.caa_route == "caa" and t.original_state not in VERIFIED:
                blockers.append(f"Original received but not CAA verified: {r.title}{who}")
            elif t.caa_route == "caa" and r.current_document is not None and t.caa_document_id not in (None, r.current_document.id):
                blockers.append(f"CAA verification was recorded for an earlier version of: {r.title}{who}")
    return {"blockers": blockers, "warnings": warnings, "ok": not blockers}


# ------------------------------------------------------------------ actions
def set_stage(case, key, staff):
    if key not in STAFF_STAGES and key != "auto":
        return False, "Choose a stage from the list."
    cd = itin.case_data(case, create=True)
    before = itin.stage_of(case)
    cd.stage = None if key == "auto" else key
    db.session.commit()
    after = itin.stage_of(case)
    if after != before:
        _log(case, "itin_stage_changed", staff, {"from_label": itin.stage_label(before), "to_label": itin.stage_label(after)})
    return True, None


def mark_ready_for_irs(case, staff):
    r = readiness(case)
    if r["blockers"]:
        return False, r
    cd = itin.case_data(case, create=True)
    cd.stage, cd.ready_for_irs_at, cd.ready_for_irs_by = "ready_irs", datetime.utcnow(), staff
    db.session.commit()
    _log(case, "itin_ready_for_irs", staff)
    return True, r


def unmark_ready_for_irs(case, staff):
    cd = itin.case_data(case, create=True)
    if cd.stage == "ready_irs":
        cd.stage = None
    cd.ready_for_irs_at = cd.ready_for_irs_by = None
    db.session.commit()
    _log(case, "itin_stage_changed", staff, {"from_label": itin.stage_label("ready_irs"), "to_label": itin.stage_label(itin.stage_of(case))})


def record_package(case, tracking, mailed, delivered, mailing_status, staff):
    cd = itin.case_data(case, create=True)
    if cd.ready_for_irs_at is None:
        return False, "Mark the case Ready for IRS first."
    tracking = "".join(ch for ch in (tracking or "") if ch.isalnum())[:40]
    mailed_d = _parse(mailed)
    if not tracking and mailed_d is None and not (cd.usps_tracking or cd.irs_mailed_date):
        return False, "Enter the USPS tracking number or the date it was mailed."
    if mailed and mailed_d is None:
        return False, "Enter a valid mailed date."
    cd.usps_tracking = tracking or cd.usps_tracking
    cd.irs_mailed_date = mailed_d or cd.irs_mailed_date
    cd.irs_delivered_date = _parse(delivered) or cd.irs_delivered_date
    cd.irs_mailing_status = ((mailing_status or "").strip()[:120]) or cd.irs_mailing_status
    if cd.stage in (None, "ready_irs"):
        cd.stage = "sent_irs"
    db.session.commit()
    _log(case, "itin_package_sent", staff)
    return True, None


def set_processing(case, staff):
    """Staff say the package is now with the IRS for processing. Never inferred from USPS delivery."""
    cd = itin.case_data(case, create=True)
    if cd.stage not in ("sent_irs", "irs_processing"):
        return False, "Record that the package was sent first."
    cd.stage = "irs_processing"
    db.session.commit()
    _log(case, "itin_stage_changed", staff, {"from_label": itin.stage_label("sent_irs"), "to_label": itin.stage_label("irs_processing")})
    return True, None


def record_response(case, outcome, when, note, staff):
    if outcome not in itin.IRS_OUTCOMES:
        return False, "Choose what the IRS sent (ITIN issued, IRS notice or other)."
    cd = itin.case_data(case, create=True)
    cd.irs_outcome, cd.irs_outcome_at, cd.irs_note = outcome, _parse(when) or date.today(), ((note or "").strip()[:2000]) or None
    cd.stage = "irs_response"
    db.session.commit()
    _log(case, "itin_irs_response", staff, {"outcome": itin.IRS_OUTCOMES[outcome][0]})
    return True, None


def complete_case(case, staff):
    cd = itin.case_data(case, create=True)
    if cd.irs_outcome is None:
        return False, "Record the IRS response first."
    cd.stage = "completed"
    db.session.commit()
    _log(case, "itin_stage_changed", staff, {"from_label": itin.stage_label("irs_response"), "to_label": itin.stage_label("completed")})
    return True, None


def confirm_reason(submission, letter, note, staff):
    from app.w7_calc import REASONS

    if letter not in {k for k, _l in REASONS}:
        return False, "Choose the W-7 reason (a to h)."
    w = itin.w7_row(submission)
    a = D.case_svc.answers_by_name(submission)
    _fl, cand = w7_calc.flags(a, submission)
    w.reason_candidate = cand
    w.reason_confirmed, w.reason_confirmed_by, w.reason_confirmed_at = letter, staff, datetime.utcnow()
    w.reason_note = ((note or "").strip()[:1000]) or None
    db.session.commit()
    if submission.case is not None:
        _log(submission.case, "itin_reason_confirmed", staff, {"application": submission.code}, entity=("submission", submission.id))
    return True, None


def set_signature(submission, state, note, staff):
    if state not in {k for k, _l in SIGNATURE_STATES}:
        return False, "Choose a signature status."
    w = itin.w7_row(submission)
    w.signature_state, w.signature_note = state, ((note or "").strip()[:200]) or None
    db.session.commit()
    if submission.case is not None:
        _log(submission.case, "itin_signature_recorded", staff, {"application": submission.code, "state": dict(SIGNATURE_STATES)[state]}, entity=("submission", submission.id))
    return True, None


def record_original(req, form, staff):
    """Update the physical-original tracking of one requirement (mail / in person, inbound tracking, received, returned)."""
    t = getattr(req, "itin_track", None)
    if t is None or not t.original_required:
        return False, "This document does not need an original."
    state = form.get("state", "")
    if state not in STAFF_ORIGINAL_STATES:
        return False, "Choose a status from the list. CAA verification has its own button."
    if state in ("ready_to_return", "returned") and t.original_state not in ("received", "caa_verified", "ready_to_return", "returned"):
        return False, "The original must be received first."
    if state in ("required", "will_mail", "will_bring", "in_transit") and t.original_state in VERIFIED:
        return False, "This original was already verified; it cannot go back to “not received”."
    t.delivery_choice = form.get("delivery") if form.get("delivery") in ("mail", "in_person") else t.delivery_choice
    t.mailed_date = _parse(form.get("mailed_date")) or t.mailed_date
    t.inbound_tracking = ("".join(ch for ch in (form.get("inbound_tracking") or "") if ch.isalnum())[:40]) or t.inbound_tracking
    if state == "received":
        t.received_date = _parse(form.get("received_date")) or t.received_date or date.today()
        t.received_by = staff
    if state in ("ready_to_return", "returned") or form.get("return_method"):
        t.return_method = ((form.get("return_method") or "").strip()[:20]) or t.return_method
        t.returned_date = _parse(form.get("returned_date")) or (date.today() if state == "returned" else t.returned_date)
        t.outbound_tracking = ("".join(ch for ch in (form.get("outbound_tracking") or "") if ch.isalnum())[:40]) or t.outbound_tracking
    t.original_state = state
    db.session.commit()
    _log(req.case, "itin_original_updated", staff, {"state": dict((k, e) for k, e, _s in ORIGINAL_STATES)[state], "title": req.title})
    return True, None


def verify_original(req, staff):
    """CAA verification: only an explicit staff action, only for a document OG can certify, only after the original is in OG's hands."""
    t = getattr(req, "itin_track", None)
    if t is None or not t.original_required:
        return False, "This document does not need an original."
    if t.caa_route != "caa":
        return False, "OG cannot certify this document (as a Certifying Acceptance Agent); the original goes to the IRS with the package."
    if t.original_state != "received":
        return False, "Record that OG received the original first."
    if req.current_document is None:
        return False, "There is no uploaded copy to attach this verification to."
    t.caa_verified_by, t.caa_verified_at, t.caa_document_id, t.original_state = staff, datetime.utcnow(), req.current_document.id, "caa_verified"
    db.session.commit()
    _log(req.case, "itin_caa_verified", staff, {"title": req.title})
    return True, None


def caa_review(submission, staff, note=None):
    """The applicant's CAA review is complete: allowed only when every document OG can certify has been verified."""
    w = itin.w7_row(submission)
    pending = [r.title for r in D.requirements_of(submission) if r.itin_track is not None and r.itin_track.original_required and r.itin_track.caa_route == "caa" and r.itin_track.original_state not in VERIFIED]
    if pending:
        return False, "Still to verify: " + ", ".join(pending)
    w.caa_status, w.caa_verified_by, w.caa_verified_at, w.caa_note = "verified", staff, datetime.utcnow(), ((note or "").strip()[:300]) or None
    db.session.commit()
    if submission.case is not None:
        _log(submission.case, "itin_caa_verified", staff, {"title": "CAA review of " + submission.code}, entity=("submission", submission.id))
    return True, None


def staff_read_passport(submission, mrz_text, typed, staff):
    """OG staff enter what the uploaded passport page shows (a pasted MRZ, or typed values). It becomes a PENDING reading: the customer still confirms."""
    from app import w7_passport as PP

    values = {}
    if (mrz_text or "").strip():
        parsed = PP.parse_mrz(mrz_text)
        if not parsed["values"]:
            return False, " ".join(parsed["errors"]) or "The MRZ could not be read."
        values = dict(parsed["values"])
        warn = " ".join(parsed["errors"])
    else:
        warn = ""
        for k in ("family", "given", "middle", "dob", "sex", "birth_city", "birth_country", "nationality", "pp_number", "pp_country", "pp_issued", "pp_expiry"):
            v = (typed.get(k) or "").strip()
            if v:
                values[k] = v
        if not values:
            return False, "Paste the two MRZ lines or type at least one value."
    req = D.passport_requirement(submission)
    doc = req.current_document if req is not None else None
    PP.add_extraction(submission, doc, "staff_read", values)
    if submission.case is not None:
        _log(submission.case, "w7_passport_read", staff, {"application": submission.code}, entity=("submission", submission.id))
    w7_calc.write(submission.form, submission)
    db.session.commit()
    return True, warn or None
