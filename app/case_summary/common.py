"""Shared building blocks every Case Summary presenter can reuse — Documents, Pricing/Payment, Notes,
Case Information. These read the SAME tables/services every other part of Admin already reads
(app/models/cases.py DocumentRequirement/CaseDocument, app/payments.py, CaseNote/SubmissionNote) — no
business logic is re-derived here, only reformatted into the PDF's Field/Block shapes.
"""
from app.case_summary.blocks import DocumentGroup, DocumentLine, DocumentsBlock, Field, NotesBlock, PricingBlock

_REQ_STATUS_MAP = {
    "accepted": "received",
    "uploaded": "received",
    "under_review": "received",
    "needed": "missing",
    "requested": "missing",
    "needs_replacement": "missing",
}
_REQ_NOTE = {
    "under_review": "under review",
    "needs_replacement": "replacement requested",
}


def documents_block(case, *, source_key=None, person_filter=None):
    """One DocumentGroup per CasePerson (None-person requirements grouped under a case-level, unlabeled
    group). `source_key` scopes to one intake's own requirements (e.g. "tax", "nj_dl") when a case can
    hold more than one; `person_filter` is an optional set of CasePerson ids to include (e.g. only this
    W-7 applicant), for the ITIN per-applicant blocks."""
    reqs = [r for r in case.requirements if r.withdrawn_at is None]
    if source_key:
        reqs = [r for r in reqs if r.source_key == source_key]
    if person_filter is not None:
        reqs = [r for r in reqs if r.person_id in person_filter]
    if not reqs:
        return None
    groups = {}
    order = []
    for r in reqs:
        key = r.person_id
        if key not in groups:
            groups[key] = DocumentGroup(person_label=(r.person.full_name if r.person else None), documents=[])
            order.append(key)
        status = _REQ_STATUS_MAP.get(r.status, "missing")
        note = _REQ_NOTE.get(r.status)
        groups[key].documents.append(DocumentLine(label=r.title, status=status, note=note))
    return DocumentsBlock(groups=[groups[k] for k in order])


def pricing_block_for_charge(charge):
    """Never claims "Paid" unless `app.payments.status_of()` — the same function Admin/My Account
    already use — actually says so."""
    if charge is None:
        return None
    from app import payments as pay

    lines = []
    if charge.total_cents is not None:
        if charge.price_mode == "estimate":
            lines.append(Field("System Estimate", pay.format_cents(charge.total_cents)))
        else:
            lines.append(Field("Confirmed Price", pay.format_cents(charge.total_cents)))
    paid = pay.paid_cents(charge)
    if paid:
        lines.append(Field("Amount Paid", pay.format_cents(paid)))
    bal = pay.balance_cents(charge)
    if bal is not None:
        lines.append(Field("Amount Due", pay.format_cents(bal)))
    status = pay.status_of(charge)
    status_label = {
        "no_payment_required": "No payment required", "estimate": "Estimate only — not yet confirmed",
        "payment_pending": "Payment pending", "partially_paid": "Partially paid", "paid": "Paid in full",
        "refunded": "Refunded", "partially_refunded": "Partially refunded", "canceled": "Canceled",
    }.get(status, status)
    completed = [p for p in charge.payments if p.status == "completed"]
    method_note = None
    if completed:
        methods = sorted({p.method for p in completed})
        from app.models import method_label

        method_note = ", ".join(method_label(m, "en") for m in methods)
    if method_note:
        status_label = f"{status_label} ({method_note})"
    return PricingBlock(lines=lines, payment_status=status_label)


def charge_for_case(case):
    from app.models import Charge

    return Charge.query.filter_by(case_id=case.id).order_by(Charge.id.desc()).first()


def internal_notes_block(case, submission=None):
    """Internal OG Notes ONLY — never shown to the customer. Case-level CaseNotes plus, for a
    FormSubmission-based intake, that application's own internal (is_customer_visible=False)
    SubmissionNotes."""
    notes = [f"{n.created_at.strftime('%b %d, %Y')} — {n.author_name or 'OG staff'}: {n.body}" for n in case.notes]
    if submission is not None:
        for n in submission.notes:
            if not n.is_customer_visible:
                notes.append(f"{n.created_at.strftime('%b %d, %Y')} — {n.author_name or 'OG staff'}: {n.body}")
    notes.sort()
    return NotesBlock(heading="Internal OG Notes", notes=notes)


def case_info(case, *, application_label, status_label, submitted_at=None):
    from datetime import datetime as _dt

    def fmt(d):
        return d.strftime("%b %d, %Y") if d else None

    return {
        "case_number": case.case_number or f"#{case.id}",
        "customer_name": case.customer.name if case.customer else "—",
        "application_label": application_label,
        "status_label": status_label,
        "submitted_at": fmt(submitted_at),
        "updated_at": fmt(case.updated_at),
    }
