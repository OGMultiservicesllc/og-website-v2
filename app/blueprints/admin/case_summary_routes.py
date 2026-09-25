"""Case Summary PDF download endpoints — Admin/staff only, enforced server-side on every route (never
just a hidden button). A customer can never reach another customer's PDF by editing a URL: every route
loads the underlying record by id and, where relevant, checks it actually belongs to the case it claims —
there is no path here a signed-in customer session can use at all, since every route is @admin_required.
"""
from flask import Response, abort

from app.auth import admin_required
from app.blueprints.admin.routes import admin_bp
from app.case_summary import engine, presenters


def _send(doc, suffix="Case_Summary"):
    if doc is None:
        abort(404)
    pdf_bytes = engine.render(doc)
    filename = engine.safe_filename(doc.case_number, suffix)
    return Response(pdf_bytes, mimetype="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@admin_bp.route("/case-summary/tax/<int:tax_id>.pdf")
@admin_required
def case_summary_tax(tax_id):
    from app.models import TaxCaseData

    tax = TaxCaseData.query.get_or_404(tax_id)
    return _send(presenters.tax_doc(tax))


@admin_bp.route("/case-summary/driver-license/<int:dl_id>.pdf")
@admin_required
def case_summary_dl(dl_id):
    from app.models import DlCaseData

    dl = DlCaseData.query.get_or_404(dl_id)
    return _send(presenters.driver_license_doc(dl))


@admin_bp.route("/case-summary/consent-travel/<int:ct_id>.pdf")
@admin_required
def case_summary_ct(ct_id):
    from app.models import ConsentTravelCaseData

    ct = ConsentTravelCaseData.query.get_or_404(ct_id)
    return _send(presenters.consent_travel_doc(ct))


@admin_bp.route("/case-summary/itin/<int:case_id>.pdf")
@admin_required
def case_summary_itin(case_id):
    from app.models import Case

    case = Case.query.get_or_404(case_id)
    if case.case_type != "itin_application":
        abort(404)
    return _send(presenters.itin_doc(case))


@admin_bp.route("/case-summary/application/<int:submission_id>.pdf")
@admin_required
def case_summary_application(submission_id):
    from app.models import FormSubmission

    submission = FormSubmission.query.get_or_404(submission_id)
    return _send(presenters.generic_intake_doc(submission))
