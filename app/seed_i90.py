"""Form I-90 Client Intake — the first production Smart Intake.

SOURCE OF TRUTH: the USCIS "Form I-90, Application to Replace Permanent Resident
Card", Edition 01/20/25 (OMB No. 1615-0082, expires 02/28/2027), 7 pages, supplied by
OG Multiservices. Every field below carries the Part/Item it comes from in
`FormField.source_ref` (admin-only). Questions, choices and dependencies were read
from that document; nothing was reconstructed from memory.

Not customer questions, on purpose:
  * Part 7 (preparer) — completed by OG as the preparer, not asked of the customer.
  * All signatures/dates (Part 5 item 6, Part 6 item 7, Part 7 item 8) — signed in ink
    on the final form; no e-signature is collected here.
  * "For USCIS Use Only" boxes and the barcode.

Items that are OG additions for a better experience (not USCIS questions) are labelled
"OG helper" in source_ref so they are never mistaken for form items:
  * "Is this address in the United States?" — the form has State/ZIP (U.S.) and
    Province/Postal Code/Country (foreign); the answer only picks which set to show.
  * "Is your physical address different?" — Part 1 Item 7 says to provide it only if
    different from the mailing address.
  * "How were you admitted?" — Part 3 says to complete 3.a/3.a.1 only if you entered
    with an immigrant visa (if adjustment of status, go to item 4).

The USCIS notes that accompany certain items are shown as help text in the customer's
own words of the form, never as an eligibility conclusion.
"""

from datetime import datetime

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
SOURCE_NAME = "I-90"
SOURCE_EDITION = "01/20/25"

STATES = [
    ("AL", "Alabama"), ("AK", "Alaska"), ("AS", "American Samoa"), ("AZ", "Arizona"), ("AR", "Arkansas"),
    ("AA", "Armed Forces Americas"), ("AE", "Armed Forces Europe, Middle East, Africa, Canada"),
    ("AP", "Armed Forces Pacific"), ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"),
    ("DE", "Delaware"), ("DC", "District of Columbia"), ("FL", "Florida"), ("FM", "Federated States of Micronesia"),
    ("GA", "Georgia"), ("GU", "Guam"), ("HI", "Hawaii"), ("ID", "Idaho"), ("IL", "Illinois"), ("IN", "Indiana"),
    ("IA", "Iowa"), ("KS", "Kansas"), ("KY", "Kentucky"), ("LA", "Louisiana"), ("ME", "Maine"),
    ("MH", "Marshall Islands"), ("MD", "Maryland"), ("MA", "Massachusetts"), ("MI", "Michigan"),
    ("MN", "Minnesota"), ("MS", "Mississippi"), ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"),
    ("NV", "Nevada"), ("NH", "New Hampshire"), ("NJ", "New Jersey"), ("NM", "New Mexico"), ("NY", "New York"),
    ("NC", "North Carolina"), ("ND", "North Dakota"), ("MP", "Northern Mariana Islands"), ("OH", "Ohio"),
    ("OK", "Oklahoma"), ("OR", "Oregon"), ("PW", "Palau"), ("PA", "Pennsylvania"), ("PR", "Puerto Rico"),
    ("RI", "Rhode Island"), ("SC", "South Carolina"), ("SD", "South Dakota"), ("TN", "Tennessee"), ("TX", "Texas"),
    ("UT", "Utah"), ("VT", "Vermont"), ("VI", "U.S. Virgin Islands"), ("VA", "Virginia"), ("WA", "Washington"),
    ("WV", "West Virginia"), ("WI", "Wisconsin"), ("WY", "Wyoming"),
]
STATE_OPTIONS = [(code, f"{name} ({code})", f"{name} ({code})") for code, name in STATES]

YES_NO = [("yes", "Yes", "Sí"), ("no", "No", "No")]
UNIT_TYPES = [("apt", "Apt.", "Apto."), ("ste", "Ste.", "Ste."), ("flr", "Flr.", "Piso")]

EYE = [("BLK", "Black", "Negros"), ("BLU", "Blue", "Azules"), ("BRO", "Brown", "Marrones"), ("GRY", "Gray", "Grises"),
       ("GRN", "Green", "Verdes"), ("HAZ", "Hazel", "Color avellana"), ("MAR", "Maroon", "Granate"),
       ("PNK", "Pink", "Rosados"), ("UNK", "Unknown / Other", "Desconocido / Otro")]
HAIR = [("BAL", "Bald (no hair)", "Calvo (sin cabello)"), ("BLK", "Black", "Negro"), ("BLN", "Blond", "Rubio"),
        ("BRO", "Brown", "Castaño"), ("GRY", "Gray", "Gris"), ("RED", "Red", "Pelirrojo"), ("SDY", "Sandy", "Arena"),
        ("WHI", "White", "Blanco"), ("UNK", "Unknown / Other", "Desconocido / Otro")]


class Builder:
    def __init__(self, form):
        self.form = form
        self.page_order = 0
        self.fields = {}
        self.pages = {}
        self.page = None

    def new_page(self, key, title, desc=None):
        p = FormPage(
            form_id=self.form.id, sort_order=self.page_order, title_en=title[0], title_es=title[1],
            description_en=desc[0] if desc else None, description_es=desc[1] if desc else None,
        )
        db.session.add(p)
        db.session.flush()
        self.page_order += 1
        self.pages[key] = p
        self.page = p
        self._order = 0
        return p

    def field(self, name, ftype, label, *, ref=None, req=False, opts=None, help=None, detail=None, pattern=None,
              sensitive=False, date_rule=None, width="full", content=None, files=None, maxlen=None, minv=None,
              maxv=None, note=None, ph=None, msg=None):
        f = FormField(
            page_id=self.page.id, sort_order=self._order, field_type=ftype, internal_name=name,
            label_en=label[0] if label else "", label_es=label[1] if label else "", required=req, width=width,
            source_ref=ref, source_note=note, is_sensitive=sensitive, pattern=pattern, date_rule=date_rule,
            help_text_en=help[0] if help else None, help_text_es=help[1] if help else None,
            help_detail_en=detail[0] if detail else None, help_detail_es=detail[1] if detail else None,
            content_en=content[0] if content else None, content_es=content[1] if content else None,
            max_length=maxlen, min_value=minv, max_value=maxv,
            placeholder_en=ph[0] if ph else None, placeholder_es=ph[1] if ph else None,
            validation_message_en=msg[0] if msg else None, validation_message_es=msg[1] if msg else None,
        )
        if files:
            f.allowed_file_types, f.max_files, f.max_file_size_mb = files
        db.session.add(f)
        db.session.flush()
        self._order += 1
        for i, (value, en, es) in enumerate(opts or []):
            db.session.add(FieldOption(field_id=f.id, sort_order=i, value=value, label_en=en, label_es=es))
        self.fields[name] = f
        return f

    def rule(self, action, target, conditions, match="all"):
        r = ConditionalRule(form_id=self.form.id, sort_order=len(self.form.rules), match_type=match, action=action)
        if action in ("show_page", "skip_page", "goto_page"):
            r.target_page_id = self.pages[target].id
        else:
            r.target_field_id = self.fields[target].id
        db.session.add(r)
        db.session.flush()
        for name, op, value in conditions:
            db.session.add(RuleCondition(rule_id=r.id, field_id=self.fields[name].id, operator=op, value=value))
        self.form.rules.append(r)


def _address_fields(b, prefix, ref, *, required_core=True, us_label=None):
    """Mailing/physical/interpreter address block with the US vs foreign helper."""
    b.field(f"{prefix}_is_us", "single_choice", us_label or ("Is this address in the United States?", "¿Esta dirección está en los Estados Unidos?"),
            ref=f"OG helper ({ref})", note="Chooses State/ZIP Code (U.S.) or Province/Postal Code/Country (foreign).", req=True, opts=YES_NO)
    b.field(f"{prefix}_street", "short_answer", ("Street number and name", "Número y nombre de la calle"), ref=ref + " — Street Number and Name", req=required_core)
    b.field(f"{prefix}_unit_type", "dropdown", ("Unit type (if any)", "Tipo de unidad (si aplica)"), ref=ref + " — Apt./Ste./Flr.", opts=UNIT_TYPES, width="half")
    b.field(f"{prefix}_unit_number", "short_answer", ("Unit number", "Número de unidad"), ref=ref + " — Number", width="half")
    b.field(f"{prefix}_city", "short_answer", ("City or town", "Ciudad o pueblo"), ref=ref + " — City or Town", req=required_core)
    b.field(f"{prefix}_state", "dropdown", ("State", "Estado"), ref=ref + " — State", req=True, opts=STATE_OPTIONS, width="half")
    b.field(f"{prefix}_zip", "short_answer", ("ZIP code", "Código postal (ZIP)"), ref=ref + " — ZIP Code", req=True, width="half", pattern=r"\d{5}", maxlen=5,
            msg=("Enter a 5-digit ZIP code.", "Ingresa un ZIP de 5 dígitos."))
    b.field(f"{prefix}_province", "short_answer", ("Province", "Provincia"), ref=ref + " — Province", width="half")
    b.field(f"{prefix}_postal_code", "short_answer", ("Postal code", "Código postal"), ref=ref + " — Postal Code", width="half")
    b.field(f"{prefix}_country", "short_answer", ("Country", "País"), ref=ref + " — Country", req=True)
    for name in ("state", "zip"):
        b.rule("show_field", f"{prefix}_{name}", [(f"{prefix}_is_us", "equals", "yes")])
    for name in ("province", "postal_code", "country"):
        b.rule("show_field", f"{prefix}_{name}", [(f"{prefix}_is_us", "equals", "no")])


def build_i90(form):
    b = Builder(form)

    # 1 ------------------------------------------------------------- intro
    b.new_page("intro", ("Before you start", "Antes de empezar"))
    b.field("intro_1", "paragraph", ("", ""), content=(
        "This intake collects the information OG Multiservices needs to prepare your Form I-90, Application to Replace Permanent Resident Card (USCIS edition 01/20/25). It takes about 15–20 minutes.",
        "Este formulario reúne la información que OG Multiservices necesita para preparar tu Formulario I-90, Solicitud para reemplazar la Tarjeta de Residente Permanente (edición USCIS 01/20/25). Toma unos 15–20 minutos."))
    b.field("intro_2", "paragraph", ("", ""), content=(
        "Your answers are saved automatically, so you can stop and come back anytime. Have your current card nearby if you still have it. You'll review everything before sending it to OG.",
        "Tus respuestas se guardan automáticamente; puedes parar y volver cuando quieras. Ten a la mano tu tarjeta actual si todavía la tienes. Revisarás todo antes de enviarlo a OG."))
    b.field("intro_3", "paragraph", ("", ""), content=(
        "OG Multiservices provides document preparation and administrative assistance. We are not a law firm and do not provide legal advice or representation. Sending this to OG does not file anything with USCIS.",
        "OG Multiservices ofrece preparación de documentos y asistencia administrativa. No somos un bufete de abogados ni brindamos asesoría o representación legal. Enviar esto a OG no presenta nada ante USCIS."))

    # 2 ------------------------------------------------------------- status (Part 2 item 1)
    b.new_page("status", ("Your status", "Tu estatus"))
    b.field("lpr_status", "single_choice", ("What is your current status?", "¿Cuál es tu estatus actual?"),
            ref="Part 2, Item 1 (1.a–1.c)", req=True,
            help=("Select only one.", "Selecciona solo una."),
            detail=("USCIS note on the form: if your conditional permanent resident status (for example CR1, CR2, CF1, CF2) is expiring within the next 90 days, do not file this application. See the “What is the Purpose of This Application” section of the Form I-90 Instructions for more information.",
                    "Nota de USCIS en el formulario: si tu estatus de residente permanente condicional (por ejemplo CR1, CR2, CF1, CF2) vence dentro de los próximos 90 días, no presentes esta solicitud. Consulta la sección “What is the Purpose of This Application” de las Instrucciones del Formulario I-90."),
            opts=[
                ("lpr", "Lawful Permanent Resident", "Residente Permanente Legal"),
                ("commuter", "Permanent Resident – In Commuter Status", "Residente Permanente – en Estatus de Commuter"),
                ("conditional", "Conditional Permanent Resident", "Residente Permanente Condicional"),
            ])

    # 3 ------------------------------------------------------------- reason (Part 2 item 2 / 3)
    b.new_page("reason", ("Reason for this application", "Motivo de esta solicitud"))
    b.field("reason_a", "single_choice", ("Why are you filing Form I-90?", "¿Por qué presentas el Formulario I-90?"),
            ref="Part 2, Item 2 (Section A)", req=True,
            help=("Select only one.", "Selecciona solo una."),
            detail=("USCIS notes on the form: if you are filing this application before your 14th birthday, or more than 30 days after your 14th birthday, you must select the last option (a prior edition of the card, or a reason not specified above). However, if your card has expired, you must select “already expired or will expire within six months.”",
                    "Notas de USCIS en el formulario: si presentas esta solicitud antes de cumplir 14 años, o más de 30 días después de tu cumpleaños 14, debes elegir la última opción (una edición anterior de la tarjeta o un motivo no especificado arriba). Sin embargo, si tu tarjeta ya venció, debes elegir “ya venció o vencerá dentro de seis meses”."),
            opts=[
                ("lost_stolen_destroyed", "My previous card was lost, stolen, or destroyed", "Mi tarjeta anterior fue perdida, robada o destruida"),
                ("never_received", "My previous card was issued but never received", "Mi tarjeta anterior fue emitida pero nunca la recibí"),
                ("mutilated", "My existing card has been mutilated", "Mi tarjeta actual está mutilada (dañada)"),
                ("dhs_error", "My existing card has incorrect data because of a Department of Homeland Security (DHS) error", "Mi tarjeta actual tiene datos incorrectos por un error del Departamento de Seguridad Nacional (DHS)"),
                ("name_or_bio_changed", "My name or other biographic information has been legally changed since my existing card was issued", "Mi nombre u otra información biográfica ha cambiado legalmente desde que se emitió mi tarjeta actual"),
                ("expired_or_expiring", "My existing card has already expired or will expire within six months", "Mi tarjeta actual ya venció o vencerá dentro de seis meses"),
                ("age14_expires_after_16", "I have reached my 14th birthday and am registering as required; my existing card will expire AFTER my 16th birthday", "Cumplí 14 años y me estoy registrando como se requiere; mi tarjeta actual vencerá DESPUÉS de mi cumpleaños 16"),
                ("age14_expires_before_16", "I have reached my 14th birthday and am registering as required; my existing card will expire BEFORE my 16th birthday", "Cumplí 14 años y me estoy registrando como se requiere; mi tarjeta actual vencerá ANTES de mi cumpleaños 16"),
                ("taking_up_commuter", "I am a permanent resident who is taking up commuter status", "Soy residente permanente y voy a adoptar el estatus de commuter"),
                ("commuter_taking_residence", "I am a commuter who is taking up actual residence in the United States", "Soy commuter y voy a establecer residencia real en los Estados Unidos"),
                ("auto_converted", "I have been automatically converted to lawful permanent resident status", "Fui convertido(a) automáticamente a residente permanente legal"),
                ("other_or_prior_edition", "I have a prior edition of the Alien Registration Card, or I am applying to replace my current Permanent Resident Card for a reason that is not specified above", "Tengo una edición anterior de la Tarjeta de Registro de Extranjero, o solicito reemplazar mi tarjeta actual por un motivo no especificado arriba"),
            ])
    b.field("reason_b", "single_choice", ("Why are you filing Form I-90?", "¿Por qué presentas el Formulario I-90?"),
            ref="Part 2, Item 3 (Section B)", req=True, help=("Select only one.", "Selecciona solo una."),
            opts=[
                ("cond_lost_stolen_destroyed", "My previous card was lost, stolen, or destroyed", "Mi tarjeta anterior fue perdida, robada o destruida"),
                ("cond_never_received", "My previous card was issued but never received", "Mi tarjeta anterior fue emitida pero nunca la recibí"),
                ("cond_mutilated", "My existing card has been mutilated", "Mi tarjeta actual está mutilada (dañada)"),
                ("cond_dhs_error", "My existing card has incorrect data because of a DHS error", "Mi tarjeta actual tiene datos incorrectos por un error del DHS"),
                ("cond_name_or_bio_changed", "My name or other biographic information has legally changed since the issuance of my existing card", "Mi nombre u otra información biográfica ha cambiado legalmente desde que se emitió mi tarjeta actual"),
            ])
    b.rule("show_field", "reason_a", [("lpr_status", "equals", "lpr"), ("lpr_status", "equals", "commuter")], "any")
    b.rule("show_field", "reason_b", [("lpr_status", "equals", "conditional")])

    # 4 ------------------------------------------------------------- commuter port of entry (conditional page)
    b.new_page("commuter", ("Commuter details", "Detalles de commuter"))
    b.field("commuter_poe", "short_answer", ("My port of entry (POE) into the United States will be (city or town and state)", "Mi puerto de entrada (POE) a los Estados Unidos será (ciudad o pueblo y estado)"),
            ref="Part 2, Item 2.h.1.a", req=True)
    b.rule("show_page", "commuter", [("reason_a", "equals", "taking_up_commuter")])

    # 5 ------------------------------------------------------------- your name (Part 1 items 3, 4, 5)
    b.new_page("name", ("Your name", "Tu nombre"), ("Your card will be issued in this name.", "Tu tarjeta se emitirá con este nombre."))
    b.field("name_family", "short_answer", ("Family name (last name)", "Apellido"), ref="Part 1, Item 3.a", req=True, width="half")
    b.field("name_given", "short_answer", ("Given name (first name)", "Nombre(s)"), ref="Part 1, Item 3.b", req=True, width="half")
    b.field("name_middle", "short_answer", ("Middle name", "Segundo nombre"), ref="Part 1, Item 3.c", width="half")

    b.new_page("name_changed", ("Name change", "Cambio de nombre"))
    b.field("name_changed", "single_choice", ("Has your name legally changed since the issuance of your Permanent Resident Card?", "¿Tu nombre cambió legalmente desde que se emitió tu Tarjeta de Residente Permanente?"),
            ref="Part 1, Item 4", req=True,
            opts=[("yes", "Yes", "Sí"), ("no", "No", "No"), ("never_received", "N/A – I never received my previous card", "N/A – Nunca recibí mi tarjeta anterior")])

    b.new_page("prev_name", ("Name on your current card", "Nombre en tu tarjeta actual"),
               ("Provide your name exactly as it is printed on your current Permanent Resident Card.", "Escribe tu nombre exactamente como aparece impreso en tu Tarjeta de Residente Permanente actual."))
    b.field("prev_family", "short_answer", ("Family name (last name)", "Apellido"), ref="Part 1, Item 5.a", req=True, width="half")
    b.field("prev_given", "short_answer", ("Given name (first name)", "Nombre(s)"), ref="Part 1, Item 5.b", req=True, width="half")
    b.field("prev_middle", "short_answer", ("Middle name", "Segundo nombre"), ref="Part 1, Item 5.c", width="half")
    b.field("prev_note", "paragraph", ("", ""), content=("USCIS note on the form: attach all evidence of your legal name change with this application. You can upload it in the Documents step.",
                                                          "Nota de USCIS en el formulario: adjunta toda la evidencia de tu cambio legal de nombre con esta solicitud. Puedes subirla en el paso de Documentos."))
    b.rule("show_page", "prev_name", [("name_changed", "equals", "yes")])

    # 8 ------------------------------------------------------------- identification numbers
    b.new_page("ids", ("Identification numbers", "Números de identificación"))
    b.field("a_number", "short_answer", ("Alien Registration Number (A-Number)", "Número de Registro de Extranjero (Número A)"), ref="Part 1, Item 1", req=True, pattern=r"A?-?\d{7,9}", maxlen=12,
            help=("It looks like A-123456789. Enter the digits.", "Se ve como A-123456789. Escribe los dígitos."),
            msg=("Enter your A-Number: 7 to 9 digits, with or without “A-”.", "Ingresa tu Número A: 7 a 9 dígitos, con o sin “A-”."), sensitive=True)
    b.field("uscis_account", "short_answer", ("USCIS Online Account Number (if any)", "Número de cuenta en línea de USCIS (si tienes)"), ref="Part 1, Item 2", maxlen=12,
            pattern=r"\d{1,12}", msg=("Use digits only (up to 12).", "Usa solo dígitos (hasta 12)."))
    b.field("ssn", "short_answer", ("U.S. Social Security Number (if any)", "Número de Seguro Social de EE. UU. (si tienes)"), ref="Part 1, Item 16", sensitive=True, pattern=r"\d{3}-?\d{2}-?\d{4}",
            help=("Only if you have one. It is private and protected.", "Solo si tienes uno. Es privado y está protegido."),
            msg=("Enter 9 digits.", "Ingresa 9 dígitos."))

    b.new_page("admission", ("Your admission", "Tu admisión"))
    b.field("class_of_admission", "short_answer", ("Class of Admission", "Clase de admisión"), ref="Part 1, Item 14", width="half",
            help=("For example IR1, CR6, F24. Check your card if you still have it.", "Por ejemplo IR1, CR6, F24. Revisa tu tarjeta si todavía la tienes."))
    b.field("date_of_admission", "date", ("Date of admission", "Fecha de admisión"), ref="Part 1, Item 15", width="half", date_rule="past")

    # 10 ------------------------------------------------------------- mailing address (Part 1 item 6)
    b.new_page("mailing", ("Mailing address", "Dirección postal"), ("Where should USCIS mail things to you?", "¿A dónde deben enviarte el correo?"))
    b.field("mail_in_care_of", "short_answer", ("In care of name (if any)", "A cargo de (si aplica)"), ref="Part 1, Item 6.a")
    _address_fields(b, "mail", "Part 1, Item 6")

    b.new_page("phys_gate", ("Physical address", "Dirección física"))
    b.field("phys_different", "single_choice", ("Is your physical address different from your mailing address?", "¿Tu dirección física es diferente a tu dirección postal?"),
            ref="OG helper (Part 1, Item 7)", note="Form says: provide this information only if different than mailing address.", req=True, opts=YES_NO)

    b.new_page("physical", ("Your physical address", "Tu dirección física"))
    _address_fields(b, "phys", "Part 1, Item 7")
    b.rule("show_page", "physical", [("phys_different", "equals", "yes")])

    # 13 ------------------------------------------------------------- about you
    b.new_page("about", ("About you", "Sobre ti"))
    b.field("sex", "single_choice", ("Sex", "Sexo"), ref="Part 1, Item 8", req=True, opts=[("male", "Male", "Masculino"), ("female", "Female", "Femenino")])
    b.field("dob", "date", ("Date of birth", "Fecha de nacimiento"), ref="Part 1, Item 9", req=True, date_rule="past", width="half")
    b.field("birth_city", "short_answer", ("City / town / village of birth", "Ciudad / pueblo / aldea de nacimiento"), ref="Part 1, Item 10", req=True, width="half")
    b.field("birth_country", "short_answer", ("Country of birth", "País de nacimiento"), ref="Part 1, Item 11", req=True)

    b.new_page("parents", ("Your parents", "Tus padres"), ("If you don't know, leave it blank — you can tell us in the last step.", "Si no lo sabes, déjalo en blanco; puedes decírnoslo en el último paso."))
    b.field("mother_given", "short_answer", ("Mother's given name (first name)", "Nombre de tu madre (primer nombre)"), ref="Part 1, Item 12", width="half")
    b.field("father_given", "short_answer", ("Father's given name (first name)", "Nombre de tu padre (primer nombre)"), ref="Part 1, Item 13", width="half")

    # 15 ------------------------------------------------------------- processing (Part 3)
    b.new_page("route", ("How you became a permanent resident", "Cómo obtuviste la residencia permanente"))
    b.field("admission_route", "single_choice", ("How were you admitted as a permanent resident?", "¿Cómo fuiste admitido(a) como residente permanente?"),
            ref="OG helper (Part 3, Items 3.a / 3.a.1)", note="Form says: complete 3.a and 3.a.1 only if you entered with an immigrant visa; if adjustment of status was granted, go to Item 4.", req=True,
            opts=[("immigrant_visa", "I entered the United States with an immigrant visa", "Entré a los Estados Unidos con una visa de inmigrante"),
                  ("adjustment", "I was granted adjustment of status", "Me concedieron el ajuste de estatus")])

    b.new_page("where", ("Where it happened", "Dónde ocurrió"))
    b.field("loc_applied", "short_answer", ("Location where you applied for an immigrant visa or adjustment of status", "Lugar donde solicitaste una visa de inmigrante o el ajuste de estatus"), ref="Part 3, Item 1", req=True)
    b.field("loc_issued", "short_answer", ("Location where your immigrant visa was issued, or the USCIS office where you were granted adjustment of status", "Lugar donde se emitió tu visa de inmigrante, u oficina de USCIS donde te concedieron el ajuste de estatus"), ref="Part 3, Item 2", req=True)

    b.new_page("arrival", ("Your arrival in the U.S.", "Tu llegada a EE. UU."))
    b.field("dest_us", "short_answer", ("Destination in the United States at time of admission", "Destino en los Estados Unidos al momento de la admisión"), ref="Part 3, Item 3.a", req=True)
    b.field("port_of_entry", "short_answer", ("Port of entry where admitted to the United States (city or town and state)", "Puerto de entrada donde fuiste admitido(a) a los Estados Unidos (ciudad o pueblo y estado)"), ref="Part 3, Item 3.a.1", req=True)
    b.rule("show_page", "arrival", [("admission_route", "equals", "immigrant_visa")])

    b.new_page("history", ("Immigration history", "Historial migratorio"), ("Two short questions. If you answer Yes to either, you'll be asked to explain.", "Dos preguntas breves. Si respondes Sí a alguna, te pediremos que la expliques."))
    b.field("removal_proceedings", "single_choice", ("Have you ever been in exclusion, deportation, or removal proceedings or ordered removed from the United States?", "¿Alguna vez has estado en procedimientos de exclusión, deportación o remoción, o se te ha ordenado la remoción de los Estados Unidos?"),
            ref="Part 3, Item 4", req=True, opts=YES_NO)
    b.field("abandoned_status", "single_choice", ("Since you were granted permanent residence, have you ever filed Form I-407, Abandonment by Alien of Status as Lawful Permanent Resident, or otherwise been determined to have abandoned your status?", "Desde que se te concedió la residencia permanente, ¿alguna vez presentaste el Formulario I-407, Abandono del estatus de residente permanente legal, o se determinó de otra forma que abandonaste tu estatus?"),
            ref="Part 3, Item 5", req=True, opts=YES_NO)

    b.new_page("history_explain", ("Tell us more", "Cuéntanos más"))
    b.field("history_explanation", "long_answer", ("Please explain your answer(s) in detail", "Explica tus respuestas con detalle"),
            ref="Part 3 NOTE / Part 8", note="Form says: if Yes to Item 4 or 5, provide a detailed explanation in Part 8. Additional Information.", req=True)
    b.rule("show_page", "history_explain", [("removal_proceedings", "equals", "yes"), ("abandoned_status", "equals", "yes")], "any")

    b.new_page("ethnicity", ("Ethnicity and race", "Etnia y raza"))
    b.field("ethnicity", "single_choice", ("Ethnicity", "Etnia"), ref="Part 3, Item 6", req=True, help=("Select only one.", "Selecciona solo una."),
            opts=[("hispanic", "Hispanic or Latino", "Hispano o Latino"), ("not_hispanic", "Not Hispanic or Latino", "No hispano ni latino")])
    b.field("race", "multi_choice", ("Race", "Raza"), ref="Part 3, Item 7", req=True, help=("Select all that apply.", "Selecciona todas las que apliquen."),
            opts=[("white", "White", "Blanca"), ("asian", "Asian", "Asiática"), ("black", "Black or African American", "Negra o afroamericana"),
                  ("american_indian", "American Indian or Alaska Native", "Indígena americana o nativa de Alaska"),
                  ("pacific_islander", "Native Hawaiian or Other Pacific Islander", "Nativa de Hawái u otra isla del Pacífico")])

    b.new_page("physical_desc", ("Physical description", "Descripción física"))
    b.field("height_feet", "dropdown", ("Height — feet", "Estatura — pies"), ref="Part 3, Item 8", req=True, width="half", opts=[(str(n), str(n), str(n)) for n in range(2, 9)])
    b.field("height_inches", "dropdown", ("Height — inches", "Estatura — pulgadas"), ref="Part 3, Item 8", req=True, width="half", opts=[(str(n), str(n), str(n)) for n in range(0, 12)])
    b.field("weight_lbs", "number", ("Weight (pounds)", "Peso (libras)"), ref="Part 3, Item 9", req=True, minv=1, maxv=999, width="half")
    b.field("eye_color", "dropdown", ("Eye color", "Color de ojos"), ref="Part 3, Item 10", req=True, opts=EYE, width="half")
    b.field("hair_color", "dropdown", ("Hair color", "Color de cabello"), ref="Part 3, Item 11", req=True, opts=HAIR, width="half")

    # 22 ------------------------------------------------------------- accommodations (Part 4)
    b.new_page("accommodations", ("Accommodations", "Adaptaciones"),
               ("USCIS offers accommodations for individuals with disabilities and/or impairments. This is optional.", "USCIS ofrece adaptaciones para personas con discapacidades o impedimentos. Esto es opcional."))
    b.field("accommodation_request", "single_choice", ("Are you requesting an accommodation because of your disabilities and/or impairments?", "¿Solicitas una adaptación debido a tus discapacidades o impedimentos?"),
            ref="Part 4, Item 1", req=True, opts=YES_NO)
    b.field("accommodation_types", "multi_choice", ("Select any that apply", "Selecciona las que apliquen"), ref="Part 4, Items 1.a–1.c", req=True,
            opts=[("deaf", "I am deaf or hard of hearing and request an accommodation", "Soy sordo(a) o con dificultad auditiva y solicito una adaptación"),
                  ("blind", "I am blind or have low vision and request an accommodation", "Soy ciego(a) o tengo baja visión y solicito una adaptación"),
                  ("other", "I have another type of disability and/or impairment", "Tengo otro tipo de discapacidad o impedimento")])
    b.field("accommodation_deaf_detail", "long_answer", ("Which accommodation? (If you need a sign-language interpreter, tell us which language, for example American Sign Language.)", "¿Qué adaptación? (Si necesitas intérprete de lenguaje de señas, indica el idioma, por ejemplo Lengua de Señas Americana.)"), ref="Part 4, Item 1.a", req=True)
    b.field("accommodation_blind_detail", "long_answer", ("Which accommodation do you request?", "¿Qué adaptación solicitas?"), ref="Part 4, Item 1.b", req=True)
    b.field("accommodation_other_detail", "long_answer", ("Describe the nature of your disability and/or impairment and the accommodation you are requesting", "Describe la naturaleza de tu discapacidad o impedimento y la adaptación que solicitas"), ref="Part 4, Item 1.c", req=True)
    b.rule("show_field", "accommodation_types", [("accommodation_request", "equals", "yes")])
    b.rule("show_field", "accommodation_deaf_detail", [("accommodation_types", "selected", "deaf")])
    b.rule("show_field", "accommodation_blind_detail", [("accommodation_types", "selected", "blind")])
    b.rule("show_field", "accommodation_other_detail", [("accommodation_types", "selected", "other")])

    # 23 ------------------------------------------------------------- contact + language (Part 5)
    b.new_page("contact", ("Your contact information", "Tu información de contacto"))
    b.field("phone_daytime", "phone", ("Daytime telephone number", "Teléfono de día"), ref="Part 5, Item 3", req=True, width="half")
    b.field("phone_mobile", "phone", ("Mobile telephone number (if any)", "Teléfono móvil (si tienes)"), ref="Part 5, Item 4", width="half")
    b.field("contact_email", "email", ("Email address (if any)", "Correo electrónico (si tienes)"), ref="Part 5, Item 5")
    b.fields["contact_email"].required = False

    b.new_page("language", ("Language", "Idioma"))
    b.field("english_or_interpreter", "single_choice", ("Which of these is true for you?", "¿Cuál de estas opciones es cierta para ti?"), ref="Part 5, Item 1.a / 1.b", req=True,
            opts=[("english", "I can read and understand English, and I have read and understand every question and instruction on this application and my answer to every question.",
                   "Puedo leer y entender inglés, y he leído y entendido cada pregunta e instrucción de esta solicitud y mi respuesta a cada pregunta."),
                  ("interpreter", "An interpreter read to me every question and instruction on this application and my answer to every question in a language in which I am fluent, and I understood everything.",
                   "Un intérprete me leyó cada pregunta e instrucción de esta solicitud y mi respuesta a cada pregunta en un idioma en el que soy fluido(a), y lo entendí todo.")])
    b.field("interpreter_language", "short_answer", ("Language the interpreter used", "Idioma que usó el intérprete"), ref="Part 5, Item 1.b (language)", req=True)
    b.rule("show_field", "interpreter_language", [("english_or_interpreter", "equals", "interpreter")])

    b.new_page("interp_who", ("Your interpreter", "Tu intérprete"), ("Information about the interpreter (Part 6 of the form).", "Información del intérprete (Parte 6 del formulario)."))
    b.field("int_family", "short_answer", ("Interpreter's family name (last name)", "Apellido del intérprete"), ref="Part 6, Item 1.a", req=True, width="half")
    b.field("int_given", "short_answer", ("Interpreter's given name (first name)", "Nombre del intérprete"), ref="Part 6, Item 1.b", req=True, width="half")
    b.field("int_org", "short_answer", ("Interpreter's business or organization name (if any)", "Empresa u organización del intérprete (si aplica)"), ref="Part 6, Item 2")
    b.field("int_phone", "phone", ("Interpreter's daytime telephone number", "Teléfono de día del intérprete"), ref="Part 6, Item 4", req=True, width="half")
    b.field("int_mobile", "phone", ("Interpreter's mobile telephone number (if any)", "Teléfono móvil del intérprete (si tiene)"), ref="Part 6, Item 5", width="half")
    b.field("int_email", "email", ("Interpreter's email address (if any)", "Correo electrónico del intérprete (si tiene)"), ref="Part 6, Item 6")
    b.fields["int_email"].required = False
    b.rule("show_page", "interp_who", [("english_or_interpreter", "equals", "interpreter")])

    b.new_page("interp_addr", ("Interpreter's mailing address", "Dirección postal del intérprete"))
    _address_fields(b, "int", "Part 6, Item 3")
    b.rule("show_page", "interp_addr", [("english_or_interpreter", "equals", "interpreter")])

    # 27 ------------------------------------------------------------- documents
    b.new_page("documents", ("Documents", "Documentos"), ("Upload what you have now. You can add more before you submit.", "Sube lo que tengas ahora. Puedes agregar más antes de enviar."))
    b.field("evidence_name_change", "file_upload", ("Evidence of your legal name change", "Evidencia de tu cambio legal de nombre"), ref="Part 1, Item 4 NOTE", note="Form says: attach all evidence of your legal name change.",
            help=("USCIS asks you to attach all evidence of your legal name change with this application.", "USCIS pide adjuntar toda la evidencia de tu cambio legal de nombre con esta solicitud."),
            files=("pdf,jpg,jpeg,png", 5, 10))
    b.field("evidence_card_error", "file_upload", ("Your existing card with the incorrect data", "Tu tarjeta actual con los datos incorrectos"), ref="Part 2, Items 2.d / 3.d", note="Form says: attach your existing card with incorrect data.",
            help=("USCIS asks you to attach your existing card with the incorrect data along with this application. Upload a clear copy of the front and back.", "USCIS pide adjuntar tu tarjeta actual con los datos incorrectos. Sube una copia clara del frente y del reverso."),
            files=("pdf,jpg,jpeg,png", 2, 10))
    b.field("documents_other", "file_upload", ("Other supporting documents (optional)", "Otros documentos de apoyo (opcional)"), ref="OG addition", note="Optional supporting documents; not a USCIS item.",
            help=("Anything else you think will help us prepare your application.", "Cualquier otra cosa que creas que nos ayude a preparar tu solicitud."),
            files=("pdf,jpg,jpeg,png", 10, 10))
    b.rule("show_field", "evidence_name_change", [("name_changed", "equals", "yes")])
    b.rule("show_field", "evidence_card_error", [("reason_a", "equals", "dhs_error"), ("reason_b", "equals", "cond_dhs_error")], "any")

    b.new_page("additional", ("Anything else?", "¿Algo más?"))
    b.field("additional_information", "long_answer", ("Is there anything else you want us to know?", "¿Hay algo más que quieras que sepamos?"), ref="Part 8. Additional Information",
            help=("If something didn't fit any question, tell us here. If it relates to a specific question, say which one.", "Si algo no encajó en ninguna pregunta, cuéntanoslo aquí. Si se relaciona con una pregunta específica, dinos cuál."))

    b.new_page("confirm", ("Confirm and send to OG", "Confirma y envía a OG"))
    b.field("confirm_note", "paragraph", ("", ""), content=(
        "Form I-90 must be signed by you in ink. We do not collect a signature here — OG will prepare your documents and guide you through signing.",
        "El Formulario I-90 debe ser firmado por ti con tinta. Aquí no recopilamos una firma: OG preparará tus documentos y te guiará para firmar."))
    b.field("preparer_request", "consent", ("Request for preparation", "Solicitud de preparación"), ref="Part 5, Item 2", note="Preparer prepared the application at the applicant's request.", req=True, content=(
        "I ask OG Multiservices to prepare my Form I-90 for me, based only on the information I provide or authorize.",
        "Le pido a OG Multiservices que prepare mi Formulario I-90, basándose solo en la información que yo proporcione o autorice."))
    b.field("confirm_accurate", "consent", ("Accuracy confirmation", "Confirmación de exactitud"), ref="Part 5, Certification", note="Customer confirmation only; not a signature.", req=True, content=(
        "I confirm that the information I entered is complete, true, and correct to the best of my knowledge.",
        "Confirmo que la información que ingresé es completa, verdadera y correcta según mi mejor conocimiento."))
    return b


def ensure_i90_intake():
    """Create (or, if it is still the empty shell, rebuild) the production I-90 intake."""
    service = (
        Service.query.join(ServiceCategory)
        .filter(ServiceCategory.slug == "immigration", Service.slug == "green-card-renewal")
        .first()
    )
    if not service:
        return False
    form = Form.query.filter_by(slug=I90_SLUG).first()
    if form and form.source_edition:
        return False  # already the production intake (or a later version of it)
    if form:
        if form.submissions:
            return False  # never rebuild under real submissions
        # Delete rules (and, via cascade, their RuleCondition rows, which reference
        # FormField.id) BEFORE deleting the pages/fields themselves, with a flush in
        # between. Deleting pages first (cascading to FormField) risks a mid-loop
        # autoflush — triggered by SQLAlchemy lazily loading a later page's/rule's
        # collection while cascading — reaching the database before the RuleCondition
        # rows that still reference those fields have been removed. PostgreSQL always
        # enforces that foreign key; SQLite does not unless PRAGMA foreign_keys=ON is
        # set, which this project's engine never issues, so the ordering bug was
        # invisible in development. See Production deployment blocker, 2026-09-23.
        for rule in list(form.rules):
            db.session.delete(rule)
        db.session.flush()
        for page in list(form.pages):
            db.session.delete(page)
        db.session.flush()
        db.session.expire(form)
    else:
        form = Form(slug=I90_SLUG, name_admin="I-90 Client Intake")
        db.session.add(form)
    form.name_admin = "I-90 Client Intake"
    form.form_type = "service_intake"
    form.status = "published"
    form.source_form_name = SOURCE_NAME
    form.source_edition = SOURCE_EDITION
    form.version = 1
    form.published_at = datetime.utcnow()
    form.title_en, form.title_es = "Green Card Renewal — Form I-90", "Renovación de Green Card — Formulario I-90"
    form.description_en = "Guided intake for OG Multiservices to prepare your Form I-90. Your progress is saved automatically."
    form.description_es = "Solicitud guiada para que OG Multiservices prepare tu Formulario I-90. Tu progreso se guarda automáticamente."
    form.submit_label_en, form.submit_label_es = "Submit to OG", "Enviar a OG"
    form.success_message_en = "OG Multiservices has your information and will review it. We'll contact you if we need anything else."
    form.success_message_es = "OG Multiservices tiene tu información y la revisará. Te contactaremos si necesitamos algo más."
    form.show_progress = True
    db.session.flush()
    build_i90(form)
    service.requires_intake = True
    service.form_id = form.id
    service.requires_account = True
    service.intake_label = "I-90 Client Intake"
    db.session.commit()
    return True


# Services whose intake is planned but whose questions have NOT been built. They get a
# label so the admin shows "NOT YET CONFIGURED"; with no form attached, has_intake is
# False and the public Get Started button never routes to an unfinished form.
PREPARED_INTAKES = {
    "naturalization-citizenship": "N-400 Client Intake",
    "i-130-petition": "I-130 Client Intake",
}


def ensure_prepared_intakes():
    changed = False
    for slug, label in PREPARED_INTAKES.items():
        svc = Service.query.filter_by(slug=slug).first()
        if svc and not svc.intake_label and not svc.form_id:
            svc.intake_label = label
            changed = True
    if changed:
        db.session.commit()
    return changed
