"""Consent to Travel pricing — fully data-driven (`ConsentTravelPriceRule` rows, Admin -> Consent to Travel ->
Pricing), exactly like Tax/NJ Driver License. $60 per document (includes the first child in that document),
+$10 for every additional child grouped into the SAME document (same consenting parent(s) — see `rules.py`).
A child with no consenting parent needed does not add a document/charge. Payment is never requestable until
OG explicitly approves and confirms a price — see `service.py confirm_price`/`app.payments`.
"""

import json
from datetime import datetime

from app.extensions import db
from app.models import ConsentTravelPriceRule, ConsentTravelQuote

SEED = [
    ("base_document", "Consent to Travel Document", "Documento de Autorización de Viaje", 6000),
    ("additional_child", "Additional Child (same document)", "Menor Adicional (mismo documento)", 1000),
]


def ensure_seed():
    have = {r.code for r in ConsentTravelPriceRule.query.all()}
    added = 0
    for code, en, es, cents in SEED:
        if code not in have:
            db.session.add(ConsentTravelPriceRule(code=code, label_en=en, label_es=es, amount_cents=cents))
            added += 1
    if added:
        db.session.commit()
    return added


def _rule(code):
    return ConsentTravelPriceRule.query.filter_by(code=code, active=True).first()


def _money(cents):
    return f"${cents / 100:,.2f}"


def fmt(cents):
    return _money(cents or 0)


def estimate(ct, groups, lang="en"):
    """{lines, system_estimate_cents}. `groups` = `rules.group_documents()` output. One line per document
    group that actually needs one (a group with an empty consenting set costs nothing)."""
    base = _rule("base_document")
    extra = _rule("additional_child")
    base_cents = base.amount_cents if base else 6000
    extra_cents = extra.amount_cents if extra else 1000
    lines, total = [], 0
    doc_n = 0
    for g in groups:
        n = len(g["children"])
        names = [c["name"] for c in g["children"]]
        if not g["consenting"]:
            lines.append({"code": "no_document", "children": names, "amount_cents": None,
                          "label_en": f"{', '.join(names)} — no consenting parent required (no separate document)",
                          "label_es": f"{', '.join(names)} — no se requiere el consentimiento de otro padre (sin documento aparte)"})
            continue
        doc_n += 1
        amount = base_cents + extra_cents * max(0, n - 1)
        total += amount
        lines.append({"code": f"document_{doc_n}", "children": names, "amount_cents": amount,
                      "label_en": f"Consent to Travel Document {doc_n} — {n} {'child' if n == 1 else 'children'}",
                      "label_es": f"Documento de Autorización de Viaje {doc_n} — {n} {'menor' if n == 1 else 'menores'}"})
    return {"lines": lines, "system_estimate_cents": total}


def snapshot(ct, groups):
    est = estimate(ct, groups)
    last = ct.current_quote
    if last is not None and last.source == "system" and last.lines_json == json.dumps(est["lines"], ensure_ascii=False):
        return last, False
    confirmed = next((q for q in reversed(ct.quotes) if q.status == "confirmed"), None)
    nxt = (ct.quotes[-1].revision + 1) if ct.quotes else 1
    status = "revised" if confirmed is not None else "estimated"
    for q in ct.quotes:
        if q.status in ("estimated", "revised"):
            q.status = "superseded"
    quote = ConsentTravelQuote(ct_case_id=ct.id, revision=nxt, source="system", lines_json=json.dumps(est["lines"], ensure_ascii=False),
                               system_estimate_cents=est["system_estimate_cents"], status=status,
                               previous_total_cents=confirmed.final_total_cents if confirmed is not None else None)
    db.session.add(quote)
    db.session.flush()
    return quote, True


def confirm(ct, total_cents, staff, reason=None):
    """OG approval action: sets the FINAL, authoritative price. This is the ONLY thing that makes a
    PaymentRequest possible — see `service.approve`."""
    cur = ct.current_quote
    prev = next((q for q in reversed(ct.quotes) if q.status == "confirmed"), None)
    if total_cents is None or total_cents < 0 or total_cents > 10_000_000:
        raise ValueError("Enter a valid amount.")
    nxt = (ct.quotes[-1].revision + 1) if ct.quotes else 1
    for q in ct.quotes:
        if q.status in ("estimated", "revised", "confirmed"):
            q.status = "superseded"
    quote = ConsentTravelQuote(ct_case_id=ct.id, revision=nxt, source="admin", lines_json=cur.lines_json if cur else "[]",
                               system_estimate_cents=cur.system_estimate_cents if cur else None, final_total_cents=total_cents,
                               previous_total_cents=prev.final_total_cents if prev is not None else None, status="confirmed",
                               reason=(reason or "").strip()[:400] or None, staff=staff,
                               needs_ack=bool(prev is not None and prev.final_total_cents != total_cents))
    db.session.add(quote)
    ct.price_status = "confirmed"
    db.session.commit()
    return quote


def acknowledge(ct):
    q = ct.current_quote
    if q is not None and q.needs_ack and q.acknowledged_at is None:
        q.acknowledged_at = datetime.utcnow()
        db.session.commit()
        return True
    return False


def customer_view(ct, groups, lang):
    en = lang != "es"
    confirmed = next((q for q in reversed(ct.quotes) if q.status == "confirmed"), None)
    if confirmed is not None and ct.current_quote is confirmed:
        return {"state": "confirmed", "final": fmt(confirmed.final_total_cents), "needs_ack": bool(confirmed.needs_ack and confirmed.acknowledged_at is None),
                "previous": fmt(confirmed.previous_total_cents) if confirmed.previous_total_cents else None}
    est = estimate(ct, groups)
    lines = [{"label": (l["label_es"] if not en else l["label_en"]), "amount": fmt(l["amount_cents"]) if l["amount_cents"] is not None else None} for l in est["lines"]]
    return {"state": "estimate" if lines else "none", "lines": lines, "subtotal": fmt(est["system_estimate_cents"])}
