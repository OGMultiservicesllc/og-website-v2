"""Human-friendly summaries of a tax case: the customer's Final Review cards (sensitive values masked) and the structured Admin preparation summary.
Generated from structured data only. No AI."""

from app import secure_store
from app.tax import docs, flags as tax_flags, people, service
from app.tax.questions import pick
from app.tax.registry import config_for
from app.tax.y2025 import BIZ_TYPES, PLATFORM_TYPES


def _t(en, es, lang):
    return es if lang == "es" else en


def label(cfg, key, value, lang):
    """Readable text of a stored value (option label, list of labels, plain text)."""
    q = cfg.index().get(key)
    if value in (None, "", []):
        return ""
    if q is None:
        return str(value)
    if isinstance(value, list):
        return ", ".join(filter(None, (label(cfg, key, v, lang) for v in value)))
    opts = q.options if not callable(q.options) else []
    o = next((x for x in opts if x.value == value), None)
    return (f"{o.emoji} " if o and o.emoji else "") + pick(o.label, lang) if o else str(value)


def _money(v):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"${n:,.0f}" if n == int(n) else f"${n:,.2f}"


def _line(lab, val):
    return {"label": lab, "value": val} if val not in (None, "", []) else None


def review_cards(tax, lang):
    cfg = config_for(tax.tax_year)
    c = service.ctx(tax, lang)
    en = lang != "es"
    owner = people.self_person(tax)
    g = lambda bind: people.get_fact(owner, bind)  # noqa: E731
    cards = []
    name = " ".join(x for x in (g("given_name"), g("family_name")) if x)
    addr = ", ".join(x for x in (g("address.street"), g("address.city"), " ".join(x for x in (g("address.state"), g("address.zip")) if x)) if x)
    ssn = g("ssn")
    lines = [_line(_t("Name", "Nombre", lang), name), _line(_t("Date of birth", "Fecha de nacimiento", lang), g("date_of_birth")),
             _line(_t("SSN / ITIN", "SSN / ITIN", lang), people.mask_ssn(ssn) if ssn else None), _line(_t("Phone", "Teléfono", lang), g("phone_daytime")),
             _line("Email", g("email")), _line(_t("Address", "Dirección", lang), addr), _line(_t("Occupation", "Ocupación", lang), c.v("occupation"))]
    cards.append({"key": "about", "icon": "👤", "title": _t("About you", "Sobre ti", lang), "lines": [x for x in lines if x], "edit": "about"})
    fam = []
    marital = label(cfg, "marital", c.v("marital"), lang)
    fam.append(_line(_t("Situation on December 31, 2025", "Situación al 31 de diciembre de 2025", lang), marital))
    parts = []
    if c.v("marital") == "married":
        parts.append(_t("Spouse", "Esposo(a)", lang))
    if c.deps:
        n = len(c.deps)
        parts.append(_t(f"{n} potential dependent{'s' if n != 1 else ''}", f"{n} posible{'s' if n != 1 else ''} dependiente{'s' if n != 1 else ''}", lang))
    fam.append(_line(_t("Family", "Familia", lang), " + ".join(parts) or _t("Just you", "Solo tú", lang)))
    cards.append({"key": "family", "icon": "👨‍👩‍👧‍👦", "title": _t("Family", "Familia", lang), "lines": [x for x in fam if x], "edit": "status"})
    inc = []
    if c.has("income", "w2"):
        n = int(c.num("w2_count", 0))
        inc.append(f"{n} W-2" if n else "W-2")
    for b in c.bizs:
        t = next((o for o in BIZ_TYPES if o.value == b.data.get("b_type")), None)
        inc.append(pick(t.label, lang) if t else (b.data.get("b_desc") or _t("Own work", "Trabajo por cuenta propia", lang)))
    if c.bizs:
        inc.append(_t("Self-employment", "Trabajo por cuenta propia", lang))
    for v in ("unemployment", "retirement", "ss", "interest", "invest", "rental", "other"):
        if c.has("income", v) or c.has("situations", v):
            inc.append(label(cfg, "income", v, lang).lstrip("👔🚗💵📱📄💰👴🏦📈🏠➕ "))
    cards.append({"key": "income", "icon": "💰", "title": _t("Income", "Ingresos", lang), "lines": [{"label": None, "value": x} for x in dict.fromkeys(inc)] or [{"label": None, "value": _t("Nothing added yet", "Nada agregado todavía", lang)}], "edit": "income"})
    hl = [_line(_t("Coverage in 2025", "Cobertura en 2025", lang), label(cfg, "h_cover", c.v("h_cover"), lang)), _line(_t("Source", "Fuente", lang), label(cfg, "h_sources", c.v("h_sources"), lang))]
    cards.append({"key": "health", "icon": "🏥", "title": _t("Health insurance", "Seguro médico", lang), "lines": [x for x in hl if x], "edit": "health"})
    have, total, missing = docs.counts(tax)
    dl = [{"label": None, "value": _t(f"{have} received", f"{have} recibidos", lang) + (" · " + _t(f"{missing} pending", f"{missing} pendientes", lang) if missing else "")}]
    cards.append({"key": "documents", "icon": "📄", "title": _t("Documents", "Documentos", lang), "lines": dl, "edit": "documents"})
    other = []
    for key, txt in (("e_student", ("Education", "Educación")), ("cc_paid", ("Childcare", "Cuidado de niños")), ("o_own", ("Homeowner", "Dueño de casa")), ("ch_gave", ("Donations", "Donaciones")), ("ep_paid", ("Estimated payments", "Pagos por adelantado"))):
        if c.v(key) == "yes":
            other.append({"label": None, "value": txt[1 if not en else 0]})
    for o in cfg.index()["situations"].options:
        if c.has("situations", o.value) and o.value not in ("none",) and not c.has("income", o.value):
            other.append({"label": None, "value": pick(o.label, lang)})
    cards.append({"key": "other", "icon": "🧾", "title": _t("Other situations", "Otras situaciones", lang), "lines": other or [{"label": None, "value": _t("Nothing else", "Nada más", lang)}], "edit": "situations"})
    pref = []
    pref.append(_line(_t("If you owe", "Si le debes al IRS", lang), label(cfg, "pay_pref", c.v("pay_pref"), lang)))
    if c.v("dd_want") == "yes":
        pref.append(_line(_t("Refund", "Reembolso", lang), _t("Direct deposit", "Depósito directo", lang) + (f" ••••{tax.bank.account_last4}" if tax.bank is not None and tax.bank.account_last4 else "")))
    elif c.v("dd_want"):
        pref.append(_line(_t("Refund", "Reembolso", lang), label(cfg, "dd_want", c.v("dd_want"), lang)))
    cards.append({"key": "prefs", "icon": "💳", "title": _t("Payments", "Pagos", lang), "lines": [x for x in pref if x], "edit": "payment_pref"})
    return cards


# ------------------------------------------------------------------ admin
def admin_summary(tax):
    """Structured preparation summary for OG staff (English). Bank details and SSNs stay masked here; the bank reveal is an audited action."""
    cfg = config_for(tax.tax_year)
    lang = "en"
    c = service.ctx(tax, lang)
    owner = people.self_person(tax)
    g = lambda bind: people.get_fact(owner, bind)  # noqa: E731
    sections = []

    def sec(title, rows):
        rows = [r for r in rows if r and r[1] not in (None, "", [])]
        sections.append({"title": title, "rows": rows})

    ssn = g("ssn")
    sec("Taxpayer", [("Name", " ".join(x for x in (g("given_name"), g("family_name")) if x)), ("Date of birth", g("date_of_birth")), ("SSN / ITIN", people.mask_ssn(ssn) if ssn else "— not provided"),
                     ("Email", g("email")), ("Phone", g("phone_daytime")), ("Address", ", ".join(x for x in (g("address.street"), g("address.unit_number"), g("address.city"), g("address.state"), g("address.zip")) if x)),
                     ("Occupation", c.v("occupation")), ("Photo ID", label(cfg, "id_kind", c.v("id_kind"), lang)), ("Moved during the year", label(cfg, "moved", c.v("moved"), lang)),
                     ("Moved from", c.v("moved_from")), ("Changes since last year", label(cfg, "changes", c.v("changes"), lang))])
    fam = [("Situation on Dec 31", label(cfg, "marital", c.v("marital"), lang))]
    sp = people.spouse_person(tax)
    if sp is not None:
        sp_ssn = people.get_fact(sp, "ssn")
        fam.append(("Spouse", f"{sp.full_name} · DOB {people.get_fact(sp, 'date_of_birth') or '—'} · SSN/ITIN {people.mask_ssn(sp_ssn) if sp_ssn else '— not provided'}"))
    sec("Filing situation / family facts", fam)
    dep_rows = []
    for r in c.deps:
        d = r.data
        i = people.info(tax, r)
        d_ssn = people.get_fact(people.owner_for(tax, "record", r), "ssn")
        dep_rows.append((f"{i.get('given') or '?'} {i.get('family') or ''}".strip(), f"DOB {i['dob'] or '—'} · {label(cfg, 'd_rel', d.get('d_rel'), lang)} · months with taxpayer: {d.get('d_months', '—')} · "
                         f"student: {d.get('d_student', '—')} · disability: {d.get('d_disabled', '—')} · others may claim: {d.get('d_other_claim', '—')} · SSN/ITIN: {people.mask_ssn(d_ssn) if d_ssn else d.get('d_ssn_status', '—')}"))
    sec("Dependents", dep_rows)
    sec("Income sources", [("Routing", label(cfg, "income", c.v("income"), lang)), ("1099 types", label(cfg, "f1099_types", c.v("f1099_types"), lang)), ("W-2 count", c.v("w2_count")),
                           ("Rental properties", c.v("rental_count")), ("Investment sales", label(cfg, "invest_size", c.v("invest_size"), lang)), ("Other income", c.v("other_income_text")),
                           ("Income in another state", label(cfg, "state_other", c.v("state_other"), lang))])
    biz_rows = []
    for b in c.bizs:
        d = b.data
        t = next((o for o in BIZ_TYPES if o.value == d.get("b_type")), None)
        biz_rows.append((f"{pick(t.label, lang) if t else 'Business'} — {d.get('b_desc') or ''}", f"name: {d.get('b_name') or '—'} · started: {d.get('b_start') or '—'} · TOTAL RECEIPTS reported: {_money(d.get('b_receipts')) if d.get('b_receipts') else '—'} · "
                         f"sources: {label(cfg, 'b_sources', d.get('b_sources'), lang) or '—'} · NOT in any document: {_money(d.get('b_undoc')) if d.get('b_undoc') else '—'} · "
                         f"documents supporting: {', '.join(r.rule_key.split('.')[-1] for r in docs.requirements(tax) if r.rule_key.startswith(f'tax.biz.{b.id}.') and r.current_document is not None) or 'none yet'}"))
    sec("Self-employment activities", biz_rows)
    veh = []
    for b in c.bizs:
        d = b.data
        if d.get("b_vehicle") in ("yes", "unsure"):
            costs = ", ".join(f"{o.label[0]} {_money(d.get('b_v_' + o.value))}" for o in cfg.index()["b_vcosts"].options if d.get("b_v_" + o.value))
            veh.append((d.get("b_desc") or f"#{b.id}", f"vehicle: {d.get('b_vehicle')} · business miles: {d.get('b_miles', '—')} · costs: {costs or '—'}"))
    sec("Vehicle", veh)
    exp = []
    for b in c.bizs:
        d = b.data
        if d.get("b_exp") in ("yes", "unsure"):
            cats = ", ".join(f"{o.label[0]} {_money(d.get('b_x_' + o.value)) if d.get('b_x_' + o.value) else '(amount not given)'}" for o in cfg.index()["b_exp_cats"].options if o.value in (d.get("b_exp_cats") or []))
            exp.append((d.get("b_desc") or f"#{b.id}", f"expenses: {d.get('b_exp')} · {cats or '—'} · records: {d.get('b_exp_docs', '—')}"))
    sec("Business expenses", exp)
    sec("Health insurance", [("Coverage in 2025", label(cfg, "h_cover", c.v("h_cover"), lang)), ("Sources", label(cfg, "h_sources", c.v("h_sources"), lang)), ("Who", label_who(c, c.v("h_who"))), ("1095-A count", c.v("h_1095_count"))])
    sec("Education / childcare", [("Studied", label(cfg, "e_student", c.v("e_student"), lang)), ("Who studied", label_who(c, c.v("e_who"))), ("Student loan interest", label(cfg, "e_loan", c.v("e_loan"), lang)),
                                  ("Childcare paid", label(cfg, "cc_paid", c.v("cc_paid"), lang)), ("Childcare for", label_who(c, c.v("cc_who"))), ("Provider", c.v("cc_provider")), ("Childcare amount", _money(c.v("cc_amount")) if c.v("cc_amount") else None)])
    sec("Home / donations / estimated payments", [("Owned a home", label(cfg, "o_own", c.v("o_own"), lang)), ("Mortgage interest", label(cfg, "o_mortgage", c.v("o_mortgage"), lang)), ("Donations", label(cfg, "ch_gave", c.v("ch_gave"), lang)),
                                                 ("Donation types", label(cfg, "ch_types", c.v("ch_types"), lang)), ("Donation amount", _money(c.v("ch_amount")) if c.v("ch_amount") else None),
                                                 ("Estimated payments made", label(cfg, "ep_paid", c.v("ep_paid"), lang)), ("Federal", _money(c.v("ep_fed")) if c.v("ep_fed") else None), ("State", _money(c.v("ep_state")) if c.v("ep_state") else None)])
    sec("Other tax situations", [("Selected", label(cfg, "situations", c.v("situations"), lang)), ("Crypto", label(cfg, "cr_size", c.v("cr_size"), lang)), ("Foreign", c.v("fo_text")), ("Gambling", _money(c.v("gm_amount")) if c.v("gm_amount") else None),
                                 ("Medical (out of pocket)", _money(c.v("med_amount")) if c.v("med_amount") else None), ("Retirement contributions", _money(c.v("rc_amount")) if c.v("rc_amount") else None), ("Other", c.v("ot_text")),
                                 ("Customer's note to OG", c.v("notes_text"))])
    bank = tax.bank
    sec("Bank / refund preference", [("Direct deposit", label(cfg, "dd_want", c.v("dd_want"), lang)), ("Account type", bank.account_type if bank else None),
                                     ("Routing", f"•••••{bank.routing_last4}" if bank and bank.routing_last4 else None), ("Account", f"••••{bank.account_last4}" if bank and bank.account_last4 else None)])
    sec("IRS payment preference", [("If the customer owes", label(cfg, "pay_pref", c.v("pay_pref"), lang))])
    fl = tax_flags.flags(c)
    return {"sections": sections, "flags": fl, "missing": service.missing_info(tax, lang)}


def label_who(c, values):
    if not values:
        return ""
    names = {o.value: o.label[0] for o in __import__("app.tax.y2025", fromlist=["household_options"]).household_options(c)}
    return ", ".join(names.get(v, v) for v in values)
