"""Tax Pricing Engine — DATA-DRIVEN. No preparation price is written in a template or in the branching code: every amount, percentage, threshold and manual-review trigger is a
`TaxPriceRule` row for a tax year, edited in Admin. Cases keep a PRICING SNAPSHOT (`TaxPriceQuote.config_json`) so later price changes never rewrite history.

The engine estimates the OG preparation fee from FACTS (never from tax forms: nothing is charged per schedule or per credit). The pricing categories (single / married / family)
are NOT filing-status conclusions. A complex situation (or an estimate above the automatic-quote threshold) becomes a MANUAL quote: the customer is told OG will confirm the price;
staff still see the calculated estimate. The returning-client discount comes from OG's own tax history and applies to the preparation fee only.
"""

import json
from datetime import datetime

from app.extensions import db
from app.models import TaxPriceQuote, TaxPriceRule
from app.tax import flags as tax_flags
from app.tax.questions import pick

R = lambda code, kind, en, es, cents=None, percent=None, active=True, params=None, sort=0: dict(  # noqa: E731
    code=code, kind=kind, label_en=en, label_es=es, amount_cents=cents, percent=percent, active=active, params_json=json.dumps(params) if params else None, sort_order=sort)

SEED_2025 = [
    R("base_single", "base", "Single, no dependents (up to 3 W-2)", "Soltero(a), sin dependientes (hasta 3 W-2)", 15000, params={"included_w2": 3}, sort=10),
    R("base_mfj", "base", "Married, no dependents (up to 3 W-2 combined)", "Casado(a), sin dependientes (hasta 3 W-2 en total)", 17500, params={"included_w2": 3}, sort=11),
    R("base_hoh", "base", "Family return, unmarried with dependents (up to 3 dependents and 3 W-2)", "Declaración familiar, sin cónyuge y con dependientes (hasta 3 dependientes y 3 W-2)", 19000, params={"included_w2": 3, "included_deps": 3}, sort=12),
    R("base_mfj_family", "base", "Family return, married with dependents (up to 3 dependents and 3 W-2)", "Declaración familiar, casado(a) con dependientes (hasta 3 dependientes y 3 W-2)", 21000, params={"included_w2": 3, "included_deps": 3}, sort=13),
    R("base_qss", "base", "Family return, widowed with dependents", "Declaración familiar, viudo(a) con dependientes", 19000, params={"included_w2": 3, "included_deps": 3}, sort=14),
    R("extra_dependent", "addon", "Each dependent after the first 3", "Cada dependiente después de los primeros 3", 1500, sort=20),
    R("extra_w2", "addon", "Each W-2 after the first 3", "Cada W-2 después de los primeros 3", 1000, sort=21),
    R("se_simple", "addon", "Self-employment — simple", "Trabajo por cuenta propia — sencillo", 10000, sort=30),
    R("se_moderate", "addon", "Self-employment — moderate", "Trabajo por cuenta propia — moderado", 15000, sort=31),
    R("se_extra_activity", "addon", "Each additional separate business activity", "Cada actividad de negocio separada adicional", 7500, sort=32),
    R("marketplace", "addon", "Marketplace health coverage (Form 1095-A)", "Seguro del Marketplace (Form 1095-A)", 3000, sort=40),
    R("childcare", "addon", "Childcare expenses", "Gastos de cuidado de niños", 2500, sort=41),
    R("education", "addon", "Education", "Educación", 2500, sort=42),
    R("unemployment", "addon", "Unemployment income", "Ingreso de unemployment", 1500, sort=43),
    R("retirement", "addon", "Simple retirement / pension income", "Ingreso sencillo de retiro / pensión", 2000, sort=44),
    R("social_security", "addon", "Social Security (included)", "Social Security (incluido)", 0, sort=45),
    R("interest_dividends", "addon", "Simple interest / dividends (included)", "Intereses / dividendos sencillos (incluido)", 0, sort=46),
    R("investment_sales", "addon", "Investment sales (a few, simple)", "Ventas de inversiones (pocas, sencillas)", 5000, sort=47),
    R("rental_property", "addon", "Each rental property", "Cada propiedad alquilada", 10000, sort=48),
    R("itemized", "addon", "Itemized-deduction complexity", "Complejidad de deducciones detalladas", 5000, sort=49),
    R("extra_state", "addon", "Additional state return", "Declaración de un estado adicional", 5000, sort=50),
    R("crypto_simple", "addon", "Simple crypto activity", "Actividad sencilla de crypto", 5000, sort=51),
    R("returning_discount", "discount", "OG Returning Client Discount", "Descuento de Cliente Recurrente de OG", None, 10.0, params={"stackable": False, "applies_to": "preparation"}, sort=60),
    R("max_auto_quote", "setting", "Maximum automatic quote", "Cotización automática máxima", 40000, sort=70),
    R("se_moderate_expense_cats", "setting", "Self-employment: expense categories that make it moderate", "Trabajo por cuenta propia: categorías de gastos para considerarlo moderado", None, params={"value": 3}, sort=71),
    R("se_complex_expense_cats", "setting", "Self-employment: expense categories that make it complex", "Trabajo por cuenta propia: categorías de gastos para considerarlo complejo", None, params={"value": 6}, sort=72),
    R("se_moderate_sources", "setting", "Self-employment: income sources that make it moderate", "Trabajo por cuenta propia: fuentes de ingreso para considerarlo moderado", None, params={"value": 3}, sort=73),
    R("se_complex_sources", "setting", "Self-employment: income sources that make it complex", "Trabajo por cuenta propia: fuentes de ingreso para considerarlo complejo", None, params={"value": 5}, sort=74),
    R("itemized_charity_min", "setting", "Donations amount that counts as itemized complexity", "Monto de donaciones que cuenta como complejidad de deducciones", 50000, sort=75),
    R("trigger_foreign", "trigger", "Manual pricing: foreign income or accounts", "Precio manual: ingresos o cuentas en el extranjero", None, sort=80),
    R("trigger_complex_crypto", "trigger", "Manual pricing: complex or unclear crypto", "Precio manual: crypto complejo o poco claro", None, sort=81),
    R("trigger_complex_se", "trigger", "Manual pricing: complex self-employment", "Precio manual: trabajo por cuenta propia complejo", None, sort=82),
    R("trigger_part_year", "trigger", "Manual pricing: moved to another state (part-year / multi-state)", "Precio manual: se mudó a otro estado (parcial / varios estados)", None, sort=83),
    R("trigger_many_investments", "trigger", "Manual pricing: many or unclear investment sales", "Precio manual: muchas o poco claras ventas de inversiones", None, sort=84),
]


def ensure_seed(year=2025):
    """Idempotent: create the year's rows that do not exist yet. NEVER touches a row an administrator may have edited."""
    have = {r.code for r in TaxPriceRule.query.filter_by(tax_year=year).all()}
    seed = SEED_2025
    added = 0
    for row in seed:
        if row["code"] not in have:
            db.session.add(TaxPriceRule(tax_year=year, **row))
            added += 1
    if added:
        db.session.commit()
    return added


def rules_for(year):
    return {r.code: r for r in TaxPriceRule.query.filter_by(tax_year=year).order_by(TaxPriceRule.sort_order, TaxPriceRule.id).all()}


def _money(cents):
    return f"${cents / 100:,.2f}"


def fmt(cents):
    return _money(cents or 0)


# ------------------------------------------------------------------ classification of one self-employment activity
def classify_activity(record, rules):
    d = record.data
    if d.get("_level") in ("simple", "moderate", "complex"):
        return d["_level"], "override"

    def setting(code, default):
        r = rules.get(code)
        return int((r.params or {}).get("value", default)) if r is not None else default

    cats = list(d.get("b_exp_cats") or []) if d.get("b_exp") == "yes" else []
    sources = list(d.get("b_sources") or [])
    if "workers" in cats or len(cats) >= setting("se_complex_expense_cats", 6) or len(sources) >= setting("se_complex_sources", 5):
        return "complex", "auto"
    if d.get("b_vehicle") == "yes" or len(cats) >= setting("se_moderate_expense_cats", 3) or len(sources) >= setting("se_moderate_sources", 3):
        return "moderate", "auto"
    return "simple", "auto"


# ------------------------------------------------------------------ the estimate
def estimate(tax, ctx):
    """Deterministic estimate from the answers. Returns a dict (cents) ready to store as a quote."""
    rules = rules_for(tax.tax_year)
    on = lambda code: code in rules and rules[code].active  # noqa: E731
    amount = lambda code: (rules[code].amount_cents or 0) if code in rules else 0  # noqa: E731
    lines, manual = [], []

    def line(code, count=1, label_suffix=""):
        if not on(code) or count <= 0:
            return
        r = rules[code]
        total = amount(code) * count
        lines.append({"code": code, "count": count, "label_en": r.label_en + label_suffix, "label_es": r.label_es + label_suffix, "amount_cents": total})

    married = ctx.v("marital") == "married"
    n_deps = len([r for r in ctx.deps])
    if married:
        category = "mfj_family" if n_deps else "mfj"
    elif n_deps:
        category = "qss" if ctx.v("marital") == "widowed" else "hoh"
    else:
        category = "single"
    base_code = {"single": "base_single", "mfj": "base_mfj", "hoh": "base_hoh", "mfj_family": "base_mfj_family", "qss": "base_qss"}[category]
    line(base_code)
    params = rules[base_code].params if base_code in rules else {}
    w2 = int(ctx.num("w2_count", 0)) if ctx.has("income", "w2") else 0
    line("extra_w2", max(0, w2 - int(params.get("included_w2", 3))))
    line("extra_dependent", max(0, n_deps - int(params.get("included_deps", 3))) if n_deps else 0)

    levels = []
    for idx, b in enumerate(ctx.bizs):
        level, how = classify_activity(b, rules)
        levels.append({"id": b.id, "level": level, "how": how})
        if level == "complex":
            if on("trigger_complex_se"):
                manual.append("complex_se")
            continue
        if idx == 0:
            line("se_simple" if level == "simple" else "se_moderate")
        else:
            line("se_extra_activity")
    if ctx.has("h_sources", "marketplace"):
        line("marketplace")
    if ctx.v("cc_paid") == "yes":
        line("childcare")
    if ctx.v("e_student") == "yes":
        line("education")
    from app.tax.y2025 import mod

    if mod(ctx, "unemployment"):
        line("unemployment")
    if mod(ctx, "retirement"):
        line("retirement")
    if mod(ctx, "invest"):
        if ctx.v("invest_size") == "few":
            line("investment_sales")
        elif on("trigger_many_investments"):
            manual.append("many_investments")
    if mod(ctx, "rental"):
        line("rental_property", max(1, int(ctx.num("rental_count", 1))))
    charity_min = (rules["itemized_charity_min"].amount_cents if "itemized_charity_min" in rules else 50000) / 100
    if ctx.v("o_mortgage") == "yes" or ctx.num("ch_amount") >= charity_min or (ctx.has("situations", "medical") and ctx.num("med_amount") > 0):
        line("itemized")
    if ctx.v("state_other") == "yes":
        line("extra_state")
    if ctx.has("situations", "crypto"):
        if ctx.v("cr_size") == "simple":
            line("crypto_simple")
        elif on("trigger_complex_crypto"):
            manual.append("complex_crypto")
    if ctx.has("situations", "foreign") and on("trigger_foreign"):
        manual.append("foreign")
    if ctx.v("moved") == "other" and on("trigger_part_year"):
        manual.append("part_year")

    subtotal = sum(l["amount_cents"] for l in lines)
    max_auto = amount("max_auto_quote") if on("max_auto_quote") else None
    over = max_auto is not None and subtotal > max_auto
    mode = "manual" if (manual or over) else "auto"
    if over and "over_threshold" not in manual:
        manual.append("over_threshold")

    disc = rules.get("returning_discount")
    eligible = bool(tax.is_returning and disc is not None and disc.active and (disc.params.get("year") in (None, tax.tax_year)))
    percent = disc.percent if eligible else 0.0
    discount = int(round(subtotal * (percent or 0) / 100.0)) if eligible else 0
    snapshot = {code: {"amount_cents": r.amount_cents, "percent": r.percent, "active": r.active, "params": r.params} for code, r in rules.items()}
    return {"category": category, "lines": lines, "system_estimate_cents": subtotal, "discount_percent": percent if eligible else 0.0, "discount_cents": discount,
            "estimated_final_cents": subtotal - discount, "mode": mode, "manual_reasons": manual, "levels": levels, "returning_eligible": eligible,
            "max_auto_cents": max_auto, "config": snapshot, "flags": [f["code"] for f in tax_flags.flags(ctx)]}


# ------------------------------------------------------------------ quotes / history
def _same_as(q, est):
    return (q is not None and q.system_estimate_cents == est["system_estimate_cents"] and q.discount_cents == est["discount_cents"] and q.mode == est["mode"]
            and q.category == est["category"] and q.lines_json == json.dumps(est["lines"], ensure_ascii=False))


def snapshot(tax, ctx, *, staff=None, reason=None, source="system"):
    """Store the current estimate as a new revision when it changed. A CONFIRMED price is never silently replaced: a changed estimate becomes a `revised` quote that OG must confirm.
    Returns (quote, created)."""
    est = estimate(tax, ctx)
    last = tax.current_quote
    if _same_as(last, est) and last.source == "system":
        return last, False
    confirmed = next((q for q in reversed(tax.quotes) if q.status == "confirmed"), None)
    nxt = (tax.quotes[-1].revision + 1) if tax.quotes else 1
    status = "revised" if confirmed is not None else "estimated"
    for q in tax.quotes:
        if q.status in ("estimated", "revised"):
            q.status = "superseded"
    quote = TaxPriceQuote(tax_case_id=tax.id, revision=nxt, source=source, mode=est["mode"], category=est["category"], lines_json=json.dumps(est["lines"], ensure_ascii=False),
                          system_estimate_cents=est["system_estimate_cents"], discount_percent=est["discount_percent"], discount_cents=est["discount_cents"],
                          estimated_final_cents=est["estimated_final_cents"], status=status, staff=staff, reason=reason,
                          previous_fee_cents=confirmed.final_fee_cents if confirmed is not None else None,
                          config_json=json.dumps({"rules": est["config"], "levels": est["levels"], "manual": est["manual_reasons"], "max_auto_cents": est["max_auto_cents"]}, ensure_ascii=False),
                          flags_json=json.dumps(est["flags"]))
    db.session.add(quote)
    # the customer keeps seeing the CONFIRMED fee until OG confirms the revision
    tax.price_status = "confirmed" if confirmed is not None else ("manual" if est["mode"] == "manual" else "estimated")
    db.session.flush()
    return quote, True


def confirm(tax, fee_cents, staff, reason=None):
    """OG sets the final preparation fee (also when it equals the estimate). A reason is required when it differs from the estimate or replaces an earlier confirmed fee."""
    cur = next((q for q in reversed(tax.quotes) if q.status in ("estimated", "revised", "confirmed")), None)
    if cur is None:
        raise ValueError("There is no estimate yet.")
    prev = next((q for q in reversed(tax.quotes) if q.status == "confirmed"), None)
    differs = fee_cents != cur.estimated_final_cents
    if (differs or (prev is not None and prev.final_fee_cents != fee_cents)) and not (reason or "").strip():
        raise ValueError("Write the reason for this price.")
    if fee_cents is None or fee_cents < 0 or fee_cents > 10_000_000:
        raise ValueError("Enter a valid amount.")
    nxt = tax.quotes[-1].revision + 1
    for q in tax.quotes:
        if q.status in ("estimated", "revised", "confirmed"):
            q.status = "superseded"
    quote = TaxPriceQuote(tax_case_id=tax.id, revision=nxt, source="admin", mode=cur.mode, category=cur.category, lines_json=cur.lines_json, system_estimate_cents=cur.system_estimate_cents,
                          discount_percent=cur.discount_percent, discount_cents=cur.discount_cents, estimated_final_cents=cur.estimated_final_cents, final_fee_cents=fee_cents,
                          previous_fee_cents=prev.final_fee_cents if prev is not None else None, status="confirmed", reason=(reason or "").strip()[:400] or None, staff=staff,
                          config_json=cur.config_json, flags_json=cur.flags_json, needs_ack=bool(prev is not None and prev.final_fee_cents != fee_cents))
    db.session.add(quote)
    tax.price_status = "confirmed"
    db.session.commit()
    return quote


def acknowledge(tax):
    q = tax.current_quote
    if q is not None and q.needs_ack and q.acknowledged_at is None:
        q.acknowledged_at = datetime.utcnow()
        db.session.commit()
        return True
    return False


# ------------------------------------------------------------------ what the customer sees
def customer_view(tax, ctx, lang):
    """The price section of the customer's screen: confirmed fee, an estimate with the returning discount, or the 'OG will confirm the price' message."""
    en = lang != "es"
    q = tax.current_quote
    confirmed = next((x for x in reversed(tax.quotes) if x.status == "confirmed"), None)
    est = None if (q is not None and q.status == "confirmed") else estimate(tax, ctx)
    if confirmed is not None:
        return {"state": "confirmed", "final": fmt(confirmed.final_fee_cents), "needs_ack": bool(confirmed.needs_ack and confirmed.acknowledged_at is None), "previous": fmt(confirmed.previous_fee_cents) if confirmed.previous_fee_cents else None,
                "lines": [], "discount": None, "revised_pending": any(x.status == "revised" for x in tax.quotes)}
    est = est or estimate(tax, ctx)
    if est["mode"] == "manual":
        return {"state": "manual"}
    return {"state": "estimate", "lines": [{"label": l["label_es" if not en else "label_en"], "amount": fmt(l["amount_cents"])} for l in est["lines"]], "subtotal": fmt(est["system_estimate_cents"]),
            "discount": ({"percent": int(est["discount_percent"]) if float(est["discount_percent"]).is_integer() else est["discount_percent"], "amount": "-" + fmt(est["discount_cents"])} if est["discount_cents"] else None),
            "final": fmt(est["estimated_final_cents"])}
