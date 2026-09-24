"""Tax document requirements: generated from the answers, stored in the existing Document Vault (`source_key == "tax"`), localized EN/ES for the customer.

Reusable documents (birth certificate, an accepted photo ID) already on file for the same real Person are attached instead of asked for again (within the case, or from another
case of the same customer). Annual documents (W-2, 1099, 1095-A, residency proof of the year...) are always requested for the tax year.

A vault requirement holds ONE current document, so several W-2s (or 1095-As) are several requirements ("W-2 #1", "W-2 #2"...) driven by the count the customer gives.
The customer's choices ("I'll upload it later", "I can't find it", "I don't have it") are stored on the tax case; they never block the intake.
"""

from datetime import datetime

from app import case_documents as vault
from app.extensions import db
from app.models import DocumentRequirement
from app.tax import people
from app.tax.questions import Ctx, pick
from app.tax.registry import config_for
from app.tax.y2025 import BIZ_TYPES, PLATFORM_TYPES

SOURCE_KEY = "tax"
OPTIONAL_KEYS = ("tax.prior_return", "tax.id.self", "tax.childcare", "tax.charity", "tax.estimated")
OPTIONAL_PARTS = (".expenses", "tax.rental.")
REUSABLE = ("birth_certificate", "marriage_certificate", "photo_id")

STATUS_WORDS = {
    "needed": ("⏰ Pending", "⏰ Pendiente"), "requested": ("⏰ Pending", "⏰ Pendiente"), "uploaded": ("✓ Received", "✓ Recibido"), "under_review": ("🔎 OG is reviewing it", "🔎 OG lo está revisando"),
    "accepted": ("✅ Accepted", "✅ Aceptado"), "needs_replacement": ("⚠️ We need a new photo", "⚠️ Necesitamos otra foto"),
}
CHOICE_LABEL = {"later": ("⏰ I'll upload it later", "⏰ Lo subiré después"), "cant_find": ("🔍 I can't find it", "🔍 No lo encuentro"), "dont_have": ("🚫 I don't have it", "🚫 No lo tengo")}
_CHOICES_FOR = {"later": ("later",), "cant_find": ("later", "cant_find"), "dont_have": ("later", "dont_have")}


def is_optional(rule_key):
    return rule_key in OPTIONAL_KEYS or any(p in rule_key for p in OPTIONAL_PARTS)


def choice_kinds(rule_key):
    if rule_key.startswith(("tax.w2.", "tax.1095a.")) or rule_key.endswith((".platform", ".f1099")) or rule_key.startswith("tax.f1099"):
        return _CHOICES_FOR["cant_find"]
    if rule_key in ("tax.prior_return",) or rule_key.endswith(".expenses") or rule_key in OPTIONAL_KEYS:
        return _CHOICES_FOR["dont_have"]
    return _CHOICES_FOR["later"]


# ------------------------------------------------------------------ what is needed
def desired(tax, ctx):
    """[{rule_key, title, person, category, customer_message, ...}] for `sync_requirements`; English text is the stored admin record."""
    cfg = ctx.cfg
    me = people.case_person(tax, people.self_person(tax), "self")
    out = []

    def add(key, category, person=None):
        title, message = req_text_for(key, tax, ctx, "en")
        out.append({"rule_key": key, "title": title, "person": person if person is not None else me, "category": category, "customer_message": message, "doc_basis": "workflow", "reuse": False})

    if not ctx.returning and ctx.v("prior_return") in ("now", "later"):
        add("tax.prior_return", "tax_return_copy")
    if ctx.v("id_kind") in ("license", "state_id", "other"):
        add("tax.id.self", "photo_id")
    if ctx.has("income", "w2"):
        for i in range(1, max(1, int(ctx.num("w2_count", 1))) + 1):
            add(f"tax.w2.{i}", "w2")
    for code, key in (("g", "tax.f1099g"), ("r", "tax.f1099r"), ("int", "tax.f1099int"), ("b", "tax.f1099b"), ("other", "tax.f1099x")):
        if ctx.has("f1099_types", code):
            add(key, "tax_document")
    from app.tax.y2025 import mod

    if mod(ctx, "unemployment") and not ctx.has("f1099_types", "g"):
        add("tax.f1099g", "tax_document")
    if mod(ctx, "retirement") and not ctx.has("f1099_types", "r"):
        add("tax.f1099r", "tax_document")
    if mod(ctx, "ss"):
        add("tax.ssa1099", "tax_document")
    if mod(ctx, "interest") and not ctx.has("f1099_types", "int"):
        add("tax.f1099int", "tax_document")
    if mod(ctx, "invest") and not ctx.has("f1099_types", "b"):
        add("tax.f1099b", "tax_document")
    if mod(ctx, "rental"):
        for i in range(1, max(1, int(ctx.num("rental_count", 1))) + 1):
            add(f"tax.rental.{i}", "tax_document")
    for b in ctx.bizs:
        bd = b.data
        if bd.get("b_type") in PLATFORM_TYPES or "platform" in (bd.get("b_sources") or []):
            add(f"tax.biz.{b.id}.platform", "platform_summary")
        if "f1099" in (bd.get("b_sources") or []):
            add(f"tax.biz.{b.id}.f1099", "tax_document")
        if bd.get("b_exp") == "yes" and bd.get("b_exp_docs") in ("upload", "later"):
            add(f"tax.biz.{b.id}.expenses", "expense_records")
    if ctx.has("h_sources", "marketplace"):
        for i in range(1, max(1, int(ctx.num("h_1095_count", 1))) + 1):
            add(f"tax.1095a.{i}", "tax_document")
    for r in ctx.deps:
        cp = r.person
        if cp is None:
            continue
        add(f"tax.dep.{r.id}.birth", "birth_certificate", cp)
        add(f"tax.dep.{r.id}.residency", "residency_proof", cp)
    if ctx.v("e_student") == "yes":
        for who in ctx.v("e_who") or []:
            cp = _who_person(tax, who)
            if cp is not None:
                add(f"tax.1098t.{who.replace(':', '')}", "tax_document", cp)
    if ctx.v("e_loan") == "yes":
        add("tax.1098e", "tax_document")
    if ctx.v("o_mortgage") == "yes":
        add("tax.1098", "tax_document")
    if ctx.v("cc_paid") == "yes":
        add("tax.childcare", "tax_document")
    if ctx.v("ch_gave") == "yes":
        add("tax.charity", "tax_document")
    if ctx.v("ep_paid") == "yes":
        add("tax.estimated", "tax_document")
    return out


def _who_person(tax, who):
    if who == "self":
        return people.case_person(tax, people.self_person(tax), "self")
    if who == "spouse":
        sp = people.spouse_person(tax)
        return people.case_person(tax, sp, "spouse") if sp is not None else None
    if who.startswith("dep:"):
        rec = next((r for r in tax.records if r.kind == "dependent" and str(r.id) == who[4:]), None)
        return rec.person if rec is not None else None
    return None


def sync(tax, ctx=None):
    """Create / withdraw exactly the requirements the answers ask for, attach reusable documents already on file, keep everything uploaded."""
    from app.tax import service

    ctx = ctx or service.ctx(tax, "en")
    specs = desired(tax, ctx)
    vault.sync_requirements(tax.case, SOURCE_KEY, specs)
    for req in DocumentRequirement.query.filter_by(case_id=tax.case_id, source_key=SOURCE_KEY).all():
        if req.withdrawn_at is not None or req.current_document is not None or req.category not in REUSABLE or req.person is None:
            continue
        doc, accepted = vault.find_reusable_document(tax.case, req.person, req.category)
        if doc is not None and accepted:
            vault._attach(req, doc, reason_for_previous="replaced")  # noqa: SLF001
            req.status, req.reused_at = "accepted", req.reused_at or datetime.utcnow()
            continue
        other = vault.find_reusable_elsewhere(tax.case, req.person, req.category)
        if other is not None:
            vault.reuse_across_cases(req, other)
    db.session.commit()


def requirements(tax):
    return [r for r in DocumentRequirement.query.filter_by(case_id=tax.case_id, source_key=SOURCE_KEY).all() if r.withdrawn_at is None]


def missing_required(tax):
    return [r for r in requirements(tax) if not is_optional(r.rule_key) and r.status in ("needed", "requested", "needs_replacement")]


def counts(tax):
    reqs = requirements(tax)
    have = sum(1 for r in reqs if r.status in ("uploaded", "under_review", "accepted"))
    return have, len(reqs), len([r for r in reqs if not is_optional(r.rule_key) and r.status in ("needed", "requested", "needs_replacement")])


# ------------------------------------------------------------------ customer wording
def _rec(tax, rid):
    return next((r for r in tax.records if str(r.id) == str(rid)), None)


def _dep_name(tax, rid, lang):
    r = _rec(tax, rid)
    return (people.info(tax, r).get("given") if r is not None else None) or ("this person" if lang != "es" else "esta persona")


def _biz_label(tax, rid, lang):
    r = _rec(tax, rid)
    if r is None:
        return "this work" if lang != "es" else "este trabajo"
    d = r.data
    t = next((o for o in BIZ_TYPES if o.value == d.get("b_type")), None)
    return (pick(t.label, lang) if t else "") or d.get("b_desc") or ("this work" if lang != "es" else "este trabajo")


_FIXED = {
    "tax.prior_return": (("Last year's tax return", "Tus taxes del año pasado"), ("It helps OG a lot, but you can continue without it.", "A OG le ayuda mucho, pero puedes continuar sin ella.")),
    "tax.id.self": (("Photo ID", "Identificación con foto"), ("Optional. A clear photo of your driver's license or ID.", "Opcional. Una foto clara de tu licencia o identificación.")),
    "tax.f1099g": (("Form 1099-G (unemployment)", "Form 1099-G (unemployment)"), ("Upload it if you have it. You can do it later.", "Súbelo si lo tienes. Puedes hacerlo después.")),
    "tax.f1099r": (("Form 1099-R (retirement)", "Form 1099-R (retiro)"), ("Upload it if you have it. You can do it later.", "Súbelo si lo tienes. Puedes hacerlo después.")),
    "tax.ssa1099": (("Social Security statement (SSA-1099)", "Estado de Social Security (SSA-1099)"), ("Upload it if you have it. You can do it later.", "Súbelo si lo tienes. Puedes hacerlo después.")),
    "tax.f1099int": (("Interest or dividends statement (1099-INT / 1099-DIV)", "Estado de intereses o dividendos (1099-INT / 1099-DIV)"), ("Upload it if you have it.", "Súbelo si lo tienes.")),
    "tax.f1099b": (("Investment sales statement (1099-B)", "Estado de venta de inversiones (1099-B)"), ("Upload it if you have it.", "Súbelo si lo tienes.")),
    "tax.f1099x": (("Another 1099", "Otro 1099"), ("Upload it if you have it.", "Súbelo si lo tienes.")),
    "tax.1098e": (("Student loan interest (Form 1098-E)", "Intereses de préstamo estudiantil (Form 1098-E)"), ("Upload it if you have it. You can do it later.", "Súbelo si lo tienes. Puedes hacerlo después.")),
    "tax.1098": (("Mortgage interest (Form 1098)", "Intereses de hipoteca (Form 1098)"), ("Your lender sends it every year. Upload it if you have it.", "Tu prestamista te lo envía cada año. Súbelo si lo tienes.")),
    "tax.childcare": (("Childcare information", "Información del cuidado de niños"), ("Receipts or the provider's name, address and ID number. Optional.", "Recibos o el nombre, dirección y número de identificación del proveedor. Opcional.")),
    "tax.charity": (("Donation receipts", "Recibos de donaciones"), ("Optional. Receipts from the church or charity.", "Opcional. Recibos de la iglesia u organización.")),
    "tax.estimated": (("Proof of payments made ahead of time", "Comprobante de pagos hechos por adelantado"), ("Optional. A screenshot or receipt of each payment.", "Opcional. Una captura o recibo de cada pago.")),
}


def req_text_for(key, tax, ctx_or_none, lang):
    """(title, message) for a rule key in `lang`."""
    i = 0 if lang != "es" else 1
    if key in _FIXED:
        t, m = _FIXED[key]
        return t[i], m[i]
    parts = key.split(".")
    if parts[:2] == ["tax", "w2"]:
        return (f"W-2 #{parts[2]}", f"W-2 #{parts[2]}")[i], ("Upload a clear photo of your W-2, or do it later.", "Sube una foto clara de tu W-2, o hazlo después.")[i]
    if parts[:2] == ["tax", "1095a"]:
        return (f"Form 1095-A #{parts[2]}", f"Form 1095-A #{parts[2]}")[i], ("📄 If you received a Form 1095-A from the Marketplace / HealthCare.gov, upload it here.", "📄 Si recibiste un Form 1095-A del Marketplace / HealthCare.gov, súbelo aquí.")[i]
    if parts[:2] == ["tax", "rental"]:
        return (f"Rental property records #{parts[2]}", f"Registros de la propiedad alquilada #{parts[2]}")[i], ("Rent received and expenses, or a yearly summary.", "Renta recibida y gastos, o un resumen del año.")[i]
    if parts[:3] == ["tax", "dep"] or (parts[:2] == ["tax", "dep"] and len(parts) >= 4):
        name = _dep_name(tax, parts[2], lang)
        if parts[3] == "birth":
            return (f"👶 Birth certificate — {name}", f"👶 Acta de nacimiento — {name}")[i], ("A clear photo is enough.", "Una foto clara basta.")[i]
        return ((f"🏠 Proof of where {name} lived in 2025", f"🏠 Prueba de dónde vivió {name} durante 2025")[i],
                (f"We need proof of where {name} lived during 2025. The easiest is usually a document from the school or the doctor that shows {name}'s name and address.",
                 f"Necesitamos una prueba de dónde vivió {name} durante 2025. Lo más fácil normalmente es un documento de la escuela o del médico que muestre el nombre y la dirección de {name}.")[i])
    if parts[:3] == ["tax", "biz"] or (parts[:2] == ["tax", "biz"] and len(parts) >= 4):
        what = _biz_label(tax, parts[2], lang)
        if parts[3] == "platform":
            return (f"{what} — annual summary", f"{what} — resumen anual")[i], ("The annual summary can have important information about your income, miles and platform charges.", "El resumen anual puede tener información importante sobre tus ingresos, millas y cargos de la plataforma.")[i]
        if parts[3] == "f1099":
            return (f"{what} — Form 1099", f"{what} — Form 1099")[i], ("Upload it if you received one.", "Súbelo si recibiste uno.")[i]
        return (f"{what} — records of your expenses", f"{what} — registros de tus gastos")[i], ("Statements, reports, receipts or spreadsheets all work. You do not need every receipt.", "Sirven estados de cuenta, reportes, recibos u hojas de cálculo. No necesitas todos los recibos.")[i]
    if parts[:2] == ["tax", "1098t"]:
        who = parts[2]
        name = ("me" if who == "self" else "my spouse") if lang != "es" else ("yo" if who == "self" else "mi esposo(a)")
        if who.startswith("dep"):
            name = _dep_name(tax, who[3:], lang)
        return (f"Form 1098-T — {name}", f"Form 1098-T — {name}")[i], ("The school sends it in January. Upload it if you have it, or do it later.", "La escuela lo envía en enero. Súbelo si lo tienes o hazlo después.")[i]
    return key, ""


def req_text(req, lang="en"):
    """Customer-facing (title, message) of a tax requirement; used through `case_documents.customer_text`."""
    tax = req.case.tax_data
    if tax is None:
        return req.title, req.customer_message
    return req_text_for(req.rule_key or "", tax, None, lang)


# ------------------------------------------------------------------ cards (customer)
def _matches(key, prefixes):
    return any(key == p or (p.endswith(".") and key.startswith(p)) for p in prefixes)


def resolve_prefixes(prefixes, record=None):
    out = []
    for p in prefixes:
        if record is not None and p in ("tax.dep.", "tax.biz."):
            out.append(f"{p}{record.id}.")
        else:
            out.append(p)
    return out


def cards(tax, prefixes, lang, record=None):
    rows = []
    choices = tax.doc_choices
    for r in sorted(requirements(tax), key=lambda x: x.id):
        if not _matches(r.rule_key or "", resolve_prefixes(prefixes, record)):
            continue
        title, message = req_text(r, lang)
        i = 0 if lang != "es" else 1
        review_msg = None
        if r.status == "needs_replacement":
            review_msg = r.review_message or ((f"We need another photo of {title}. The image we received cannot be read completely.", f"Necesitamos otra foto de {title}. La imagen que recibimos no se puede leer completamente.")[i])
        doc = r.current_document
        rows.append({"req": r, "title": title, "message": message, "status": r.status, "status_text": STATUS_WORDS[r.status][i], "doc": doc, "optional": is_optional(r.rule_key),
                     "can_upload": r.status in vault.CUSTOMER_CAN_UPLOAD, "can_remove": vault.customer_can_remove(r, doc), "review_message": review_msg,
                     "choice": choices.get(r.rule_key), "choice_text": (CHOICE_LABEL[choices[r.rule_key]][i] if choices.get(r.rule_key) in CHOICE_LABEL else None),
                     "choices": [(k, CHOICE_LABEL[k][i]) for k in choice_kinds(r.rule_key)], "reused": r.reused_at is not None})
    return rows
