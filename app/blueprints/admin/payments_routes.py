"""Admin: OG Payments. One generic surface (the customer's Payments tab) covers every payment model —
fixed price, OG-confirmed price, estimate-to-final, and balance/partial payments — because they are all
just "set/change a Charge's price, then Request Payment, then Admin records or Square confirms a Payment".
Tax and NJ Driver License additionally get one-click "Request Payment" actions on their own Case admin
views (app/blueprints/admin/tax_routes.py / dl_routes.py) that create the Charge from the SAME confirmed
`final_fee_cents` those modules already track — never a second, disconnected price.
"""

from datetime import datetime

from flask import abort, flash, redirect, render_template, request, session, url_for

from app import payments as pay_svc
from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.models import Case, Charge, Payment, PaymentRequest, Student


def _staff_id():
    return session.get("admin_user_id")


def _csrf():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)


def _back(student_id, anchor=""):
    return redirect(url_for("admin.customer_detail", student_id=student_id, tab="payments") + anchor)


def _charge_or_404(charge_id, student_id=None):
    c = Charge.query.get_or_404(charge_id)
    if student_id is not None and c.customer_id != student_id:
        abort(404)
    return c


@admin_bp.route("/customers/<int:student_id>/charges/new", methods=["POST"])
@admin_required
def charge_new(student_id):
    _csrf()
    student = Student.query.get_or_404(student_id)
    description = (request.form.get("description") or "").strip()
    if not description:
        flash("A description is required.", "error")
        return _back(student_id)
    case_id = request.form.get("case_id", type=int)
    case = Case.query.filter_by(id=case_id, customer_id=student.id).first() if case_id else None
    total_cents = pay_svc.parse_dollars_to_cents(request.form.get("total"))
    mode = "final" if request.form.get("mode") == "final" else ("estimate" if total_cents is not None else "none")
    pay_svc.create_charge(student, description=description, case=case, total_cents=total_cents, price_mode=mode, admin_id=_staff_id())
    flash("Charge created.", "success")
    return _back(student_id)


@admin_bp.route("/charges/<int:charge_id>/price", methods=["POST"])
@admin_required
def charge_price(charge_id):
    _csrf()
    charge = _charge_or_404(charge_id)
    total_cents = pay_svc.parse_dollars_to_cents(request.form.get("total"))
    if total_cents is None or total_cents <= 0:
        flash("Enter a valid amount.", "error")
        return _back(charge.customer_id)
    mode = "final" if request.form.get("mode", "final") == "final" else "estimate"
    pay_svc.set_price(charge, total_cents, admin_id=_staff_id(), mode=mode, reason=request.form.get("reason"))
    flash("Price confirmed." if mode == "final" else "Estimate saved.", "success")
    return _back(charge.customer_id, "#payments")


@admin_bp.route("/charges/<int:charge_id>/cancel", methods=["POST"])
@admin_required
def charge_cancel(charge_id):
    _csrf()
    charge = _charge_or_404(charge_id)
    pay_svc.cancel_charge(charge, admin_id=_staff_id())
    flash("Charge canceled.", "success")
    return _back(charge.customer_id, "#payments")


@admin_bp.route("/charges/<int:charge_id>/request", methods=["POST"])
@admin_required
def charge_request(charge_id):
    _csrf()
    charge = _charge_or_404(charge_id)
    requested_cents = pay_svc.parse_dollars_to_cents(request.form.get("amount"))
    due_raw = (request.form.get("due_date") or "").strip()
    due_date = None
    if due_raw:
        try:
            due_date = datetime.strptime(due_raw, "%Y-%m-%d").date()
        except ValueError:
            due_date = None
    if requested_cents is None:
        flash("Enter a valid amount to request.", "error")
        return _back(charge.customer_id, "#payments")
    try:
        pay_svc.request_payment(charge, requested_cents, admin_id=_staff_id(), message=request.form.get("message"), due_date=due_date)
    except ValueError as exc:
        flash(str(exc), "error")
        return _back(charge.customer_id, "#payments")
    flash("Payment requested — the customer will see this in My Account > Payments.", "success")
    return _back(charge.customer_id, "#payments")


@admin_bp.route("/payment-requests/<int:request_id>/cancel", methods=["POST"])
@admin_required
def payment_request_cancel(request_id):
    _csrf()
    req = PaymentRequest.query.get_or_404(request_id)
    pay_svc.cancel_request(req, admin_id=_staff_id())
    flash("Payment request canceled.", "success")
    return _back(req.charge.customer_id, "#payments")


@admin_bp.route("/charges/<int:charge_id>/manual-payment", methods=["POST"])
@admin_required
def charge_manual_payment(charge_id):
    _csrf()
    charge = _charge_or_404(charge_id)
    amount_cents = pay_svc.parse_dollars_to_cents(request.form.get("amount"))
    method = request.form.get("method", "")
    date_raw = (request.form.get("payment_date") or "").strip()
    try:
        payment_date = datetime.strptime(date_raw, "%Y-%m-%d").date() if date_raw else datetime.utcnow().date()
    except ValueError:
        payment_date = datetime.utcnow().date()
    if amount_cents is None or amount_cents <= 0:
        flash("Enter a valid amount.", "error")
        return _back(charge.customer_id, "#payments")
    open_req = pay_svc.open_request(charge)
    try:
        pay_svc.record_manual_payment(charge, amount_cents=amount_cents, method=method, payment_date=payment_date, admin_id=_staff_id(),
                                      reference=request.form.get("reference"), note=request.form.get("note"), payment_request=open_req)
    except ValueError as exc:
        flash(str(exc), "error")
        return _back(charge.customer_id, "#payments")
    flash("Payment recorded.", "success")
    return _back(charge.customer_id, "#payments")


@admin_bp.route("/payments/<int:payment_id>/refund", methods=["POST"])
@admin_required
def payment_refund(payment_id):
    _csrf()
    payment = Payment.query.get_or_404(payment_id)
    amount_cents = pay_svc.parse_dollars_to_cents(request.form.get("amount"))
    if amount_cents is None or amount_cents <= 0:
        flash("Enter a valid refund amount.", "error")
        return _back(payment.customer_id, "#payments")
    try:
        pay_svc.refund_payment(payment, amount_cents, admin_id=_staff_id(), reason=request.form.get("reason"))
    except ValueError as exc:
        flash(str(exc), "error")
        return _back(payment.customer_id, "#payments")
    flash("Refund submitted.", "success")
    return _back(payment.customer_id, "#payments")


@admin_bp.route("/payments/<int:payment_id>/reconcile", methods=["POST"])
@admin_required
def payment_reconcile(payment_id):
    """Phase 38: a safe manual check against Square when a webhook might have been missed."""
    _csrf()
    payment = Payment.query.get_or_404(payment_id)
    pay_svc.reconcile_payment(payment)
    flash("Checked with Square." if payment.status == "pending" else f"Updated: {payment.status}.", "success")
    return _back(payment.customer_id, "#payments")


# ------------------------------------------------------------------ Alternate checkout methods (Zelle / Cash App / Pay at
# Office, 2026-09-23) — confirming or canceling a pending manual-method Payment the CUSTOMER created at checkout.
@admin_bp.route("/payments/<int:payment_id>/confirm", methods=["POST"])
@admin_required
def payment_confirm(payment_id):
    _csrf()
    payment = Payment.query.get_or_404(payment_id)
    try:
        result = pay_svc.confirm_manual_payment(payment, admin_id=_staff_id())
    except ValueError as exc:
        flash(str(exc), "error")
        return _back(payment.customer_id, "#payments")
    flash("Payment confirmed." if result.status == "completed" else "This payment was already resolved — no changes made.", "success")
    return _back(payment.customer_id, "#payments")


@admin_bp.route("/payments/<int:payment_id>/cancel", methods=["POST"])
@admin_required
def payment_manual_cancel(payment_id):
    _csrf()
    payment = Payment.query.get_or_404(payment_id)
    try:
        result = pay_svc.cancel_manual_payment(payment, admin_id=_staff_id(), reason=request.form.get("reason"))
    except ValueError as exc:
        flash(str(exc), "error")
        return _back(payment.customer_id, "#payments")
    flash("Payment request canceled." if result.status == "canceled" else "This payment was already resolved — no changes made.", "success")
    return _back(payment.customer_id, "#payments")


@admin_bp.route("/pending-payments")
@admin_required
def manual_payments_list():
    """A minimal cross-customer view of every pending Zelle/Cash App/Pay at Office request — the per-customer
    Payments tab (customer_detail, tab=payments) already has the full detail and the same Confirm/Cancel
    actions; this exists only so Admin doesn't have to already know which customer to look at."""
    from app.models import MANUAL_METHODS, PAYMENT_METHODS

    pending = (
        Payment.query.filter(Payment.status == "pending", Payment.method.in_(MANUAL_METHODS))
        .order_by(Payment.created_at.asc()).all()
    )
    return render_template("admin/manual_payments_list.html", pending=pending, payment_methods=PAYMENT_METHODS)
