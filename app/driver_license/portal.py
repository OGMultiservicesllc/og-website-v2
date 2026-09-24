"""My Account view of a Driver License case: OG's workflow status in the customer's own words, the milestone roadmap, what's needed
from them, and the price. Never implies an MVC decision or guarantees an appointment.

`continue_url`/`docs_url`/`next_step_url` are unresolved `(endpoint, kwargs)` tuples, not built strings — the SAME convention
`tax_portal.dashboard()` uses (see `_tax_entry`/`_tax_dash.html`: `url_for(d.continue_url[0], **d.continue_url[1])`). Returning an
already-built string here once broke `account_dashboard._dl_entry`, which (like `_tax_entry`/`_itin_entry`) expects the tuple shape."""

from app import customer_status
from app.driver_license import docs, pricing, service


def roadmap(dl, lang):
    """[{key, label, state}] state: done | current | upcoming | to_be_determined."""
    from app.models import DL_MILESTONE_EN, DL_MILESTONE_ES, DL_MILESTONE_ORDER

    labels = DL_MILESTONE_EN if lang != "es" else DL_MILESTONE_ES
    idx = DL_MILESTONE_ORDER.index(dl.milestone) if dl.milestone in DL_MILESTONE_ORDER else 0
    out = []
    for i, key in enumerate(DL_MILESTONE_ORDER):
        if key == "road_test" and dl.road_test_state == "not_required":
            state = "not_required"
        elif i < idx:
            state = "done"
        elif i == idx:
            state = "current"
        elif key == "road_test" and dl.road_test_state == "to_be_determined":
            state = "to_be_determined"
        else:
            state = "upcoming"
        out.append({"key": key, "label": labels[key], "state": state})
    return out


def next_step(dl, lang):
    en = lang != "es"
    if dl.milestone == "documents":
        return ("Finish your document information" if en else "Termina tu información de documentos"), ("public.dl_home", {})
    if dl.milestone == "initial_permit":
        if dl.initial_permit_state == "obtained":
            return ("Ready for the Knowledge Test" if en else "Listo(a) para el examen teórico"), None
        return ("Prepare for your Initial Permit" if en else "Prepárate para tu Initial Permit"), None
    if dl.milestone == "knowledge_test":
        if dl.knowledge_test_state == "passed":
            return ("Ready for the Road Test" if en else "Listo(a) para el examen práctico"), None
        return ("Practice for your Knowledge Test" if en else "Practica para tu examen teórico"), ("public.dl_practice_home", {})
    if dl.milestone == "road_test":
        return ("OG will help determine your Road Test step" if en else "OG te ayudará a determinar tu paso del examen práctico"), None
    if dl.milestone == "license_obtained":
        return ("Almost there!" if en else "¡Ya casi!"), None
    return ("Completed" if en else "Completado"), None


def _open_revision(dl):
    return next((r for r in reversed(dl.case.revisions) if r.resubmitted_at is None), None)


def dashboard(case, lang):
    dl = case.dl_data
    if dl is None:
        return None
    en = lang != "es"
    c = service.ctx(dl, lang)
    have, total, missing = docs.counts(dl)
    status_label, status_tone = customer_status.dl_status(dl.status, lang)
    milestone_label, milestone_tone = customer_status.dl_milestone_help(dl.milestone, lang)
    editable = dl.status in service.EDITABLE
    price = pricing.customer_view(dl, c, lang) if (dl.status != "draft" or dl.price_status != "none") else None
    step_text, step_route = next_step(dl, lang)
    if step_route:
        step_route = (step_route[0], {**step_route[1], "lang": lang})
    open_rev = _open_revision(dl) if dl.status == "reopened" else None
    self_editing = bool(open_rev and open_rev.reopened_by == "customer")
    actions = []
    if dl.status == "draft":
        actions.append(("✏️", "Finish your Driver License information" if en else "Termina tu información de Licencia de Conducir"))
    elif self_editing:
        actions.append(("✏️", "You're correcting your information — continue when ready" if en else "Estás corrigiendo tu información — continúa cuando quieras"))
    elif dl.status == "reopened" and dl.reopen_message:
        actions.append(("💬", ("OG asked you to update this information: " if en else "OG te pidió que actualices esta información: ") + f"“{dl.reopen_message}”"))
    elif dl.status == "reopened":
        actions.append(("✏️", "OG asked you to review and update your information" if en else "OG te pidió que revises y actualices tu información"))
    if dl.status == "waiting_client" and dl.customer_message:
        actions.append(("💬", dl.customer_message))
    if missing and dl.status not in ("closed", "completed"):
        actions.append(("📄", (f"{missing} document(s) still needed" if en else f"Todavía faltan {missing} documento(s)")))
    if price is not None and price.get("state") == "confirmed" and price.get("needs_ack"):
        actions.append(("💲", "Please review the updated price" if en else "Por favor revisa el precio actualizado"))
    return {"dl": dl, "status": status_label, "status_tone": status_tone, "milestone": dl.milestone, "milestone_label": milestone_label, "milestone_tone": milestone_tone,
            "editable": editable, "self_editing": self_editing, "can_self_edit": service.can_self_edit(dl), "docs_have": have, "docs_total": total, "docs_missing": missing, "price": price, "actions": actions,
            "roadmap": roadmap(dl, lang), "next_step_text": step_text, "next_step_route": step_route,
            "continue_url": ("public.dl_home", {"lang": lang}), "docs_url": ("public.dl_step", {"lang": lang, "step_key": "documents_vault"}),
            "edit_url": ("public.dl_edit_confirm", {"lang": lang}), "discard_url": ("public.dl_discard_confirm", {"lang": lang})}
