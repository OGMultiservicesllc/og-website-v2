"""Form I-765 Client Intake — the sixth production Smart Intake, built natively on the Case + Person architecture.

SOURCE OF TRUTH: the supplied USCIS "Form I-765, Application for Employment Authorization", Edition 08/21/25 (OMB No. 1615-0040,
expires 08/31/2027), 7 pages, Parts 1-6. Item numbers are the ones printed on that PDF; every question carries its Part/Item in
`FormField.source_ref` (admin-only).

Part map (as printed):
  Part 1   Reason for Applying          Item 1.a initial · 1.b replacement / correction NOT due to USCIS error · 1.c renewal
  Part 2   Information About You        Items 1.a-1.c full legal name · 2-4 other names (three name boxes) · 5.a-5.f U.S. mailing address · 6 mailing = physical?
                                        · 7.a-7.e U.S. physical address · 8 A-Number · 9 USCIS Online Account · 10 sex · 11 marital status
                                        · 12 previously filed Form I-765? · 13 SSN · 14.a-14.b countries of citizenship · 15.a-15.c place of birth
                                        · 16 date of birth · 17 I-94 · 18 passport (most recently issued) · 19 travel document · 20 issuing country
                                        · 21 expiration · 22 date of last arrival · 23 place · 24 status at last arrival · 25 current status
                                        · 26 SEVIS · 27 ELIGIBILITY CATEGORY · 28.a-c (c)(3)(C) STEM OPT · 29 (c)(26) · 30 (c)(8) · 31.a-b (c)(35)/(c)(36)
  Part 3   Applicant's Statement, Contact, Certification, Signature   1.a/1.b statement · 2 preparer · 3-5 contact · 6 ABC · 7.a-7.b signature
  Part 4   Interpreter                 1.a-1.b name · 2 organization · 3.a-3.h mailing address · 4-6 contact · certification · 7.a-7.b signature
  Part 5   Preparer                    1.a-1.b name · 2 organization · 3.a-3.h mailing address · 4-6 contact · 7.a/7.b statement · certification · 8.a-8.b signature
  Part 6   Additional Information      1-2 name and A-Number · 3-7 (page / part / item / text)

NOT customer questions: every signature and date of signature (Part 3 Item 7, Part 4 Item 7, Part 5 Item 8), the G-28 box and every
"For USCIS Use Only" box. Part 5 Item 7 (the preparer's statement) comes from the central OG configuration, never a customer answer.

THE ELIGIBILITY CATEGORY (Item 27) IS NEVER DECIDED BY THIS INTAKE. It stores what the customer or OG says, in the printed boxes, and
"Not sure — OG will review" is always available. The category-specific questions (Items 28-31) appear only for the exact category entered.
The Form I-765 Instructions are NOT part of the supplied PDF, so no document request claims USCIS requires it.
"""

import json
from datetime import datetime

from app.extensions import db
from app.models import Form, Service, ServiceCategory
from app.seed_i130 import page, records, where
from app.seed_i485 import (UNSURE, WHERE_A, WHERE_ACCT, WHERE_I94, WHERE_SSN, YN_UNSURE, block_pair, choice, kp, mark_block_fields, only_if)
from app.seed_i90 import STATE_OPTIONS, UNIT_TYPES, YES_NO, Builder, _address_fields
from app.seed_i90_refine import _label, _tip
from app.seed_n400 import note, show_page_any

I765_SLUG = "i-765-client-intake"
SOURCE_NAME = "I-765"
SOURCE_EDITION = "08/21/25"
NEVER = ("a_family", "equals", "__never__")

SECTIONS = [
    {"key": "before", "title": {"en": "Before You Begin", "es": "Antes de empezar"}},
    {"key": "reason", "title": {"en": "Reason for Applying", "es": "Motivo de la solicitud"}},
    {"key": "applicant", "title": {"en": "About the Applicant", "es": "Sobre el solicitante"}},
    {"key": "addresses", "title": {"en": "Addresses", "es": "Direcciones"}},
    {"key": "identifiers", "title": {"en": "Identifiers", "es": "Identificadores"}},
    {"key": "citizenship_birth", "title": {"en": "Citizenship & Birth", "es": "Ciudadanía y nacimiento"}},
    {"key": "arrival", "title": {"en": "Last U.S. Arrival", "es": "Última llegada a EE. UU."}},
    {"key": "category", "title": {"en": "Employment Authorization Category", "es": "Categoría de autorización de empleo"}},
    {"key": "statement", "title": {"en": "Applicant Statement", "es": "Declaración del solicitante"}},
    {"key": "interpreter", "title": {"en": "Interpreter", "es": "Intérprete"}},
    {"key": "preparer", "title": {"en": "Preparer", "es": "Preparador"}},
    {"key": "additional", "title": {"en": "Additional Information", "es": "Información adicional"}},
    {"key": "documents", "title": {"en": "Documents", "es": "Documentos"}},
    {"key": "confirm", "title": {"en": "Confirmation", "es": "Confirmación"}},
]
CONTEXTS = {
    "applicant": {"title": {"en": "Applicant", "es": "Solicitante"}, "subtitle": {"en": "The person applying for employment authorization.", "es": "La persona que solicita la autorización de empleo."},
                  "tone": "accent", "icon": "person"},
}
CONTEXT_ROLES = {"applicant": "applicant"}

WHERE_PASSPORT_765 = ("This is the passport you were most recently issued (not necessarily the one you used to arrive). The number is on its photo page.",
                      "Es el pasaporte que se te emitió más recientemente (no necesariamente el que usaste para llegar). El número está en la página con la foto.")
WHERE_SEVIS = ("Only students and exchange visitors (for example F-1, M-1 or J-1) have a SEVIS number. It starts with “N” and appears on the Form I-20 or DS-2019. If you have none, choose No.",
               "Solo los estudiantes y visitantes de intercambio (por ejemplo F-1, M-1 o J-1) tienen un número SEVIS. Empieza con “N” y aparece en el Formulario I-20 o DS-2019. Si no tienes, elige No.")
RECEIPT_MSG = ("A receipt number has 13 letters and digits (for example the 3 letters and 10 digits on a Form I-797 notice).",
               "Un número de recibo tiene 13 letras y dígitos (por ejemplo las 3 letras y 10 dígitos de una notificación I-797).")
COURTESY = "OFFICIAL TEXT = the English as printed on Form I-765 edition 08/21/25. The Spanish is OG's courtesy translation only (not USCIS text); the English prevails."
REVIEW_FLAG = ("OG will look at this answer with you.", "OG revisará esta respuesta contigo.")


def txt(en, es, cls="text-[15px] leading-relaxed text-slate-700"):
    return (f'<span class="block {cls}">{en}</span>', f'<span class="block {cls}">{es}</span>')


def head(en, es):
    return txt(en, es, "text-[15px] font-bold text-brand-800 pt-2")


def para(b, name, en, es):
    b.field(name, "paragraph", ("", ""), content=(en, es))


def calc_field(b, name, label_en, label_es, ref):
    """Hidden calculated / configured answer (never asked); shown only in Review, Admin and the snapshot."""
    b.field(name, "short_answer", (label_en, label_es), ref=ref, note="Calculated or configured by the platform; not a question.")
    kp(b, name)
    b.rule("show_field", name, [NEVER])


def only_missing(b, key, names):
    """On a shared block's edit step, show a field only when it is the applicant's turn to give it: nothing was known (`_avail == no`), they chose to
    edit, or the case could not supply that detail (`<key>_missing`, computed before the applicant answers). A confirmed value is never asked again."""
    from app.case_types import FORM_CASE_CONFIG

    block = FORM_CASE_CONFIG["I-765"]["blocks"][key]
    owner = {}
    for fact_key, target in block["fields"].items():
        if isinstance(target, str):
            owner[target] = fact_key
        elif isinstance(target, dict) and "address_prefix" in target:
            for n in names:
                if n.startswith(target["address_prefix"] + "_"):
                    owner[n] = fact_key
    for n in names:
        b.rule("show_field", n, [(f"{key}_avail", "equals", "no")])
        b.rule("show_field", n, [(key, "equals", "edit")])
        if n in owner:
            b.rule("show_field", n, [(key, "equals", "correct"), (f"{key}_missing", "selected", owner[n])])


def us_address(b, prefix, ref, *, in_care_of=False, required=True):
    """A U.S. address (Part 2 Items 5 and 7 are U.S. addresses)."""
    if in_care_of:
        b.field(f"{prefix}_in_care_of", "short_answer", ("In care of name (if any)", "A cargo de (si aplica)"), ref=ref + " — In Care Of Name", maxlen=34)
    b.field(f"{prefix}_street", "short_answer", ("Street number and name", "Número y nombre de la calle"), ref=ref + " — Street Number and Name", req=required)
    b.field(f"{prefix}_unit_type", "dropdown", ("Unit type (if any)", "Tipo de unidad (si aplica)"), ref=ref + " — Apt./Ste./Flr.", opts=UNIT_TYPES, width="half")
    b.field(f"{prefix}_unit_number", "short_answer", ("Unit number", "Número de unidad"), ref=ref + " — Number", width="half")
    b.field(f"{prefix}_city", "short_answer", ("City or town", "Ciudad o pueblo"), ref=ref + " — City or Town", req=required)
    b.field(f"{prefix}_state", "dropdown", ("State", "Estado"), ref=ref + " — State", req=required, opts=STATE_OPTIONS, width="half")
    b.field(f"{prefix}_zip", "short_answer", ("ZIP code", "Código postal (ZIP)"), ref=ref + " — ZIP Code", req=required, width="half", pattern=r"\d{5}", maxlen=5,
            msg=("Enter a 5-digit ZIP code.", "Ingresa un ZIP de 5 dígitos."))


# ------------------------------------------------------------------ verbatim source texts (English = official; Spanish = OG courtesy translation)
CERT_EN = [
    "Copies of any documents I have submitted are exact photocopies of unaltered, original documents, and I understand that USCIS may require that I submit original documents to USCIS at a later date. Furthermore, I authorize the release of any information from any and all of my records that USCIS may need to determine my eligibility for the immigration benefit that I seek. I furthermore authorize release of information contained in this application, in supporting documents, and in my USCIS records, to other entities and persons where necessary for the administration and enforcement of U.S. immigration law.",
    "I understand that USCIS may require me to appear for an appointment to take my biometrics (fingerprints, photograph, and/or signature) and, at that time, if I am required to provide biometrics, I will be required to sign an oath reaffirming that: <strong>1)</strong> I reviewed and provided or authorized all of the information in my application; and <strong>2)</strong> I understood all of the information contained in, and submitted with, my application; and <strong>3)</strong> All of this information was complete, true, and correct at the time of filing.",
    "I certify, under penalty of perjury, that I provided or authorized all of the information in my application, I understand all of the information contained in, and submitted with, my application, and that all of this information is complete, true, and correct.",
    "<strong>NOTE TO ALL APPLICANTS:</strong> If you do not completely fill out this application or fail to submit required documents listed in the Instructions, USCIS may deny your application.",
]
CERT_ES = [
    "Las copias de cualquier documento que he presentado son fotocopias exactas de documentos originales sin alterar, y entiendo que USCIS puede exigir que presente documentos originales a USCIS en una fecha posterior. Además, autorizo la divulgación de cualquier información de todos mis registros que USCIS pueda necesitar para determinar mi elegibilidad para el beneficio migratorio que solicito. Asimismo, autorizo la divulgación de la información contenida en esta solicitud, en los documentos de respaldo y en mis registros de USCIS, a otras entidades y personas cuando sea necesario para la administración y aplicación de la ley de inmigración de EE. UU.",
    "Entiendo que USCIS puede exigirme que comparezca a una cita para tomar mis datos biométricos (huellas digitales, fotografía y/o firma) y que, en ese momento, si se me exige proporcionar datos biométricos, se me exigirá firmar un juramento que reafirme que: <strong>1)</strong> revisé y proporcioné o autoricé toda la información de mi solicitud; y <strong>2)</strong> entendí toda la información contenida en mi solicitud y presentada con ella; y <strong>3)</strong> toda esta información estaba completa, era verdadera y correcta al momento de la presentación.",
    "Certifico, bajo pena de perjurio, que proporcioné o autoricé toda la información de mi solicitud, que entiendo toda la información contenida en mi solicitud y presentada con ella, y que toda esta información es completa, verdadera y correcta.",
    "<strong>NOTA PARA TODOS LOS SOLICITANTES:</strong> Si no completas por completo esta solicitud o no presentas los documentos requeridos que se enumeran en las Instrucciones, USCIS puede denegar tu solicitud.",
]
INTERP_CERT_EN = "I certify, under penalty of perjury, that: I am fluent in English and the language named in Part 3, Item 1.b., which is the same language specified in Part 3., Item Number 1.b., and I have read to this applicant in the identified language every question and instruction on this application and his or her answer to every question. The applicant informed me that he or she understands every instruction, question, and answer on the application, including the Applicant's Certification, and has verified the accuracy of every answer."
INTERP_CERT_ES = "Certifico, bajo pena de perjurio, que: soy fluido(a) en inglés y en el idioma indicado en la Parte 3, Ítem 1.b., que es el mismo idioma especificado en la Parte 3, Ítem 1.b., y que le he leído a este solicitante, en el idioma identificado, cada pregunta e instrucción de esta solicitud y su respuesta a cada pregunta. El solicitante me informó que entiende cada instrucción, pregunta y respuesta de la solicitud, incluida la Certificación del Solicitante, y que ha verificado la exactitud de cada respuesta."
PREP_CERT_EN = "By my signature, I certify, under penalty of perjury, that I prepared this application at the request of the applicant. The applicant then reviewed this completed application and informed me that he or she understands all of the information contained in, and submitted with, his or her application, including the Applicant's Certification, and that all of this information is complete, true, and correct. I completed this application based only on information that the applicant provided to me or authorized me to obtain or use."
PREP_CERT_ES = "Con mi firma, certifico, bajo pena de perjurio, que preparé esta solicitud a petición del solicitante. El solicitante luego revisó esta solicitud completada y me informó que entiende toda la información contenida en su solicitud y presentada con ella, incluida la Certificación del Solicitante, y que toda esta información es completa, verdadera y correcta. Completé esta solicitud con base únicamente en la información que el solicitante me proporcionó o me autorizó a obtener o usar."
PREP_STATEMENT_EN = {
    "7.a": "I am not an attorney or accredited representative but have prepared this application on behalf of the applicant and with the applicant's consent.",
    "7.b": "I am an attorney or accredited representative and my representation of the applicant in this case {extends} beyond the preparation of this application. NOTE: If you are an attorney or accredited representative, you may need to submit a completed Form G-28, Notice of Entry of Appearance as Attorney or Accredited Representative, with this application.",
}
PREP_STATEMENT_ES = {
    "7.a": "No soy abogado ni representante acreditado, pero preparé esta solicitud en nombre del solicitante y con su consentimiento.",
    "7.b": "Soy abogado o representante acreditado y mi representación del solicitante en este caso {extends} más allá de la preparación de esta solicitud. NOTA: Si es abogado o representante acreditado, es posible que deba presentar con esta solicitud un Formulario G-28 completado, Notificación de Comparecencia como Abogado o Representante Acreditado.",
}


def _add_preparer_page(b):
    """PART 5 — the preparer (OG). INFORMATION only (Items 1-6); the statement (Item 7) is derived from the central configuration and the
    preparer's signature and date (Item 8) are never collected. Defaults come from `business_info.PREPARER_*` / `OFFICE_*` (the same central
    configuration the I-864 uses)."""
    page(b, "preparer", ("Who prepares your application", "Quién prepara tu solicitud"),
         ("OG Multiservices prepares this application for you, so OG is listed as the preparer. These details come from OG's own settings — you normally do not need to change anything. OG does not sign for you, and the preparer's signature is handled by OG separately.",
          "OG Multiservices prepara esta solicitud por ti, así que OG figura como preparador. Estos datos vienen de la configuración propia de OG: normalmente no necesitas cambiar nada. OG no firma por ti, y la firma del preparador la maneja OG por separado."),
         group="preparer", ctx="applicant")
    b.field("prep_family", "short_answer", ("Preparer's family name (last name)", "Apellido del preparador"), ref="Part 5, Item 1.a", req=True, width="half", maxlen=30)
    b.field("prep_given", "short_answer", ("Preparer's given name (first name)", "Nombre del preparador"), ref="Part 5, Item 1.b", req=True, width="half", maxlen=18)
    b.field("prep_org", "short_answer", ("Preparer's business or organization name (if any)", "Empresa u organización del preparador (si aplica)"), ref="Part 5, Item 2", maxlen=38)
    _address_fields(b, "prep", "Part 5, Item 3 (Preparer's Mailing Address, 3.a–3.h)")
    b.field("prep_phone", "phone", ("Preparer's daytime telephone number", "Teléfono de día del preparador"), ref="Part 5, Item 4", req=True, width="half")
    b.field("prep_mobile", "phone", ("Preparer's mobile telephone number (if any)", "Teléfono móvil del preparador (si tiene)"), ref="Part 5, Item 5", width="half")
    b.field("prep_email", "email", ("Preparer's email address (if any)", "Correo electrónico del preparador (si tiene)"), ref="Part 5, Item 6")
    b.fields["prep_email"].required = False
    defaults = {"prep_family": "@biz:PREPARER_LAST_NAME", "prep_given": "@biz:PREPARER_FIRST_NAME", "prep_org": "@biz:PREPARER_ORG", "prep_phone": "@biz:PREPARER_PHONE",
                "prep_mobile": "@biz:PREPARER_MOBILE", "prep_email": "@biz:PREPARER_EMAIL", "prep_is_us": "yes", "prep_street": "@biz:OFFICE_STREET",
                "prep_unit_type": "@biz:OFFICE_UNIT_TYPE", "prep_unit_number": "@biz:OFFICE_UNIT_NUMBER", "prep_city": "@biz:OFFICE_CITY", "prep_state": "@biz:OFFICE_STATE",
                "prep_zip": "@biz:OFFICE_ZIP"}
    for name, value in defaults.items():
        b.fields[name].default_value = value
    b.field("prep_statement_card", "paragraph", ("", ""), content=("", ""))
    b.fields["prep_statement_card"].config_json = json.dumps({"dynamic": {"kind": "i765_preparer"}})
    para(b, "prep_cert", *txt(f"<strong>Preparer's Certification (as printed on the form; OG signs it separately):</strong> {PREP_CERT_EN}",
                              f"<strong>Certificación del preparador (tal como está impresa en el formulario; OG la firma por separado):</strong> {PREP_CERT_ES} <em>(Traducción de cortesía de OG; el texto oficial es el inglés.)</em>", "text-[13px] leading-relaxed text-slate-600"))
    b.fields["prep_cert"].source_note = COURTESY


def build_i765(form):
    b = Builder(form)
    blocks = ["sb_identity", "sb_othernames", "sb_address", "sb_ids", "sb_marital", "sb_arrival", "sb_docs", "sb_arrdoc", "sb_contact"]
    page(b, "sys", ("Case information", "Información del caso"), group=None)
    from app.case_types import FORM_CASE_CONFIG

    for k in blocks:
        b.field(f"{k}_avail", "short_answer", (f"{k} available", f"{k} disponible"), ref="OG system flag (never shown)")
        kp(b, f"{k}_avail", system=True)
        if FORM_CASE_CONFIG["I-765"]["blocks"][k].get("ask") or k == "sb_address":
            facts = list(FORM_CASE_CONFIG["I-765"]["blocks"][k]["fields"])
            b.field(f"{k}_missing", "multi_choice", (f"{k} missing", f"{k} faltante"), ref="OG system flag (never shown)", opts=[(f, f, f) for f in facts])
            kp(b, f"{k}_missing", system=True)
    for name, label in (("c_branch", "Category-specific questions that apply"), ("c_abc_rel", "ABC question asked")):
        b.field(name, "short_answer", (label, label), ref="OG system value (never shown): " + ("Part 2, Items 28–31 (which apply)" if name == "c_branch" else "Part 3, Item 6 (whether asked)"))
        kp(b, name, system=True)
    show_page_any(b, "sys", [[("sb_identity_avail", "equals", "__never__")]])

    # ================================================================== Before you begin
    page(b, "intro", ("Before you begin", "Antes de empezar"), group="before", ctx="applicant")
    para(b, "intro_1", "This intake collects what OG Multiservices needs to prepare Form I-765, Application for Employment Authorization (USCIS edition 08/21/25). Your answers save automatically, so you can stop and come back anytime.",
         "Este formulario reúne lo que OG Multiservices necesita para preparar el Formulario I-765, Solicitud de Autorización de Empleo (edición USCIS 08/21/25). Tus respuestas se guardan automáticamente, así que puedes parar y volver cuando quieras.")
    b.field("intro_case", "paragraph", ("", ""), content=("", ""))
    b.fields["intro_case"].config_json = json.dumps({"dynamic": {"kind": "context"}})
    para(b, "intro_2", "If OG already has information about the applicant from another application, we show it to you first so you can confirm it instead of typing it again. Nothing is reused without your confirmation, and anything time-sensitive is checked with you first.",
         "Si OG ya tiene información del solicitante de otra solicitud, te la mostramos primero para que la confirmes en lugar de escribirla otra vez. Nada se reutiliza sin tu confirmación, y lo que cambia con el tiempo se verifica contigo primero.")
    para(b, "intro_3", "OG Multiservices provides document preparation and administrative assistance. We are not a law firm and do not provide legal advice or representation. We cannot tell you whether you qualify for employment authorization or which category applies to you: OG reviews that with you. Sending this to OG does not file anything with USCIS.",
         "OG Multiservices ofrece preparación de documentos y asistencia administrativa. No somos un bufete de abogados ni brindamos asesoría o representación legal. No podemos decirte si calificas para la autorización de empleo ni qué categoría te corresponde: OG lo revisa contigo. Enviar esto a OG no presenta nada ante USCIS.")
    page(b, "smart_start", ("We already have information about {app}", "Ya tenemos información sobre {app}"),
         ("This is what OG already knows. You will review it before it is used — nothing is copied without your confirmation.", "Esto es lo que OG ya sabe. Lo revisarás antes de usarlo: nada se copia sin tu confirmación."), group="before", ctx="applicant")
    b.field("smart_card", "paragraph", ("", ""), content=("", ""))
    b.fields["smart_card"].config_json = json.dumps({"dynamic": {"kind": "i765_start"}})
    show_page_any(b, "smart_start", [[(f"{k}_avail", "equals", "yes")] for k in ("sb_identity", "sb_othernames", "sb_address", "sb_ids", "sb_marital", "sb_arrival", "sb_contact")])

    # ================================================================== PART 1 — reason for applying
    page(b, "reason", ("Why are you applying?", "¿Por qué solicitas?"), ("The form asks you to select only one. OG never chooses this for you.", "El formulario pide seleccionar solo una. OG nunca la elige por ti."), group="reason", ctx="applicant")
    choice(b, "r_reason", ("I am applying for…", "Estoy solicitando…"), "Part 1, Items 1.a–1.c", [
        ("1a", "Initial permission to accept employment.", "Permiso inicial para aceptar empleo."),
        ("1b", "Replacement of lost, stolen, or damaged employment authorization document, or correction of my employment authorization document NOT DUE to U.S. Citizenship and Immigration Services (USCIS) error.",
         "Reemplazo de un documento de autorización de empleo perdido, robado o dañado, o corrección de mi documento de autorización de empleo NO DEBIDA a un error de los Servicios de Ciudadanía e Inmigración de EE. UU. (USCIS)."),
        ("1c", "Renewal of my permission to accept employment. (Attach a copy of your previous employment authorization document.)",
         "Renovación de mi permiso para aceptar empleo. (Adjunta una copia de tu documento de autorización de empleo anterior.)")])
    note(b, "r_note_1b", "Note from the form: replacement (correction) of an employment authorization document due to USCIS error does not require a new Form I-765 and filing fee. See www.uscis.gov/i-765 for details.",
         "Nota del formulario: el reemplazo (corrección) de un documento de autorización de empleo debido a un error de USCIS no requiere un nuevo Formulario I-765 ni tarifa de presentación. Consulta www.uscis.gov/i-765.")
    only_if(b, "r_note_1b", ("r_reason", "equals", "1b"))
    note(b, "r_note_1c", "The form says to attach a copy of your previous employment authorization document. OG will list it in your documents.",
         "El formulario indica adjuntar una copia de tu documento de autorización de empleo anterior. OG lo incluirá en tu lista de documentos.")
    only_if(b, "r_note_1c", ("r_reason", "equals", "1c"))

    # ================================================================== PART 2 — about the applicant (shared blocks)
    def edit_identity():
        b.field("a_family", "short_answer", ("Family name (last name)", "Apellido"), ref="Part 2, Item 1.a", req=True, width="half", maxlen=60)
        b.field("a_given", "short_answer", ("Given name (first name)", "Nombre(s)"), ref="Part 2, Item 1.b", req=True, width="half", maxlen=60)
        b.field("a_middle", "short_answer", ("Middle name (if applicable)", "Segundo nombre (si aplica)"), ref="Part 2, Item 1.c", width="half", maxlen=60)
        b.field("a_dob", "date", ("Date of birth", "Fecha de nacimiento"), ref="Part 2, Item 16", req=True, date_rule="past", width="half")
        b.field("a_sex", "single_choice", ("Sex", "Sexo"), ref="Part 2, Item 10", req=True, opts=[("male", "Male", "Masculino"), ("female", "Female", "Femenino")])
        b.field("a_birth_city", "short_answer", ("City, town or village of birth", "Ciudad, pueblo o aldea de nacimiento"), ref="Part 2, Item 15.a", req=True, width="half", maxlen=60)
        b.field("a_birth_state", "short_answer", ("State or province of birth", "Estado o provincia de nacimiento"), ref="Part 2, Item 15.b", width="half", maxlen=60,
                help=("Leave it blank only if the place where you were born has no state or province.", "Déjalo en blanco solo si el lugar donde naciste no tiene estado ni provincia."))
        b.field("a_birth_country", "short_answer", ("Country of birth", "País de nacimiento"), ref="Part 2, Item 15.c", req=True, width="half", maxlen=60)
        b.field("a_citizenship", "short_answer", ("Country of citizenship or nationality", "País de ciudadanía o nacionalidad"), ref="Part 2, Item 14.a", req=True, width="half", maxlen=60,
                help=("If you are a citizen or national of more than one country, add the others in a later step.", "Si eres ciudadano(a) o nacional de más de un país, agrega los demás en un paso posterior."))
        mark_block_fields(b, "sb_identity", ["a_family", "a_given", "a_middle", "a_dob", "a_sex", "a_birth_city", "a_birth_state", "a_birth_country", "a_citizenship"])
        only_missing(b, "sb_identity", ["a_family", "a_given", "a_middle", "a_dob", "a_sex", "a_birth_city", "a_birth_state", "a_birth_country", "a_citizenship"])
    block_pair(b, "sb_identity", group="applicant", form_name="I-765", ask_missing=True,
               review_title=("We already have {app}'s identity information", "Ya tenemos los datos de identidad de {app}"),
               review_desc=("Name, date of birth, sex, place of birth and citizenship. Confirm them or change them.", "Nombre, fecha de nacimiento, sexo, lugar de nacimiento y ciudadanía. Confírmalos o cámbialos."),
               edit_title=("About you", "Sobre ti"),
               edit_desc=("Your full legal name (do not use a nickname), date of birth, sex, place of birth and citizenship. Only what is still missing is asked.",
                          "Tu nombre legal completo (no uses un apodo), fecha de nacimiento, sexo, lugar de nacimiento y ciudadanía. Solo se pregunta lo que aún falta."), build_edit=edit_identity)

    page(b, "more_countries", ("Other countries of citizenship or nationality", "Otros países de ciudadanía o nacionalidad"),
         ("List all countries where you are currently a citizen or national (Item 14).", "Indica todos los países donde eres actualmente ciudadano(a) o nacional (Ítem 14)."), group="citizenship_birth", ctx="applicant")
    b.field("a_more_countries", "single_choice", ("Are you currently a citizen or national of any other country?", "¿Eres actualmente ciudadano(a) o nacional de algún otro país?"), ref="Part 2, Item 14.b (OG helper)", req=True, opts=YES_NO)
    records(b, "a_countries_more", ("Other countries where you are currently a citizen or national", "Otros países donde eres actualmente ciudadano(a) o nacional"), "Part 2, Item 14.b (more than two go in Part 6)", "i765_country", req=True, max=10)
    only_if(b, "a_countries_more", ("a_more_countries", "equals", "yes"))

    def edit_othernames():
        records(b, "a_other_names", ("Other names you have ever used", "Otros nombres que has usado alguna vez"), "Part 2, Items 2–4 (three name boxes; more go in Part 6)", "other_name", max=12,
                help=("Include aliases, maiden name and nicknames. If you have none, just continue.", "Incluye alias, apellido de soltera y apodos. Si no tienes, solo continúa."))
        mark_block_fields(b, "sb_othernames", ["a_other_names"])
    block_pair(b, "sb_othernames", group="applicant", form_name="I-765",
               review_title=("We already have the other names {app} has used", "Ya tenemos los otros nombres que ha usado {app}"), review_desc=("Confirm this list or change it.", "Confirma esta lista o cámbiala."),
               edit_title=("Other names you have used", "Otros nombres que has usado"),
               edit_desc=("Provide all other names you have ever used, including aliases, maiden name and nicknames.", "Indica todos los demás nombres que has usado alguna vez, incluidos alias, apellido de soltera y apodos."), build_edit=edit_othernames)

    def edit_marital():
        b.field("a_marital", "single_choice", ("Marital status", "Estado civil"), ref="Part 2, Item 11", req=True,
                opts=[("single", "Single", "Soltero(a)"), ("married", "Married", "Casado(a)"), ("divorced", "Divorced", "Divorciado(a)"), ("widowed", "Widowed", "Viudo(a)")])
        mark_block_fields(b, "sb_marital", ["a_marital"])
    block_pair(b, "sb_marital", group="applicant", form_name="I-765",
               review_title=("{app}'s marital status", "Estado civil de {app}"), review_desc=("Marital status can change. Is this still correct?", "El estado civil puede cambiar. ¿Sigue siendo correcto?"),
               edit_title=("Your marital status", "Tu estado civil"), edit_desc=None, build_edit=edit_marital)

    page(b, "prior", ("Previous Forms I-765", "Formularios I-765 anteriores"), group="applicant", ctx="applicant")
    b.field("prior_card", "paragraph", ("", ""), content=("", ""))
    b.fields["prior_card"].config_json = json.dumps({"dynamic": {"kind": "i765_prior"}})
    b.field("p_prior", "single_choice", ("Have you previously filed Form I-765?", "¿Has presentado anteriormente el Formulario I-765?"), ref="Part 2, Item 12", req=True, opts=YES_NO,
            help=("Answer for your whole history: with another preparer, an attorney, or years ago. OG's records only show what OG handled.", "Responde por todo tu historial: con otro preparador, un abogado o hace años. Los registros de OG solo muestran lo que OG manejó."))
    b.field("p_prior_details", "long_answer", ("Anything you remember about it (optional)", "Lo que recuerdes al respecto (opcional)"), ref="OG helper (goes to Part 6 if given)", maxlen=1000,
            help=("For example roughly when and where it was filed, the receipt number, or the result.", "Por ejemplo cuándo y dónde se presentó más o menos, el número de recibo o el resultado."))
    only_if(b, "p_prior_details", ("p_prior", "equals", "yes"))

    # ================================================================== addresses (Items 5-7)
    def edit_address():
        us_address(b, "ph", "Part 2, Item 7 (U.S. Physical Address)")
        mark_block_fields(b, "sb_address", [n for n in b.fields if n.startswith("ph_")])
        only_missing(b, "sb_address", [n for n in b.fields if n.startswith("ph_")])
    block_pair(b, "sb_address", group="addresses", form_name="I-765", ask_missing=True,
               review_title=("{app}'s U.S. physical address", "Dirección física de {app} en EE. UU."), review_desc=("Is this still where you live?", "¿Sigues viviendo aquí?"),
               edit_title=("Your current U.S. physical address", "Tu dirección física actual en EE. UU."),
               edit_desc=("Where you live now. Do not use an older address.", "Donde vives ahora. No uses una dirección anterior."), build_edit=edit_address)
    page(b, "mail_gate", ("Mailing address", "Dirección postal"), group="addresses", ctx="applicant")
    b.field("m_same", "single_choice", ("Is your current mailing address the same as your physical address?", "¿Tu dirección postal actual es la misma que tu dirección física?"), ref="Part 2, Item 6", req=True, opts=YES_NO)
    page(b, "mailing", ("Your U.S. mailing address", "Tu dirección postal en EE. UU."), group="addresses", ctx="applicant")
    us_address(b, "ml", "Part 2, Item 5 (Your U.S. Mailing Address)", in_care_of=True)
    show_page_any(b, "mailing", [[("m_same", "equals", "no")]])

    # ================================================================== identifiers (Items 8, 9, 13)
    def edit_ids():
        b.field("a_anumber", "short_answer", ("A-Number (if any)", "Número A (si tienes)"), ref="Part 2, Item 8", sensitive=True, pattern=r"A?-?\d{7,9}", maxlen=12,
                msg=("Enter 7 to 9 digits, with or without “A-”.", "Ingresa 7 a 9 dígitos, con o sin “A-”."))
        where(b, "a_anumber", *WHERE_A)
        b.field("a_uscis_account", "short_answer", ("USCIS Online Account Number (if any)", "Número de cuenta en línea de USCIS (si tienes)"), ref="Part 2, Item 9", maxlen=12,
                pattern=r"\d{1,12}", msg=("Use digits only (up to 12).", "Usa solo dígitos (hasta 12)."))
        where(b, "a_uscis_account", *WHERE_ACCT)
        b.field("a_ssn", "short_answer", ("U.S. Social Security number (if known)", "Número de Seguro Social de EE. UU. (si lo conoces)"), ref="Part 2, Item 13", sensitive=True,
                pattern=r"\d{3}-?\d{2}-?\d{4}", msg=("Enter 9 digits.", "Ingresa 9 dígitos."))
        where(b, "a_ssn", *WHERE_SSN)
        mark_block_fields(b, "sb_ids", ["a_anumber", "a_uscis_account", "a_ssn"])
    block_pair(b, "sb_ids", group="identifiers", form_name="I-765",
               review_title=("We already have {app}'s identification numbers", "Ya tenemos los números de identificación de {app}"),
               review_desc=("A-Number, USCIS online account and Social Security number (partly hidden). Confirm them or change them.", "Número A, cuenta de USCIS y Seguro Social (parcialmente ocultos). Confírmalos o cámbialos."),
               edit_title=("Your identification numbers", "Tus números de identificación"),
               edit_desc=("Give the ones you have. Leave the rest blank.", "Indica los que tienes. Deja en blanco los demás."), build_edit=edit_ids)

    # ================================================================== last U.S. arrival (Items 17-26)
    def edit_arrival():
        b.field("a_i94_number", "short_answer", ("Form I-94 Arrival-Departure Record number (if any)", "Número del Registro de Llegada/Salida Formulario I-94 (si tienes)"), ref="Part 2, Item 17", maxlen=11,
                pattern=r"[A-Za-z0-9]{1,11}", msg=("Use letters and digits only (up to 11).", "Usa solo letras y dígitos (hasta 11)."))
        where(b, "a_i94_number", *WHERE_I94)
        b.field("a_arr_date", "date", ("Date of your last arrival into the United States, on or about", "Fecha de tu última llegada a los Estados Unidos, aproximadamente"), ref="Part 2, Item 22", req=True, date_rule="past", width="half")
        b.field("a_arr_place", "short_answer", ("Place of your last arrival into the United States", "Lugar de tu última llegada a los Estados Unidos"), ref="Part 2, Item 23", req=True, width="half", maxlen=80,
                help=("For example the city and state, or the airport.", "Por ejemplo la ciudad y el estado, o el aeropuerto."))
        b.field("a_arr_status", "short_answer", ("Immigration status at your last arrival (for example B-2 visitor, F-1 student, or no status)", "Estatus migratorio en tu última llegada (por ejemplo visitante B-2, estudiante F-1 o sin estatus)"), ref="Part 2, Item 24", req=True, maxlen=80)
        b.field("a_current_status", "short_answer", ("Your current immigration status or category (for example B-2 visitor, F-1 student, parolee, deferred action, or no status or category)", "Tu estatus o categoría migratoria actual (por ejemplo visitante B-2, estudiante F-1, parolee, acción diferida o sin estatus ni categoría)"), ref="Part 2, Item 25", req=True, maxlen=100)
        mark_block_fields(b, "sb_arrival", ["a_i94_number", "a_arr_date", "a_arr_place", "a_arr_status", "a_current_status"])
        only_missing(b, "sb_arrival", ["a_i94_number", "a_arr_date", "a_arr_place", "a_arr_status", "a_current_status"])
    block_pair(b, "sb_arrival", group="arrival", form_name="I-765", ask_missing=True,
               review_title=("{app}'s last U.S. arrival", "Última llegada de {app} a EE. UU."), review_desc=("Immigration details change. Is this still current?", "Los datos migratorios cambian. ¿Siguen vigentes?"),
               edit_title=("Your last arrival in the United States", "Tu última llegada a los Estados Unidos"),
               edit_desc=("The form asks about your most recent arrival and your status now.", "El formulario pregunta por tu llegada más reciente y tu estatus actual."), build_edit=edit_arrival)

    # passport vs travel document are DIFFERENT concepts (Items 18 / 19) — reused only when the applicant says what the known document is
    page(b, "d_kind_page", ("The document you used at your last arrival", "El documento que usaste en tu última llegada"),
         ("OG has a passport or travel document from your earlier application. The form asks separately for your most recently issued PASSPORT (Item 18) and any TRAVEL DOCUMENT (Item 19), so tell us which this is.", "OG tiene un pasaporte o documento de viaje de tu solicitud anterior. El formulario pide por separado tu PASAPORTE emitido más recientemente (Ítem 18) y cualquier DOCUMENTO DE VIAJE (Ítem 19), así que dinos cuál es."),
         group="arrival", ctx="applicant")
    b.field("d_card", "paragraph", ("", ""), content=("", ""))
    b.fields["d_card"].config_json = json.dumps({"dynamic": {"kind": "i765_arrdoc"}})
    choice(b, "d_kind", ("That document is…", "Ese documento es…"), "OG helper (Items 18–21: which document the known number is)", [
        ("passport", "My most recently issued passport", "Mi pasaporte emitido más recientemente"), ("travel_document", "A travel document (not a passport)", "Un documento de viaje (no un pasaporte)"),
        ("other", "Neither — I will enter my details", "Ninguno — ingresaré mis datos")],
           note_="Lets OG reuse the passport/travel-document details from the applicant's earlier application without guessing which item they belong to.")
    kp(b, "d_kind")
    show_page_any(b, "d_kind_page", [[("sb_docs_avail", "equals", "no"), ("sb_arrdoc_avail", "equals", "yes")]])

    def edit_docs():
        b.field("a_passport", "short_answer", ("Passport number of your most recently issued passport", "Número de pasaporte de tu pasaporte emitido más recientemente"), ref="Part 2, Item 18", sensitive=True, maxlen=20)
        where(b, "a_passport", *WHERE_PASSPORT_765)
        b.field("a_travel_doc", "short_answer", ("Travel document number (if any)", "Número del documento de viaje (si tienes)"), ref="Part 2, Item 19", sensitive=True, maxlen=20)
        b.field("a_doc_country", "short_answer", ("Country that issued your passport or travel document", "País que emitió tu pasaporte o documento de viaje"), ref="Part 2, Item 20", width="half", maxlen=60)
        b.field("a_doc_expiry", "date", ("Expiration date for your passport or travel document", "Fecha de vencimiento de tu pasaporte o documento de viaje"), ref="Part 2, Item 21", width="half")
        mark_block_fields(b, "sb_docs", ["a_passport", "a_travel_doc", "a_doc_country", "a_doc_expiry"])
    block_pair(b, "sb_docs", group="arrival", form_name="I-765",
               review_title=("{app}'s passport and travel document", "Pasaporte y documento de viaje de {app}"), review_desc=("These can change when a passport is renewed. Are they still current?", "Pueden cambiar al renovar un pasaporte. ¿Siguen vigentes?"),
               edit_title=("Your passport and travel document", "Tu pasaporte y documento de viaje"),
               edit_desc=("Item 18 is your most recently issued passport; Item 19 is a separate travel document, if you have one. Where a document was already known you only confirm it.", "El Ítem 18 es tu pasaporte emitido más recientemente; el Ítem 19 es un documento de viaje aparte, si tienes uno. Donde ya se conocía un documento, solo lo confirmas."), build_edit=edit_docs)
    # the pseudo-block that only tells us whether an earlier application stated a passport-or-travel-document at last arrival
    for n in ("x_arr_num", "x_arr_country", "x_arr_expiry"):
        b.field(n, "short_answer", (n, n), ref="OG system flag (never shown)")
        kp(b, n, system=True)
        b.rule("show_field", n, [NEVER])

    page(b, "sevis_page", ("Student and exchange visitor number", "Número de estudiante y visitante de intercambio"), group="arrival", ctx="applicant")
    b.field("has_sevis", "single_choice", ("Do you have a SEVIS number?", "¿Tienes un número SEVIS?"), ref="Part 2, Item 26 (OG helper)", req=True, opts=YES_NO, help=WHERE_SEVIS)
    b.field("a_sevis", "short_answer", ("SEVIS number", "Número SEVIS"), ref="Part 2, Item 26", req=True, maxlen=12, pattern=r"N-?\d{10}", msg=("A SEVIS number is the letter N followed by 10 digits.", "Un número SEVIS es la letra N seguida de 10 dígitos."))
    only_if(b, "a_sevis", ("has_sevis", "equals", "yes"))

    # ================================================================== ELIGIBILITY CATEGORY (Item 27) — stored, never decided
    page(b, "category", ("Employment authorization category", "Categoría de autorización de empleo"),
         ("The form asks for the eligibility category as a letter and a number, for example (a)(8) or (c)(17)(iii). OG does not choose it for you — enter it if you know it, or say you are not sure and OG will review it with you.",
          "El formulario pide la categoría de elegibilidad como una letra y un número, por ejemplo (a)(8) o (c)(17)(iii). OG no la elige por ti: ingrésala si la sabes, o di que no estás seguro(a) y OG la revisará contigo."), group="category", ctx="applicant")
    b.field("cat_card", "paragraph", ("", ""), content=("", ""))
    b.fields["cat_card"].config_json = json.dumps({"dynamic": {"kind": "i765_category_hint"}})
    choice(b, "e_known", ("Do you know your eligibility category?", "¿Sabes tu categoría de elegibilidad?"), "Part 2, Item 27 (OG helper)",
           [("known", "Yes — I know it (it may be on a notice, or OG gave it to me)", "Sí — la sé (puede estar en una notificación, o OG me la dio)"), ("unsure", "Not sure — OG will review it with me", "No estoy seguro(a) — OG la revisará conmigo")],
           help=("Refer to the Who May File Form I-765 section of the Form I-765 Instructions to determine the category. OG can help.", "Consulta la sección “Who May File Form I-765” de las Instrucciones del Formulario I-765 para determinar la categoría. OG puede ayudarte."))
    b.field("e_cat_a", "short_answer", ("First part — a letter", "Primera parte — una letra"), ref="Part 2, Item 27 (first box)", req=True, width="half", maxlen=3, pattern=r"\(?[A-Za-z]\)?",
            msg=("Enter one letter, for example a or c.", "Ingresa una letra, por ejemplo a o c."))
    b.field("e_cat_b", "short_answer", ("Second part — a number", "Segunda parte — un número"), ref="Part 2, Item 27 (second box)", req=True, width="half", maxlen=4, pattern=r"\(?\d{1,2}\)?",
            msg=("Enter a number, for example 8 or 17.", "Ingresa un número, por ejemplo 8 o 17."))
    b.field("e_cat_c", "short_answer", ("Third part (only if your category has one)", "Tercera parte (solo si tu categoría la tiene)"), ref="Part 2, Item 27 (third box)", width="half", maxlen=6, pattern=r"\(?[A-Za-z]{1,4}\)?",
            msg=("Use letters only, for example C or iii.", "Usa solo letras, por ejemplo C o iii."), help=("For (c)(17)(iii) this is iii; for (c)(3)(C) it is C. Leave it blank if there is none.", "Para (c)(17)(iii) es iii; para (c)(3)(C) es C. Déjala en blanco si no hay."))
    for n in ("e_cat_a", "e_cat_b", "e_cat_c"):
        b.rule("show_field", n, [("e_known", "equals", "known")])
    note(b, "e_unsure_note", "That is fine. OG will go through the category with you before anything is prepared.", "Está bien. OG revisará contigo la categoría antes de preparar nada.")
    only_if(b, "e_unsure_note", ("e_known", "equals", "unsure"))

    # category-specific questions: the exact category entered only (source Items 28-31)
    page(b, "x_stem", ("Your STEM OPT category — (c)(3)(C)", "Tu categoría STEM OPT — (c)(3)(C)"),
         ("Because you entered (c)(3)(C), the form asks for these details (Items 28.a–28.c).", "Como ingresaste (c)(3)(C), el formulario pide estos datos (Ítems 28.a–28.c)."), group="category", ctx="applicant")
    b.field("x_degree", "short_answer", ("Degree", "Título académico"), ref="Part 2, Item 28.a", req=True, maxlen=80)
    b.field("x_everify_name", "short_answer", ("Employer's name as listed in E-Verify", "Nombre del empleador tal como aparece en E-Verify"), ref="Part 2, Item 28.b", req=True, maxlen=80)
    b.field("x_everify_id", "short_answer", ("Employer's E-Verify Company Identification Number or a valid E-Verify Client Company Identification Number", "Número de identificación de la compañía en E-Verify del empleador o un Número de identificación de compañía cliente de E-Verify válido"), ref="Part 2, Item 28.c", req=True, maxlen=40)
    show_page_any(b, "x_stem", [[("c_branch", "equals", "c3c")]])
    page(b, "x_c26", ("Your H-1B spouse's notice — (c)(26)", "El aviso de tu cónyuge H-1B — (c)(26)"),
         ("Because you entered (c)(26), the form asks for this receipt number (Item 29).", "Como ingresaste (c)(26), el formulario pide este número de recibo (Ítem 29)."), group="category", ctx="applicant")
    b.field("x_c26_receipt", "short_answer", ("Receipt number of your H-1B spouse's most recent Form I-797 Notice for Form I-129, Petition for a Nonimmigrant Worker", "Número de recibo del Aviso más reciente del Formulario I-797 de tu cónyuge H-1B para el Formulario I-129, Petición de Trabajador No Inmigrante"),
            ref="Part 2, Item 29", req=True, maxlen=16, pattern=r"[A-Za-z0-9-]{10,16}", msg=RECEIPT_MSG)
    show_page_any(b, "x_c26", [[("c_branch", "equals", "c26")]])
    page(b, "x_c8", ("Arrests and convictions — (c)(8)", "Arrestos y condenas — (c)(8)"),
         ("Because you entered (c)(8), the form asks one question (Item 30). OG does not decide what your answer means.", "Como ingresaste (c)(8), el formulario hace una pregunta (Ítem 30). OG no decide qué significa tu respuesta."), group="category", ctx="applicant")
    b.field("x_c8_arrest", "single_choice", ("Have you EVER been arrested for and/or convicted of any crime?", "¿Has sido ALGUNA VEZ arrestado(a) y/o condenado(a) por algún delito?"), ref="Part 2, Item 30", req=True, opts=YES_NO)
    note(b, "x_c8_note", "Note from the form: if you answered Yes, see Special Filing Instructions for Those With Pending Asylum Applications (c)(8) in the Required Documentation section of the Form I-765 Instructions for information about providing court dispositions. OG will review this with you.",
         "Nota del formulario: si respondiste Sí, consulta las Instrucciones Especiales de Presentación para quienes tienen solicitudes de asilo pendientes (c)(8) en la sección de Documentación Requerida de las Instrucciones del Formulario I-765 para obtener información sobre cómo presentar las disposiciones judiciales. OG lo revisará contigo.")
    only_if(b, "x_c8_note", ("x_c8_arrest", "equals", "yes"))
    b.field("x_c8_details", "long_answer", ("Tell OG briefly what happened (optional)", "Cuéntale a OG brevemente qué pasó (opcional)"), ref="OG helper (goes to Part 6 if given)", maxlen=1500,
            help=("Where and when, and what the result was, if you remember. OG will ask for anything else it needs.", "Dónde y cuándo, y cuál fue el resultado, si lo recuerdas. OG pedirá lo demás que necesite."))
    only_if(b, "x_c8_details", ("x_c8_arrest", "equals", "yes"))
    show_page_any(b, "x_c8", [[("c_branch", "equals", "c8")]])
    page(b, "x_c3536", ("Your Form I-140 notice — (c)(35) / (c)(36)", "Tu aviso del Formulario I-140 — (c)(35) / (c)(36)"),
         ("Because you entered (c)(35) or (c)(36), the form asks for the notice receipt number and one question (Items 31.a–31.b).", "Como ingresaste (c)(35) o (c)(36), el formulario pide el número de recibo del aviso y una pregunta (Ítems 31.a–31.b)."), group="category", ctx="applicant")
    b.field("x_c35_receipt", "short_answer", ("Receipt number of your Form I-797 Notice for Form I-140, Immigrant Petition for Alien Worker", "Número de recibo de tu Aviso del Formulario I-797 para el Formulario I-140, Petición de Inmigrante para Trabajador Extranjero"),
            ref="Part 2, Item 31.a ((c)(35))", req=True, maxlen=16, pattern=r"[A-Za-z0-9-]{10,16}", msg=RECEIPT_MSG)
    only_if(b, "x_c35_receipt", ("c_branch", "equals", "c35"))
    b.field("x_c36_receipt", "short_answer", ("Receipt number of your spouse's or parent's Form I-797 Notice for Form I-140", "Número de recibo del Aviso del Formulario I-797 de tu cónyuge o padre/madre para el Formulario I-140"),
            ref="Part 2, Item 31.a ((c)(36))", req=True, maxlen=16, pattern=r"[A-Za-z0-9-]{10,16}", msg=RECEIPT_MSG)
    only_if(b, "x_c36_receipt", ("c_branch", "equals", "c36"))
    b.field("x_c3536_arrest", "single_choice", ("Have you EVER been arrested for and/or convicted of any crime?", "¿Has sido ALGUNA VEZ arrestado(a) y/o condenado(a) por algún delito?"), ref="Part 2, Item 31.b", req=True, opts=YES_NO)
    note(b, "x_c3536_note", "Note from the form: if you answered Yes, see Employment-Based Nonimmigrant Categories, Items 8–9, in the Who May File Form I-765 section of the Form I-765 Instructions for information about providing court dispositions. OG will review this with you.",
         "Nota del formulario: si respondiste Sí, consulta Categorías de No Inmigrantes Basadas en el Empleo, Ítems 8–9, en la sección Who May File Form I-765 de las Instrucciones del Formulario I-765 para obtener información sobre cómo presentar las disposiciones judiciales. OG lo revisará contigo.")
    only_if(b, "x_c3536_note", ("x_c3536_arrest", "equals", "yes"))
    b.field("x_c3536_details", "long_answer", ("Tell OG briefly what happened (optional)", "Cuéntale a OG brevemente qué pasó (opcional)"), ref="OG helper (goes to Part 6 if given)", maxlen=1500)
    only_if(b, "x_c3536_details", ("x_c3536_arrest", "equals", "yes"))
    show_page_any(b, "x_c3536", [[("c_branch", "equals", "c35")], [("c_branch", "equals", "c36")]])

    # ================================================================== PART 3 — applicant's statement, contact, ABC, certification
    page(b, "statement", ("Your statement", "Tu declaración"), ("Select the one that is true for you (Part 3, Items 1.a / 1.b).", "Selecciona la que sea cierta para ti (Parte 3, Ítems 1.a / 1.b)."), group="statement", ctx="applicant")
    choice(b, "s_statement", ("Applicant's statement", "Declaración del solicitante"), "Part 3, Items 1.a / 1.b", [
        ("english", "I can read and understand English, and I have read and understand every question and instruction on this application and my answer to every question.",
         "Puedo leer y entender inglés, y he leído y entendido cada pregunta e instrucción de esta solicitud y mi respuesta a cada pregunta."),
        ("interpreter", "The interpreter named in Part 4 read to me every question and instruction on this application and my answer to every question, in a language in which I am fluent, and I understood everything.",
         "El intérprete nombrado en la Parte 4 me leyó cada pregunta e instrucción de esta solicitud y mi respuesta a cada pregunta, en un idioma en el que soy fluido(a), y lo entendí todo.")],
           help=("Part 3 also says you must file Form I-765 while in the United States. An interpreter is never assumed.", "La Parte 3 también indica que debes presentar el Formulario I-765 estando en los Estados Unidos. Nunca se asume un intérprete."))

    def edit_contact():
        b.field("a_phone", "phone", ("Applicant's daytime telephone number", "Teléfono de día del solicitante"), ref="Part 3, Item 3", req=True, width="half")
        b.field("a_mobile", "phone", ("Applicant's mobile telephone number (if any)", "Teléfono móvil del solicitante (si tiene)"), ref="Part 3, Item 4", width="half")
        b.field("a_email", "email", ("Applicant's email address (if any)", "Correo electrónico del solicitante (si tiene)"), ref="Part 3, Item 5")
        b.fields["a_email"].required = False
        mark_block_fields(b, "sb_contact", ["a_phone", "a_mobile", "a_email"])
    block_pair(b, "sb_contact", group="statement", form_name="I-765",
               review_title=("We already have {app}'s contact information", "Ya tenemos la información de contacto de {app}"), review_desc=("Is it still current?", "¿Sigue vigente?"),
               edit_title=("Your contact information", "Tu información de contacto"), edit_desc=None, build_edit=edit_contact)
    page(b, "abc_page", ("ABC settlement agreement", "Acuerdo de conciliación ABC"), group="statement", ctx="applicant")
    choice(b, "a_abc", ("Are you a Salvadoran or Guatemalan national eligible for benefits under the ABC settlement agreement?", "¿Eres un(a) nacional salvadoreño(a) o guatemalteco(a) elegible para beneficios bajo el acuerdo de conciliación ABC?"), "Part 3, Item 6",
           [("yes", "Yes — I am", "Sí — lo soy"), ("no", "No", "No"), UNSURE],
           help=("The form has a box for this. OG does not decide it for you: if you are not sure, choose “Not sure” and OG will review it with you.", "El formulario tiene una casilla para esto. OG no lo decide por ti: si no estás seguro(a), elige “No estoy seguro(a)” y OG lo revisará contigo."))
    show_page_any(b, "abc_page", [[("c_abc_rel", "equals", "yes")]])
    page(b, "cert", ("What you will be asked to certify", "Lo que se te pedirá certificar"),
         ("This is the Applicant's Certification printed on the form, shown so you can read it now. You do not sign it here. The English is the official text as printed on the form.",
          "Esta es la Certificación del Solicitante impresa en el formulario, mostrada para que la leas ahora. No la firmas aquí. Abajo aparece una traducción de cortesía hecha por OG; no es un texto oficial de USCIS. El texto oficial es el del formulario en inglés y es el que prevalece."),
         group="statement", ctx="applicant")
    for i, (en, es) in enumerate(zip(CERT_EN, CERT_ES), 1):
        para(b, f"cert_{i}", *txt(en, es))
        b.fields[f"cert_{i}"].source_note = COURTESY + " Part 3, Applicant's Certification."
    b.field("c_cert_ack", "consent", ("Reading the certification", "Lectura de la certificación"), ref="Part 3 (Applicant's Certification) — customer acknowledgment only", req=True,
            note="Customer acknowledgment that the certification was read; not a signature and not the certification itself. " + COURTESY,
            content=("I have read this certification. I understand that I am not signing or certifying anything here, and that OG will explain how and when I sign.",
                     "He leído esta certificación. Entiendo que aquí no firmo ni certifico nada y que OG me explicará cómo y cuándo firmo."))

    # ================================================================== PART 4 — interpreter (only when the applicant says one was used)
    page(b, "interp", ("Your interpreter", "Tu intérprete"), ("Information about the interpreter (Part 4 of the form).", "Información del intérprete (Parte 4 del formulario)."), group="interpreter", ctx="applicant")
    b.field("int_family", "short_answer", ("Interpreter's family name (last name)", "Apellido del intérprete"), ref="Part 4, Item 1.a", req=True, width="half")
    b.field("int_given", "short_answer", ("Interpreter's given name (first name)", "Nombre del intérprete"), ref="Part 4, Item 1.b", req=True, width="half")
    b.field("int_org", "short_answer", ("Interpreter's business or organization name (if any)", "Empresa u organización del intérprete (si aplica)"), ref="Part 4, Item 2", maxlen=38)
    _address_fields(b, "int", "Part 4, Item 3 (Interpreter's Mailing Address, 3.a–3.h)")
    b.field("int_phone", "phone", ("Interpreter's daytime telephone number", "Teléfono de día del intérprete"), ref="Part 4, Item 4", req=True, width="half")
    b.field("int_mobile", "phone", ("Interpreter's mobile telephone number (if any)", "Teléfono móvil del intérprete (si tiene)"), ref="Part 4, Item 5", width="half")
    b.field("int_email", "email", ("Interpreter's email address (if any)", "Correo electrónico del intérprete (si tiene)"), ref="Part 4, Item 6")
    b.fields["int_email"].required = False
    b.field("int_language", "short_answer", ("Language the interpreter used", "Idioma que usó el intérprete"), ref="Part 3, Item 1.b (language) and Part 4, Interpreter's Certification (language)", req=True)
    para(b, "int_cert", *txt(f"<strong>Interpreter's Certification (as printed on the form; the interpreter signs it separately):</strong> {INTERP_CERT_EN}",
                              f"<strong>Certificación del intérprete (tal como está impresa en el formulario; el intérprete la firma por separado):</strong> {INTERP_CERT_ES} <em>(Traducción de cortesía de OG; el texto oficial es el inglés.)</em>", "text-[13px] leading-relaxed text-slate-600"))
    b.fields["int_cert"].source_note = COURTESY
    for name, value in {"int_family": "@biz:INTERPRETER_LAST_NAME", "int_given": "@biz:INTERPRETER_FIRST_NAME", "int_org": "@biz:INTERPRETER_ORG", "int_phone": "@biz:INTERPRETER_PHONE",
                        "int_email": "@biz:INTERPRETER_EMAIL", "int_is_us": "yes", "int_street": "@biz:OFFICE_STREET", "int_unit_type": "@biz:OFFICE_UNIT_TYPE",
                        "int_unit_number": "@biz:OFFICE_UNIT_NUMBER", "int_city": "@biz:OFFICE_CITY", "int_state": "@biz:OFFICE_STATE", "int_zip": "@biz:OFFICE_ZIP"}.items():
        b.fields[name].default_value = value
    show_page_any(b, "interp", [[("s_statement", "equals", "interpreter")]])

    # ================================================================== PART 5 — preparer (OG)
    _add_preparer_page(b)

    # ================================================================== PART 6 — additional information
    page(b, "additional", ("Anything else?", "¿Algo más?"), group="additional", ctx="applicant")
    b.field("add_card", "paragraph", ("", ""), content=("", ""))
    b.fields["add_card"].config_json = json.dumps({"dynamic": {"kind": "i765_additional"}})
    b.field("additional_information", "long_answer", ("Is there anything else you want us to know?", "¿Hay algo más que quieras que sepamos?"), ref="Part 6. Additional Information (Items 3–7)", maxlen=3000,
            help=("You never need to know a page, part or item number. When your answers do not fit on the printed form (for example more than three other names or two countries), OG adds them to Part 6 for you.",
                  "Nunca necesitas saber un número de página, parte o ítem. Cuando tus respuestas no caben en el formulario impreso (por ejemplo más de tres otros nombres o dos países), OG las agrega a la Parte 6 por ti."))
    calc_field(b, "c_category", "Eligibility category (as entered)", "Categoría de elegibilidad (como se ingresó)", "Part 2, Item 27")
    calc_field(b, "c_addl", "Part 6 entries generated from the answers", "Entradas de la Parte 6 generadas a partir de las respuestas", "Part 6, Items 3–7")
    calc_field(b, "prep_status", "Preparer's statement (from OG configuration)", "Declaración del preparador (de la configuración de OG)", "Part 5, Item 7.a / 7.b")
    calc_field(b, "prep_extends", "Representation extends / does not extend beyond preparation", "La representación se extiende / no se extiende más allá de la preparación", "Part 5, Item 7.b")

    # ================================================================== documents
    page(b, "documents", ("Documents", "Documentos"), ("Documents are kept once in your case, so a document OG already has for this person is not asked for again.", "Los documentos se guardan una sola vez en tu caso, así que un documento que OG ya tiene de esta persona no se vuelve a pedir."), group="documents", ctx="applicant")
    b.field("docs_scope_note", "paragraph", ("", ""), content=(
        _label("What OG asks for", "These are OG's requests to prepare and review your application, plus what the form itself says to attach. USCIS lists its required evidence in the Form I-765 Instructions; OG will confirm what applies to you."),
        _label("Lo que pide OG", "Son solicitudes de OG para preparar y revisar tu solicitud, más lo que el propio formulario indica adjuntar. USCIS enumera su evidencia requerida en las Instrucciones del Formulario I-765; OG confirmará lo que aplica en tu caso.")))
    b.field("docs_list", "paragraph", ("", ""), content=("", ""))
    b.fields["docs_list"].config_json = json.dumps({"dynamic": {"kind": "documents"}})
    b.field("docs_tip", "paragraph", ("", ""), content=(
        _tip("Make sure each document is complete, readable, well lit and not cropped or blurry. Documents that are not in English may need a certified translation — OG can help."),
        _tip("Asegúrate de que cada documento esté completo, legible, bien iluminado y sin cortes ni desenfoque. Los documentos que no estén en inglés pueden necesitar una traducción certificada; OG puede ayudarte.")))

    # ================================================================== confirm
    page(b, "confirm", ("Confirm and Send to OG", "Confirma y envía a OG"), group="confirm", ctx="applicant",
         desc=("Review your information and confirm that it is complete and accurate. OG Multiservices will use the information you provided to assist with preparing your Form I-765 and related documents.",
               "Revisa tu información y confirma que esté completa y correcta. OG Multiservices utilizará la información proporcionada para ayudarte con la preparación de tu Formulario I-765 y los documentos relacionados."))
    note(b, "confirm_warning", "Sending this to OG does not file anything with USCIS, is not an electronic signature, is not the Applicant's Certification, and is not a decision about whether you qualify for employment authorization or which category applies. OG will contact you about the next steps, including how signatures are handled.",
         "Enviar esto a OG no presenta nada ante USCIS, no es una firma electrónica, no es la Certificación del Solicitante y no es una decisión sobre si calificas para la autorización de empleo ni sobre qué categoría aplica. OG te contactará sobre los siguientes pasos, incluido cómo se manejan las firmas.")
    b.field("preparer_request", "consent", ("Request for preparation", "Solicitud de preparación"), ref="Part 3, Item 2 (preparer prepared the application at the applicant's request)", req=True,
            note="Customer confirmation only; not a signature.", content=("I ask OG Multiservices to assist with preparing this Form I-765 based only on the information I provided or authorized.",
                                                                          "Solicito a OG Multiservices que me ayude a preparar este Formulario I-765 con base únicamente en la información que proporcioné o autoricé."))
    b.field("confirm_accurate", "consent", ("Accuracy confirmation and authorization", "Confirmación de exactitud y autorización"), ref="Part 3 (Applicant's Certification wording)", req=True,
            note="Customer confirmation only; not a signature and not the certification under penalty of perjury.", content=("I confirm that the information I provided is complete and correct to the best of my knowledge, and I authorize OG Multiservices to use it to assist with preparing Form I-765 and related documents.",
                                                                                                                             "Confirmo que la información que proporcioné es completa y correcta según mi leal saber y entender, y autorizo a OG Multiservices a usarla para ayudarme a preparar el Formulario I-765 y los documentos relacionados."))
    return b


def _features():
    return {
        "completeness_check": True, "consistency": "i765", "documents_check": True,
        "sections": SECTIONS, "contexts": CONTEXTS, "context_roles": CONTEXT_ROLES,
        "name_tokens": {"app": {"role": "applicant", "fallback": {"en": "the applicant", "es": "el solicitante"}}},
        "sync": [{"kind": "i765_calc"}, {"kind": "requirements_i765"}],
    }


def ensure_i765_intake():
    """Create the production I-765 intake and connect it to the employment-authorization service pages (idempotent; never rebuilt over submissions)."""
    if Form.query.filter_by(slug=I765_SLUG).first():
        return False
    category = ServiceCategory.query.filter_by(slug="immigration").first()
    if category is None:
        return False
    service = Service.query.filter_by(category_id=category.id, slug="employment-authorization").first()
    if service is None:
        top = db.session.query(db.func.max(Service.sort_order)).filter(Service.category_id == category.id).scalar() or 0
        service = Service(
            category_id=category.id, slug="employment-authorization", admin_name="Employment Authorization (Form I-765) Preparation", icon="immigration",
            is_published=True, sort_order=top + 10,
            title_en="Employment Authorization (Form I-765) Preparation", title_es="Preparación de Autorización de Empleo (Formulario I-765)",
            short_en="Document preparation support for Form I-765, the application for a work permit (Employment Authorization Document).",
            short_es="Apoyo en la preparación de documentos para el Formulario I-765, la solicitud del permiso de trabajo (Documento de Autorización de Empleo).",
            hero_text_en="Support organizing your information and documents for a first, replacement or renewal Form I-765.",
            hero_text_es="Apoyo organizando tu información y documentos para un Formulario I-765 inicial, de reemplazo o de renovación.",
            content_title_en="What is Form I-765?", content_title_es="¿Qué es el Formulario I-765?",
            content_en="<p>Form I-765, Application for Employment Authorization, is the form used to ask USCIS for a work permit (Employment Authorization Document). It is used for a first permit, to replace a lost, stolen or damaged one, or to renew one, in many different situations. OG Multiservices helps you gather and organize the information and documents so the form can be prepared. OG provides document preparation and administrative assistance only; we are not a law firm and do not provide legal advice.</p>",
            content_es="<p>El Formulario I-765, Solicitud de Autorización de Empleo, es el formulario que se usa para pedir a USCIS un permiso de trabajo (Documento de Autorización de Empleo). Se usa para un primer permiso, para reemplazar uno perdido, robado o dañado, o para renovarlo, en muchas situaciones distintas. OG Multiservices te ayuda a reunir y organizar la información y los documentos para que el formulario pueda prepararse. OG ofrece solo preparación de documentos y asistencia administrativa; no somos un bufete de abogados ni brindamos asesoría legal.</p>",
            nj_in_person=True, remote_nationwide=True)
        db.session.add(service)
        db.session.flush()
    form = Form(slug=I765_SLUG, name_admin="I-765 Client Intake")
    db.session.add(form)
    form.form_type = "service_intake"
    form.status = "published"
    form.source_form_name = SOURCE_NAME
    form.source_edition = SOURCE_EDITION
    form.version = 1
    form.published_at = datetime.utcnow()
    form.title_en, form.title_es = "Employment Authorization — Form I-765", "Autorización de Empleo — Formulario I-765"
    form.description_en = "Guided intake for OG Multiservices to prepare your Form I-765. Your progress is saved automatically."
    form.description_es = "Solicitud guiada para que OG Multiservices prepare tu Formulario I-765. Tu progreso se guarda automáticamente."
    form.submit_label_en, form.submit_label_es = "Send to OG", "Enviar a OG"
    form.success_message_en = "OG Multiservices has your information and will review it. We'll contact you if we need anything else."
    form.success_message_es = "OG Multiservices tiene tu información y la revisará. Te contactaremos si necesitamos algo más."
    form.show_progress = True
    form.features_json = json.dumps(_features(), ensure_ascii=False)
    db.session.flush()
    build_i765(form)
    db.session.flush()
    service.requires_intake = True
    service.form_id = form.id
    service.requires_account = True
    service.intake_label = "I-765 Client Intake"
    renewal = Service.query.filter_by(category_id=category.id, slug="work-permit-renewal").first()
    if renewal is not None and not renewal.form_id:  # the existing work-permit renewal page starts the same intake (Part 1 asks initial / replacement / renewal)
        renewal.requires_intake = True
        renewal.form_id = form.id
        renewal.requires_account = True
        renewal.intake_label = "I-765 Client Intake"
    db.session.commit()
    return True
