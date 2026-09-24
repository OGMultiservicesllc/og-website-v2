"""Customer activity log: record meaningful events, render them as sentences.

What is recorded: account and workflow events useful for support, fulfilment,
security and audit. What is deliberately NOT recorded: page views, clicks, scroll,
field focus, keystrokes, and never the *values* of anything a customer typed.
"""

import json

from flask import has_request_context, session

from app.extensions import db
from app.models import ActivityEvent

# event_type -> (filter group, sentence template). `{x}` placeholders come from metadata.
EVENTS = {
    "account_created": ("account", "Account created"),
    "login": ("account", "Logged in"),
    "password_changed": ("account", "Changed their password"),
    "profile_updated": ("account", "Updated their profile"),
    "email_verified": ("account", "Verified their email address"),
    "email_changed": ("account", "Changed their account email to {new_email}"),
    "password_reset_requested": ("account", "Requested a password reset"),
    "password_reset_completed": ("account", "Reset their password"),
    "email_sent": ("account", "Sent an email: {subject}"),
    "email_failed": ("account", "An email failed to send: {subject}"),
    "application_started": ("applications", "Started the {service} intake"),
    "application_continued": ("applications", "Continued the {service} intake"),
    "application_submitted": ("applications", "Submitted the {service} application to OG"),
    "application_status_changed": ("applications", "Application status changed from {from_label} to {to_label} ({service})"),
    "application_reopened": ("applications", "OG reopened the {service} application for customer editing"),
    "application_editing_resumed": ("applications", "Customer resumed editing the {service} application"),
    "application_resubmitted": ("applications", "Customer resubmitted the {service} application to OG"),
    "spouse_supplement_completed": ("applications", "Completed the additional spouse information (Form I-130A) — {service}"),
    "application_relocked": ("applications", "OG closed editing on the {service} application"),
    "ds260_ready_for_ceac": ("applications", "OG marked the {service} answers ready to be entered in CEAC (this is not a CEAC submission)"),
    "ds260_ceac_status": ("applications", "OG recorded the CEAC status as “{status_label}” ({service})"),
    "ds260_case_data_updated": ("applications", "OG updated the consular case details ({service})"),
    "itin_case_started": ("cases", "ITIN case {case} started for {applicants} applicant(s)"),
    "w7_passport_uploaded": ("documents", "Passport photo page uploaded ({application})"),
    "w7_passport_removed": ("documents", "Passport photo page removed by the customer ({application})"),
    "w7_passport_confirmed": ("applications", "Passport information confirmed by the customer ({application})"),
    "w7_passport_read": ("applications", "OG staff read the passport details; waiting for the customer's confirmation ({application})"),
    "itin_original_choice": ("documents", "Customer chose how the original will reach OG: {choice} ({title})"),
    "itin_original_updated": ("documents", "OG recorded the original document as “{state}” ({title})"),
    "itin_caa_verified": ("documents", "OG (as Certifying Acceptance Agent) recorded the verification of the original: {title}"),
    "itin_reason_confirmed": ("applications", "OG confirmed the W-7 details for {application}"),
    "itin_signature_recorded": ("applications", "OG recorded the Form W-7 signature status as “{state}” ({application})"),
    "itin_stage_changed": ("cases", "ITIN case {case} status changed from {from_label} to {to_label}"),
    "itin_ready_for_irs": ("cases", "OG marked ITIN case {case} ready to send to the IRS (this is not a submission)"),
    "itin_package_sent": ("cases", "OG recorded that the ITIN package for case {case} was mailed to the IRS"),
    "itin_irs_response": ("cases", "OG recorded the IRS response for ITIN case {case}: {outcome}"),
    "tax_case_created": ("cases", "Tax return {year} started"),
    "tax_intake_resumed": ("cases", "Continued the {year} tax return"),
    "tax_submitted": ("cases", "Sent the {year} tax information to OG (this is not a filing)"),
    "tax_resubmitted": ("cases", "Re-sent the updated {year} tax information to OG"),
    "tax_price_calculated": ("cases", "Estimated preparation fee calculated for the {year} return ({mode})"),
    "tax_discount_applied": ("cases", "Returning client discount applied ({percent}%)"),
    "tax_price_confirmed": ("cases", "OG confirmed the preparation fee for the {year} return"),
    "tax_price_revised": ("cases", "OG revised the preparation fee for the {year} return"),
    "tax_price_acknowledged": ("cases", "Customer acknowledged the updated preparation fee ({year})"),
    "tax_info_requested": ("cases", "OG asked for more information on the {year} return"),
    "tax_reopened": ("cases", "OG reopened the {year} return for customer editing"),
    "tax_status_changed": ("cases", "{year} tax return status changed from {from_label} to {to_label}"),
    "tax_completed": ("cases", "The {year} tax return was marked completed"),
    "tax_doc_replaced": ("documents", "A tax document was replaced ({title})"),
    "tax_bank_viewed": ("admin", "OG staff viewed the refund bank details of the {year} return"),
    "tax_price_rule_updated": ("admin", "A tax pricing rule was updated ({year}): {rule}"),
    "admin_info_requested": ("applications", "OG requested additional information ({service})"),
    "document_uploaded": ("documents", "Uploaded document “{filename}” ({service})"),
    "document_removed": ("documents", "Removed document “{filename}” ({service})"),
    "course_enrolled": ("academy", "Enrolled in {course}"),
    "course_access_granted": ("academy", "Course access granted for {course} ({access_source})"),
    "course_access_extended": ("academy", "Course access extended for {course}"),
    "course_access_revoked": ("academy", "Course access revoked for {course}"),
    "course_access_restored": ("academy", "Course access restored for {course}"),
    "course_activated_from_payment": ("academy", "Course access activated for {course} after payment ({amount})"),
    "payment_price_estimated": ("payments", "Estimated price set for {service}: {amount}"),
    "payment_price_confirmed": ("payments", "Final price confirmed for {service}: {amount}"),
    "payment_price_changed": ("payments", "Price changed for {service}: {from} → {to}"),
    "payment_requested": ("payments", "Payment requested for {service}: {amount}"),
    "payment_request_canceled": ("payments", "Payment request canceled for {service}"),
    "square_payment_initiated": ("payments", "Card payment started for {service}: {amount}"),
    "payment_completed": ("payments", "Payment received for {service}: {amount} ({method})"),
    "payment_failed": ("payments", "Payment attempt failed for {service}: {amount}"),
    "manual_payment_recorded": ("payments", "OG recorded a {method} payment for {service}: {amount}"),
    "manual_payment_requested": ("payments", "Customer chose to pay by {method} for {service}: {amount} (awaiting OG confirmation)"),
    "manual_payment_confirmed": ("payments", "OG confirmed a {method} payment for {service}: {amount}"),
    "manual_payment_canceled": ("payments", "OG canceled a pending {method} payment for {service}: {amount}"),
    "payment_refunded": ("payments", "Payment refunded for {service}: {amount}"),
    "payment_partially_refunded": ("payments", "Payment partially refunded for {service}: {amount}"),
    "refund_failed": ("payments", "A refund attempt failed for {service}"),
    "course_started": ("academy", "Started {course}"),
    "course_completed": ("academy", "Completed {course}"),
    "final_exam_completed": ("academy", "Completed the final exam for {course}"),
    "certificate_issued": ("academy", "Certificate issued for {course}"),
    "certificate_revoked": ("academy", "Certificate revoked for {course}"),
    "certificate_reissued": ("academy", "Certificate reissued for {course}"),
    "admin_note_added": ("admin", "An admin added an internal note"),
    "person_conflict_resolved": ("cases", "Different information was resolved: {fact} ({application})"),
    "case_created": ("cases", "Case {case} created: {title}"),
    "case_status_changed": ("cases", "Case {case} status changed from {from_label} to {to_label}"),
    "case_person_added": ("cases", "{person} was added to the case"),
    "application_added_to_case": ("cases", "Application {application} ({form}) was added to the case"),
    "case_document_requested": ("cases", "Document requested: {title}{for_person}"),
    "case_document_uploaded": ("cases", "Document uploaded for “{title}”: {filename}"),
    "case_document_reused": ("cases", "Document already in the case: “{title}” uses {filename}"),
    "case_document_under_review": ("cases", "Document under review: {title}"),
    "case_document_accepted": ("cases", "Document accepted: {title}"),
    "case_document_replacement_requested": ("cases", "Replacement requested: {title}"),
    "case_document_withdrawn": ("cases", "Document requirement withdrawn: {title}"),
    "case_document_removed": ("cases", "Document removed: {filename}"),
    "case_note_added": ("admin", "An admin added an internal case note"),
}
FILTER_GROUPS = (
    ("all", "All"),
    ("applications", "Applications"),
    ("documents", "Documents"),
    ("academy", "Academy"),
    ("payments", "Payments"),
    ("account", "Account"),
    ("cases", "Cases"),
    ("admin", "Admin actions"),
)


def log_event(customer_id, event_type, *, actor="customer", actor_id=None, entity=None, meta=None, commit=True, case_id=None):
    """Append one event. Never raises into the caller's flow: logging must not be
    able to break a customer's application."""
    try:
        if actor == "customer" and actor_id is None:
            actor_id = customer_id
        if actor == "admin" and actor_id is None and has_request_context():
            actor_id = session.get("admin_user_id")
        if case_id is None and entity and entity[0] == "submission":  # an application event also belongs to its case's timeline
            from app.models import FormSubmission

            sub = db.session.get(FormSubmission, entity[1])
            case_id = sub.case_id if sub is not None else None
        event = ActivityEvent(
            case_id=case_id,
            customer_id=customer_id,
            event_type=event_type,
            actor_type=actor,
            actor_id=actor_id,
            entity_type=entity[0] if entity else None,
            entity_id=entity[1] if entity else None,
            metadata_json=json.dumps(meta, ensure_ascii=False) if meta else None,
        )
        db.session.add(event)
        if commit:
            db.session.commit()
        return event
    except Exception:  # noqa: BLE001
        db.session.rollback()
        return None


def _meta(event):
    try:
        return json.loads(event.metadata_json) if event.metadata_json else {}
    except ValueError:
        return {}


class _Safe(dict):
    def __missing__(self, key):
        return "—"


def describe(event):
    """(group, sentence) for an event. Unknown types still render something sensible."""
    group, template = EVENTS.get(event.event_type, ("account", event.event_type.replace("_", " ").capitalize()))
    try:
        sentence = template.format_map(_Safe(_meta(event)))
    except (ValueError, KeyError):
        sentence = template
    return group, sentence


def group_of(event_type):
    return EVENTS.get(event_type, ("account", ""))[0]


def timeline(customer_id, group="all", limit=200):
    query = ActivityEvent.query.filter_by(customer_id=customer_id)
    if group == "admin":
        query = query.filter(ActivityEvent.actor_type == "admin")
    elif group in ("applications", "documents", "academy", "account", "cases"):
        types = [t for t, (g, _) in EVENTS.items() if g == group]
        query = query.filter(ActivityEvent.event_type.in_(types))
    events = query.order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc()).limit(limit).all()
    return [(e, describe(e)[1]) for e in events]
