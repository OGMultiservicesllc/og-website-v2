"""The transactional email catalog (item 9 of the spec). Two kinds of template:

- DIRECT templates (`email_verification`, `password_reset`, `email_changed`) carry a secret or a
  moment-in-time value (a code, a reset link, an old/new email pair) that must never be persisted in
  `EmailLog.ref_json` — their `EmailContent` is built once, at send time, by the caller (app/verification.py,
  app/password_reset.py, the profile change-email route) and handed to `app.email_service.send_transactional_email`
  via its `content=` parameter. They are not in `TEMPLATES` and are not retryable — a "failed" verification
  code or reset-link email is fixed by the customer requesting a new one, not by replaying stale content.

- REGISTRY templates (everything else) are looked up in `TEMPLATES` by `template_key` and rebuilt from a
  small, safe `ref` dict of reference ids (e.g. {"payment_id": 5}) — never rendered content, never PII
  beyond ids — so a failed send can be retried later and always reflects CURRENT data, and Admin's retry
  button works uniformly for all of them.

Every builder returns `None` when, on reflection, nothing should actually be sent (e.g. the record no
longer exists) — `app.email_service.send_transactional_email` treats that as "nothing to do", not a failure.
"""

from app.email_render import EmailContent, abs_url, mask_email

TXT = {
    "verify_heading": ("Confirm your email address", "Confirma tu dirección de correo electrónico"),
    "verify_p1": (
        "We sent a 6-digit verification code to {email}.",
        "Enviamos un código de verificación de 6 dígitos a {email}.",
    ),
    "verify_p2": (
        "Enter this code on the verification screen to continue.",
        "Ingresa este código en la pantalla de verificación para continuar.",
    ),
    "verify_footnote": (
        "This code expires in 10 minutes and can only be used once.",
        "Este código vence en 10 minutos y solo se puede usar una vez.",
    ),
    "reset_heading": ("Reset your password", "Restablece tu contraseña"),
    "reset_p1": (
        "We received a request to reset the password for your OG Multiservices account.",
        "Recibimos una solicitud para restablecer la contraseña de tu cuenta de OG Multiservices.",
    ),
    "reset_p2": (
        "Click the button below to choose a new password. If you didn't request this, you can safely ignore this email.",
        "Haz clic en el botón de abajo para elegir una nueva contraseña. Si no solicitaste esto, puedes ignorar este correo.",
    ),
    "reset_cta": ("Reset Password", "Restablecer Contraseña"),
    "reset_footnote": (
        "This link expires in 30 minutes and can only be used once.",
        "Este enlace vence en 30 minutos y solo se puede usar una vez.",
    ),
    "changed_heading": ("Your account email was changed", "Se cambió el correo electrónico de tu cuenta"),
    "changed_p1": (
        "The email address on your OG Multiservices account was changed to {new_email}.",
        "La dirección de correo electrónico de tu cuenta de OG Multiservices se cambió a {new_email}.",
    ),
    "changed_p2": (
        "If you made this change, no action is needed. If you did NOT make this change, please contact OG Multiservices immediately.",
        "Si tú hiciste este cambio, no se requiere ninguna acción. Si NO hiciste este cambio, comunícate con OG Multiservices de inmediato.",
    ),
    "submitted_heading": ("We received your information", "Recibimos tu información"),
    "submitted_p1": (
        "Thank you. OG Multiservices has received your information for {service}.",
        "Gracias. OG Multiservices recibió tu información para {service}.",
    ),
    "submitted_p2": (
        "Our team will review it and let you know if anything else is needed.",
        "Nuestro equipo la revisará y te avisaremos si necesitamos algo más.",
    ),
    "submitted_cta": ("View in My Account", "Ver en Mi Cuenta"),
    "info_heading": ("OG needs more information", "OG necesita más información"),
    "info_p1": (
        "OG Multiservices needs additional information for {service}.",
        "OG Multiservices necesita información adicional para {service}.",
    ),
    "info_p2": (
        "Sign in securely to My Account to see exactly what's needed.",
        "Inicia sesión de forma segura en Mi Cuenta para ver exactamente qué se necesita.",
    ),
    "info_cta": ("Go to My Account", "Ir a Mi Cuenta"),
    "doc_heading": ("OG needs a document", "OG necesita un documento"),
    "doc_p1": (
        "OG Multiservices needs a document for {service}.",
        "OG Multiservices necesita un documento para {service}.",
    ),
    "doc_p2": (
        "Sign in securely to My Account to see the request and upload it.",
        "Inicia sesión de forma segura en Mi Cuenta para ver la solicitud y subirlo.",
    ),
    "doc_cta": ("Upload Document", "Subir Documento"),
    "replace_heading": ("A document needs to be replaced", "Un documento debe ser reemplazado"),
    "replace_p1": (
        "OG Multiservices needs an updated document for {service}. Sign in to My Account to view the request.",
        "OG Multiservices necesita un documento actualizado para {service}. Inicia sesión en Mi Cuenta para ver la solicitud.",
    ),
    "replace_cta": ("View Request", "Ver Solicitud"),
    "completed_heading": ("Your service is complete", "Tu servicio está completo"),
    "completed_p1": (
        "Good news — OG Multiservices has marked {service} as completed.",
        "Buenas noticias: OG Multiservices marcó {service} como completado.",
    ),
    "completed_cta": ("View in My Account", "Ver en Mi Cuenta"),
    "file_heading": ("A new file is available", "Hay un nuevo archivo disponible"),
    "file_p1": (
        "A new file from OG Multiservices is available in your account.",
        "Hay un nuevo archivo de OG Multiservices disponible en tu cuenta.",
    ),
    "file_cta": ("View File", "Ver Archivo"),
    "preq_heading": ("Payment requested", "Pago solicitado"),
    "preq_p1": (
        "OG Multiservices has requested a payment of {amount} for {service}.",
        "OG Multiservices ha solicitado un pago de {amount} por {service}.",
    ),
    "preq_cta": ("Pay Now", "Pagar Ahora"),
    "prcv_heading": ("Payment received", "Pago recibido"),
    "prcv_p1": (
        "Thank you — OG Multiservices received your payment of {amount} for {service}.",
        "Gracias. OG Multiservices recibió tu pago de {amount} por {service}.",
    ),
    "prcv_p2_receipt": (
        "Receipt {receipt} · {date} · {method}",
        "Recibo {receipt} · {date} · {method}",
    ),
    "prcv_cta": ("View Receipt", "Ver Recibo"),
    "refund_heading": ("Refund processed", "Reembolso procesado"),
    "refund_p1": (
        "OG Multiservices processed a refund of {amount} for {service}.",
        "OG Multiservices procesó un reembolso de {amount} por {service}.",
    ),
    "refund_cta": ("View in My Account", "Ver en Mi Cuenta"),
    "course_heading": ("Your course is available", "Tu curso está disponible"),
    "course_p1": (
        "{course} is now available in your OG Academy account.",
        "{course} ya está disponible en tu cuenta de OG Academy.",
    ),
    "course_cta": ("Go to My Courses", "Ir a Mis Cursos"),
    "cert_heading": ("Your certificate is ready", "Tu certificado está listo"),
    "cert_p1": (
        "Congratulations! Your certificate for {course} is ready.",
        "¡Felicidades! Tu certificado para {course} está listo.",
    ),
    "cert_cta": ("View Certificate", "Ver Certificado"),
}


def _t(key, lang):
    en, es = TXT[key]
    return es if lang == "es" else en


# ------------------------------------------------------------------ DIRECT templates (never ref-based)

def build_email_verification(lang, code, email):
    return EmailContent(
        subject=_t("verify_heading", lang),
        heading=_t("verify_heading", lang),
        paragraphs=[_t("verify_p1", lang).format(email=mask_email(email)), _t("verify_p2", lang)],
        code=code,
        footnote=_t("verify_footnote", lang),
    )


def build_password_reset(lang, reset_url):
    return EmailContent(
        subject=_t("reset_heading", lang),
        heading=_t("reset_heading", lang),
        paragraphs=[_t("reset_p1", lang), _t("reset_p2", lang)],
        cta_label=_t("reset_cta", lang),
        cta_url=reset_url,
        footnote=_t("reset_footnote", lang),
    )


def build_email_changed(lang, new_email):
    return EmailContent(
        subject=_t("changed_heading", lang),
        heading=_t("changed_heading", lang),
        paragraphs=[_t("changed_p1", lang).format(new_email=mask_email(new_email)), _t("changed_p2", lang)],
    )


def build_account_invitation(activate_url, name):
    """Account invitations go to migrated Wix customers whose language preference is unknown — always
    bilingual (EN then ES) rather than guessing, per the migration spec's explicit instruction."""
    return EmailContent(
        subject="Activate Your OG Multiservices Account / Activa tu cuenta de OG Multiservices",
        heading=f"Welcome, {name} / Bienvenido/a, {name}",
        paragraphs=[
            "OG Multiservices has set up an account for you on our new website. Click the button below "
            "to create a password and access your account — your services and information are waiting for you.",
            "OG Multiservices creó una cuenta para ti en nuestro nuevo sitio web. Haz clic en el botón de "
            "abajo para crear una contraseña y acceder a tu cuenta — tus servicios e información te esperan.",
        ],
        cta_label="Activate My Account / Activar Mi Cuenta",
        cta_url=activate_url,
        footnote="This link expires in 7 days and can only be used once. / Este enlace vence en 7 días y solo se puede usar una vez.",
    )


# ------------------------------------------------------------------ REGISTRY templates (ref-based, retryable)

def _service_title_and_url(lang, kind, obj_id):
    """(service_title, cta_url) for the three intake shapes this app has (item 8/9)."""
    if kind == "form_submission":
        from app.models import FormSubmission

        sub = FormSubmission.query.get(obj_id)
        if not sub:
            return None, None
        title = sub.service.title(lang) if sub.service else sub.form.name_admin
        if sub.case_id:
            return title, abs_url("account.my_case_detail", lang, case_id=sub.case_id)
        return title, abs_url("account.application_detail", lang, submission_id=sub.id)
    if kind == "tax":
        from app.models import TaxCaseData

        tax = TaxCaseData.query.get(obj_id)
        if not tax:
            return None, None
        title = "Individual Tax Return" if lang == "en" else "Declaración de Impuestos Individual"
        return title, abs_url("account.my_case_detail", lang, case_id=tax.case_id)
    if kind == "dl":
        from app.models import DlCaseData

        dl = DlCaseData.query.get(obj_id)
        if not dl:
            return None, None
        title = "NJ Driver License Assistance" if lang == "en" else "Asistencia de Licencia de Conducir de NJ"
        return title, abs_url("account.my_case_detail", lang, case_id=dl.case_id)
    if kind == "case":
        from app.models import Case

        case = Case.query.get(obj_id)
        if not case:
            return None, None
        from app.case_types import type_title

        return type_title(case.case_type), abs_url("account.my_case_detail", lang, case_id=case.id)
    return None, None


def build_service_submitted(lang, ref):
    title, url = _service_title_and_url(lang, ref.get("kind"), ref.get("id"))
    if not title:
        return None
    return EmailContent(
        subject=_t("submitted_heading", lang),
        heading=_t("submitted_heading", lang),
        paragraphs=[_t("submitted_p1", lang).format(service=title), _t("submitted_p2", lang)],
        cta_label=_t("submitted_cta", lang), cta_url=url,
    )


def build_info_needed(lang, ref):
    title, url = _service_title_and_url(lang, ref.get("kind"), ref.get("id"))
    if not title:
        return None
    return EmailContent(
        subject=_t("info_heading", lang),
        heading=_t("info_heading", lang),
        paragraphs=[_t("info_p1", lang).format(service=title)],
        cta_label=_t("info_cta", lang), cta_url=url,
    )


def build_document_needed(lang, ref):
    from app.models import DocumentRequirement

    req = DocumentRequirement.query.get(ref.get("requirement_id"))
    if not req:
        return None
    from app.case_types import type_title

    title = type_title(req.case.case_type)
    return EmailContent(
        subject=_t("doc_heading", lang),
        heading=_t("doc_heading", lang),
        paragraphs=[_t("doc_p1", lang).format(service=title), _t("doc_p2", lang)],
        cta_label=_t("doc_cta", lang), cta_url=abs_url("account.my_case_detail", lang, case_id=req.case_id),
    )


def build_document_replacement(lang, ref):
    from app.models import DocumentRequirement

    req = DocumentRequirement.query.get(ref.get("requirement_id"))
    if not req:
        return None
    from app.case_types import type_title

    title = type_title(req.case.case_type)
    return EmailContent(
        subject=_t("replace_heading", lang),
        heading=_t("replace_heading", lang),
        paragraphs=[_t("replace_p1", lang).format(service=title)],
        cta_label=_t("replace_cta", lang), cta_url=abs_url("account.my_case_detail", lang, case_id=req.case_id),
    )


def build_service_completed(lang, ref):
    title, url = _service_title_and_url(lang, ref.get("kind"), ref.get("id"))
    if not title:
        return None
    return EmailContent(
        subject=_t("completed_heading", lang),
        heading=_t("completed_heading", lang),
        paragraphs=[_t("completed_p1", lang).format(service=title)],
        cta_label=_t("completed_cta", lang), cta_url=url,
    )


def build_file_available(lang, ref):
    from app.models import CustomerFile

    f = CustomerFile.query.get(ref.get("file_id"))
    if not f or not f.published_at:
        return None
    return EmailContent(
        subject=_t("file_heading", lang),
        heading=_t("file_heading", lang),
        paragraphs=[_t("file_p1", lang)],
        cta_label=_t("file_cta", lang), cta_url=abs_url("account.files_from_og", lang),
    )


def build_payment_requested(lang, ref):
    from app import payments as pay_svc
    from app.models import PaymentRequest

    req = PaymentRequest.query.get(ref.get("payment_request_id"))
    if not req or not req.is_open:
        return None
    charge = req.charge
    return EmailContent(
        subject=_t("preq_heading", lang),
        heading=_t("preq_heading", lang),
        paragraphs=[_t("preq_p1", lang).format(amount=pay_svc.format_cents(req.requested_cents), service=charge.display_title(lang))],
        cta_label=_t("preq_cta", lang), cta_url=abs_url("account.payments", lang),
    )


def build_payment_received(lang, ref):
    from app import payments as pay_svc
    from app.models import Payment, method_label

    p = Payment.query.get(ref.get("payment_id"))
    if not p or p.status != "completed":
        return None
    charge = p.charge
    method = f"{(p.card_brand or 'Card').title()} •••• {p.card_last4}" if p.method == "square" and p.card_last4 else method_label(p.method, lang)
    when = (p.completed_at or p.created_at)
    receipt_line = _t("prcv_p2_receipt", lang).format(
        receipt=p.receipt_number or f"#{p.id}", date=when.strftime("%b %d, %Y") if when else "", method=method,
    )
    return EmailContent(
        subject=_t("prcv_heading", lang),
        heading=_t("prcv_heading", lang),
        paragraphs=[_t("prcv_p1", lang).format(amount=pay_svc.format_cents(p.amount_cents), service=charge.display_title(lang)), receipt_line],
        cta_label=_t("prcv_cta", lang), cta_url=abs_url("account.payment_receipt", lang, payment_id=p.id),
    )


def build_refund_processed(lang, ref):
    from app import payments as pay_svc
    from app.models import Refund

    r = Refund.query.get(ref.get("refund_id"))
    if not r or r.status != "completed":
        return None
    charge = r.payment.charge
    return EmailContent(
        subject=_t("refund_heading", lang),
        heading=_t("refund_heading", lang),
        paragraphs=[_t("refund_p1", lang).format(amount=pay_svc.format_cents(r.amount_cents), service=charge.display_title(lang))],
        cta_label=_t("refund_cta", lang), cta_url=abs_url("account.payments", lang),
    )


def build_course_access(lang, ref):
    from app.models import Enrollment

    e = Enrollment.query.get(ref.get("enrollment_id"))
    if not e or not e.is_active:
        return None
    return EmailContent(
        subject=_t("course_heading", lang),
        heading=_t("course_heading", lang),
        paragraphs=[_t("course_p1", lang).format(course=e.course.title(lang))],
        cta_label=_t("course_cta", lang), cta_url=abs_url("account.courses", lang),
    )


def build_certificate_available(lang, ref):
    from app.models import Certificate

    cert = Certificate.query.get(ref.get("certificate_id"))
    if not cert or cert.status != "valid":
        return None
    return EmailContent(
        subject=_t("cert_heading", lang),
        heading=_t("cert_heading", lang),
        paragraphs=[_t("cert_p1", lang).format(course=cert.course.title(lang))],
        cta_label=_t("cert_cta", lang), cta_url=abs_url("account.certificate", lang, slug=cert.course.slug),
    )


TEMPLATES = {
    "service_submitted": build_service_submitted,
    "info_needed": build_info_needed,
    "document_needed": build_document_needed,
    "document_replacement": build_document_replacement,
    "service_completed": build_service_completed,
    "file_available": build_file_available,
    "payment_requested": build_payment_requested,
    "payment_received": build_payment_received,
    "refund_processed": build_refund_processed,
    "course_access": build_course_access,
    "certificate_available": build_certificate_available,
}

# Direct templates are intentionally NOT in TEMPLATES — see the module docstring. Admin's retry action
# checks against this set to show "request a new one" instead of an unsafe generic content replay.
DIRECT_TEMPLATE_KEYS = ("email_verification", "password_reset", "email_changed", "account_invitation")
