"""Customer-facing Tax Smart Intake (Individual & Family Tax Preparation). Every route acts only on the signed-in customer's OWN tax case: the case id in a URL is looked up
THROUGH the customer, so someone else's id answers 404 exactly like a missing one. No sensitive value ever travels in a URL."""

from flask import abort, flash, jsonify, redirect, render_template, request, url_for

from app import case_documents as vault
from app.auth import validate_csrf
from app.blueprints.public.routes import public_bp
from app.extensions import db
from app.i18n import get_text
from app.models import Person
from app.ratelimit import allow
from app.student_auth import current_student, student_required
from app.tax import docs, people, pricing, service, summary, terms
from datetime import date

from app.tax.questions import STATES, pick
from app.tax.registry import config_for


def _tax_or_404(case_id):
    tax = service.owned(current_student(), case_id)
    if tax is None:
        abort(404)
    return tax


def _csrf():
    if not validate_csrf(request.form.get("csrf_token") or request.headers.get("X-CSRFToken")):
        abort(400)


def _account_url(tax, lang):
    return url_for("account.my_case_detail", lang=lang, case_id=tax.case_id)


def step_url(tax, lang, key, **kw):
    return url_for("public.tax_step", lang=lang, case_id=tax.case_id, step_key=key, **kw)


def home_url(tax, lang):
    if tax.status not in service.EDITABLE:
        return _account_url(tax, lang)
    c = service.ctx(tax, lang)
    key = tax.current_step if service.step_by_key(c, tax.current_step or "") else "intro"
    return step_url(tax, lang, key)


# ------------------------------------------------------------------ entry
@public_bp.route("/tax/start")
@student_required
def tax_start(lang):
    """Get Started: create the customer's 2025 tax return, or continue the one they already have (never a second active case for the same year)."""
    tax, _created = service.start_or_resume(current_student(), lang)
    return redirect(home_url(tax, lang))


@public_bp.route("/tax/terms")
def tax_terms(lang):
    year = request.args.get("year", type=int) or 2025
    return render_template("tax/terms.html", sections=terms.SECTIONS, version=terms.version_for(year), year=year, cert=terms.CERTIFICATION, accept=terms.ACCEPTANCE)


@public_bp.route("/tax/<int:case_id>")
@student_required
def tax_home(lang, case_id):
    return redirect(home_url(_tax_or_404(case_id), lang))


# ------------------------------------------------------------------ rendering helpers
def _values(c, step, form=None):
    """{key: {value, error-free display}} for the questions of a step: what the customer posted (after an error) or what is stored."""
    out = {}
    scope_record = c.record is not None
    for q in step.questions:
        if q.kind in ("note", "docs", "records", "person_pick"):
            continue
        if form is not None and q.key in set(form.getlist("__q")):
            out[q.key] = form.getlist(q.key) if q.kind == "multi" else (form.get(q.key) or "")
        elif q.kind in ("ssn", "secret"):
            out[q.key] = ""
        else:
            out[q.key] = c.raw(q.key, "record" if scope_record else "self") or ([] if q.kind == "multi" else "")
    return out


def _qview(tax, c, step, lang, form=None, errors=None):
    values = _values(c, step, form)
    rows = []
    for q in step.questions:
        opts = q.opts(c) if q.kind in ("choice", "select", "multi", "yn3") else []
        has_secret = ""
        if q.kind == "ssn" and q.bind:
            owner = people.owner_for(tax, step.scope, c.record if step.scope == "record" else None)
            has_secret = people.mask_ssn(people.get_fact(owner, q.bind)) if owner is not None else ""
        if q.kind == "secret" and tax.bank is not None and q.key in ("dd_routing", "dd_account", "dd_account2"):
            has_secret = "••••" + ((tax.bank.routing_last4 if q.key == "dd_routing" else tax.bank.account_last4) or "")
        rows.append({"q": q, "label": pick(q.label, lang), "help": pick(q.help, lang) if q.help else "", "opts": opts, "value": values.get(q.key, ""), "error": (errors or {}).get(q.key),
                     "visible": c.visible(q.key), "secret": has_secret, "ph": pick(q.ph, lang) if q.ph else ""})
    return rows


def _doc_cards(tax, c, step, lang):
    out = {}
    for q in step.questions:
        if q.kind == "docs":
            out[q.key] = docs.cards(tax, q.docs, lang, c.record)
    return out


def _render_step(tax, lang, step, c, *, errors=None, form=None, record=None, urls=None):
    prog = service.progress(c, step.key) if record is None else service.progress(c, _list_key(record.kind))
    extra = {}
    if step.kind == "records":
        recs = c.deps if step.record == "dependent" else c.bizs
        extra["records"] = [{"r": r, "name": (people.info(tax, r).get("given") if r.kind == "dependent" else (r.data.get("b_desc") or "")) or ("…"), "complete": r.complete,
                             "sub": r.data.get("b_type") if r.kind == "business" else None} for r in recs]
        if step.record == "dependent" and tax.is_returning:
            extra["previous"] = service.previous_dependents(tax)
        extra["kind"] = step.record
    if step.key == "spouse":
        used = {r.person.person_id for r in tax.records if r.kind == "dependent" and r.person is not None}
        extra["known"] = people.known_people(tax, exclude_ids=used)
        extra["spouse_person"] = people.spouse_person(tax)
    if step.key == "documents":
        extra["groups"] = _doc_groups(tax, lang)
    if step.key in ("price", "review", "send"):
        extra.update(_special(tax, c, step, lang))
    return render_template("tax/step.html", tax=tax, c=c, step=step, rows=_qview(tax, c, step, lang, form, errors), qdocs=_doc_cards(tax, c, step, lang), errors=errors or {}, progress=prog,
                           record=record, urls=urls or {}, title=pick(step.title, lang), states=STATES, today=date.today().isoformat(), **extra)


def _doc_groups(tax, lang):
    have, total, missing = docs.counts(tax)
    cards = docs.cards(tax, ("tax.",), lang)
    groups = {"required": [], "optional": []}
    for card in cards:
        groups["optional" if card["optional"] else "required"].append(card)
    return {"groups": groups, "have": have, "total": total, "missing": missing}


def _special(tax, c, step, lang):
    if step.key == "price":
        return {"price": pricing.customer_view(tax, c, lang)}
    if step.key == "review":
        have, total, missing = docs.counts(tax)
        return {"cards": summary.review_cards(tax, lang), "docs_missing": missing, "missing_answers": service.required_missing(tax, lang)}
    if step.key == "send":
        have, total, missing = docs.counts(tax)
        return {"docs_missing": missing, "missing_answers": service.required_missing(tax, lang), "cert": terms.CERTIFICATION, "accept": terms.ACCEPTANCE, "price": pricing.customer_view(tax, c, lang)}
    return {}


def _editable_or_redirect(tax, lang):
    if tax.status not in service.EDITABLE:
        return redirect(_account_url(tax, lang))
    return None


# ------------------------------------------------------------------ the interview
@public_bp.route("/tax/<int:case_id>/s/<step_key>", methods=["GET", "POST"])
@student_required
def tax_step(lang, case_id, step_key):
    tax = _tax_or_404(case_id)
    c = service.ctx(tax, lang)
    step = service.step_by_key(c, step_key)
    if step is None:
        return redirect(home_url(tax, lang))
    if step.key != "documents":
        gate = _editable_or_redirect(tax, lang)
        if gate is not None:
            return gate
    if request.method == "GET":
        if tax.status in service.EDITABLE and tax.current_step != step.key:
            tax.current_step = step.key
            db.session.commit()
        return _render_step(tax, lang, step, c)
    _csrf()
    if not allow(f"tax-step:{current_student().id}", 240, 60):
        abort(429)
    nav = request.form.get("nav", "next")
    autosave = request.form.get("autosave") == "1"
    if tax.status not in service.EDITABLE and step.key != "documents":
        abort(403)
    if nav == "pick":
        return _pick_spouse(tax, lang)
    errors = {}
    if step.kind in ("form", "records") and tax.status in service.EDITABLE:
        errors = service.save_step(tax, step, request.form, lang, strict=(nav == "next" and not autosave))
    if autosave:
        c2 = service.ctx(tax, lang)
        return jsonify(ok=True, visible=[q.key for q in step.questions if c2.visible(q.key)])
    docs.sync(tax)
    if nav == "exit":
        flash("Saved. You can continue any time." if lang != "es" else "Guardado. Puedes continuar cuando quieras.", "success")
        return redirect(_account_url(tax, lang))
    c2 = service.ctx(tax, lang)
    if nav == "back":
        prev = service.neighbour(c2, step.key, -1)
        return redirect(step_url(tax, lang, prev) if prev else _account_url(tax, lang))
    if errors:
        return _render_step(tax, lang, step, c2, errors=errors, form=request.form)
    nxt = service.neighbour(c2, step.key, +1)
    if nxt is None:
        return redirect(step_url(tax, lang, "send"))
    return redirect(step_url(tax, lang, nxt))


def _pick_spouse(tax, lang):
    pid = request.form.get("s_pick", type=int)
    person = Person.query.filter_by(id=pid or 0, customer_id=tax.case.customer_id, is_self=False).first()
    if person is not None:
        from app import persons as pers

        people.case_person(tax, person, "spouse")
        a = tax.answers
        a["_spouse_pid"] = person.id
        tax.answers = a
        db.session.commit()
    return redirect(step_url(tax, lang, "spouse"))


# ------------------------------------------------------------------ records (dependents, self-employment activities)
def _record_or_404(tax, kind, rid):
    rec = service.owned_record(tax, rid)
    if rec is None or rec.kind != kind:
        abort(404)
    return rec


def _flow(tax, kind):
    return config_for(tax.tax_year).record_flows.get(kind) or abort(404)


def _list_key(kind):
    return "deps" if kind == "dependent" else "business"


@public_bp.route("/tax/<int:case_id>/r/<kind>/new", methods=["POST"])
@student_required
def tax_record_new(lang, case_id, kind):
    _csrf()
    tax = _tax_or_404(case_id)
    gate = _editable_or_redirect(tax, lang)
    if gate is not None:
        return gate
    flow = _flow(tax, kind)
    rec = service.add_record(tax, kind)
    return redirect(url_for("public.tax_record_step", lang=lang, case_id=tax.case_id, kind=kind, rid=rec.id, sub=flow[0].key))


@public_bp.route("/tax/<int:case_id>/r/dependent/carry", methods=["POST"])
@student_required
def tax_record_carry(lang, case_id):
    _csrf()
    tax = _tax_or_404(case_id)
    gate = _editable_or_redirect(tax, lang)
    if gate is not None:
        return gate
    person = Person.query.filter_by(id=request.form.get("person_id", type=int) or 0, customer_id=tax.case.customer_id, is_self=False).first()
    if person is None:
        abort(404)
    rec = service.carry_over(tax, person)
    flow = _flow(tax, "dependent")
    # dep_who's own name/date of birth/SSN fields read straight from the Person (already known); only relationship and SSN status are
    # per-record and must still be asked, so the flow starts there rather than skipping to dep_life.
    return redirect(url_for("public.tax_record_step", lang=lang, case_id=tax.case_id, kind="dependent", rid=rec.id, sub=flow[0].key))


@public_bp.route("/tax/<int:case_id>/r/<kind>/<int:rid>/remove", methods=["POST"])
@student_required
def tax_record_remove(lang, case_id, kind, rid):
    _csrf()
    tax = _tax_or_404(case_id)
    gate = _editable_or_redirect(tax, lang)
    if gate is not None:
        return gate
    service.remove_record(tax, _record_or_404(tax, kind, rid))
    return redirect(step_url(tax, lang, _list_key(kind)))


@public_bp.route("/tax/<int:case_id>/r/<kind>/<int:rid>/<sub>", methods=["GET", "POST"])
@student_required
def tax_record_step(lang, case_id, kind, rid, sub):
    tax = _tax_or_404(case_id)
    gate = _editable_or_redirect(tax, lang)
    if gate is not None:
        return gate
    rec = _record_or_404(tax, kind, rid)
    flow = _flow(tax, kind)
    keys = [s.key for s in flow]
    if sub not in keys:
        abort(404)
    step = flow[keys.index(sub)]
    c = service.ctx(tax, lang, rec)
    here = lambda k: url_for("public.tax_record_step", lang=lang, case_id=tax.case_id, kind=kind, rid=rec.id, sub=k)  # noqa: E731
    urls = {"back": here(keys[keys.index(sub) - 1]) if keys.index(sub) > 0 else step_url(tax, lang, _list_key(kind)), "list": step_url(tax, lang, _list_key(kind)),
            "self": url_for("public.tax_record_step", lang=lang, case_id=tax.case_id, kind=kind, rid=rec.id, sub=sub)}
    if request.method == "GET":
        return _render_step(tax, lang, step, c, record=rec, urls=urls)
    _csrf()
    if not allow(f"tax-step:{current_student().id}", 240, 60):
        abort(429)
    nav = request.form.get("nav", "next")
    autosave = request.form.get("autosave") == "1"
    errors = service.save_step(tax, step, request.form, lang, record=rec, strict=(nav == "next" and not autosave))
    if autosave:
        c2 = service.ctx(tax, lang, rec)
        return jsonify(ok=True, visible=[q.key for q in step.questions if c2.visible(q.key)])
    docs.sync(tax)
    if nav == "exit":
        flash("Saved. You can continue any time." if lang != "es" else "Guardado. Puedes continuar cuando quieras.", "success")
        return redirect(_account_url(tax, lang))
    if nav == "back":
        return redirect(urls["back"])
    if errors:
        return _render_step(tax, lang, step, service.ctx(tax, lang, rec), errors=errors, form=request.form, record=rec, urls=urls)
    i = keys.index(sub)
    if i + 1 < len(keys):
        return redirect(here(keys[i + 1]))
    rec.complete = True
    db.session.commit()
    return redirect(urls["list"])


# ------------------------------------------------------------------ documents (upload now / later; the vault does the storing)
def _req_or_404(tax, req_id):
    case, req = vault.owned_requirement(current_student(), tax.case_id, req_id)
    if case is None or req is None or req.source_key != docs.SOURCE_KEY:
        abort(404)
    return req


@public_bp.route("/tax/<int:case_id>/doc/<int:req_id>/upload", methods=["POST"])
@student_required
def tax_doc_upload(lang, case_id, req_id):
    _csrf()
    tax = _tax_or_404(case_id)
    req = _req_or_404(tax, req_id)
    if not allow(f"tax-upload:{current_student().id}", 60, 300):
        return jsonify(ok=False, error=get_text(lang, "flash_too_many")), 429
    f = request.files.get("file")
    error = vault.validate_upload(f, lang) if f and f.filename else get_text(lang, "case_choose_file")
    if error:
        return jsonify(ok=False, error=error), 422
    if req.status not in vault.CUSTOMER_CAN_UPLOAD:
        return jsonify(ok=False, error=get_text(lang, "case_cannot_upload")), 409
    had = req.current_document is not None
    vault.upload_for_requirement(req, f, uploaded_by="customer", uploaded_by_id=current_student().id)
    if had:
        service.log(tax, "tax_doc_replaced", {"title": docs.req_text(req, "en")[0]})
    choices = tax.doc_choices
    if req.rule_key in choices:
        choices.pop(req.rule_key)
        tax.doc_choices = choices
        db.session.commit()
    return jsonify(ok=True)


@public_bp.route("/tax/<int:case_id>/doc/<int:req_id>/remove", methods=["POST"])
@student_required
def tax_doc_remove(lang, case_id, req_id):
    _csrf()
    tax = _tax_or_404(case_id)
    req = _req_or_404(tax, req_id)
    doc = req.current_document
    if doc is None or not vault.customer_can_remove(req, doc):
        return jsonify(ok=False), 409
    vault.remove_document(doc, actor="customer", actor_id=current_student().id)
    return jsonify(ok=True)


@public_bp.route("/tax/<int:case_id>/doc/<int:req_id>/choice", methods=["POST"])
@student_required
def tax_doc_choice(lang, case_id, req_id):
    _csrf()
    tax = _tax_or_404(case_id)
    req = _req_or_404(tax, req_id)
    choice = request.form.get("choice", "")
    choices = tax.doc_choices
    if choice == "":
        choices.pop(req.rule_key, None)
    elif choice in docs.choice_kinds(req.rule_key):
        choices[req.rule_key] = choice
    else:
        return jsonify(ok=False), 400
    tax.doc_choices = choices
    db.session.commit()
    return jsonify(ok=True)


# ------------------------------------------------------------------ send to OG
@public_bp.route("/tax/<int:case_id>/send", methods=["POST"])
@student_required
def tax_send(lang, case_id):
    _csrf()
    tax = _tax_or_404(case_id)
    gate = _editable_or_redirect(tax, lang)
    if gate is not None:
        return gate
    ok, err = service.submit(tax, current_student(), lang, bool(request.form.get("certify")), bool(request.form.get("terms")), {"ip": request.remote_addr, "ua": request.headers.get("User-Agent")})
    if ok:
        return redirect(url_for("public.tax_done", lang=lang, case_id=tax.case_id))
    c = service.ctx(tax, lang)
    step = service.step_by_key(c, "send")
    msg = {"accept": ("Please check both boxes to send your information.", "Marca las dos casillas para enviar tu información."),
           "incomplete": ("😊 A few answers are still missing. Let's finish them first.", "😊 Todavía faltan algunas respuestas. Terminémoslas primero."), "state": ("This return was already sent.", "Esta declaración ya fue enviada.")}[err]
    return _render_step(tax, lang, step, c, errors={"_send": pick(msg, lang)})


@public_bp.route("/tax/<int:case_id>/done")
@student_required
def tax_done(lang, case_id):
    tax = _tax_or_404(case_id)
    have, total, missing = docs.counts(tax)
    return render_template("tax/done.html", tax=tax, missing=missing, account_url=_account_url(tax, lang))


@public_bp.route("/tax/<int:case_id>/price/ack", methods=["POST"])
@student_required
def tax_price_ack(lang, case_id):
    _csrf()
    tax = _tax_or_404(case_id)
    if pricing.acknowledge(tax):
        service.log(tax, "tax_price_acknowledged")
    return redirect(_account_url(tax, lang))
