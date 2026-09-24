"""OG Payments — presentation/aggregation layer for My Account > Payments, the Home "Payment needed" Action
Required item, and the Admin customer Payments tab. Mirrors `app/account_dashboard.py`'s own shape (a thin
aggregation over the authoritative `app.payments` records, never inventing new state) so it plugs into the
existing Action Required/Home patterns without changing them."""

from flask import url_for

from app import payments as pay_svc
from app import customer_status
from app.case_types import type_title
from app.models import Charge, Payment


def _charge_row(charge, lang):
    status = pay_svc.status_of(charge)
    label, tone = customer_status.payment_status(status, lang)
    req = pay_svc.open_request(charge)
    # `Charge.description` is an admin-authored, English-only label (same convention as every other
    # admin-typed customer-facing string in this project, e.g. Document Vault requirement titles) — EXCEPT
    # for a course purchase, where a real bilingual `Course.title(lang)` already exists, so it takes over as
    # the primary title instead of duplicating the English name next to its own Spanish translation.
    description = charge.display_title(lang)
    context_title = type_title(charge.case.case_type, lang) if charge.case_id else None
    return {
        "charge": charge, "description": description, "status": status, "label": label, "tone": tone,
        "total": pay_svc.format_cents(charge.total_cents), "paid": pay_svc.format_cents(pay_svc.paid_cents(charge)),
        "balance": pay_svc.format_cents(pay_svc.balance_cents(charge)),
        "requested": pay_svc.format_cents(req.requested_cents) if req else None,
        "pay_url": url_for("account.pay_request", lang=lang, request_id=req.id) if req else None,
        "view_url": url_for("account.my_case_detail", lang=lang, case_id=charge.case_id) if charge.case_id else
                    (url_for("public.course_detail", lang=lang, slug=charge.course.slug) if charge.course_id else None),
        "context_title": context_title,
    }


def _payment_row(payment, lang):
    en = lang != "es"
    from app.models import method_label

    if payment.method == "square":
        method_text = f"{(payment.card_brand or 'Card').title()} •••• {payment.card_last4}" if payment.card_last4 else method_label("square", lang)
    else:
        method_text = method_label(payment.method, lang)
    status_text = {"pending": ("Payment Processing", "Pago en proceso"), "completed": ("Paid", "Pagado"),
                   "failed": ("Failed", "Fallido"), "canceled": ("Canceled", "Cancelado")}.get(payment.status, (payment.status, payment.status))
    service_title = payment.charge.display_title(lang)
    return {"payment": payment, "date": payment.completed_at or payment.created_at, "service": service_title,
            "amount": pay_svc.format_cents(payment.amount_cents), "net_amount": pay_svc.format_cents(payment.net_cents),
            "status_text": status_text[0] if en else status_text[1], "method_text": method_text,
            "refunded": payment.refunded_cents > 0, "receipt_url": url_for("account.payment_receipt", lang=lang, payment_id=payment.id)}


def data(student, lang):
    charges = Charge.query.filter_by(customer_id=student.id).order_by(Charge.created_at.desc()).all()
    needed_charges = [c for c in charges if pay_svc.is_payable(c)]
    needed = [_charge_row(c, lang) for c in needed_charges]
    amount_due_cents = sum(pay_svc.open_request(c).requested_cents for c in needed_charges)
    payments = (Payment.query.filter_by(customer_id=student.id).filter(Payment.status.in_(("completed", "failed")))
                .order_by(Payment.created_at.desc()).all())
    history = [_payment_row(p, lang) for p in payments]
    return {"amount_due_cents": amount_due_cents, "amount_due": pay_svc.format_cents(amount_due_cents),
            "needed": needed, "history": history, "has_any": bool(charges)}


def action_items(student, lang):
    """One row per OPEN, currently-payable charge — deep-links straight to that exact payment (item 20:
    "do not merely send the customer to generic Payments when an exact payment action exists")."""
    en = lang != "es"
    charges = Charge.query.filter_by(customer_id=student.id).order_by(Charge.created_at.desc()).all()
    items = []
    for c in charges:
        if not pay_svc.is_payable(c):
            continue
        req = pay_svc.open_request(c)
        title = c.display_title(lang)
        items.append({"text": f"{title}: {'Amount due' if en else 'Monto pendiente'} {pay_svc.format_cents(req.requested_cents)}",
                      "href": url_for("account.pay_request", lang=lang, request_id=req.id), "verb": "Pay Now" if en else "Pagar Ahora"})
    return items
