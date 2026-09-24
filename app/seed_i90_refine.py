"""UX / content refinement pass for the existing I-90 intake.

Applied IN PLACE to the one I-90 form (no second form is created) and idempotent:
it does nothing once `green_card_front` exists. Changes:

  * "already expired / expires within six months" is listed first under the reason
    question (presentation order only; stored values and logic are untouched);
  * the arrival step explains what "admission" and "port of entry" mean;
  * interpreter fields start pre-filled with OG's details, as EDITABLE defaults read
    from `app/business_info.py` ("@biz:NAME" defaults — nothing is locked);
  * the Documents step asks explicitly for the Green Card front/back and the Social
    Security card, adapted to the customer's reason;
  * the final step's signature wording no longer states an absolute rule.

The form's `version` is bumped so applications completed earlier stay tied to the
version they were completed under.
"""

from app.extensions import db
from app.models import ConditionalRule, Form, FormField, RuleCondition

I90_SLUG = "i-90-client-intake"

_ICON = ('<svg class="w-4 h-4 text-accent-600 shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" '
         'stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24" aria-hidden="true">{}</svg>')
_PLANE = _ICON.format('<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>')
_CAR = _ICON.format('<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/>')
_SHIP = _ICON.format('<path d="M2 21c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1 .6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M19.38 20A11.6 11.6 0 0 0 21 14l-9-4-9 4c0 2.9.94 5.34 2.81 7.76"/><path d="M19 13V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6"/><path d="M12 10v4"/><path d="M12 2v3"/>')
_CAMERA = _ICON.format('<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3z"/><circle cx="12" cy="13" r="3"/>')
_CHIP = ('<span class="inline-flex items-center gap-2 rounded-full bg-mist-50 border border-mist-200 px-3 py-1.5 '
         'text-[13px] font-semibold text-brand-800">{}{}</span>')


def _chips(a, b, c):
    return '<div class="flex flex-wrap gap-2">' + _CHIP.format(_PLANE, a) + _CHIP.format(_CAR, b) + _CHIP.format(_SHIP, c) + "</div>"


def _label(text, sub=None):
    html = f'<span class="text-xs font-bold uppercase tracking-wider text-accent-700">{text}</span>'
    if sub:
        html += f'<span class="block mt-1 text-[13px] text-slate-600">{sub}</span>'
    return html


def _tip(text):
    return ('<div class="flex gap-2.5 rounded-xl bg-mist-50 border border-mist-200 px-3.5 py-3 text-[13px] '
            f'leading-relaxed text-slate-700">{_CAMERA}<span>{text}</span></div>')


def _field(form, name):
    for page in form.pages:
        for f in page.fields:
            if f.internal_name == name:
                return f
    return None


def _page(form, title_en):
    return next((p for p in form.pages if p.title_en == title_en), None)


def _add_field(page, name, ftype, order, label=("", ""), content=None, help=None, **kw):
    f = FormField(page_id=page.id, sort_order=order, field_type=ftype, internal_name=name,
                  label_en=label[0], label_es=label[1], width="full", **kw)
    if content:
        f.content_en, f.content_es = content
    if help:
        f.help_text_en, f.help_text_es = help
    db.session.add(f)
    db.session.flush()
    return f


def _add_rule(form, action, target, conditions, match="all"):
    rule = ConditionalRule(form_id=form.id, sort_order=len(form.rules), match_type=match, action=action, target_field_id=target.id)
    db.session.add(rule)
    db.session.flush()
    for field, op, value in conditions:
        db.session.add(RuleCondition(rule_id=rule.id, field_id=field.id, operator=op, value=value))
    form.rules.append(rule)


def apply_i90_refinements(form):
    if _field(form, "green_card_front") is not None:
        return False

    # 1. Most common reason first — order only.
    reason = _field(form, "reason_a")
    for i, o in enumerate(sorted(reason.options, key=lambda o: (o.value != "expired_or_expiring", o.sort_order))):
        o.sort_order = i
        if o.value == "expired_or_expiring":
            o.label_en = "My current card has already expired or will expire within six months"

    # 2. Arrival step.
    arrival = _page(form, "Your arrival in the U.S.")
    arrival.description_en = "Think about the trip in which you were admitted to the United States."
    arrival.description_es = "Piensa en el viaje en el que fuiste admitido(a) a los Estados Unidos."
    dest, port = _field(form, "dest_us"), _field(form, "port_of_entry")
    dest.sort_order, port.sort_order = 1, 2
    _add_field(arrival, "arrival_intro", "paragraph", 0,
               content=(_chips("Airport", "Land border", "Seaport"), _chips("Aeropuerto", "Frontera terrestre", "Puerto marítimo")))
    dest.help_text_en = "Enter the destination you were traveling to in the United States when you were admitted."
    dest.help_text_es = "Indica el destino al que te dirigías en Estados Unidos cuando fuiste admitido(a)."
    port.help_text_en = "This may be the airport, land border crossing, or seaport where you entered and were admitted to the United States."
    port.help_text_es = "Puede ser el aeropuerto, cruce fronterizo terrestre o puerto marítimo donde ingresaste y fuiste admitido(a) a Estados Unidos."

    # 3. Interpreter defaults (editable; resolved from business_info at render time).
    for name, value in {
        "int_family": "@biz:INTERPRETER_LAST_NAME", "int_given": "@biz:INTERPRETER_FIRST_NAME",
        "int_org": "@biz:INTERPRETER_ORG", "int_phone": "@biz:INTERPRETER_PHONE", "int_email": "@biz:INTERPRETER_EMAIL",
        "int_is_us": "yes", "int_street": "@biz:OFFICE_STREET", "int_unit_type": "@biz:OFFICE_UNIT_TYPE",
        "int_unit_number": "@biz:OFFICE_UNIT_NUMBER", "int_city": "@biz:OFFICE_CITY", "int_state": "@biz:OFFICE_STATE",
        "int_zip": "@biz:OFFICE_ZIP",
    }.items():
        _field(form, name).default_value = value

    # 4. Documents.
    docs = _page(form, "Documents")
    old_card = _field(form, "evidence_card_error")  # superseded by the card front/back requests
    if old_card is not None:
        for rule in [r for r in form.rules if r.target_field_id == old_card.id]:
            for c in list(rule.conditions):
                db.session.delete(c)
            form.rules.remove(rule)
            db.session.delete(rule)
        db.session.flush()
        db.session.delete(old_card)
        db.session.flush()
    name_change, other = _field(form, "evidence_name_change"), _field(form, "documents_other")

    _add_field(docs, "docs_main_label", "paragraph", 0, content=(_label("Main documents"), _label("Documentos principales")))
    _add_field(docs, "docs_quality_tip", "paragraph", 1, content=(
        _tip("To avoid delays, make sure the entire card is visible, the text is readable, and there is no glare, heavy shadow, or cropped information."),
        _tip("Para evitar retrasos, asegúrate de que la tarjeta completa aparezca en la foto, que el texto sea legible y que no haya reflejos, sombras ni partes cortadas.")))
    single = dict(allowed_file_types="pdf,jpg,jpeg,png", max_files=1, max_file_size_mb=10)
    front = _add_field(
        docs, "green_card_front", "file_upload", 2, ("Permanent Resident Card — Front", "Tarjeta de Residente Permanente — Frente"), required=True,
        help=("Upload a clear, complete, readable, well-lit photo of the front of your Green Card.",
              "Sube una foto clara, completa, legible y bien iluminada del frente de tu Green Card."),
        source_ref="OG addition (Part 2, Items 2.d / 3.d)",
        source_note="Card copy for OG's preparation; also the card USCIS asks to attach when the card holds DHS-error data. Not requested when the reason means the card is lost, stolen or not received.",
        **single)
    back = _add_field(
        docs, "green_card_back", "file_upload", 3, ("Permanent Resident Card — Back", "Tarjeta de Residente Permanente — Reverso"), required=True,
        help=("Upload a clear, complete, readable, well-lit photo of the back of your Green Card.",
              "Sube una foto clara, completa, legible y bien iluminada del reverso de tu Green Card."),
        source_ref="OG addition (Part 2, Items 2.d / 3.d)", source_note="See front.", **single)
    _add_field(
        docs, "ssn_card", "file_upload", 4, ("Social Security Card", "Tarjeta del Seguro Social"), required=False,
        help=("Upload a clear, readable photo of your Social Security card.", "Sube una foto clara y legible de tu tarjeta del Seguro Social."),
        source_ref="OG addition", source_note="OG document-collection request; not a USCIS requirement for every I-90. Optional.", **single)
    name_change.sort_order = 5
    _add_field(docs, "docs_other_label", "paragraph", 6, content=(
        _label("Other documents", "Do you have any other document that could help us?"),
        _label("Otros documentos", "¿Tienes algún otro documento que pueda ayudarnos?")))
    other.sort_order = 7
    other.label_en, other.label_es = "Other Supporting Documents (optional)", "Otros documentos de apoyo (opcional)"
    other.help_text_en = other.help_text_es = None

    # The card is requested only when the reason means the customer still holds it.
    ra, rb = _field(form, "reason_a"), _field(form, "reason_b")
    conds = [(ra, "not_equals", v) for v in ("lost_stolen_destroyed", "never_received")] + \
            [(rb, "not_equals", v) for v in ("cond_lost_stolen_destroyed", "cond_never_received")]
    for f in (front, back):
        _add_rule(form, "show_field", f, conds, "all")

    # 5. Final step.
    confirm = _page(form, "Confirm and send to OG")
    confirm.title_en, confirm.title_es = "Confirm and Send to OG", "Confirma y envía a OG"
    confirm.description_en = ("Review your information and confirm that it is complete and accurate. OG Multiservices will prepare your Form I-90 "
                              "and guide you through the required signature based on how your application will be filed.")
    confirm.description_es = ("Revisa tu información y confirma que esté completa y correcta. OG Multiservices preparará tu Formulario I-90 "
                              "y te indicará cómo completar la firma requerida según la forma en que se presente tu solicitud.")
    note = _field(form, "confirm_note")
    note.content_en = '<span class="text-[13px] text-slate-500">Online filing may use an electronic signing process. Paper filings require the appropriate signature on the application.</span>'
    note.content_es = '<span class="text-[13px] text-slate-500">Las solicitudes presentadas en línea pueden utilizar un proceso de firma electrónica. Las solicitudes en papel requieren la firma correspondiente en el formulario.</span>'
    prep, acc = _field(form, "preparer_request"), _field(form, "confirm_accurate")
    prep.content_en = "I ask OG Multiservices to prepare my Form I-90 based on the information I provided or authorized."
    prep.content_es = "Solicito a OG Multiservices que prepare mi Formulario I-90 con base en la información que proporcioné o autoricé."
    acc.content_en = "I confirm that the information I provided is complete, true, and correct to the best of my knowledge."
    acc.content_es = "Confirmo que la información que proporcioné es completa, verdadera y correcta según mi leal saber y entender."
    form.submit_label_en, form.submit_label_es = "Send to OG", "Enviar a OG"
    form.version = (form.version or 1) + 1
    return True


def ensure_i90_refinements():
    form = Form.query.filter_by(slug=I90_SLUG).first()
    if not form or not form.source_edition:
        return False
    if not apply_i90_refinements(form):
        return False
    db.session.commit()
    return True
