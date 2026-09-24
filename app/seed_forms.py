"""Pilot smart-intake shell for Green Card Renewal Preparation (Form I-90).

This is a SHELL only: the structure, the bilingual plumbing, one branching
question and the consent page. It deliberately contains NO USCIS I-90 questions:
the official, current question set must be supplied and verified before any are
added. It is created as a Draft, so nothing reaches visitors until an
administrator finishes and publishes it.

Idempotent: does nothing if the form already exists (or has been renamed).
"""

from app.extensions import db
from app.models import (
    ConditionalRule,
    FieldOption,
    Form,
    FormField,
    FormPage,
    RuleCondition,
    Service,
    ServiceCategory,
)

I90_SLUG = "i-90-client-intake"


def _field(page, order, field_type, name, label, *, required=False, options=(), **extra):
    from app.blueprints.admin.forms_routes import _default_field_kwargs

    kwargs = _default_field_kwargs(field_type)
    kwargs.update(extra)
    kwargs["required"] = required
    field = FormField(
        page_id=page.id, sort_order=order, internal_name=name,
        label_en=label[0], label_es=label[1], **kwargs,
    )
    db.session.add(field)
    db.session.flush()
    for i, (value, en, es) in enumerate(options):
        db.session.add(FieldOption(field_id=field.id, sort_order=i, value=value, label_en=en, label_es=es))
    return field


def ensure_i90_shell():
    if Form.query.filter_by(slug=I90_SLUG).first():
        return False
    service = (
        Service.query.join(ServiceCategory)
        .filter(ServiceCategory.slug == "immigration", Service.slug == "green-card-renewal")
        .first()
    )
    if not service:
        return False

    form = Form(
        slug=I90_SLUG, name_admin="I-90 Client Intake", status="draft", form_type="service_intake",
        title_en="Green Card Renewal — Client Intake", title_es="Renovación de Green Card — Solicitud del Cliente",
        description_en="Answer a few questions so we can prepare your document package. Your progress is saved automatically — you can leave and come back anytime.",
        description_es="Responde unas preguntas para que preparemos tu paquete de documentos. Tu progreso se guarda automáticamente: puedes salir y volver cuando quieras.",
        submit_label_en="Submit application", submit_label_es="Enviar solicitud",
        success_message_en="Thank you! We received your information and will contact you about the next steps.",
        success_message_es="¡Gracias! Recibimos tu información y te contactaremos sobre los próximos pasos.",
        show_progress=True,
    )
    db.session.add(form)
    db.session.flush()

    def page(order, en, es):
        p = FormPage(form_id=form.id, sort_order=order, title_en=en, title_es=es)
        db.session.add(p)
        db.session.flush()
        return p

    p1 = page(0, "Your contact information", "Tu información de contacto")
    _field(p1, 0, "full_name", "full_name", ("Full name", "Nombre completo"), required=True,
           admin_notes="SHELL — the official I-90 question set has not been added yet. Do not publish until it is.")
    _field(p1, 1, "email", "email", ("Email", "Correo electrónico"), required=True)
    _field(p1, 2, "phone", "phone", ("Phone", "Teléfono"), required=True)

    p2 = page(1, "Your request", "Tu solicitud")
    reason = _field(
        p2, 0, "single_choice", "request_reason",
        ("What do you need help with?", "¿En qué necesitas ayuda?"), required=True,
        options=[
            ("renew_expiring", "Renew an expiring Green Card", "Renovar una Green Card por vencer"),
            ("replace_lost", "Replace a lost Green Card", "Reemplazar una Green Card perdida"),
            ("replace_stolen", "Replace a stolen Green Card", "Reemplazar una Green Card robada"),
            ("replace_damaged", "Replace a damaged Green Card", "Reemplazar una Green Card dañada"),
            ("other", "Other reason", "Otro motivo"),
        ],
    )
    other = _field(p2, 1, "long_answer", "other_reason_details", ("Tell us more", "Cuéntanos más"))
    rule = ConditionalRule(form_id=form.id, sort_order=0, match_type="all", action="show_field", target_field_id=other.id)
    db.session.add(rule)
    db.session.flush()
    db.session.add(RuleCondition(rule_id=rule.id, field_id=reason.id, operator="equals", value="other"))

    p3 = page(2, "Documents", "Documentos")
    _field(p3, 0, "paragraph", "documents_note", ("", ""),
           content_en="Upload any documents you already have. You can add more later.",
           content_es="Sube los documentos que ya tengas. Puedes agregar más después.")
    _field(p3, 1, "file_upload", "documents", ("Your documents (optional)", "Tus documentos (opcional)"),
           allowed_file_types="pdf,jpg,jpeg,png", max_file_size_mb=10, max_files=10)

    p4 = page(3, "Review & consent", "Revisión y consentimiento")
    _field(p4, 0, "paragraph", "disclaimer", ("", ""),
           content_en="OG Multiservices provides document preparation and administrative assistance. We do not provide legal representation or legal advice.",
           content_es="OG Multiservices ofrece preparación de documentos y asistencia administrativa. No brindamos representación legal ni asesoría legal.")
    _field(p4, 1, "consent", "consent", (
        "I confirm the information I provided is accurate and I understand OG Multiservices does not provide legal representation.",
        "Confirmo que la información que proporcioné es correcta y entiendo que OG Multiservices no brinda representación legal.",
    ), required=True)

    service.requires_intake = True
    service.form_id = form.id
    service.requires_account = True
    db.session.commit()
    return True
