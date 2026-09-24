"""My Account redesign: ONE place that turns an internal status/state into the plain words a customer sees.

Internal/admin statuses stay exactly as they are everywhere else in the platform
(`SUBMISSION_STATUS_LABELS`, `CASE_STATUS_LABELS`, `TAX_STATUS_EN/ES`, `itin.STAGE_EN/ES`,
`case_documents.STATUS_ES`/`REQUIREMENT_STATUS_LABELS`) — nothing here renames a stored value or
changes admin-facing text. This module only maps {kind, internal_key} -> a short customer-facing
phrase + a "tone" (what color/urgency it reads as), reused by Home, Services, Documents and Messages
so the wording lives in one place instead of being retyped in every template.

`tone` is one of: action (something for the customer to do — amber), problem (needs their attention
urgently — red), processing (OG is working on it — blue/accent), done (green), neutral (gray).
"""


def _t(row, lang):
    return row[1] if lang == "es" else row[0]


TONE_CLASSES = {
    "action": "bg-amber-50 text-amber-800 border-amber-200",
    "problem": "bg-red-50 text-red-700 border-red-200",
    "processing": "bg-accent-50 text-accent-700 border-accent-100",
    "done": "bg-emerald-50 text-emerald-700 border-emerald-100",
    "neutral": "bg-fog-100 text-slate-600 border-slate-200",
}
TONE_DOT = {"action": "bg-amber-500", "problem": "bg-red-500", "processing": "bg-accent-500", "done": "bg-emerald-500", "neutral": "bg-slate-300"}


def tone_classes(tone):
    return TONE_CLASSES.get(tone, TONE_CLASSES["neutral"])


def tone_dot(tone):
    return TONE_DOT.get(tone, TONE_DOT["neutral"])


# ------------------------------------------------------------------ Applications (FormSubmission / Smart Intake)
_APP = {
    "draft": (("Continue where you left off", "Continúa donde te quedaste"), "action"),
    "reopened": (("We need updated information from you", "Necesitamos información actualizada de ti"), "action"),
    "new": (("We received your information", "Recibimos tu información"), "processing"),
    "in_review": (("OG is reviewing your information", "OG está revisando tu información"), "processing"),
    "waiting_client": (("We need information from you", "Necesitamos información de ti"), "action"),
    "ready_for_ceac": (("Ready for the next step", "Listo para el siguiente paso"), "processing"),
    "completed": (("Completed", "Completado"), "done"),
    "archived": (("Archived", "Archivado"), "neutral"),
}


def application_status(status_key, lang):
    """(label, tone) for a FormSubmission's status_key (see app/intake_engine.py)."""
    text, tone = _APP.get(status_key, ((status_key, status_key), "neutral"))
    return _t(text, lang), tone


# ------------------------------------------------------------------ Cases (app/models/cases.py Case.status)
_CASE = {
    "open": (("In progress", "En progreso"), "processing"),
    "in_review": (("OG is reviewing your information", "OG está revisando tu información"), "processing"),
    "waiting_client": (("We need information from you", "Necesitamos información de ti"), "action"),
    "completed": (("Completed", "Completado"), "done"),
    "closed": (("Closed", "Cerrado"), "neutral"),
}


def case_status(status_key, lang):
    text, tone = _CASE.get(status_key, ((status_key, status_key), "neutral"))
    return _t(text, lang), tone


# ------------------------------------------------------------------ Tax Return (app/models/tax.py TAX_STATUSES)
_TAX = {
    "draft": (("Continue where you left off", "Continúa donde te quedaste"), "action"),
    "submitted": (("We received your information", "Recibimos tu información"), "processing"),
    "og_review": (("OG is reviewing your information", "OG está revisando tu información"), "processing"),
    "waiting_client": (("We need information from you", "Necesitamos información de ti"), "action"),
    "ready_prep": (("Ready to start preparation", "Lista para comenzar la preparación"), "processing"),
    "in_prep": (("OG is preparing your return", "OG está preparando tu declaración"), "processing"),
    "client_review": (("Ready for your review", "Lista para tu revisión"), "action"),
    "ready_file": (("Ready to file", "Lista para presentar"), "processing"),
    "filed": (("Filed", "Presentada"), "processing"),
    "accepted": (("Accepted", "Aceptada"), "done"),
    "completed": (("Completed", "Completada"), "done"),
    "rejected": (("Sent back — OG will tell you what's next", "Devuelta — OG te dirá qué sigue"), "problem"),
    "amendment": (("An update is needed", "Se necesita una actualización"), "problem"),
    "on_hold": (("On hold", "En pausa"), "neutral"),
    "closed": (("Closed", "Cerrado"), "neutral"),
    "reopened": (("We need updated information from you", "Necesitamos información actualizada de ti"), "action"),
}


def tax_status(status_key, lang):
    text, tone = _TAX.get(status_key, ((status_key, status_key), "neutral"))
    return _t(text, lang), tone


# ------------------------------------------------------------------ ITIN / W-7 (app/models/itin.py ITIN_STAGES)
_ITIN = {
    "intake_started": (("Continue where you left off", "Continúa donde te quedaste"), "action"),
    "waiting_docs": (("We need documents from you", "Necesitamos documentos de ti"), "action"),
    "waiting_originals": (("We need your original documents", "Necesitamos tus documentos originales"), "action"),
    "ready_review": (("OG is about to review your case", "OG está por revisar tu caso"), "processing"),
    "og_reviewing": (("OG is reviewing your information", "OG está revisando tu información"), "processing"),
    "tax_preparation": (("OG is preparing your tax return", "OG está preparando tu declaración"), "processing"),
    "ready_signature": (("Ready for your signature", "Lista para tu firma"), "action"),
    "ready_irs": (("Your package is ready", "Tu paquete está listo"), "processing"),
    "sent_irs": (("Sent to the IRS", "Enviado al IRS"), "processing"),
    "irs_processing": (("Being processed by the IRS", "En proceso en el IRS"), "processing"),
    "irs_response": (("The IRS responded — OG will follow up", "El IRS respondió — OG dará seguimiento"), "processing"),
    "completed": (("Completed", "Completado"), "done"),
}


def itin_status(stage_key, lang):
    text, tone = _ITIN.get(stage_key, ((stage_key, stage_key), "neutral"))
    return _t(text, lang), tone


# ------------------------------------------------------------------ Document requirements (app/case_documents.py DocumentRequirement.status)
_REQ = {
    "needed": (("Needed", "Necesario"), "action"),
    "requested": (("Requested", "Solicitado"), "action"),
    "uploaded": (("Received", "Recibido"), "processing"),
    "under_review": (("Being reviewed", "En revisión"), "processing"),
    "accepted": (("Accepted", "Aceptado"), "done"),
    "needs_replacement": (("Please upload a new copy", "Sube una copia nueva"), "problem"),
}


def requirement_status(status_key, lang):
    text, tone = _REQ.get(status_key, ((status_key, status_key), "neutral"))
    return _t(text, lang), tone


# ------------------------------------------------------------------ Payments (app.payments.status_of — Charge)
_PAYMENT = {
    "no_payment_required": (("No Payment Required", "No se requiere pago"), "neutral"),
    "estimate": (("Estimate", "Estimado"), "neutral"),
    "payment_pending": (("Payment Needed", "Pago necesario"), "action"),
    "partially_paid": (("Partially Paid", "Pagado parcialmente"), "action"),
    "paid": (("Paid", "Pagado"), "done"),
    "refunded": (("Refunded", "Reembolsado"), "neutral"),
    "partially_refunded": (("Partially Refunded", "Reembolsado parcialmente"), "neutral"),
    "canceled": (("Canceled", "Cancelado"), "neutral"),
}


def payment_status(status_key, lang):
    text, tone = _PAYMENT.get(status_key, ((status_key, status_key), "neutral"))
    return _t(text, lang), tone


# ------------------------------------------------------------------ NJ Driver License (app/models/driver_license.py DL_STATUSES)
_DL = {
    "draft": (("Continue where you left off", "Continúa donde te quedaste"), "action"),
    "submitted": (("We received your information", "Recibimos tu información"), "processing"),
    "og_review": (("OG is reviewing your information", "OG está revisando tu información"), "processing"),
    "waiting_client": (("We need information from you", "Necesitamos información de ti"), "action"),
    "in_progress": (("In progress", "En progreso"), "processing"),
    "completed": (("Completed", "Completado"), "done"),
    "on_hold": (("On hold", "En pausa"), "neutral"),
    "closed": (("Closed", "Cerrado"), "neutral"),
    "reopened": (("We need updated information from you", "Necesitamos información actualizada de ti"), "action"),
}


def dl_status(status_key, lang):
    text, tone = _DL.get(status_key, ((status_key, status_key), "neutral"))
    return _t(text, lang), tone


# ------------------------------------------------------------------ NJ Driver License milestone sub-statuses (customer-friendly, per-milestone)
_DL_MILESTONE = {
    "documents": (("We are checking your documents", "Estamos revisando tus documentos"), "processing"),
    "initial_permit": (("Appointment needed", "Se necesita una cita"), "action"),
    "knowledge_test": (("Ready to practice", "Listo(a) para practicar"), "processing"),
    "road_test": (("To be determined", "Por determinar"), "neutral"),
    "license_obtained": (("Almost there!", "¡Ya casi!"), "processing"),
    "completed": (("Completed", "Completado"), "done"),
}


def dl_milestone_help(milestone, lang):
    text, tone = _DL_MILESTONE.get(milestone, ((milestone, milestone), "neutral"))
    return _t(text, lang), tone
