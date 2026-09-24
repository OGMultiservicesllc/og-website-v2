"""OG Payments — service layer. All money is integer cents end to end (never a float); every balance is
DERIVED from `Payment`/`Refund` rows at read time rather than cached, so it can never silently drift from
the authoritative records (Phase 3: "the balance must be derived safely from authoritative records").

Status model (Phase 4) is a pure function of the data, not a stored column, for the same reason:
no_payment_required | estimate | payment_pending | partially_paid | paid | refunded | partially_refunded | canceled.
"""

import logging
import secrets
from datetime import datetime

from app.activity import log_event
from app.extensions import db
from app.models import Charge, Payment, PaymentRequest, Refund

logger = logging.getLogger("og_payments")

CENTS_PER_UNIT = 100


def _notify(student, template_key, **kw):
    """Best-effort transactional email — never allowed to affect the payment transaction itself (Phase 9
    of the Transactional Email spec: "email delivery failure must NOT crash the customer transaction")."""
    if student is None:
        return
    try:
        from app.email_service import send_transactional_email

        send_transactional_email(student, template_key, student.preferred_language or "en", **kw)
    except Exception:  # noqa: BLE001
        logger.exception("[payments] transactional email %r failed to queue", template_key)


# ------------------------------------------------------------------ money
def format_cents(cents, currency="USD"):
    if cents is None:
        return ""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    symbol = "$" if currency == "USD" else (currency + " ")
    return f"{sign}{symbol}{cents // CENTS_PER_UNIT:,}.{cents % CENTS_PER_UNIT:02d}"


def parse_dollars_to_cents(value):
    """Admin-form input ("175", "175.50") -> integer cents. Never used for anything a customer submits —
    the amount a customer can pay always comes from a server-side PaymentRequest, never parsed from their
    own input (Phase 30)."""
    if value is None or str(value).strip() == "":
        return None
    try:
        from decimal import Decimal, InvalidOperation

        d = Decimal(str(value).strip().replace(",", "").replace("$", ""))
        return int((d * 100).to_integral_value())
    except (InvalidOperation, ValueError):
        return None


# ------------------------------------------------------------------ derived balance / status
def paid_cents(charge):
    return sum(p.net_cents for p in charge.payments if p.status == "completed")


def pending_cents(charge):
    return sum(p.amount_cents for p in charge.payments if p.status == "pending")


def refunded_cents(charge):
    return sum(p.refunded_cents for p in charge.payments if p.status == "completed")


def balance_cents(charge):
    if charge.total_cents is None:
        return None
    return max(0, charge.total_cents - paid_cents(charge))


def open_request(charge):
    return next((r for r in reversed(charge.requests) if r.status == "open"), None)


def status_of(charge):
    """One pure function, one place — every page (Home, Services, Payments, Admin) calls this instead of
    re-deriving its own notion of "is this paid"."""
    if charge.is_canceled:
        return "canceled"
    if charge.total_cents is None:
        return "no_payment_required"
    if charge.price_mode == "estimate":
        return "estimate"
    paid = paid_cents(charge)
    refunded = refunded_cents(charge)
    if refunded > 0:
        return "refunded" if paid <= 0 else "partially_refunded"
    if paid >= charge.total_cents and charge.total_cents > 0:
        return "paid"
    if paid > 0:
        return "partially_paid"
    # final price set, nothing paid yet (whether or not Admin has requested payment yet) — Pay Now only
    # appears once an OPEN PaymentRequest exists (see is_payable()); this status just says "there's a balance".
    return "payment_pending"


def is_payable(charge):
    return status_of(charge) in ("payment_pending", "partially_paid") and open_request(charge) is not None


# ------------------------------------------------------------------ receipts
def _assign_receipt_number(payment):
    db.session.flush()  # need payment.id
    payment.receipt_number = f"OGP-{payment.id:06d}"


def _idempotency_key():
    return secrets.token_hex(16)


# ------------------------------------------------------------------ Charge lifecycle (Admin)
def create_charge(customer, *, description, case=None, enrollment=None, course=None, total_cents=None, price_mode="none", admin_id=None):
    c = Charge(customer_id=customer.id, case_id=case.id if case else None, enrollment_id=enrollment.id if enrollment else None,
              course_id=course.id if course else None, description=description[:200], total_cents=total_cents,
              price_mode=price_mode if total_cents is not None else "none",
              created_by_admin_id=admin_id, priced_at=datetime.utcnow() if total_cents is not None else None, priced_by_admin_id=admin_id if total_cents is not None else None)
    db.session.add(c)
    db.session.commit()
    if total_cents is not None:
        log_event(customer.id, "payment_price_confirmed" if price_mode == "final" else "payment_price_estimated", actor="admin", actor_id=admin_id,
                  entity=("charge", c.id), case_id=case.id if case else None, meta={"service": c.description, "amount": format_cents(total_cents)})
    return c


def set_price(charge, total_cents, *, admin_id, mode="final", reason=None):
    """Phase 24: an estimate is never silently promoted into an authoritative amount due — this is always
    an explicit Admin action ("Confirm Price" / "Set Final Price"), and the previous amount is kept for audit."""
    before = charge.total_cents
    charge.previous_total_cents = before
    charge.total_cents = total_cents
    charge.price_mode = mode
    charge.priced_at = datetime.utcnow()
    charge.priced_by_admin_id = admin_id
    db.session.commit()
    event = "payment_price_confirmed" if mode == "final" else "payment_price_estimated"
    if before is not None and before != total_cents:
        event = "payment_price_changed"
    log_event(charge.customer_id, event, actor="admin", actor_id=admin_id, entity=("charge", charge.id), case_id=charge.case_id,
              meta={"service": charge.description, "from": format_cents(before), "to": format_cents(total_cents), "reason": (reason or "").strip() or None})
    return charge


def cancel_charge(charge, *, admin_id):
    charge.canceled_at = datetime.utcnow()
    for r in charge.requests:
        if r.status == "open":
            r.status = "canceled"
            r.canceled_at = datetime.utcnow()
            r.canceled_by_admin_id = admin_id
    db.session.commit()
    log_event(charge.customer_id, "payment_request_canceled", actor="admin", actor_id=admin_id, entity=("charge", charge.id), case_id=charge.case_id,
              meta={"service": charge.description})


# ------------------------------------------------------------------ Payment requests (Admin "Request Payment", Phase 23)
def request_payment(charge, requested_cents, *, admin_id, message=None, due_date=None):
    """V1 deliberately prevents an invalid negative balance (Phase 23): a request can never exceed the
    current balance due. Only one OPEN request at a time per charge — requesting again supersedes the
    previous open request rather than stacking ambiguous concurrent asks."""
    if charge.total_cents is None or charge.price_mode != "final":
        raise ValueError("A final price must be set before requesting payment.")
    bal = balance_cents(charge)
    if requested_cents <= 0 or requested_cents > bal:
        raise ValueError(f"Requested amount must be between $0.01 and the balance due ({format_cents(bal)}).")
    existing = open_request(charge)
    if existing is not None:
        existing.status = "canceled"
        existing.canceled_at = datetime.utcnow()
        existing.canceled_by_admin_id = admin_id
    req = PaymentRequest(charge_id=charge.id, requested_cents=requested_cents, message=(message or "").strip()[:500] or None,
                         due_date=due_date, created_by_admin_id=admin_id)
    db.session.add(req)
    db.session.commit()
    log_event(charge.customer_id, "payment_requested", actor="admin", actor_id=admin_id, entity=("payment_request", req.id), case_id=charge.case_id,
              meta={"service": charge.description, "amount": format_cents(requested_cents)})
    _notify(charge.customer, "payment_requested", ref={"payment_request_id": req.id}, related_type="payment_request", related_id=req.id,
            dedupe_key=f"payment_requested:{req.id}")
    return req


def cancel_request(payment_request, *, admin_id):
    payment_request.status = "canceled"
    payment_request.canceled_at = datetime.utcnow()
    payment_request.canceled_by_admin_id = admin_id
    db.session.commit()
    log_event(payment_request.charge.customer_id, "payment_request_canceled", actor="admin", actor_id=admin_id,
              entity=("payment_request", payment_request.id), case_id=payment_request.charge.case_id,
              meta={"service": payment_request.charge.description, "amount": format_cents(payment_request.requested_cents)})


def _maybe_fulfill_request(payment_request):
    if payment_request is None:
        return
    charge = payment_request.charge
    fulfilled = sum(p.amount_cents for p in payment_request.payments if p.status == "completed")
    if fulfilled >= payment_request.requested_cents:
        payment_request.status = "fulfilled"
        payment_request.fulfilled_at = datetime.utcnow()


def _fulfill_charge_context(charge, payment):
    """What a completed payment DOES beyond just recording money (Phase 14): a course purchase (Model A)
    activates Academy access here — never on the browser's redirect back (Phase 1/12), only once a payment
    is genuinely `completed`. Every other context (Case-based services) needs no extra action; the
    Case/Application itself is unaffected by payment status, exactly as the spec asks."""
    if charge.course_id and not charge.enrollment_id:
        from app import academy_access

        course = charge.course
        student = charge.customer
        enrollment, _status = academy_access.grant_access(student, course, access_source="paid_new_site", admin_id=None, actor="system")
        charge.enrollment_id = enrollment.id
        db.session.commit()
        log_event(charge.customer_id, "course_activated_from_payment", actor="system", entity=("enrollment", enrollment.id), case_id=charge.case_id,
                  meta={"course": course.title_en, "amount": format_cents(payment.amount_cents)})


# ------------------------------------------------------------------ Manual payments (Admin only, Phase 6 — customers can never create these)
def record_manual_payment(charge, *, amount_cents, method, payment_date, admin_id, reference=None, note=None, payment_request=None):
    from app.models import MANUAL_METHODS

    if method not in MANUAL_METHODS:
        raise ValueError("Not a valid manual payment method.")
    if amount_cents <= 0:
        raise ValueError("Amount must be greater than zero.")
    p = Payment(charge_id=charge.id, customer_id=charge.customer_id, payment_request_id=payment_request.id if payment_request else None,
               amount_cents=amount_cents, method=method, status="completed", reference=(reference or "").strip()[:120] or None,
               internal_note=(note or "").strip() or None, recorded_by_admin_id=admin_id, payment_date=payment_date, completed_at=datetime.utcnow())
    db.session.add(p)
    _assign_receipt_number(p)
    db.session.commit()
    _maybe_fulfill_request(payment_request)
    db.session.commit()
    log_event(charge.customer_id, "manual_payment_recorded", actor="admin", actor_id=admin_id, entity=("payment", p.id), case_id=charge.case_id,
              meta={"service": charge.description, "amount": format_cents(amount_cents), "method": method})
    _fulfill_charge_context(charge, p)
    _notify(charge.customer, "payment_received", ref={"payment_id": p.id}, related_type="payment", related_id=p.id,
            dedupe_key=f"payment_received:{p.id}")
    return p


# ------------------------------------------------------------------ Alternate checkout methods (Zelle / Cash App / Pay at
# Office, 2026-09-23) — the CUSTOMER's own selection at checkout, unlike record_manual_payment above (which is
# Admin typing in a payment that already happened). Creates a PENDING Payment exactly like start_square_payment
# does for Square; only Admin's confirm_manual_payment below can ever mark it paid or grant access — selecting
# a method here never does either.
def cash_app_tag():
    """The Cash App cashtag shown at checkout: SiteSettings override if set, else the built-in default —
    same "empty field = built-in default" convention PageBlock already uses."""
    from app import business_info
    from app.models import SiteSettings

    settings = SiteSettings.query.get(1)
    tag = (settings.cash_app_tag or "").strip() if settings else ""
    return tag or business_info.CASH_APP_TAG_DEFAULT


def start_manual_payment(charge, payment_request, *, method, student):
    """Mirrors start_square_payment's shape and guards (same ownership/open-request checks, same "resume an
    existing pending attempt instead of creating a second one" idempotency), but for a manual checkout method.
    The amount always comes from the server-side PaymentRequest, never from the client (Phase 30's rule
    applies here identically to Square)."""
    from app.models import CHECKOUT_MANUAL_METHODS

    if method not in CHECKOUT_MANUAL_METHODS:
        raise ValueError("Not a valid checkout payment method.")
    if payment_request.charge_id != charge.id or not payment_request.is_open:
        raise ValueError("This payment request is no longer open.")
    if payment_request.charge.customer_id != student.id:
        raise ValueError("Not your payment request.")
    existing = next((p for p in payment_request.payments if p.method in CHECKOUT_MANUAL_METHODS and p.status == "pending"), None)
    if existing and existing.customer_id == student.id:
        return existing
    p = Payment(charge_id=charge.id, customer_id=student.id, payment_request_id=payment_request.id,
               amount_cents=payment_request.requested_cents, method=method, status="pending")
    db.session.add(p)
    db.session.commit()
    log_event(student.id, "manual_payment_requested", actor="customer", entity=("payment", p.id), case_id=charge.case_id,
              meta={"service": charge.description, "amount": format_cents(p.amount_cents), "method": method})
    return p


def pending_manual_payment(payment_request, student):
    """The customer's own pending manual-method attempt on this request, if any — used to re-show the
    "awaiting verification" screen instead of the payment-method picker on a repeat visit."""
    from app.models import CHECKOUT_MANUAL_METHODS

    existing = next((p for p in payment_request.payments if p.method in CHECKOUT_MANUAL_METHODS and p.status == "pending"), None)
    if existing and existing.customer_id == student.id:
        return existing
    return None


def confirm_manual_payment(payment, *, admin_id):
    """Admin's "Confirm Payment" — transitions an EXISTING pending manual-method Payment to completed.
    Idempotent by construction, identically to _apply_square_payment: once status is no longer "pending",
    every further call is a no-op that returns the same payment unchanged, so pressing Confirm twice (or a
    slow double-click) can never double-grant access, double-issue a receipt, or double-send the email."""
    from app.models import MANUAL_METHODS

    if payment.method not in MANUAL_METHODS:
        raise ValueError("Not a manual payment.")
    if payment.status != "pending":
        return payment
    payment.status = "completed"
    payment.completed_at = datetime.utcnow()
    payment.recorded_by_admin_id = admin_id
    if payment.payment_date is None:
        payment.payment_date = datetime.utcnow().date()
    _assign_receipt_number(payment)
    db.session.commit()
    _maybe_fulfill_request(payment.payment_request)
    db.session.commit()
    log_event(payment.customer_id, "manual_payment_confirmed", actor="admin", actor_id=admin_id, entity=("payment", payment.id),
              case_id=payment.charge.case_id, meta={"service": payment.charge.description, "amount": format_cents(payment.amount_cents), "method": payment.method})
    _fulfill_charge_context(payment.charge, payment)
    _notify(payment.customer, "payment_received", ref={"payment_id": payment.id}, related_type="payment", related_id=payment.id,
            dedupe_key=f"payment_received:{payment.id}")
    return payment


def cancel_manual_payment(payment, *, admin_id, reason=None):
    """Admin's "Cancel / Reject Payment Request". Never touches a Square payment (Square has its own
    reconcile/refund lifecycle) and never touches anything already resolved — a completed, failed, or
    already-canceled payment is left exactly as it is, so this can safely be called more than once too."""
    from app.models import MANUAL_METHODS

    if payment.method not in MANUAL_METHODS:
        raise ValueError("Square payments are managed through Reconcile/Refund, not this action.")
    if payment.status != "pending":
        return payment
    payment.status = "canceled"
    payment.canceled_at = datetime.utcnow()
    payment.canceled_by_admin_id = admin_id
    if reason:
        payment.internal_note = ((payment.internal_note + "\n") if payment.internal_note else "") + f"Canceled: {reason.strip()[:280]}"
    db.session.commit()
    log_event(payment.customer_id, "manual_payment_canceled", actor="admin", actor_id=admin_id, entity=("payment", payment.id),
              case_id=payment.charge.case_id, meta={"service": payment.charge.description, "amount": format_cents(payment.amount_cents), "method": payment.method})
    return payment


# ------------------------------------------------------------------ Square online payments (Phase 7-8)
def start_square_payment(charge, payment_request, *, student):
    """Creates a PENDING Payment row with a persisted idempotency key BEFORE calling Square — the same key
    is reused on every retry of this same logical attempt (double-click, refresh, network retry), so Square
    itself de-duplicates the charge even if our own request never got a response (Phase 8)."""
    if payment_request.charge_id != charge.id or not payment_request.is_open:
        raise ValueError("This payment request is no longer open.")
    if payment_request.charge.customer_id != student.id:
        raise ValueError("Not your payment request.")
    p = Payment(charge_id=charge.id, customer_id=student.id, payment_request_id=payment_request.id,
               amount_cents=payment_request.requested_cents, method="square", status="pending", idempotency_key=_idempotency_key())
    db.session.add(p)
    db.session.commit()
    log_event(student.id, "square_payment_initiated", actor="customer", entity=("payment", p.id), case_id=charge.case_id,
              meta={"service": charge.description, "amount": format_cents(p.amount_cents)})
    return p


def get_or_resume_pending_square_payment(payment_request, student):
    """A pending Square Payment row already exists for this request (the customer reloaded the pay page
    after a network hiccup) — reuse it (and its idempotency key) instead of creating a new attempt."""
    existing = next((p for p in payment_request.payments if p.method == "square" and p.status == "pending"), None)
    if existing and existing.customer_id == student.id:
        return existing
    return None


def confirm_square_payment(payment, *, source_id, buyer_email=None):
    """Calls Square with the payment's OWN persisted idempotency key. Never trusts an amount from the
    request — `payment.amount_cents` was fixed server-side when `start_square_payment` created the row,
    itself bounded by the PaymentRequest (Phase 30)."""
    from app import square_client

    if payment.status != "pending":
        return payment  # already resolved (webhook or a prior call) — never double-process
    try:
        sq_payment = square_client.create_payment(
            source_id=source_id, idempotency_key=payment.idempotency_key, amount_cents=payment.amount_cents,
            currency=payment.currency, customer_note=payment.charge.description, buyer_email=buyer_email,
        )
    except Exception as exc:  # noqa: BLE001 — Square SDK raises its own exception types; never let one crash the request
        payment.status = "failed"
        payment.failure_reason = str(exc)[:300]
        db.session.commit()
        log_event(payment.customer_id, "payment_failed", actor="customer", entity=("payment", payment.id), case_id=payment.charge.case_id,
                  meta={"service": payment.charge.description, "amount": format_cents(payment.amount_cents)})
        return payment
    _apply_square_payment(payment, sq_payment)
    return payment


def _apply_square_payment(payment, sq_payment):
    """Shared by the synchronous confirm call AND the webhook handler — whichever arrives first sets the
    result; the other is then an idempotent no-op (Phase 9: "duplicate webhook delivery must NOT duplicate
    payments"). `sq_payment` is a Square SDK Payment object (or a dict from a webhook payload)."""
    def g(obj, key):
        return getattr(obj, key, None) if not isinstance(obj, dict) else obj.get(key)

    sq_status = (g(sq_payment, "status") or "").upper()
    payment.square_payment_id = g(sq_payment, "id") or payment.square_payment_id
    order_id = g(sq_payment, "order_id")
    if order_id:
        payment.square_order_id = order_id
    card = g(sq_payment, "card_details")
    card_dict = card if isinstance(card, dict) else (card.__dict__ if card else None)
    if card_dict:
        card_obj = card_dict.get("card") if isinstance(card_dict.get("card"), dict) else getattr(card, "card", None)
        if card_obj:
            payment.card_brand = (card_obj.get("card_brand") if isinstance(card_obj, dict) else getattr(card_obj, "card_brand", None)) or payment.card_brand
            payment.card_last4 = (
                card_obj.get("last_4") if isinstance(card_obj, dict)
                else (getattr(card_obj, "last4", None) or getattr(card_obj, "last_4", None))
            ) or payment.card_last4
    if sq_status == "COMPLETED":
        if payment.status != "completed":
            payment.status = "completed"
            payment.completed_at = datetime.utcnow()
            _assign_receipt_number(payment)
            db.session.commit()
            _maybe_fulfill_request(payment.payment_request)
            db.session.commit()
            log_event(payment.customer_id, "payment_completed", actor="customer", entity=("payment", payment.id), case_id=payment.charge.case_id,
                      meta={"service": payment.charge.description, "amount": format_cents(payment.amount_cents), "method": "square"})
            _fulfill_charge_context(payment.charge, payment)
            _notify(payment.customer, "payment_received", ref={"payment_id": payment.id}, related_type="payment", related_id=payment.id,
                    dedupe_key=f"payment_received:{payment.id}")
    elif sq_status in ("FAILED", "CANCELED"):
        if payment.status == "pending":
            payment.status = "failed"
            payment.failure_reason = f"Square payment status: {sq_status}"
            db.session.commit()
            log_event(payment.customer_id, "payment_failed", actor="customer", entity=("payment", payment.id), case_id=payment.charge.case_id,
                      meta={"service": payment.charge.description, "amount": format_cents(payment.amount_cents)})
    else:
        db.session.commit()  # APPROVED/PENDING — stays "pending" on our side (Phase 12: never treat pending as paid)


def reconcile_payment(payment):
    """Phase 38: a safe way to check Square directly when a webhook might have been missed — never marks a
    payment paid without asking Square itself first."""
    from app import square_client

    if payment.method != "square" or not payment.square_payment_id or payment.status != "pending":
        return payment
    try:
        sq_payment = square_client.get_payment(payment.square_payment_id)
    except Exception:  # noqa: BLE001
        return payment
    _apply_square_payment(payment, sq_payment)
    return payment


# ------------------------------------------------------------------ Webhooks (Phase 9) — a safety net, never the ONLY
# path a payment is confirmed through: `confirm_square_payment` already applies the result synchronously on the
# customer's own request. A webhook re-applying the SAME outcome is a no-op by construction (`_apply_square_payment`
# only transitions status once), so retried/duplicate delivery can never duplicate a payment or a course activation.
def handle_square_webhook_event(event_type, data):
    obj = (data or {}).get("object") or {}
    if event_type in ("payment.created", "payment.updated"):
        sq_payment = obj.get("payment")
        if not sq_payment or not sq_payment.get("id"):
            return
        payment = Payment.query.filter_by(square_payment_id=sq_payment["id"]).first()
        if payment is None:
            logger.info("[payments] webhook for unknown Square payment id %s (no matching Payment row yet)", sq_payment.get("id"))
            return
        _apply_square_payment(payment, sq_payment)
    elif event_type in ("refund.created", "refund.updated"):
        sq_refund = obj.get("refund")
        if not sq_refund or not sq_refund.get("id"):
            return
        refund = Refund.query.filter_by(square_refund_id=sq_refund["id"]).first()
        if refund is None:
            logger.info("[payments] webhook for unknown Square refund id %s", sq_refund.get("id"))
            return
        status = (sq_refund.get("status") or "").upper()
        if status == "COMPLETED" and refund.status != "completed":
            refund.status = "completed"
            refund.completed_at = datetime.utcnow()
            db.session.commit()
            _notify(refund.payment.customer, "refund_processed", ref={"refund_id": refund.id}, related_type="refund", related_id=refund.id,
                    dedupe_key=f"refund_processed:{refund.id}")
        elif status in ("FAILED", "REJECTED") and refund.status == "pending":
            refund.status = "failed"
            db.session.commit()


# ------------------------------------------------------------------ Refunds (Phase 13)
def refund_payment(payment, amount_cents, *, admin_id, reason=None):
    if amount_cents <= 0 or amount_cents > payment.net_cents:
        raise ValueError("Refund amount must be between $0.01 and the remaining paid amount.")
    if payment.method == "square":
        from app import square_client

        idem = _idempotency_key()
        r = Refund(payment_id=payment.id, amount_cents=amount_cents, status="pending", reason=(reason or "").strip()[:300] or None,
                  idempotency_key=idem, created_by_admin_id=admin_id)
        db.session.add(r)
        db.session.commit()
        try:
            sq_refund = square_client.create_refund(payment_id=payment.square_payment_id, amount_cents=amount_cents,
                                                     currency=payment.currency, idempotency_key=idem, reason=reason)
        except Exception as exc:  # noqa: BLE001
            r.status = "failed"
            db.session.commit()
            log_event(payment.customer_id, "refund_failed", actor="admin", actor_id=admin_id, entity=("refund", r.id), case_id=payment.charge.case_id,
                      meta={"amount": format_cents(amount_cents), "error": str(exc)[:200]})
            return r
        r.square_refund_id = getattr(sq_refund, "id", None)
        sq_status = (getattr(sq_refund, "status", "") or "").upper()
        r.status = "completed" if sq_status in ("COMPLETED", "APPROVED") else "pending"
        if r.status == "completed":
            r.completed_at = datetime.utcnow()
        db.session.commit()
    else:
        r = Refund(payment_id=payment.id, amount_cents=amount_cents, status="completed", reason=(reason or "").strip()[:300] or None,
                  created_by_admin_id=admin_id, completed_at=datetime.utcnow())
        db.session.add(r)
        db.session.commit()
    event = "payment_refunded" if r.amount_cents >= payment.amount_cents else "payment_partially_refunded"
    log_event(payment.customer_id, event, actor="admin", actor_id=admin_id, entity=("refund", r.id), case_id=payment.charge.case_id,
              meta={"service": payment.charge.description, "amount": format_cents(amount_cents), "method": payment.method})
    if r.status == "completed":
        _notify(payment.customer, "refund_processed", ref={"refund_id": r.id}, related_type="refund", related_id=r.id,
                dedupe_key=f"refund_processed:{r.id}")
    return r
