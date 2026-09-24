"""Admin side of the Tax Smart Intake: Tax Cases (list + case view), the explicit staff actions (status, request information, reopen, confirm / override the price, payment
placeholders, audited bank reveal) and Tax Services -> Pricing (the data-driven price configuration per tax year). Nothing here files a return or talks to the IRS."""

import json
from datetime import date, datetime

from flask import abort, flash, redirect, render_template, request, session, url_for

from app import case_documents as vault
from app import cases as case_svc
from app import secure_store
from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.models import TAX_STATUS_EN, TAX_STATUSES, Case, CaseNote, TaxCaseData, TaxPriceRule
from app.tax import docs, pricing, service, summary
from app.tax.registry import CONFIGS, CURRENT_YEAR

STAFF_STATUSES = [(k, en) for k, en, _es in TAX_STATUSES if k not in ("draft",)]


def _staff():
    return session.get("admin_name") or session.get("admin_email") or "OG team"


def _csrf():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)


def _tax_or_404(case_id):
    case = db.session.get(Case, case_id)
    if case is None or case.case_type != "tax_return" or case.tax_data is None:
        abort(404)
    return case.tax_data


def _back(tax, anchor=""):
    return redirect(url_for("admin.tax_case", case_id=tax.case_id) + anchor)


def _cents(text):
    text = (text or "").replace("$", "").replace(",", "").strip()
    if not text:
        return None
    try:
        return int(round(float(text) * 100))
    except ValueError:
        return None


@admin_bp.route("/tax")
@admin_required
def tax_list():
    q = TaxCaseData.query.join(Case, Case.id == TaxCaseData.case_id)
    year = request.args.get("year", type=int)
    status = request.args.get("status", "")
    if year:
        q = q.filter(TaxCaseData.tax_year == year)
    if status in TAX_STATUS_EN:
        q = q.filter(TaxCaseData.status == status)
    rows = []
    for tax in q.order_by(TaxCaseData.updated_at.desc()).limit(300).all():
        have, total, missing = docs.counts(tax)
        quote = tax.current_quote
        rows.append({"tax": tax, "case": tax.case, "docs": f"{have}/{total}", "missing": missing, "quote": quote,
                     "price": pricing.fmt(next((x.final_fee_cents for x in reversed(tax.quotes) if x.status == "confirmed"), None)) if tax.price_status == "confirmed" else None})
    return render_template("admin/tax_list.html", rows=rows, statuses=STAFF_STATUSES + [("draft", "Draft")], year=year, status=status, years=sorted(CONFIGS), fmt=pricing.fmt)


@admin_bp.route("/tax/<int:case_id>")
@admin_required
def tax_case(case_id):
    tax = _tax_or_404(case_id)
    c = service.ctx(tax, "en")
    data = summary.admin_summary(tax)
    est = pricing.estimate(tax, c)
    confirmed = next((q for q in reversed(tax.quotes) if q.status == "confirmed"), None)
    reqs = []
    for r in sorted(docs.requirements(tax), key=lambda x: (x.status in ("accepted",), x.id)):
        title, msg = docs.req_text(r, "en")
        reqs.append({"r": r, "title": title, "status": vault.status_label(r.status, "en"), "choice": tax.doc_choices.get(r.rule_key), "optional": docs.is_optional(r.rule_key),
                     "doc": r.current_document})
    have, total, missing = docs.counts(tax)
    notes = CaseNote.query.filter_by(case_id=tax.case_id).order_by(CaseNote.id.desc()).all()
    events = case_svc.case_timeline(tax.case, 60)
    from app import case_revisions

    revisions = [{"rev": r, "changes": case_revisions.revision_changes(r)} for r in reversed(case_revisions.history(tax.case))]
    return render_template("admin/tax_case.html", tax=tax, case=tax.case, data=data, est=est, confirmed=confirmed, reqs=reqs, docs_have=have, docs_total=total, docs_missing=missing,
                           notes=notes, events=events, statuses=STAFF_STATUSES, ready=service.readiness(tax, "en"), fmt=pricing.fmt, quotes=list(reversed(tax.quotes)),
                           status_label=TAX_STATUS_EN.get(tax.status, tax.status), bank_ok=secure_store.available(), today=date.today().isoformat(), revisions=revisions)


@admin_bp.route("/tax/<int:case_id>/status", methods=["POST"])
@admin_required
def tax_status(case_id):
    _csrf()
    tax = _tax_or_404(case_id)
    when = None
    raw = request.form.get("when")
    if raw:
        try:
            when = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            when = None
    ok, err = service.set_status(tax, request.form.get("status", ""), _staff(), message=request.form.get("message"), when=when, note=request.form.get("note"), force=bool(request.form.get("force")))
    flash("Status updated." if ok else (err or "Not done."), "success" if ok else "error")
    return _back(tax)


@admin_bp.route("/tax/<int:case_id>/request-info", methods=["POST"])
@admin_required
def tax_request_info(case_id):
    _csrf()
    tax = _tax_or_404(case_id)
    ok, err = service.request_info(tax, request.form.get("message", ""), _staff())
    flash("The customer will see your message in My Account." if ok else err, "success" if ok else "error")
    return _back(tax)


@admin_bp.route("/tax/<int:case_id>/reopen", methods=["POST"])
@admin_required
def tax_reopen(case_id):
    _csrf()
    tax = _tax_or_404(case_id)
    ok, err = service.reopen(tax, request.form.get("message", ""), _staff(), actor_id=session.get("admin_user_id"))
    flash("Reopened. The customer can edit the same tax return and send it again." if ok else err, "success" if ok else "error")
    return _back(tax)


@admin_bp.route("/tax/<int:case_id>/price", methods=["POST"])
@admin_required
def tax_price(case_id):
    """Confirm the preparation fee (as estimated or overridden) with a reason, or recalculate the system estimate."""
    _csrf()
    tax = _tax_or_404(case_id)
    action = request.form.get("action")
    c = service.ctx(tax, "en")
    if action == "recalc":
        quote, created = pricing.snapshot(tax, c, staff=_staff(), source="system")
        db.session.commit()
        flash("Estimate recalculated." if created else "The estimate has not changed.", "success")
        return _back(tax, "#price")
    fee = _cents(request.form.get("fee"))
    if fee is None:
        flash("Enter the preparation fee.", "error")
        return _back(tax, "#price")
    pricing.snapshot(tax, c)
    db.session.flush()
    before = next((q for q in reversed(tax.quotes) if q.status == "confirmed"), None)
    try:
        quote = pricing.confirm(tax, fee, _staff(), request.form.get("reason"))
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return _back(tax, "#price")
    service.log(tax, "tax_price_revised" if before is not None else "tax_price_confirmed", {"fee": pricing.fmt(fee), "previous": pricing.fmt(before.final_fee_cents) if before else None, "reason": quote.reason}, actor="admin")
    flash("Preparation fee confirmed." + (" The customer will be asked to acknowledge the change." if quote.needs_ack else ""), "success")
    return _back(tax, "#price")


@admin_bp.route("/tax/<int:case_id>/request-payment", methods=["POST"])
@admin_required
def tax_request_payment(case_id):
    """Model C (OG Payments): syncs the OG Payments Charge to the SAME confirmed `final_fee_cents` this
    module already tracks (never a second, disconnected price) and opens a payment request for the amount
    the customer still owes. Requires a CONFIRMED fee — an estimate is never requestable."""
    from app import payments as pay_svc

    _csrf()
    tax = _tax_or_404(case_id)
    confirmed = next((q for q in reversed(tax.quotes) if q.status == "confirmed"), None)
    if confirmed is None or confirmed.final_fee_cents is None:
        flash("Confirm the preparation fee before requesting payment.", "error")
        return _back(tax, "#price")
    description = f"Tax Preparation — {tax.tax_year}"
    charge = next((c for c in tax.case.charges if c.description == description and not c.is_canceled), None)
    if charge is None:
        charge = pay_svc.create_charge(tax.case.customer, description=description, case=tax.case,
                                       total_cents=confirmed.final_fee_cents, price_mode="final", admin_id=session.get("admin_user_id"))
    elif charge.total_cents != confirmed.final_fee_cents:
        pay_svc.set_price(charge, confirmed.final_fee_cents, admin_id=session.get("admin_user_id"), mode="final", reason="Synced from the confirmed tax preparation fee.")
    bal = pay_svc.balance_cents(charge)
    if not bal:
        flash("This charge is already fully paid.", "error")
        return _back(tax, "#price")
    try:
        pay_svc.request_payment(charge, bal, admin_id=session.get("admin_user_id"))
    except ValueError as exc:
        flash(str(exc), "error")
        return _back(tax, "#price")
    flash("Payment requested — the customer will see this in My Account > Payments.", "success")
    return _back(tax, "#price")


@admin_bp.route("/tax/<int:case_id>/payment", methods=["POST"])
@admin_required
def tax_payment(case_id):
    """Payment architecture placeholder: only the state and a reference are recorded. No gateway is connected."""
    _csrf()
    tax = _tax_or_404(case_id)
    status = request.form.get("payment_status", "")
    if status in ("not_started", "requested", "paid", "waived"):
        tax.payment_status = status
    tax.payment_reference = (request.form.get("payment_reference") or "").strip()[:80] or None
    db.session.commit()
    flash("Payment information saved.", "success")
    return _back(tax, "#price")


@admin_bp.route("/tax/<int:case_id>/note", methods=["POST"])
@admin_required
def tax_note(case_id):
    _csrf()
    tax = _tax_or_404(case_id)
    body = request.form.get("body", "").strip()
    if body:
        db.session.add(CaseNote(case_id=tax.case_id, body=body[:4000], author_name=_staff()))
        db.session.commit()
        case_svc.case_event(tax.case, "case_note_added", actor="admin")
    return _back(tax, "#notes")


@admin_bp.route("/tax/<int:case_id>/bank", methods=["POST"])
@admin_required
def tax_bank_reveal(case_id):
    """Audited reveal of the refund bank details: shown in this response only (never stored in a session, flash message, URL or log)."""
    _csrf()
    tax = _tax_or_404(case_id)
    bank = tax.bank
    if bank is None or not secure_store.available():
        flash("There are no bank details to show.", "error")
        return _back(tax, "#bank")
    routing, account = secure_store.decrypt(bank.routing_enc), secure_store.decrypt(bank.account_enc)
    service.log(tax, "tax_bank_viewed", {"by": _staff()}, actor="admin")
    return render_template("admin/tax_bank.html", tax=tax, routing=routing, account=account, account_type=bank.account_type)


# ------------------------------------------------------------------ Tax Services -> Pricing
@admin_bp.route("/tax/pricing")
@admin_required
def tax_pricing():
    year = request.args.get("year", type=int) or CURRENT_YEAR
    if year not in CONFIGS:
        abort(404)
    pricing.ensure_seed(year)
    rules = pricing.rules_for(year)
    groups = {}
    for r in rules.values():
        groups.setdefault(r.kind, []).append(r)
    return render_template("admin/tax_pricing.html", year=year, years=sorted(CONFIGS), groups=groups, fmt=pricing.fmt)


@admin_bp.route("/tax/pricing/<int:year>", methods=["POST"])
@admin_required
def tax_pricing_save(year):
    _csrf()
    if year not in CONFIGS:
        abort(404)
    changed = []
    for rule in TaxPriceRule.query.filter_by(tax_year=year).all():
        key = f"r{rule.id}"
        if f"{key}__present" not in request.form:
            continue
        before = (rule.amount_cents, rule.percent, rule.active, rule.params_json)
        active = bool(request.form.get(f"{key}__active"))
        if rule.kind in ("base", "addon") or (rule.kind == "setting" and rule.amount_cents is not None):
            cents = _cents(request.form.get(f"{key}__amount"))
            if cents is not None and 0 <= cents <= 10_000_000:
                rule.amount_cents = cents
        if rule.kind == "discount":
            try:
                pct = float(request.form.get(f"{key}__percent", rule.percent))
            except ValueError:
                pct = rule.percent
            if 0 <= pct <= 100:
                rule.percent = pct
            params = rule.params
            params["stackable"] = bool(request.form.get(f"{key}__stackable"))
            rule.params_json = json.dumps(params)
        if rule.kind == "setting" and rule.amount_cents is None:
            params = rule.params
            try:
                params["value"] = max(0, int(request.form.get(f"{key}__value", params.get("value", 0))))
            except ValueError:
                pass
            rule.params_json = json.dumps(params)
        rule.active = active
        if before != (rule.amount_cents, rule.percent, rule.active, rule.params_json):
            rule.updated_by = _staff()
            changed.append(rule.label_en)
    db.session.commit()
    flash(f"{len(changed)} price setting(s) updated. Cases already priced keep their own snapshot." if changed else "Nothing changed.", "success")
    return redirect(url_for("admin.tax_pricing", year=year))
