"""My Account view of a tax return: OG's workflow status in the customer's words, what is needed from them, and the price. Never a government decision."""

from app.tax import docs, pricing, service
from app.tax.questions import pick

STATUS_HELP = {
    "draft": ("Your tax return is not sent yet. Continue where you left off.", "Tu declaración todavía no se ha enviado. Continúa donde te quedaste."),
    "submitted": ("We received your information. OG will review it.", "Recibimos tu información. OG la va a revisar."),
    "og_review": ("OG is reviewing your information and documents.", "OG está revisando tu información y documentos."),
    "waiting_client": ("OG needs something from you to keep going.", "OG necesita algo de ti para continuar."),
    "ready_prep": ("We have what we need. Preparation is next.", "Tenemos lo necesario. Sigue la preparación."),
    "in_prep": ("OG is preparing your tax return.", "OG está preparando tu declaración."),
    "client_review": ("Your tax return is ready for you to review and sign.", "Tu declaración está lista para que la revises y la firmes."),
    "ready_file": ("Your tax return is ready to be filed.", "Tu declaración está lista para presentarse."),
    "filed": ("OG filed your tax return. This does not mean it was accepted yet.", "OG presentó tu declaración. Esto todavía no significa que haya sido aceptada."),
    "accepted": ("Your tax return was accepted for processing.", "Tu declaración fue aceptada para procesamiento."),
    "completed": ("Your tax return is complete.", "Tu declaración está completa."),
    "rejected": ("Your return was sent back. OG will tell you what to do next.", "Tu declaración fue devuelta. OG te dirá qué sigue."),
    "amendment": ("OG needs to prepare an amended return. We will tell you the next step.", "OG necesita preparar una declaración enmendada. Te diremos el próximo paso."),
    "on_hold": ("Your tax return is on hold. Contact OG if you have questions.", "Tu declaración está en pausa. Contacta a OG si tienes preguntas."),
    "closed": ("This tax return is closed.", "Esta declaración está cerrada."),
    "reopened": ("OG opened your information so you can update it.", "OG abrió tu información para que la actualices."),
}


def dashboard(case, lang):
    tax = case.tax_data
    if tax is None:
        return None
    from app.models import TAX_STATUS_EN, TAX_STATUS_ES

    en = lang != "es"
    c = service.ctx(tax, lang)
    have, total, missing = docs.counts(tax)
    keys = [s.key for s in service.visible_steps(c)]
    idx = keys.index(tax.current_step) + 1 if tax.current_step in keys else 1
    editable = tax.status in service.EDITABLE
    price = pricing.customer_view(tax, c, lang) if (tax.status != "draft" or tax.price_status != "none") else None
    actions = []
    if editable:
        actions.append(("✏️", "Finish your tax return" if en else "Termina tu declaración"))
    if tax.status == "waiting_client" and tax.customer_message:
        actions.append(("💬", tax.customer_message))
    if tax.status == "reopened" and tax.reopen_message:
        actions.append(("💬", tax.reopen_message))
    if missing and tax.status not in ("closed", "completed"):
        actions.append(("📄", (f"{missing} document(s) still needed" if en else f"Todavía faltan {missing} documento(s)")))
    if price is not None and price.get("state") == "confirmed" and price.get("needs_ack"):
        actions.append(("💲", "Please review the updated price" if en else "Por favor revisa el precio actualizado"))
    return {"tax": tax, "year": tax.tax_year, "status": (TAX_STATUS_EN if en else TAX_STATUS_ES).get(tax.status, tax.status), "help": pick(STATUS_HELP.get(tax.status, ("", "")), lang),
            "editable": editable, "percent": int(round(100 * idx / max(1, len(keys)))) if editable else 100, "docs_have": have, "docs_total": total, "docs_missing": missing,
            "price": price, "actions": actions, "continue_url": ("public.tax_home", {"lang": lang, "case_id": tax.case_id}), "docs_url": ("public.tax_step", {"lang": lang, "case_id": tax.case_id, "step_key": "documents"}),
            "sent": tax.submitted_at is not None}
