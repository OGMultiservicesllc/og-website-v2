"""Admin: Cases (the customer's overall matter) with People, Applications, Document Vault, Activity, Notes.

Named `client cases` / `ocase_*` on purpose: the Academy already owns /admin/cases/... and case_* for its
Case Simulations. Every action re-reads the case and its children from the database and checks that the child
belongs to THAT case, so an id in a URL is never trusted on its own.
"""

import os

from flask import abort, flash, redirect, render_template, request, send_file, session, url_for

from app import case_documents as vault
from app import cases as case_svc
from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import SERVICE_GROUPS, admin_bp
from app.case_types import CASE_TYPES, DOCUMENT_CATEGORIES, RELATIONSHIPS, ROLE_LABELS
from app.extensions import db
from app.intake_engine import progress_for, status_key, status_label
from app.models import (
    CASE_STATUSES,
    ApplicationRole,
    Case,
    CaseDocument,
    CaseNote,
    CasePerson,
    DocumentRequirement,
    FormSubmission,
    Student,
)
from app.uploads import course_media_full_path

TABS = (("overview", "Overview"), ("people", "People"), ("applications", "Applications"), ("documents", "Documents"), ("activity", "Activity"), ("notes", "Notes"))


def _admin_name():
    return session.get("admin_username") or session.get("admin_name") or "OG staff"


def _admin_id():
    return session.get("admin_user_id")


def _case_or_404(case_id):
    return Case.query.get_or_404(case_id)


def _csrf():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)


def _back(case, tab):
    return redirect(url_for("admin.ocase_detail", case_id=case.id, tab=tab))


# ------------------------------------------------------------------ list / create
@admin_bp.route("/client-cases")
@admin_required
def ocase_list():
    """The generic Cases list — reached WITHOUT a `service` filter it is the site-wide "All Cases" view
    (e.g. from global search or an id-only link). Only the sidebar's Immigration -> Cases link passes
    `service=Immigration`, scoping this SAME route/template to just that service's own case types —
    reusing SERVICE_GROUPS (app/blueprints/admin/routes.py), the exact taxonomy the sidebar and the
    Dashboard's "Cases by Service" chart already use, so they can never disagree about what "Immigration"
    means. Every other service already has its OWN dedicated case list (Tax/ITIN/DL/Notary), so this is
    the only place such a filter is needed."""
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    ctype = request.args.get("type", "")
    service = request.args.get("service", "")
    query = Case.query.join(Student, Student.id == Case.customer_id)
    if status:
        query = query.filter(Case.status == status)
    if ctype:
        query = query.filter(Case.case_type == ctype)
    if service:
        service_types = [k for k, v in SERVICE_GROUPS.items() if v == service]
        query = query.filter(Case.case_type.in_(service_types))
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Student.name.ilike(like), Student.email.ilike(like), Case.case_number.ilike(like), Case.title.ilike(like)))
    cases = query.order_by(Case.updated_at.desc(), Case.id.desc()).all()
    rows = []
    for c in cases:
        counts = vault.requirement_counts(c)
        rows.append({"c": c, "apps": len(c.applications), "people": len(c.people), "open_docs": len(vault.open_customer_actions(c)),
                     "review_docs": counts.get("uploaded", 0) + counts.get("under_review", 0), "activity": case_svc.last_activity(c)})
    customers = Student.query.order_by(Student.name).all()
    # Only offer case types that actually belong to this service in the "Type" filter dropdown, so it
    # can never suggest filtering an Immigration list down to a NJ Driver License case type. "other" is
    # kept regardless — it's the template's own fallback key for an unrecognized case_type, not a real
    # option a customer's case would ever have.
    if service:
        types_for_ui = {k: v for k, v in CASE_TYPES.items() if SERVICE_GROUPS.get(k) == service}
        types_for_ui.setdefault("other", CASE_TYPES["other"])
    else:
        types_for_ui = CASE_TYPES
    return render_template("admin/client_cases_list.html", rows=rows, q=q, status=status, ctype=ctype, service=service,
                          statuses=CASE_STATUSES, types=types_for_ui, customers=customers)


@admin_bp.route("/client-cases/new", methods=["POST"])
@admin_required
def ocase_new():
    _csrf()
    customer = Student.query.get_or_404(request.form.get("customer_id", type=int) or 0)
    case_type = request.form.get("case_type") if request.form.get("case_type") in CASE_TYPES else "other"
    title = request.form.get("title", "").strip() or None
    case = case_svc.create_case(customer, case_type, title, origin="admin", actor="admin", actor_id=_admin_id())
    flash(f"Case {case.case_number} created.", "success")
    return redirect(url_for("admin.ocase_detail", case_id=case.id))


# ------------------------------------------------------------------ detail
@admin_bp.route("/client-cases/<int:case_id>")
@admin_required
def ocase_detail(case_id):
    case = _case_or_404(case_id)
    tab = request.args.get("tab", "overview")
    if tab not in dict(TABS):
        tab = "overview"
    apps = []
    for s in case.applications:
        apps.append({
            "s": s, "key": status_key(s), "label": status_label(s),
            "percent": 100 if (s.is_complete or s.status == "reopened") else (progress_for(s.form, s)["percent"] if s.form.is_service_intake else None),
            "roles": [(r.person, r.role_key) for r in ApplicationRole.query.filter_by(submission_id=s.id).all()],
        })
    people = []
    for p in case.people:
        people.append({
            "p": p, "roles": [(r.submission, r.role_key) for r in p.roles],
            "facts": case_svc.facts_for_review(p, lang="en", reveal=False) if tab == "people" else [],
        })
    unassigned = (FormSubmission.query.filter(FormSubmission.student_id == case.customer_id, db.or_(FormSubmission.case_id.is_(None), FormSubmission.case_id != case.id))
                  .order_by(FormSubmission.id).all())
    unassigned = [s for s in unassigned if s.form.is_service_intake]
    counts = vault.requirement_counts(case)
    return render_template(
        "admin/client_case_detail.html", case=case, tab=tab, tabs=TABS, apps=apps, people=people, unassigned=unassigned, counts=counts,
        groups=vault.requirement_groups(case), vault_docs=vault.vault_documents(case), app_files=vault.application_files(case) if tab == "documents" else [],
        events=case_svc.case_timeline(case, 300) if tab == "activity" else case_svc.case_timeline(case, 6), last_activity=case_svc.last_activity(case),
        statuses=CASE_STATUSES, types=CASE_TYPES, relationships=RELATIONSHIPS, roles=ROLE_LABELS, categories=DOCUMENT_CATEGORIES,
        req_status_tone=vault.STATUS_TONE, open_actions=len(vault.open_customer_actions(case)),
    )


@admin_bp.route("/client-cases/<int:case_id>/status", methods=["POST"])
@admin_required
def ocase_status(case_id):
    from datetime import datetime

    from app.models import CASE_STATUS_LABELS

    _csrf()
    case = _case_or_404(case_id)
    new = request.form.get("status")
    if new in CASE_STATUS_LABELS and new != case.status:
        old = case.status
        case.status = new
        case.closed_at = datetime.utcnow() if new == "closed" else None
        db.session.commit()
        case_svc.case_event(case, "case_status_changed", actor="admin", actor_id=_admin_id(), meta={"from_label": CASE_STATUS_LABELS[old], "to_label": CASE_STATUS_LABELS[new]})
        if new == "completed":
            try:
                from app.email_service import send_transactional_email

                student = case.customer
                send_transactional_email(student, "service_completed", student.preferred_language or "en",
                                         ref={"kind": "case", "id": case.id}, related_type="case", related_id=case.id)
            except Exception:  # noqa: BLE001
                import logging

                logging.getLogger("og_email").exception("[cases] service_completed email failed to queue for case %s", case.id)
        flash("Case status updated.", "success")
    return _back(case, "overview")


@admin_bp.route("/client-cases/<int:case_id>/notes", methods=["POST"])
@admin_required
def ocase_note(case_id):
    _csrf()
    case = _case_or_404(case_id)
    body = request.form.get("body", "").strip()
    if body:
        db.session.add(CaseNote(case_id=case.id, body=body[:4000], author_name=_admin_name()))
        db.session.commit()
        case_svc.case_event(case, "case_note_added", actor="admin", actor_id=_admin_id())
    return _back(case, "notes")


# ------------------------------------------------------------------ people / facts / applications
@admin_bp.route("/client-cases/<int:case_id>/people/new", methods=["POST"])
@admin_required
def ocase_person_new(case_id):
    _csrf()
    case = _case_or_404(case_id)
    given, family = request.form.get("given_name", "").strip(), request.form.get("family_name", "").strip()
    if not (given or family):
        flash("Enter a name.", "error")
    else:
        case_svc.add_person(case, given, family, request.form.get("relationship_key", "other"), actor="admin", actor_id=_admin_id())
        flash("Person added. They have no OG login and no access to this case.", "success")
    return _back(case, "people")


@admin_bp.route("/client-cases/<int:case_id>/people/<int:person_id>/edit", methods=["POST"])
@admin_required
def ocase_person_edit(case_id, person_id):
    _csrf()
    case = _case_or_404(case_id)
    person = CasePerson.query.filter_by(id=person_id, case_id=case.id).first_or_404()
    person.given_name = request.form.get("given_name", "").strip()[:120] or person.given_name
    person.family_name = request.form.get("family_name", "").strip()[:120] or person.family_name
    rel = request.form.get("relationship_key")
    if not person.is_customer and rel in RELATIONSHIPS and rel != "self":
        person.relationship_key = rel
    db.session.commit()
    return _back(case, "people")


@admin_bp.route("/client-cases/<int:case_id>/people/<int:person_id>/facts/confirm", methods=["POST"])
@admin_required
def ocase_facts_confirm(case_id, person_id):
    _csrf()
    case = _case_or_404(case_id)
    person = CasePerson.query.filter_by(id=person_id, case_id=case.id).first_or_404()
    keys = request.form.getlist("fact_key") or None
    n = case_svc.confirm_facts(person, keys, actor=f"OG: {_admin_name()}")
    flash(f"{n} fact(s) marked as confirmed.", "success")
    return _back(case, "people")


@admin_bp.route("/client-cases/<int:case_id>/applications/add", methods=["POST"])
@admin_required
def ocase_application_add(case_id):
    _csrf()
    case = _case_or_404(case_id)
    sub = FormSubmission.query.get_or_404(request.form.get("submission_id", type=int) or 0)
    try:
        case_svc.attach_application(case, sub, actor="admin", actor_id=_admin_id())
        flash(f"Application {sub.code} is now part of {case.case_number}.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return _back(case, "applications")


# ------------------------------------------------------------------ documents: requirements
@admin_bp.route("/client-cases/<int:case_id>/requirements/new", methods=["POST"])
@admin_required
def ocase_requirement_new(case_id):
    """+ Request Document: the customer sees it under My Account > Cases > Documents."""
    _csrf()
    case = _case_or_404(case_id)
    person = None
    if request.form.get("person_id", type=int):
        person = CasePerson.query.filter_by(id=request.form.get("person_id", type=int), case_id=case.id).first()
        if person is None:
            abort(400)
    ids = request.form.getlist("application_ids", type=int)
    apps = FormSubmission.query.filter(FormSubmission.id.in_(ids or [-1]), FormSubmission.case_id == case.id).all()
    category = request.form.get("category") if request.form.get("category") in DOCUMENT_CATEGORIES else "other"
    title = request.form.get("title", "").strip() or DOCUMENT_CATEGORIES[category]["en"]
    vault.create_requirement(case, title, category=category, person=person, applications=apps, customer_message=request.form.get("customer_message"),
                             internal_note=request.form.get("internal_note"), source="admin", actor="admin", actor_id=_admin_id(), created_by=_admin_name())
    flash("Document requested. The customer will see it in their account.", "success")
    return _back(case, "documents")


def _requirement(case, requirement_id):
    return DocumentRequirement.query.filter_by(id=requirement_id, case_id=case.id).first_or_404()


@admin_bp.route("/client-cases/<int:case_id>/requirements/<int:requirement_id>/<action>", methods=["POST"])
@admin_required
def ocase_requirement_action(case_id, requirement_id, action):
    _csrf()
    case = _case_or_404(case_id)
    req = _requirement(case, requirement_id)
    try:
        if action == "review":
            vault.mark_under_review(req, _admin_name(), _admin_id())
        elif action == "accept":
            vault.accept(req, _admin_name(), _admin_id())
        elif action == "replace":
            vault.request_replacement(req, request.form.get("message", ""), _admin_name(), _admin_id())
        elif action == "withdraw":
            vault.withdraw_requirement(req, actor="admin", actor_id=_admin_id())
        elif action == "upload":
            f = request.files.get("file")
            error = vault.validate_upload(f) if f else "Choose a file."
            if error:
                raise ValueError(error)
            vault.upload_for_requirement(req, f, uploaded_by="admin", uploaded_by_id=_admin_id())
        else:
            abort(404)
    except ValueError as exc:
        flash(str(exc), "error")
    return _back(case, "documents")


@admin_bp.route("/client-cases/<int:case_id>/documents/<int:document_id>")
@admin_required
def ocase_document_file(case_id, document_id):
    case = _case_or_404(case_id)
    doc = CaseDocument.query.filter_by(id=document_id, case_id=case.id).first_or_404()
    path = course_media_full_path(doc.stored_filename)
    if not os.path.isfile(path):
        abort(404)
    inline = request.args.get("inline") == "1" and (doc.mime_type or "") in ("application/pdf", "image/jpeg", "image/png", "image/webp")
    response = send_file(path, mimetype=doc.mime_type or "application/octet-stream", as_attachment=not inline, download_name=doc.original_filename, conditional=True)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@admin_bp.route("/client-cases/<int:case_id>/documents/<int:document_id>/delete", methods=["POST"])
@admin_required
def ocase_document_delete(case_id, document_id):
    _csrf()
    case = _case_or_404(case_id)
    doc = CaseDocument.query.filter_by(id=document_id, case_id=case.id).first_or_404()
    vault.remove_document(doc, actor="admin", actor_id=_admin_id())
    flash("Document removed.", "success")
    return _back(case, "documents")
