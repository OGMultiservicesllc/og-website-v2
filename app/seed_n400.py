"""Form N-400 Client Intake — the second production Smart Intake.

SOURCE OF TRUTH: the supplied USCIS "Form N-400, Application for Naturalization",
Edition 01/20/25 (OMB No. 1615-0052, expires 02/28/2027), 14 pages. Every question
below carries the Part/Item it maps to in `FormField.source_ref` (admin-only), and
the question wording follows the printed form. Customer-friendly help text only
EXPLAINS an item; it never changes what is asked.

Deliberately not customer questions:
  * Signatures and dates (Part 11 item 4, Part 12 item 6, Part 13 item 6, Part 15, Part 16):
    OG guides the required signature depending on how the case is filed.
  * Part 13 (preparer): completed by OG.
  * Part 15 / Part 16 (interview signature, oath): "Do not complete until the USCIS officer
    instructs you". The oath text is shown as reading material for Part 9 item 32.
  * The "For USCIS Use Only" boxes.

How the paper form's tables became guided builders (all reusable, see intake_records.py):
  Part 4  item 1  Physical addresses (last 5 years)  -> address history builder
  Part 7  item 1  Employment / schools (last 5 years) -> work & school history builder
  Part 8  item 1  Trips outside the U.S. (last 5 years) -> travel history builder
  Part 6  item 2  Children table -> repeatable records
  Part 2  item 2  Other names -> repeatable records
  Part 9  item 15 Offense table -> repeatable records

Period covered: the form says "the last 5 years if you are filing based on the general
provision" and refers to the Instructions for the other filing options. The supplied PDF
does not contain those Instructions, so the builders always collect the last 5 years and the
step says OG will confirm the exact period for the customer's filing option.

Items that are OG additions (not USCIS questions) say "OG helper" / "OG addition".
"""

import json
from datetime import datetime

from app.extensions import db
from app.models import Form, Service, ServiceCategory
from app.n400_data import OFFICES
from app.seed_i90 import EYE, HAIR, STATE_OPTIONS, YES_NO, Builder, _address_fields  # noqa: F401

N400_SLUG = "n-400-client-intake"
SOURCE_NAME = "N-400"
SOURCE_EDITION = "01/20/25"

SECTIONS = [
    {"key": "personal", "title": {"en": "Personal Information", "es": "Información personal"}},
    {"key": "address", "title": {"en": "Mailing Address", "es": "Dirección postal"}},
    {"key": "residence", "title": {"en": "Residence History", "es": "Historial de residencia"}},
    {"key": "employment", "title": {"en": "Employment & Education History", "es": "Historial de empleo y estudios"}},
    {"key": "travel", "title": {"en": "Travel History", "es": "Historial de viajes"}},
    {"key": "family", "title": {"en": "Family Information", "es": "Información familiar"}},
    {"key": "additional", "title": {"en": "Additional Questions", "es": "Preguntas adicionales"}},
    {"key": "contact", "title": {"en": "Contact & Interpreter", "es": "Contacto e intérprete"}},
    {"key": "documents", "title": {"en": "Documents", "es": "Documentos"}},
    {"key": "confirm", "title": {"en": "Confirmation", "es": "Confirmación"}},
]

RECORD_INTRO_PERIOD = (
    "The form asks for the last 5 years if you are filing under the general provision. For other filing options, USCIS's Instructions set the period; "
    "we collect the last 5 years and OG will confirm what applies to you.",
    "El formulario pide los últimos 5 años si presentas bajo la disposición general. Para otras opciones, las Instrucciones de USCIS fijan el período; "
    "recopilamos los últimos 5 años y OG confirmará lo que aplica en tu caso.",
)


def T(en, es):
    return (en, es)


def _cfg(**kw):
    return json.dumps(kw, ensure_ascii=False)


def new_page(b, key, title, desc=None, group=None):
    p = b.new_page(key, title, desc)
    p.group_key = group
    return p


def show_any(b, target, groups):
    """Show `target` (a field name) when ANY of the AND-groups of conditions holds."""
    for conds in groups:
        b.rule("show_field", target, conds, "all")


def show_page_any(b, key, groups):
    for conds in groups:
        b.rule("show_page", key, conds, "all")


def yesno(b, name, ref, en, es, *, req=True, help=None, detail=None, explain=None, note=None):
    """A Yes/No question; `explain` adds a required follow-up (Part 14 explanation) when Yes."""
    b.field(name, "single_choice", (en, es), ref=ref, req=req, opts=YES_NO, help=help, detail=detail, note=note)
    if explain:
        item = explain if isinstance(explain, str) else ref
        b.field(f"{name}_explain", "long_answer", ("Please explain your answer", "Explica tu respuesta"), ref=f"Part 14 (explanation for {item})", req=True,
                help=("This becomes your explanation in Additional Information (Part 14) of the form. Say what happened, when, and where.",
                      "Esto se convierte en tu explicación en Información adicional (Parte 14) del formulario. Cuenta qué pasó, cuándo y dónde."))
        b.rule("show_field", f"{name}_explain", [(name, "equals", "yes")])


def intro(b, name, en, es):
    b.field(name, "paragraph", ("", ""), content=(f'<span class="text-[15px] font-semibold text-brand-800">{en}</span>', f'<span class="text-[15px] font-semibold text-brand-800">{es}</span>'))


def note(b, name, en, es):
    b.field(name, "paragraph", ("", ""), content=(f'<span class="text-[13px] text-slate-500">{en}</span>', f'<span class="text-[13px] text-slate-500">{es}</span>'))


OATH_EN = ("I hereby declare on oath, that I absolutely and entirely renounce and abjure all allegiance and fidelity to any foreign prince, potentate, state, or "
           "sovereignty, of whom or which I have heretofore been a subject or citizen; that I will support and defend the Constitution and laws of the United States "
           "of America against all enemies, foreign, and domestic; that I will bear true faith and allegiance to the same; that I will bear arms on behalf of the "
           "United States when required by the law; that I will perform noncombatant service in the armed forces of the United States when required by the law; "
           "that I will perform work of national importance under civilian direction when required by the law; and that I take this obligation freely, without any "
           "mental reservation or purpose of evasion; so help me God.")
OATH_ES = ("Traducción de cortesía; el texto oficial es el que aparece en inglés en el formulario. Declaro bajo juramento que renuncio absoluta y enteramente a toda "
           "lealtad y fidelidad a cualquier príncipe, potentado, estado o soberanía extranjera de quien o del cual haya sido hasta ahora súbdito o ciudadano; que apoyaré y "
           "defenderé la Constitución y las leyes de los Estados Unidos de América contra todo enemigo, extranjero y doméstico; que tendré verdadera fe y lealtad a las mismas; "
           "que portaré armas en nombre de los Estados Unidos cuando la ley lo exija; que prestaré servicio no combatiente en las fuerzas armadas de los Estados Unidos cuando la "
           "ley lo exija; que realizaré trabajo de importancia nacional bajo dirección civil cuando la ley lo exija; y que asumo esta obligación libremente, sin ninguna reserva "
           "mental ni propósito de evasión; que Dios me ayude.")


def build_n400(form):
    b = Builder(form)

    # ============================================================ intro
    new_page(b, "intro", T("Before you start", "Antes de empezar"))
    b.field("intro_1", "paragraph", ("", ""), content=(
        "This intake collects the information OG Multiservices needs to prepare your Form N-400, Application for Naturalization (USCIS edition 01/20/25). It is longer than most forms, so take your time — your answers save automatically and you can stop and come back anytime.",
        "Este formulario reúne la información que OG Multiservices necesita para preparar tu Formulario N-400, Solicitud de Naturalización (edición USCIS 01/20/25). Es más largo que otros, así que tómate tu tiempo: tus respuestas se guardan automáticamente y puedes parar y volver cuando quieras."))
    b.field("intro_2", "paragraph", ("", ""), content=(
        "We will help you build your address, work/school and travel histories step by step, so you don't have to work out the dates by yourself. Have your passport, Green Card and past addresses nearby if you can.",
        "Te ayudaremos a construir tus historiales de direcciones, trabajo/estudios y viajes paso a paso, para que no tengas que calcular las fechas tú solo(a). Ten a la mano tu pasaporte, tu Green Card y tus direcciones anteriores si puedes."))
    b.field("intro_3", "paragraph", ("", ""), content=(
        "OG Multiservices provides document preparation and administrative assistance. We are not a law firm and do not provide legal advice or representation, and we cannot tell you whether you qualify. Sending this to OG does not file anything with USCIS.",
        "OG Multiservices ofrece preparación de documentos y asistencia administrativa. No somos un bufete de abogados, no brindamos asesoría ni representación legal y no podemos decirte si calificas. Enviar esto a OG no presenta nada ante USCIS."))

    # ============================================================ Part 1
    new_page(b, "basis", T("Your reason for filing", "Tu motivo para presentar"), group="personal")
    b.field("basis", "single_choice", ("Why are you filing Form N-400?", "¿Por qué presentas el Formulario N-400?"), ref="Part 1, Item 1", req=True,
            help=("Select only one. If you're not sure, choose the one that seems closest — OG will confirm it with you.", "Selecciona solo una. Si no estás seguro(a), elige la que más se parezca; OG lo confirmará contigo."),
            detail=("USCIS notes on the form: select only one box to identify the basis of your eligibility, or your Form N-400 may be delayed or rejected. If your mother or father (including legal adoptive mother or father) is a U.S. citizen by birth, or was naturalized before you reached your 18th birthday, you may not need to file Form N-400 because you may already be a U.S. citizen; see Form N-600 at www.uscis.gov/N-600.",
                    "Notas de USCIS en el formulario: selecciona solo una casilla para identificar la base de tu elegibilidad, o tu Formulario N-400 podría demorarse o ser rechazado. Si tu madre o tu padre (incluido madre o padre adoptivo legal) es ciudadano de EE. UU. por nacimiento, o se naturalizó antes de que cumplieras 18 años, quizá no necesites presentar el N-400 porque podrías ser ya ciudadano(a); consulta el Formulario N-600 en www.uscis.gov/N-600."),
            opts=[
                ("general", "General Provision", "Disposición general"),
                ("spouse_citizen", "Spouse of U.S. Citizen", "Cónyuge de ciudadano(a) de EE. UU."),
                ("vawa", "VAWA — Spouse, Former Spouse, or Child of a U.S. Citizen under the Violence Against Women Act", "VAWA — Cónyuge, excónyuge o hijo(a) de ciudadano(a) de EE. UU. bajo la Ley de Violencia contra las Mujeres"),
                ("spouse_abroad", "Spouse of U.S. Citizen in Qualified Employment Outside the United States", "Cónyuge de ciudadano(a) de EE. UU. en empleo calificado fuera de los Estados Unidos"),
                ("military_hostilities", "Military Service During Period of Hostilities", "Servicio militar durante un período de hostilidades"),
                ("military_one_year", "At Least One Year of Honorable Military Service at Any Time", "Al menos un año de servicio militar honorable en cualquier momento"),
                ("other", "Other Reason for Filing Not Listed Above", "Otro motivo para presentar no listado arriba"),
            ])
    b.field("basis_other_explain", "long_answer", ("Please explain your other reason for filing", "Explica tu otro motivo para presentar"), ref="Part 1, Item 1.g (explanation)", req=True)
    b.field("field_office", "dropdown", ("USCIS field office for your naturalization interview", "Oficina de campo de USCIS para tu entrevista de naturalización"), ref="Part 1 (field office)",
            help=("Only if your residential address is outside the United States and you are filing under INA section 319(b).", "Solo si tu dirección de residencia está fuera de los Estados Unidos y presentas bajo la sección 319(b) de la INA."),
            opts=[(o, o, o) for o in OFFICES])
    b.rule("show_field", "basis_other_explain", [("basis", "equals", "other")])
    b.rule("show_field", "field_office", [("basis", "equals", "spouse_abroad")])

    # ============================================================ Part 2
    new_page(b, "name", T("Your legal name", "Tu nombre legal"), T("Your current legal name — do not provide a nickname.", "Tu nombre legal actual; no escribas un apodo."), group="personal")
    b.field("name_family", "short_answer", ("Family name (last name)", "Apellido"), ref="Part 2, Item 1", req=True, width="half")
    b.field("name_given", "short_answer", ("Given name (first name)", "Nombre(s)"), ref="Part 2, Item 1", req=True, width="half")
    b.field("name_middle", "short_answer", ("Middle name (if applicable)", "Segundo nombre (si aplica)"), ref="Part 2, Item 1", width="half")

    new_page(b, "other_names", T("Other names you have used", "Otros nombres que has usado"), group="personal")
    f = b.field("other_names", "record_list", ("Other names you have used since birth", "Otros nombres que has usado desde que naciste"), ref="Part 2, Item 2",
                help=("Add any other name you have used since birth, such as a maiden name. See the N-400 Instructions for which names to include. If you have none, just continue.",
                      "Agrega cualquier otro nombre que hayas usado desde que naciste, como un apellido de soltera. Consulta las Instrucciones del N-400 para saber qué nombres incluir. Si no tienes ninguno, solo continúa."))
    f.config_json = _cfg(record="other_name", max=10)

    new_page(b, "name_change", T("Name change", "Cambio de nombre"), group="personal")
    b.field("name_change", "single_choice", ("Would you like to legally change your name?", "¿Quieres cambiar legalmente tu nombre?"), ref="Part 2, Item 3", req=True, opts=YES_NO,
            help=("Optional. Read the N-400 Instructions for this item before you decide.", "Opcional. Lee las Instrucciones del N-400 para este punto antes de decidir."))
    b.field("new_family", "short_answer", ("New family name (last name)", "Nuevo apellido"), ref="Part 2, Item 3 (new name)", req=True, width="half")
    b.field("new_given", "short_answer", ("New given name (first name)", "Nuevo nombre"), ref="Part 2, Item 3 (new name)", req=True, width="half")
    b.field("new_middle", "short_answer", ("New middle name (if applicable)", "Nuevo segundo nombre (si aplica)"), ref="Part 2, Item 3 (new name)", width="half")
    for n in ("new_family", "new_given", "new_middle"):
        b.rule("show_field", n, [("name_change", "equals", "yes")])

    new_page(b, "ids", T("Identification numbers", "Números de identificación"), group="personal")
    b.field("a_number", "short_answer", ("Alien Registration Number (A-Number)", "Número de Registro de Extranjero (Número A)"), ref="Part 1 (A-Number) / Part 2", req=True, sensitive=True,
            pattern=r"A?-?\d{7,9}", maxlen=12, help=("The form asks for your 9-digit A-Number. It looks like A-123456789.", "El formulario pide tu Número A de 9 dígitos. Se ve como A-123456789."),
            msg=("Enter your A-Number: 7 to 9 digits, with or without “A-”.", "Ingresa tu Número A: 7 a 9 dígitos, con o sin “A-”."))
    b.field("uscis_account", "short_answer", ("USCIS Online Account Number (if any)", "Número de cuenta en línea de USCIS (si tienes)"), ref="Part 2, Item 4", maxlen=12,
            pattern=r"\d{1,12}", msg=("Use digits only (up to 12).", "Usa solo dígitos (hasta 12)."))

    new_page(b, "about", T("About you", "Sobre ti"), group="personal")
    b.field("sex", "single_choice", ("Sex", "Sexo"), ref="Part 2, Item 5", req=True, opts=[("male", "Male", "Masculino"), ("female", "Female", "Femenino")])
    b.field("dob", "date", ("Date of birth", "Fecha de nacimiento"), ref="Part 2, Item 6", req=True, date_rule="past", width="half",
            help=("In addition to your actual date of birth, list any other dates of birth you have ever used in the last step (Additional Information).", "Además de tu fecha de nacimiento real, indica en el último paso (Información adicional) cualquier otra fecha de nacimiento que hayas usado."))
    b.field("date_lpr", "date", ("Date you became a lawful permanent resident", "Fecha en que te convertiste en residente permanente legal"), ref="Part 2, Item 7", req=True, date_rule="past", width="half",
            help=("If you are a lawful permanent resident, the date on your Green Card (“Resident Since”).", "Si eres residente permanente legal, la fecha de tu Green Card (“Resident Since”)."))
    b.field("country_birth", "short_answer", ("Country of birth", "País de nacimiento"), ref="Part 2, Item 8", req=True)
    b.field("country_citizenship", "short_answer", ("Country of citizenship or nationality", "País de ciudadanía o nacionalidad"), ref="Part 2, Item 9", req=True)
    b.field("other_citizenship", "short_answer", ("Other countries of citizenship or nationality (if any)", "Otros países de ciudadanía o nacionalidad (si aplica)"), ref="Part 2, Item 9 / Part 14",
            help=("If you are a citizen or national of more than one country, list the additional countries.", "Si eres ciudadano(a) o nacional de más de un país, indica los países adicionales."))

    new_page(b, "parents", T("Two questions about you", "Dos preguntas sobre ti"), group="personal")
    b.field("parent_citizen", "single_choice", ("Was your mother or father (including adoptive mother or father) a U.S. citizen before your 18th birthday?", "¿Tu madre o tu padre (incluidos madre o padre adoptivos) era ciudadano(a) de EE. UU. antes de que cumplieras 18 años?"),
            ref="Part 2, Item 10", req=True, opts=YES_NO,
            detail=("USCIS note on the form: if you answered “Yes,” you may already be a U.S. citizen. If you are a U.S. citizen, you should not complete Form N-400. OG will go over this with you.",
                    "Nota de USCIS en el formulario: si respondiste “Sí”, quizá ya seas ciudadano(a) de EE. UU. Si eres ciudadano(a), no debes completar el Formulario N-400. OG lo revisará contigo."))
    b.field("disability", "single_choice", ("Do you have a physical or developmental disability or mental impairment that prevents you from demonstrating your knowledge and understanding of the English language or civics requirements for naturalization?", "¿Tienes una discapacidad física o del desarrollo, o un impedimento mental, que te impide demostrar tu conocimiento y comprensión del idioma inglés o de los requisitos de civismo para la naturalización?"),
            ref="Part 2, Item 11", req=True, opts=YES_NO,
            detail=("USCIS note on the form: if you answered “Yes,” submit a completed Form N-648, Medical Certification for Disability Exceptions, when you file your Form N-400. See the Naturalization Testing and Exceptions section of the Instructions for exceptions, including those based on age and years as a lawful permanent resident.",
                    "Nota de USCIS en el formulario: si respondiste “Sí”, presenta un Formulario N-648, Certificación médica para excepciones por discapacidad, completado, junto con tu Formulario N-400. Consulta la sección Naturalization Testing and Exceptions de las Instrucciones para ver las excepciones, incluidas las basadas en la edad y en los años como residente permanente legal."))

    new_page(b, "ssa", T("Social Security update", "Actualización del Seguro Social"), group="personal")
    b.field("ssa_request", "single_choice", ("Do you want the Social Security Administration (SSA) to issue you an original or replacement Social Security card and update your immigration status with the SSA if and when you are naturalized?", "¿Quieres que la Administración del Seguro Social (SSA) te emita una tarjeta de Seguro Social original o de reemplazo y actualice tu estatus migratorio con la SSA si y cuando te naturalices?"),
            ref="Part 2, Item 12.a", req=True, opts=YES_NO)
    b.field("ssn", "short_answer", ("Your Social Security number (SSN), if any", "Tu número de Seguro Social (SSN), si tienes"), ref="Part 2, Item 12.b", sensitive=True, pattern=r"\d{3}-?\d{2}-?\d{4}",
            msg=("Enter 9 digits.", "Ingresa 9 dígitos."), help=("Private and protected.", "Privado y protegido."))
    b.field("ssa_consent", "single_choice", ("Consent for disclosure: I authorize disclosure of information from this application and USCIS systems to the SSA as required for the purpose of assigning me an SSN, issuing me an original or replacement Social Security card, and updating my immigration status with the SSA.", "Consentimiento para divulgar: autorizo la divulgación de información de esta solicitud y de los sistemas de USCIS a la SSA según sea necesario para asignarme un SSN, emitirme una tarjeta de Seguro Social original o de reemplazo y actualizar mi estatus migratorio con la SSA."),
            ref="Part 2, Item 12.c", req=True, opts=YES_NO,
            help=("USCIS note on the form: if you answered “Yes” to the first question, you must also answer “Yes” here to receive a card.", "Nota de USCIS en el formulario: si respondiste “Sí” a la primera pregunta, también debes responder “Sí” aquí para recibir una tarjeta."))
    for n in ("ssn", "ssa_consent"):
        b.rule("show_field", n, [("ssa_request", "equals", "yes")])

    # ============================================================ Part 3
    new_page(b, "bio1", T("Ethnicity and race", "Etnia y raza"), T("USCIS requires these categories to conduct background checks.", "USCIS requiere estas categorías para realizar verificaciones de antecedentes."), group="personal")
    b.field("ethnicity", "single_choice", ("Ethnicity", "Etnia"), ref="Part 3, Item 1", req=True, help=("Select only one.", "Selecciona solo una."),
            opts=[("hispanic", "Hispanic or Latino", "Hispano o Latino"), ("not_hispanic", "Not Hispanic or Latino", "No hispano ni latino")])
    b.field("race", "multi_choice", ("Race", "Raza"), ref="Part 3, Item 2", req=True, help=("Select all that apply.", "Selecciona todas las que apliquen."),
            opts=[("white", "White", "Blanca"), ("asian", "Asian", "Asiática"), ("black", "Black or African American", "Negra o afroamericana"),
                  ("american_indian", "American Indian or Alaska Native", "Indígena americana o nativa de Alaska"),
                  ("pacific_islander", "Native Hawaiian or Other Pacific Islander", "Nativa de Hawái u otra isla del Pacífico")])
    new_page(b, "bio2", T("Physical description", "Descripción física"), group="personal")
    b.field("height_feet", "dropdown", ("Height — feet", "Estatura — pies"), ref="Part 3, Item 3", req=True, width="half", opts=[(str(n), str(n), str(n)) for n in range(2, 9)])
    b.field("height_inches", "dropdown", ("Height — inches", "Estatura — pulgadas"), ref="Part 3, Item 3", req=True, width="half", opts=[(str(n), str(n), str(n)) for n in range(0, 12)])
    b.field("weight_lbs", "number", ("Weight (pounds)", "Peso (libras)"), ref="Part 3, Item 4", req=True, minv=1, maxv=999, width="half")
    b.field("eye_color", "dropdown", ("Eye color", "Color de ojos"), ref="Part 3, Item 5", req=True, opts=EYE, width="half")
    b.field("hair_color", "dropdown", ("Hair color", "Color de cabello"), ref="Part 3, Item 6", req=True, opts=HAIR, width="half")

    # ============================================================ Part 4
    new_page(b, "residence", T("Where you have lived", "Dónde has vivido"),
             T("Start with where you live now. Then add each previous address until the period is covered.", "Empieza con donde vives ahora. Luego agrega cada dirección anterior hasta cubrir el período."), group="residence")
    f = b.field("residence_history", "record_list", ("Physical addresses — every place you have lived in the last 5 years", "Direcciones físicas: cada lugar donde has vivido en los últimos 5 años"),
                ref="Part 4, Item 1", req=True)
    f.config_json = _cfg(record="address", max=20, timeline={"years": 5, "gap_days": 3, "overlap_days": 31},
                         intro={"en": RECORD_INTRO_PERIOD[0], "es": RECORD_INTRO_PERIOD[1]})

    new_page(b, "mail_gate", T("Mailing address", "Dirección postal"), group="address")
    b.field("mail_same", "single_choice", ("Is your current physical address also your current mailing address?", "¿Tu dirección física actual es también tu dirección postal actual?"), ref="Part 4, Item 2", req=True, opts=YES_NO)
    new_page(b, "mail_addr", T("Your mailing address", "Tu dirección postal"), T("The Safe Mailing Address, if applicable.", "La dirección postal segura, si aplica."), group="address")
    b.field("mail_in_care_of", "short_answer", ("In care of name (if any)", "A cargo de (si aplica)"), ref="Part 4, Item 3")
    _address_fields(b, "mail", "Part 4, Item 3")
    b.rule("show_page", "mail_addr", [("mail_same", "equals", "no")])

    # ============================================================ Part 5
    new_page(b, "marital", T("Marital status", "Estado civil"), group="family")
    b.field("marital_status", "single_choice", ("What is your current marital status?", "¿Cuál es tu estado civil actual?"), ref="Part 5, Item 1", req=True,
            opts=[("single", "Single, Never Married", "Soltero(a), nunca casado(a)"), ("married", "Married", "Casado(a)"), ("divorced", "Divorced", "Divorciado(a)"),
                  ("widowed", "Widowed", "Viudo(a)"), ("annulled", "Marriage Annulled", "Matrimonio anulado"), ("separated", "Separated", "Separado(a)")])

    new_page(b, "marriages", T("Your marriages", "Tus matrimonios"), group="family")
    b.field("spouse_military", "single_choice", ("If you are currently married, is your spouse a current member of the U.S. armed forces?", "Si estás casado(a) actualmente, ¿tu cónyuge es miembro actual de las fuerzas armadas de EE. UU.?"), ref="Part 5, Item 2", req=True, opts=YES_NO)
    b.field("times_married", "number", ("How many times have you been married?", "¿Cuántas veces te has casado?"), ref="Part 5, Item 3", req=True, minv=0, maxv=99, width="half",
            help=("See the Instructions for which marriages to include. Bring the current marriage certificate and any divorce, annulment or death certificate for prior marriages (you can upload them at the end).", "Consulta las Instrucciones para saber qué matrimonios incluir. Ten a la mano el acta de matrimonio actual y cualquier decreto de divorcio, anulación o acta de defunción de matrimonios anteriores (puedes subirlos al final)."))
    for n in ("spouse_military",):
        show_any(b, n, [[("marital_status", "equals", "married")], [("marital_status", "equals", "separated")]])
    show_any(b, "times_married", [[("marital_status", "equals", v)] for v in ("married", "divorced", "widowed", "annulled", "separated")])

    spouse_groups = [[("basis", "equals", b_), ("marital_status", "equals", m)] for b_ in ("spouse_citizen", "spouse_abroad") for m in ("married", "separated")]
    new_page(b, "spouse1", T("Your current spouse", "Tu cónyuge actual"),
             T("You are asked about your current spouse because of the reason you selected for filing.", "Te preguntamos sobre tu cónyuge actual por el motivo de presentación que elegiste."), group="family")
    b.field("spouse_family", "short_answer", ("Spouse's family name (last name)", "Apellido de tu cónyuge"), ref="Part 5, Item 4.a", req=True, width="half")
    b.field("spouse_given", "short_answer", ("Spouse's given name (first name)", "Nombre de tu cónyuge"), ref="Part 5, Item 4.a", req=True, width="half")
    b.field("spouse_middle", "short_answer", ("Spouse's middle name (if applicable)", "Segundo nombre de tu cónyuge (si aplica)"), ref="Part 5, Item 4.a", width="half")
    b.field("spouse_dob", "date", ("Spouse's date of birth", "Fecha de nacimiento de tu cónyuge"), ref="Part 5, Item 4.b", req=True, date_rule="past", width="half")
    b.field("marriage_date", "date", ("Date you entered into marriage with your current spouse", "Fecha en que te casaste con tu cónyuge actual"), ref="Part 5, Item 4.c", req=True, date_rule="past", width="half")
    b.field("spouse_same_address", "single_choice", ("Is your current spouse's present physical address the same as your physical address?", "¿La dirección física actual de tu cónyuge es la misma que tu dirección física?"), ref="Part 5, Item 4.d", req=True, opts=YES_NO)
    b.field("spouse_address", "long_answer", ("Your spouse's present physical address", "La dirección física actual de tu cónyuge"), ref="Part 5, Item 4.d (address goes to Part 14)", req=True)
    b.rule("show_field", "spouse_address", [("spouse_same_address", "equals", "no")])
    show_page_any(b, "spouse1", spouse_groups)

    new_page(b, "spouse2", T("Your spouse's citizenship and work", "Ciudadanía y trabajo de tu cónyuge"), group="family")
    b.field("spouse_citizen_when", "single_choice", ("When did your current spouse become a U.S. citizen?", "¿Cuándo se hizo ciudadano(a) de EE. UU. tu cónyuge actual?"), ref="Part 5, Item 5.a", req=True,
            opts=[("birth", "By birth in the United States", "Por nacimiento en los Estados Unidos"), ("other", "Other", "Otro")])
    b.field("spouse_citizen_date", "date", ("Date your current spouse became a U.S. citizen", "Fecha en que tu cónyuge actual se hizo ciudadano(a) de EE. UU."), ref="Part 5, Item 5.b", req=True, date_rule="past", width="half")
    b.rule("show_field", "spouse_citizen_date", [("spouse_citizen_when", "equals", "other")])
    b.field("spouse_a_number", "short_answer", ("Your spouse's Alien Registration Number (A-Number), if any", "Número A de tu cónyuge, si tiene"), ref="Part 5, Item 6", sensitive=True, pattern=r"A?-?\d{7,9}", maxlen=12,
            msg=("Enter 7 to 9 digits, with or without “A-”.", "Ingresa 7 a 9 dígitos, con o sin “A-”."))
    b.field("spouse_times_married", "number", ("How many times has your current spouse been married?", "¿Cuántas veces se ha casado tu cónyuge actual?"), ref="Part 5, Item 7", req=True, minv=0, maxv=99, width="half",
            help=("Include prior marriages of your spouse as the Instructions explain; provide divorce decrees, annulment decrees or death certificates if applicable.", "Incluye matrimonios anteriores de tu cónyuge como explican las Instrucciones; ten a la mano decretos de divorcio, anulación o actas de defunción si aplica."))
    b.field("spouse_employer", "short_answer", ("Your current spouse's current employer or company", "Empleador o empresa actual de tu cónyuge"), ref="Part 5, Item 8", req=True,
            help=("Only for “Spouse of U.S. Citizen in Qualified Employment Outside the United States”.", "Solo para “Cónyuge de ciudadano(a) de EE. UU. en empleo calificado fuera de los Estados Unidos”."))
    b.rule("show_field", "spouse_employer", [("basis", "equals", "spouse_abroad")])
    show_page_any(b, "spouse2", spouse_groups)

    # ============================================================ Part 7 / Part 8
    new_page(b, "employment", T("Where you have worked or studied", "Dónde has trabajado o estudiado"),
             T("Start with your current or most recent activity, then work backwards.", "Empieza con tu actividad actual o más reciente y ve hacia atrás."), group="employment")
    f = b.field("employment_history", "record_list", ("Employment, self-employment, school, unemployment — the last 5 years", "Empleo, trabajo por cuenta propia, estudios, desempleo: los últimos 5 años"),
                ref="Part 7, Item 1", req=True,
                help=("Include full-time and part-time work or school, and foreign government employment such as military, police and intelligence services. If you worked for yourself, the form says to write “self-employed”; if you were unemployed, “unemployed”; if retired, “retired” — choose that option and we'll do it for you.",
                      "Incluye trabajo o estudios de tiempo completo y parcial, y empleo con un gobierno extranjero, como militar, policía y servicios de inteligencia. Si trabajaste por tu cuenta, el formulario indica escribir “self-employed”; si estuviste desempleado(a), “unemployed”; si estás jubilado(a), “retired”: elige esa opción y lo haremos por ti."))
    f.config_json = _cfg(record="activity", max=20, timeline={"years": 5, "gap_days": 3, "overlap_days": 31},
                         intro={"en": RECORD_INTRO_PERIOD[0], "es": RECORD_INTRO_PERIOD[1]})

    new_page(b, "travel", T("Trips outside the United States", "Viajes fuera de los Estados Unidos"), group="travel")
    b.field("has_trips", "single_choice", ("Have you taken any trips outside the United States during the last 5 years?", "¿Has hecho algún viaje fuera de los Estados Unidos durante los últimos 5 años?"),
            ref="Part 8, Item 1", req=True, opts=YES_NO,
            help=("Do not include day trips (where the entire trip was completed within 24 hours). If you are filing under a different option, USCIS's Instructions set the period; we collect the last 5 years.",
                  "No incluyas viajes de un solo día (donde todo el viaje se completó en menos de 24 horas). Si presentas bajo otra opción, las Instrucciones de USCIS fijan el período; recopilamos los últimos 5 años."),
            detail=("USCIS note on the form: if you have taken any trips outside the United States that lasted more than 6 months, see the Required Evidence – Continuous Residence section of the Instructions for the evidence you should provide.",
                    "Nota de USCIS en el formulario: si has hecho viajes fuera de los Estados Unidos que duraron más de 6 meses, consulta la sección Required Evidence – Continuous Residence de las Instrucciones para ver la evidencia que debes presentar."))
    f = b.field("trips", "record_list", ("Your trips, starting with the most recent", "Tus viajes, empezando por el más reciente"), ref="Part 8, Item 1", req=True)
    f.config_json = _cfg(record="trip", max=30, years=5)
    b.rule("show_field", "trips", [("has_trips", "equals", "yes")])

    # ============================================================ Part 6
    new_page(b, "children_total", T("Your children", "Tus hijos"), group="family")
    b.field("children_total", "number", ("Total number of children under 18 years of age", "Número total de hijos menores de 18 años"), ref="Part 6, Item 1", req=True, minv=0, maxv=99, width="half")
    new_page(b, "children", T("About your children", "Sobre tus hijos"), T("Add each child under 18, one at a time.", "Agrega a cada hijo(a) menor de 18 años, uno por uno."), group="family")
    f = b.field("children", "record_list", ("Your children", "Tus hijos"), ref="Part 6, Item 2", req=True,
                help=("For each child: name, where the child lives, date of birth, relationship, and whether you provide support. If a child does not live with you, we also ask where the child lives (it goes in Additional Information, Part 14).",
                      "Para cada hijo(a): nombre, dónde vive, fecha de nacimiento, relación y si le brindas manutención. Si un hijo(a) no vive contigo, también preguntamos dónde vive (va en Información adicional, Parte 14)."))
    f.config_json = _cfg(record="child", max=20)
    b.rule("show_page", "children", [("children_total", "greater_than", "0")])

    # ============================================================ Part 9
    def qpage(key, title, group="additional", desc=None):
        return new_page(b, key, title, desc, group=group)

    qpage("p9_claims", T("Citizenship claims and voting", "Ciudadanía y votación"),
          desc=T("When a question includes the word “EVER,” answer for anything you did anywhere in the world at any time, unless the question says otherwise.", "Cuando una pregunta incluye la palabra “EVER” (alguna vez), responde por cualquier cosa que hayas hecho en cualquier parte del mundo y en cualquier momento, salvo que la pregunta indique otra cosa."))
    yesno(b, "claimed_citizen", "Part 9, Item 1", "Have you EVER claimed to be a U.S. citizen (in writing or any other way)?", "¿Alguna vez has afirmado ser ciudadano(a) de EE. UU. (por escrito o de cualquier otra forma)?", explain="Part 9, Item 1")
    yesno(b, "voted", "Part 9, Item 2", "Have you EVER registered to vote or voted in any Federal, state, or local election in the United States?", "¿Alguna vez te has registrado para votar o has votado en alguna elección federal, estatal o local en los Estados Unidos?",
          help=("If you lawfully voted only in a local election where aliens are eligible to vote, you may answer “No.”", "Si votaste legalmente solo en una elección local en la que los extranjeros pueden votar, puedes responder “No”."), explain="Part 9, Item 2")

    qpage("p9_taxes", T("Taxes", "Impuestos"))
    yesno(b, "owe_taxes", "Part 9, Item 3", "Do you currently owe any overdue Federal, state, or local taxes in the United States?", "¿Actualmente debes impuestos federales, estatales o locales vencidos en los Estados Unidos?", explain="Part 9, Item 3")
    yesno(b, "nonresident_tax", "Part 9, Item 4", "Since you became a lawful permanent resident, have you called yourself a “nonresident alien” on a Federal, state, or local tax return or decided not to file a tax return because you considered yourself to be a nonresident?",
          "Desde que te convertiste en residente permanente legal, ¿te has llamado “extranjero no residente” en una declaración de impuestos federal, estatal o local, o has decidido no presentar una declaración porque te considerabas no residente?", explain="Part 9, Item 4")

    qpage("p9_groups", T("Groups and organizations", "Grupos y organizaciones"))
    yesno(b, "party_member", "Part 9, Item 5.a", "Have you EVER been a member of, involved in, or in any way associated with any Communist or totalitarian party anywhere in the world?",
          "¿Alguna vez has sido miembro, has estado involucrado(a) o has estado asociado(a) de cualquier manera con algún partido comunista o totalitario en cualquier parte del mundo?", explain="Part 9, Item 5.a")
    yesno(b, "advocated", "Part 9, Item 5.b", "Have you EVER advocated (supported and promoted) any of the following, or been a member of, involved in, or in any way associated with any group anywhere in the world that advocated any of the following?",
          "¿Alguna vez has abogado por (apoyado y promovido) algo de lo siguiente, o has sido miembro, has estado involucrado(a) o asociado(a) de cualquier manera con algún grupo en cualquier parte del mundo que abogara por algo de lo siguiente?",
          help=("• The overthrow by force or violence or other unconstitutional means of the Government of the United States or all forms of law\n• Opposition to all organized government\n• World communism\n• The establishment in the United States of a totalitarian dictatorship\n• The unlawful assaulting or killing of any officer or officers of the Government of the United States or of any other organized government because of their official character\n• The unlawful damage, injury, or destruction of property\n• Sabotage",
                "• El derrocamiento por la fuerza o la violencia u otros medios inconstitucionales del Gobierno de los Estados Unidos o de todas las formas de ley\n• La oposición a todo gobierno organizado\n• El comunismo mundial\n• El establecimiento en los Estados Unidos de una dictadura totalitaria\n• El asalto o asesinato ilegal de cualquier funcionario o funcionarios del Gobierno de los Estados Unidos o de cualquier otro gobierno organizado por su carácter oficial\n• El daño, lesión o destrucción ilegal de propiedad\n• El sabotaje"),
          explain="Part 9, Item 5.b")

    qpage("p9_violence", T("Groups and violence", "Grupos y violencia"))
    intro(b, "p9_6_intro", "Have you EVER been a member of, involved in, or in any way associated with, or have you EVER provided money, a thing of value, services or labor, or any other assistance or support to a group that:",
          "¿Alguna vez has sido miembro, has estado involucrado(a) o asociado(a) de cualquier manera con, o has proporcionado dinero, algo de valor, servicios, trabajo o cualquier otra ayuda o apoyo a un grupo que:")
    yesno(b, "group_weapon", "Part 9, Item 6.a", "Used a weapon or explosive with intent to harm another person or cause damage to property?", "¿Usó un arma o explosivo con la intención de dañar a otra persona o causar daño a la propiedad?", explain="Part 9, Item 6.a")
    yesno(b, "group_kidnap", "Part 9, Item 6.b", "Engaged (participated) in kidnapping, assassination, or hijacking or sabotage of an airplane, ship, vehicle, or other mode of transportation?",
          "¿Participó en secuestro, asesinato, o secuestro o sabotaje de un avión, barco, vehículo u otro medio de transporte?", explain="Part 9, Item 6.b")
    yesno(b, "group_threat", "Part 9, Item 6.c", "Threatened, attempted (tried), conspired (planned with others), prepared, planned, advocated for, or incited (encouraged) others to commit any of the acts listed in Item Numbers 6.a. or 6.b.?",
          "¿Amenazó, intentó, conspiró (planeó con otros), preparó, planeó, abogó por o incitó (alentó) a otros a cometer cualquiera de los actos indicados en los puntos 6.a. o 6.b.?", explain="Part 9, Item 6.c")

    qpage("p9_harm1", T("Harm to others (1 of 2)", "Daño a otras personas (1 de 2)"))
    intro(b, "p9_7_intro", "Have you EVER ordered, incited, called for, committed, assisted, helped with, or otherwise participated in any of the following:",
          "¿Alguna vez has ordenado, incitado, solicitado, cometido, ayudado o participado de otra manera en cualquiera de lo siguiente:")
    yesno(b, "harm_torture", "Part 9, Item 7.a", "Torture?", "¿Tortura?", explain="Part 9, Item 7.a")
    yesno(b, "harm_genocide", "Part 9, Item 7.b", "Genocide?", "¿Genocidio?", explain="Part 9, Item 7.b")
    yesno(b, "harm_killing", "Part 9, Item 7.c", "Killing or trying to kill any person?", "¿Matar o intentar matar a cualquier persona?", explain="Part 9, Item 7.c")
    yesno(b, "harm_sexual", "Part 9, Item 7.d", "Any kind of sexual contact or activity with any person who did not consent (did not agree) or was unable to consent (could not agree), or was being forced or threatened by you or by someone else?",
          "¿Cualquier tipo de contacto o actividad sexual con una persona que no dio su consentimiento (no estuvo de acuerdo), que no pudo dar su consentimiento (no pudo estar de acuerdo) o que estaba siendo forzada o amenazada por ti o por otra persona?", explain="Part 9, Item 7.d")
    qpage("p9_harm2", T("Harm to others (2 of 2)", "Daño a otras personas (2 de 2)"))
    intro(b, "p9_7b_intro", "Have you EVER ordered, incited, called for, committed, assisted, helped with, or otherwise participated in any of the following:",
          "¿Alguna vez has ordenado, incitado, solicitado, cometido, ayudado o participado de otra manera en cualquiera de lo siguiente:")
    yesno(b, "harm_injury", "Part 9, Item 7.e", "Intentionally and severely injuring or trying to injure any person?", "¿Lesionar intencional y gravemente, o intentar lesionar, a cualquier persona?", explain="Part 9, Item 7.e")
    yesno(b, "harm_religion", "Part 9, Item 7.f", "Not letting someone practice his or her religion?", "¿No permitir que alguien practique su religión?", explain="Part 9, Item 7.f")
    yesno(b, "harm_discrimination", "Part 9, Item 7.g", "Causing harm or suffering to any person because of his or her race, religion, national origin, membership in a particular social group, or political opinion?",
          "¿Causar daño o sufrimiento a cualquier persona por su raza, religión, origen nacional, pertenencia a un grupo social particular u opinión política?", explain="Part 9, Item 7.g")

    qpage("p9_military", T("Military, police and armed groups", "Militares, policía y grupos armados"))
    yesno(b, "military_police", "Part 9, Item 8.a", "Have you EVER served in, been a member of, assisted (helped), or participated in any military or police unit?",
          "¿Alguna vez has servido, has sido miembro, has ayudado o has participado en alguna unidad militar o de policía?")
    yesno(b, "armed_group", "Part 9, Item 8.b", "Have you EVER served in, been a member of, assisted (helped), or participated in any armed group (a group that carries weapons), for example: paramilitary unit (a group of people who act like a military group but are not part of the official military), self-defense unit, vigilante unit, rebel group, or guerrilla group?",
          "¿Alguna vez has servido, has sido miembro, has ayudado o has participado en algún grupo armado (un grupo que porta armas), por ejemplo: unidad paramilitar (un grupo de personas que actúan como un grupo militar pero no forman parte del ejército oficial), unidad de autodefensa, grupo de vigilantes, grupo rebelde o guerrilla?")
    note(b, "mil_note", "USCIS asks you to include the name of the country, the name of the military unit or armed group, your rank or position, and your dates of involvement.",
         "USCIS pide que incluyas el nombre del país, el nombre de la unidad militar o del grupo armado, tu rango o posición y tus fechas de participación.")
    b.field("mil_country", "short_answer", ("Country", "País"), ref="Part 14 (Part 9, Item 8.a/8.b)", req=True, width="half")
    b.field("mil_unit", "short_answer", ("Name of the military unit or armed group", "Nombre de la unidad militar o del grupo armado"), ref="Part 14 (Part 9, Item 8.a/8.b)", req=True, width="half")
    b.field("mil_rank", "short_answer", ("Your rank or position", "Tu rango o posición"), ref="Part 14 (Part 9, Item 8.a/8.b)", req=True, width="half")
    b.field("mil_dates", "short_answer", ("Dates of your involvement", "Fechas de tu participación"), ref="Part 14 (Part 9, Item 8.a/8.b)", req=True, width="half", ph=("e.g. 2010 – 2012", "p. ej. 2010 – 2012"))
    for n in ("mil_note", "mil_country", "mil_unit", "mil_rank", "mil_dates"):
        show_any(b, n, [[("military_police", "equals", "yes")], [("armed_group", "equals", "yes")]])

    qpage("p9_detention", T("Detention and weapons", "Detención y armas"))
    yesno(b, "detention", "Part 9, Item 9", "Have you EVER worked, volunteered, or otherwise served in a place where people were detained (forced to stay), for example, a prison, jail, prison camp (a camp where prisoners of war or political prisoners are kept), detention facility, or labor camp, or have you EVER directed or participated in any other activity that involved detaining people?",
          "¿Alguna vez has trabajado, has sido voluntario(a) o has servido de otra manera en un lugar donde se detenía a personas (obligadas a permanecer), por ejemplo, una prisión, cárcel, campo de prisioneros (un campo donde se mantiene a prisioneros de guerra o presos políticos), centro de detención o campo de trabajo, o has dirigido o participado en cualquier otra actividad que implicara detener a personas?", explain="Part 9, Item 9")
    yesno(b, "weapon_group", "Part 9, Item 10.a", "Were you EVER a part of any group, or did you EVER help any group, unit, or organization that used a weapon against any person, or threatened to do so?",
          "¿Alguna vez fuiste parte de algún grupo, o ayudaste alguna vez a algún grupo, unidad u organización que usó un arma contra alguna persona, o amenazó con hacerlo?")
    yesno(b, "weapon_used", "Part 9, Item 10.b", "When you were part of this group, or when you helped this group, did you ever use a weapon against another person?",
          "Cuando fuiste parte de este grupo, o cuando ayudaste a este grupo, ¿alguna vez usaste un arma contra otra persona?", explain="Part 9, Item 10.b")
    yesno(b, "weapon_threat", "Part 9, Item 10.c", "When you were part of this group, or when you helped this group, did you ever threaten another person that you would use a weapon against that person?",
          "Cuando fuiste parte de este grupo, o cuando ayudaste a este grupo, ¿alguna vez amenazaste a otra persona con que usarías un arma contra ella?", explain="Part 9, Item 10.c")
    for n in ("weapon_used", "weapon_threat"):
        b.rule("show_field", n, [("weapon_group", "equals", "yes")])
    b.field("weapon_group_explain", "long_answer", ("Please explain your answer", "Explica tu respuesta"), ref="Part 14 (explanation for Part 9, Item 10.a)", req=True)
    b.rule("show_field", "weapon_group_explain", [("weapon_group", "equals", "yes")])

    qpage("p9_training", T("Weapons, training and children", "Armas, entrenamiento y menores"))
    yesno(b, "training", "Part 9, Item 11", "Have you EVER received any weapons training, paramilitary training, or other military-type training?", "¿Alguna vez has recibido entrenamiento con armas, entrenamiento paramilitar u otro entrenamiento de tipo militar?", explain="Part 9, Item 11")
    yesno(b, "weapons_traffic", "Part 9, Item 12", "Have you EVER sold, provided, or transported weapons, or assisted any person in selling, providing, or transporting weapons, which you knew or believed would be used against another person?",
          "¿Alguna vez has vendido, proporcionado o transportado armas, o has ayudado a alguna persona a vender, proporcionar o transportar armas, que sabías o creías que se usarían contra otra persona?", explain="Part 9, Item 12")
    yesno(b, "recruit_minor", "Part 9, Item 13", "Have you EVER recruited (asked), enlisted (signed up), conscripted (required to join), or used any person under 15 years of age to serve in or help an armed group, or attempted or worked with others to do so?",
          "¿Alguna vez has reclutado (pedido), enlistado (inscrito), reclutado a la fuerza (obligado a unirse) o usado a alguna persona menor de 15 años para servir o ayudar a un grupo armado, o has intentado o trabajado con otros para hacerlo?", explain="Part 9, Item 13")
    yesno(b, "hostilities_minor", "Part 9, Item 14", "Have you EVER used any person under 15 years of age to take part in hostilities or attempted or worked with others to do so? This could include participating in combat or providing services related to combat (such as serving as a messenger or transporting supplies).",
          "¿Alguna vez has usado a alguna persona menor de 15 años para participar en hostilidades, o has intentado o trabajado con otros para hacerlo? Esto puede incluir participar en combate o prestar servicios relacionados con el combate (como servir de mensajero o transportar suministros).", explain="Part 9, Item 14")

    qpage("p9_arrests", T("Arrests and offenses", "Arrestos e infracciones"),
          desc=T("Answer even if your records were sealed, expunged, or otherwise cleared: USCIS asks you to disclose it anyway.", "Responde aunque tus registros hayan sido sellados, borrados o de otra forma eliminados: USCIS pide que lo declares de todos modos."))
    yesno(b, "offense_not_arrested", "Part 9, Item 15.a", "Have you EVER committed, agreed to commit, asked someone else to commit, helped commit, or tried to commit a crime or offense for which you were NOT arrested?",
          "¿Alguna vez has cometido, acordado cometer, pedido a otra persona que cometa, ayudado a cometer o intentado cometer un delito o infracción por el cual NO fuiste arrestado(a)?",
          detail=("USCIS note on the form: include all crimes and offenses in the United States or anywhere in the world (including domestic violence, driving under the influence of drugs or alcohol, and crimes and offenses while you were under 18 years of age) which you EVER: committed, agreed to commit, or asked someone else to commit; were arrested, cited, detained, or confined by any law enforcement officer, military official or immigration official; were charged with committing, helping commit, or trying to commit; pled guilty to; were convicted of; were placed in alternative sentencing or a rehabilitative program for; or received a suspended sentence, clemency, amnesty, or pardon for, or were placed on probation or paroled for. Submit evidence to support your answers.",
                  "Nota de USCIS en el formulario: incluye todos los delitos e infracciones en los Estados Unidos o en cualquier parte del mundo (incluida violencia doméstica, conducir bajo la influencia de drogas o alcohol, y delitos e infracciones cometidos siendo menor de 18 años) que ALGUNA VEZ: cometiste, acordaste cometer o pediste a otro que cometiera; por los que fuiste arrestado(a), citado(a), detenido(a) o confinado(a) por un agente del orden, un oficial militar o un oficial de inmigración; por los que fuiste acusado(a) de cometer, ayudar a cometer o intentar cometer; de los que te declaraste culpable; por los que fuiste condenado(a); por los que te pusieron en una sentencia alternativa o programa de rehabilitación; o por los que recibiste sentencia suspendida, clemencia, amnistía o indulto, o fuiste puesto(a) en libertad condicional o en libertad bajo palabra. Presenta evidencia que respalde tus respuestas."))
    yesno(b, "offense_arrested", "Part 9, Item 15.b", "Have you EVER been arrested, cited, detained or confined by any law enforcement officer, military official (in the U.S. or elsewhere), or immigration official for any reason, or been charged with a crime or offense?",
          "¿Alguna vez has sido arrestado(a), citado(a), detenido(a) o confinado(a) por algún agente del orden, oficial militar (en EE. UU. o en otro lugar) u oficial de inmigración por cualquier motivo, o has sido acusado(a) de un delito o infracción?")

    qpage("p9_offenses", T("Your arrests and offenses", "Tus arrestos e infracciones"), desc=T("Add each one, even if it was a long time ago or the record was cleared.", "Agrega cada uno, aunque haya sido hace mucho tiempo o el registro haya sido eliminado."))
    f = b.field("offenses", "record_list", ("Crimes and offenses", "Delitos e infracciones"), ref="Part 9, Item 15 (table)", req=True,
                help=("For each one: where, what, when, the result, and any conviction date and sentence.", "Para cada uno: dónde, qué, cuándo, el resultado, y la fecha de condena y la sentencia si aplican."))
    f.config_json = _cfg(record="offense", max=15)
    yesno(b, "sentence_completed", "Part 9, Item 16", "If you received a suspended sentence, were placed on probation, or were paroled, have you completed your suspended sentence, probation, or parole?",
          "Si recibiste una sentencia suspendida, fuiste puesto(a) en libertad condicional o en libertad bajo palabra, ¿has completado tu sentencia suspendida, libertad condicional o libertad bajo palabra?", req=False,
          help=("Answer only if this applies to you.", "Responde solo si esto aplica en tu caso."))
    show_page_any(b, "p9_offenses", [[("offense_not_arrested", "equals", "yes")], [("offense_arrested", "equals", "yes")]])

    qpage("p9_conduct1", T("Other conduct (1 of 2)", "Otra conducta (1 de 2)"))
    intro(b, "p9_17_intro", "Have you EVER:", "¿Alguna vez has:")
    yesno(b, "prostitution", "Part 9, Item 17.a", "Engaged in prostitution, attempted to procure or import prostitutes or persons for the purpose of prostitution, or received any proceeds or money from prostitution?",
          "¿Ejercido la prostitución, intentado conseguir o importar prostitutas o personas con fines de prostitución, o recibido ganancias o dinero de la prostitución?", explain="Part 9, Item 17.a")
    yesno(b, "drugs", "Part 9, Item 17.b", "Manufactured, cultivated, produced, distributed, dispensed, sold, or smuggled (trafficked) any controlled substances, illegal drugs, narcotics, or drug paraphernalia in violation of any law or regulation of a U.S. state, the United States, or a foreign country?",
          "¿Fabricado, cultivado, producido, distribuido, despachado, vendido o contrabandeado (traficado) sustancias controladas, drogas ilegales, narcóticos o parafernalia de drogas en violación de cualquier ley o reglamento de un estado de EE. UU., de los Estados Unidos o de un país extranjero?", explain="Part 9, Item 17.b")
    yesno(b, "sham_marriage", "Part 9, Item 17.c", "Married someone in order to obtain an immigration benefit?", "¿Te has casado con alguien para obtener un beneficio migratorio?", explain="Part 9, Item 17.c")
    yesno(b, "bigamy", "Part 9, Item 17.d", "Been married to more than one person at the same time?", "¿Has estado casado(a) con más de una persona al mismo tiempo?", explain="Part 9, Item 17.d")
    qpage("p9_conduct2", T("Other conduct (2 of 2)", "Otra conducta (2 de 2)"))
    intro(b, "p9_17b_intro", "Have you EVER:", "¿Alguna vez has:")
    yesno(b, "smuggling", "Part 9, Item 17.e", "Helped anyone to enter, or try to enter, the United States illegally?", "¿Ayudado a alguien a entrar, o intentar entrar, ilegalmente a los Estados Unidos?", explain="Part 9, Item 17.e")
    yesno(b, "gambling", "Part 9, Item 17.f", "Gambled illegally or received income from illegal gambling?", "¿Apostado ilegalmente o recibido ingresos del juego ilegal?", explain="Part 9, Item 17.f")
    yesno(b, "support_failure", "Part 9, Item 17.g", "Failed to support your dependents (pay child support) or to pay alimony (court-ordered financial support after divorce or separation)?",
          "¿Dejado de mantener a tus dependientes (pagar manutención de hijos) o de pagar pensión alimenticia (apoyo económico ordenado por un tribunal después de un divorcio o separación)?", explain="Part 9, Item 17.g")
    yesno(b, "benefit_misrep", "Part 9, Item 17.h", "Made any misrepresentation to obtain any public benefit in the United States?", "¿Hecho alguna declaración falsa para obtener algún beneficio público en los Estados Unidos?", explain="Part 9, Item 17.h")

    qpage("p9_false", T("Statements and immigration proceedings", "Declaraciones y procesos migratorios"))
    yesno(b, "false_info", "Part 9, Item 18", "Have you EVER given any U.S. Government officials any information or documentation that was false, fraudulent, or misleading?",
          "¿Alguna vez has dado a algún funcionario del Gobierno de EE. UU. información o documentación que fuera falsa, fraudulenta o engañosa?", explain="Part 9, Item 18")
    yesno(b, "lied_entry", "Part 9, Item 19", "Have you EVER lied to any U.S. Government officials to gain entry or admission into the United States or to gain immigration benefits while in the United States?",
          "¿Alguna vez has mentido a algún funcionario del Gobierno de EE. UU. para lograr la entrada o admisión a los Estados Unidos o para obtener beneficios migratorios mientras estabas en los Estados Unidos?", explain="Part 9, Item 19")
    yesno(b, "removed", "Part 9, Item 20", "Have you EVER been removed or deported from the United States?", "¿Alguna vez has sido removido(a) o deportado(a) de los Estados Unidos?", explain="Part 9, Item 20")
    yesno(b, "proceedings", "Part 9, Item 21", "Have you EVER been placed in removal, rescission, or deportation proceedings?", "¿Alguna vez has sido puesto(a) en procedimientos de remoción, rescisión o deportación?", explain="Part 9, Item 21")

    qpage("p9_selective", T("Selective Service", "Servicio Selectivo"),
          desc=T("Federal law requires nearly all people born as male who are either U.S. citizens or immigrants, 18 through 25 years of age, to register with Selective Service. See www.sss.gov.", "La ley federal requiere que casi todas las personas nacidas como varones, ciudadanas o inmigrantes, de 18 a 25 años, se registren en el Servicio Selectivo. Ver www.sss.gov."))
    yesno(b, "selective_male", "Part 9, Item 22.a", "Are you a male who lived in the United States at any time between your 18th and 26th birthdays? (Do not select “Yes” if you were a lawful nonimmigrant for all of that time period.)",
          "¿Eres varón y viviste en los Estados Unidos en algún momento entre tus 18 y 26 años? (No selecciones “Sí” si fuiste no inmigrante legal durante todo ese período.)")
    yesno(b, "selective_registered", "Part 9, Item 22.b", "If you answered “Yes” to Item Number 22.a., did you register for the Selective Service?", "Si respondiste “Sí” al punto 22.a., ¿te registraste en el Servicio Selectivo?",
          detail=("USCIS note on the form: if you answered “No” to this question, see the Specific Instructions by Item Number, Part 9, of the Instructions for more information.", "Nota de USCIS en el formulario: si respondiste “No” a esta pregunta, consulta las Specific Instructions by Item Number, Parte 9, de las Instrucciones para más información."))
    b.field("selective_date", "date", ("Date you registered", "Fecha en que te registraste"), ref="Part 9, Item 22.c", req=True, date_rule="past", width="half")
    b.field("selective_number", "short_answer", ("Selective Service Number", "Número del Servicio Selectivo"), ref="Part 9, Item 22.c", req=True, maxlen=10, width="half")
    b.rule("show_field", "selective_registered", [("selective_male", "equals", "yes")])
    for n in ("selective_date", "selective_number"):
        b.rule("show_field", n, [("selective_registered", "equals", "yes")])

    qpage("p9_draft", T("Military draft and service", "Servicio militar obligatorio"))
    yesno(b, "left_draft", "Part 9, Item 23", "Have you EVER left the United States to avoid being drafted in the U.S. armed forces?", "¿Alguna vez has salido de los Estados Unidos para evitar ser reclutado(a) en las fuerzas armadas de EE. UU.?", explain="Part 9, Item 23")
    yesno(b, "draft_exemption", "Part 9, Item 24", "Have you EVER applied for any kind of exemption from military service in the U.S. armed forces?", "¿Alguna vez has solicitado algún tipo de exención del servicio militar en las fuerzas armadas de EE. UU.?", explain="Part 9, Item 24")
    yesno(b, "served_us", "Part 9, Item 25", "Have you EVER served in the U.S. armed forces?", "¿Alguna vez has servido en las fuerzas armadas de EE. UU.?")

    qpage("p9_current_mil", T("Your U.S. military service", "Tu servicio militar en EE. UU."))
    yesno(b, "mil_current", "Part 9, Item 26.a", "Are you currently a member of the U.S. armed forces?", "¿Eres actualmente miembro de las fuerzas armadas de EE. UU.?")
    yesno(b, "mil_deploy", "Part 9, Item 26.b", "If you answered “Yes” to Item Number 26.a., are you scheduled to deploy outside the United States, including to a vessel, within the next 3 months?", "Si respondiste “Sí” al punto 26.a., ¿está programado que te despliegues fuera de los Estados Unidos, incluido a un buque, dentro de los próximos 3 meses?",
          help=("Call the Military Help Line at 877-247-4645 if you transfer to a new duty station after you file, including if you are deployed outside the United States or to a vessel.", "Llama a la Línea de Ayuda Militar al 877-247-4645 si te transfieren a una nueva base después de presentar, incluso si te despliegan fuera de los Estados Unidos o a un buque."))
    yesno(b, "mil_stationed", "Part 9, Item 26.c", "If you answered “Yes” to Item Number 26.a., are you currently stationed outside the United States?", "Si respondiste “Sí” al punto 26.a., ¿estás actualmente destacado(a) fuera de los Estados Unidos?")
    yesno(b, "mil_former_abroad", "Part 9, Item 26.d", "If you answered “No” to Item Number 26.a., are you a former U.S. military service member who is currently residing outside of the U.S.?", "Si respondiste “No” al punto 26.a., ¿eres un ex miembro del servicio militar de EE. UU. que actualmente reside fuera de los EE. UU.?")
    for n in ("mil_deploy", "mil_stationed"):
        b.rule("show_field", n, [("mil_current", "equals", "yes")])
    b.rule("show_field", "mil_former_abroad", [("mil_current", "equals", "no")])
    b.rule("show_page", "p9_current_mil", [("served_us", "equals", "yes")])

    qpage("p9_mil_history", T("Your U.S. military record", "Tu historial militar en EE. UU."))
    yesno(b, "mil_alien_discharge", "Part 9, Item 27", "Have you EVER been discharged from training or service in the U.S. armed forces because you were an alien?", "¿Alguna vez has sido dado(a) de baja del entrenamiento o del servicio en las fuerzas armadas de EE. UU. por ser extranjero(a)?", explain="Part 9, Item 27")
    yesno(b, "mil_courtmartial", "Part 9, Item 28", "Have you EVER been court-martialed or have you received a discharge characterized as other than honorable, bad conduct, or dishonorable, while in the U.S. armed forces?", "¿Alguna vez has sido sometido(a) a una corte marcial o has recibido una baja caracterizada como distinta de honorable, mala conducta o deshonrosa mientras estabas en las fuerzas armadas de EE. UU.?", explain="Part 9, Item 28")
    yesno(b, "mil_desertion", "Part 9, Item 29", "Have you EVER deserted from the U.S. armed forces?", "¿Alguna vez has desertado de las fuerzas armadas de EE. UU.?", explain="Part 9, Item 29")
    b.rule("show_page", "p9_mil_history", [("served_us", "equals", "yes")])

    qpage("p9_nobility", T("Titles of nobility", "Títulos de nobleza"))
    yesno(b, "nobility", "Part 9, Item 30.a", "Do you now have, or did you EVER have, a hereditary title or an order of nobility in any foreign country?", "¿Tienes ahora, o tuviste alguna vez, un título hereditario o una orden de nobleza en algún país extranjero?", explain="Part 9, Item 30.a")
    yesno(b, "nobility_giveup", "Part 9, Item 30.b", "If you answered “Yes” to Item Number 30.a., are you willing to give up any inherited titles or orders of nobility that you have in a foreign country at your naturalization ceremony?",
          "Si respondiste “Sí” al punto 30.a., ¿estás dispuesto(a) a renunciar a cualquier título heredado u orden de nobleza que tengas en un país extranjero en tu ceremonia de naturalización?")
    b.field("nobility_titles", "short_answer", ("List your titles", "Indica tus títulos"), ref="Part 9, Item 30.b (titles)", req=True)
    for n in ("nobility_giveup", "nobility_titles"):
        b.rule("show_field", n, [("nobility", "equals", "yes")])

    qpage("p9_oath1", T("Constitution and Oath of Allegiance", "Constitución y Juramento de Lealtad"))
    yesno(b, "support_constitution", "Part 9, Item 31", "Do you support the Constitution and form of Government of the United States?", "¿Apoyas la Constitución y la forma de Gobierno de los Estados Unidos?")
    yesno(b, "understand_oath", "Part 9, Item 32", "Do you understand the full Oath of Allegiance to the United States (see Part 16, Oath of Allegiance)?", "¿Entiendes el Juramento de Lealtad completo a los Estados Unidos (ver Parte 16, Oath of Allegiance)?",
          detail=(OATH_EN, OATH_ES))
    yesno(b, "oath_unable", "Part 9, Item 33", "Are you unable to take the Oath of Allegiance because of a physical or developmental disability or mental impairment?", "¿No puedes prestar el Juramento de Lealtad debido a una discapacidad física o del desarrollo o a un impedimento mental?",
          detail=("USCIS note on the form: if you answer “Yes,” skip Item Numbers 34 – 37 and see the Legal Guardian, Surrogate, or Designated Representative section in the Instructions.", "Nota de USCIS en el formulario: si respondes “Sí”, omite los puntos 34 a 37 y consulta la sección Legal Guardian, Surrogate, or Designated Representative de las Instrucciones."))
    qpage("p9_oath2", T("Willingness to take the Oath", "Disposición para prestar el Juramento"))
    yesno(b, "willing_oath", "Part 9, Item 34", "Are you willing to take the full Oath of Allegiance to the United States?", "¿Estás dispuesto(a) a prestar el Juramento de Lealtad completo a los Estados Unidos?")
    yesno(b, "willing_arms", "Part 9, Item 35", "If the law requires it, are you willing to bear arms (carry weapons) on behalf of the United States?", "Si la ley lo exige, ¿estás dispuesto(a) a portar armas en nombre de los Estados Unidos?")
    yesno(b, "willing_noncombat", "Part 9, Item 36", "If the law requires it, are you willing to perform noncombatant services (do something that does not include fighting in a war) in the U.S. armed forces?", "Si la ley lo exige, ¿estás dispuesto(a) a prestar servicios no combatientes (hacer algo que no incluya luchar en una guerra) en las fuerzas armadas de EE. UU.?")
    yesno(b, "willing_civilian", "Part 9, Item 37", "If the law requires it, are you willing to perform work of national importance under civilian direction (do non-military work that the U.S. Government says is important to the country)?", "Si la ley lo exige, ¿estás dispuesto(a) a realizar trabajo de importancia nacional bajo dirección civil (hacer trabajo no militar que el Gobierno de EE. UU. considera importante para el país)?")
    note(b, "oath_note", "USCIS note on the form: if you answer “No” to any question except Item 33, see the Oath of Allegiance section of the Instructions. OG will review it with you.", "Nota de USCIS en el formulario: si respondes “No” a cualquier pregunta excepto el punto 33, consulta la sección Oath of Allegiance de las Instrucciones. OG lo revisará contigo.")
    b.rule("show_page", "p9_oath2", [("oath_unable", "equals", "no")])

    # ============================================================ Part 10
    new_page(b, "fee", T("Request for a fee reduction", "Solicitud de reducción de tarifa"),
             T("For information about fees, fee waivers and reduced fees, see Form G-1055, Fee Schedule, at www.uscis.gov/g-1055.", "Para información sobre tarifas, exenciones y tarifas reducidas, consulta el Formulario G-1055, Fee Schedule, en www.uscis.gov/g-1055."), group="additional")
    b.field("fee_request", "single_choice", ("Is your household income less than or equal to 400% of the Federal Poverty Guidelines?", "¿Los ingresos de tu hogar son iguales o menores al 400% de las Guías Federales de Pobreza?"), ref="Part 10, Item 1", req=True, opts=YES_NO,
            help=("If “Yes,” answer the next questions to request a reduced fee. See the Instructions for the required documentation.", "Si es “Sí”, responde las siguientes preguntas para solicitar una tarifa reducida. Consulta las Instrucciones para ver la documentación requerida."))
    b.field("household_income", "number", ("Total household income", "Ingreso total del hogar"), ref="Part 10, Item 2", req=True, minv=0, maxv=9999999, width="half")
    b.field("household_size", "number", ("My household size is", "El tamaño de mi hogar es"), ref="Part 10, Item 3", req=True, minv=1, maxv=99, width="half")
    b.field("household_earners", "number", ("Total number of household members earning income, including yourself", "Número total de miembros del hogar que generan ingresos, incluyéndote"), ref="Part 10, Item 4", req=True, minv=0, maxv=99, width="half")
    b.field("head_of_household", "single_choice", ("I am the head of household", "Soy el jefe(a) del hogar"), ref="Part 10, Item 5.a", req=True, opts=YES_NO)
    b.field("head_name", "short_answer", ("Name of head of household", "Nombre del jefe(a) del hogar"), ref="Part 10, Item 5.b", req=True)
    for n in ("household_income", "household_size", "household_earners", "head_of_household"):
        b.rule("show_field", n, [("fee_request", "equals", "yes")])
    b.rule("show_field", "head_name", [("fee_request", "equals", "yes"), ("head_of_household", "equals", "no")], "all")

    # ============================================================ Part 11 / 12
    new_page(b, "contact", T("Your contact information", "Tu información de contacto"), group="contact")
    b.field("phone_daytime", "phone", ("Daytime telephone number", "Teléfono de día"), ref="Part 11, Item 1", req=True, width="half")
    b.field("phone_mobile", "phone", ("Mobile telephone number (if any)", "Teléfono móvil (si tienes)"), ref="Part 11, Item 2", width="half")
    b.field("contact_email", "email", ("Email address (if any)", "Correo electrónico (si tienes)"), ref="Part 11, Item 3")
    b.fields["contact_email"].required = False

    new_page(b, "language", T("Language", "Idioma"), group="contact")
    b.field("english_or_interpreter", "single_choice", ("Which of these is true for you?", "¿Cuál de estas opciones es cierta para ti?"), ref="Part 11 (certification wording)", req=True,
            opts=[("english", "I can read and understand English, and I have read and understand every question and instruction on this application and my answer to every question.",
                   "Puedo leer y entender inglés, y he leído y entendido cada pregunta e instrucción de esta solicitud y mi respuesta a cada pregunta."),
                  ("interpreter", "An interpreter read to me every question and instruction on this application and my answer to every question in a language in which I am fluent, and I understood everything.",
                   "Un intérprete me leyó cada pregunta e instrucción de esta solicitud y mi respuesta a cada pregunta en un idioma en el que soy fluido(a), y lo entendí todo.")])
    new_page(b, "interp", T("Your interpreter", "Tu intérprete"), T("Information about the interpreter (Part 12 of the form).", "Información del intérprete (Parte 12 del formulario)."), group="contact")
    b.field("int_family", "short_answer", ("Interpreter's family name (last name)", "Apellido del intérprete"), ref="Part 12, Item 1", req=True, width="half")
    b.field("int_given", "short_answer", ("Interpreter's given name (first name)", "Nombre del intérprete"), ref="Part 12, Item 1", req=True, width="half")
    b.field("int_org", "short_answer", ("Interpreter's business or organization name (if any)", "Empresa u organización del intérprete (si aplica)"), ref="Part 12, Item 2")
    b.field("int_phone", "phone", ("Interpreter's daytime telephone number", "Teléfono de día del intérprete"), ref="Part 12, Item 3", req=True, width="half")
    b.field("int_mobile", "phone", ("Interpreter's mobile telephone number (if any)", "Teléfono móvil del intérprete (si tiene)"), ref="Part 12, Item 5", width="half")
    b.field("int_email", "email", ("Interpreter's email address (if any)", "Correo electrónico del intérprete (si tiene)"), ref="Part 12, Item 4")
    b.fields["int_email"].required = False
    b.field("int_language", "short_answer", ("Language the interpreter used", "Idioma que usó el intérprete"), ref="Part 12 (language of certification)", req=True)
    for name, value in {"int_family": "@biz:INTERPRETER_LAST_NAME", "int_given": "@biz:INTERPRETER_FIRST_NAME", "int_org": "@biz:INTERPRETER_ORG",
                        "int_phone": "@biz:INTERPRETER_PHONE", "int_email": "@biz:INTERPRETER_EMAIL"}.items():
        b.fields[name].default_value = value
    b.rule("show_page", "interp", [("english_or_interpreter", "equals", "interpreter")])

    new_page(b, "additional", T("Anything else?", "¿Algo más?"), group="additional")
    b.field("additional_information", "long_answer", ("Is there anything else you want us to know?", "¿Hay algo más que quieras que sepamos?"), ref="Part 14. Additional Information",
            help=("For example: other dates of birth you have used, other countries of citizenship, or anything that did not fit a question. If it relates to a specific question, say which one.",
                  "Por ejemplo: otras fechas de nacimiento que hayas usado, otros países de ciudadanía, o algo que no encajó en ninguna pregunta. Si se relaciona con una pregunta específica, dinos cuál."))

    # ============================================================ documents
    new_page(b, "documents", T("Documents", "Documentos"),
             T("Upload what you have now; you can add more before you send. We separate what OG asks for from what the form itself mentions.", "Sube lo que tengas ahora; puedes agregar más antes de enviar. Separamos lo que pide OG de lo que menciona el propio formulario."), group="documents")
    from app.seed_i90_refine import _label, _tip

    single = dict(files=("pdf,jpg,jpeg,png", 1, 10))
    multi = dict(files=("pdf,jpg,jpeg,png", 5, 10))
    b.field("docs_og_label", "paragraph", ("", ""), content=(_label("What OG asks for", "To prepare your application. These are OG's requests, not a list of what USCIS requires."), _label("Lo que pide OG", "Para preparar tu solicitud. Son solicitudes de OG, no una lista de lo que exige USCIS.")))
    b.field("docs_tip", "paragraph", ("", ""), content=(
        _tip("Make sure the whole document is visible, the text is readable, and there is no glare or cropped information."),
        _tip("Asegúrate de que todo el documento se vea, el texto sea legible y no haya reflejos ni partes cortadas.")))
    b.field("green_card_front", "file_upload", ("Permanent Resident Card — Front", "Tarjeta de Residente Permanente — Frente"), ref="OG addition", note="OG document-collection request.",
            help=("A clear, complete, readable photo of the front of your Green Card.", "Una foto clara, completa y legible del frente de tu Green Card."), **single)
    b.field("green_card_back", "file_upload", ("Permanent Resident Card — Back", "Tarjeta de Residente Permanente — Reverso"), ref="OG addition", note="OG document-collection request.",
            help=("A clear, complete, readable photo of the back of your Green Card.", "Una foto clara, completa y legible del reverso de tu Green Card."), **single)
    b.field("id_document", "file_upload", ("Passport or government photo ID", "Pasaporte o identificación oficial con foto"), ref="OG addition", note="OG document-collection request.",
            help=("Optional, but it helps OG check your name and dates.", "Opcional, pero ayuda a OG a verificar tu nombre y fechas."), **single)
    b.field("docs_form_label", "paragraph", ("", ""), content=(_label("Documents the form mentions", "Only the ones that apply to your answers appear here."), _label("Documentos que menciona el formulario", "Aquí solo aparecen los que aplican según tus respuestas.")))
    b.field("marriage_certificate", "file_upload", ("Current marriage certificate", "Acta de matrimonio actual"), ref="Part 5 (note)", note="Form note: provide current marriage certificate and any divorce/annulment/death certificate showing prior marriages were terminated.",
            help=("The form asks you to provide your current marriage certificate.", "El formulario pide que presentes tu acta de matrimonio actual."), **multi)
    b.field("prior_marriage_docs", "file_upload", ("Divorce decree, annulment decree or death certificate for your prior marriages", "Decreto de divorcio, decreto de anulación o acta de defunción de tus matrimonios anteriores"), ref="Part 5 (note)",
            note="Form note (Part 5).", help=("Showing that your prior marriages were terminated, if applicable.", "Que demuestren que tus matrimonios anteriores terminaron, si aplica."), **multi)
    b.field("spouse_prior_marriage_docs", "file_upload", ("Divorce decrees, annulment decrees or death certificates for your spouse's prior marriages", "Decretos de divorcio, anulación o actas de defunción de los matrimonios anteriores de tu cónyuge"), ref="Part 5, Item 7 (note)",
            note="Form note (Part 5, Item 7).", **multi)
    b.field("n648_doc", "file_upload", ("Form N-648, Medical Certification for Disability Exceptions", "Formulario N-648, Certificación médica para excepciones por discapacidad"), ref="Part 2, Item 11 (note)",
            note="Form note: submit a completed Form N-648 if Item 11 is Yes.", **single)
    b.field("crime_evidence", "file_upload", ("Evidence related to your answers about arrests, offenses or other conduct", "Evidencia relacionada con tus respuestas sobre arrestos, infracciones u otra conducta"), ref="Part 9 (note)",
            note="Form note: submit evidence to support your answers (Items 15, 17.a–19).", help=("The form asks you to submit evidence to support these answers. OG will tell you what is useful.", "El formulario pide presentar evidencia que respalde estas respuestas. OG te dirá qué es útil."), **multi)
    b.field("trip_evidence", "file_upload", ("Evidence for trips that lasted more than 6 months (if any)", "Evidencia de viajes que duraron más de 6 meses (si los hubo)"), ref="Part 8 (note)",
            note="Form note: see Required Evidence – Continuous Residence for trips over 6 months.", **multi)
    b.field("fee_docs", "file_upload", ("Income documents for your fee reduction request", "Documentos de ingresos para tu solicitud de reducción de tarifa"), ref="Part 10, Item 1 (note)",
            note="Form note: see Instructions for required documentation.", **multi)
    b.field("docs_other_label", "paragraph", ("", ""), content=(_label("Other documents", "Do you have any other document that could help us?"), _label("Otros documentos", "¿Tienes algún otro documento que pueda ayudarnos?")))
    b.field("documents_other", "file_upload", ("Other Supporting Documents (optional)", "Otros documentos de apoyo (opcional)"), ref="OG addition", files=("pdf,jpg,jpeg,png", 10, 10))
    b.rule("show_field", "marriage_certificate", [("marital_status", "not_equals", "single")])
    show_any(b, "prior_marriage_docs", [[("marital_status", "equals", v)] for v in ("divorced", "widowed", "annulled")] + [[("times_married", "greater_than", "1")]])
    b.rule("show_field", "spouse_prior_marriage_docs", [("spouse_times_married", "greater_than", "1")])
    b.rule("show_field", "n648_doc", [("disability", "equals", "yes")])
    show_any(b, "crime_evidence", [[(n, "equals", "yes")] for n in ("offense_not_arrested", "offense_arrested", "prostitution", "drugs", "sham_marriage", "bigamy", "smuggling", "gambling", "support_failure", "benefit_misrep", "false_info", "lied_entry")])
    b.rule("show_field", "trip_evidence", [("trips", "is_not_empty", "")])
    b.rule("show_field", "fee_docs", [("fee_request", "equals", "yes")])

    # ============================================================ confirm
    new_page(b, "confirm", T("Confirm and Send to OG", "Confirma y envía a OG"), group="confirm",
             desc=T("Review your information and confirm that it is complete and accurate. OG Multiservices will prepare your Form N-400 and guide you through the required signature based on how your application will be filed.",
                    "Revisa tu información y confirma que esté completa y correcta. OG Multiservices preparará tu Formulario N-400 y te indicará cómo completar la firma requerida según la forma en que se presente tu solicitud."))
    note(b, "confirm_note", "Online filing may use an electronic signing process. Paper filings require the appropriate signature on the application.",
         "Las solicitudes presentadas en línea pueden utilizar un proceso de firma electrónica. Las solicitudes en papel requieren la firma correspondiente en el formulario.")
    b.field("preparer_request", "consent", ("Request for preparation", "Solicitud de preparación"), ref="Part 11 (preparer request)", note="Preparer prepared the application at the applicant's request.", req=True, content=(
        "I ask OG Multiservices to prepare my Form N-400 based on the information I provided or authorized.",
        "Solicito a OG Multiservices que prepare mi Formulario N-400 con base en la información que proporcioné o autoricé."))
    b.field("confirm_accurate", "consent", ("Accuracy confirmation", "Confirmación de exactitud"), ref="Part 11 (certification wording)", note="Customer confirmation only; not a signature.", req=True, content=(
        "I confirm that the information I provided is complete, true, and correct to the best of my knowledge.",
        "Confirmo que la información que proporcioné es completa, verdadera y correcta según mi leal saber y entender."))
    return b


def ensure_n400_intake():
    """Create the production N-400 intake and connect it to the Naturalization service.
    Rebuilt in place only while it has no submissions."""
    service = (
        Service.query.join(ServiceCategory)
        .filter(ServiceCategory.slug == "immigration", Service.slug == "naturalization-citizenship")
        .first()
    )
    if not service:
        return False
    form = Form.query.filter_by(slug=N400_SLUG).first()
    if form:
        return False
    form = Form(slug=N400_SLUG, name_admin="N-400 Client Intake")
    db.session.add(form)
    form.form_type = "service_intake"
    form.status = "published"
    form.source_form_name = SOURCE_NAME
    form.source_edition = SOURCE_EDITION
    form.version = 1
    form.published_at = datetime.utcnow()
    form.title_en, form.title_es = "Naturalization — Form N-400", "Naturalización — Formulario N-400"
    form.description_en = "Guided intake for OG Multiservices to prepare your Form N-400. Your progress is saved automatically."
    form.description_es = "Solicitud guiada para que OG Multiservices prepare tu Formulario N-400. Tu progreso se guarda automáticamente."
    form.submit_label_en, form.submit_label_es = "Send to OG", "Enviar a OG"
    form.success_message_en = "OG Multiservices has your information and will review it. We'll contact you if we need anything else."
    form.success_message_es = "OG Multiservices tiene tu información y la revisará. Te contactaremos si necesitamos algo más."
    form.show_progress = True
    form.features_json = json.dumps({"completeness_check": True, "consistency": "n400", "sections": SECTIONS}, ensure_ascii=False)
    db.session.flush()
    build_n400(form)
    service.requires_intake = True
    service.form_id = form.id
    service.requires_account = True
    service.intake_label = "N-400 Client Intake"
    db.session.commit()
    return True
