"""NJ Driver License Assistance — translation + appointment-assistance pricing. Fully data-driven (`DlPriceRule` rows, Admin -> Driver
License -> Pricing), exactly like the Tax Return pricing engine (`app/tax/pricing.py`): nothing here is a hard-coded price in a template.
A translation whose document/language combination has no configured rule, or whose document needs a closer look (e.g. a non-standard
birth certificate), becomes "OG Review" rather than a guessed price. Cases already quoted keep their own snapshot (`DlPriceQuote`).
"""

import json
from datetime import datetime

from app.extensions import db
from app.models import DlPriceQuote, DlPriceRule

R = lambda code, kind, en, es, cents=None, *, doc_key=None, lang_key=None, requires_review=False, sort=0: dict(  # noqa: E731
    code=code, kind=kind, label_en=en, label_es=es, amount_cents=cents, doc_key=doc_key, lang_key=lang_key, requires_review=requires_review, sort_order=sort)

SEED = [
    R("trans_es_national_id", "translation", "National ID / Cédula — Spanish to English", "Identificación Nacional / Cédula — Español a Inglés", 3500, doc_key="national_id", lang_key="es", sort=10),
    R("trans_es_foreign_license", "translation", "Foreign Driver License — Spanish to English", "Licencia de Conducir Extranjera — Español a Inglés", 3500, doc_key="foreign_license", lang_key="es", sort=11),
    R("trans_es_birth_certificate", "translation", "Birth Certificate — Spanish to English (standard, single-page)", "Acta de Nacimiento — Español a Inglés (estándar, una página)", 3500, doc_key="birth_certificate", lang_key="es", sort=12),
    R("trans_pt_id_license", "translation", "National ID / Driver License — Portuguese to English", "Identificación / Licencia — Portugués a Inglés", 4500, doc_key=None, lang_key="pt", sort=20),
    R("trans_fr_id_license", "translation", "National ID / Driver License — French to English", "Identificación / Licencia — Francés a Inglés", 4500, doc_key=None, lang_key="fr", sort=21),
    R("affidavit_no_ssn_itin", "affidavit", "Affidavit of No SSN / ITIN — Preparation Assistance", "Declaración Jurada de No SSN / ITIN — Asistencia de Preparación", 2500, sort=25),
    R("appointment_initial_permit", "appointment", "Initial Permit — Appointment Assistance", "Permiso Inicial — Asistencia con la Cita", 1000, sort=30),
]


def ensure_seed():
    have = {r.code for r in DlPriceRule.query.all()}
    added = 0
    for row in SEED:
        if row["code"] not in have:
            db.session.add(DlPriceRule(**row))
            added += 1
    if added:
        db.session.commit()
    return added


def rules_for_kind(kind):
    return [r for r in DlPriceRule.query.filter_by(kind=kind, active=True).order_by(DlPriceRule.sort_order, DlPriceRule.id).all()]


def _money(cents):
    return f"${cents / 100:,.2f}"


def fmt(cents):
    return _money(cents or 0)


def translation_rule(doc_key, lang_key):
    """The best-matching active translation rule, or None (falls to OG Review: no price was configured for this combination)."""
    if lang_key in (None, "en"):
        return None
    rules = rules_for_kind("translation")
    exact = next((r for r in rules if r.doc_key == doc_key and r.lang_key == lang_key), None)
    if exact:
        return exact
    return next((r for r in rules if r.doc_key is None and r.lang_key == lang_key), None)


def appointment_rule():
    rows = rules_for_kind("appointment")
    return rows[0] if rows else None


def affidavit_rule():
    rows = rules_for_kind("affidavit")
    return rows[0] if rows else None


def estimate(dl, ctx):
    """{lines, system_estimate_cents, has_review_item, mode}. `ctx` gives the answers (doc selections, languages, appointment need).

    Only translates the documents `rules.document_plan()` actually marks "needed" (OG's stated priority: foreign license,
    then national ID, then birth certificate — the smallest useful set, never every translatable document the customer
    happens to have). A document marked "alternative" is never priced or sold a translation."""
    lines, total, review = [], 0, False
    from app.driver_license import rules as dl_rules
    from app.driver_license.config import OTHER_TRANSLATABLE, doc_lang_value

    docs = ctx.v("documents") or []
    plan = dl_rules.document_plan(docs)
    complex_bc = ctx.v("bc_standard") in ("no", "unsure")

    def add_line(doc_key, lang, *, needs_review_extra=False, label_en=None, label_es=None):
        nonlocal total, review
        if not lang or lang == "en":
            return
        label_en = label_en or dl_rules.document_label(doc_key, "en")
        label_es = label_es or dl_rules.document_label(doc_key, "es")
        needs_review = lang == "other" or needs_review_extra
        rule = None if needs_review else translation_rule(doc_key, lang)
        if rule is None:
            review = True
            lines.append({"code": f"review_{doc_key}", "label_en": f"{label_en} translation — needs OG review", "label_es": f"Traducción de {label_es} — requiere revisión de OG", "amount_cents": None, "requires_review": True})
        else:
            total += rule.amount_cents or 0
            lines.append({"code": rule.code, "label_en": rule.label_en, "label_es": rule.label_es, "amount_cents": rule.amount_cents, "requires_review": False})

    for d in docs:
        info = dl_rules.DOCUMENT_TYPES.get(d)
        if not info or not info.get("translatable") or plan.get(d) != "needed":
            continue
        lang = doc_lang_value(ctx, d)
        add_line(d, lang, needs_review_extra=(d == "birth_certificate" and complex_bc))

    # "Other documents that may need translation" (item 4): NJ address proof, ITIN evidence — same configured-price-else-review
    # rule as identity documents, never assumed to be a flat price, never mixed into the identity-document priority plan.
    for other_key, (lang_key, long_key) in OTHER_TRANSLATABLE.items():
        lang = ctx.v(lang_key)
        is_long = long_key and ctx.v(long_key) in ("yes", "unsure")
        if other_key == "address_proof":
            add_line("nj_address_proof", lang, needs_review_extra=is_long, label_en="NJ address proof document", label_es="Comprobante de dirección de NJ")
        elif other_key == "itin_evidence":
            add_line("itin_doc", lang, label_en="ITIN document", label_es="Documento de ITIN")

    if ctx.v("ssn_itin_path") == "neither":
        rule = affidavit_rule()
        if rule:
            total += rule.amount_cents or 0
            lines.append({"code": rule.code, "label_en": rule.label_en, "label_es": rule.label_es, "amount_cents": rule.amount_cents, "requires_review": False})

    if ctx.v("wants_appointment_help") == "yes":
        rule = appointment_rule()
        if rule:
            total += rule.amount_cents or 0
            lines.append({"code": rule.code, "label_en": rule.label_en, "label_es": rule.label_es, "amount_cents": rule.amount_cents, "requires_review": False})
    return {"lines": lines, "system_estimate_cents": total, "has_review_item": review, "mode": "manual" if review else "auto"}


def snapshot(dl, ctx, *, staff=None, source="system"):
    est = estimate(dl, ctx)
    last = dl.current_quote
    if last is not None and last.source == "system" and last.lines_json == json.dumps(est["lines"], ensure_ascii=False):
        return last, False
    confirmed = next((q for q in reversed(dl.quotes) if q.status == "confirmed"), None)
    nxt = (dl.quotes[-1].revision + 1) if dl.quotes else 1
    status = "revised" if confirmed is not None else "estimated"
    for q in dl.quotes:
        if q.status in ("estimated", "revised"):
            q.status = "superseded"
    quote = DlPriceQuote(dl_case_id=dl.id, revision=nxt, source=source, lines_json=json.dumps(est["lines"], ensure_ascii=False),
                         system_estimate_cents=est["system_estimate_cents"], has_review_item=est["has_review_item"], status=status,
                         staff=staff, previous_total_cents=confirmed.final_total_cents if confirmed is not None else None)
    db.session.add(quote)
    dl.price_status = "confirmed" if confirmed is not None else ("manual" if est["has_review_item"] else "estimated")
    db.session.flush()
    return quote, True


def confirm(dl, total_cents, staff, reason=None):
    cur = next((q for q in reversed(dl.quotes) if q.status in ("estimated", "revised", "confirmed")), None)
    if cur is None:
        raise ValueError("There is no estimate yet.")
    prev = next((q for q in reversed(dl.quotes) if q.status == "confirmed"), None)
    differs = total_cents != cur.system_estimate_cents
    if (differs or (prev is not None and prev.final_total_cents != total_cents)) and not (reason or "").strip():
        raise ValueError("Write the reason for this price.")
    if total_cents is None or total_cents < 0 or total_cents > 10_000_000:
        raise ValueError("Enter a valid amount.")
    nxt = dl.quotes[-1].revision + 1
    for q in dl.quotes:
        if q.status in ("estimated", "revised", "confirmed"):
            q.status = "superseded"
    quote = DlPriceQuote(dl_case_id=dl.id, revision=nxt, source="admin", lines_json=cur.lines_json, system_estimate_cents=cur.system_estimate_cents,
                         final_total_cents=total_cents, previous_total_cents=prev.final_total_cents if prev is not None else None, status="confirmed",
                         reason=(reason or "").strip()[:400] or None, staff=staff, needs_ack=bool(prev is not None and prev.final_total_cents != total_cents))
    db.session.add(quote)
    dl.price_status = "confirmed"
    db.session.commit()
    return quote


def acknowledge(dl):
    q = dl.current_quote
    if q is not None and q.needs_ack and q.acknowledged_at is None:
        q.acknowledged_at = datetime.utcnow()
        db.session.commit()
        return True
    return False


def customer_view(dl, ctx, lang):
    en = lang != "es"
    q = dl.current_quote
    confirmed = next((x for x in reversed(dl.quotes) if x.status == "confirmed"), None)
    if confirmed is not None and (q is None or q.status == "confirmed"):
        return {"state": "confirmed", "final": fmt(confirmed.final_total_cents), "needs_ack": bool(confirmed.needs_ack and confirmed.acknowledged_at is None), "previous": fmt(confirmed.previous_total_cents) if confirmed.previous_total_cents else None}
    est = estimate(dl, ctx)
    lines = [{"label": l["label_es"] if not en else l["label_en"], "amount": fmt(l["amount_cents"]) if l["amount_cents"] is not None else ("Requiere revisión" if lang == "es" else "Needs review")} for l in est["lines"]]
    return {"state": "review" if est["has_review_item"] else ("estimate" if lines else "none"), "lines": lines, "subtotal": fmt(est["system_estimate_cents"]), "has_review_item": est["has_review_item"]}
