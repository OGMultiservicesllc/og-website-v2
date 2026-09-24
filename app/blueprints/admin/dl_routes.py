"""Admin side of the NJ Driver License Assistance service: case list + case view, the explicit staff milestone/status actions,
Pricing config, MVC Locations config, and the Knowledge Test question bank. Nothing here files anything with NJ MVC."""

from flask import abort, flash, redirect, render_template, request, session, url_for

from app import case_documents as vault
from app import cases as case_svc
from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.models import (DL_MILESTONES, DL_STATUS_EN, DL_STATUSES, DL_TOPICS, Case, CaseNote, DlCaseData, DlPriceRule, DlQuestion, DlQuestionOption, MvcLocation)
from app.driver_license import docs, pricing, service, summary
from app.models.driver_license import INITIAL_PERMIT_STATES, KNOWLEDGE_TEST_STATES, ROAD_TEST_STATES

STAFF_STATUSES = [(k, en) for k, en, _es in DL_STATUSES if k != "draft"]


def _staff():
    return session.get("admin_name") or session.get("admin_email") or "OG team"


def _csrf():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)


def _case_or_404(case_id):
    case = db.session.get(Case, case_id)
    if case is None or case.case_type != service.CASE_TYPE or case.dl_data is None:
        abort(404)
    return case.dl_data


def _back(dl, anchor=""):
    return redirect(url_for("admin.dl_case", case_id=dl.case_id) + anchor)


@admin_bp.route("/driver-license")
@admin_required
def dl_list():
    q = DlCaseData.query.join(Case, Case.id == DlCaseData.case_id)
    status = request.args.get("status", "")
    if status in DL_STATUS_EN:
        q = q.filter(DlCaseData.status == status)
    rows = []
    for dl in q.order_by(DlCaseData.updated_at.desc()).limit(300).all():
        have, total, missing = docs.counts(dl)
        quote = dl.current_quote
        rows.append({"dl": dl, "case": dl.case, "docs": f"{have}/{total}", "missing": missing, "quote": quote,
                     "price": pricing.fmt(next((x.final_total_cents for x in reversed(dl.quotes) if x.status == "confirmed"), None)) if dl.price_status == "confirmed" else None})
    return render_template("admin/dl_list.html", rows=rows, statuses=STAFF_STATUSES + [("draft", "Draft")], status=status, fmt=pricing.fmt)


@admin_bp.route("/driver-license/<int:case_id>")
@admin_required
def dl_case(case_id):
    dl = _case_or_404(case_id)
    c = service.ctx(dl, "en")
    data = summary.admin_summary(dl)
    est = pricing.estimate(dl, c)
    confirmed = next((q for q in reversed(dl.quotes) if q.status == "confirmed"), None)
    reqs = []
    roles = docs._role_map(dl)  # noqa: SLF001
    for r in sorted(docs.requirements(dl), key=lambda x: (x.status in ("accepted",), x.id)):
        title, msg = docs.req_text(r, "en")
        reqs.append({"r": r, "title": title, "status": vault.status_label(r.status, "en"), "choice": dl.doc_choices.get(r.rule_key),
                     "optional": docs.is_optional(r.rule_key, roles), "role": docs.doc_role(r.rule_key, roles), "doc": r.current_document})
    have, total, missing = docs.counts(dl)
    notes = CaseNote.query.filter_by(case_id=dl.case_id).order_by(CaseNote.id.desc()).all()
    events = case_svc.case_timeline(dl.case, 60)
    locations = MvcLocation.query.filter_by(active=True).order_by(MvcLocation.sort_order, MvcLocation.name).all()
    from app import case_revisions

    revisions = [{"rev": r, "changes": case_revisions.revision_changes(r)} for r in reversed(case_revisions.history(dl.case))]
    return render_template("admin/dl_case.html", dl=dl, case=dl.case, data=data, est=est, confirmed=confirmed, reqs=reqs, docs_have=have, docs_total=total, docs_missing=missing,
                           notes=notes, events=events, statuses=STAFF_STATUSES, milestones=DL_MILESTONES, ip_states=INITIAL_PERMIT_STATES, kt_states=KNOWLEDGE_TEST_STATES,
                           rt_states=ROAD_TEST_STATES, locations=locations, fmt=pricing.fmt, quotes=list(reversed(dl.quotes)), status_label=DL_STATUS_EN.get(dl.status, dl.status), revisions=revisions)


@admin_bp.route("/driver-license/<int:case_id>/status", methods=["POST"])
@admin_required
def dl_status(case_id):
    _csrf()
    dl = _case_or_404(case_id)
    ok, err = service.set_status(dl, request.form.get("status", ""), _staff(), message=request.form.get("message"))
    flash("Status updated." if ok else (err or "Not done."), "success" if ok else "error")
    return _back(dl)


@admin_bp.route("/driver-license/<int:case_id>/milestone", methods=["POST"])
@admin_required
def dl_milestone(case_id):
    _csrf()
    dl = _case_or_404(case_id)
    ok, err = service.set_milestone(dl, request.form.get("milestone", ""), _staff())
    flash("Milestone updated." if ok else err, "success" if ok else "error")
    return _back(dl, "#milestones")


@admin_bp.route("/driver-license/<int:case_id>/sub-status", methods=["POST"])
@admin_required
def dl_sub_status(case_id):
    _csrf()
    dl = _case_or_404(case_id)
    field = request.form.get("field")
    valid = {"initial_permit_state": INITIAL_PERMIT_STATES, "knowledge_test_state": KNOWLEDGE_TEST_STATES, "road_test_state": ROAD_TEST_STATES}.get(field)
    if valid is None:
        abort(400)
    ok, err = service.set_sub_status(dl, field, request.form.get("value", ""), _staff(), valid=valid)
    flash("Updated." if ok else err, "success" if ok else "error")
    return _back(dl, "#milestones")


@admin_bp.route("/driver-license/<int:case_id>/request-info", methods=["POST"])
@admin_required
def dl_request_info(case_id):
    _csrf()
    dl = _case_or_404(case_id)
    ok, err = service.request_info(dl, request.form.get("message", ""), _staff())
    flash("The customer will see your message in My Account." if ok else err, "success" if ok else "error")
    return _back(dl)


@admin_bp.route("/driver-license/<int:case_id>/reopen", methods=["POST"])
@admin_required
def dl_reopen(case_id):
    _csrf()
    dl = _case_or_404(case_id)
    ok, err = service.reopen(dl, request.form.get("message", ""), _staff(), actor_id=session.get("admin_user_id"))
    flash("Reopened." if ok else err, "success" if ok else "error")
    return _back(dl)


@admin_bp.route("/driver-license/<int:case_id>/price", methods=["POST"])
@admin_required
def dl_price(case_id):
    _csrf()
    dl = _case_or_404(case_id)
    action = request.form.get("action")
    c = service.ctx(dl, "en")
    if action == "recalc":
        pricing.snapshot(dl, c, staff=_staff())
        db.session.commit()
        flash("Estimate recalculated.", "success")
        return _back(dl, "#price")
    text = (request.form.get("fee") or "").replace("$", "").replace(",", "").strip()
    try:
        cents = int(round(float(text) * 100))
    except ValueError:
        flash("Enter the price.", "error")
        return _back(dl, "#price")
    pricing.snapshot(dl, c)
    db.session.flush()
    before = next((q for q in reversed(dl.quotes) if q.status == "confirmed"), None)
    try:
        quote = pricing.confirm(dl, cents, _staff(), request.form.get("reason"))
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return _back(dl, "#price")
    service.log(dl, "dl_price_confirmed", {"fee": pricing.fmt(cents), "previous": pricing.fmt(before.final_total_cents) if before else None, "reason": quote.reason}, actor="admin")
    flash("Price confirmed." + (" The customer will be asked to acknowledge the change." if quote.needs_ack else ""), "success")
    return _back(dl, "#price")


@admin_bp.route("/driver-license/<int:case_id>/request-payment", methods=["POST"])
@admin_required
def dl_request_payment(case_id):
    """Model C (OG Payments): the intake's own estimate is never requestable — only a CONFIRMED price, read
    straight from the SAME `final_total_cents` this module already tracks, syncs into the OG Payments Charge."""
    from app import payments as pay_svc

    _csrf()
    dl = _case_or_404(case_id)
    confirmed = next((q for q in reversed(dl.quotes) if q.status == "confirmed"), None)
    if confirmed is None or confirmed.final_total_cents is None:
        flash("Confirm the price before requesting payment.", "error")
        return _back(dl, "#price")
    description = "NJ Driver License Assistance"
    charge = next((c for c in dl.case.charges if c.description == description and not c.is_canceled), None)
    if charge is None:
        charge = pay_svc.create_charge(dl.case.customer, description=description, case=dl.case,
                                       total_cents=confirmed.final_total_cents, price_mode="final", admin_id=session.get("admin_user_id"))
    elif charge.total_cents != confirmed.final_total_cents:
        pay_svc.set_price(charge, confirmed.final_total_cents, admin_id=session.get("admin_user_id"), mode="final", reason="Synced from the confirmed NJ Driver License price.")
    bal = pay_svc.balance_cents(charge)
    if not bal:
        flash("This charge is already fully paid.", "error")
        return _back(dl, "#price")
    try:
        pay_svc.request_payment(charge, bal, admin_id=session.get("admin_user_id"))
    except ValueError as exc:
        flash(str(exc), "error")
        return _back(dl, "#price")
    flash("Payment requested — the customer will see this in My Account > Payments.", "success")
    return _back(dl, "#price")


@admin_bp.route("/driver-license/<int:case_id>/note", methods=["POST"])
@admin_required
def dl_note(case_id):
    _csrf()
    dl = _case_or_404(case_id)
    body = request.form.get("body", "").strip()
    if body:
        db.session.add(CaseNote(case_id=dl.case_id, body=body[:4000], author_name=_staff()))
        db.session.commit()
        case_svc.case_event(dl.case, "case_note_added", actor="admin")
    return _back(dl, "#notes")


@admin_bp.route("/driver-license/<int:case_id>/appointment", methods=["POST"])
@admin_required
def dl_appointment(case_id):
    """Record the appointment information staff obtained from MVC (informational — OG has no special MVC access)."""
    _csrf()
    dl = _case_or_404(case_id)
    dl.appointment = {"date": request.form.get("date", "").strip()[:20], "note": request.form.get("note", "").strip()[:300]}
    db.session.commit()
    flash("Appointment information saved.", "success")
    return _back(dl, "#milestones")


# ------------------------------------------------------------------ Driver License -> Pricing
@admin_bp.route("/driver-license/pricing")
@admin_required
def dl_pricing():
    pricing.ensure_seed()
    rules = DlPriceRule.query.order_by(DlPriceRule.sort_order, DlPriceRule.id).all()
    groups = {}
    for r in rules:
        groups.setdefault(r.kind, []).append(r)
    return render_template("admin/dl_pricing.html", groups=groups, fmt=pricing.fmt)


@admin_bp.route("/driver-license/pricing", methods=["POST"])
@admin_required
def dl_pricing_save():
    _csrf()
    changed = []
    for rule in DlPriceRule.query.all():
        key = f"r{rule.id}"
        if f"{key}__present" not in request.form:
            continue
        before = (rule.amount_cents, rule.active)
        text = (request.form.get(f"{key}__amount") or "").replace("$", "").replace(",", "").strip()
        try:
            cents = int(round(float(text) * 100)) if text else None
        except ValueError:
            cents = rule.amount_cents
        if cents is not None and 0 <= cents <= 10_000_000:
            rule.amount_cents = cents
        rule.active = bool(request.form.get(f"{key}__active"))
        if before != (rule.amount_cents, rule.active):
            rule.updated_by = _staff()
            changed.append(rule.label_en)
    db.session.commit()
    flash(f"{len(changed)} price setting(s) updated." if changed else "Nothing changed.", "success")
    return redirect(url_for("admin.dl_pricing"))


# ------------------------------------------------------------------ Driver License -> Locations
@admin_bp.route("/driver-license/locations")
@admin_required
def dl_locations():
    rows = MvcLocation.query.order_by(MvcLocation.sort_order, MvcLocation.name).all()
    return render_template("admin/dl_locations.html", rows=rows)


@admin_bp.route("/driver-license/locations/new", methods=["POST"])
@admin_required
def dl_location_new():
    _csrf()
    name = request.form.get("name", "").strip()[:120]
    if not name:
        flash("Enter a location name.", "error")
        return redirect(url_for("admin.dl_locations"))
    slug = name.lower().replace(" ", "-")[:60]
    if MvcLocation.query.filter_by(slug=slug).first():
        flash("That location already exists.", "error")
        return redirect(url_for("admin.dl_locations"))
    n = MvcLocation.query.count()
    db.session.add(MvcLocation(name=name, slug=slug, sort_order=n))
    db.session.commit()
    flash("Location added.", "success")
    return redirect(url_for("admin.dl_locations"))


@admin_bp.route("/driver-license/locations/<int:loc_id>", methods=["POST"])
@admin_required
def dl_location_edit(loc_id):
    _csrf()
    loc = MvcLocation.query.get_or_404(loc_id)
    action = request.form.get("action")
    if action == "toggle":
        loc.active = not loc.active
    elif action == "rename":
        name = request.form.get("name", "").strip()[:120]
        if name:
            loc.name = name
    db.session.commit()
    return redirect(url_for("admin.dl_locations"))


# ------------------------------------------------------------------ Driver License -> Knowledge Test Questions
@admin_bp.route("/driver-license/questions")
@admin_required
def dl_questions():
    topic = request.args.get("topic", "")
    q = DlQuestion.query
    if topic in DL_TOPICS:
        q = q.filter_by(topic=topic)
    rows = q.order_by(DlQuestion.topic, DlQuestion.sort_order, DlQuestion.id).all()
    return render_template("admin/dl_questions.html", rows=rows, topics=DL_TOPICS, topic=topic)


@admin_bp.route("/driver-license/questions/<int:q_id>/toggle", methods=["POST"])
@admin_required
def dl_question_toggle(q_id):
    _csrf()
    q = DlQuestion.query.get_or_404(q_id)
    q.active = not q.active
    db.session.commit()
    return redirect(url_for("admin.dl_questions", topic=request.form.get("topic", "")))


@admin_bp.route("/driver-license/questions/<int:q_id>/edit", methods=["GET", "POST"])
@admin_required
def dl_question_edit(q_id):
    q = DlQuestion.query.get_or_404(q_id)
    if request.method == "POST":
        _csrf()
        q.question_en = request.form.get("question_en", "").strip()[:2000] or q.question_en
        q.question_es = request.form.get("question_es", "").strip()[:2000] or q.question_es
        q.explanation_en = request.form.get("explanation_en", "").strip()[:2000] or None
        q.explanation_es = request.form.get("explanation_es", "").strip()[:2000] or None
        q.difficulty = request.form.get("difficulty") or q.difficulty
        q.topic = request.form.get("topic") if request.form.get("topic") in DL_TOPICS else q.topic
        correct_id = request.form.get("correct_option", type=int)
        for o in q.options:
            text_en = request.form.get(f"opt_en_{o.id}", "").strip()
            text_es = request.form.get(f"opt_es_{o.id}", "").strip()
            if text_en:
                o.text_en = text_en[:300]
            if text_es:
                o.text_es = text_es[:300]
            o.is_correct = o.id == correct_id
        db.session.commit()
        flash("Question saved.", "success")
        return redirect(url_for("admin.dl_questions", topic=q.topic))
    return render_template("admin/dl_question_edit.html", q=q, topics=DL_TOPICS)


@admin_bp.route("/driver-license/questions/new", methods=["POST"])
@admin_required
def dl_question_new():
    _csrf()
    import secrets

    topic = request.form.get("topic") or DL_TOPICS[0]
    q = DlQuestion(concept_key=f"custom_{secrets.token_hex(4)}", topic=topic, difficulty="medium", question_en="New question", question_es="Nueva pregunta", version="admin")
    db.session.add(q)
    db.session.flush()
    for i in range(4):
        db.session.add(DlQuestionOption(question_id=q.id, text_en=f"Option {i + 1}", text_es=f"Opción {i + 1}", is_correct=(i == 0), sort_order=i))
    db.session.commit()
    return redirect(url_for("admin.dl_question_edit", q_id=q.id))
