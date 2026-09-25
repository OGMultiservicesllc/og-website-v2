"""Admin side of the ITIN / W-7 workflow: the ITIN Case view, the W-7 Preparation View and the explicit staff actions (reason, signature status, CAA verification, original
documents, Ready for IRS, package tracking, IRS response). Nothing here talks to the IRS; OG Multiservices does not approve or deny ITIN applications.
"""

from flask import abort, flash, redirect, render_template, request, session, url_for

from app import itin, itin_admin
from app import w7_calc, w7_docs, w7_map
from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.models import Case, FormSubmission
from app.models.itin import ITIN_STAGES, ORIGINAL_STATES


def _staff():
    return session.get("admin_name") or session.get("admin_email") or "OG team"


def _csrf():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)


def _case_or_404(case_id):
    case = db.session.get(Case, case_id)
    if case is None or case.case_type != "itin_application":
        abort(404)
    return case


def _w7_or_404(submission_id):
    sub = db.session.get(FormSubmission, submission_id)
    if sub is None or sub.form.source_form_name != "W-7" or sub.case is None:
        abort(404)
    return sub


def _done(result, ok_msg, back):
    ok, info = result
    if ok:
        flash(ok_msg + (f" {info}" if isinstance(info, str) else ""), "success")
    else:
        flash(info if isinstance(info, str) else "Not done.", "error")
    return redirect(back)


@admin_bp.route("/itin")
@admin_required
def itin_list():
    cases = Case.query.filter_by(case_type="itin_application").order_by(Case.updated_at.desc()).all()
    rows = []
    for c in cases:
        apps = itin.applicants(c)
        got, total = itin.doc_counts(c)
        rows.append({"case": c, "stage": itin.stage_label(itin.stage_of(c)), "apps": len(apps), "docs": f"{got}/{total}", "originals": len(itin.pending_originals(c)),
                     "year": c.itin_data.tax_year if c.itin_data else None})
    return render_template("admin/itin_list.html", rows=rows)


@admin_bp.route("/itin/<int:case_id>")
@admin_required
def itin_case(case_id):
    from app import itin_pricing

    case = _case_or_404(case_id)
    cd = itin.case_data(case, create=True)
    apps = []
    for x in itin.applicants(case):
        s = x["submission"]
        a = w7_docs.case_svc.answers_by_name(s)
        fl, cand = w7_calc.flags(a, s)
        apps.append({**x, "flags": fl, "candidate": cand, "candidate_label": w7_calc.REASON_LABEL.get(cand, ("", ""))[0], "passport": w7_docs.passport_state(s), "coverage": w7_docs.coverage_for(s, planned=True),
                     "reqs": w7_docs.requirements_of(s), "kind_label": itin.kind_label(x["kind"]), "name": x["person"].full_name if x["person"] else s.code})
    ready = itin_admin.readiness(case)
    est = itin_pricing.estimate(case)
    confirmed = next((q for q in reversed(cd.quotes) if q.status == "confirmed"), None)
    return render_template("admin/itin_case.html", case=case, cd=cd, apps=apps, ready=ready, stage=itin.stage_of(case), stage_label=itin.stage_label(itin.stage_of(case)),
                           stages=[(k, en) for k, en, _es in ITIN_STAGES if k in itin_admin.STAFF_STAGES], all_stages=ITIN_STAGES, original_states=[(k, en) for k, en, _es in ORIGINAL_STATES if k != "caa_verified"],
                           original_labels={k: en for k, en, _es in ORIGINAL_STATES}, signature_states=itin_admin.SIGNATURE_STATES, reasons=w7_calc.REASONS, outcomes=itin.IRS_OUTCOMES,
                           usps_url=itin.usps_url(cd.usps_tracking), verified=itin_admin.VERIFIED, est=est, confirmed=confirmed, quotes=list(reversed(cd.quotes)), fmt=itin_pricing.fmt)


@admin_bp.route("/w7/<int:submission_id>")
@admin_required
def w7_prep(submission_id):
    sub = _w7_or_404(submission_id)
    data = w7_map.build(sub, reveal=True)
    a = w7_docs.case_svc.answers_by_name(sub)
    return render_template("admin/w7_prep.html", submission=sub, data=data, reasons=w7_calc.REASONS, coverage=w7_docs.coverage_for(sub, planned=True), passport=w7_docs.passport_state(sub),
                           person=w7_docs.case_svc.role_person(sub, "itin_applicant"), status_text=w7_map.STATUS_TEXT, w=sub.w7, answers_pp=a.get("pp_status"),
                           signature_states=itin_admin.SIGNATURE_STATES, blockers=itin_admin.app_blockers(sub))


def _back(case, anchor=""):
    return redirect(url_for("admin.itin_case", case_id=case.id) + anchor)


# ---------------------------------------------------------------- Admin -> ITIN -> Pricing (Admin-editable, same pattern as Driver License / Tax pricing)
@admin_bp.route("/itin/pricing")
@admin_required
def itin_pricing_page():
    from app import itin_pricing
    from app.models import ItinPriceRule

    itin_pricing.ensure_seed()
    rules = ItinPriceRule.query.order_by(ItinPriceRule.sort_order, ItinPriceRule.id).all()
    return render_template("admin/itin_pricing.html", rules=rules, fmt=itin_pricing.fmt)


@admin_bp.route("/itin/pricing", methods=["POST"])
@admin_required
def itin_pricing_save():
    from app.models import ItinPriceRule

    _csrf()
    changed = []
    for rule in ItinPriceRule.query.all():
        key = f"r{rule.id}"
        if f"{key}__present" not in request.form:
            continue
        before = (rule.amount_cents, rule.active)
        text = (request.form.get(f"{key}__amount") or "").replace("$", "").replace(",", "").strip()
        try:
            cents = int(round(float(text) * 100)) if text else None
        except ValueError:
            cents = rule.amount_cents
        if cents is not None and 0 <= cents <= 10_000_000:
            rule.amount_cents = cents
        rule.active = bool(request.form.get(f"{key}__active"))
        if before != (rule.amount_cents, rule.active):
            rule.updated_by = _staff()
            changed.append(rule.label_en)
    db.session.commit()
    flash(f"{len(changed)} price setting(s) updated." if changed else "Nothing changed.", "success")
    return redirect(url_for("admin.itin_pricing_page"))


# ---------------------------------------------------------------- pricing / payment (OG Payments, Model C)
@admin_bp.route("/itin/<int:case_id>/price", methods=["POST"])
@admin_required
def itin_price(case_id):
    """Same estimate -> confirm -> revision-history flow as Tax/DL pricing — the total is always derived from
    the real applicants in the case (`itin.applicants`), never typed in blind."""
    from app import itin_pricing

    _csrf()
    case = _case_or_404(case_id)
    action = request.form.get("action")
    if action == "recalc":
        itin_pricing.snapshot(case, staff=_staff())
        db.session.commit()
        flash("Estimate recalculated.", "success")
        return _back(case, "#price")
    text = (request.form.get("fee") or "").replace("$", "").replace(",", "").strip()
    try:
        cents = int(round(float(text) * 100))
    except ValueError:
        flash("Enter the price.", "error")
        return _back(case, "#price")
    itin_pricing.snapshot(case)
    db.session.flush()
    before = next((q for q in reversed(itin.case_data(case).quotes) if q.status == "confirmed"), None)
    try:
        quote = itin_pricing.confirm(case, cents, _staff(), request.form.get("reason"))
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return _back(case, "#price")
    itin.log_case_event(case.customer_id, "itin_price_confirmed", case, {"fee": itin_pricing.fmt(cents), "previous": itin_pricing.fmt(before.final_total_cents) if before else None, "reason": quote.reason}, actor="admin")
    flash("Price confirmed.", "success")
    return _back(case, "#price")


@admin_bp.route("/itin/<int:case_id>/request-payment", methods=["POST"])
@admin_required
def itin_request_payment(case_id):
    """Model C (OG Payments): the intake's own estimate is never requestable — only a CONFIRMED price, read
    straight from the SAME `final_total_cents` this module already tracks, syncs into the OG Payments Charge."""
    from app import itin_pricing
    from app import payments as pay_svc

    _csrf()
    case = _case_or_404(case_id)
    cd = itin.case_data(case)
    confirmed = next((q for q in reversed(cd.quotes) if q.status == "confirmed"), None) if cd else None
    if confirmed is None or confirmed.final_total_cents is None:
        flash("Confirm the price before requesting payment.", "error")
        return _back(case, "#price")
    description = "ITIN Application Preparation"
    charge = next((c for c in case.charges if c.description == description and not c.is_canceled), None)
    if charge is None:
        charge = pay_svc.create_charge(case.customer, description=description, case=case,
                                       total_cents=confirmed.final_total_cents, price_mode="final", admin_id=session.get("admin_user_id"))
    elif charge.total_cents != confirmed.final_total_cents:
        pay_svc.set_price(charge, confirmed.final_total_cents, admin_id=session.get("admin_user_id"), mode="final", reason="Synced from the confirmed ITIN price.")
    bal = pay_svc.balance_cents(charge)
    if not bal:
        flash("This charge is already fully paid.", "error")
        return _back(case, "#price")
    try:
        pay_svc.request_payment(charge, bal, admin_id=session.get("admin_user_id"))
    except ValueError as exc:
        flash(str(exc), "error")
        return _back(case, "#price")
    flash("Payment requested — the customer will see this in My Account > Payments.", "success")
    return _back(case, "#price")


# ---------------------------------------------------------------- case-level actions
@admin_bp.route("/itin/<int:case_id>/tax", methods=["POST"])
@admin_required
def itin_tax(case_id):
    _csrf()
    case = _case_or_404(case_id)
    cd = itin.case_data(case, create=True)
    try:
        year = int(request.form.get("tax_year", ""))
    except ValueError:
        year = 0
    if not 2000 < year <= itin.date.today().year:
        flash("Enter a valid tax year.", "error")
        return redirect(url_for("admin.itin_case", case_id=case.id))
    cd.tax_year = year
    if request.form.get("request_kind") in ("new", "renew", "unsure"):
        cd.request_kind = request.form.get("request_kind")
    if request.form.get("taxpayer_us_status") in ("yes", "no", "unsure"):
        cd.taxpayer_us_status = request.form.get("taxpayer_us_status")
    db.session.commit()
    for x in itin.applicants(case):
        w7_calc.write(x["submission"].form, x["submission"])
    db.session.commit()
    flash("Tax information updated.", "success")
    return redirect(url_for("admin.itin_case", case_id=case.id))


@admin_bp.route("/itin/<int:case_id>/stage", methods=["POST"])
@admin_required
def itin_stage(case_id):
    _csrf()
    case = _case_or_404(case_id)
    return _done(itin_admin.set_stage(case, request.form.get("stage", ""), _staff()), "Status updated.", url_for("admin.itin_case", case_id=case.id))


@admin_bp.route("/itin/<int:case_id>/ready", methods=["POST"])
@admin_required
def itin_ready(case_id):
    _csrf()
    case = _case_or_404(case_id)
    ok, r = itin_admin.mark_ready_for_irs(case, _staff())
    if ok:
        flash("Marked Ready for IRS. This is not a submission: the package still has to be prepared and mailed by staff.", "success")
    else:
        flash("Not ready yet: " + "; ".join(r["blockers"][:12]) + ("…" if len(r["blockers"]) > 12 else ""), "error")
    return redirect(url_for("admin.itin_case", case_id=case.id))


@admin_bp.route("/itin/<int:case_id>/not-ready", methods=["POST"])
@admin_required
def itin_not_ready(case_id):
    _csrf()
    case = _case_or_404(case_id)
    itin_admin.unmark_ready_for_irs(case, _staff())
    flash("Ready for IRS removed.", "success")
    return redirect(url_for("admin.itin_case", case_id=case.id))


@admin_bp.route("/itin/<int:case_id>/package", methods=["POST"])
@admin_required
def itin_package(case_id):
    _csrf()
    case = _case_or_404(case_id)
    f = request.form
    return _done(itin_admin.record_package(case, f.get("tracking"), f.get("mailed"), f.get("delivered"), f.get("mailing_status"), _staff()), "Package details recorded.", url_for("admin.itin_case", case_id=case.id))


@admin_bp.route("/itin/<int:case_id>/processing", methods=["POST"])
@admin_required
def itin_processing(case_id):
    _csrf()
    case = _case_or_404(case_id)
    return _done(itin_admin.set_processing(case, _staff()), "Status set to IRS Processing.", url_for("admin.itin_case", case_id=case.id))


@admin_bp.route("/itin/<int:case_id>/response", methods=["POST"])
@admin_required
def itin_response(case_id):
    _csrf()
    case = _case_or_404(case_id)
    f = request.form
    return _done(itin_admin.record_response(case, f.get("outcome"), f.get("when"), f.get("note"), _staff()), "IRS response recorded (by staff; never inferred).", url_for("admin.itin_case", case_id=case.id))


@admin_bp.route("/itin/<int:case_id>/complete", methods=["POST"])
@admin_required
def itin_complete(case_id):
    _csrf()
    case = _case_or_404(case_id)
    return _done(itin_admin.complete_case(case, _staff()), "Case marked Completed.", url_for("admin.itin_case", case_id=case.id))


# ---------------------------------------------------------------- application-level actions
@admin_bp.route("/w7/<int:submission_id>/reason", methods=["POST"])
@admin_required
def w7_reason(submission_id):
    _csrf()
    sub = _w7_or_404(submission_id)
    return _done(itin_admin.confirm_reason(sub, request.form.get("reason", ""), request.form.get("note"), _staff()), "W-7 reason confirmed by staff.", url_for("admin.w7_prep", submission_id=sub.id))


@admin_bp.route("/w7/<int:submission_id>/signature", methods=["POST"])
@admin_required
def w7_signature(submission_id):
    _csrf()
    sub = _w7_or_404(submission_id)
    return _done(itin_admin.set_signature(sub, request.form.get("state", ""), request.form.get("note"), _staff()), "Signature status recorded.", url_for("admin.w7_prep", submission_id=sub.id))


@admin_bp.route("/w7/<int:submission_id>/caa", methods=["POST"])
@admin_required
def w7_caa(submission_id):
    _csrf()
    sub = _w7_or_404(submission_id)
    return _done(itin_admin.caa_review(sub, _staff(), request.form.get("note")), "CAA review recorded.", url_for("admin.w7_prep", submission_id=sub.id))


@admin_bp.route("/w7/<int:submission_id>/passport-read", methods=["POST"])
@admin_required
def w7_passport_read(submission_id):
    """OG staff read the uploaded passport page (paste the MRZ or type the values). The customer still has to confirm before anything is used."""
    _csrf()
    sub = _w7_or_404(submission_id)
    typed = {k: request.form.get(k, "") for k in ("family", "given", "middle", "dob", "sex", "birth_city", "birth_country", "nationality", "pp_number", "pp_country", "pp_issued", "pp_expiry")}
    return _done(itin_admin.staff_read_passport(sub, request.form.get("mrz", ""), typed, _staff()), "Passport reading saved. The customer will be asked to confirm it.", url_for("admin.w7_prep", submission_id=sub.id))


@admin_bp.route("/itin/<int:case_id>/original/<int:requirement_id>", methods=["POST"])
@admin_required
def itin_original(case_id, requirement_id):
    _csrf()
    case = _case_or_404(case_id)
    from app.models import DocumentRequirement

    req = DocumentRequirement.query.filter_by(id=requirement_id, case_id=case.id).first_or_404()
    back = url_for("admin.itin_case", case_id=case.id) + f"#req-{req.id}"
    if request.form.get("action") == "verify":
        return _done(itin_admin.verify_original(req, _staff()), "CAA verification recorded.", back)
    return _done(itin_admin.record_original(req, request.form, _staff()), "Original tracking updated.", back)
