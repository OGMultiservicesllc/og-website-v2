"""Customer-facing NJ Driver License Assistance intake. Every route acts only on the signed-in customer's OWN Driver License case: the
case is always looked up THROUGH `service.owned` from the signed-in student, never trusted from a URL — there is exactly one open case
per customer for this service, so no case id ever needs to appear in a URL at all (unlike Tax/Immigration, which support several cases)."""

from datetime import date

from flask import abort, flash, jsonify, redirect, render_template, request, url_for

from app import case_documents as vault
from app.auth import validate_csrf
from app.blueprints.public.routes import public_bp
from app.extensions import db
from app.i18n import get_text
from app.ratelimit import allow
from app.student_auth import current_student, student_required
from app.driver_license import docs, pricing, service, summary, terms
from app.driver_license.config import CONFIG
from app.tax.questions import STATES, pick


def _dl_or_404():
    dl = service.owned_current()
    if dl is None:
        abort(404)
    return dl


def _csrf():
    if not validate_csrf(request.form.get("csrf_token") or request.headers.get("X-CSRFToken")):
        abort(400)


def _account_url(dl, lang):
    return url_for("account.my_case_detail", lang=lang, case_id=dl.case_id)


def step_url(lang, key, **kw):
    return url_for("public.dl_step", lang=lang, step_key=key, **kw)


def home_url(dl, lang):
    if dl.status not in service.EDITABLE:
        return _account_url(dl, lang)
    c = service.ctx(dl, lang)
    key = dl.current_step if service.step_by_key(c, dl.current_step or "") else "intro"
    return step_url(lang, key)


# ------------------------------------------------------------------ entry
@public_bp.route("/nj-driver-license/start")
@student_required
def dl_start(lang):
    """Get Started: create the customer's Driver License case, or resume the one they already have."""
    dl, _created = service.start_or_resume(current_student(), lang)
    return redirect(home_url(dl, lang))


@public_bp.route("/nj-driver-license/terms")
def dl_terms(lang):
    return render_template("driver_license/terms.html", sections=terms.SECTIONS, version=terms.version_for(), cert=terms.CERTIFICATION, accept=terms.ACCEPTANCE)


@public_bp.route("/nj-driver-license/case")
@student_required
def dl_home(lang):
    return redirect(home_url(_dl_or_404(), lang))


# ------------------------------------------------------------------ self-service correction (NJ Driver License only — see service.can_self_edit)
@public_bp.route("/nj-driver-license/edit")
@student_required
def dl_edit_confirm(lang):
    """"Edit My Information": a confirmation step BEFORE unlocking (item 33) — one accidental click must never
    reopen a submitted case."""
    dl = _dl_or_404()
    if not service.can_self_edit(dl):
        return redirect(_account_url(dl, lang))
    return render_template("driver_license/edit_confirm.html", dl=dl)


@public_bp.route("/nj-driver-license/edit/start", methods=["POST"])
@student_required
def dl_edit_start(lang):
    _csrf()
    dl = _dl_or_404()
    ok, _err = service.start_self_edit(dl, current_student())
    if not ok:
        flash("This information can no longer be edited here." if lang != "es" else "Esta información ya no se puede editar aquí.", "error")
        return redirect(_account_url(dl, lang))
    return redirect(home_url(dl, lang))


@public_bp.route("/nj-driver-license/edit/discard")
@student_required
def dl_discard_confirm(lang):
    """Item 52: a real confirmation SCREEN before discarding — not a one-click JS popup."""
    dl = _dl_or_404()
    return render_template("driver_license/discard_confirm.html", dl=dl)


@public_bp.route("/nj-driver-license/edit/discard", methods=["POST"])
@student_required
def dl_edit_discard(lang):
    _csrf()
    dl = _dl_or_404()
    service.discard_self_edit(dl, current_student(), lang)
    return redirect(_account_url(dl, lang))


# ------------------------------------------------------------------ rendering helpers
def _values(c, step, form=None):
    out = {}
    for q in step.questions:
        if q.kind in ("note", "docs"):
            continue
        if form is not None and q.key in set(form.getlist("__q")):
            out[q.key] = form.getlist(q.key) if q.kind == "multi" else (form.get(q.key) or "")
        else:
            out[q.key] = c.raw(q.key) or ([] if q.kind == "multi" else "")
    return out


def _qview(dl, c, step, lang, form=None, errors=None):
    values = _values(c, step, form)
    rows = []
    for q in step.questions:
        opts = q.opts(c) if q.kind in ("choice", "select", "multi", "yn3") else []
        rows.append({"q": q, "label": pick(q.label, lang), "help": pick(q.help, lang) if q.help else "", "opts": opts, "value": values.get(q.key, ""),
                     "error": (errors or {}).get(q.key), "visible": c.visible(q.key), "secret": "", "ph": pick(q.ph, lang) if q.ph else ""})
    return rows


def _render_step(dl, lang, step, c, *, errors=None, form=None):
    prog = service.progress(c, step.key)
    extra = {}
    if step.key == "documents_vault":
        have, total, missing = docs.counts(dl)
        extra.update(doc_cards=docs.cards(dl, lang), have=have, missing=missing)
    if step.key in ("price", "review", "send"):
        extra.update(_special(dl, c, step, lang))
    return render_template("driver_license/step.html", dl=dl, c=c, step=step, rows=_qview(dl, c, step, lang, form, errors), errors=errors or {}, progress=prog,
                           states=STATES, today=date.today().isoformat(), title=pick(step.title, lang), **extra)


def _special(dl, c, step, lang):
    if step.key == "price":
        return {"price": pricing.customer_view(dl, c, lang)}
    if step.key == "review":
        have, total, missing = docs.counts(dl)
        return {"cards": summary.review_cards(dl, lang), "docs_missing": missing, "missing_answers": service.missing_answers(dl, lang)}
    if step.key == "send":
        have, total, missing = docs.counts(dl)
        return {"docs_missing": missing, "missing_answers": service.missing_answers(dl, lang), "cert": terms.CERTIFICATION, "accept": terms.ACCEPTANCE, "price": pricing.customer_view(dl, c, lang)}
    return {}


def _editable_or_redirect(dl, lang):
    if dl.status not in service.EDITABLE:
        return redirect(_account_url(dl, lang))
    return None


# ------------------------------------------------------------------ the interview
@public_bp.route("/nj-driver-license/s/<step_key>", methods=["GET", "POST"])
@student_required
def dl_step(lang, step_key):
    dl = _dl_or_404()
    c = service.ctx(dl, lang)
    step = service.step_by_key(c, step_key)
    if step is None:
        return redirect(home_url(dl, lang))
    if step.key != "documents_vault":
        gate = _editable_or_redirect(dl, lang)
        if gate is not None:
            return gate
    if request.method == "GET":
        if dl.status in service.EDITABLE and dl.current_step != step.key:
            dl.current_step = step.key
            db.session.commit()
        return _render_step(dl, lang, step, c)
    _csrf()
    if not allow(f"dl-step:{current_student().id}", 240, 60):
        abort(429)
    nav = request.form.get("nav", "next")
    autosave = request.form.get("autosave") == "1"
    if dl.status not in service.EDITABLE and step.key != "documents_vault":
        abort(403)
    errors = {}
    if step.kind == "form" and dl.status in service.EDITABLE:
        errors = service.save_step(dl, step, request.form, lang, strict=(nav == "next" and not autosave))
    if autosave:
        c2 = service.ctx(dl, lang)
        return jsonify(ok=True, visible=[q.key for q in step.questions if c2.visible(q.key)])
    if nav == "exit":
        flash("Saved. You can continue any time." if lang != "es" else "Guardado. Puedes continuar cuando quieras.", "success")
        return redirect(_account_url(dl, lang))
    c2 = service.ctx(dl, lang)
    if nav == "back":
        prev = service.neighbour(c2, step.key, -1)
        return redirect(step_url(lang, prev) if prev else _account_url(dl, lang))
    if errors:
        return _render_step(dl, lang, step, c2, errors=errors, form=request.form)
    nxt = service.neighbour(c2, step.key, +1)
    if nxt is None:
        return redirect(step_url(lang, "send"))
    return redirect(step_url(lang, nxt))


# ------------------------------------------------------------------ documents (upload now / later; the vault does the storing)
def _req_or_404(dl, req_id):
    case, req = vault.owned_requirement(current_student(), dl.case_id, req_id)
    if case is None or req is None or req.source_key != docs.SOURCE_KEY:
        abort(404)
    return req


@public_bp.route("/nj-driver-license/doc/<int:req_id>/upload", methods=["POST"])
@student_required
def dl_doc_upload(lang, req_id):
    _csrf()
    dl = _dl_or_404()
    req = _req_or_404(dl, req_id)
    if not allow(f"dl-upload:{current_student().id}", 60, 300):
        return jsonify(ok=False, error=get_text(lang, "flash_too_many")), 429
    f = request.files.get("file")
    error = vault.validate_upload(f, lang) if f and f.filename else get_text(lang, "case_choose_file")
    if error:
        return jsonify(ok=False, error=error), 422
    if req.status not in vault.CUSTOMER_CAN_UPLOAD:
        return jsonify(ok=False, error=get_text(lang, "case_cannot_upload")), 409
    vault.upload_for_requirement(req, f, uploaded_by="customer", uploaded_by_id=current_student().id)
    choices = dl.doc_choices
    if req.rule_key in choices:
        choices.pop(req.rule_key)
        dl.doc_choices = choices
        db.session.commit()
    return jsonify(ok=True)


@public_bp.route("/nj-driver-license/doc/<int:req_id>/remove", methods=["POST"])
@student_required
def dl_doc_remove(lang, req_id):
    _csrf()
    dl = _dl_or_404()
    req = _req_or_404(dl, req_id)
    doc = req.current_document
    if doc is None or not vault.customer_can_remove(req, doc):
        return jsonify(ok=False), 409
    vault.remove_document(doc, actor="customer", actor_id=current_student().id)
    return jsonify(ok=True)


@public_bp.route("/nj-driver-license/doc/<int:req_id>/choice", methods=["POST"])
@student_required
def dl_doc_choice(lang, req_id):
    _csrf()
    dl = _dl_or_404()
    req = _req_or_404(dl, req_id)
    choice = request.form.get("choice", "")
    choices = dl.doc_choices
    if choice == "":
        choices.pop(req.rule_key, None)
    elif choice in docs.choice_kinds(req.rule_key):
        choices[req.rule_key] = choice
    else:
        return jsonify(ok=False), 400
    dl.doc_choices = choices
    db.session.commit()
    return jsonify(ok=True)


# ------------------------------------------------------------------ send to OG
@public_bp.route("/nj-driver-license/send", methods=["POST"])
@student_required
def dl_send(lang):
    _csrf()
    dl = _dl_or_404()
    gate = _editable_or_redirect(dl, lang)
    if gate is not None:
        return gate
    ok, err = service.submit(dl, current_student(), lang, bool(request.form.get("certify")), bool(request.form.get("terms")), {"ip": request.remote_addr, "ua": request.headers.get("User-Agent")})
    if ok:
        return redirect(url_for("public.dl_done", lang=lang))
    c = service.ctx(dl, lang)
    step = service.step_by_key(c, "send")
    msg = {"accept": ("Please check both boxes to send your information.", "Marca las dos casillas para enviar tu información."),
           "incomplete": ("😊 A few answers are still missing. Let's finish them first.", "😊 Todavía faltan algunas respuestas. Terminémoslas primero."), "state": ("This was already sent.", "Esto ya fue enviado.")}[err]
    return _render_step(dl, lang, step, c, errors={"_send": pick(msg, lang)})


@public_bp.route("/nj-driver-license/done")
@student_required
def dl_done(lang):
    dl = _dl_or_404()
    have, total, missing = docs.counts(dl)
    return render_template("driver_license/done.html", dl=dl, missing=missing, account_url=_account_url(dl, lang))


@public_bp.route("/nj-driver-license/price/ack", methods=["POST"])
@student_required
def dl_price_ack(lang):
    _csrf()
    dl = _dl_or_404()
    if pricing.acknowledge(dl):
        service.log(dl, "dl_price_acknowledged")
    return redirect(_account_url(dl, lang))
