"""My OG Account > Payments (customer-facing) + the generic "Pay Now" flow shared by every payment model
(Academy Enroll & Pay, translations/notary/etc. Model B, DL/Tax estimate-to-final Model C, immigration
balance Model D — one page, one route, reused everywhere per Phase 21 "use the SAME underlying payment
records, do not duplicate payment data").

Ownership is always decided on the server from the signed-in customer: a charge/request/payment id in a
URL is only ever looked up THROUGH `owned_*`, so someone else's id answers 404 exactly like a missing one
(Phase 29)."""

from flask import abort, jsonify, redirect, render_template, request, url_for

from app import payments as pay_svc
from app.auth import validate_csrf
from app.blueprints.account.routes import account_bp
from app.extensions import db
from app.models import Charge, Payment, PaymentRequest
from app.student_auth import current_student, student_required


def owned_charge(student, charge_id):
    c = Charge.query.get(charge_id)
    return c if c and c.customer_id == student.id else None


def owned_request(student, request_id):
    r = PaymentRequest.query.get(request_id)
    return r if r and r.charge.customer_id == student.id else None


def owned_payment(student, payment_id):
    p = Payment.query.get(payment_id)
    return p if p and p.customer_id == student.id else None


def _service_url(charge):
    """Where "View" on a payment card/history row should go — the same case detail page every other My
    Account surface already links to; a course-only charge (no case yet) goes to the course itself."""
    if charge.case_id:
        return url_for("account.my_case_detail", lang=request.view_args.get("lang", "en"), case_id=charge.case_id)
    if charge.course_id:
        return url_for("public.course_detail", lang=request.view_args.get("lang", "en"), slug=charge.course.slug)
    return None


# ------------------------------------------------------------------ My Account > Payments
@account_bp.route("/payments")
@student_required
def payments(lang):
    from app import payments_dashboard

    return render_template("account/payments.html", section="payments", **payments_dashboard.data(current_student(), lang))


@account_bp.route("/payments/<int:payment_id>/receipt")
@student_required
def payment_receipt(lang, payment_id):
    from app.models import method_label

    p = owned_payment(current_student(), payment_id)
    if p is None:
        abort(404)
    return render_template("account/payment_receipt.html", section="payments", p=p, charge=p.charge,
                           service_url=_service_url(p.charge), refunded=p.refunded_cents, method_label=method_label)


# ------------------------------------------------------------------ Academy "Enroll & Pay" (Model A) — creates/reuses the Charge+PaymentRequest, then hands off to the generic pay page
@account_bp.route("/courses/<int:course_id>/enroll-pay")
@student_required
def course_enroll_pay(lang, course_id):
    from app.models import Course

    student = current_student()
    course = Course.query.get_or_404(course_id)
    if not course.is_published or not course.price_cents:
        abort(404)
    from app.academy_access import existing_enrollment

    active = existing_enrollment(student, course)
    if active is not None and active.is_active:
        # Phase 15: never present a purchase flow that could accidentally charge an already-active student again.
        return redirect(url_for("public.course_detail", lang=lang, slug=course.slug))

    charge = Charge.query.filter_by(customer_id=student.id, course_id=course.id).filter(Charge.canceled_at.is_(None)).first()
    if charge is None:
        charge = pay_svc.create_charge(student, description=course.title_en, course=course, total_cents=course.price_cents, price_mode="final")
    open_req = pay_svc.open_request(charge)
    if open_req is None:
        open_req = pay_svc.request_payment(charge, course.price_cents, admin_id=None, message=None)
    return redirect(url_for("account.pay_request", lang=lang, request_id=open_req.id))


# ------------------------------------------------------------------ The generic Pay Now page (Square Web Payments SDK
# plus the alternate Zelle/Cash App/Pay at Office checkout methods) — a GLOBAL OG Multiservices checkout. Any
# open, owned PaymentRequest is payable through all four methods regardless of what the Charge is for (an
# Academy course, a Case-based service, or a plain Admin-created charge) — nothing here is Academy-specific;
# course-specific behavior (granting Enrollment) happens only in payments._fulfill_charge_context, AFTER a
# payment completes, never at checkout time.
@account_bp.route("/pay/<int:request_id>")
@student_required
def pay_request(lang, request_id):
    student = current_student()
    req = owned_request(student, request_id)
    if req is None:
        abort(404)
    if not req.is_open:
        return redirect(url_for("account.pay_success", lang=lang, request_id=req.id) if req.status == "fulfilled" else url_for("account.payments", lang=lang))

    pending_manual = pay_svc.pending_manual_payment(req, student)
    if pending_manual is not None:
        return redirect(url_for("account.pay_request_pending", lang=lang, request_id=req.id))

    payment = pay_svc.get_or_resume_pending_square_payment(req, student)
    if payment is None:
        payment = pay_svc.start_square_payment(req.charge, req, student=student)
    from app import square_client

    manual_ctx = _manual_method_context(lang)
    if not square_client.is_configured():
        return render_template("account/pay.html", section="payments", req=req, charge=req.charge, payment=payment, square_ready=False,
                               show_manual_methods=True, manual=manual_ctx)
    return render_template("account/pay.html", section="payments", req=req, charge=req.charge, payment=payment, square_ready=True,
                           application_id=square_client.application_id(), location_id=square_client.location_id(), sandbox=square_client.is_sandbox(),
                           show_manual_methods=True, manual=manual_ctx)


def _manual_method_context(lang):
    from app import business_info

    return {
        "zelle_phone": business_info.ZELLE_PHONE,
        "zelle_recipient": business_info.ZELLE_RECIPIENT,
        "cash_app_tag": pay_svc.cash_app_tag(),
        "cash_app_recipient": business_info.CASH_APP_RECIPIENT,
        "office_line1": business_info.ADDRESS_LINE1,
        "office_line2": business_info.ADDRESS_LINE2,
        "office_name": business_info.BUSINESS_NAME,
    }


@account_bp.route("/pay/<int:request_id>/manual", methods=["POST"])
@student_required
def pay_request_manual(lang, request_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    student = current_student()
    req = owned_request(student, request_id)
    if req is None:
        abort(404)
    if not req.is_open:
        return redirect(url_for("account.payments", lang=lang))
    method = request.form.get("method", "")
    try:
        pay_svc.start_manual_payment(req.charge, req, method=method, student=student)
    except ValueError:
        abort(400)
    return redirect(url_for("account.pay_request_pending", lang=lang, request_id=req.id))


@account_bp.route("/pay/<int:request_id>/pending")
@student_required
def pay_request_pending(lang, request_id):
    student = current_student()
    req = owned_request(student, request_id)
    if req is None:
        abort(404)
    payment = pay_svc.pending_manual_payment(req, student)
    if payment is None:
        return redirect(url_for("account.pay_request", lang=lang, request_id=req.id))
    return render_template("account/pay_manual_pending.html", section="payments", req=req, charge=req.charge, payment=payment,
                           manual=_manual_method_context(lang), service_url=_service_url(req.charge))


@account_bp.route("/pay/<int:request_id>/charge", methods=["POST"])
@student_required
def pay_request_charge(lang, request_id):
    if not validate_csrf(request.form.get("csrf_token") or (request.get_json(silent=True) or {}).get("csrf_token")):
        return jsonify(ok=False, error="Session expired — please refresh and try again."), 400
    student = current_student()
    req = owned_request(student, request_id)
    if req is None:
        return jsonify(ok=False, error="Not found."), 404
    if not req.is_open:
        return jsonify(ok=False, error="This payment request is no longer open.", already="true"), 409
    body = request.get_json(silent=True) or request.form
    source_id = body.get("source_id")
    if not source_id:
        return jsonify(ok=False, error="Missing payment details."), 400
    payment = pay_svc.get_or_resume_pending_square_payment(req, student)
    if payment is None:
        payment = pay_svc.start_square_payment(req.charge, req, student=student)
    payment = pay_svc.confirm_square_payment(payment, source_id=source_id, buyer_email=student.email)
    if payment.status == "completed":
        return jsonify(ok=True, redirect=url_for("account.pay_success", lang=lang, request_id=req.id))
    if payment.status == "failed":
        return jsonify(ok=False, error="We couldn't complete this payment. Your card has not been charged. Please try again or use another payment method."
                       if lang != "es" else "No pudimos completar este pago. No se cobró tu tarjeta. Intenta de nuevo u otro método de pago."), 402
    return jsonify(ok=False, pending=True, error="Payment Processing" if lang != "es" else "Pago en proceso"), 202


@account_bp.route("/pay/<int:request_id>/success")
@student_required
def pay_success(lang, request_id):
    student = current_student()
    req = owned_request(student, request_id)
    if req is None:
        abort(404)
    payment = Payment.query.filter_by(payment_request_id=req.id, status="completed").order_by(Payment.completed_at.desc()).first()
    return render_template("account/pay_success.html", section="payments", req=req, charge=req.charge, payment=payment,
                           service_url=_service_url(req.charge))
