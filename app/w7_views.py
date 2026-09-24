"""Customer-facing cards, the passport confirmation service and the review summary for the ITIN / W-7 intake.

Everything here shows what OG knows or what the customer said; nothing decides an ITIN, an IRS outcome or W-7 eligibility. Sensitive identifiers (passport, visa, ITIN, SSN) are
shown masked; only the customer's own confirmation form (their own draft, owner-checked) shows the typed values.
"""

import html
import json
from datetime import date, datetime

from flask import url_for

from app import cases as case_svc
from app import persons as pers
from app import w7_calc
from app import w7_docs as D
from app import w7_passport as PP
from app import w7_rules as R
from app import w7_text as T
from app.case_types import FACTS
from app.extensions import db
from app.intake_records import parse_date

# (answer, label EN, label ES, kind, required). Only what the passport photo page shows, plus place of birth (the MRZ does not carry it).
PASSPORT_FIELDS = [
    ("a_family", "Surnames (family name)", "Apellidos", "text", True), ("a_given", "Given names", "Nombres", "text", True), ("a_middle", "Middle name (if any)", "Segundo nombre (si tiene)", "text", False),
    ("a_dob", "Date of birth", "Fecha de nacimiento", "date", True), ("a_sex", "Sex", "Sexo", "sex", True), ("a_birth_city", "City of birth", "Ciudad de nacimiento", "text", True),
    ("a_birth_country", "Country of birth", "País de nacimiento", "text", True), ("a_nationality", "Nationality (country of citizenship)", "Nacionalidad (país de ciudadanía)", "text", True),
    ("a_pp_number", "Passport number", "Número de pasaporte", "number", True), ("a_pp_country", "Country that issued the passport", "País que emitió el pasaporte", "text", True),
    ("a_pp_issued", "Issue date", "Fecha de emisión", "date", False), ("a_pp_expiry", "Expiration date", "Fecha de vencimiento", "date", True),
]

def _e(x):
    return html.escape(str(x if x is not None else ""))


def mask(value):
    v = "".join(ch for ch in str(value or "") if ch.isalnum())
    return ("•" * max(len(v) - 4, 0) + v[-4:]) if v else ""


def _card(inner, tone="accent"):
    return f'<div class="rounded-xl border border-{tone}-200 bg-mist-50 px-4 py-3">{inner}</div>'


def _link(endpoint, **kw):
    try:
        return url_for(endpoint, **kw)
    except RuntimeError:
        return "#"


def _lang_of(lang):
    return lang if lang in ("en", "es") else "en"


def _btn(label, href, primary=True):
    cls = "bg-accent-600 text-white hover:bg-accent-700" if primary else "border border-slate-200 text-accent-700 hover:border-accent-300 bg-white"
    return f'<a href="{_e(href)}" class="inline-flex items-center justify-center min-h-[46px] rounded-xl px-5 text-[14px] font-semibold transition {cls}">{_e(label)}</a>'


def passport_url(submission, lang="en"):
    return _link("public.og_form_passport", lang=lang, slug=submission.form.slug, t=submission.resume_token)


# ------------------------------------------------------------------ dynamic cards (intake steps)
def context_html(submission, lang="en"):
    """Who this application is for, and the tax year — nothing else (the intro page must stay very short)."""
    en = lang == "en"
    case = submission.case
    cp = case_svc.role_person(submission, "itin_applicant")
    if case is None or cp is None:
        return ""
    cd = case.itin_data
    year = f'<p class="text-[14px] text-slate-600">{_e("Tax Year" if en else "Año fiscal")} {_e(cd.tax_year)}</p>' if cd is not None and cd.tax_year else ""
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{_e("This application is for:" if en else "Esta solicitud es para:")}</p>'
                 f'<p class="text-[19px] font-extrabold tracking-tight text-brand-800 break-words">{_e(cp.full_name)}</p>{year}')


def passport_html(submission, lang="en"):
    en = lang == "en"
    st = D.passport_state(submission)
    href = passport_url(submission, lang)
    if st["confirmed"]:
        a = case_svc.answers_by_name(submission)
        body = (f'<p class="text-[15px] font-semibold text-emerald-700"><span aria-hidden="true">&#10003;</span> {_e("Passport information confirmed" if en else "Información del pasaporte confirmada")}</p>'
                f'<p class="mt-1 text-[13px] text-slate-600 break-words">{_e(a.get("a_given", ""))} {_e(a.get("a_family", ""))} &middot; {_e("Passport" if en else "Pasaporte")} {_e(mask(a.get("a_pp_number")))}</p>'
                f'<div class="mt-3">{_btn("Review or change" if en else "Revisar o cambiar", href, primary=False)}</div>')
        return _card(body, "emerald")
    if st["pending_confirm"]:
        body = (f'<p class="text-[15px] font-semibold text-brand-800">{_e("We found information on the passport." if en else "Encontramos información en el pasaporte.")}</p>'
                f'<p class="mt-1 text-[13px] text-slate-600">{_e("Check it and confirm it, or correct anything that is wrong." if en else "Revísala y confírmala, o corrige lo que esté mal.")}</p>'
                f'<div class="mt-3">{_btn("Review and confirm" if en else "Revisar y confirmar", href)}</div>')
        return _card(body)
    body = (f'<p class="text-[15px] font-semibold text-brand-800">📘 {_e("Upload the photo page of the passport" if en else "Sube la página con la foto del pasaporte")}</p>'
            f'<p class="mt-1 text-[13px] text-slate-600">{_e("We will read it and you only check the information." if en else "Nosotros leemos los datos y tú solo los revisas.")}</p>'
            f'<div class="mt-3 flex flex-wrap gap-2">{_btn("Upload the passport" if en else "Subir el pasaporte", href)}</div>'
            f'<p class="mt-3 text-[12px] text-slate-500">⏰ {_e("Don’t have it now? Press Continue and upload it later from My Account." if en else "¿No lo tienes ahora? Presiona Continuar y súbelo después desde Mi Cuenta.")}</p>')
    return _card(body)


def visa_html(submission, lang="en"):
    en = lang == "en"
    reqs = [r for r in D.requirements_of(submission) if r.rule_key == "w7.visa_page"]
    case = submission.case
    if not reqs or case is None:
        return ""
    r = reqs[0]
    href = _link("account.my_case_detail", lang=lang, case_id=case.id, _anchor=f"req-{r.id}")
    if r.current_document is not None:
        body = f'<p class="text-[15px] font-semibold text-emerald-700"><span aria-hidden="true">&#10003;</span> {_e("Visa page uploaded — OG will read it and ask you to confirm." if en else "Página de la visa subida — OG la leerá y te pedirá confirmar.")}</p>'
    else:
        body = (f'<p class="text-[15px] font-semibold text-brand-800">{_e("Upload the page with the U.S. visa (now or later)" if en else "Sube la página con la visa de EE. UU. (ahora o después)")}</p>'
                f'<div class="mt-3">{_btn("Upload the visa page" if en else "Subir la página de la visa", href, primary=False)}</div>')
    return _card(body)


# ------------------------------------------------------------------ passport confirmation service
def form_values(submission):
    """What the confirmation form shows: the pending reading (or the confirmed values, or what the application already holds)."""
    a = case_svc.answers_by_name(submission)
    out = {name: a.get(name) or "" for name, *_ in PASSPORT_FIELDS}
    row = PP.latest(submission, statuses=("pending",))
    if row is not None:
        for k, v in PP.values_of(row).items():
            if k in PP._ANSWER_OF and v:  # noqa: SLF001
                out[PP._ANSWER_OF[k]] = v  # noqa: SLF001
    return out, row


def validate_passport(posted, lang="en"):
    """(answers, errors) for the confirmation form."""
    en = lang == "en"
    answers, errors = {}, {}
    for name, le, ls, kind, required in PASSPORT_FIELDS:
        raw = (posted.get(name) or "").strip()
        if not raw:
            if required:
                errors[name] = "This is needed." if en else "Esto es necesario."
            continue
        if kind == "date":
            d = parse_date(raw)
            if d is None or d.year < 1900 or (name in ("a_dob", "a_pp_issued") and d > date.today()):
                errors[name] = "Enter a valid date." if en else "Escribe una fecha válida."
                continue
            raw = d.isoformat()
        elif kind == "sex":
            if raw not in ("male", "female"):
                errors[name] = "Choose one." if en else "Elige una opción."
                continue
        elif kind == "number":
            raw = "".join(ch for ch in raw.upper() if ch.isalnum())
            if not 5 <= len(raw) <= 15:
                errors[name] = "Enter the passport number as printed (5 to 15 letters or digits)." if en else "Escribe el número de pasaporte como está impreso (5 a 15 letras o dígitos)."
                continue
        else:
            raw = raw[:60]
        answers[name] = raw
    return answers, errors


def save_passport(submission, answers, lang="en"):
    """The customer confirmed / corrected the passport details. Writes the application answers, records the Person facts (conflicts become visible claims), recalculates
    everything and returns the list of conflicting fact keys."""
    from app.intake_shared import _set
    from app.itin import log_case_event

    form = submission.form
    fields = {f.internal_name: f for f in form.all_fields}
    written, conflicts, source = PP.confirm_typed(submission, answers)
    for name, value in written.items():
        _set(form, submission, fields, name, value)
    submission.updated_at = datetime.utcnow()
    db.session.commit()
    w7_calc.write(form, submission, fields)
    D.sync(submission)
    if submission.is_complete:
        from app.intake_engine import build_snapshot

        submission.snapshot_json = build_snapshot(form, submission)
    db.session.commit()
    try:
        case_svc.sync_claims(submission)
    except Exception:  # noqa: BLE001
        db.session.rollback()
    if submission.case is not None:
        log_case_event(submission.student_id, "w7_passport_confirmed", submission.case, {"source": source, "application": submission.code}, entity=("submission", submission.id))
    return conflicts


def conflict_rows(submission, lang="en"):
    """[{key, label, kept, passport}] — passport facts that differ from what OG already confirmed for this real person (never resolved silently)."""
    cp = case_svc.role_person(submission, "itin_applicant")
    if cp is None:
        return []
    owner = pers.owner_of(cp)
    rows = []
    for fact in pers.open_conflicts(person=owner):
        mine = next((c for c in fact.claims if c.submission_id == submission.id and not c.resolved), None)
        if mine is None:
            continue
        meta = FACTS.get(fact.fact_key, {})
        rows.append({"key": fact.fact_key, "label": meta.get(lang, fact.fact_key), "kept": case_svc.display_fact_value(fact.fact_key, pers.fact_value(fact), lang, reveal=False),
                     "passport": case_svc.display_fact_value(fact.fact_key, json.loads(mine.value_json), lang, reveal=False), "value": json.loads(mine.value_json)})
    return rows


def resolve_conflicts(submission, choices, lang="en"):
    """choices: {fact_key: "passport" | "keep"}. The customer decides; the other value stays in the history as a claim."""
    from app.intake_shared import _set

    cp = case_svc.role_person(submission, "itin_applicant")
    if cp is None:
        return 0
    owner = pers.owner_of(cp)
    fields = {f.internal_name: f for f in submission.form.all_fields}
    n = 0
    for row in conflict_rows(submission, lang):
        pick = choices.get(row["key"])
        if pick == "passport":
            pers.update(owner, row["key"], row["value"], submission, actor="customer", source_field="passport confirmation")
            n += 1
        elif pick == "keep":
            fact = pers.get_fact(owner, row["key"])
            for c in fact.claims:
                if c.submission_id == submission.id:
                    c.resolved = True
            pers.confirm(owner, [row["key"]], submission, actor="customer")
            answer = next((k for k, v in PP._FACT_OF.items() if v == row["key"]), None)  # noqa: SLF001
            if answer:
                _set(submission.form, submission, fields, answer, pers.fact_value(pers.get_fact(owner, row["key"])))
            n += 1
    db.session.commit()
    return n


def after_upload(req, doc):
    """A document was stored for a requirement: a passport photo page gets a reading attempt (optional local backend only) and waits for the customer's confirmation."""
    if req.rule_key != "w7.passport" or not req.applications:
        return None
    from app.uploads import course_media_full_path

    submission = req.applications[0]
    values = PP.extract(course_media_full_path(doc.stored_filename))
    row = PP.add_extraction(submission, doc, "mrz_ocr", values or {}) if values else PP.add_extraction(submission, doc, "pending_read", {})
    D.sync(submission)
    w7_calc.write(submission.form, submission)
    db.session.commit()
    return row


def remove_passport(submission, req, doc, actor_id=None):
    """The customer took back the uploaded passport photo (only before OG started reviewing it: `vault.customer_can_remove`). The vault document is removed through the existing
    safe path; earlier readings stay as history (status superseded, no longer linked to the deleted file) and can never count as a confirmed passport again. The Person facts they
    produced keep their provenance. Everything is recalculated, so the passport is "needed" again and a new upload must be confirmed again."""
    from app import case_documents as vault
    from app.itin import log_case_event

    for row in list(submission.extractions):
        if row.kind == "passport" and row.status in ("pending", "confirmed"):
            row.status = "superseded"
        if row.document_id == doc.id:
            row.document_id = None
    db.session.flush()
    vault.remove_document(doc, actor="customer", actor_id=actor_id)
    db.session.refresh(submission)
    w7_calc.write(submission.form, submission)
    D.sync(submission)
    if submission.is_complete:
        from app.intake_engine import build_snapshot

        submission.snapshot_json = build_snapshot(submission.form, submission)
    db.session.commit()
    if submission.case is not None:
        log_case_event(submission.student_id, "w7_passport_removed", submission.case, {"application": submission.code}, entity=("submission", submission.id))


# ------------------------------------------------------------------ review summary (customer)
def _tick(ok, text, note=""):
    mark = '<span class="text-emerald-600" aria-hidden="true">&#10003;</span>' if ok else '<span class="text-amber-600" aria-hidden="true">&#9888;</span>'
    tail = f'<span class="block text-[12px] text-slate-500 break-words">{_e(note)}</span>' if note else ""
    return f'<li class="flex items-start gap-2 text-[14px] text-brand-800">{mark}<span class="min-w-0 break-words">{_e(text)}{tail}</span></li>'


def review_summary_html(submission, lang="en"):
    """Friendly ✓ / ⚠ summary by group + the document list. Missing documents show here as things to send later; they never block Send to OG."""
    en = lang == "en"
    a = case_svc.answers_by_name(submission)
    st = D.passport_state(submission)
    kind = D.kind_of(a)
    fl, _cand = w7_calc.flags(a, submission)
    codes = {f["code"] for f in fl}
    rows = []
    rows.append(_tick(st["confirmed"], "Passport information confirmed" if en else "Información del pasaporte confirmada",
                      "" if st["confirmed"] else ("Passport needed — you can upload it any time from My Account." if en else "Se necesita el pasaporte: puedes subirlo cuando quieras desde Mi Cuenta.") if not st["uploaded"] else ("Waiting for your confirmation of what we found." if en else "Esperando tu confirmación de lo que encontramos.")))
    if a.get("pp_status") == "none":
        cov = D.coverage_for(submission, planned=True)
        rows.append(_tick(bool(cov["ok"]), "Identification documents" if en else "Documentos de identificación", "" if cov["ok"] else ("OG will review what else is needed." if en else "OG revisará qué más se necesita.")))
    rows.append(_tick(bool(a.get("ua_street") and a.get("ua_city")), "U.S. mailing address" if en else "Dirección postal en EE. UU."))
    rows.append(_tick(bool(a.get("a_phone")), "Phone number" if en else "Número de teléfono"))
    rows.append(_tick(bool(a.get("a_entry_date")), "Date of entry to the U.S." if en else "Fecha de entrada a EE. UU."))
    if a.get("visa_entered") == "yes":
        vr = next((r for r in D.requirements_of(submission) if r.rule_key == "w7.visa_page"), None)
        rows.append(_tick(bool(vr is not None and vr.current_document is not None), "U.S. visa page" if en else "Página de la visa de EE. UU.", "" if (vr is not None and vr.current_document is not None) else ("Can be sent later." if en else "Se puede enviar después.")))
    if kind != "dependent":
        rows.append(_tick(bool(a.get("inc_type")), "Work and income" if en else "Trabajo e ingresos"))
    if "w2_identifier" in codes:
        rows.append(_tick(False, "W-2" if en else "W-2", T.W2_REVIEW[0 if en else 1]))
    if kind == "dependent":
        cov = D.coverage_for(submission, planned=True)
        rows.append(_tick(cov["residency"] is not False, "Proof of U.S. residency" if en else "Prueba de residencia en EE. UU.", "" if cov["residency"] is not False else ("OG will tell you which document fits." if en else "OG te dirá qué documento sirve.")))
    reqs = D.requirements_of(submission)
    got = sum(1 for r in reqs if r.current_document is not None)
    if reqs:
        rows.append(_tick(got == len(reqs), (f"Documents: {got} of {len(reqs)} uploaded" if en else f"Documentos: {got} de {len(reqs)} subidos"),
                          "" if got == len(reqs) else ("The rest can be uploaded later; you can still send this to OG now." if en else "Lo demás se puede subir después; aun así puedes enviar esto a OG ahora.")))
    pend = sum(1 for r in reqs if r.itin_track is not None and r.itin_track.original_required and r.itin_track.original_state in ("required", "will_mail", "will_bring"))
    if pend:
        rows.append(_tick(False, (f"Originals still to give OG: {pend}" if en else f"Originales que aún debes entregar a OG: {pend}"),
                          "Mail them or bring them to the Paterson office. A photo upload does not replace the original." if en else "Envíalos por correo o tráelos a la oficina de Paterson. Subir una foto no reemplaza el original."))
    head = "Where you are" if en else "Cómo vas"
    return (f'<div class="rounded-xl border border-mist-200 bg-mist-50 px-4 py-3"><p class="text-xs font-bold uppercase tracking-wider text-accent-700">{_e(head)}</p>'
            f'<ul class="mt-2 space-y-1.5">{"".join(rows)}</ul></div><div class="mt-4">{D.documents_html(submission, lang)}</div>')


# ------------------------------------------------------------------ admin (application detail panel)
def admin_summary(submission):
    """What OG staff see on the application page: the applicant, the ITIN case, passport / reason / CAA state and the flag list. Identifiers stay masked here (the W-7 Preparation View shows them)."""
    from app import itin

    a = case_svc.answers_by_name(submission)
    cp = case_svc.role_person(submission, "itin_applicant")
    fl, cand = w7_calc.flags(a, submission)
    reqs = D.requirements_of(submission)
    w = submission.w7
    return {"person": cp, "kind": itin.kind_label(D.kind_of(a)), "flags": fl, "candidate": w7_calc.REASON_LABEL.get(cand, ("", ""))[0], "w": w, "passport": D.passport_state(submission),
            "docs_got": sum(1 for r in reqs if r.current_document is not None), "docs_total": len(reqs), "case": submission.case, "pp_status": a.get("pp_status") or "have",
            "siblings": [x for x in itin.applicants(submission.case) if x["submission"].id != submission.id] if submission.case is not None else []}
