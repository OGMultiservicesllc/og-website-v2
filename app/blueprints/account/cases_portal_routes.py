"""My OG Account > Cases: a minimal customer view of a case (overview, applications, documents).

Authorization is always decided on the server from the signed-in customer: a case, requirement or document
id in a URL is only ever looked up THROUGH the customer's own cases (`owned_case` / `owned_document` /
`owned_requirement`), so someone else's id answers 404 exactly like a missing one. People listed in a case
(a spouse, a sponsor) have no login and gain nothing by being listed.
"""

import os

from flask import abort, flash, redirect, render_template, request, send_file, url_for

from app import case_documents as vault
from app import cases as case_svc
from app.blueprints.account.portal_routes import application_cards_single
from app.blueprints.account.routes import account_bp
from app.auth import validate_csrf
from app.case_types import category_label, domain_of, role_label, type_title
from app.extensions import db
from app.i18n import get_text
from app.intake_engine import status_key, status_label
from app.models import ApplicationRole, Case, CaseDocument, CASE_STATUS_LABELS
from app.models.itin import ORIGINAL_EN, ORIGINAL_ES
from app.ratelimit import allow
from app.student_auth import current_student, student_required
from app.uploads import course_media_full_path

CASE_STATUS_ES = {"open": "Abierto", "in_review": "En revisión", "waiting_client": "Esperando al cliente", "completed": "Completado", "closed": "Cerrado"}


def case_status_text(case, lang):
    return CASE_STATUS_ES.get(case.status, case.status) if lang == "es" else CASE_STATUS_LABELS.get(case.status, case.status)


def _case_or_404(case_id):
    case = case_svc.owned_case(current_student(), case_id)
    if case is None:
        abort(404)
    return case


@account_bp.route("/cases")
@student_required
def my_cases(lang):
    student = current_student()
    cases = Case.query.filter_by(customer_id=student.id).order_by(Case.updated_at.desc(), Case.id.desc()).all()
    cases = [c for c in cases if not (c.status == "closed" and not c.applications)]  # emptied shells stay out of the customer's list
    cards = [{"case": c, "type": type_title(c.case_type, lang), "status": case_status_text(c, lang), "apps": len(c.applications),
              "actions": len(vault.open_customer_actions(c)), "domain": domain_of(c.case_type, lang)} for c in cases]
    return render_template("account/cases.html", cards=cards, section="cases")


@account_bp.route("/cases/<int:case_id>")
@student_required
def my_case_detail(lang, case_id):
    case = _case_or_404(case_id)
    apps = []
    consular_dash, add_applicant_url = None, None
    if case.case_type == "consular_processing":
        from app import consular
        from app.models import Service

        consular_dash = consular.dashboard(case, lang)
        svc = Service.query.filter_by(slug="immigrant-visa-ds-260").first()
        if svc is not None and svc.category is not None and svc.is_published:
            add_applicant_url = url_for("public.service_start", lang=lang, category_slug=svc.category.slug, service_slug=svc.slug, new=1)
    itin_dash = None
    if case.case_type == "itin_application":
        from app import itin

        itin_dash = itin.dashboard(case, lang)
    tax_dash = None
    if case.case_type == "tax_return":
        from app.tax import portal as tax_portal

        tax_dash = tax_portal.dashboard(case, lang)
    dl_dash = None
    if case.case_type == "nj_driver_license":
        from app.driver_license import portal as dl_portal

        dl_dash = dl_portal.dashboard(case, lang)
    ct_dash = None
    if case.case_type == "consent_travel":
        from app.consent_travel import portal as ct_portal

        ct_dash = ct_portal.dashboard(case, lang)
    applicant_names = {a["submission"].id: a["person"].full_name for a in ((consular_dash or itin_dash) or {}).get("applicants", []) if a["person"] is not None}
    for s in case.applications:
        card = application_cards_single(s, lang)
        roles = [role_label(r.role_key, lang) for r in ApplicationRole.query.filter_by(submission_id=s.id).all() if r.person.is_customer]
        apps.append({"s": s, "card": card, "label": status_label(s, lang), "key": status_key(s), "roles": roles,
                     "title": (f"{applicant_names[s.id]} — {s.form.source_form_name}" if s.id in applicant_names else (s.service.title(lang) if s.service else s.form.title(lang))), "form_name": s.form.source_form_name})
    def _status_and_tone(r):
        override = vault.status_override(r, lang)
        return override if override else (vault.status_label(r.status, lang), vault.STATUS_TONE[r.status])

    groups = []
    docs = vault.vault_documents(case)
    for g in vault.requirement_groups(case):
        person = g["person"]
        groups.append({"person": person, "label": (person.full_name if person else (get_text(lang, "case_general"))),
                       "is_customer": bool(person and person.is_customer),
                       "requirements": [{"r": r, "title": vault.customer_text(r, lang)[0], "message": vault.customer_text(r, lang)[1], "status": _status_and_tone(r)[0], "tone": _status_and_tone(r)[1],
                                         "doc": r.current_document, "category": category_label(r.category, lang),
                                         "can_upload": r.status in vault.CUSTOMER_CAN_UPLOAD,
                                         "can_remove": vault.customer_can_remove(r, r.current_document),
                                         "reusable": [d for d in docs if (not r.person_id or not d.person_id or d.person_id == r.person_id)
                                                      and (r.current_document is None or d.id != r.current_document.id)],
                                         "apps": [a.code for a in r.applications], "track": getattr(r, "itin_track", None),
                                         "confirm_url": _passport_confirm_url(r, lang)} for r in g["requirements"]]})
    return render_template("account/case_detail.html", case=case, type_title=type_title(case.case_type, lang), status_text=case_status_text(case, lang),
                           apps=apps, groups=groups, actions=len(vault.open_customer_actions(case)), section="cases", consular_dash=consular_dash, add_applicant_url=add_applicant_url, itin_dash=itin_dash, tax_dash=tax_dash, dl_dash=dl_dash, ct_dash=ct_dash, domain=domain_of(case.case_type, lang),
                           original_states=(ORIGINAL_EN if lang == "en" else ORIGINAL_ES))


def _passport_confirm_url(req, lang):
    """A passport requirement of a W-7 application links to the confirmation page once a photo is uploaded."""
    if req.rule_key != "w7.passport" or not req.applications:
        return None
    from app.w7_views import passport_url

    return passport_url(req.applications[0], lang)


def _guard_post():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)


@account_bp.route("/cases/<int:case_id>/requirements/<int:requirement_id>/upload", methods=["POST"])
@student_required
def my_case_upload(lang, case_id, requirement_id):
    _guard_post()
    student = current_student()
    case, req = vault.owned_requirement(student, case_id, requirement_id)
    if case is None or req is None:
        abort(404)
    if not allow(f"case-upload:{student.id}", 30, 300):
        flash(get_text(lang, "flash_too_many"), "error")
        return redirect(url_for("account.my_case_detail", lang=lang, case_id=case.id, _anchor="documents"))
    if req.status not in vault.CUSTOMER_CAN_UPLOAD:
        flash(get_text(lang, "case_cannot_upload"), "error")
    else:
        f = request.files.get("file")
        error = vault.validate_upload(f, lang) if f and f.filename else get_text(lang, "case_choose_file")
        if error:
            flash(error, "error")
        else:
            doc = vault.upload_for_requirement(req, f, uploaded_by="customer", uploaded_by_id=student.id)
            if req.rule_key == "w7.passport":
                from app import w7_views

                w7_views.after_upload(req, doc)
            flash(get_text(lang, "case_uploaded"), "success")
    return redirect(url_for("account.my_case_detail", lang=lang, case_id=case.id, _anchor="documents"))


@account_bp.route("/cases/<int:case_id>/requirements/<int:requirement_id>/reuse", methods=["POST"])
@student_required
def my_case_reuse(lang, case_id, requirement_id):
    """Use a document that is already in this case's vault (no second copy of the file)."""
    _guard_post()
    student = current_student()
    case, req = vault.owned_requirement(student, case_id, requirement_id)
    if case is None or req is None:
        abort(404)
    doc = CaseDocument.query.filter_by(id=request.form.get("document_id", type=int) or 0, case_id=case.id).first()
    if doc is None or req.status not in vault.CUSTOMER_CAN_UPLOAD:
        abort(404)
    try:
        vault.attach_existing_document(req, doc, actor="customer", actor_id=student.id)
        flash(get_text(lang, "case_reused"), "success")
    except ValueError:
        abort(404)
    return redirect(url_for("account.my_case_detail", lang=lang, case_id=case.id, _anchor="documents"))


@account_bp.route("/cases/<int:case_id>/requirements/<int:requirement_id>/remove", methods=["POST"])
@student_required
def my_case_remove(lang, case_id, requirement_id):
    _guard_post()
    student = current_student()
    case, req = vault.owned_requirement(student, case_id, requirement_id)
    if case is None or req is None:
        abort(404)
    doc = req.current_document
    if not vault.customer_can_remove(req, doc):
        abort(404)
    if req.rule_key == "w7.passport" and req.applications:  # ITIN: the earlier passport reading must not count as a confirmed passport once the photo is gone
        from app import w7_views

        w7_views.remove_passport(req.applications[0], req, doc, actor_id=student.id)
    else:
        vault.remove_document(doc, actor="customer", actor_id=student.id)
    return redirect(url_for("account.my_case_detail", lang=lang, case_id=case.id, _anchor="documents"))


@account_bp.route("/cases/<int:case_id>/documents/<int:document_id>")
@student_required
def my_case_document(lang, case_id, document_id):
    case, doc = vault.owned_document(current_student(), case_id, document_id)
    if case is None or doc is None:
        abort(404)
    path = course_media_full_path(doc.stored_filename)
    if not os.path.isfile(path):
        abort(404)
    inline = request.args.get("inline") == "1" and (doc.mime_type or "") in ("application/pdf", "image/jpeg", "image/png", "image/webp")
    response = send_file(path, mimetype=doc.mime_type or "application/octet-stream", as_attachment=not inline, download_name=doc.original_filename, conditional=True)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@account_bp.route("/cases/<int:case_id>/requirements/<int:requirement_id>/original", methods=["POST"])
@student_required
def my_case_original(lang, case_id, requirement_id):
    """ITIN: the customer says HOW the physical original will reach OG (mail it or bring it). It records an intention only: an original is never marked received here."""
    _guard_post()
    student = current_student()
    case, req = vault.owned_requirement(student, case_id, requirement_id)
    if case is None or req is None:
        abort(404)
    track = getattr(req, "itin_track", None)
    choice = request.form.get("choice")
    if track is None or not track.original_required or choice not in ("mail", "in_person") or track.original_state not in ("required", "will_mail", "will_bring"):
        abort(404)
    track.delivery_choice = choice
    track.original_state = "will_mail" if choice == "mail" else "will_bring"
    db.session.commit()
    from app.itin import log_case_event

    log_case_event(student.id, "itin_original_choice", case, {"choice": ("mail" if choice == "mail" else "bring in person"), "title": req.title})
    return redirect(url_for("account.my_case_detail", lang=lang, case_id=case.id, _anchor=f"req-{req.id}"))
