"""Form I-485 Client Intake — the fourth production Smart Intake, built natively on the Case architecture.

SOURCE OF TRUTH: the supplied USCIS "Form I-485, Application to Register Permanent Residence or Adjust Status",
Edition 09/18/26 (OMB No. 1615-0023, expires 03/31/2027), 24 pages, Parts 1-14. Every question carries the
Part/Item it maps to in `FormField.source_ref` (admin-only). Item numbers were read from the PDF's own layout.

Part map (as printed):
  Part 1   Information About You      items 1-19: names, DOB, A-Number, sex, birth, citizenship, USCIS account, recent
                                      immigration history (10-17), addresses (18), Social Security card (19)
  Part 2   Application Type or Filing Category   items 1-5 (EOIR, underlying petition, principal/derivative, category 3.a-3.g, 245(i), CSPA)
  Part 3   Request for Exemption for the Affidavit of Support   item 1.a-1.f
  Part 4   Additional Information About You   items 1-6 (prior immigrant visa / applications), 7-8 (employment & education)
  Part 5   Your Parents   items 1-8
  Part 6   Marital History  items 1-18
  Part 7   Children  items 1-3
  Part 8   Biographic Information  items 1-6
  Part 9   General Eligibility and Inadmissibility Grounds  items 1-84 (organizations, immigration, criminal, security, public charge, violations, misc.)
  Part 10  Contact, certification, signature   -> contact answers only (signature is never collected)
  Part 11  Interpreter (name, organization, contact, language) -> collected; the interpreter's own signature is not
  Part 12  Preparer -> NOT asked (OG prepares); Part 13 (signature at interview) -> NOT collected; Part 14 -> assembled from explanation answers.

Explicitly NOT built: Form I-864, Form I-765 and every other companion form.

OG does not choose the customer's category, decide eligibility or say anything about admissibility: it collects the
answers the form asks for. "Not sure — OG will review" is offered only where the form itself is a workflow choice (Parts 2-3
and Part 4 items 1, 5, 6); the yes/no eligibility questions of Part 9 keep their exact official meaning. The Form I-485
Instructions (which list USCIS's required evidence) are NOT part of the supplied PDF, so no document request claims USCIS requires it.

Facts the case already knows (name, birth, A-Number, USCIS account, SSN, arrival date, I-94, address, address history, employment
history, parents, the spouse and contact details) are shown for confirmation ("We already have this information") instead of
being asked again; see app/shared_blocks.py and FORM_CASE_CONFIG["I-485"] in app/case_types.py.
"""

import json
from datetime import datetime

from app.extensions import db
from app.models import Form, Service, ServiceCategory
from app.seed_i90 import EYE, HAIR, STATE_OPTIONS, UNIT_TYPES, YES_NO, Builder, _address_fields  # noqa: F401
from app.seed_i90_refine import _label, _tip
from app.seed_n400 import _cfg, intro, note, show_any, show_page_any, yesno
from app.seed_i130 import page, records, where

I485_SLUG = "i-485-client-intake"
SOURCE_NAME = "I-485"
SOURCE_EDITION = "09/18/26"

SECTIONS = [
    {"key": "before", "title": {"en": "Before You Begin", "es": "Antes de empezar"}},
    {"key": "about_you", "title": {"en": "About You", "es": "Sobre ti"}},
    {"key": "adjustment", "title": {"en": "Your Adjustment Application", "es": "Tu solicitud de ajuste"}},
    {"key": "arrival", "title": {"en": "Immigration & Arrival", "es": "Inmigración y llegada"}},
    {"key": "addresses", "title": {"en": "Address History", "es": "Historial de direcciones"}},
    {"key": "family", "title": {"en": "Family & Relationships", "es": "Familia y relaciones"}},
    {"key": "employment", "title": {"en": "Employment & Education", "es": "Empleo y estudios"}},
    {"key": "history", "title": {"en": "Immigration History", "es": "Historial migratorio"}},
    {"key": "elig_groups", "title": {"en": "Eligibility Questions — Groups & Organizations", "es": "Preguntas de elegibilidad — Grupos y organizaciones"}},
    {"key": "elig_immigration", "title": {"en": "Eligibility Questions — Immigration", "es": "Preguntas de elegibilidad — Inmigración"}},
    {"key": "elig_criminal", "title": {"en": "Eligibility Questions — Criminal Matters", "es": "Preguntas de elegibilidad — Asuntos penales"}},
    {"key": "elig_security", "title": {"en": "Eligibility Questions — Security", "es": "Preguntas de elegibilidad — Seguridad"}},
    {"key": "elig_public_charge", "title": {"en": "Eligibility Questions — Public Charge", "es": "Preguntas de elegibilidad — Carga pública"}},
    {"key": "elig_violations", "title": {"en": "Eligibility Questions — Immigration Violations", "es": "Preguntas de elegibilidad — Violaciones migratorias"}},
    {"key": "elig_misc", "title": {"en": "Eligibility Questions — Other Conduct", "es": "Preguntas de elegibilidad — Otra conducta"}},
    {"key": "contact", "title": {"en": "Contact & Interpreter", "es": "Contacto e intérprete"}},
    {"key": "documents", "title": {"en": "Documents", "es": "Documentos"}},
    {"key": "confirm", "title": {"en": "Confirmation", "es": "Confirmación"}},
]

CONTEXTS = {
    "applicant": {"title": {"en": "Applicant", "es": "Solicitante"},
                  "subtitle": {"en": "The person applying for lawful permanent residence.", "es": "La persona que solicita la residencia permanente."},
                  "tone": "accent", "icon": "person"},
}
CONTEXT_ROLES = {"applicant": "applicant"}

CORRECT_OPTS = [("correct", "Yes, this is correct", "Sí, es correcto"), ("edit", "Review / Edit", "Revisar / Editar")]
CURRENT_OPTS = [("correct", "Yes, this is still current", "Sí, sigue vigente"), ("edit", "No, I need to update it", "No, necesito actualizarlo")]


def _confirm_opts(key, form_name="I-485"):
    from app.case_types import FORM_CASE_CONFIG
    from app.shared_blocks import block_scope

    return CURRENT_OPTS if block_scope(FORM_CASE_CONFIG[form_name]["blocks"][key]) == "situational" else CORRECT_OPTS
UNSURE = ("unsure", "Not sure — OG will review", "No estoy seguro(a) — OG lo revisará")
YN_UNSURE = YES_NO + [UNSURE]
REVIEW_FLAG = ("OG will look at this answer with you.", "OG revisará esta respuesta contigo.")

WHERE_A = ("Your A-Number (Alien Registration Number) is 7 to 9 digits and usually starts with “A”. It may appear on a Green Card, a work permit (EAD) or other USCIS documents, where it can be labelled “A-Number”, “Alien Registration Number” or “USCIS #”, and on USCIS notices. If you have none, choose No.",
           "Tu Número A (Número de Registro de Extranjero) tiene de 7 a 9 dígitos y normalmente empieza con “A”. Puede aparecer en una Green Card, un permiso de trabajo (EAD) u otros documentos de USCIS, donde puede llamarse “A-Number”, “Alien Registration Number” o “USCIS #”, y en las notificaciones de USCIS. Si no tienes, elige No.")
WHERE_ACCT = ("If you have a USCIS online account, the number appears in that account and on some USCIS notices. Leave it blank if you have no account.",
              "Si tienes una cuenta en línea de USCIS, el número aparece en esa cuenta y en algunas notificaciones de USCIS. Déjalo en blanco si no tienes cuenta.")
WHERE_SSN = ("A Social Security number has 9 digits and is on your Social Security card.", "Un número de Seguro Social tiene 9 dígitos y está en tu tarjeta del Seguro Social.")
WHERE_I94 = ("The Form I-94 Arrival/Departure Record number identifies your admission to the United States. Many people can get their most recent electronic I-94 from U.S. Customs and Border Protection's official I-94 website, or it may be on a paper I-94 card stapled in the passport.",
             "El número del Formulario I-94 (Registro de Llegada/Salida) identifica tu admisión a los Estados Unidos. Muchas personas pueden obtener su I-94 electrónico más reciente en el sitio web oficial de I-94 de la Oficina de Aduanas y Protección Fronteriza (CBP), o puede estar en una tarjeta I-94 de papel grapada al pasaporte.")
WHERE_CLASS = ("The status or class of admission is shown on the I-94 record (for example B-2 for a visitor, or “paroled”) and on the visa in the passport.",
               "El estatus o clase de admisión aparece en el registro I-94 (por ejemplo B-2 para un visitante, o “paroled”) y en la visa del pasaporte.")
WHERE_PASSPORT = ("This is the passport or travel document you showed when you last arrived. The number, issue country and expiration date are on its photo page.",
                  "Es el pasaporte o documento de viaje que mostraste en tu última llegada. El número, el país emisor y la fecha de vencimiento están en la página con la foto.")
WHERE_VISA = ("If you arrived on a visa, the visa number is printed in red on the visa stamp in your passport. Leave it blank if you did not use a visa.",
              "Si llegaste con una visa, el número de la visa está impreso en rojo en el sello de la visa de tu pasaporte. Déjalo en blanco si no usaste una visa.")


def kp(b, name, block=None, system=False):
    """Mark an answer as part of a shared block: kept while its step is skipped; `system` = bookkeeping, hidden from Review."""
    f = b.fields[name]
    cfg = json.loads(f.config_json) if f.config_json else {}
    cfg["keep"] = True
    if block:
        cfg["block"] = block
    if system:
        cfg["system"] = True
    f.config_json = json.dumps(cfg, ensure_ascii=False)
    return f


def choice(b, name, label, ref, opts, *, req=True, help=None, note_=None, width="full", dropdown=False):
    return b.field(name, "dropdown" if dropdown else "single_choice", label, ref=ref, req=req, opts=opts, help=help, note=note_, width=width)


def only_if(b, target, *conds):
    b.rule("show_field", target, list(conds))


def any_of(b, target, *groups):
    show_any(b, target, [list(g) for g in groups])


def block_pair(b, key, *, group, review_title, review_desc, edit_title, edit_desc, gates=None, edit_extra_no=(), needed=(), build_edit, form_name="I-485", ctx="applicant", ask_missing=False, extra_edit=()):
    """A "We already have this information" review step + the ordinary edit step, on the same shared block.

    review step: shown when the case has the facts (`<key>_avail == yes`) and one of `gates` holds (each gate = AND-list).
    edit step:   shown when there was nothing to reuse (plus `edit_extra_no`), or the applicant chose "I need to change something",
                 or — after "Everything is correct" — while a `needed` detail the case could not supply is still empty.
    """
    gates = [list(g) for g in (gates or [[]])]
    page(b, f"{key}_review", review_title, review_desc, group=group, ctx=ctx)
    b.field(f"{key}_card", "paragraph", ("", ""), content=("", ""))
    b.fields[f"{key}_card"].config_json = json.dumps({"dynamic": {"shared_block": key}})
    b.field(key, "single_choice", ("Is this information correct?", "¿Esta información es correcta?"), ref="OG confirmation (shared case information)",
            note="The applicant confirmed (or changed) what the case already knew. Recorded against the canonical person facts with provenance.",
            req=True, opts=_confirm_opts(key, form_name))
    kp(b, key, system=True)
    show_page_any(b, f"{key}_review", [[(f"{key}_avail", "equals", "yes")] + g for g in gates])
    edit_page = page(b, f"{key}_edit", edit_title, edit_desc, group=group, ctx=ctx)
    build_edit()
    for f in edit_page.fields:  # every answer on the edit step is kept: the step may drop off the path once its details are complete
        if not f.is_content_only:
            kp(b, f.internal_name, block=key)
    show_page_any(b, f"{key}_edit", [[(f"{key}_avail", "equals", "no"), *edit_extra_no] + g for g in gates] + [[(key, "equals", "edit")] + g for g in gates]
                  + [[(key, "equals", "correct"), (n, "is_empty", "")] + g for n in needed for g in gates]
                  + ([[(key, "equals", "correct"), (f"{key}_missing", "is_not_empty", "")] + g for g in gates] if ask_missing else [])
                  + [[(key, "equals", "correct"), *grp] + g for grp in extra_edit for g in gates])


def mark_block_fields(b, key, names):
    for n in names:
        kp(b, n, block=key)


def build_i485(form):
    b = Builder(form)
    # ---- never-shown system page: the frozen "does the case already know this?" flags
    page(b, "sys", ("Case information", "Información del caso"), group=None)
    blocks = ["sb_name", "sb_birth", "sb_othernames", "sb_ids", "sb_uscis", "sb_ssn", "sb_i94", "sb_arrival", "sb_address", "sb_addr_history", "sb_employment",
              "sb_parents", "sb_spouse", "sb_contact"]
    for k in blocks:
        b.field(f"{k}_avail", "short_answer", (f"{k} available", f"{k} disponible"), ref="OG system flag (never shown)")
        kp(b, f"{k}_avail", system=True)
    show_page_any(b, "sys", [[("sb_name_avail", "equals", "__never__")]])

    # ================================================================== Before you begin
    page(b, "intro", ("Before you begin", "Antes de empezar"), group="before", ctx="applicant")
    b.field("intro_1", "paragraph", ("", ""), content=(
        "This intake collects what OG Multiservices needs to prepare Form I-485, Application to Register Permanent Residence or Adjust Status (USCIS edition 09/18/26). Your answers save automatically, so you can stop and come back anytime.",
        "Este formulario reúne lo que OG Multiservices necesita para preparar el Formulario I-485, Solicitud para Registrar la Residencia Permanente o Ajustar el Estatus (edición USCIS 09/18/26). Tus respuestas se guardan automáticamente, así que puedes parar y volver cuando quieras."))
    b.field("intro_case", "paragraph", ("", ""), content=("", ""))
    b.fields["intro_case"].config_json = json.dumps({"dynamic": {"kind": "context"}})
    b.field("intro_2", "paragraph", ("", ""), content=(
        "If we already have information about the applicant from another application in this case, we will show it to you first so you can confirm it instead of typing it again. Nothing is reused without your confirmation.",
        "Si ya tenemos información del solicitante de otra solicitud en este caso, te la mostraremos primero para que la confirmes en lugar de escribirla de nuevo. Nada se reutiliza sin tu confirmación."))
    b.field("intro_3", "paragraph", ("", ""), content=(
        "OG Multiservices provides document preparation and administrative assistance. We are not a law firm and do not provide legal advice or representation. We cannot tell you whether you qualify, which category to choose, or whether any answer affects your case. Sending this to OG does not file anything with USCIS.",
        "OG Multiservices ofrece preparación de documentos y asistencia administrativa. No somos un bufete de abogados ni brindamos asesoría o representación legal. No podemos decirte si calificas, qué categoría elegir ni si alguna respuesta afecta tu caso. Enviar esto a OG no presenta nada ante USCIS."))

    # ================================================================== ABOUT YOU — Part 1 items 1-9, 19; Part 8
    def edit_name():
        b.field("a_family", "short_answer", ("Family name (last name)", "Apellido"), ref="Part 1, Item 1.a", req=True, width="half", maxlen=60)
        b.field("a_given", "short_answer", ("Given name (first name)", "Nombre(s)"), ref="Part 1, Item 1.b", req=True, width="half", maxlen=60)
        b.field("a_middle", "short_answer", ("Middle name (if applicable)", "Segundo nombre (si aplica)"), ref="Part 1, Item 1.c", width="half", maxlen=60,
                help=("Do not use a nickname here — nicknames go in the next step.", "No uses un apodo aquí; los apodos van en el siguiente paso."))
        mark_block_fields(b, "sb_name", ["a_family", "a_given", "a_middle"])
    block_pair(b, "sb_name", group="about_you",
               review_title=("We already have {app}'s legal name", "Ya tenemos el nombre legal de {app}"),
               review_desc=("This is the name from earlier in your case. Confirm it or change it.", "Es el nombre de un paso anterior de tu caso. Confírmalo o cámbialo."),
               edit_title=("Your current legal name", "Tu nombre legal actual"),
               edit_desc=("Use the name exactly as it is on your current legal documents. Do not provide a nickname.", "Usa el nombre exactamente como aparece en tus documentos legales actuales. No des un apodo."),
               build_edit=edit_name)

    def edit_othernames():
        records(b, "a_other_names", ("Other names you have used since birth", "Otros nombres que has usado desde que naciste"), "Part 1, Item 2", "other_name", max=10,
                help=("Include your family name at birth, other legal names, nicknames, aliases and assumed names. If none, just continue.",
                      "Incluye tu apellido de nacimiento, otros nombres legales, apodos, alias y nombres supuestos. Si no tienes, solo continúa."))
        mark_block_fields(b, "sb_othernames", ["a_other_names"])
    block_pair(b, "sb_othernames", group="about_you",
               review_title=("We already have the other names {app} has used", "Ya tenemos los otros nombres que ha usado {app}"),
               review_desc=("Confirm this list or change it.", "Confirma esta lista o cámbiala."),
               edit_title=("Other names you have used", "Otros nombres que has usado"),
               edit_desc=("Provide all other names you have ever used since birth, including your family name at birth, other legal names, nicknames, aliases and assumed names.",
                          "Indica todos los demás nombres que has usado desde que naciste, incluidos tu apellido de nacimiento, otros nombres legales, apodos, alias y nombres supuestos."),
               build_edit=edit_othernames)

    def edit_birth():
        b.field("a_dob", "date", ("Date of birth", "Fecha de nacimiento"), ref="Part 1, Item 3", req=True, date_rule="past", width="half")
        b.field("a_sex", "single_choice", ("Sex", "Sexo"), ref="Part 1, Item 6", req=True, opts=[("male", "Male", "Masculino"), ("female", "Female", "Femenino")])
        b.field("a_birth_city", "short_answer", ("City or town of birth", "Ciudad o pueblo de nacimiento"), ref="Part 1, Item 7 (City or Town of Birth)", req=True, width="half", maxlen=60)
        b.field("a_birth_country", "short_answer", ("Country of birth", "País de nacimiento"), ref="Part 1, Item 7 (Country of Birth)", req=True, width="half", maxlen=60)
        b.field("a_citizenship", "short_answer", ("Country of citizenship or nationality", "País de ciudadanía o nacionalidad"), ref="Part 1, Item 8", req=True, maxlen=60,
                help=("If you have more than one, give the one on the passport you used to arrive; add the other in “Anything else” at the end.", "Si tienes más de una, indica la del pasaporte con el que llegaste; agrega la otra en “¿Algo más?” al final."))
        mark_block_fields(b, "sb_birth", ["a_dob", "a_sex", "a_birth_city", "a_birth_country", "a_citizenship"])
    block_pair(b, "sb_birth", group="about_you", needed=["a_citizenship"],
               review_title=("We already have {app}'s birth information", "Ya tenemos los datos de nacimiento de {app}"),
               review_desc=("Confirm this information or change it.", "Confirma esta información o cámbiala."),
               edit_title=("Birth and citizenship", "Nacimiento y ciudadanía"),
               edit_desc=("The form asks for your date of birth, sex, place of birth and country of citizenship or nationality.", "El formulario pide tu fecha de nacimiento, sexo, lugar de nacimiento y país de ciudadanía o nacionalidad."),
               build_edit=edit_birth)

    page(b, "a_other_dob_page", ("Other dates of birth", "Otras fechas de nacimiento"), group="about_you", ctx="applicant")
    b.field("a_other_dob", "single_choice", ("Have you ever used any other date of birth?", "¿Has usado alguna vez otra fecha de nacimiento?"), ref="Part 1, Item 3 (other dates of birth)", req=True, opts=YES_NO)
    records(b, "a_other_dobs", ("Other dates of birth you have used", "Otras fechas de nacimiento que has usado"), "Part 1, Item 3 (other dates of birth)", "i485_other_dob", req=True, max=5)
    only_if(b, "a_other_dobs", ("a_other_dob", "equals", "yes"))

    def edit_ids():
        b.field("a_has_anumber", "single_choice", ("Do you have an Alien Registration Number (A-Number)?", "¿Tienes un Número de Registro de Extranjero (Número A)?"), ref="Part 1, Item 4", req=True, opts=YES_NO)
        b.field("a_anumber", "short_answer", ("A-Number", "Número A"), ref="Part 1, Item 4 (A-Number)", req=True, sensitive=True, pattern=r"A?-?\d{7,9}", maxlen=12,
                msg=("Enter 7 to 9 digits, with or without “A-”.", "Ingresa 7 a 9 dígitos, con o sin “A-”."))
        where(b, "a_anumber", *WHERE_A)
        only_if(b, "a_anumber", ("a_has_anumber", "equals", "yes"))
        mark_block_fields(b, "sb_ids", ["a_has_anumber", "a_anumber"])
    block_pair(b, "sb_ids", group="about_you",
               review_title=("We already have {app}'s A-Number", "Ya tenemos el Número A de {app}"),
               review_desc=("Confirm it or change it.", "Confírmalo o cámbialo."),
               edit_title=("Your A-Number", "Tu Número A"), edit_desc=None, build_edit=edit_ids)
    page(b, "a_other_anumber_page", ("Other A-Numbers", "Otros Números A"), group="about_you", ctx="applicant")
    b.field("a_other_anumber", "single_choice", ("Have you ever used, or been assigned, any other A-Number?", "¿Has usado o se te ha asignado alguna vez otro Número A?"), ref="Part 1, Item 5", req=True, opts=YES_NO)
    b.field("a_other_anumbers", "short_answer", ("Provide the other A-Numbers", "Indica los otros Números A"), ref="Part 1, Item 5 (A-Numbers)", req=True, sensitive=True, maxlen=120,
            help=("Separate them with commas.", "Sepáralos con comas."))
    only_if(b, "a_other_anumbers", ("a_other_anumber", "equals", "yes"))

    def edit_uscis():
        b.field("a_uscis_account", "short_answer", ("USCIS Online Account Number (if any)", "Número de cuenta en línea de USCIS (si tienes)"), ref="Part 1, Item 9", maxlen=12,
                pattern=r"\d{1,12}", msg=("Use digits only (up to 12).", "Usa solo dígitos (hasta 12)."),
                help=("If one has been assigned, you can find it on a notice USCIS may have sent you. Leave it blank if you have none.", "Si se te asignó uno, puedes encontrarlo en una notificación que USCIS te haya enviado. Déjalo en blanco si no tienes."))
        where(b, "a_uscis_account", *WHERE_ACCT)
        mark_block_fields(b, "sb_uscis", ["a_uscis_account"])
    block_pair(b, "sb_uscis", group="about_you",
               review_title=("We already have {app}'s USCIS online account number", "Ya tenemos el número de cuenta en línea de USCIS de {app}"),
               review_desc=("Confirm it or change it.", "Confírmalo o cámbialo."),
               edit_title=("USCIS online account", "Cuenta en línea de USCIS"), edit_desc=None, build_edit=edit_uscis)

    def edit_ssn():
        b.field("a_ssn_issued", "single_choice", ("Has the Social Security Administration (SSA) ever officially issued a Social Security card to you?", "¿La Administración del Seguro Social (SSA) te ha emitido alguna vez oficialmente una tarjeta del Seguro Social?"),
                ref="Part 1, Item 19 (card ever issued)", req=True, opts=YES_NO)
        b.field("a_ssn", "short_answer", ("U.S. Social Security Number (SSN)", "Número de Seguro Social de EE. UU. (SSN)"), ref="Part 1, Item 19 (SSN)", req=True, sensitive=True,
                pattern=r"\d{3}-?\d{2}-?\d{4}", msg=("Enter 9 digits.", "Ingresa 9 dígitos."))
        where(b, "a_ssn", *WHERE_SSN)
        only_if(b, "a_ssn", ("a_ssn_issued", "equals", "yes"))
        mark_block_fields(b, "sb_ssn", ["a_ssn_issued", "a_ssn"])
    block_pair(b, "sb_ssn", group="about_you",
               review_title=("We already have {app}'s Social Security number", "Ya tenemos el número de Seguro Social de {app}"),
               review_desc=("Confirm it or change it.", "Confírmalo o cámbialo."),
               edit_title=("Social Security card", "Tarjeta del Seguro Social"), edit_desc=None, build_edit=edit_ssn)
    page(b, "a_ssn_request", ("Requesting a Social Security card", "Solicitud de tarjeta del Seguro Social"), group="about_you", ctx="applicant")
    b.field("a_ssn_want", "single_choice", ("Do you want the SSA to issue you a Social Security card?", "¿Quieres que la SSA te emita una tarjeta del Seguro Social?"), ref="Part 1, Item 19 (want a card)", req=True, opts=YES_NO,
            help=("If you answer Yes, the form also asks for your consent below.", "Si respondes Sí, el formulario también pide tu consentimiento abajo."))
    b.field("a_ssn_consent", "single_choice", ("Consent for disclosure: I authorize disclosure of information from this application to the SSA as required for the purpose of assigning me an SSN and issuing me a Social Security card.",
                                             "Consentimiento de divulgación: autorizo la divulgación de información de esta solicitud a la SSA según se requiera con el fin de asignarme un SSN y emitirme una tarjeta del Seguro Social."),
            ref="Part 1, Item 19 (Consent for Disclosure)", req=True, opts=YES_NO,
            note="The form says a Yes to wanting a card requires Yes here. It is shown only when the applicant wants a card; when not, the box is left blank.")
    only_if(b, "a_ssn_consent", ("a_ssn_want", "equals", "yes"))

    page(b, "bio_1", ("Ethnicity and race", "Etnia y raza"), group="about_you", ctx="applicant")
    b.field("a_ethnicity", "single_choice", ("Ethnicity (select only one)", "Etnia (selecciona solo una)"), ref="Part 8, Item 1", req=True,
            opts=[("hispanic", "Hispanic or Latino", "Hispano o Latino"), ("not_hispanic", "Not Hispanic or Latino", "No hispano ni latino")])
    b.field("a_race", "multi_choice", ("Race (select all that apply)", "Raza (selecciona todas las que apliquen)"), ref="Part 8, Item 2", req=True,
            opts=[("american_indian", "American Indian or Alaska Native", "Indígena americano o nativo de Alaska"), ("asian", "Asian", "Asiático"),
                  ("black", "Black or African American", "Negro o afroamericano"), ("pacific_islander", "Native Hawaiian or Other Pacific Islander", "Nativo de Hawái u otra isla del Pacífico"),
                  ("white", "White", "Blanco")])
    page(b, "bio_2", ("Physical description", "Descripción física"), group="about_you", ctx="applicant")
    b.field("a_height_ft", "dropdown", ("Height — feet", "Estatura — pies"), ref="Part 8, Item 3", req=True, width="half", opts=[(str(n), str(n), str(n)) for n in range(2, 9)])
    b.field("a_height_in", "dropdown", ("Height — inches", "Estatura — pulgadas"), ref="Part 8, Item 3", req=True, width="half", opts=[(str(n), str(n), str(n)) for n in range(0, 12)])
    b.field("a_weight", "number", ("Weight (pounds)", "Peso (libras)"), ref="Part 8, Item 4", req=True, minv=1, maxv=999, width="half")
    b.field("a_eye", "dropdown", ("Eye color", "Color de ojos"), ref="Part 8, Item 5", req=True, opts=EYE, width="half")
    b.field("a_hair", "dropdown", ("Hair color", "Color de cabello"), ref="Part 8, Item 6", req=True, opts=HAIR, width="half")

    # ================================================================== YOUR ADJUSTMENT APPLICATION — Parts 2 and 3
    page(b, "p2_eoir", ("Court proceedings", "Procesos ante la corte"), group="adjustment", ctx="applicant")
    b.field("p2_eoir", "single_choice", ("Are you filing for adjustment of status with the Executive Office for Immigration Review (EOIR) while in removal, exclusion, rescission, or deportation proceedings?",
                                         "¿Estás solicitando el ajuste de estatus ante la Oficina Ejecutiva de Revisión de Inmigración (EOIR) mientras estás en procedimientos de remoción, exclusión, rescisión o deportación?"),
            ref="Part 2, Item 1", req=True, opts=YN_UNSURE, help=("If you are not sure, choose “Not sure” and OG will look at it with you.", "Si no estás seguro(a), elige “No estoy seguro(a)” y OG lo revisará contigo."))

    page(b, "p2_petition", ("The petition behind this application", "La petición en que se basa esta solicitud"),
         ("Some applications are based on a petition (for example a Form I-130). OG does not decide this for you — tell us what you know.", "Algunas solicitudes se basan en una petición (por ejemplo un Formulario I-130). OG no lo decide por ti: cuéntanos lo que sabes."),
         group="adjustment", ctx="applicant")
    b.field("p2_petition_card", "paragraph", ("", ""), content=("", ""))
    b.fields["p2_petition_card"].config_json = json.dumps({"dynamic": {"kind": "underlying"}})
    choice(b, "b_underlying", ("Is this Form I-485 based on the petition shown above?", "¿Este Formulario I-485 se basa en la petición que aparece arriba?"), "OG helper (links the I-130 in this case)",
           [("yes", "Yes — it is based on that petition", "Sí — se basa en esa petición"), ("no", "No — it is not based on that petition", "No — no se basa en esa petición"), UNSURE],
           note_="Links the related petition inside the case; it does not choose a category or say anything about eligibility.")
    b.field("b_receipt", "short_answer", ("Receipt number of the underlying petition (if any)", "Número de recibo de la petición subyacente (si tienes)"), ref="Part 2, Item 2 (Receipt Number)", maxlen=20,
            pattern=r"[A-Za-z0-9-]{10,16}", msg=("A receipt number has 13 letters and digits, for example the 3 letters and 10 digits on a USCIS notice.", "Un número de recibo tiene 13 letras y dígitos, por ejemplo las 3 letras y 10 dígitos de una notificación de USCIS."),
            help=("It is on the USCIS receipt notice (Form I-797). Leave it blank if you do not have one yet.", "Está en la notificación de recibo de USCIS (Formulario I-797). Déjalo en blanco si aún no lo tienes."))
    b.field("b_priority", "date", ("Priority date from the underlying petition (if any)", "Fecha de prioridad de la petición subyacente (si tienes)"), ref="Part 2, Item 2 (Priority Date)", width="half")

    page(b, "p2_role", ("Principal or derivative applicant", "Solicitante principal o derivado"), group="adjustment", ctx="applicant")
    choice(b, "b_role", ("I am filing this Form I-485 as a…", "Presento este Formulario I-485 como…"), "Part 2 (filing as)",
           [("principal", "Principal applicant", "Solicitante principal"), ("derivative", "Derivative applicant (I apply through someone else's application)", "Solicitante derivado (solicito a través de la solicitud de otra persona)"), UNSURE],
           help=("Select only one.", "Selecciona solo una."))
    page(b, "p2_principal", ("The principal applicant", "El solicitante principal"), ("Information about the principal applicant.", "Información sobre el solicitante principal."), group="adjustment", ctx="applicant")
    b.field("b_pa_family", "short_answer", ("Principal applicant's family name (last name)", "Apellido del solicitante principal"), ref="Part 2 (Principal Applicant's Name)", req=True, width="half", maxlen=60)
    b.field("b_pa_given", "short_answer", ("Principal applicant's given name (first name)", "Nombre del solicitante principal"), ref="Part 2 (Principal Applicant's Name)", req=True, width="half", maxlen=60)
    b.field("b_pa_middle", "short_answer", ("Middle name (if applicable)", "Segundo nombre (si aplica)"), ref="Part 2 (Principal Applicant's Name)", width="half", maxlen=60)
    b.field("b_pa_anumber", "short_answer", ("Principal applicant's A-Number (if any)", "Número A del solicitante principal (si tiene)"), ref="Part 2 (Principal Applicant's A-Number)", sensitive=True, pattern=r"A?-?\d{7,9}", maxlen=12,
            msg=("Enter 7 to 9 digits, with or without “A-”.", "Ingresa 7 a 9 dígitos, con o sin “A-”."), width="half")
    b.field("b_pa_dob", "date", ("Principal applicant's date of birth", "Fecha de nacimiento del solicitante principal"), ref="Part 2 (Principal Applicant's Date of Birth)", req=True, date_rule="past", width="half")
    show_page_any(b, "p2_principal", [[("b_role", "equals", "derivative")]])

    # -- Item 3: the category (only ONE); the customer chooses, OG never suggests one
    page(b, "p2_category", ("Category of your application", "Categoría de tu solicitud"),
         ("The form asks you to select ONLY ONE category. Pick the group that matches how you are applying; the next step lists the exact choices printed on the form. OG never picks a category for you.",
          "El formulario pide seleccionar SOLO UNA categoría. Elige el grupo que corresponde a cómo estás solicitando; el siguiente paso muestra las opciones exactas del formulario. OG nunca elige una categoría por ti."),
         group="adjustment", ctx="applicant")
    choice(b, "b_cat_group", ("I am applying based on the following category…", "Estoy solicitando con base en la siguiente categoría…"), "Part 2, Item 3 (3.a–3.g)",
           [("family", "Family-based", "Basada en la familia"), ("employment", "Employment-based", "Basada en el empleo"), ("special_immigrant", "Special immigrant", "Inmigrante especial"),
            ("asylee_refugee", "Asylee or refugee", "Asilado o refugiado"), ("victim", "Human trafficking victim or crime victim", "Víctima de trata de personas o víctima de un delito"),
            ("special_programs", "Special programs based on certain public laws", "Programas especiales basados en ciertas leyes públicas"),
            ("additional", "Additional options (for example the Diversity Visa program or Registry)", "Opciones adicionales (por ejemplo el programa de Visa de Diversidad o Registro)"), UNSURE],
           help=("You must select only one category. If you are a derivative applicant, pick the category the principal applicant is applying under.", "Debes seleccionar solo una categoría. Si eres solicitante derivado, elige la categoría bajo la cual solicita el solicitante principal."))
    note(b, "b_cat_unsure_note", "That is fine. OG will go through the category with you before anything is prepared.", "Está bien. OG revisará contigo la categoría antes de preparar nada.")
    only_if(b, "b_cat_unsure_note", ("b_cat_group", "equals", "unsure"))

    page(b, "p2_cat_family", ("Family-based category", "Categoría basada en la familia"), ("Part 2, Item 3.a. Select only one.", "Parte 2, Ítem 3.a. Selecciona solo una."), group="adjustment", ctx="applicant")
    choice(b, "b_cat_fam", ("Which one applies?", "¿Cuál aplica?"), "Part 2, Item 3.a", [
        ("fam_spouse_usc", "Immediate relative of a U.S. citizen — Spouse of a U.S. Citizen", "Familiar inmediato de un ciudadano de EE. UU. — Cónyuge de un ciudadano de EE. UU."),
        ("fam_child_usc", "Immediate relative of a U.S. citizen — Unmarried child under 21 years of age of a U.S. citizen", "Familiar inmediato de un ciudadano de EE. UU. — Hijo(a) soltero(a) menor de 21 años de un ciudadano de EE. UU."),
        ("fam_parent_usc", "Immediate relative of a U.S. citizen — Parent of a U.S. citizen (if the citizen is at least 21 years of age)", "Familiar inmediato de un ciudadano de EE. UU. — Padre o madre de un ciudadano de EE. UU. (si el ciudadano tiene al menos 21 años)"),
        ("fam_fiance", "Immediate relative of a U.S. citizen — Person admitted as a fiancé(e) or child of a fiancé(e) of a U.S. citizen (K-1/K-2 Nonimmigrant)", "Familiar inmediato de un ciudadano de EE. UU. — Persona admitida como prometido(a) o hijo(a) de un prometido(a) de un ciudadano de EE. UU. (K-1/K-2)"),
        ("fam_widow_usc", "Immediate relative of a U.S. citizen — Widow or widower of a U.S. citizen", "Familiar inmediato de un ciudadano de EE. UU. — Viudo(a) de un ciudadano de EE. UU."),
        ("fam_ndaa", "Immediate relative of a U.S. citizen — Spouse, child, or parent of a deceased U.S. active-duty service member in the armed forces under the National Defense Authorization Act (NDAA)", "Familiar inmediato de un ciudadano de EE. UU. — Cónyuge, hijo(a) o padre/madre de un miembro del servicio activo de las fuerzas armadas de EE. UU. fallecido, según la Ley de Autorización de Defensa Nacional (NDAA)"),
        ("fam_son_daughter_usc_unmarried", "Other relative of a U.S. citizen — Unmarried son or daughter of a U.S. citizen and I am 21 years of age or older", "Otro familiar de un ciudadano de EE. UU. — Hijo(a) soltero(a) de un ciudadano de EE. UU. y tengo 21 años o más"),
        ("fam_son_daughter_usc_married", "Other relative of a U.S. citizen — Married son or daughter of a U.S. citizen", "Otro familiar de un ciudadano de EE. UU. — Hijo(a) casado(a) de un ciudadano de EE. UU."),
        ("fam_sibling_usc", "Other relative of a U.S. citizen — Brother or sister of a U.S. citizen (if the citizen is at least 21 years of age)", "Otro familiar de un ciudadano de EE. UU. — Hermano(a) de un ciudadano de EE. UU. (si el ciudadano tiene al menos 21 años)"),
        ("fam_spouse_lpr", "Relative of a lawful permanent resident — Spouse of a lawful permanent resident", "Familiar de un residente permanente legal — Cónyuge de un residente permanente legal"),
        ("fam_child_lpr", "Relative of a lawful permanent resident — Unmarried child under 21 years of age of a lawful permanent resident", "Familiar de un residente permanente legal — Hijo(a) soltero(a) menor de 21 años de un residente permanente legal"),
        ("fam_son_daughter_lpr", "Relative of a lawful permanent resident — Unmarried son or daughter of a lawful permanent resident and I am 21 years of age or older", "Familiar de un residente permanente legal — Hijo(a) soltero(a) de un residente permanente legal y tengo 21 años o más"),
        ("fam_vawa_spouse", "VAWA self-petitioner — VAWA self-petitioning spouse of a U.S. citizen or lawful permanent resident", "Autopeticionario VAWA — Cónyuge autopeticionario VAWA de un ciudadano de EE. UU. o residente permanente legal"),
        ("fam_vawa_child", "VAWA self-petitioner — VAWA self-petitioning child of a U.S. citizen or lawful permanent resident", "Autopeticionario VAWA — Hijo(a) autopeticionario VAWA de un ciudadano de EE. UU. o residente permanente legal"),
        ("fam_vawa_parent", "VAWA self-petitioner — VAWA self-petitioning parent of a U.S. citizen (if the citizen is at least 21 years of age)", "Autopeticionario VAWA — Padre o madre autopeticionario VAWA de un ciudadano de EE. UU. (si el ciudadano tiene al menos 21 años)"),
    ])
    only_page = lambda key, grp: show_page_any(b, key, [[("b_cat_group", "equals", grp)]])  # noqa: E731
    only_page("p2_cat_family", "family")

    page(b, "p2_cat_emp", ("Employment-based category", "Categoría basada en el empleo"), ("Part 2, Item 3.b. Select only one.", "Parte 2, Ítem 3.b. Selecciona solo una."), group="adjustment", ctx="applicant")
    choice(b, "b_cat_emp", ("Which one applies?", "¿Cuál aplica?"), "Part 2, Item 3.b", [
        ("emp_investor", "Alien Investor, Form I-526 or Form I-526E", "Inversionista extranjero, Formulario I-526 o I-526E"),
        ("emp_extraordinary", "Alien Worker (Form I-140) — Alien of Extraordinary Ability", "Trabajador extranjero (Formulario I-140) — Extranjero con habilidad extraordinaria"),
        ("emp_professor", "Alien Worker (Form I-140) — Outstanding Professor or Researcher", "Trabajador extranjero (Formulario I-140) — Profesor o investigador destacado"),
        ("emp_executive", "Alien Worker (Form I-140) — Multinational Executive or Manager", "Trabajador extranjero (Formulario I-140) — Ejecutivo o gerente multinacional"),
        ("emp_advanced", "Alien Worker (Form I-140) — Member of the Professions Holding an Advanced Degree or Alien of Exceptional Ability (who is NOT seeking a National Interest Waiver)", "Trabajador extranjero (Formulario I-140) — Miembro de las profesiones con un título avanzado o extranjero con habilidad excepcional (que NO busca una exención de interés nacional)"),
        ("emp_professional", "Alien Worker (Form I-140) — A Professional (at a minimum, requiring a bachelor's degree or a foreign degree equivalent to a U.S. bachelor's degree)", "Trabajador extranjero (Formulario I-140) — Un profesional (como mínimo, que requiere un título de licenciatura o un título extranjero equivalente)"),
        ("emp_skilled", "Alien Worker (Form I-140) — A Skilled Worker (requiring at least 2 years of specialized training or experience)", "Trabajador extranjero (Formulario I-140) — Un trabajador calificado (que requiere al menos 2 años de capacitación o experiencia especializada)"),
        ("emp_other_worker", "Alien Worker (Form I-140) — Any Other Worker (requiring less than 2 years of training or experience)", "Trabajador extranjero (Formulario I-140) — Cualquier otro trabajador (que requiere menos de 2 años de capacitación o experiencia)"),
        ("emp_niw", "Alien Worker (Form I-140) — An Alien Applying For a National Interest Waiver (who IS a member of the professions holding an advanced degree or an alien of exceptional ability)", "Trabajador extranjero (Formulario I-140) — Extranjero que solicita una exención de interés nacional (que SÍ es miembro de las profesiones con un título avanzado o extranjero con habilidad excepcional)"),
    ])
    only_page("p2_cat_emp", "employment")
    page(b, "p2_emp_relative", ("Employment-based: relatives", "Basada en el empleo: familiares"), ("Part 2, Item 3.b follow-up questions for the Form I-140.", "Parte 2, Ítem 3.b: preguntas adicionales sobre el Formulario I-140."), group="adjustment", ctx="applicant")
    choice(b, "b_emp_relative", ("Did a relative file the associated Form I-140 for you (or for the principal applicant if you are a derivative applicant) or does a relative have a significant ownership interest (5 percent or more) in the business that filed Form I-140 for you (or for the principal applicant)?",
                                 "¿Un familiar presentó el Formulario I-140 asociado para ti (o para el solicitante principal si eres derivado) o un familiar tiene una participación significativa (5 por ciento o más) en el negocio que presentó el Formulario I-140 para ti (o para el solicitante principal)?"),
           "Part 2, Item 3.b (relative filed / ownership)", [("na_self", "N/A (I am adjusting on the basis of a Form I-140 self-petition)", "N/A (estoy ajustando con base en un Formulario I-140 de autopetición)"), ("no", "No", "No"), ("yes", "Yes", "Sí")])
    choice(b, "b_emp_rel_type", ("If you answered “Yes,” is this relative your (select only one)…", "Si respondiste “Sí”, este familiar es tu… (selecciona solo una)"), "Part 2, Item 3.b (relative is your)",
           [("father", "Father", "Padre"), ("mother", "Mother", "Madre"), ("child", "Child", "Hijo(a)"), ("adult_son", "Adult Son", "Hijo adulto"), ("adult_daughter", "Adult Daughter", "Hija adulta"),
            ("brother", "Brother", "Hermano"), ("sister", "Sister", "Hermana"), ("none", "None of These", "Ninguno de estos")])
    only_if(b, "b_emp_rel_type", ("b_emp_relative", "equals", "yes"))
    choice(b, "b_emp_rel_status", ("Is the relative above a…", "El familiar anterior es…"), "Part 2, Item 3.b (relative is a)",
           [("usc", "U.S. Citizen", "Ciudadano de EE. UU."), ("us_national", "U.S. National", "Nacional de EE. UU."), ("lpr", "Lawful Permanent Resident", "Residente permanente legal"), ("none", "None of These", "Ninguno de estos")])
    only_if(b, "b_emp_rel_status", ("b_emp_relative", "equals", "yes"))
    show_page_any(b, "p2_emp_relative", [[("b_cat_group", "equals", "employment"), ("b_cat_emp", "equals", v)] for v in
                                         ("emp_extraordinary", "emp_professor", "emp_executive", "emp_advanced", "emp_professional", "emp_skilled", "emp_other_worker", "emp_niw")])

    page(b, "p2_cat_special", ("Special immigrant category", "Categoría de inmigrante especial"), ("Part 2, Item 3.c. Select only one.", "Parte 2, Ítem 3.c. Selecciona solo una."), group="adjustment", ctx="applicant")
    choice(b, "b_cat_spec", ("Which one applies?", "¿Cuál aplica?"), "Part 2, Item 3.c", [
        ("sp_sij", "Special Immigrant Juvenile, Form I-360", "Inmigrante Juvenil Especial, Formulario I-360"),
        ("sp_afghan_iraqi", "Certain Afghan or Iraqi National, Form I-360 or Form DS-157", "Ciertos nacionales de Afganistán o Irak, Formulario I-360 o DS-157"),
        ("sp_broadcaster", "Certain International Broadcaster, Form I-360", "Cierto locutor internacional, Formulario I-360"),
        ("sp_g4_nato6", "Certain G-4 International Organization or Family Member or NATO-6 Employee or Family Member, Form I-360", "Cierto empleado o familiar de organización internacional G-4 o empleado o familiar NATO-6, Formulario I-360"),
        ("sp_armed_forces", "Certain U.S. Armed Forces Members (also known as the Six and Six program), Form I-360", "Ciertos miembros de las Fuerzas Armadas de EE. UU. (programa “Six and Six”), Formulario I-360"),
        ("sp_panama_canal", "Panama Canal Zone Employees, Form I-360", "Empleados de la Zona del Canal de Panamá, Formulario I-360"),
        ("sp_physician", "Certain Physicians, Form I-360", "Ciertos médicos, Formulario I-360"),
        ("sp_usg_abroad", "Certain Employee or Former Employee of the U.S. Government Abroad, DS-1884", "Cierto empleado o ex empleado del gobierno de EE. UU. en el extranjero, DS-1884"),
        ("sp_minister", "Religious Worker, Form I-360 — Minister of Religion", "Trabajador religioso, Formulario I-360 — Ministro de religión"),
        ("sp_religious_other", "Religious Worker, Form I-360 — Other Religious Worker", "Trabajador religioso, Formulario I-360 — Otro trabajador religioso"),
    ])
    only_page("p2_cat_special", "special_immigrant")

    page(b, "p2_cat_asylee", ("Asylee or refugee", "Asilado o refugiado"), ("Part 2, Item 3.d. Select only one.", "Parte 2, Ítem 3.d. Selecciona solo una."), group="adjustment", ctx="applicant")
    choice(b, "b_cat_asy", ("Which one applies?", "¿Cuál aplica?"), "Part 2, Item 3.d", [
        ("asylum", "Asylum Status (Immigration and Nationality Act (INA) section 208), Form I-589 or Form I-730", "Estatus de asilo (sección 208 de la Ley de Inmigración y Nacionalidad (INA)), Formulario I-589 o I-730"),
        ("refugee", "Refugee Status (INA section 207), Form I-590 or Form I-730", "Estatus de refugiado (sección 207 de la INA), Formulario I-590 o I-730")])
    b.field("b_asylum_date", "date", ("Date you were granted asylum", "Fecha en que se te concedió asilo"), ref="Part 2, Item 3.d (asylum date)", req=True, date_rule="past", width="half")
    only_if(b, "b_asylum_date", ("b_cat_asy", "equals", "asylum"))
    b.field("b_refugee_date", "date", ("Date of initial admission as a refugee", "Fecha de la admisión inicial como refugiado"), ref="Part 2, Item 3.d (refugee date)", req=True, date_rule="past", width="half")
    only_if(b, "b_refugee_date", ("b_cat_asy", "equals", "refugee"))
    only_page("p2_cat_asylee", "asylee_refugee")

    page(b, "p2_cat_victim", ("Human trafficking or crime victim", "Víctima de trata de personas o de un delito"), ("Part 2, Item 3.e. Select only one.", "Parte 2, Ítem 3.e. Selecciona solo una."), group="adjustment", ctx="applicant")
    choice(b, "b_cat_vic", ("Which one applies?", "¿Cuál aplica?"), "Part 2, Item 3.e", [
        ("vic_t", "Human Trafficking Victim (T Nonimmigrant), Form I-914 or Derivative Family Member, Form I-914A", "Víctima de trata de personas (no inmigrante T), Formulario I-914 o familiar derivado, Formulario I-914A"),
        ("vic_u", "Victim of Qualifying Criminal Activity (U Nonimmigrant), Form I-918, Derivative Family Member, Form I-918A, or Qualifying Family Member, Form I-929", "Víctima de actividad delictiva calificada (no inmigrante U), Formulario I-918, familiar derivado, Formulario I-918A, o familiar calificado, Formulario I-929")])
    only_page("p2_cat_victim", "victim")

    page(b, "p2_cat_programs", ("Special programs", "Programas especiales"), ("Part 2, Item 3.f. Select only one.", "Parte 2, Ítem 3.f. Selecciona solo una."), group="adjustment", ctx="applicant")
    choice(b, "b_cat_prog", ("Which one applies?", "¿Cuál aplica?"), "Part 2, Item 3.f", [
        ("prog_caa", "The Cuban Adjustment Act", "La Ley de Ajuste Cubano"),
        ("prog_caa_vawa", "A Victim of Battery or Extreme Cruelty as a Spouse or Child Under the Cuban Adjustment Act", "Víctima de maltrato o crueldad extrema como cónyuge o hijo(a) bajo la Ley de Ajuste Cubano"),
        ("prog_hrifa", "Applicant Adjusting Based on Dependent Status Under the Haitian Refugee Immigrant Fairness Act", "Solicitante que ajusta con base en el estatus de dependiente bajo la Ley de Equidad para Inmigrantes Refugiados Haitianos"),
        ("prog_hrifa_vawa", "A Victim of Battery or Extreme Cruelty as a Spouse or Child Applying Based on Dependent Status Under the Haitian Refugee Immigrant Fairness Act", "Víctima de maltrato o crueldad extrema como cónyuge o hijo(a) que solicita con base en el estatus de dependiente bajo la Ley de Equidad para Inmigrantes Refugiados Haitianos"),
        ("prog_lautenberg", "Lautenberg Parolees", "Parolados Lautenberg"),
        ("prog_diplomat", "Diplomats or High-Ranking Officials Unable to Return Home (Section 13 of the Act of September 11, 1957)", "Diplomáticos o funcionarios de alto rango que no pueden regresar a su país (Sección 13 de la Ley del 11 de septiembre de 1957)"),
        ("prog_vietnam", "Nationals of Vietnam, Cambodia, and Laos Applying for Adjustment of Status Under section 586 of Public Law 106-429", "Nacionales de Vietnam, Camboya y Laos que solicitan el ajuste de estatus bajo la sección 586 de la Ley Pública 106-429"),
        ("prog_amerasian", "Applicant Adjusting Under the Amerasian Act (October 22, 1982), Form I-360", "Solicitante que ajusta bajo la Ley Amerasiática (22 de octubre de 1982), Formulario I-360")])
    only_page("p2_cat_programs", "special_programs")

    page(b, "p2_cat_additional", ("Additional options", "Opciones adicionales"), ("Part 2, Item 3.g. Select only one.", "Parte 2, Ítem 3.g. Selecciona solo una."), group="adjustment", ctx="applicant")
    choice(b, "b_cat_add", ("Which one applies?", "¿Cuál aplica?"), "Part 2, Item 3.g", [
        ("add_dv", "Diversity Visa program", "Programa de Visa de Diversidad"),
        ("add_registry", "Continuous Residence in the United States Since Before January 1, 1972 (“Registry”)", "Residencia continua en los Estados Unidos desde antes del 1 de enero de 1972 (“Registro”)"),
        ("add_foreign_govt", "Individual Born to a Foreign Government Employee in the United States", "Persona nacida en los Estados Unidos de un empleado de un gobierno extranjero"),
        ("add_s_nonimmigrant", "S Nonimmigrants and Qualifying Family Members (can only adjust in this category with an approved Form I-854B filed by a law enforcement officer)", "No inmigrantes S y familiares calificados (solo pueden ajustar en esta categoría con un Formulario I-854B aprobado presentado por un oficial de la ley)"),
        ("add_other", "Other Eligibility", "Otra elegibilidad")])
    b.field("b_dv_rank", "short_answer", ("Diversity Visa Rank Number", "Número de rango de la Visa de Diversidad"), ref="Part 2, Item 3.g (Diversity Visa Rank Number)", req=True, maxlen=20)
    only_if(b, "b_dv_rank", ("b_cat_add", "equals", "add_dv"))
    b.field("b_other_explain", "long_answer", ("Tell us what the other eligibility is", "Cuéntanos cuál es la otra elegibilidad"), ref="Part 14 (explanation for Part 2, Item 3.g Other Eligibility)", maxlen=600,
            help=("Optional. OG will confirm it with you.", "Opcional. OG lo confirmará contigo."))
    only_if(b, "b_other_explain", ("b_cat_add", "equals", "add_other"))
    only_page("p2_cat_additional", "additional")

    page(b, "p2_245i_cspa", ("Two more questions about your category", "Dos preguntas más sobre tu categoría"), group="adjustment", ctx="applicant")
    choice(b, "b_245i", ("If you selected a family-based, employment-based, special immigrant, or Diversity Visa immigrant category, are you applying for adjustment based on INA section 245(i)?",
                         "Si seleccionaste una categoría basada en la familia, el empleo, inmigrante especial o Visa de Diversidad, ¿estás solicitando el ajuste con base en la sección 245(i) de la INA?"),
           "Part 2, Item 4", YN_UNSURE, help=("If you are not sure, choose “Not sure”. OG will look at it with you.", "Si no estás seguro(a), elige “No estoy seguro(a)”. OG lo revisará contigo."))
    any_of(b, "b_245i", [("b_cat_group", "equals", "family")], [("b_cat_group", "equals", "employment")], [("b_cat_group", "equals", "special_immigrant")], [("b_cat_add", "equals", "add_dv")], [("b_cat_group", "equals", "unsure")])
    choice(b, "b_cspa", ("Are you 21 years of age or older and applying for adjustment based on classification as a child, under the provisions of the Child Status Protection Act (CSPA)?",
                         "¿Tienes 21 años o más y solicitas el ajuste con base en la clasificación como hijo(a), bajo las disposiciones de la Ley de Protección del Estatus del Niño (CSPA)?"),
           "Part 2, Item 5", YN_UNSURE, help=("For more information on whether you qualify under CSPA, see the “Who May File Form I-485” section of the USCIS Instructions. OG can help you review it.", "Para más información sobre si calificas bajo la CSPA, consulta la sección “Who May File Form I-485” de las Instrucciones de USCIS. OG puede ayudarte a revisarlo."))

    page(b, "p3_exempt", ("Affidavit of Support exemption", "Exención de la Declaración Jurada de Patrocinio"),
         ("Part 3 asks whether you are requesting an exemption from submitting an Affidavit of Support (Form I-864 or I-864EZ). Select only one. OG does not decide this — if you are not sure, say so.",
          "La Parte 3 pregunta si solicitas una exención de presentar una Declaración Jurada de Patrocinio (Formulario I-864 o I-864EZ). Selecciona solo una. OG no lo decide: si no estás seguro(a), dilo."),
         group="adjustment", ctx="applicant")
    choice(b, "b_i864_exempt", ("I am requesting an exemption from submitting an Affidavit of Support Under Section 213A of the INA because (select only one):", "Solicito una exención de presentar una Declaración Jurada de Patrocinio bajo la sección 213A de la INA porque (selecciona solo una):"), "Part 3, Items 1.a–1.f", [
        ("q40", "I have earned or can receive credit for 40 qualifying quarters (credits) of work in the United States (as defined by the Social Security Act). (Attach your SSA earnings statements. Do not count any quarters during which you received a means-tested public benefit.)", "He ganado o puedo recibir crédito por 40 trimestres calificados (créditos) de trabajo en los Estados Unidos (según la Ley del Seguro Social). (Adjunta tus estados de ganancias de la SSA. No cuentes ningún trimestre en el que recibiste un beneficio público sujeto a verificación de recursos.)"),
        ("child_320", "I am under 18 years of age, unmarried, the child of a U.S. citizen, am not likely to become a public charge, and will automatically become a U.S. citizen under INA section 320, upon my admission as a lawful permanent resident.", "Soy menor de 18 años, soltero(a), hijo(a) de un ciudadano de EE. UU., no es probable que me convierta en carga pública y me convertiré automáticamente en ciudadano de EE. UU. bajo la sección 320 de la INA, al ser admitido como residente permanente legal."),
        ("widow", "I am applying under the widow or widower of a U.S. citizen (Form I-360) immigrant category.", "Estoy solicitando bajo la categoría de inmigrante de viudo(a) de un ciudadano de EE. UU. (Formulario I-360)."),
        ("vawa", "I am applying as a VAWA self-petitioner.", "Estoy solicitando como autopeticionario VAWA."),
        ("none_not_required", "None of these exemptions apply to me and I am not required by statute to submit an Affidavit of Support Under Section 213A of the INA, nor am I required to request an exemption.", "Ninguna de estas exenciones me aplica y la ley no me exige presentar una Declaración Jurada de Patrocinio bajo la sección 213A de la INA, ni me exige solicitar una exención."),
        ("none_required", "None of these exemptions apply to me and I am not requesting an exemption as I am required to submit an Affidavit of Support Under Section 213A of the INA.", "Ninguna de estas exenciones me aplica y no solicito una exención porque debo presentar una Declaración Jurada de Patrocinio bajo la sección 213A de la INA."),
        UNSURE])
    note(b, "p3_i864_note", "OG does not prepare Form I-864 in this application. This answer only records what the form asks.", "OG no prepara el Formulario I-864 en esta solicitud. Esta respuesta solo registra lo que pide el formulario.")

    # ================================================================== IMMIGRATION & ARRIVAL — Part 1 items 10-17
    page(b, "arr_passport", ("Passport or travel document used at your last arrival", "Pasaporte o documento de viaje usado en tu última llegada"),
         ("If you last entered the United States using a passport or travel document, give these details. If you did not use one, skip them.", "Si la última vez entraste a los Estados Unidos con un pasaporte o documento de viaje, indica estos datos. Si no usaste uno, sáltalos."),
         group="arrival", ctx="applicant")
    b.field("a_pp_number", "short_answer", ("Passport or travel document number used at last arrival", "Número del pasaporte o documento de viaje usado en la última llegada"), ref="Part 1, Item 10", maxlen=20, sensitive=True)
    where(b, "a_pp_number", *WHERE_PASSPORT)
    b.field("a_pp_expiry", "date", ("Expiration date of this passport or travel document", "Fecha de vencimiento de este pasaporte o documento de viaje"), ref="Part 1, Item 10", width="half")
    b.field("a_pp_country", "short_answer", ("Country that issued this passport or travel document", "País que emitió este pasaporte o documento de viaje"), ref="Part 1, Item 10", width="half", maxlen=60)
    b.field("a_visa_number", "short_answer", ("Nonimmigrant visa number used during most recent arrival (if any)", "Número de la visa de no inmigrante usada en la llegada más reciente (si aplica)"), ref="Part 1, Item 10", maxlen=20, width="half")
    where(b, "a_visa_number", *WHERE_VISA)
    b.field("a_visa_issued", "date", ("Date the nonimmigrant visa was issued", "Fecha de emisión de la visa de no inmigrante"), ref="Part 1, Item 10", width="half")

    def edit_arrival():
        b.field("a_arr_city", "short_answer", ("City or town of your last arrival into the United States", "Ciudad o pueblo de tu última llegada a los Estados Unidos"), ref="Part 1, Item 10 (Place of Last Arrival)", width="half", maxlen=60)
        b.field("a_arr_state", "dropdown", ("State", "Estado"), ref="Part 1, Item 10 (Place of Last Arrival)", opts=STATE_OPTIONS, width="half")
        b.field("a_arr_date", "date", ("Date of last arrival into the United States", "Fecha de la última llegada a los Estados Unidos"), ref="Part 1, Item 10 (Date of Last Arrival)", req=True, date_rule="past", width="half")
        mark_block_fields(b, "sb_arrival", ["a_arr_date"])
    block_pair(b, "sb_arrival", group="arrival",
               review_title=("We already have {app}'s date of last arrival", "Ya tenemos la fecha de la última llegada de {app}"),
               review_desc=("Confirm it or change it. You will still add the place of arrival.", "Confírmala o cámbiala. Aún agregarás el lugar de llegada."),
               edit_title=("Place and date of your last arrival", "Lugar y fecha de tu última llegada"),
               edit_desc=("Where and when you last came into the United States.", "Dónde y cuándo entraste por última vez a los Estados Unidos."), build_edit=edit_arrival)

    page(b, "arr_how", ("How you last arrived", "Cómo llegaste la última vez"), group="arrival", ctx="applicant")
    choice(b, "a_arr_how", ("When I last arrived in the United States:", "Cuando llegué por última vez a los Estados Unidos:"), "Part 1, Item 11", [
        ("admitted", "I was inspected at a Port of Entry and admitted", "Fui inspeccionado(a) en un puerto de entrada y admitido(a)"),
        ("paroled", "I was inspected at a Port of Entry and paroled", "Fui inspeccionado(a) en un puerto de entrada y se me otorgó parole"),
        ("no_inspection", "I came into the United States without admission or parole", "Entré a los Estados Unidos sin admisión ni parole"),
        ("other", "Other", "Otro")], help=("Select only one. The I-94 record often shows how you were admitted.", "Selecciona solo una. El registro I-94 suele mostrar cómo fuiste admitido(a)."))
    b.field("a_arr_admitted_as", "short_answer", ("Admitted as (for example, exchange visitor, visitor, temporary worker, student)", "Admitido(a) como (por ejemplo, visitante de intercambio, visitante, trabajador temporal, estudiante)"), ref="Part 1, Item 11 (admitted as)", req=True, maxlen=80)
    only_if(b, "a_arr_admitted_as", ("a_arr_how", "equals", "admitted"))
    b.field("a_arr_paroled_as", "short_answer", ("Paroled as (for example, humanitarian parole, Cuban parole)", "Parole otorgado como (por ejemplo, parole humanitario, parole cubano)"), ref="Part 1, Item 11 (paroled as)", req=True, maxlen=80)
    only_if(b, "a_arr_paroled_as", ("a_arr_how", "equals", "paroled"))
    b.field("a_arr_other", "short_answer", ("Other (explain)", "Otro (explica)"), ref="Part 1, Item 11 (Other)", req=True, maxlen=120)
    only_if(b, "a_arr_other", ("a_arr_how", "equals", "other"))

    page(b, "arr_i94_gate", ("Form I-94 record", "Registro Formulario I-94"), ("The form asks for your most recent I-94 if you were issued one.", "El formulario pide tu I-94 más reciente si se te emitió uno."), group="arrival", ctx="applicant")
    choice(b, "a_i94_issued", ("Were you issued a Form I-94 Arrival/Departure Record?", "¿Se te emitió un Registro de Llegada/Salida Formulario I-94?"), "Part 1, Item 12 (OG helper)",
           [("yes", "Yes", "Sí"), ("no", "No", "No"), ("unsure", "I don't know", "No sé")], note_="Chooses whether the I-94 details are asked. “I don't know”: OG will help find it.")
    kp(b, "a_i94_issued", block="sb_i94")
    show_page_any(b, "arr_i94_gate", [[("sb_i94_avail", "equals", "no")]])

    def edit_i94():
        b.field("a_i94_family", "short_answer", ("Family name (last name) as shown on the I-94", "Apellido como aparece en el I-94"), ref="Part 1, Item 12 (Family Name)", req=True, width="half", maxlen=60)
        b.field("a_i94_given", "short_answer", ("Given name (first name) as shown on the I-94", "Nombre como aparece en el I-94"), ref="Part 1, Item 12 (Given Name)", req=True, width="half", maxlen=60)
        b.field("a_i94_number", "short_answer", ("Form I-94 Arrival/Departure Record number", "Número del Registro de Llegada/Salida (Formulario I-94)"), ref="Part 1, Item 12 (I-94 Number)", req=True, maxlen=11, pattern=r"[A-Za-z0-9]{1,11}",
                msg=("Use letters and digits only (up to 11).", "Usa solo letras y dígitos (hasta 11)."))
        where(b, "a_i94_number", *WHERE_I94)
        b.field("a_i94_stay_type", "single_choice", ("Expiration of the authorized stay shown on the I-94", "Vencimiento de la estadía autorizada que aparece en el I-94"), ref="Part 1, Item 12 (Expiration Date of Authorized Stay)", req=True,
                opts=[("date", "A specific date", "Una fecha específica"), ("ds", "“D/S” — Duration of Status", "“D/S” — Duración del estatus")])
        b.field("a_i94_stay_date", "date", ("Authorized stay expiration date", "Fecha de vencimiento de la estadía autorizada"), ref="Part 1, Item 12 (Expiration Date of Authorized Stay)", req=True, width="half")
        only_if(b, "a_i94_stay_date", ("a_i94_stay_type", "equals", "date"))
        b.field("a_i94_status", "short_answer", ("Immigration status on the I-94 (for example, class of admission, or paroled)", "Estatus migratorio en el I-94 (por ejemplo, clase de admisión, o paroled)"), ref="Part 1, Item 12 (Immigration Status)", req=True, maxlen=40)
        where(b, "a_i94_status", *WHERE_CLASS)
        mark_block_fields(b, "sb_i94", ["a_i94_number", "a_i94_stay_type", "a_i94_stay_date", "a_i94_status"])
    block_pair(b, "sb_i94", group="arrival", edit_extra_no=[("a_i94_issued", "equals", "yes")], needed=["a_i94_family", "a_i94_given", "a_i94_status", "a_i94_stay_type"],
               review_title=("We already have {app}'s Form I-94 information", "Ya tenemos la información del Formulario I-94 de {app}"),
               review_desc=("Confirm it or change it.", "Confírmala o cámbiala."),
               edit_title=("Your most recent Form I-94", "Tu Formulario I-94 más reciente"), edit_desc=None, build_edit=edit_i94)

    page(b, "arr_status", ("Your current immigration status", "Tu estatus migratorio actual"), group="arrival", ctx="applicant")
    b.field("a_first_time", "single_choice", ("Was your last arrival the first time you were physically present in the United States?", "¿Tu última llegada fue la primera vez que estuviste físicamente en los Estados Unidos?"), ref="Part 1, Item 13", req=True, opts=YES_NO)
    b.field("a_current_status", "short_answer", ("What is your current immigration status (if it has changed since your last arrival)?", "¿Cuál es tu estatus migratorio actual (si ha cambiado desde tu última llegada)?"), ref="Part 1, Item 14", maxlen=60,
            help=("Leave blank if it has not changed.", "Déjalo en blanco si no ha cambiado."))
    b.field("a_current_stay_type", "single_choice", ("Expiration of your current immigration status", "Vencimiento de tu estatus migratorio actual"), ref="Part 1, Item 15",
            opts=[("date", "A specific date", "Una fecha específica"), ("ds", "“D/S” — Duration of Status", "“D/S” — Duración del estatus")])
    b.field("a_current_stay_date", "date", ("Expiration date of your current immigration status", "Fecha de vencimiento de tu estatus migratorio actual"), ref="Part 1, Item 15", req=True, width="half")
    only_if(b, "a_current_stay_date", ("a_current_stay_type", "equals", "date"))
    only_if(b, "a_current_stay_type", ("a_current_status", "is_not_empty", ""))

    page(b, "arr_crew", ("Crewman visa and vessel arrival", "Visa de tripulante y llegada en una embarcación"), group="arrival", ctx="applicant")
    b.field("a_crewman_visa", "single_choice", ("Have you ever been issued an “alien crewman” visa?", "¿Se te ha emitido alguna vez una visa de “tripulante extranjero”?"), ref="Part 1, Item 16", req=True, opts=YES_NO)
    b.field("a_crewman_arrival", "single_choice", ("Did you last arrive in the United States to join a vessel as a seaman or crewman, or while serving in any capacity aboard a vessel or aircraft?", "¿Llegaste por última vez a los Estados Unidos para unirte a una embarcación como marinero o tripulante, o mientras servías en cualquier capacidad a bordo de una embarcación o aeronave?"), ref="Part 1, Item 17", req=True, opts=YES_NO)

    # ================================================================== ADDRESS HISTORY — Part 1 item 18
    def edit_address():
        b.field("cur_in_care_of", "short_answer", ("In care of name (if any)", "A cargo de (si aplica)"), ref="Part 1, Item 18 (Current U.S. Physical Address — In Care Of Name)", maxlen=34)
        b.field("cur_street", "short_answer", ("Street number and name", "Número y nombre de la calle"), ref="Part 1, Item 18 (Current U.S. Physical Address)", req=True, maxlen=60)
        b.field("cur_unit_type", "dropdown", ("Unit type (if any)", "Tipo de unidad (si aplica)"), ref="Part 1, Item 18 (Apt./Ste./Flr.)", opts=UNIT_TYPES, width="half")
        b.field("cur_unit_number", "short_answer", ("Unit number", "Número de unidad"), ref="Part 1, Item 18 (Number)", width="half", maxlen=10)
        b.field("cur_city", "short_answer", ("City or town", "Ciudad o pueblo"), ref="Part 1, Item 18 (City or Town)", req=True, maxlen=60)
        b.field("cur_state", "dropdown", ("State", "Estado"), ref="Part 1, Item 18 (State)", req=True, opts=STATE_OPTIONS, width="half")
        b.field("cur_zip", "short_answer", ("ZIP code", "Código postal (ZIP)"), ref="Part 1, Item 18 (ZIP Code)", req=True, width="half", pattern=r"\d{5}", maxlen=5, msg=("Enter a 5-digit ZIP code.", "Ingresa un ZIP de 5 dígitos."))
        mark_block_fields(b, "sb_address", ["cur_street", "cur_unit_type", "cur_unit_number", "cur_city", "cur_state", "cur_zip"])
    block_pair(b, "sb_address", group="addresses", needed=["cur_street", "cur_city", "cur_state", "cur_zip"],
               review_title=("We already have {app}'s current U.S. address", "Ya tenemos la dirección actual de {app} en EE. UU."),
               review_desc=("Confirm it or change it.", "Confírmala o cámbiala."),
               edit_title=("Current U.S. physical address", "Dirección física actual en EE. UU."),
               edit_desc=("Where you live now. This is your physical address, not a P.O. box.", "Donde vives ahora. Es tu dirección física, no un apartado postal."), build_edit=edit_address)

    page(b, "addr_mailing", ("Your mailing address", "Tu dirección postal"), group="addresses", ctx="applicant")
    b.field("a_mail_same", "single_choice", ("Is this your current mailing address?", "¿Esta es tu dirección postal actual?"), ref="Part 1, Item 18 (Is this your current mailing address?)", req=True, opts=YES_NO,
            help=("If you use a safe or alternate mailing address, choose No and enter it next.", "Si usas una dirección postal segura o alternativa, elige No e ingrésala a continuación."))
    page(b, "addr_mailing_details", ("Your current mailing address", "Tu dirección postal actual"), ("Safe or alternate mailing address, if applicable.", "Dirección postal segura o alternativa, si aplica."), group="addresses", ctx="applicant")
    b.field("a_mail_in_care_of", "short_answer", ("In care of name (if any)", "A cargo de (si aplica)"), ref="Part 1, Item 18 (Current Mailing Address — In Care Of Name)", maxlen=34)
    _address_fields(b, "a_mail", "Part 1, Item 18 (Current Mailing Address)")
    show_page_any(b, "addr_mailing_details", [[("a_mail_same", "equals", "no")]])

    def edit_history():
        records(b, "a_address_history", ("Where you have lived for the last five years", "Dónde has vivido durante los últimos cinco años"), "Part 1, Item 18 (Prior Address; Dates of Residence)", "address", req=True, max=20,
                timeline={"years": 5, "gap_days": 3, "overlap_days": 31},
                default_from={"prefix": "cur", "present": True},
                intro={"en": "We started with your current address — just add the date you began living there (the form calls it “Date You First Resided at This Address”).",
                       "es": "Empezamos con tu dirección actual: solo agrega la fecha en que empezaste a vivir ahí (el formulario la llama “Date You First Resided at This Address”)."})
        b.fields["a_address_history"].source_note = ("Current address = Item 18 Current U.S. Physical Address + its 'Date You First Resided' (kept identical to that answer). The form has one Prior Address block "
                                                      "with a five-year question; further addresses go in Part 14 (OG places them). Addresses outside the U.S. are allowed.")
        mark_block_fields(b, "sb_addr_history", ["a_address_history"])
    block_pair(b, "sb_addr_history", group="addresses",
               review_title=("We already have {app}'s address history", "Ya tenemos el historial de direcciones de {app}"),
               review_desc=("Confirm it or change it. The form covers the last five years.", "Confírmalo o cámbialo. El formulario cubre los últimos cinco años."),
               edit_title=("Where {app} has lived", "Dónde ha vivido {app}"),
               edit_desc=("Start with where you live now, then add each previous address until the last five years are covered — inside or outside the United States.", "Empieza con donde vives ahora y agrega cada dirección anterior hasta cubrir los últimos cinco años, dentro o fuera de los Estados Unidos."),
               build_edit=edit_history)

    page(b, "addr_foreign_q", ("Your last address outside the U.S.", "Tu última dirección fuera de EE. UU."), group="addresses", ctx="applicant")
    b.field("a_foreign_addr_intro", "paragraph", ("", ""), content=(
        "The form also asks for your most recent physical address outside the United States where you lived for more than one year — if it is not already listed above.",
        "El formulario también pide tu dirección física más reciente fuera de los Estados Unidos donde viviste por más de un año, si no está ya en el historial de arriba."))
    b.field("a_foreign_addr_found", "paragraph", ("", ""), content=("", ""))
    b.fields["a_foreign_addr_found"].config_json = json.dumps({"dynamic": {
        "candidate": "last_foreign_address", "source": "a_address_history", "record": "address", "who": "app",
        "none": {"en": "We did not find an address outside the U.S. of more than one year in {app}'s history.", "es": "No encontramos en el historial de {app} una dirección fuera de EE. UU. de más de un año."}}})
    choice(b, "a_foreign_addr_status", ("Did you live at an address outside the United States for more than one year?", "¿Viviste en una dirección fuera de los Estados Unidos por más de un año?"), "Part 1, Item 18 (Most Recent Address Outside the United States) — OG helper", [
        ("yes_history", "Yes — it is already listed in my history above", "Sí — ya está en mi historial de arriba"),
        ("different", "Yes — at a different address (for example, an older one)", "Sí — en otra dirección (por ejemplo, una más antigua)"),
        ("never", "No — I have not lived outside the U.S. for more than one year", "No — no he vivido fuera de EE. UU. por más de un año")],
        note_="The form only wants this address if it is not already listed above; 'listed above' leaves the block blank.")
    page(b, "addr_foreign", ("The address where you lived outside the U.S.", "La dirección donde viviste fuera de EE. UU."), ("Enter the address and the dates.", "Ingresa la dirección y las fechas."), group="addresses", ctx="applicant")
    records(b, "a_foreign_addr", ("Most recent address outside the United States (more than one year)", "Dirección más reciente fuera de los Estados Unidos (más de un año)"),
            "Part 1, Item 18 (Most Recent Address Outside the United States)", "foreign_address", req=True, max=1)
    show_page_any(b, "addr_foreign", [[("a_foreign_addr_status", "equals", "different")]])

    # ================================================================== FAMILY — Parts 5, 6, 7
    def edit_parents():
        records(b, "a_parents", ("Your parents", "Tus padres"), "Part 5, Items 1–8", "i485_parent", max=2,
                help=("Add each parent, one at a time. Leave blank anything you do not know.", "Agrega a cada padre o madre, uno por uno. Deja en blanco lo que no sepas."))
        mark_block_fields(b, "sb_parents", ["a_parents"])
    block_pair(b, "sb_parents", group="family",
               review_title=("We already have information about {app}'s parents", "Ya tenemos información sobre los padres de {app}"),
               review_desc=("Confirm it or change it.", "Confírmala o cámbiala."),
               edit_title=("About {app}'s parents", "Sobre los padres de {app}"),
               edit_desc=("The form asks for the legal name, name at birth (if different), date of birth and country of birth of both parents.", "El formulario pide el nombre legal, el nombre de nacimiento (si es diferente), la fecha de nacimiento y el país de nacimiento de ambos padres."),
               build_edit=edit_parents)

    page(b, "m_status_page", ("Your marital status", "Tu estado civil"), group="family", ctx="applicant")
    choice(b, "m_status", ("What is your current marital status?", "¿Cuál es tu estado civil actual?"), "Part 6, Item 1", [
        ("single", "Single, Never Married", "Soltero(a), nunca casado(a)"), ("married", "Married", "Casado(a)"), ("divorced", "Divorced", "Divorciado(a)"),
        ("widowed", "Widowed", "Viudo(a)"), ("annulled", "Marriage Annulled", "Matrimonio anulado"), ("separated", "Legally Separated", "Legalmente separado(a)")])
    choice(b, "m_military", ("If you are married, is your spouse a current member of the U.S. armed forces or U.S. Coast Guard?", "Si estás casado(a), ¿tu cónyuge es actualmente miembro de las fuerzas armadas o de la Guardia Costera de EE. UU.?"), "Part 6, Item 2",
           [("na", "N/A", "No aplica"), ("yes", "Yes", "Sí"), ("no", "No", "No")])
    any_of(b, "m_military", [("m_status", "equals", "married")], [("m_status", "equals", "separated")])
    b.field("m_times", "number", ("How many times have you been married (including your current marriage, marriages abroad, annulled marriages, and marriages to the same person)?", "¿Cuántas veces te has casado (incluido tu matrimonio actual, matrimonios en el extranjero, matrimonios anulados y matrimonios con la misma persona)?"), ref="Part 6, Item 3", req=True, minv=0, maxv=20)
    any_of(b, "m_times", *[[("m_status", "equals", v)] for v in ("married", "divorced", "widowed", "annulled", "separated")])

    def edit_spouse():
        b.field("s_family", "short_answer", ("Current spouse's family name (last name)", "Apellido de tu cónyuge actual"), ref="Part 6, Item 4", req=True, width="half", maxlen=60)
        b.field("s_given", "short_answer", ("Current spouse's given name (first name)", "Nombre de tu cónyuge actual"), ref="Part 6, Item 4", req=True, width="half", maxlen=60)
        b.field("s_middle", "short_answer", ("Middle name (if applicable)", "Segundo nombre (si aplica)"), ref="Part 6, Item 4", width="half", maxlen=60)
        b.field("s_anumber", "short_answer", ("Current spouse's A-Number (if any)", "Número A de tu cónyuge actual (si tiene)"), ref="Part 6, Item 5", sensitive=True, pattern=r"A?-?\d{7,9}", maxlen=12, width="half",
                msg=("Enter 7 to 9 digits, with or without “A-”.", "Ingresa 7 a 9 dígitos, con o sin “A-”."))
        b.field("s_dob", "date", ("Current spouse's date of birth", "Fecha de nacimiento de tu cónyuge actual"), ref="Part 6, Item 6", req=True, date_rule="past", width="half")
        b.field("s_birth_country", "short_answer", ("Current spouse's country of birth", "País de nacimiento de tu cónyuge actual"), ref="Part 6, Item 7", req=True, maxlen=60, width="half")
        mark_block_fields(b, "sb_spouse", ["s_family", "s_given", "s_middle", "s_anumber", "s_dob", "s_birth_country"])
    block_pair(b, "sb_spouse", group="family", needed=["s_birth_country", "s_dob"], gates=[[("m_status", "equals", "married")], [("m_status", "equals", "separated")]],
               review_title=("We already have information about {app}'s spouse", "Ya tenemos información sobre el cónyuge de {app}"),
               review_desc=("This person is already in your case. Confirm the information or change it.", "Esta persona ya está en tu caso. Confirma la información o cámbiala."),
               edit_title=("Your current spouse", "Tu cónyuge actual"),
               edit_desc=("Information about your current marriage (including if you are legally separated).", "Información sobre tu matrimonio actual (incluso si estás legalmente separado(a))."), build_edit=edit_spouse)
    # -- the spouse's address, marriage and whether the spouse applies too (Part 6 items 8-10)
    married_or_sep = [[("m_status", "equals", "married")], [("m_status", "equals", "separated")]]
    page(b, "s_address_gate", ("Where your spouse lives", "Dónde vive tu cónyuge"), group="family", ctx="applicant")
    b.field("s_same_address", "single_choice", ("Does your current spouse live at the same address as you?", "¿Tu cónyuge actual vive en la misma dirección que tú?"), ref="Part 6, Item 8 (OG helper)", req=True, opts=YES_NO,
            note="Chooses whether the spouse's physical address is asked separately; 'same' means Item 8 repeats the applicant's current U.S. physical address.")
    show_page_any(b, "s_address_gate", married_or_sep)
    page(b, "s_address_details", ("Your spouse's current physical address", "La dirección física actual de tu cónyuge"), group="family", ctx="applicant")
    _address_fields(b, "s_addr", "Part 6, Item 8")
    show_page_any(b, "s_address_details", [[("s_same_address", "equals", "no"), ("m_status", "equals", "married")], [("s_same_address", "equals", "no"), ("m_status", "equals", "separated")]])
    page(b, "s_marriage", ("Your current marriage", "Tu matrimonio actual"), group="family", ctx="applicant")
    b.field("s_marr_city", "short_answer", ("City or town where you married", "Ciudad o pueblo donde se casaron"), ref="Part 6, Item 9 (Place of Marriage — City or Town)", req=True, maxlen=60, width="half")
    b.field("s_marr_state", "short_answer", ("State or province", "Estado o provincia"), ref="Part 6, Item 9 (Place of Marriage — State or Province)", maxlen=60, width="half")
    b.field("s_marr_country", "short_answer", ("Country", "País"), ref="Part 6, Item 9 (Place of Marriage — Country)", req=True, maxlen=60)
    b.field("s_marr_date", "date", ("Date of marriage to current spouse", "Fecha del matrimonio con tu cónyuge actual"), ref="Part 6, Item 9 (Date of Marriage)", req=True, date_rule="past", width="half")
    b.field("s_applying", "single_choice", ("Is your current spouse applying with you?", "¿Tu cónyuge actual está solicitando junto contigo?"), ref="Part 6, Item 10", req=True, opts=YES_NO)
    show_page_any(b, "s_marriage", married_or_sep)

    page(b, "m_prior_page", ("Your prior marriages", "Tus matrimonios anteriores"),
         ("The form asks about each prior spouse: name, date of birth, country of birth and citizenship, when and where you married, and how and where the marriage ended. Add each prior marriage.",
          "El formulario pregunta por cada cónyuge anterior: nombre, fecha de nacimiento, país de nacimiento y ciudadanía, cuándo y dónde se casaron, y cómo y dónde terminó el matrimonio. Agrega cada matrimonio anterior."),
         group="family", ctx="applicant")
    records(b, "m_prior", ("Prior marriages", "Matrimonios anteriores"), "Part 6, Items 11–18", "i485_prior_marriage", req=True, max=8)
    b.fields["m_prior"].source_note = "The form has one prior-marriage block; further prior marriages go in Part 14 (OG places them)."
    show_page_any(b, "m_prior_page", [[("m_status", "equals", "divorced")], [("m_status", "equals", "widowed")], [("m_status", "equals", "annulled")], [("m_times", "greater_than", "1")]])

    page(b, "ch_page", ("Your children", "Tus hijos"), group="family", ctx="applicant")
    b.field("ch_count", "number", ("Indicate the total number of ALL living children anywhere in the world (including adult sons and daughters) that you have.", "Indica el número total de TODOS tus hijos vivos en cualquier parte del mundo (incluidos hijos e hijas adultos)."), ref="Part 7, Item 1", req=True, minv=0, maxv=30,
            help=("“Children” includes all biological or legally adopted children, as well as current stepchildren, of any age, born in the United States or other countries, married or unmarried, living with you or elsewhere, including missing children and those born to you outside of marriage.",
                  "“Hijos” incluye a todos los hijos biológicos o legalmente adoptados, así como a los hijastros actuales, de cualquier edad, nacidos en los Estados Unidos o en otros países, casados o solteros, que vivan contigo o en otro lugar, incluidos los hijos desaparecidos y los nacidos fuera del matrimonio."))
    page(b, "ch_list", ("About your children", "Sobre tus hijos"), ("Add each child, one at a time. The form has room for two; OG places any others in Part 14.", "Agrega a cada hijo(a), uno por uno. El formulario tiene espacio para dos; OG coloca los demás en la Parte 14."), group="family", ctx="applicant")
    records(b, "a_children", ("Your children", "Tus hijos"), "Part 7, Items 2–3", "i485_child", req=True, max=15)
    show_page_any(b, "ch_list", [[("ch_count", "greater_than", "0")]])

    # ================================================================== EMPLOYMENT & EDUCATION — Part 4 items 7-8
    def edit_emp():
        records(b, "a_employment_history", ("Employment, self-employment, school, unemployment or retirement — last five years", "Empleo, trabajo por cuenta propia, escuela, desempleo o jubilación — últimos cinco años"), "Part 4, Item 7", "i485_activity", req=True, max=15,
                timeline={"years": 5, "gap_days": 3, "overlap_days": 31},
                help=("Start with what you do now (current employment or school), then go back five years. For each period of unemployment or retirement, add the source of financial support.",
                      "Empieza con lo que haces ahora (empleo o escuela actual) y ve hacia atrás cinco años. En cada período de desempleo o jubilación, agrega la fuente de sustento económico."))
        b.fields["a_employment_history"].source_note = ("The form has one employer/school block for the current or most recent one; further periods go in Part 14 (OG places them). "
                                                          "Only activity types the form names are offered: employment, self-employment, school, unemployment, retirement.")
        mark_block_fields(b, "sb_employment", ["a_employment_history"])
    block_pair(b, "sb_employment", group="employment",
               review_title=("We already have {app}'s employment history", "Ya tenemos el historial de empleo de {app}"),
               review_desc=("Confirm it or change it. The form covers the last five years, including school.", "Confírmalo o cámbialo. El formulario cubre los últimos cinco años, incluidos los estudios."),
               edit_title=("Where {app} has worked or studied", "Dónde ha trabajado o estudiado {app}"),
               edit_desc=("Provide ALL of your employment and educational history for the last 5 years. Include periods of self-employment, unemployment, or retirement.", "Indica TODO tu historial de empleo y educación de los últimos 5 años. Incluye períodos de trabajo por cuenta propia, desempleo o jubilación."),
               build_edit=edit_emp)

    page(b, "emp_foreign_q", ("Your last employer or school outside the U.S.", "Tu último empleador o escuela fuera de EE. UU."), group="employment", ctx="applicant")
    b.field("a_foreign_activity_intro", "paragraph", ("", ""), content=(
        "The form also asks for your most recent employer or school outside the United States — if it is not already listed above.",
        "El formulario también pide tu empleador o escuela más reciente fuera de los Estados Unidos, si no está ya en el historial de arriba."))
    b.field("a_foreign_activity_found", "paragraph", ("", ""), content=("", ""))
    b.fields["a_foreign_activity_found"].config_json = json.dumps({"dynamic": {
        "candidate": "last_foreign_activity", "source": "a_employment_history", "record": "i485_activity", "who": "app",
        "none": {"en": "We did not find an employer or school outside the U.S. in {app}'s history.", "es": "No encontramos un empleador o escuela fuera de EE. UU. en el historial de {app}."}}})
    choice(b, "a_foreign_activity_status", ("Do you have a most recent employer or school outside the United States?", "¿Tienes un empleador o escuela más reciente fuera de los Estados Unidos?"), "Part 4, Item 8 (OG helper)", [
        ("yes_history", "Yes — it is already listed in my history above", "Sí — ya está en mi historial de arriba"),
        ("different", "Yes — a different one that is not listed above", "Sí — otro que no está en mi historial de arriba"),
        ("never", "No — I have not worked or studied outside the U.S.", "No — no he trabajado ni estudiado fuera de EE. UU.")],
        note_="The form only wants Item 8 if it is not already listed in Item 7; 'listed above' leaves Item 8 blank.")
    page(b, "emp_foreign", ("Your most recent employer or school outside the U.S.", "Tu empleador o escuela más reciente fuera de EE. UU."), group="employment", ctx="applicant")
    records(b, "a_foreign_activity", ("Most recent employer or school outside the United States", "Empleador o escuela más reciente fuera de los Estados Unidos"), "Part 4, Item 8", "i485_foreign_activity", req=True, max=1)
    show_page_any(b, "emp_foreign", [[("a_foreign_activity_status", "equals", "different")]])

    # ================================================================== IMMIGRATION HISTORY — Part 4 items 1-6
    page(b, "h_visa", ("Immigrant visa abroad", "Visa de inmigrante en el extranjero"), group="history", ctx="applicant")
    b.field("h_visa_abroad", "single_choice", ("Have you ever applied for an immigrant visa to obtain permanent resident status at a U.S. Embassy or U.S. Consulate abroad?", "¿Has solicitado alguna vez una visa de inmigrante para obtener la residencia permanente en una Embajada o Consulado de EE. UU. en el extranjero?"), ref="Part 4, Item 1", req=True, opts=YN_UNSURE)
    b.field("h_visa_city", "short_answer", ("City or town of the U.S. Embassy or Consulate", "Ciudad o pueblo de la Embajada o Consulado de EE. UU."), ref="Part 4, Item 2 (City or Town)", req=True, maxlen=60, width="half")
    b.field("h_visa_country", "short_answer", ("Country", "País"), ref="Part 4, Item 2 (Country)", req=True, maxlen=60, width="half")
    b.field("h_visa_decision", "short_answer", ("Decision (for example, approved, refused, denied, withdrawn)", "Decisión (por ejemplo, aprobada, rechazada, denegada, retirada)"), ref="Part 4, Item 3", req=True, maxlen=60)
    b.field("h_visa_date", "date", ("Date of decision", "Fecha de la decisión"), ref="Part 4, Item 4", req=True, date_rule="past", width="half")
    for n in ("h_visa_city", "h_visa_country", "h_visa_decision", "h_visa_date"):
        only_if(b, n, ("h_visa_abroad", "equals", "yes"))
    page(b, "h_prev", ("Earlier applications", "Solicitudes anteriores"), group="history", ctx="applicant")
    b.field("h_prev_pr", "single_choice", ("Have you previously applied for permanent residence while in the United States?", "¿Has solicitado anteriormente la residencia permanente mientras estabas en los Estados Unidos?"), ref="Part 4, Item 5", req=True, opts=YN_UNSURE)
    b.field("h_rescinded", "single_choice", ("Have you EVER held lawful permanent resident status which was later rescinded under INA section 246?", "¿Has tenido ALGUNA VEZ el estatus de residente permanente legal que posteriormente fue rescindido bajo la sección 246 de la INA?"), ref="Part 4, Item 6", req=True, opts=YN_UNSURE)
    b.field("h_details", "long_answer", ("Anything OG should know about these answers? (optional)", "¿Algo que OG deba saber sobre estas respuestas? (opcional)"), ref="Part 14 (optional details for Part 4, Items 5–6)", maxlen=1500)
    show_any(b, "h_details", [[("h_prev_pr", "equals", "yes")], [("h_rescinded", "equals", "yes")], [("h_prev_pr", "equals", "unsure")], [("h_rescinded", "equals", "unsure")]])

    # ================================================================== ELIGIBILITY — Part 9
    from app.seed_i485_elig import build_eligibility

    build_eligibility(b)

    # ================================================================== CONTACT & INTERPRETER — Parts 10-11
    def edit_contact():
        b.field("a_phone", "phone", ("Daytime telephone number", "Teléfono de día"), ref="Part 10, Item 1", req=True, width="half")
        b.field("a_mobile", "phone", ("Mobile telephone number (if any)", "Teléfono móvil (si tienes)"), ref="Part 10, Item 2", width="half")
        b.field("a_email", "email", ("Email address (if any)", "Correo electrónico (si tienes)"), ref="Part 10, Item 3")
        b.fields["a_email"].required = False
        mark_block_fields(b, "sb_contact", ["a_phone", "a_mobile", "a_email"])
    block_pair(b, "sb_contact", group="contact",
               review_title=("We already have {app}'s contact information", "Ya tenemos la información de contacto de {app}"),
               review_desc=("Confirm it or change it.", "Confírmala o cámbiala."),
               edit_title=("Your contact information", "Tu información de contacto"), edit_desc=None, build_edit=edit_contact)
    page(b, "language", ("Language", "Idioma"), group="contact", ctx="applicant")
    choice(b, "english_or_interpreter", ("Which of these is true for you?", "¿Cuál de estas opciones es cierta para ti?"), "Part 10 (certification: read and understand, or interpreted)", [
        ("english", "I can read and understand English, and I have read and understand every question and instruction on this application and my answer to every question.", "Puedo leer y entender inglés, y he leído y entendido cada pregunta e instrucción de esta solicitud y mi respuesta a cada pregunta."),
        ("interpreter", "An interpreter read to me every question and instruction on this application and my answer to every question in a language in which I am fluent, and I understood all of this information as interpreted.", "Un intérprete me leyó cada pregunta e instrucción de esta solicitud y mi respuesta a cada pregunta en un idioma en el que soy fluido(a), y entendí toda esta información tal como fue interpretada.")])
    page(b, "interp", ("Your interpreter", "Tu intérprete"), ("Information about the interpreter (Part 11 of the form).", "Información del intérprete (Parte 11 del formulario)."), group="contact", ctx="applicant")
    b.field("int_family", "short_answer", ("Interpreter's family name (last name)", "Apellido del intérprete"), ref="Part 11, Item 1 (Family Name)", req=True, width="half")
    b.field("int_given", "short_answer", ("Interpreter's given name (first name)", "Nombre del intérprete"), ref="Part 11, Item 1 (Given Name)", req=True, width="half")
    b.field("int_org", "short_answer", ("Interpreter's business or organization name (if any)", "Empresa u organización del intérprete (si aplica)"), ref="Part 11, Item 2", maxlen=38)
    b.field("int_phone", "phone", ("Interpreter's daytime telephone number", "Teléfono de día del intérprete"), ref="Part 11, Item 3", req=True, width="half")
    b.field("int_mobile", "phone", ("Interpreter's mobile telephone number (if any)", "Teléfono móvil del intérprete (si tiene)"), ref="Part 11, Item 4", width="half")
    b.field("int_email", "email", ("Interpreter's email address (if any)", "Correo electrónico del intérprete (si tiene)"), ref="Part 11, Item 5")
    b.fields["int_email"].required = False
    b.field("int_language", "short_answer", ("Language the interpreter used", "Idioma que usó el intérprete"), ref="Part 11 (certification — language)", req=True)
    for name, value in {"int_family": "@biz:INTERPRETER_LAST_NAME", "int_given": "@biz:INTERPRETER_FIRST_NAME", "int_org": "@biz:INTERPRETER_ORG", "int_phone": "@biz:INTERPRETER_PHONE", "int_email": "@biz:INTERPRETER_EMAIL"}.items():
        b.fields[name].default_value = value
    show_page_any(b, "interp", [[("english_or_interpreter", "equals", "interpreter")]])

    page(b, "additional", ("Anything else?", "¿Algo más?"), group="contact", ctx="applicant")
    b.field("additional_information", "long_answer", ("Is there anything else you want us to know?", "¿Hay algo más que quieras que sepamos?"), ref="Part 14. Additional Information",
            help=("If it relates to a specific question, say which one. OG places the explanations you gave in Part 14 for you — you never need a page, part or item number.", "Si se relaciona con una pregunta específica, dinos cuál. OG coloca en la Parte 14 las explicaciones que diste; nunca necesitas un número de página, parte o ítem."), maxlen=3000)

    # ================================================================== DOCUMENTS (through the case vault)
    page(b, "documents", ("Documents", "Documentos"),
         ("Documents are kept once in your case, so a document you already gave OG for another application is not asked for again.", "Los documentos se guardan una sola vez en tu caso, así que un documento que ya le diste a OG para otra solicitud no se vuelve a pedir."), group="documents", ctx="applicant")
    b.field("docs_scope_note", "paragraph", ("", ""), content=(
        _label("What OG asks for", "These are OG's requests to prepare and review your case, plus the few documents the form itself says to attach. USCIS lists its required evidence in the Form I-485 Instructions; OG will confirm what applies to you."),
        _label("Lo que pide OG", "Son solicitudes de OG para preparar y revisar tu caso, más los pocos documentos que el propio formulario indica adjuntar. USCIS enumera la evidencia requerida en las Instrucciones del Formulario I-485; OG confirmará lo que aplica en tu caso.")))
    b.field("docs_list", "paragraph", ("", ""), content=("", ""))
    b.fields["docs_list"].config_json = json.dumps({"dynamic": {"kind": "documents"}})
    b.field("docs_tip", "paragraph", ("", ""), content=(
        _tip("Make sure each document is complete, readable, well lit and not cropped or blurry. Documents that are not in English may need a certified translation — OG can help."),
        _tip("Asegúrate de que cada documento esté completo, legible, bien iluminado y sin cortes ni desenfoque. Los documentos que no estén en inglés pueden necesitar una traducción certificada; OG puede ayudarte.")))

    # ================================================================== CONFIRM
    page(b, "confirm", ("Confirm and Send to OG", "Confirma y envía a OG"), group="confirm", ctx="applicant",
         desc=("Review your information and confirm that it is complete and accurate. OG Multiservices will use the information you provided to assist with preparing your Form I-485 and related documents.",
               "Revisa tu información y confirma que esté completa y correcta. OG Multiservices utilizará la información proporcionada para ayudarte con la preparación de tu Formulario I-485 y los documentos relacionados."))
    note(b, "confirm_warning", "Sending this to OG does not file anything with USCIS, is not an electronic signature and is not a decision about eligibility. OG will contact you about the next steps, including how any required signature is handled.",
         "Enviar esto a OG no presenta nada ante USCIS, no es una firma electrónica y no es una decisión sobre elegibilidad. OG te contactará sobre los siguientes pasos, incluido cómo se maneja cualquier firma requerida.")
    b.field("preparer_request", "consent", ("Request for preparation", "Solicitud de preparación"), ref="Part 12 (preparer prepared the application at the applicant's request)", note="Customer confirmation only; not a signature.", req=True, content=(
        "I ask OG Multiservices to assist with preparing my Form I-485 based only on the information I provided or authorized.",
        "Solicito a OG Multiservices que me ayude a preparar mi Formulario I-485 con base únicamente en la información que proporcioné o autoricé."))
    b.field("confirm_accurate", "consent", ("Accuracy confirmation and authorization", "Confirmación de exactitud y autorización"), ref="Part 10 (certification wording)", note="Customer confirmation only; not a signature and not the certification under penalty of perjury.", req=True, content=(
        "I confirm that the information I provided is complete and correct to the best of my knowledge, and I authorize OG Multiservices to use it to assist with preparing my Form I-485 and related documents.",
        "Confirmo que la información que proporcioné es completa y correcta según mi leal saber y entender, y autorizo a OG Multiservices a usarla para ayudarme a preparar mi Formulario I-485 y los documentos relacionados."))
    return b


def _features():
    return {
        "completeness_check": True, "consistency": "i485", "documents_check": True,
        "sections": SECTIONS, "contexts": CONTEXTS, "context_roles": CONTEXT_ROLES,
        "name_tokens": {"app": {"role": "applicant", "fallback": {"en": "the applicant", "es": "el solicitante"}}},
        "sync": [
            {"kind": "current_address", "record_field": "a_address_history", "prefix": "cur"},
            {"kind": "underlying_link", "field": "b_underlying"},
            {"kind": "drop_stale_candidate", "status_field": "a_foreign_addr_status", "status_value": "different", "record_field": "a_foreign_addr",
             "source": "a_address_history", "candidate": "last_foreign_address"},
            {"kind": "requirements"},
        ],
    }


def ensure_i485_intake():
    """Create the production I-485 intake and connect it to the Adjustment of Status service page (idempotent)."""
    service = (Service.query.join(ServiceCategory).filter(ServiceCategory.slug == "immigration", Service.slug == "adjustment-of-status").first())
    if not service:
        return False
    if Form.query.filter_by(slug=I485_SLUG).first():
        return False
    form = Form(slug=I485_SLUG, name_admin="I-485 Client Intake")
    db.session.add(form)
    form.form_type = "service_intake"
    form.status = "published"
    form.source_form_name = SOURCE_NAME
    form.source_edition = SOURCE_EDITION
    form.version = 1
    form.published_at = datetime.utcnow()
    form.title_en, form.title_es = "Adjustment of Status — Form I-485", "Ajuste de Estatus — Formulario I-485"
    form.description_en = "Guided intake for OG Multiservices to prepare your Form I-485. Your progress is saved automatically."
    form.description_es = "Solicitud guiada para que OG Multiservices prepare tu Formulario I-485. Tu progreso se guarda automáticamente."
    form.submit_label_en, form.submit_label_es = "Send to OG", "Enviar a OG"
    form.success_message_en = "OG Multiservices has your information and will review it. We'll contact you if we need anything else."
    form.success_message_es = "OG Multiservices tiene tu información y la revisará. Te contactaremos si necesitamos algo más."
    form.show_progress = True
    form.features_json = json.dumps(_features(), ensure_ascii=False)
    db.session.flush()
    build_i485(form)
    service.requires_intake = True
    service.form_id = form.id
    service.requires_account = True
    service.intake_label = "I-485 Client Intake"
    db.session.commit()
    return True


def ensure_i485_shared_data():
    """In-place refresh of an ALREADY seeded I-485 (never a rebuild): the reuse wording of each shared-data step ("Yes, this is correct" /
    "Review / Edit", or "Is this still current?" for time-sensitive facts), and a one-time repair of unfinished drafts whose shared
    blocks were frozen before the person's data was known (only choices that were merely defaulted are reset; answers are never touched).
    Idempotent."""
    from app.models import FieldOption, FormSubmission
    from app.shared_blocks import repair_unanswered

    form = Form.query.filter_by(slug=I485_SLUG).first()
    if form is None:
        return False
    changed = False
    fields = {f.internal_name: f for f in form.all_fields}
    for key in __import__("app.case_types", fromlist=["FORM_CASE_CONFIG"]).FORM_CASE_CONFIG["I-485"]["blocks"]:
        field = fields.get(key)
        if field is None:
            continue
        for value, en, es in _confirm_opts(key):
            opt = next((o for o in field.options if o.value == value), None)
            if opt is not None and (opt.label_en != en or opt.label_es != es):
                opt.label_en, opt.label_es = en, es
                changed = True
    for sub in FormSubmission.query.filter_by(form_id=form.id, is_complete=False).all():
        if sub.case_id and repair_unanswered(sub):
            changed = True
    if changed:
        db.session.commit()
    return changed
