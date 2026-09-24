"""My Account view of a Consent to Travel case: status in plain language, the document count, and the price —
never implies an appointment is confirmed. `continue_url` is an unresolved (endpoint, kwargs) tuple, the same
convention `tax_portal.dashboard()`/`dl_portal.dashboard()` use."""

from app import customer_status
from app.consent_travel import docs, pricing, service


def dashboard(case, lang):
    ct = case.consent_travel_data
    if ct is None:
        return None
    en = lang != "es"
    have, total, missing = docs.counts(ct)
    status_label, status_tone = customer_status.case_status(case.status, lang)
    editable = ct.status in service.EDITABLE
    groups = service.groups_for(ct)
    price = pricing.customer_view(ct, groups, lang) if (ct.status != "draft" or ct.price_status != "none") else None
    actions = []
    if ct.status == "draft":
        actions.append(("✏️", "Finish your Consent to Travel information" if en else "Termina tu información de Autorización de Viaje"))
    elif ct.status == "reopened" and ct.reopen_message:
        actions.append(("💬", ("OG asked you to update this information: " if en else "OG te pidió que actualices esta información: ") + f"“{ct.reopen_message}”"))
    if ct.status == "waiting_client" and ct.customer_message:
        actions.append(("💬", ct.customer_message))
    if missing and ct.status not in ("closed", "completed"):
        actions.append(("📄", (f"{missing} document(s) still needed" if en else f"Todavía faltan {missing} documento(s)")))
    if price is not None and price.get("state") == "confirmed" and price.get("needs_ack"):
        actions.append(("💲", "Please review the updated price" if en else "Por favor revisa el precio actualizado"))
    return {"ct": ct, "status": status_label, "editable": editable, "children": len(ct.children), "docs_have": have, "docs_total": total, "docs_missing": missing,
            "price": price, "actions": actions, "continue_url": ("public.ct_home", {"lang": lang, "case_id": case.id})}
