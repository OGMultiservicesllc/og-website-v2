"""Smart Service Intake: ITIN / Form W-7 (Rev. December 2024), Tax & ITIN Services.

This is OG's ACTUAL online ITIN workflow, not a line-by-line digital W-7. The customer never sees or chooses W-7 reason codes (a-h); OG staff confirm the final reason
before "Ready for IRS". Scope: applicant physically in the U.S., valid U.S. mailing address, ITIN tied to a federal return OG prepares. ITIN Exceptions 1-5 are NOT
implemented (see docs/W-7_source_coverage.md). One W-7 application (this form) per ITIN applicant Person, all inside one ITIN case.

Passport-first: the passport photo page is uploaded (now or later), read (local MRZ parser / staff / customer-typed) and CONFIRMED by the customer before any Person fact is
written; nothing here ever blocks a customer who has not yet uploaded it.
"""

import json
from datetime import datetime

from app import w7_rules as R
from app import w7_text as T
from app.extensions import db
from app.models import Form, Service, ServiceCategory
from app.seed_ds260 import calc_field, dyn, para, private
from app.seed_i130 import page
from app.seed_i485 import block_pair, kp, mark_block_fields, only_if
from app.seed_i90 import STATE_OPTIONS, UNIT_TYPES, YES_NO, Builder
from app.seed_n400 import show_any, show_page_any

W7_SLUG = "w-7-client-intake"
SOURCE_NAME = "W-7"
SOURCE_EDITION = "Rev. 12-2024"
YN_UNSURE = YES_NO + [("unsure", "Not sure", "No estoy seguro(a)")]

def _span(text, cls):
    return f'<span class="block {cls}">{text}</span>'


# Customer wording that ensure_w7_refinements() also applies IN PLACE to a form that already exists (never touches answers or rules)
INTRO_FIELDS = {
    "intro_1": (_span(T.INTRO_LEAD[0], "text-[16px] leading-relaxed text-slate-700"), _span(T.INTRO_LEAD[1], "text-[16px] leading-relaxed text-slate-700")),
    "intro_2": (_span(T.INTRO_TIPS[0], "text-[15px] leading-relaxed text-slate-700"), _span(T.INTRO_TIPS[1], "text-[15px] leading-relaxed text-slate-700")),
    "intro_3": (_span(T.INTRO_SAVED[0], "text-[14px] text-slate-700") + _span(T.INTRO_NOTE[0], "mt-5 text-[12px] leading-snug text-slate-500"),
                _span(T.INTRO_SAVED[1], "text-[14px] text-slate-700") + _span(T.INTRO_NOTE[1], "mt-5 text-[12px] leading-snug text-slate-500")),
}
GROSS_FIELD = ("self_gross_note", (_span(T.GROSS_NOTE[0], "text-[14px] leading-relaxed text-slate-700") + _span(T.GROSS_NOTE2[0], "mt-2 text-[13px] leading-snug text-slate-500"),
                                   _span(T.GROSS_NOTE[1], "text-[14px] leading-relaxed text-slate-700") + _span(T.GROSS_NOTE2[1], "mt-2 text-[13px] leading-snug text-slate-500")))
PP_PAGE_DESC = ("With the passport we fill in your details faster.", "Con el pasaporte llenamos tus datos más rápido.")
DOCS_PAGE_DESC = ("Upload a clear photo of each document, now or later. For some, OG will also need the original.", "Sube una foto clara de cada documento, ahora o después. Para algunos, OG también necesitará el original.")
PP_HELP = ("Not with you? Choose “later” and keep going. You can add it any time from My Account.", "¿No lo tienes contigo? Elige “después” y sigue. Puedes agregarlo cuando quieras desde Mi Cuenta.")

SECTIONS = [
    {"key": "start", "title": {"en": "Before You Begin", "es": "Antes de empezar"}},
    {"key": "about", "title": {"en": "About the Applicant", "es": "Sobre el solicitante"}},
    {"key": "passport", "title": {"en": "Passport & Identification", "es": "Pasaporte e identificación"}},
    {"key": "contact", "title": {"en": "U.S. Contact Information", "es": "Contacto en EE. UU."}},
    {"key": "entry", "title": {"en": "U.S. Entry & Visa", "es": "Entrada a EE. UU. y visa"}},
    {"key": "itin", "title": {"en": "ITIN History", "es": "Historial de ITIN"}},
    {"key": "income", "title": {"en": "Work & Income", "es": "Trabajo e ingresos"}},
    {"key": "family", "title": {"en": "Spouse & Dependents", "es": "Cónyuge y dependientes"}},
    {"key": "documents", "title": {"en": "Tax & ITIN Documents", "es": "Documentos de impuestos e ITIN"}},
    {"key": "confirm", "title": {"en": "Confirmation", "es": "Confirmación"}},
]


def yn(b, name, label, *, req=True, help=None, opts=None, ref=None):
    return b.field(name, "single_choice", label, req=req, opts=opts or YES_NO, help=help, ref=ref)


def _doc_opts(keys):
    return [(k, R.ALL_DOC_LABELS[k][0], R.ALL_DOC_LABELS[k][1]) for k in keys]


def build_w7(form):
    b = Builder(form)

    # ---------------------------------------------------------------- never-shown system page
    page(b, "sys", ("Case information", "Información del caso"), group=None)
    for k in ("sb_identity", "sb_address", "sb_contact", "sb_entry"):
        b.field(f"{k}_avail", "short_answer", (f"{k} available", f"{k} disponible"), ref="OG system flag (never shown)")
        kp(b, f"{k}_avail", system=True)
    for name, ref in (("w_kind", "primary | spouse | dependent (set at setup)"), ("c_age", "age in years from the date of birth"), ("c_band", "age band u6 | 6_17 | 18plus"),
                      ("c_student_q", "the student question applies (6 to 23 years old)"), ("c_pp_uploaded", "passport photo page uploaded"), ("c_pp_confirmed", "passport information confirmed by the customer"),
                      ("c_pp_extract", "how the passport data was read"), ("c_reason", "CANDIDATE W-7 reason (staff confirm; never shown to the customer)"), ("c_flags", "OG review flag codes"),
                      ("ua_is_us", "U.S. address marker (this intake collects U.S. mailing addresses only)"), ("a_pp_number", "W-7 line 6d: passport number (confirmed from the passport)"),
                      ("a_pp_country", "W-7 line 6d: passport issuing country"), ("a_pp_issued", "passport issue date"), ("a_pp_expiry", "W-7 line 6d: passport expiration date")):
        calc_field(b, name, name, "OG system value (never shown): " + ref)
    b.fields["a_pp_number"].is_sensitive = True
    show_page_any(b, "sys", [[("sb_identity_avail", "equals", "__never__")]])

    # ---------------------------------------------------------------- before you begin
    page(b, "intro", ("Before you begin", "Antes de empezar"), group="start")
    dyn(b, "intro_case", "w7_context")
    for name, (en_html, es_html) in INTRO_FIELDS.items():
        b.field(name, "paragraph", ("", ""), content=(en_html, es_html))

    # ---------------------------------------------------------------- passport first
    page(b, "pp_status", ("The passport", "El pasaporte"), PP_PAGE_DESC, group="passport")
    b.field("pp_status", "single_choice", ("Do you have {ap}'s passport available right now?", "¿Tienes el pasaporte de {ap} disponible ahora?"), req=True,
            ref="OG workflow: passport-first (W-7 Instructions p. 3-4: passport is the only stand-alone document)",
            opts=[("have", "Yes — I can upload it now", "Sí — puedo subirlo ahora"), ("later", "No — I will upload it later", "No — lo subiré después"),
                  ("none", "{ap} does not have a passport", "{ap} no tiene pasaporte")],
            help=PP_HELP)
    page(b, "pp_upload", ("Upload the passport photo page", "Sube la página con la foto del pasaporte"), group="passport")
    dyn(b, "pp_card", "w7_passport")
    show_page_any(b, "pp_upload", [[("pp_status", "equals", "have")]])
    page(b, "no_passport", ("Other identification", "Otra identificación"), group="passport")
    para(b, "np_note", "Without a passport the IRS needs at least two types of documents that together prove identity and foreign status, and at least one must show a photograph (a child under 14, or under 18 if a student, may not need a photo document). "
                       "Tell us which of these the applicant has. OG reviews whether they are enough and tells you exactly what is missing.",
         "Sin pasaporte, el IRS necesita al menos dos tipos de documentos que juntos prueben identidad y estatus extranjero, y al menos uno debe mostrar una fotografía (un menor de 14 años, o de 18 si es estudiante, puede no necesitar un documento con foto). "
         "Dinos cuáles de estos tiene el solicitante. OG revisa si son suficientes y te dice exactamente qué falta.")
    b.field("alt_docs", "multi_choice", ("Which of these documents does {ap} have?", "¿Cuáles de estos documentos tiene {ap}?"), req=True, ref="OG workflow: no-passport evidence (W-7 Instructions p. 4 table)",
            opts=_doc_opts(R.NO_PASSPORT_CHOICES), help=("Choose every one that applies. You can upload copies later.", "Elige todos los que apliquen. Puedes subir copias después."))
    show_page_any(b, "no_passport", [[("pp_status", "equals", "none")]])

    # ---------------------------------------------------------------- identity (only when there is no passport to read)
    def edit_identity():
        b.field("a_family", "short_answer", ("Surnames (family name)", "Apellidos"), ref="W-7 line 1a", req=True, width="half", maxlen=60)
        b.field("a_given", "short_answer", ("First name", "Nombre"), ref="W-7 line 1a", req=True, width="half", maxlen=60)
        b.field("a_middle", "short_answer", ("Middle name (if any)", "Segundo nombre (si tiene)"), ref="W-7 line 1a", width="half", maxlen=60)
        b.field("a_dob", "date", ("Date of birth", "Fecha de nacimiento"), ref="W-7 line 4", req=True, date_rule="past", width="half")
        b.field("a_sex", "single_choice", ("Sex", "Sexo"), ref="W-7 line 4", req=True, width="half", opts=[("male", "Male", "Masculino"), ("female", "Female", "Femenino")])
        b.field("a_birth_city", "short_answer", ("City of birth", "Ciudad de nacimiento"), ref="W-7 line 4", req=True, width="half", maxlen=60)
        b.field("a_birth_country", "short_answer", ("Country of birth", "País de nacimiento"), ref="W-7 line 4", req=True, width="half", maxlen=60)
        b.field("a_nationality", "short_answer", ("Country of citizenship", "País de ciudadanía"), ref="W-7 line 6a", req=True, maxlen=60)
        names = ["a_family", "a_given", "a_middle", "a_dob", "a_sex", "a_birth_city", "a_birth_country", "a_nationality"]
        mark_block_fields(b, "sb_identity", names)
        for n in names:  # required only when there is no passport to read: with a passport these answers come from the customer's confirmation and must never block Review
            if b.fields[n].required:
                b.fields[n].required = False
                b.rule("require_field", n, [("pp_status", "equals", "none")])
    block_pair(b, "sb_identity", group="about", form_name="W-7", ctx=None, gates=[[("pp_status", "equals", "none")]],
               review_title=("We already have {ap}'s identity information", "Ya tenemos los datos de identidad de {ap}"), review_desc=("Confirm them or change them.", "Confírmalos o cámbialos."),
               edit_title=("About the applicant", "Sobre el solicitante"), edit_desc=("Type the details exactly as they appear on the identification documents.", "Escribe los datos exactamente como aparecen en los documentos de identificación."), build_edit=edit_identity)

    page(b, "birthname", ("Name at birth", "Nombre de nacimiento"), group="about")
    b.field("a_birth_name", "short_answer", ("Name at birth, if different from the name above", "Nombre de nacimiento, si es diferente al nombre de arriba"), ref="W-7 line 1b", maxlen=120,
            help=("For example a maiden name. Leave it blank if it is the same.", "Por ejemplo, un apellido de soltera. Déjalo en blanco si es el mismo."))

    # ---------------------------------------------------------------- U.S. contact
    def edit_address():
        b.field("ua_street", "short_answer", ("Street number and name", "Número y nombre de la calle"), ref="W-7 line 2 (U.S. mailing address)", req=True, maxlen=80,
                help=("Use a street address. A P.O. box or an “in care of” address can make the IRS reject an application when only a country is given for the foreign address.", "Usa una dirección de calle. Un apartado postal o una dirección “a cargo de” puede hacer que el IRS rechace una solicitud cuando solo se indica un país como dirección en el extranjero."))
        b.field("ua_unit_type", "dropdown", ("Unit type (if any)", "Tipo de unidad (si aplica)"), ref="W-7 line 2", opts=UNIT_TYPES, width="half")
        b.field("ua_unit_number", "short_answer", ("Unit number", "Número de unidad"), ref="W-7 line 2", width="half", maxlen=20)
        b.field("ua_city", "short_answer", ("City or town", "Ciudad o pueblo"), ref="W-7 line 2", req=True, maxlen=60)
        b.field("ua_state", "dropdown", ("State", "Estado"), ref="W-7 line 2", req=True, opts=STATE_OPTIONS, width="half")
        b.field("ua_zip", "short_answer", ("ZIP code", "Código postal (ZIP)"), ref="W-7 line 2", req=True, width="half", pattern=r"\d{5}", maxlen=5, msg=("Enter a 5-digit ZIP code.", "Ingresa un ZIP de 5 dígitos."))
        mark_block_fields(b, "sb_address", ["ua_street", "ua_unit_type", "ua_unit_number", "ua_city", "ua_state", "ua_zip"])
    block_pair(b, "sb_address", group="contact", form_name="W-7", ctx=None, review_title=("{ap}'s U.S. mailing address", "Dirección postal de {ap} en EE. UU."), review_desc=("Is this still where the IRS can send mail?", "¿Sigue siendo donde el IRS puede enviar correo?"),
               edit_title=("U.S. mailing address", "Dirección postal en EE. UU."), edit_desc=("A valid U.S. address where the IRS can mail the applicant.", "Una dirección válida en EE. UU. donde el IRS pueda enviar correo al solicitante."), build_edit=edit_address)

    def edit_contact():
        b.field("a_phone", "phone", ("Daytime telephone number", "Teléfono de día"), ref="W-7 (Sign Here: applicant's phone)", req=True, width="half")
        b.field("a_email", "email", ("Email address (if any)", "Correo electrónico (si tiene)"), ref="OG contact (not a W-7 item)", width="half")
        b.fields["a_email"].required = False
        mark_block_fields(b, "sb_contact", ["a_phone", "a_email"])
    block_pair(b, "sb_contact", group="contact", form_name="W-7", ctx=None, review_title=("{ap}'s phone and email", "Teléfono y correo de {ap}"), review_desc=("Is this still current?", "¿Sigue vigente?"),
               edit_title=("Phone and email", "Teléfono y correo"), edit_desc=("How OG can reach {ap} about this application.", "Cómo puede OG comunicarse con {ap} sobre esta solicitud."), build_edit=edit_contact)

    def edit_entry():
        b.field("a_entry_date", "date", ("Date {ap} entered the United States", "Fecha en que {ap} entró a Estados Unidos"), ref="OG workflow (days present in the U.S. for W-7 reasons b/c)", req=True, date_rule="past",
                help=("Use the date of the most recent entry. If you do not remember exactly, give your best date: OG checks it with the passport.", "Usa la fecha de la entrada más reciente. Si no la recuerdas exactamente, da tu mejor fecha: OG la verifica con el pasaporte."))
        mark_block_fields(b, "sb_entry", ["a_entry_date"])
    block_pair(b, "sb_entry", group="entry", form_name="W-7", ctx=None, review_title=("{ap}'s date of entry", "Fecha de entrada de {ap}"), review_desc=("Is this still correct?", "¿Sigue siendo correcta?"),
               edit_title=("Date of entry to the U.S.", "Fecha de entrada a EE. UU."), edit_desc=None, build_edit=edit_entry)

    page(b, "prior_country", ("Where {ap} lived before", "Dónde vivía {ap} antes"), group="entry")
    yn(b, "a_foreign_res", ("Does {ap} still keep a home or residence outside the United States?", "¿{ap} todavía mantiene un hogar o residencia fuera de Estados Unidos?"), opts=YN_UNSURE, ref="W-7 line 3 (foreign address)")
    b.field("a_prior_country", "short_answer", ("Which country did {ap} live in before moving to the United States?", "¿En qué país vivía {ap} antes de mudarse a Estados Unidos?"), ref="W-7 line 3", req=True, maxlen=60,
            help=("OG only asks for the country. If a foreign home remains, OG will ask you for its full address if the IRS needs it.", "OG solo pide el país. Si queda un hogar en el extranjero, OG te pedirá su dirección completa si el IRS la necesita."))

    # ---------------------------------------------------------------- visa
    page(b, "visa", ("The U.S. visa", "La visa de EE. UU."), group="entry")
    b.field("visa_entered", "single_choice", ("Did {ap} enter the United States with a visa?", "¿{ap} entró a Estados Unidos con una visa?"), req=True, ref="W-7 line 6c", opts=YN_UNSURE)
    dyn(b, "visa_card", "w7_visa")
    b.field("visa_class", "short_answer", ("Visa type (for example B-2, F-1, H-4)", "Tipo de visa (por ejemplo B-2, F-1, H-4)"), ref="OG workflow (W-7 line 6c)", width="half", maxlen=20)
    b.field("visa_number", "short_answer", ("Visa number", "Número de la visa"), ref="W-7 line 6c", width="half", maxlen=20, sensitive=True,
            help=("Printed in red on the visa page. If you upload the visa page, you can leave the details blank: OG reads them and asks you to confirm.", "Está impreso en rojo en la página de la visa. Si subes la página de la visa, puedes dejar los datos en blanco: OG los lee y te pide confirmarlos."))
    b.field("visa_expiry", "date", ("Visa expiration date", "Fecha de vencimiento de la visa"), ref="W-7 line 6c", width="half")
    for n in ("visa_card", "visa_class", "visa_number", "visa_expiry"):
        only_if(b, n, ("visa_entered", "equals", "yes"))

    # ---------------------------------------------------------------- ITIN history
    page(b, "itin_history", ("Social Security and earlier ITIN", "Seguro Social e ITIN anterior"), group="itin")
    b.field("ssn_status", "single_choice", ("Does {ap} have, or is {ap} eligible for or applying for, a U.S. Social Security number?", "¿{ap} tiene, es elegible o está solicitando un número de Seguro Social de EE. UU.?"), req=True,
            ref="W-7 top of form (do not file if the applicant has, is eligible for, or applied for an SSN)",
            opts=[("no", "No — none, and not eligible or applying", "No — ninguno, y no es elegible ni lo está solicitando"), ("have", "Yes — already has one", "Sí — ya tiene uno"),
                  ("applied", "Applied for one", "Lo solicitó"), ("unsure", "Not sure", "No estoy seguro(a)")],
            help=(T.SSN_NOTE[0], T.SSN_NOTE[1]))
    b.field("hist_itin", "single_choice", ("Has {ap} ever received an ITIN or an IRS Number (IRSN) before?", "¿{ap} ha recibido antes un ITIN o un Número del IRS (IRSN)?"), req=True, ref="W-7 line 6e",
            opts=[("yes", "Yes", "Sí"), ("no", "No", "No"), ("unsure", "I do not know", "No lo sé")])
    b.field("hist_itin_num", "short_answer", ("ITIN or IRSN received", "ITIN o IRSN recibido"), ref="W-7 line 6f", sensitive=True, maxlen=15, width="half", help=("It is the 9-digit number that starts with 9. Leave it blank if you do not remember.", "Es el número de 9 dígitos que empieza con 9. Déjalo en blanco si no lo recuerdas."))
    b.field("hist_itin_name", "short_answer", ("Name it was issued under (if different)", "Nombre con el que se emitió (si es diferente)"), ref="W-7 line 6f", maxlen=120, width="half")
    b.field("hist_name_changed", "single_choice", ("Has {ap}'s legal name changed since that ITIN was issued?", "¿El nombre legal de {ap} ha cambiado desde que se emitió ese ITIN?"), req=True, ref="W-7 Instructions p. 8 (Line 1a / 6f note: renewal with a legal name change)",
            opts=YN_UNSURE, help=("If it changed, the IRS asks for proof such as a marriage certificate or a court order. OG will ask for a copy.", "Si cambió, el IRS pide una prueba, como un acta de matrimonio o una orden de un tribunal. OG te pedirá una copia."))
    for n in ("hist_itin_num", "hist_itin_name", "hist_name_changed"):
        only_if(b, n, ("hist_itin", "equals", "yes"))
    b.field("a_foreign_tin", "short_answer", ("Foreign tax identification number (only if {ap} has one)", "Número de identificación fiscal extranjero (solo si {ap} tiene uno)"), ref="W-7 line 6b", maxlen=40, sensitive=True,
            help=("Leave it blank if there is none.", "Déjalo en blanco si no tiene."))

    # ---------------------------------------------------------------- spouse / dependent
    page(b, "spouse", ("About the marriage", "Sobre el matrimonio"), group="family")
    para(b, "sp_note", "OG will ask for the marriage certificate (a clear photo is enough for now) to document the marriage for the tax return. Whether the spouse has income of their own is asked on the work page and is not a requirement OG assumes.",
         "OG pedirá el acta de matrimonio (por ahora basta una foto clara) para documentar el matrimonio en la declaración. Si el cónyuge tiene ingresos propios se pregunta en la página de trabajo y no es un requisito que OG dé por hecho.")
    show_page_any(b, "spouse", [[("w_kind", "equals", "spouse")]])

    page(b, "dependent", ("About the dependent", "Sobre el dependiente"), group="family")
    b.field("dep_rel", "short_answer", ("Relationship to the taxpayer (for example son, daughter, stepchild, grandchild)", "Relación con el contribuyente (por ejemplo hijo, hija, hijastro, nieto)"), req=True, ref="W-7 (dependent's relationship)", maxlen=60)
    b.field("dep_student", "single_choice", ("Is {ap} a student?", "¿{ap} es estudiante?"), req=True, ref="W-7 Instructions p. 4 (student photo exception, school record)", opts=YES_NO)
    only_if(b, "dep_student", ("c_student_q", "equals", "yes"))
    b.field("dep_entry_stamp", "single_choice", ("Does the passport show the date {ap} entered the United States (an entry stamp or visa)?", "¿El pasaporte muestra la fecha en que {ap} entró a Estados Unidos (un sello de entrada o visa)?"), req=True,
            ref="W-7 Instructions p. 4 (U.S. residency proof)", opts=YN_UNSURE)
    only_if(b, "dep_entry_stamp", ("pp_status", "equals", "have"))
    only_if(b, "dep_entry_stamp", ("pp_status", "equals", "later"))
    para(b, "res_note", T.RESIDENCY_HELP[0], T.RESIDENCY_HELP[1], "text-[13px] leading-relaxed text-slate-600")
    res_u6 = [("medical_record", "Medical record", "Registro médico"), ("school_record", "School record", "Registro escolar"), ("us_state_id", "U.S. state identification", "Identificación estatal de EE. UU."),
              ("us_visa", "U.S. visa", "Visa de EE. UU."), ("unsure", "Not sure — OG will tell me", "No estoy seguro(a) — OG me dirá")]
    res_617 = [("school_record", "School record", "Registro escolar"), ("us_state_id", "U.S. state identification", "Identificación estatal de EE. UU."), ("us_dl", "U.S. driver's license", "Licencia de conducir de EE. UU."),
               ("us_visa", "U.S. visa", "Visa de EE. UU."), ("unsure", "Not sure — OG will tell me", "No estoy seguro(a) — OG me dirá")]
    res_18 = res_617 + [("us_bank_statement", "U.S. bank statement", "Estado de cuenta bancario de EE. UU."), ("us_rental_statement", "U.S. rental statement", "Recibo o contrato de alquiler de EE. UU."),
                        ("us_utility_bill", "U.S. utility bill", "Factura de servicios de EE. UU.")]
    for name, opts, band in (("res_u6", res_u6, "u6"), ("res_6_17", res_617, "6_17"), ("res_18", res_18, "18plus")):
        b.field(name, "single_choice", ("Which document can show {ap} lives in the U.S.?", "¿Qué documento puede mostrar que {ap} vive en EE. UU.?"), ref="W-7 Instructions p. 4 (dependent U.S. residency evidence by age)", opts=opts,
                help=("Choose the one you can provide most easily.", "Elige el que puedas dar con más facilidad."))
        for extra in (("dep_entry_stamp", "equals", "no"), ("dep_entry_stamp", "equals", "unsure"), ("pp_status", "equals", "none")):
            b.rule("show_field", name, [("c_band", "equals", band), extra])
    show_page_any(b, "dependent", [[("w_kind", "equals", "dependent")]])

    page(b, "taxpayer_id", ("The taxpayer's number", "El número del contribuyente"), group="family")
    b.field("taxpayer_ssn_itin", "short_answer", ("Social Security number or ITIN of the taxpayer (the U.S. citizen or resident who files the return)", "Número de Seguro Social o ITIN del contribuyente (el ciudadano o residente de EE. UU. que presenta la declaración)"),
            ref="W-7 reason d/e (name and SSN/ITIN of the U.S. citizen or resident alien)", maxlen=15, sensitive=True,
            help=("It is only used to prepare this application. Leave it blank if you do not have it with you: OG will ask again.", "Solo se usa para preparar esta solicitud. Déjalo en blanco si no lo tienes a la mano: OG lo pedirá de nuevo."))
    show_page_any(b, "taxpayer_id", [[("c_reason", "equals", "d")], [("c_reason", "equals", "e")]])

    # ---------------------------------------------------------------- work & income (primary and spouse)
    page(b, "work", ("Work and income", "Trabajo e ingresos"), ("Information for OG's tax preparation and the ITIN file. OG does not calculate taxes here.", "Información para la preparación de impuestos de OG y el expediente del ITIN. Aquí OG no calcula impuestos."), group="income")
    b.field("inc_type", "single_choice", ("Did {ap} have income from work in the U.S. during the tax year?", "¿{ap} tuvo ingresos por trabajo en EE. UU. durante el año fiscal?"), req=True, ref="OG workflow (tax return context)",
            opts=[("employee", "Yes — as an employee (received a W-2)", "Sí — como empleado (recibió un W-2)"), ("self", "Yes — self-employed", "Sí — trabajo por cuenta propia"), ("both", "Yes — both", "Sí — ambos"),
                  ("other", "Other income", "Otros ingresos"), ("none", "No income of their own", "Sin ingresos propios"), ("unsure", "Not sure", "No estoy seguro(a)")])
    b.field("inc_w2_ssn", "single_choice", ("Does the W-2 show a Social Security number for {ap}?", "¿El W-2 muestra un número de Seguro Social para {ap}?"), req=True, ref="OG workflow (W-2 taxpayer identifier review)",
            opts=YN_UNSURE, help=(T.W2_REVIEW[0], T.W2_REVIEW[1]))
    show_any(b, "inc_w2_ssn", [[("inc_type", "equals", "employee")], [("inc_type", "equals", "both")]])
    b.field("self_activity", "short_answer", ("What kind of work does {ap} do on their own?", "¿Qué tipo de trabajo hace {ap} por cuenta propia?"), req=True, ref="OG workflow (self-employment)", maxlen=100)
    b.field("self_occupation", "short_answer", ("Occupation", "Ocupación"), req=True, ref="OG workflow (self-employment)", maxlen=80, width="half")
    b.field(GROSS_FIELD[0], "paragraph", ("", ""), content=GROSS_FIELD[1])
    b.field("self_gross", "number", ("Approximate gross income for the year (USD)", "Ingreso bruto aproximado del año (USD)"), req=True, ref="OG workflow (self-employment; not a Schedule C)", minv=0, maxv=99999999, width="half")
    for n in ("self_activity", "self_occupation", GROSS_FIELD[0], "self_gross"):
        show_any(b, n, [[("inc_type", "equals", "self")], [("inc_type", "equals", "both")]])
    b.field("inc_other", "short_answer", ("What other income did {ap} have?", "¿Qué otros ingresos tuvo {ap}?"), req=True, ref="OG workflow", maxlen=120)
    only_if(b, "inc_other", ("inc_type", "equals", "other"))
    show_page_any(b, "work", [[("w_kind", "equals", "primary")], [("w_kind", "equals", "spouse")]])

    # ---------------------------------------------------------------- documents
    page(b, "documents", ("Documents", "Documentos"), DOCS_PAGE_DESC, group="documents")
    dyn(b, "docs_list", "documents")

    # ---------------------------------------------------------------- what happens next
    page(b, "processing", ("What happens next", "Qué sigue"), group="confirm")
    para(b, "proc_text", T.PROCESSING[0], T.PROCESSING[1], "text-[14px] leading-relaxed text-slate-700")
    para(b, "proc_disc", "<strong>OG MULTISERVICES DOES NOT APPROVE OR DENY ITIN APPLICATIONS.</strong> " + T.DISCLAIMER[0],
         "<strong>OG MULTISERVICES NO APRUEBA NI NIEGA SOLICITUDES DE ITIN.</strong> " + T.DISCLAIMER[1], "text-[14px] leading-relaxed text-slate-700")

    # ---------------------------------------------------------------- confirm
    page(b, "confirm", ("Confirm and Send to OG", "Confirma y envía a OG"), ("Review your information and confirm that it is complete and correct as far as you know.", "Revisa tu información y confirma que está completa y correcta hasta donde sabes."), group="confirm")
    para(b, "confirm_note", T.SEND_NOTE[0], T.SEND_NOTE[1], "text-[13px] leading-relaxed text-slate-600")
    b.field("c_prepare", "consent", ("Request for preparation", "Solicitud de preparación"), ref="OG confirmation", req=True, note="Customer confirmation only; not a signature.",
            content=("I ask OG Multiservices to prepare the ITIN application (Form W-7) and the related tax return from the information I gave.", "Solicito a OG Multiservices que prepare la solicitud de ITIN (Formulario W-7) y la declaración de impuestos relacionada con la información que di."))
    b.field("c_accurate", "consent", ("Accuracy confirmation", "Confirmación de exactitud"), ref="OG confirmation", req=True, note="Customer confirmation only; the W-7 is signed separately, never here.",
            content=("I confirm the information is complete and correct to the best of my knowledge. I understand that documents I still owe can be sent later, and that the W-7 is signed only when OG tells me it is ready.",
                     "Confirmo que la información está completa y es correcta según mi leal saber y entender. Entiendo que los documentos que aún debo pueden enviarse después y que el W-7 se firma solo cuando OG me diga que está listo."))
    private(b, "hist_itin_num", "taxpayer_ssn_itin", "visa_number", "a_foreign_tin")
    return b


def _features():
    return {
        "completeness_check": True, "consistency": "w7", "documents_check": True,
        "review_groups": {"passport": {"en": "Review", "es": "Revisar"}}, "review_documents": True,
        "sections": SECTIONS,
        "name_tokens": {"ap": {"role": "itin_applicant", "fallback": {"en": "the applicant", "es": "el solicitante"}}},
        "sync": [{"kind": "w7_calc"}, {"kind": "requirements_w7"}],
    }


def ensure_w7_intake():
    """Create the ITIN / W-7 intake and link it to the existing ITIN Application service (idempotent; never rebuilt over submissions)."""
    if Form.query.filter_by(slug=W7_SLUG).first():
        return False
    category = ServiceCategory.query.filter_by(slug="taxes-itin").first()
    if category is None:
        return False
    service = Service.query.filter_by(category_id=category.id, slug="itin-application").first()
    if service is None:
        return False
    form = Form(slug=W7_SLUG, name_admin="W-7 Client Intake (ITIN)")
    db.session.add(form)
    form.form_type = "service_intake"
    form.status = "published"
    form.source_form_name = SOURCE_NAME
    form.source_edition = SOURCE_EDITION
    form.version = 1
    form.published_at = datetime.utcnow()
    form.title_en, form.title_es = "ITIN Application — Form W-7", "Solicitud de ITIN — Formulario W-7"
    form.description_en = "Guided intake for OG Multiservices to prepare one Form W-7 for one person. Your progress is saved automatically."
    form.description_es = "Solicitud guiada para que OG Multiservices prepare un Formulario W-7 para una persona. Tu progreso se guarda automáticamente."
    form.submit_label_en, form.submit_label_es = "Send to OG", "Enviar a OG"
    form.success_message_en = "OG Multiservices has your information and will review it. This is not a W-7 submission to the IRS. We'll contact you about signatures and any original documents."
    form.success_message_es = "OG Multiservices tiene tu información y la revisará. Esto no es el envío del W-7 al IRS. Te contactaremos sobre las firmas y los documentos originales."
    form.show_progress = True
    form.features_json = json.dumps(_features(), ensure_ascii=False)
    db.session.flush()
    build_w7(form)
    db.session.flush()
    service.requires_intake = True
    service.form_id = form.id
    service.requires_account = True
    service.intake_label = "W-7 Client Intake"
    db.session.commit()
    return True


def ensure_w7_refinements():
    """Apply the customer-wording cleanup IN PLACE to an existing W-7 form (short intro, plain income note, passport page wording). Text and one paragraph only:
    no answer, rule, field type, requirement or form version is touched, so drafts and submissions are unaffected. Idempotent."""
    from app.models import ConditionalRule, FormField, RuleCondition

    form = Form.query.filter_by(slug=W7_SLUG).first()
    if form is None:
        return False
    fields = {f.internal_name: f for f in form.all_fields}
    changed = False
    for name, (en_html, es_html) in INTRO_FIELDS.items():
        f = fields.get(name)
        if f is not None and (f.content_en != en_html or f.content_es != es_html):
            f.content_en, f.content_es = en_html, es_html
            changed = True
    gross = fields.get("self_gross")
    if gross is not None:
        if gross.help_text_en or gross.help_text_es:
            gross.help_text_en = gross.help_text_es = None
            changed = True
        note = fields.get(GROSS_FIELD[0])
        if note is None:
            page = gross.page
            for f in page.fields:
                if f.sort_order >= gross.sort_order:
                    f.sort_order += 1
            note = FormField(page_id=page.id, sort_order=gross.sort_order - 1, field_type="paragraph", internal_name=GROSS_FIELD[0], label_en="", label_es="", required=False, width="full",
                             content_en=GROSS_FIELD[1][0], content_es=GROSS_FIELD[1][1])
            db.session.add(note)
            db.session.flush()
            inc = fields["inc_type"]
            for value in ("self", "both"):
                rule = ConditionalRule(form_id=form.id, sort_order=len(form.rules), match_type="all", action="show_field", target_field_id=note.id)
                db.session.add(rule)
                db.session.flush()
                db.session.add(RuleCondition(rule_id=rule.id, field_id=inc.id, operator="equals", value=value))
                form.rules.append(rule)
            changed = True
        elif note.content_en != GROSS_FIELD[1][0] or note.content_es != GROSS_FIELD[1][1]:
            note.content_en, note.content_es = GROSS_FIELD[1]
            changed = True
    docs = fields.get("docs_list")
    if docs is not None and (docs.page.description_en, docs.page.description_es) != DOCS_PAGE_DESC:
        docs.page.description_en, docs.page.description_es = DOCS_PAGE_DESC
        changed = True
    pp = fields.get("pp_status")
    if pp is not None:
        page = pp.page
        if (page.description_en, page.description_es) != PP_PAGE_DESC:
            page.description_en, page.description_es = PP_PAGE_DESC
            changed = True
        if (pp.help_text_en, pp.help_text_es) != PP_HELP:
            pp.help_text_en, pp.help_text_es = PP_HELP
            changed = True
    if changed:
        db.session.commit()
    return changed
