"""Customer-facing Consent to Travel Authorization intake. Every route acts only on the signed-in customer's
OWN case: the case id in a URL is looked up THROUGH the customer, so someone else's id answers 404 exactly
like a missing one. No sensitive value ever travels in a URL."""

from datetime import date

from flask import abort, flash, jsonify, redirect, render_template, request, url_for

from app import case_documents as vault
from app.auth import validate_csrf
from app.blueprints.public.routes import public_bp
from app.consent_travel import docs, people, pricing, service, summary, terms
from app.consent_travel.config import CONFIG
from app.extensions import db
from app.i18n import get_text
from app.ratelimit import allow
from app.student_auth import current_student, student_required
from app.tax.questions import STATES, pick


def _ct_or_404(case_id):
    ct = service.owned(current_student(), case_id)
    if ct is None:
        abort(404)
    return ct


def _csrf():
    if not validate_csrf(request.form.get("csrf_token") or request.headers.get("X-CSRFToken")):
        abort(400)


def _account_url(ct, lang):
    return url_for("account.my_case_detail", lang=lang, case_id=ct.case_id)


def step_url(ct, lang, key, **kw):
    return url_for("public.ct_step", lang=lang, case_id=ct.case_id, step_key=key, **kw)


def home_url(ct, lang):
    if ct.status not in service.EDITABLE:
        return _account_url(ct, lang)
    c = service.ctx(ct, lang)
    key = ct.current_step if service.step_by_key(c, ct.current_step or "") else "intro"
    return step_url(ct, lang, key)


# ------------------------------------------------------------------ entry
@public_bp.route("/consent-to-travel/start")
@student_required
def ct_start(lang):
    ct, _created = service.start_or_resume(current_student(), lang)
    return redirect(home_url(ct, lang))


@public_bp.route("/consent-to-travel/terms")
def ct_terms(lang):
    return render_template("consent_travel/terms.html", sections=terms.SECTIONS, version=terms.VERSION, cert=terms.CERTIFICATION, accept=terms.ACCEPTANCE)


@public_bp.route("/consent-to-travel/<int:case_id>")
@student_required
def ct_home(lang, case_id):
    return redirect(home_url(_ct_or_404(case_id), lang))


# ------------------------------------------------------------------ rendering helpers
def _values(c, step, form=None):
    out = {}
    scope_record = c.record is not None
    for q in step.questions:
        if q.kind in ("note", "docs", "records", "person_pick"):
            continue
        if form is not None and q.key in set(form.getlist("__q")):
            out[q.key] = form.getlist(q.key) if q.kind == "multi" else (form.get(q.key) or "")
        else:
            out[q.key] = c.raw(q.key, "record" if scope_record else "self") or ([] if q.kind == "multi" else "")
    return out


def _qview(c, step, lang, form=None, errors=None):
    values = _values(c, step, form)
    rows = []
    for q in step.questions:
        opts = q.opts(c) if q.kind in ("choice", "select", "multi", "yn3") else []
        rows.append({"q": q, "label": pick(q.label, lang), "help": pick(q.help, lang) if q.help else "", "opts": opts, "value": values.get(q.key, ""),
                     "error": (errors or {}).get(q.key), "visible": c.visible(q.key), "secret": "", "ph": pick(q.ph, lang) if q.ph else ""})
    return rows


def _render_step(ct, lang, step, c, *, errors=None, form=None, record=None, urls=None):
    prog = service.progress(c, step.key)
    extra = {}
    if step.kind == "records":
        recs = c._records(step.record)  # noqa: SLF001
        if step.record == "child":
            extra["records"] = [{"r": r, "name": (f"{people.info(ct, r).get('given') or ''} {people.info(ct, r).get('family') or ''}".strip() or "…"), "complete": r.complete} for r in recs]
        else:  # adult — auto-synced, no add/remove
            extra["records"] = [{"r": r, "name": (f"{r.person.given_name or ''} {r.person.family_name or ''}".strip() if r.person else "…"), "complete": r.complete} for r in recs]
        extra["kind"] = step.record
    if step.key in ("child_docs",) and record is not None:
        extra["doc_cards"] = docs.cards(ct, lang, record, "child")
    if step.key in ("adult_docs",) and record is not None:
        extra["doc_cards"] = docs.cards(ct, lang, record, "adult")
    if step.key == "traveler_docs":
        extra["doc_cards"] = [c for c in docs.cards(ct, lang) if (c["req"].rule_key or "").startswith("ct.traveler.")]
    if step.key == "documents_vault":
        have, total, missing = docs.counts(ct)
        extra["groups"] = {"cards": docs.cards(ct, lang), "have": have, "total": total, "missing": missing}
    if step.key in ("price", "review", "send"):
        extra.update(_special(ct, c, step, lang))
    return render_template("consent_travel/step.html", ct=ct, c=c, step=step, rows=_qview(c, step, lang, form, errors), errors=errors or {}, progress=prog,
                           record=record, urls=urls or {}, title=pick(step.title, lang), states=STATES, today=date.today().isoformat(), **extra)


def _special(ct, c, step, lang):
    groups = service.groups_for(ct)
    if step.key == "price":
        return {"price": pricing.customer_view(ct, groups, lang)}
    if step.key == "review":
        have, total, missing = docs.counts(ct)
        return {"cards": summary.review_cards(ct, lang), "docs_missing": missing, "missing_answers": service.missing_answers(ct, lang)}
    if step.key == "send":
        have, total, missing = docs.counts(ct)
        return {"docs_missing": missing, "missing_answers": service.missing_answers(ct, lang), "cert": terms.CERTIFICATION, "accept": terms.ACCEPTANCE, "price": pricing.customer_view(ct, groups, lang)}
    return {}


def _editable_or_redirect(ct, lang):
    if ct.status not in service.EDITABLE:
        return redirect(_account_url(ct, lang))
    return None


# ------------------------------------------------------------------ the interview
@public_bp.route("/consent-to-travel/<int:case_id>/s/<step_key>", methods=["GET", "POST"])
@student_required
def ct_step(lang, case_id, step_key):
    ct = _ct_or_404(case_id)
    c = service.ctx(ct, lang)
    step = service.step_by_key(c, step_key)
    if step is None:
        return redirect(home_url(ct, lang))
    gate = _editable_or_redirect(ct, lang)
    if gate is not None:
        return gate
    if request.method == "GET":
        if ct.status in service.EDITABLE and ct.current_step != step.key:
            ct.current_step = step.key
            db.session.commit()
        return _render_step(ct, lang, step, c)
    _csrf()
    if not allow(f"ct-step:{current_student().id}", 240, 60):
        abort(429)
    nav = request.form.get("nav", "next")
    autosave = request.form.get("autosave") == "1"
    errors = {}
    if step.kind in ("form", "records"):
        errors = service.save_step(ct, step, request.form, lang, strict=(nav == "next" and not autosave))
    if autosave:
        c2 = service.ctx(ct, lang)
        return jsonify(ok=True, visible=[q.key for q in step.questions if c2.visible(q.key)])
    if nav == "exit":
        flash("Saved. You can continue any time." if lang != "es" else "Guardado. Puedes continuar cuando quieras.", "success")
        return redirect(_account_url(ct, lang))
    c2 = service.ctx(ct, lang)
    if nav == "back":
        prev = service.neighbour(c2, step.key, -1)
        return redirect(step_url(ct, lang, prev) if prev else _account_url(ct, lang))
    if errors:
        return _render_step(ct, lang, step, c2, errors=errors, form=request.form)
    nxt = service.neighbour(c2, step.key, +1)
    if nxt is None:
        return redirect(step_url(ct, lang, "send"))
    return redirect(step_url(ct, lang, nxt))


# ------------------------------------------------------------------ children / consenting adults (records)
def _record_or_404(ct, kind, rid):
    rec = service.owned_record(ct, rid)
    if rec is None or rec.kind != kind:
        abort(404)
    return rec


def _flow(kind):
    return CONFIG.record_flows.get(kind) or abort(404)


def _list_key(kind):
    return "children" if kind == "child" else "adults"


@public_bp.route("/consent-to-travel/<int:case_id>/r/child/new", methods=["POST"])
@student_required
def ct_child_new(lang, case_id):
    _csrf()
    ct = _ct_or_404(case_id)
    gate = _editable_or_redirect(ct, lang)
    if gate is not None:
        return gate
    rec = service.add_child(ct)
    flow = _flow("child")
    return redirect(url_for("public.ct_record_step", lang=lang, case_id=ct.case_id, kind="child", rid=rec.id, sub=flow[0].key))


@public_bp.route("/consent-to-travel/<int:case_id>/r/child/<int:rid>/remove", methods=["POST"])
@student_required
def ct_child_remove(lang, case_id, rid):
    _csrf()
    ct = _ct_or_404(case_id)
    gate = _editable_or_redirect(ct, lang)
    if gate is not None:
        return gate
    service.remove_child(ct, _record_or_404(ct, "child", rid))
    return redirect(step_url(ct, lang, "children"))


@public_bp.route("/consent-to-travel/<int:case_id>/r/<kind>/<int:rid>/<sub>", methods=["GET", "POST"])
@student_required
def ct_record_step(lang, case_id, kind, rid, sub):
    ct = _ct_or_404(case_id)
    gate = _editable_or_redirect(ct, lang)
    if gate is not None:
        return gate
    rec = _record_or_404(ct, kind, rid)
    flow = _flow(kind)
    keys = [s.key for s in flow]
    if sub not in keys:
        abort(404)
    step = flow[keys.index(sub)]
    c = service.ctx(ct, lang, rec)
    here = lambda k: url_for("public.ct_record_step", lang=lang, case_id=ct.case_id, kind=kind, rid=rec.id, sub=k)  # noqa: E731
    urls = {"back": here(keys[keys.index(sub) - 1]) if keys.index(sub) > 0 else step_url(ct, lang, _list_key(kind)), "list": step_url(ct, lang, _list_key(kind))}
    if request.method == "GET":
        return _render_step(ct, lang, step, c, record=rec, urls=urls)
    _csrf()
    if not allow(f"ct-step:{current_student().id}", 240, 60):
        abort(429)
    nav = request.form.get("nav", "next")
    autosave = request.form.get("autosave") == "1"
    errors = service.save_step(ct, step, request.form, lang, record=rec, strict=(nav == "next" and not autosave))
    if autosave:
        c2 = service.ctx(ct, lang, rec)
        return jsonify(ok=True, visible=[q.key for q in step.questions if c2.visible(q.key)])
    if nav == "exit":
        flash("Saved. You can continue any time." if lang != "es" else "Guardado. Puedes continuar cuando quieras.", "success")
        return redirect(_account_url(ct, lang))
    if nav == "back":
        return redirect(urls["back"])
    if errors:
        return _render_step(ct, lang, step, service.ctx(ct, lang, rec), errors=errors, form=request.form, record=rec, urls=urls)
    i = keys.index(sub)
    if i + 1 < len(keys):
        return redirect(here(keys[i + 1]))
    rec.complete = True
    db.session.commit()
    return redirect(urls["list"])


# ------------------------------------------------------------------ documents
def _req_or_404(ct, req_id):
    case, req = vault.owned_requirement(current_student(), ct.case_id, req_id)
    if case is None or req is None or req.source_key != docs.SOURCE_KEY:
        abort(404)
    return req


@public_bp.route("/consent-to-travel/<int:case_id>/doc/<int:req_id>/upload", methods=["POST"])
@student_required
def ct_doc_upload(lang, case_id, req_id):
    _csrf()
    ct = _ct_or_404(case_id)
    req = _req_or_404(ct, req_id)
    if not allow(f"ct-upload:{current_student().id}", 60, 300):
        return jsonify(ok=False, error=get_text(lang, "flash_too_many")), 429
    f = request.files.get("file")
    error = vault.validate_upload(f, lang) if f and f.filename else get_text(lang, "case_choose_file")
    if error:
        return jsonify(ok=False, error=error), 422
    if req.status not in vault.CUSTOMER_CAN_UPLOAD:
        return jsonify(ok=False, error=get_text(lang, "case_cannot_upload")), 409
    vault.upload_for_requirement(req, f, uploaded_by="customer", uploaded_by_id=current_student().id)
    choices = ct.doc_choices
    if req.rule_key in choices:
        choices.pop(req.rule_key)
        ct.doc_choices = choices
        db.session.commit()
    return jsonify(ok=True)


@public_bp.route("/consent-to-travel/<int:case_id>/doc/<int:req_id>/remove", methods=["POST"])
@student_required
def ct_doc_remove(lang, case_id, req_id):
    _csrf()
    ct = _ct_or_404(case_id)
    req = _req_or_404(ct, req_id)
    doc = req.current_document
    if doc is None or not vault.customer_can_remove(req, doc):
        return jsonify(ok=False), 409
    vault.remove_document(doc, actor="customer", actor_id=current_student().id)
    return jsonify(ok=True)


@public_bp.route("/consent-to-travel/<int:case_id>/doc/<int:req_id>/choice", methods=["POST"])
@student_required
def ct_doc_choice(lang, case_id, req_id):
    _csrf()
    ct = _ct_or_404(case_id)
    req = _req_or_404(ct, req_id)
    choice = request.form.get("choice", "")
    choices = ct.doc_choices
    if choice == "":
        choices.pop(req.rule_key, None)
    elif choice in docs.choice_kinds(req.rule_key):
        choices[req.rule_key] = choice
    else:
        return jsonify(ok=False), 400
    ct.doc_choices = choices
    db.session.commit()
    return jsonify(ok=True)


# ------------------------------------------------------------------ send to OG (Pending OG Review — never payable yet)
@public_bp.route("/consent-to-travel/<int:case_id>/send", methods=["POST"])
@student_required
def ct_send(lang, case_id):
    _csrf()
    ct = _ct_or_404(case_id)
    gate = _editable_or_redirect(ct, lang)
    if gate is not None:
        return gate
    ok, err = service.submit(ct, current_student(), lang, bool(request.form.get("certify")), bool(request.form.get("terms")), {"ip": request.remote_addr, "ua": request.headers.get("User-Agent")})
    if ok:
        return redirect(url_for("public.ct_done", lang=lang, case_id=ct.case_id))
    c = service.ctx(ct, lang)
    step = service.step_by_key(c, "send")
    msg = {"accept": ("Please check both boxes to send your information.", "Marca las dos casillas para enviar tu información."),
           "incomplete": ("😊 A few answers are still missing. Let's finish them first.", "😊 Todavía faltan algunas respuestas. Terminémoslas primero."),
           "state": ("This request was already sent.", "Esta solicitud ya fue enviada.")}[err]
    return _render_step(ct, lang, step, c, errors={"_send": pick(msg, lang)})


@public_bp.route("/consent-to-travel/<int:case_id>/done")
@student_required
def ct_done(lang, case_id):
    ct = _ct_or_404(case_id)
    return render_template("consent_travel/done.html", ct=ct, account_url=_account_url(ct, lang))


@public_bp.route("/consent-to-travel/<int:case_id>/price/ack", methods=["POST"])
@student_required
def ct_price_ack(lang, case_id):
    _csrf()
    ct = _ct_or_404(case_id)
    if pricing.acknowledge(ct):
        service.log(ct, "consent_travel_price_acknowledged")
    return redirect(_account_url(ct, lang))
