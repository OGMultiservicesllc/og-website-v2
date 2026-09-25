"""ITIN Application pricing: $270 primary + $150 spouse + $125 per child/dependent, fully data-driven
(`ItinPriceRule` rows, Admin -> ITIN -> Pricing) — nothing hardcoded in a route or template, same convention
as `app/driver_license/pricing.py` / `app/tax/pricing.py`. Derived strictly from the REAL people who have a
W-7 application in the case (`itin.applicants(case)`), never from a visual/answer field: since every ITIN
applicant is created once, together, at case setup (`itin.apply_setup`), the total is stable across Save &
Resume by construction — there is no separate "selection" that could drift from the actual applications.
Same estimate -> confirm -> revision-history shape as DL/Tax: a confirmed price is never silently replaced.
"""

import json
from datetime import datetime

from app.extensions import db
from app.models import ItinPriceQuote, ItinPriceRule

SEED = [
    {"code": "primary", "label_en": "Primary applicant", "label_es": "Solicitante principal", "amount_cents": 27000, "sort_order": 10},
    {"code": "spouse", "label_en": "Spouse", "label_es": "Cónyuge", "amount_cents": 15000, "sort_order": 20},
    {"code": "dependent", "label_en": "Child / dependent", "label_es": "Hijo / dependiente", "amount_cents": 12500, "sort_order": 30},
]


def ensure_seed():
    have = {r.code for r in ItinPriceRule.query.all()}
    added = 0
    for row in SEED:
        if row["code"] not in have:
            db.session.add(ItinPriceRule(**row))
            added += 1
    if added:
        db.session.commit()
    return added


def rule_for(kind):
    return ItinPriceRule.query.filter_by(code=kind, active=True).first()


def fmt(cents):
    return f"${(cents or 0) / 100:,.2f}"


def estimate(case):
    """{lines, system_estimate_cents} — one line per ITIN applicant (primary, spouse, then each dependent
    numbered in order), the real per-applicant fee from `ItinPriceRule`, and the person's real name when
    the case already has one (never a placeholder)."""
    from app import itin

    lines, total, dep_n = [], 0, 0
    for a in itin.applicants(case):
        kind = a["kind"]
        rule = rule_for(kind)
        amount = rule.amount_cents if rule else 0
        if kind == "primary":
            role_en, role_es = "Primary applicant", "Solicitante principal"
        elif kind == "spouse":
            role_en, role_es = "Spouse", "Cónyuge"
        else:
            dep_n += 1
            role_en, role_es = f"Child {dep_n}", f"Hijo/a {dep_n}"
        name = a["person"].full_name.strip() if a["person"] and a["person"].full_name else None
        lines.append({"code": f"{kind}:{a['submission'].id}", "kind": kind, "amount_cents": amount,
                      "role_en": role_en, "role_es": role_es, "person_name": name})
        total += amount
    return {"lines": lines, "system_estimate_cents": total}


def snapshot(case, *, staff=None, source="system"):
    from app import itin

    cd = itin.case_data(case, create=True)
    est = estimate(case)
    lines_json = json.dumps(est["lines"], ensure_ascii=False)
    last = cd.current_quote
    if last is not None and last.source == "system" and last.lines_json == lines_json:
        return last, False
    confirmed = next((q for q in reversed(cd.quotes) if q.status == "confirmed"), None)
    nxt = (cd.quotes[-1].revision + 1) if cd.quotes else 1
    status = "revised" if confirmed is not None else "estimated"
    for q in cd.quotes:
        if q.status in ("estimated", "revised"):
            q.status = "superseded"
    quote = ItinPriceQuote(itin_case_id=cd.id, revision=nxt, source=source, lines_json=lines_json,
                           system_estimate_cents=est["system_estimate_cents"], status=status, staff=staff,
                           previous_total_cents=confirmed.final_total_cents if confirmed is not None else None)
    db.session.add(quote)
    cd.price_status = "confirmed" if confirmed is not None else "estimated"
    db.session.flush()
    # `cd.quotes` was already read above (the "current_quote"/loop lines), so it's cached stale in this Session
    # without the row just added — expire it so a caller in the SAME request (e.g. admin's "confirm price",
    # which calls snapshot() then confirm() back to back) sees the new quote instead of "no estimate yet".
    db.session.expire(cd, ["quotes"])
    return quote, True


def confirm(case, total_cents, staff, reason=None):
    from app import itin

    cd = itin.case_data(case, create=True)
    cur = cd.current_quote
    if cur is None:
        raise ValueError("There is no estimate yet.")
    prev = next((q for q in reversed(cd.quotes) if q.status == "confirmed"), None)
    differs = total_cents != cur.system_estimate_cents
    if (differs or (prev is not None and prev.final_total_cents != total_cents)) and not (reason or "").strip():
        raise ValueError("Write the reason for this price.")
    if total_cents is None or total_cents < 0 or total_cents > 10_000_000:
        raise ValueError("Enter a valid amount.")
    nxt = cd.quotes[-1].revision + 1
    for q in cd.quotes:
        if q.status in ("estimated", "revised", "confirmed"):
            q.status = "superseded"
    quote = ItinPriceQuote(itin_case_id=cd.id, revision=nxt, source="admin", lines_json=cur.lines_json, system_estimate_cents=cur.system_estimate_cents,
                           final_total_cents=total_cents, previous_total_cents=prev.final_total_cents if prev is not None else None, status="confirmed",
                           reason=(reason or "").strip()[:400] or None, staff=staff, needs_ack=bool(prev is not None and prev.final_total_cents != total_cents))
    db.session.add(quote)
    cd.price_status = "confirmed"
    db.session.commit()
    return quote


def acknowledge(case):
    from app import itin

    cd = itin.case_data(case)
    q = cd.current_quote if cd else None
    if q is not None and q.needs_ack and q.acknowledged_at is None:
        q.acknowledged_at = datetime.utcnow()
        db.session.commit()
        return True
    return False


def _fmt_lines(lines, lang):
    en = lang != "es"
    out = []
    for l in lines:
        role = l["role_en"] if en else l["role_es"]
        label = f"{role} — {l['person_name']}" if l.get("person_name") else role
        out.append({"label": label, "amount": fmt(l["amount_cents"])})
    return out


def customer_view(case, lang):
    """(EN/ES) breakdown for the customer — Final Review / My Account, e.g.
    "Primary applicant ... $270", "Spouse ... $150", "Child 1 ... $125", "Estimated/Service Total ... $670"."""
    from app import itin

    en = lang != "es"
    cd = itin.case_data(case)
    confirmed = next((x for x in reversed(cd.quotes) if x.status == "confirmed"), None) if cd else None
    if confirmed is not None:
        return {"state": "confirmed", "lines": _fmt_lines(confirmed.lines, lang), "final": fmt(confirmed.final_total_cents),
               "total_label": "Service Total" if en else "Total del Servicio",
               "needs_ack": bool(confirmed.needs_ack and confirmed.acknowledged_at is None),
               "previous": fmt(confirmed.previous_total_cents) if confirmed.previous_total_cents else None}
    est = estimate(case)
    return {"state": "estimate" if est["lines"] else "none", "lines": _fmt_lines(est["lines"], lang), "subtotal": fmt(est["system_estimate_cents"]),
           "total_label": "Estimated Total" if en else "Total Estimado"}
