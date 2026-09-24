"""OG review flags for a tax case: things OG should look at, derived from the answers. Never a tax conclusion and never shown to the customer as an accusation:
"Not sure" answers, missing identifiers, possible state-residency questions, situations that need a tax professional."""

from app.tax.questions import pick
from app.tax.y2025 import YEAR_END

PRO_REVIEW = ("OG TAX PROFESSIONAL REVIEW REQUIRED", "REVISIÓN DE UN PROFESIONAL DE TAXES DE OG REQUERIDA")


def flags(ctx):
    """[{code, en, es, level}] level: review | pro (tax professional review required)."""
    out = []

    def add(code, en, es, level="review"):
        out.append({"code": code, "en": en, "es": es, "level": level})

    v = ctx.v
    if v("moved") == "other":
        add("state_move", "Moved to a different state during 2025: possible part-year / multi-state residency review", "Se mudó a otro estado durante 2025: posible revisión de residencia parcial / varios estados", "pro")
    elif v("moved") == "unsure":
        add("state_move_unsure", "Not sure whether they moved during 2025: confirm state residency", "No está seguro(a) si se mudó durante 2025: confirmar residencia estatal")
    if v("marital") in ("separated", "widowed") or (v("marital") in ("single", "divorced", "widowed", "separated") and ctx.deps):
        add("filing_status", "Filing status needs the preparer's review (household situation on Dec 31, 2025)", "El estado civil para presentar necesita la revisión del preparador (situación del hogar al 31 de dic. de 2025)")
    if not v("a_ssn") and ctx.tax is not None:
        add("ssn_missing", "Taxpayer SSN / ITIN not provided", "No se dio el SSN / ITIN del contribuyente")
    for r in ctx.deps:
        d = r.data
        who = (ctx.info(r) or {}).get("given") or f"#{r.id}"
        if d.get("d_ssn_status") in ("none", "pending"):
            add(f"dep_ssn_{r.id}", f"{who}: no SSN / ITIN yet ({d.get('d_ssn_status')})", f"{who}: todavía sin SSN / ITIN ({d.get('d_ssn_status')})")
        if d.get("d_other_claim") in ("yes", "unsure"):
            add(f"dep_claim_{r.id}", f"{who}: someone else may claim this person", f"{who}: otra persona podría incluir a esta persona")
        if d.get("d_months") not in (None, "") and str(d.get("d_months")).isdigit() and int(d["d_months"]) < 7:
            add(f"dep_months_{r.id}", f"{who}: lived with the taxpayer {d['d_months']} months", f"{who}: vivió con el contribuyente {d['d_months']} meses")
    if v("has_deps") == "unsure" and not ctx.deps:
        add("deps_unsure", "Customer is not sure about dependents", "El cliente no está seguro sobre dependientes")
    if v("s_ssn") is None and v("marital") == "married":
        add("spouse_ssn", "Spouse SSN / ITIN not provided", "No se dio el SSN / ITIN del cónyuge")
    if ctx.has("income", "other"):
        add("other_income", "Other income described by the customer", "Otro ingreso descrito por el cliente")
    for b in ctx.bizs:
        d = b.data
        name = d.get("b_desc") or f"#{b.id}"
        if d.get("b_vehicle") == "yes" and str(d.get("b_miles") or "0") in ("0", ""):
            add(f"biz_miles_{b.id}", f"{name}: vehicle used but mileage is 0 / unknown", f"{name}: usó vehículo pero las millas son 0 / se desconocen")
        if d.get("b_exp") == "unsure":
            add(f"biz_exp_{b.id}", f"{name}: not sure about expenses", f"{name}: no está seguro(a) de sus gastos")
        if d.get("b_vehicle") == "unsure":
            add(f"biz_veh_{b.id}", f"{name}: not sure about vehicle use", f"{name}: no está seguro(a) si usó vehículo")
        if d.get("b_exp_docs") == "none" and d.get("b_exp") == "yes":
            add(f"biz_docs_{b.id}", f"{name}: expenses reported without documents", f"{name}: gastos reportados sin documentos")
    if v("h_cover") == "unsure":
        add("health_unsure", "Not sure about health insurance in 2025", "No está seguro(a) de su seguro médico en 2025")
    if v("cc_paid") == "unsure":
        add("childcare_unsure", "Not sure about childcare expenses", "No está seguro(a) de gastos de cuidado de niños")
    if v("e_student") == "unsure":
        add("edu_unsure", "Not sure about education", "No está seguro(a) sobre educación")
    if v("ep_paid") == "unsure":
        add("est_unsure", "Not sure about estimated tax payments", "No está seguro(a) de los pagos estimados")
    if v("state_other") == "unsure":
        add("state_other_unsure", "Not sure about income in another state", "No está seguro(a) de ingresos en otro estado")
    if ctx.has("situations", "foreign"):
        add("foreign", f"Foreign income or accounts — {PRO_REVIEW[0]}", f"Ingresos o cuentas en el extranjero — {PRO_REVIEW[1]}", "pro")
    if ctx.has("situations", "crypto") and v("cr_size") in ("complex", "unsure"):
        add("crypto", f"Crypto activity ({v('cr_size')}) — {PRO_REVIEW[0]}", f"Actividad de crypto ({v('cr_size')}) — {PRO_REVIEW[1]}", "pro")
    if v("invest_size") in ("many", "unsure"):
        add("invest", "Many / unclear investment sales", "Muchas / poco claras ventas de inversiones", "pro")
    if ctx.has("situations", "gambling"):
        add("gambling", "Gambling winnings reported", "Ganancias de juegos de azar reportadas")
    if ctx.has("situations", "other") or v("notes_text"):
        add("customer_note", "The customer left a note or another situation for OG", "El cliente dejó una nota u otra situación para OG")
    if v("pay_pref") == "agreement":
        add("payment_agreement", "Wants information about an IRS payment agreement (separate service; no eligibility is promised)", "Quiere información sobre un acuerdo de pago con el IRS (servicio separado; no se promete elegibilidad)")
    return out


def text(flag, lang):
    return flag["es"] if lang == "es" else flag["en"]
