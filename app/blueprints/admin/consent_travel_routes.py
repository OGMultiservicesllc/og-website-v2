"""Admin side of Consent to Travel Authorization: the case list, the case view, staff actions (status, request
information, reopen, review the auto-computed document grouping, APPROVE which confirms the price and is the
ONLY thing that unlocks a payment request), and Consent to Travel -> Pricing (the two data-driven amounts)."""

from flask import abort, flash, redirect, render_template, request, session, url_for

from app import cases as case_svc
from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.consent_travel import docs, people, pricing, service, summary
from app.extensions import db
from app.models import CT_STATUS_EN, CT_STATUSES, Case, CaseNote, ConsentTravelPriceRule

STAFF_STATUSES = [(k, en) for k, en, _es in CT_STATUSES if k not in ("draft",)]


def _staff():
    return session.get("admin_name") or session.get("admin_email") or "OG team"


def _csrf():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)


def _ct_or_404(case_id):
    case = db.session.get(Case, case_id)
    if case is None or case.case_type != "consent_travel" or case.consent_travel_data is None:
        abort(404)
    return case.consent_travel_data


def _back(ct, anchor=""):
    return redirect(url_for("admin.ct_case", case_id=ct.case_id) + anchor)


def _cents(text):
    text = (text or "").replace("$", "").replace(",", "").strip()
    if not text:
        return None
    try:
        return int(round(float(text) * 100))
    except ValueError:
        return None


@admin_bp.route("/consent-travel")
@admin_required
def ct_list():
    from app.models import ConsentTravelCaseData

    query = ConsentTravelCaseData.query.join(Case, Case.id == ConsentTravelCaseData.case_id)
    status = request.args.get("status", "")
    if status in CT_STATUS_EN:
        query = query.filter(ConsentTravelCaseData.status == status)
    rows = []
    for ct in query.order_by(ConsentTravelCaseData.updated_at.desc()).limit(300).all():
        have, total, missing = docs.counts(ct)
        quote = ct.current_quote
        rows.append({"ct": ct, "case": ct.case, "docs": f"{have}/{total}", "missing": missing, "children": len(ct.children),
                     "price": pricing.fmt(quote.final_total_cents) if ct.price_status == "confirmed" and quote else None})
    return render_template("admin/consent_travel_list.html", rows=rows, statuses=STAFF_STATUSES + [("draft", "Draft")], status=status)


@admin_bp.route("/consent-travel/<int:case_id>")
@admin_required
def ct_case(case_id):
    ct = _ct_or_404(case_id)
    groups = service.groups_for(ct)
    est = pricing.estimate(ct, groups)
    confirmed = next((q for q in reversed(ct.quotes) if q.status == "confirmed"), None)
    data = summary.admin_summary(ct)
    reqs = []
    from app import case_documents as vault

    for r in sorted(docs.requirements(ct), key=lambda x: (x.status in ("accepted",), x.id)):
        title, _msg = docs.req_text(r, "en")
        reqs.append({"r": r, "title": title, "status": vault.status_label(r.status, "en"), "choice": ct.doc_choices.get(r.rule_key), "doc": r.current_document})
    have, total, missing = docs.counts(ct)
    notes = CaseNote.query.filter_by(case_id=ct.case_id).order_by(CaseNote.id.desc()).all()
    events = case_svc.case_timeline(ct.case, 60)
    return render_template("admin/consent_travel_case.html", ct=ct, case=ct.case, data=data, est=est, groups=groups, confirmed=confirmed, reqs=reqs,
                           docs_have=have, docs_total=total, docs_missing=missing, notes=notes, events=events, statuses=STAFF_STATUSES, fmt=pricing.fmt,
                           quotes=list(reversed(ct.quotes)), status_label=CT_STATUS_EN.get(ct.status, ct.status))


@admin_bp.route("/consent-travel/<int:case_id>/status", methods=["POST"])
@admin_required
def ct_status(case_id):
    _csrf()
    ct = _ct_or_404(case_id)
    ok, err = service.set_status(ct, request.form.get("status", ""), _staff(), message=request.form.get("message"))
    flash("Status updated." if ok else (err or "Not done."), "success" if ok else "error")
    return _back(ct)


@admin_bp.route("/consent-travel/<int:case_id>/request-info", methods=["POST"])
@admin_required
def ct_request_info(case_id):
    _csrf()
    ct = _ct_or_404(case_id)
    ok, err = service.request_info(ct, request.form.get("message", ""), _staff())
    flash("The customer will see your message in My Account." if ok else err, "success" if ok else "error")
    return _back(ct)


@admin_bp.route("/consent-travel/<int:case_id>/reopen", methods=["POST"])
@admin_required
def ct_reopen(case_id):
    _csrf()
    ct = _ct_or_404(case_id)
    ok, err = service.reopen(ct, request.form.get("message", ""), _staff(), actor_id=session.get("admin_user_id"))
    flash("Reopened. The customer can edit and send again." if ok else err, "success" if ok else "error")
    return _back(ct)


@admin_bp.route("/consent-travel/<int:case_id>/approve", methods=["POST"])
@admin_required
def ct_approve(case_id):
    """The ONLY action that confirms a price and unlocks a payment request (item: "Solamente después de
    aprobación de OG se crea/habilita el PaymentRequest")."""
    _csrf()
    ct = _ct_or_404(case_id)
    action = request.form.get("action")
    groups = service.groups_for(ct)
    if action == "recalc":
        pricing.snapshot(ct, groups)
        db.session.commit()
        flash("Estimate recalculated.", "success")
        return _back(ct, "#price")
    fee = _cents(request.form.get("fee"))
    if fee is None:
        flash("Enter the total price.", "error")
        return _back(ct, "#price")
    ok, err = service.approve(ct, fee, _staff(), session.get("admin_user_id"), request.form.get("reason"))
    flash("Approved. The price is confirmed and payment can now be requested." if ok else err, "success" if ok else "error")
    return _back(ct, "#price")


@admin_bp.route("/consent-travel/<int:case_id>/request-payment", methods=["POST"])
@admin_required
def ct_request_payment(case_id):
    """Requires OG approval first (a CONFIRMED price) — see `service.approve`. Reuses the global OG Payments
    system (Square / Zelle / Cash App / Pay at Office) exactly like Tax and NJ Driver License."""
    from app import payments as pay_svc

    _csrf()
    ct = _ct_or_404(case_id)
    confirmed = next((q for q in reversed(ct.quotes) if q.status == "confirmed"), None)
    if ct.status not in ("approved", "in_progress") or confirmed is None or confirmed.final_total_cents is None:
        flash("Approve the case and confirm a price before requesting payment.", "error")
        return _back(ct, "#price")
    description = "Consent to Travel Authorization"
    charge = next((c for c in ct.case.charges if c.description == description and not c.is_canceled), None)
    if charge is None:
        charge = pay_svc.create_charge(ct.case.customer, description=description, case=ct.case, total_cents=confirmed.final_total_cents, price_mode="final", admin_id=session.get("admin_user_id"))
    elif charge.total_cents != confirmed.final_total_cents:
        pay_svc.set_price(charge, confirmed.final_total_cents, admin_id=session.get("admin_user_id"), mode="final", reason="Synced from the OG-approved Consent to Travel price.")
    bal = pay_svc.balance_cents(charge)
    if not bal:
        flash("This charge is already fully paid.", "error")
        return _back(ct, "#price")
    try:
        pay_svc.request_payment(charge, bal, admin_id=session.get("admin_user_id"))
    except ValueError as exc:
        flash(str(exc), "error")
        return _back(ct, "#price")
    flash("Payment requested — the customer will see this in My Account > Payments.", "success")
    return _back(ct, "#price")


@admin_bp.route("/consent-travel/<int:case_id>/note", methods=["POST"])
@admin_required
def ct_note(case_id):
    _csrf()
    ct = _ct_or_404(case_id)
    body = request.form.get("body", "").strip()
    if body:
        db.session.add(CaseNote(case_id=ct.case_id, body=body[:4000], author_name=_staff()))
        db.session.commit()
        case_svc.case_event(ct.case, "case_note_added", actor="admin")
    return _back(ct, "#notes")


# ------------------------------------------------------------------ Consent to Travel -> Pricing
@admin_bp.route("/consent-travel/pricing")
@admin_required
def ct_pricing():
    pricing.ensure_seed()
    rules = ConsentTravelPriceRule.query.order_by(ConsentTravelPriceRule.id).all()
    return render_template("admin/consent_travel_pricing.html", rules=rules, fmt=pricing.fmt)


@admin_bp.route("/consent-travel/pricing", methods=["POST"])
@admin_required
def ct_pricing_save():
    _csrf()
    changed = []
    for rule in ConsentTravelPriceRule.query.all():
        key = f"r{rule.id}"
        if f"{key}__present" not in request.form:
            continue
        before = (rule.amount_cents, rule.active)
        cents = _cents(request.form.get(f"{key}__amount"))
        if cents is not None and 0 <= cents <= 10_000_000:
            rule.amount_cents = cents
        rule.active = bool(request.form.get(f"{key}__active"))
        if before != (rule.amount_cents, rule.active):
            rule.updated_by = _staff()
            changed.append(rule.label_en)
    db.session.commit()
    flash(f"{len(changed)} price setting(s) updated. Cases already estimated/confirmed keep their own snapshot." if changed else "Nothing changed.", "success")
    return redirect(url_for("admin.ct_pricing"))
