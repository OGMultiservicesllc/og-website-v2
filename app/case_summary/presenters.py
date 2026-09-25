"""Per-intake Case Summary presenters. Each function returns a `CaseSummaryDoc` (app/case_summary/blocks.py)
built ENTIRELY from existing structured case data and existing service helpers (each dedicated module's
own `admin_summary()`, or the generic Smart-Intake adapter in generic_form.py) — no field-extraction
logic is duplicated here, only reorganized into the PDF's section order and enriched with
Documents/Pricing/Notes, which no `admin_summary()` already includes end-to-end.

`build_for_case(case)` is the single entry point Admin routes call — it dispatches on `case.case_type`
and, for the generic Smart-Intake case types, on which application the customer's route asked for.
Returns `None` (never a fabricated summary) when a case type has no presenter yet — see
UNSUPPORTED_CASE_TYPES below and the note in app/blueprints/admin/case_summary_routes.py.
"""
from app.case_summary import common
from app.case_summary.blocks import CaseSummaryDoc, DocumentsBlock, Field, KeyValueBlock, Section


def _rows_to_fields(rows):
    return [Field(label, value) for label, value in rows]


def _sections_from_admin_summary(admin_sections):
    """Adapts the {"sections": [{"title","rows":[(label,value)]}]} shape every dedicated module's
    admin_summary() already returns (app/tax/summary.py, app/consent_travel/summary.py,
    app/driver_license/summary.py) into this engine's Section/KeyValueBlock IR, one-for-one, with no
    change to the underlying label/value pairs those modules already computed."""
    out = []
    for s in admin_sections:
        rows = s.get("rows") or []
        if not rows:
            continue
        out.append(Section(title=s["title"], blocks=[KeyValueBlock(fields=_rows_to_fields(rows))]))
    return out


# ------------------------------------------------------------------ Consent to Travel
def consent_travel_doc(ct):
    from app.consent_travel import summary as ct_summary

    data = ct_summary.admin_summary(ct)
    sections = _sections_from_admin_summary(data["sections"])
    case = ct.case
    doc_block = common.documents_block(case, source_key="consent_travel")
    if doc_block:
        sections.append(Section(title="Documents", blocks=[doc_block]))
    charge = common.charge_for_case(case)
    price_block = common.pricing_block_for_charge(charge)
    if price_block:
        sections.append(Section(title="Pricing / Payment", blocks=[price_block]))
    sections.append(Section(title="Notes", blocks=[common.internal_notes_block(case)]))
    from app.models import CT_STATUS_EN

    info = common.case_info(case, application_label="Consent to Travel Authorization", status_label=CT_STATUS_EN.get(ct.status, ct.status), submitted_at=ct.submitted_at)
    return CaseSummaryDoc(service_title="Consent to Travel Authorization", sections=sections, **info)


# ------------------------------------------------------------------ Tax
def tax_doc(tax):
    from app.tax import summary as tax_summary

    data = tax_summary.admin_summary(tax)
    sections = _sections_from_admin_summary(data["sections"])
    if data.get("flags"):
        from app.case_summary.blocks import WarningBlock

        sections.append(Section(title="Review Flags", blocks=[WarningBlock(items=[f["en"] if isinstance(f, dict) else str(f) for f in data["flags"]])]))
    case = tax.case
    doc_block = common.documents_block(case, source_key="tax")
    if doc_block:
        sections.append(Section(title="Documents", blocks=[doc_block]))
    charge = common.charge_for_case(case)
    price_block = common.pricing_block_for_charge(charge)
    if price_block:
        sections.append(Section(title="Pricing / Payment", blocks=[price_block]))
    sections.append(Section(title="Notes", blocks=[common.internal_notes_block(case)]))
    from app.models import TAX_STATUS_EN

    info = common.case_info(case, application_label=f"Tax Return — Tax Year {tax.tax_year}", status_label=TAX_STATUS_EN.get(tax.status, tax.status), submitted_at=tax.submitted_at)
    return CaseSummaryDoc(service_title=f"Individual Tax Preparation — Tax Year {tax.tax_year}", sections=sections, **info)


# ------------------------------------------------------------------ NJ Driver License
def driver_license_doc(dl):
    from app.driver_license import summary as dl_summary

    data = dl_summary.admin_summary(dl)
    sections = _sections_from_admin_summary(data["sections"])
    if data.get("flags"):
        from app.case_summary.blocks import WarningBlock

        sections.append(Section(title="Review Flags", blocks=[WarningBlock(items=[f["en"] if isinstance(f, dict) else str(f) for f in data["flags"]])]))
    case = dl.case
    doc_block = common.documents_block(case, source_key="nj_dl")
    if doc_block:
        sections.append(Section(title="Documents", blocks=[doc_block]))
    charge = common.charge_for_case(case)
    price_block = common.pricing_block_for_charge(charge)
    if price_block:
        sections.append(Section(title="Pricing / Payment", blocks=[price_block]))
    sections.append(Section(title="Notes", blocks=[common.internal_notes_block(case)]))
    from app.models import DL_STATUS_EN

    info = common.case_info(case, application_label="NJ Driver License Assistance", status_label=DL_STATUS_EN.get(dl.status, dl.status), submitted_at=dl.submitted_at)
    return CaseSummaryDoc(service_title="NJ Driver License Assistance", sections=sections, **info)


# ------------------------------------------------------------------ ITIN / W-7 (case-level: one or more applicants)
def itin_doc(case):
    from app import itin
    from app.case_summary import generic_form

    applicants = itin.applicants(case)  # [{"submission": FormSubmission, ...}] — the case's own existing helper
    if not applicants:
        return None
    sections = []
    cd = getattr(case, "itin_data", None)
    if cd is not None:
        rows = [("Tax Year", cd.tax_year), ("New or Renewal", {"new": "New ITIN", "renew": "Renew existing ITIN"}.get(cd.request_kind, cd.request_kind))]
        fields = _rows_to_fields([r for r in rows if r[1]])
        if fields:
            sections.append(Section(title="ITIN Case Information", blocks=[KeyValueBlock(fields=fields)]))
    from app.case_types import role_label
    from app.models import ApplicationRole

    for entry in applicants:
        sub = entry["submission"]
        ar = ApplicationRole.query.filter_by(submission_id=sub.id).first()
        role = role_label(ar.role_key, "en") if ar else "ITIN Applicant"
        applicant_sections = generic_form.build_sections(sub.form, sub, "en")
        name = ar.person.full_name if ar and ar.person else "Applicant"
        blocks = []
        for s in applicant_sections:
            blocks.extend(s.blocks)
        doc_block = common.documents_block(case, person_filter={ar.person_id} if ar else None)
        if doc_block:
            blocks.append(doc_block)
        sections.append(Section(title=f"{role.upper()} — {name}", person_role=role.upper(), blocks=blocks or [KeyValueBlock(fields=[])]))

    charge = common.charge_for_case(case)
    price_block = common.pricing_block_for_charge(charge)
    if price_block:
        sections.append(Section(title="Pricing / Payment", blocks=[price_block]))
    sections.append(Section(title="Notes", blocks=[common.internal_notes_block(case)]))
    info = common.case_info(case, application_label="ITIN Application (Form W-7)", status_label=case.status_label, submitted_at=None)
    return CaseSummaryDoc(service_title="ITIN Application — Form W-7", sections=sections, **info)


# ------------------------------------------------------------------ Generic Smart-Intake applications (I-90, N-400,
# I-130/I-130A, I-485, I-864, I-765, I-751, DS-260)
def generic_intake_doc(submission):
    from app.case_summary import generic_form

    if submission.form is None:
        return None
    sections = generic_form.build_sections(submission.form, submission, "en")
    case = submission.case
    if case is not None:
        # Not scoped to just this one application's own requirements — a case can hold several related
        # applications (e.g. I-130 + I-485 + I-765 in one Adjustment of Status case), and showing the
        # WHOLE case's document picture is what OG staff preparing any one of them actually need.
        doc_block = common.documents_block(case)
        if doc_block:
            sections.append(Section(title="Documents", blocks=[doc_block]))
        charge = common.charge_for_case(case)
        price_block = common.pricing_block_for_charge(charge)
        if price_block:
            sections.append(Section(title="Pricing / Payment", blocks=[price_block]))
        sections.append(Section(title="Notes", blocks=[common.internal_notes_block(case, submission)]))
        info = common.case_info(case, application_label=generic_form.application_label(submission.form),
                                status_label=_submission_status_label(submission), submitted_at=submission.submitted_at)
    else:
        info = {
            "case_number": submission.code, "customer_name": submission.student.name if submission.student else "—",
            "application_label": generic_form.application_label(submission.form), "status_label": _submission_status_label(submission),
            "submitted_at": submission.submitted_at.strftime("%b %d, %Y") if submission.submitted_at else None,
            "updated_at": submission.updated_at.strftime("%b %d, %Y") if submission.updated_at else None,
        }
    return CaseSummaryDoc(service_title=submission.form.name_admin, sections=sections, **info)


def _submission_status_label(submission):
    from app.intake_engine import status_label

    return status_label(submission)
