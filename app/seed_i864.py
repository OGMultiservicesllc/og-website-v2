"""Form I-864 Client Intake — the fifth production Smart Intake, built natively on the Case + Person architecture.

SOURCE OF TRUTH: the supplied USCIS "Form I-864, Affidavit of Support Under Section 213A of the INA", Edition 08/24/26 (OMB No. 1615-0075,
expires 10/31/2027), 12 pages, Parts 1-11. Item numbers come from the PDF's own layout; every question carries its Part/Item in `source_ref`.

Part map (as printed):
  Part 1   Basis for filing (Items 1.a-1.f: petitioner / alien worker petition / 5% owner / only joint sponsor / first or second of two joint
           sponsors / substitute sponsor)
  Part 2   Information about the sponsor, Items 1-12 (name, mailing and physical address, domicile, DOB, birth country, SSN, immigration status,
           A-Number, USCIS account, active-duty military for petitioner sponsors)
  Part 3   Information about the principal immigrant, Items 1-7
  Part 4   Immigrants being sponsored, Items 1-7 (principal yes/no, family timing, Family Members 1-4 = Items 4-7; more go in Part 11)
  Part 5   Household size, Items 1-8 (arithmetic; "do not count anyone more than once")
  Part 6   Employment and income, Items 1-7 (situation, employers, occupation, individual income), 8-11 (other people's income), 12 total,
           13-14 (Form I-864A), 15-17 (federal tax returns: three most recent years)
  Part 7   Assets, Items 1-5 (sponsor + household members), 6-9 (principal immigrant), 10 total
  Part 8   Sponsor's contract, statement (Item 1.A/1.B interpreter, Item 2 preparer), contact (Items 3-5), certification, signature (Item 6)
  Part 9   Interpreter    Part 10  Preparer (OG)    Part 11  Additional information
Not customer questions on purpose: every signature and date (Part 8 Item 6, Part 9 Item 6, Part 10 Item 6), Part 10 (OG prepares), the attorney/G-28
box, every "For USCIS Use Only" box (submitter type, Section 213A review, poverty guideline table, remarks).

Financial values (income, taxes, assets, household counts) belong to THIS affidavit only. Who a person IS (name, DOB, SSN, A-Number, address,
phone) is a shared Person fact, reused through review-and-confirm (see app/shared_blocks.py). Poverty-guideline thresholds are NOT implemented: the
platform has no reliable, versioned source, and the form's I-864P comparison is OG's review. Nothing here says a household, income or assets are
sufficient, or that a joint sponsor is (or is not) needed.

The Form I-864 Instructions are NOT part of the supplied PDF, so no document request claims USCIS requires it unless the form itself says so.
"""

import json
from datetime import datetime

from app.extensions import db
from app.models import Form, Service, ServiceCategory
from app.seed_i130 import page, records, where
from app.seed_i485 import UNSURE, YN_UNSURE, any_of, block_pair, choice, kp, mark_block_fields, only_if
from app.seed_i90 import STATE_OPTIONS, UNIT_TYPES, YES_NO, Builder, _address_fields
from app.seed_i90_refine import _label, _tip
from app.seed_n400 import _cfg, note, show_any, show_page_any

I864_SLUG = "i-864-client-intake"
SOURCE_NAME = "I-864"
SOURCE_EDITION = "08/24/26"
NEVER = ("b_basis", "equals", "__never__")

SECTIONS = [
    {"key": "before", "title": {"en": "Before You Begin", "es": "Antes de empezar"}},
    {"key": "sponsor_basis", "title": {"en": "Why You Are the Sponsor", "es": "Por qué eres el patrocinador"}},
    {"key": "sponsor", "title": {"en": "About the Sponsor", "es": "Sobre el patrocinador"}},
    {"key": "principal", "title": {"en": "The Principal Immigrant", "es": "El inmigrante principal"}},
    {"key": "other_immigrants", "title": {"en": "Who You Are Sponsoring", "es": "A quién patrocinas"}},
    {"key": "household", "title": {"en": "Your Household", "es": "Tu hogar"}},
    {"key": "income", "title": {"en": "Employment & Current Income", "es": "Empleo e ingreso actual"}},
    {"key": "hh_income", "title": {"en": "Household Income", "es": "Ingreso del hogar"}},
    {"key": "tax", "title": {"en": "Federal Tax Information", "es": "Información de impuestos federales"}},
    {"key": "assets", "title": {"en": "Assets", "es": "Activos"}},
    {"key": "contract", "title": {"en": "Sponsor's Contract & Statement", "es": "Contrato y declaración del patrocinador"}},
    {"key": "contact", "title": {"en": "Contact & Interpreter", "es": "Contacto e intérprete"}},
    {"key": "documents", "title": {"en": "Documents", "es": "Documentos"}},
    {"key": "confirm", "title": {"en": "Confirmation", "es": "Confirmación"}},
]
CONTEXTS = {
    "sponsor": {"title": {"en": "Sponsor", "es": "Patrocinador"}, "subtitle": {"en": "The person promising financial support.", "es": "La persona que promete el apoyo económico."}, "tone": "accent", "icon": "person"},
    "principal": {"title": {"en": "Principal immigrant", "es": "Inmigrante principal"}, "subtitle": {"en": "The person immigrating who is being sponsored.", "es": "La persona que inmigra y es patrocinada."}, "tone": "brand", "icon": "people"},
}
CONTEXT_ROLES = {"sponsor": "sponsor", "principal": "principal_immigrant"}

WHERE_SSN = ("A Social Security number has 9 digits and is on the Social Security card.", "Un número de Seguro Social tiene 9 dígitos y está en la tarjeta del Seguro Social.")
WHERE_A = ("An A-Number is 7 to 9 digits and usually starts with “A”. It appears on a Green Card, a work permit (EAD) and other USCIS documents. Leave it blank if there is none.",
           "Un Número A tiene de 7 a 9 dígitos y normalmente empieza con “A”. Aparece en una Green Card, un permiso de trabajo (EAD) y otros documentos de USCIS. Déjalo en blanco si no hay.")
WHERE_ACCT = ("If there is a USCIS online account, the number appears in that account and on some USCIS notices. Leave it blank if there is none.",
              "Si hay una cuenta en línea de USCIS, el número aparece en esa cuenta y en algunas notificaciones. Déjalo en blanco si no hay.")
WHERE_INCOME = ("Use the exact line the form asks for: total income (adjusted gross income on IRS Form 1040EZ), as reported on the return you filed. It is on the tax return itself or on an IRS tax transcript. If you are not sure which line it is, choose the closest match and OG will confirm it with you before anything is prepared.",
                "Usa la línea exacta que pide el formulario: el ingreso total (ingreso bruto ajustado en el Formulario 1040EZ del IRS), según la declaración que presentaste. Está en la declaración de impuestos o en una transcripción del IRS. Si no estás seguro(a) de cuál línea es, elige la más parecida y OG la confirmará contigo antes de preparar nada.")


def para(b, name, en, es):
    b.field(name, "paragraph", ("", ""), content=(en, es))


def txt(en, es, cls="text-[15px] leading-relaxed text-slate-700"):
    return (f'<span class="block {cls}">{en}</span>', f'<span class="block {cls}">{es}</span>')


def head(en, es):
    return txt(en, es, "text-[15px] font-bold text-brand-800 pt-2")


def calc_fields(b, names_labels, ref_prefix):
    """Calculated answers (never asked): visible only in Review/Admin/snapshot, refreshed on every save."""
    for name, en, es, ref in names_labels:
        b.field(name, "short_answer", (en, es), ref=ref, note="Calculated by the platform from the answers above; not a question.")
        kp(b, name)
        b.rule("show_field", name, [NEVER])


def _add_preparer_page(b):
    """PART 10 — the preparer (OG) — INFORMATION only (Items 1-5); the preparer's signature and date (Item 6) are never collected.
    Defaults come from the central OG configuration (`business_info.PREPARER_*`), like the interpreter defaults."""
    page(b, "preparer", ("Who prepares your affidavit", "Quién prepara tu affidavit"),
         ("OG Multiservices prepares this affidavit for you, so OG is listed as the preparer. These details come from OG's own settings — you normally do not need to change anything. OG does not sign for you, and the preparer's signature is handled by OG separately.",
          "OG Multiservices prepara este affidavit por ti, así que OG figura como preparador. Estos datos vienen de la configuración propia de OG: normalmente no necesitas cambiar nada. OG no firma por ti, y la firma del preparador la maneja OG por separado."),
         group="confirm", ctx="sponsor")
    b.field("prep_family", "short_answer", ("Preparer's family name (last name)", "Apellido del preparador"), ref="Part 10, Item 1 (also named inline in Part 8, Item 2)", req=True, width="half", maxlen=30)
    b.field("prep_given", "short_answer", ("Preparer's given name (first name)", "Nombre del preparador"), ref="Part 10, Item 1 (also named inline in Part 8, Item 2)", req=True, width="half", maxlen=18)
    b.field("prep_org", "short_answer", ("Preparer's business or organization name", "Empresa u organización del preparador"), ref="Part 10, Item 2", maxlen=38)
    b.field("prep_phone", "phone", ("Preparer's daytime telephone number", "Teléfono de día del preparador"), ref="Part 10, Item 3", req=True, width="half")
    b.field("prep_mobile", "phone", ("Preparer's mobile telephone number (if any)", "Teléfono móvil del preparador (si tiene)"), ref="Part 10, Item 4", width="half")
    b.field("prep_email", "email", ("Preparer's email address (if any)", "Correo electrónico del preparador (si tiene)"), ref="Part 10, Item 5")
    b.fields["prep_email"].required = False
    for name, value in {"prep_family": "@biz:PREPARER_LAST_NAME", "prep_given": "@biz:PREPARER_FIRST_NAME", "prep_org": "@biz:PREPARER_ORG", "prep_phone": "@biz:PREPARER_PHONE",
                        "prep_mobile": "@biz:PREPARER_MOBILE", "prep_email": "@biz:PREPARER_EMAIL"}.items():
        b.fields[name].default_value = value


def build_i864(form):
    b = Builder(form)
    # ---- never-shown system page: frozen "does the customer's data already know this?" flags for the shared blocks
    page(b, "sys", ("Case information", "Información del caso"), group=None)
    blocks = ["sb_s_name", "sb_s_birth", "sb_s_ssn", "sb_s_ids", "sb_s_address", "sb_s_contact", "sb_p_name", "sb_p_birth", "sb_p_ids", "sb_p_phone"]
    for k in blocks:
        b.field(f"{k}_avail", "short_answer", (f"{k} available", f"{k} disponible"), ref="OG system flag (never shown)")
        kp(b, f"{k}_avail", system=True)
    show_page_any(b, "sys", [[("sb_s_name_avail", "equals", "__never__")]])

    # ================================================================== Before you begin
    page(b, "intro", ("Before you begin", "Antes de empezar"), group="before", ctx="sponsor")
    para(b, "intro_1",
         "This intake collects what OG Multiservices needs to prepare Form I-864, Affidavit of Support Under Section 213A of the INA (USCIS edition 08/24/26). Your answers save automatically, so you can stop and come back anytime.",
         "Este formulario reúne lo que OG Multiservices necesita para preparar el Formulario I-864, Declaración Jurada de Patrocinio bajo la Sección 213A de la INA (edición USCIS 08/24/26). Tus respuestas se guardan automáticamente, así que puedes parar y volver cuando quieras.")
    b.field("intro_case", "paragraph", ("", ""), content=("", ""))
    b.fields["intro_case"].config_json = json.dumps({"dynamic": {"kind": "i864_context"}})
    para(b, "intro_2",
         "The information about people (names, dates of birth, Social Security numbers, addresses) comes from the people already in your cases, so you confirm it instead of typing it again. The <strong>financial information</strong> on this page set — income, taxes, household and assets — belongs only to this affidavit.",
         "La información de las personas (nombres, fechas de nacimiento, números de Seguro Social, direcciones) viene de las personas que ya están en tus casos, así que la confirmas en lugar de escribirla otra vez. La <strong>información financiera</strong> de este formulario — ingresos, impuestos, hogar y activos — pertenece solo a este affidavit.")
    para(b, "intro_3",
         "OG Multiservices provides document preparation and administrative assistance. We are not a law firm and do not provide legal advice or representation. We cannot tell you whether your income or assets are enough, whether you need a joint sponsor, or which option applies to you: OG reviews that with you. Sending this to OG does not file anything with USCIS.",
         "OG Multiservices ofrece preparación de documentos y asistencia administrativa. No somos un bufete de abogados ni brindamos asesoría o representación legal. No podemos decirte si tus ingresos o activos son suficientes, si necesitas un patrocinador conjunto ni qué opción te aplica: OG lo revisa contigo. Enviar esto a OG no presenta nada ante USCIS.")

    # ================================================================== PART 1 — basis for filing
    page(b, "basis", ("Why are you the sponsor?", "¿Por qué eres el patrocinador?"),
         ("The form asks you to select only one. If you are not sure, say so — OG will review it with you.", "El formulario pide seleccionar solo una. Si no estás seguro(a), dilo: OG lo revisará contigo."), group="sponsor_basis", ctx="sponsor")
    choice(b, "b_basis", ("I am the sponsor submitting this affidavit of support because…", "Soy el patrocinador que presenta esta declaración jurada de patrocinio porque…"), "Part 1, Items 1.a–1.f", [
        ("1a", "I am the petitioner. I filed or am filing for the immigration of my relative.", "Soy el peticionario. Presenté o estoy presentando la petición para la inmigración de mi familiar."),
        ("1b", "I filed an alien worker petition on behalf of the intending immigrant, who is related to me as my…", "Presenté una petición de trabajador extranjero a favor del inmigrante, quien está relacionado conmigo como mi…"),
        ("1c", "I have an ownership interest of at least 5 percent in a business which filed an alien worker petition on behalf of the intending immigrant, who is related to me as my…", "Tengo una participación de propiedad de al menos 5 por ciento en un negocio que presentó una petición de trabajador extranjero a favor del inmigrante, quien está relacionado conmigo como mi…"),
        ("1d", "I am the only joint sponsor.", "Soy el único patrocinador conjunto."),
        ("1e", "I am the first or second of two joint sponsors.", "Soy el primero o el segundo de dos patrocinadores conjuntos."),
        ("1f", "The original petitioner is deceased. I am the substitute sponsor. I am the intending immigrant's…", "El peticionario original falleció. Soy el patrocinador sustituto. Soy el/la… del inmigrante."),
        UNSURE])
    para(b, "b_proof_note", "Note from the form: as a sponsor, you must include proof of your U.S. citizenship, U.S. national status, or lawful permanent resident status. OG will list it in your documents.",
         "Nota del formulario: como patrocinador, debes incluir prueba de tu ciudadanía de EE. UU., estatus de nacional de EE. UU. o estatus de residente permanente legal. OG lo incluirá en tu lista de documentos.")
    page(b, "basis_more", ("A little more about this", "Un poco más sobre esto"), group="sponsor_basis", ctx="sponsor")
    b.field("b_1b_rel", "short_answer", ("The intending immigrant is related to me as my…", "El inmigrante está relacionado conmigo como mi…"), ref="Part 1, Item 1.b", req=True, maxlen=40)
    only_if(b, "b_1b_rel", ("b_basis", "equals", "1b"))
    b.field("b_1c_business", "short_answer", ("Name of the business or organization that filed the alien worker petition", "Nombre del negocio u organización que presentó la petición de trabajador extranjero"), ref="Part 1, Item 1.c (business)", req=True, maxlen=80)
    b.field("b_1c_rel", "short_answer", ("The intending immigrant is related to me as my…", "El inmigrante está relacionado conmigo como mi…"), ref="Part 1, Item 1.c (relationship)", req=True, maxlen=40)
    only_if(b, "b_1c_business", ("b_basis", "equals", "1c"))
    only_if(b, "b_1c_rel", ("b_basis", "equals", "1c"))
    choice(b, "b_1e_which", ("I am the…", "Soy el…"), "Part 1, Item 1.e", [("first", "First of two joint sponsors", "Primero de dos patrocinadores conjuntos"), ("second", "Second of two joint sponsors", "Segundo de dos patrocinadores conjuntos")])
    only_if(b, "b_1e_which", ("b_basis", "equals", "1e"))
    b.field("b_1f_rel", "short_answer", ("I am the intending immigrant's…", "Soy el/la… del inmigrante"), ref="Part 1, Item 1.f", req=True, maxlen=40)
    only_if(b, "b_1f_rel", ("b_basis", "equals", "1f"))
    show_page_any(b, "basis_more", [[("b_basis", "equals", v)] for v in ("1b", "1c", "1e", "1f")])

    # ================================================================== PART 2 — the sponsor
    def edit_s_name():
        b.field("s_family", "short_answer", ("Sponsor's family name (last name)", "Apellido del patrocinador"), ref="Part 2, Item 1", req=True, width="half", maxlen=30)
        b.field("s_given", "short_answer", ("Sponsor's given name (first name)", "Nombre(s) del patrocinador"), ref="Part 2, Item 1", req=True, width="half", maxlen=18)
        b.field("s_middle", "short_answer", ("Middle name (if applicable)", "Segundo nombre (si aplica)"), ref="Part 2, Item 1", width="half", maxlen=18,
                help=("Full legal name — do not provide a nickname.", "Nombre legal completo: no des un apodo."))
        mark_block_fields(b, "sb_s_name", ["s_family", "s_given", "s_middle"])
    block_pair(b, "sb_s_name", group="sponsor", ctx="sponsor", form_name="I-864",
               review_title=("We already have {sp}'s legal name", "Ya tenemos el nombre legal de {sp}"), review_desc=("Confirm it or change it.", "Confírmalo o cámbialo."),
               edit_title=("The sponsor's full legal name", "El nombre legal completo del patrocinador"), edit_desc=None, build_edit=edit_s_name)

    def edit_s_address():
        b.field("sp_in_care_of", "short_answer", ("In care of name (if any)", "A cargo de (si aplica)"), ref="Part 2, Item 4 / Item 2 (In Care Of Name)", maxlen=34)
        _address_fields(b, "sp", "Part 2, Item 4 (Physical Address; Item 2 when the mailing address is the same)")
        mark_block_fields(b, "sb_s_address", [n for n in b.fields if n.startswith("sp_")])
    block_pair(b, "sb_s_address", group="sponsor", ctx="sponsor", form_name="I-864", needed=["sp_street", "sp_city"],
               review_title=("We already have {sp}'s address", "Ya tenemos la dirección de {sp}"), review_desc=("Confirm it or change it.", "Confírmala o cámbiala."),
               edit_title=("The sponsor's physical address", "La dirección física del patrocinador"),
               edit_desc=("Where the sponsor lives. If the mailing address is the same, you only enter it once.", "Donde vive el patrocinador. Si la dirección postal es la misma, solo la ingresas una vez."), build_edit=edit_s_address)
    page(b, "s_mail_gate", ("Mailing address", "Dirección postal"), group="sponsor", ctx="sponsor")
    b.field("s_mail_same", "single_choice", ("Is your current mailing address the same as your physical address?", "¿Tu dirección postal actual es la misma que tu dirección física?"), ref="Part 2, Item 3", req=True, opts=YES_NO)
    page(b, "s_mailing", ("The sponsor's current mailing address", "La dirección postal actual del patrocinador"), group="sponsor", ctx="sponsor")
    b.field("sm_in_care_of", "short_answer", ("In care of name (if any)", "A cargo de (si aplica)"), ref="Part 2, Item 2 (In Care Of Name)", maxlen=34)
    _address_fields(b, "sm", "Part 2, Item 2 (Current Mailing Address)")
    show_page_any(b, "s_mailing", [[("s_mail_same", "equals", "no")]])

    def edit_s_birth():
        b.field("s_dob", "date", ("Date of birth", "Fecha de nacimiento"), ref="Part 2, Item 6", req=True, date_rule="past", width="half")
        b.field("s_birth_country", "short_answer", ("Country of birth", "País de nacimiento"), ref="Part 2, Item 7", req=True, maxlen=60, width="half")
        b.field("s_domicile", "short_answer", ("Country of domicile", "País de domicilio"), ref="Part 2, Item 5", req=True, maxlen=60,
                help=("The country where the sponsor lives (has their principal residence).", "El país donde vive el patrocinador (su residencia principal)."))
        mark_block_fields(b, "sb_s_birth", ["s_dob", "s_birth_country", "s_domicile"])
    block_pair(b, "sb_s_birth", group="sponsor", ctx="sponsor", form_name="I-864", needed=["s_domicile"],
               review_title=("We already have {sp}'s birth information", "Ya tenemos los datos de nacimiento de {sp}"), review_desc=("Confirm it or change it. You will still add the country of domicile.", "Confírmalo o cámbialo. Aún agregarás el país de domicilio."),
               edit_title=("Birth and domicile", "Nacimiento y domicilio"), edit_desc=None, build_edit=edit_s_birth)

    def edit_s_ssn():
        b.field("s_ssn", "short_answer", ("U.S. Social Security Number (required)", "Número de Seguro Social de EE. UU. (obligatorio)"), ref="Part 2, Item 8", req=True, sensitive=True, pattern=r"\d{3}-?\d{2}-?\d{4}", msg=("Enter 9 digits.", "Ingresa 9 dígitos."))
        where(b, "s_ssn", *WHERE_SSN)
        mark_block_fields(b, "sb_s_ssn", ["s_ssn"])
    block_pair(b, "sb_s_ssn", group="sponsor", ctx="sponsor", form_name="I-864",
               review_title=("We already have {sp}'s Social Security number", "Ya tenemos el número de Seguro Social de {sp}"), review_desc=("Confirm it or change it.", "Confírmalo o cámbialo."),
               edit_title=("Social Security number", "Número de Seguro Social"), edit_desc=None, build_edit=edit_s_ssn)

    page(b, "s_status_page", ("The sponsor's immigration status", "El estatus migratorio del patrocinador"), group="sponsor", ctx="sponsor")
    choice(b, "s_status", ("Immigration status", "Estatus migratorio"), "Part 2, Item 9", [("usc", "I am a U.S. citizen.", "Soy ciudadano(a) de EE. UU."), ("national", "I am a U.S. national.", "Soy nacional de EE. UU."),
                                                                                 ("lpr", "I am a lawful permanent resident.", "Soy residente permanente legal.")])

    def edit_s_ids():
        b.field("s_anumber", "short_answer", ("Sponsor's A-Number (if any)", "Número A del patrocinador (si tiene)"), ref="Part 2, Item 10", sensitive=True, pattern=r"A?-?\d{7,9}", maxlen=12, msg=("Enter 7 to 9 digits, with or without “A-”.", "Ingresa 7 a 9 dígitos, con o sin “A-”."))
        where(b, "s_anumber", *WHERE_A)
        b.field("s_uscis", "short_answer", ("USCIS Online Account Number (if any)", "Número de cuenta en línea de USCIS (si tiene)"), ref="Part 2, Item 11", maxlen=12, pattern=r"\d{1,12}", msg=("Use digits only (up to 12).", "Usa solo dígitos (hasta 12)."))
        where(b, "s_uscis", *WHERE_ACCT)
        mark_block_fields(b, "sb_s_ids", ["s_anumber", "s_uscis"])
    block_pair(b, "sb_s_ids", group="sponsor", ctx="sponsor", form_name="I-864",
               review_title=("We already have {sp}'s A-Number and USCIS account", "Ya tenemos el Número A y la cuenta de USCIS de {sp}"), review_desc=("Confirm them or change them.", "Confírmalos o cámbialos."),
               edit_title=("The sponsor's A-Number and USCIS account", "Número A y cuenta de USCIS del patrocinador"), edit_desc=("Only if the sponsor has them.", "Solo si el patrocinador los tiene."), build_edit=edit_s_ids)
    page(b, "s_military_page", ("Military service", "Servicio militar"), ("To be completed by petitioner sponsors only.", "Solo lo completan los patrocinadores que son peticionarios."), group="sponsor", ctx="sponsor")
    b.field("s_military", "single_choice", ("I am currently on active duty in the United States Armed Forces or U.S. Coast Guard.", "Actualmente estoy en servicio activo en las Fuerzas Armadas de los Estados Unidos o en la Guardia Costera de EE. UU."), ref="Part 2, Item 12", req=True, opts=YES_NO)
    show_page_any(b, "s_military_page", [[("b_basis", "equals", "1a")], [("b_basis", "equals", "unsure")]])

    # ================================================================== PART 3 — the principal immigrant
    def edit_p_name():
        b.field("p_family", "short_answer", ("Principal immigrant's family name (last name)", "Apellido del inmigrante principal"), ref="Part 3, Item 1", req=True, width="half", maxlen=30)
        b.field("p_given", "short_answer", ("Principal immigrant's given name (first name)", "Nombre(s) del inmigrante principal"), ref="Part 3, Item 1", req=True, width="half", maxlen=18)
        b.field("p_middle", "short_answer", ("Middle name (if applicable)", "Segundo nombre (si aplica)"), ref="Part 3, Item 1", width="half", maxlen=18)
        mark_block_fields(b, "sb_p_name", ["p_family", "p_given", "p_middle"])
    block_pair(b, "sb_p_name", group="principal", ctx="principal", form_name="I-864",
               review_title=("We already have {pi}'s legal name", "Ya tenemos el nombre legal de {pi}"), review_desc=("Confirm it or change it.", "Confírmalo o cámbialo."),
               edit_title=("The principal immigrant's full legal name", "El nombre legal completo del inmigrante principal"), edit_desc=None, build_edit=edit_p_name)
    page(b, "p_mailing", ("The principal immigrant's current mailing address", "La dirección postal actual del inmigrante principal"), group="principal", ctx="principal")
    b.field("pm_in_care_of", "short_answer", ("In care of name (if any)", "A cargo de (si aplica)"), ref="Part 3, Item 2 (In Care Of Name)", maxlen=34)
    _address_fields(b, "pm", "Part 3, Item 2 (Current Mailing Address)")

    def edit_p_birth():
        b.field("p_dob", "date", ("Date of birth", "Fecha de nacimiento"), ref="Part 3, Item 4", req=True, date_rule="past", width="half")
        b.field("p_citizenship", "short_answer", ("Country of citizenship or nationality", "País de ciudadanía o nacionalidad"), ref="Part 3, Item 3", req=True, maxlen=60, width="half")
        mark_block_fields(b, "sb_p_birth", ["p_dob", "p_citizenship"])
    block_pair(b, "sb_p_birth", group="principal", ctx="principal", form_name="I-864", needed=["p_citizenship"],
               review_title=("We already have {pi}'s birth and citizenship information", "Ya tenemos los datos de nacimiento y ciudadanía de {pi}"), review_desc=("Confirm it or change it.", "Confírmalo o cámbialo."),
               edit_title=("Birth date and citizenship", "Fecha de nacimiento y ciudadanía"), edit_desc=None, build_edit=edit_p_birth)

    def edit_p_ids():
        b.field("p_anumber", "short_answer", ("A-Number (if any)", "Número A (si tiene)"), ref="Part 3, Item 5", sensitive=True, pattern=r"A?-?\d{7,9}", maxlen=12, msg=("Enter 7 to 9 digits, with or without “A-”.", "Ingresa 7 a 9 dígitos, con o sin “A-”."))
        where(b, "p_anumber", *WHERE_A)
        b.field("p_uscis", "short_answer", ("USCIS Online Account Number (if any)", "Número de cuenta en línea de USCIS (si tiene)"), ref="Part 3, Item 6", maxlen=12, pattern=r"\d{1,12}", msg=("Use digits only (up to 12).", "Usa solo dígitos (hasta 12)."))
        where(b, "p_uscis", *WHERE_ACCT)
        mark_block_fields(b, "sb_p_ids", ["p_anumber", "p_uscis"])
    block_pair(b, "sb_p_ids", group="principal", ctx="principal", form_name="I-864",
               review_title=("We already have {pi}'s A-Number and USCIS account", "Ya tenemos el Número A y la cuenta de USCIS de {pi}"), review_desc=("Confirm them or change them.", "Confírmalos o cámbialos."),
               edit_title=("The principal immigrant's A-Number and USCIS account", "Número A y cuenta de USCIS del inmigrante principal"), edit_desc=("Only if the principal immigrant has them.", "Solo si el inmigrante principal los tiene."), build_edit=edit_p_ids)

    def edit_p_phone():
        b.field("p_phone", "phone", ("Daytime telephone number", "Teléfono de día"), ref="Part 3, Item 7", req=True, width="half")
        mark_block_fields(b, "sb_p_phone", ["p_phone"])
    block_pair(b, "sb_p_phone", group="principal", ctx="principal", form_name="I-864",
               review_title=("We already have {pi}'s telephone number", "Ya tenemos el teléfono de {pi}"), review_desc=("Is it still current?", "¿Sigue vigente?"),
               edit_title=("The principal immigrant's telephone number", "El teléfono del inmigrante principal"), edit_desc=None, build_edit=edit_p_phone)

    # ================================================================== PART 4 — who is being sponsored
    page(b, "i_principal_page", ("Who you are sponsoring", "A quién patrocinas"), group="other_immigrants", ctx="sponsor")
    b.field("i_principal", "single_choice", ("Are you sponsoring the principal immigrant named earlier?", "¿Estás patrocinando al inmigrante principal mencionado antes?"), ref="Part 4, Item 1", req=True, opts=[
        ("yes", "Yes", "Sí"), ("no", "No — I am sponsoring family members as the second joint sponsor, or I am sponsoring family members who are immigrating more than six months after the principal immigrant",
                              "No: estoy patrocinando a familiares como segundo patrocinador conjunto, o estoy patrocinando a familiares que inmigran más de seis meses después del inmigrante principal")])
    b.field("i_family_q", "single_choice", ("Are you also sponsoring any family members?", "¿También estás patrocinando a algún familiar?"), ref="Part 4, Items 2–3 (OG helper)", req=True, opts=YES_NO,
            note="Chooses whether Items 2/3 and the family list (Items 4-7) are asked. When Item 1 is No, family members are required.")
    only_if(b, "i_family_q", ("i_principal", "equals", "yes"))
    page(b, "i_family_page", ("The family members you are sponsoring", "Los familiares que estás patrocinando"), group="other_immigrants", ctx="sponsor")
    choice(b, "i_timing", ("These family members are…", "Estos familiares…"), "Part 4, Items 2 / 3", [
        ("same_time", "Immigrating at the same time or within six months of the principal immigrant (do not include any relative listed on a separate visa petition)", "Inmigran al mismo tiempo o dentro de los seis meses del inmigrante principal (no incluyas a ningún familiar que aparezca en una petición de visa aparte)"),
        ("later", "Immigrating more than six months after the principal immigrant", "Inmigran más de seis meses después del inmigrante principal")])
    records(b, "i_family", ("Family members you are sponsoring", "Familiares que estás patrocinando"), "Part 4, Items 4–7 (Family Members 1–4; more go in Part 11)", "i864_family", req=True, max=20,
            help=("Add each one. Pick someone you already have in your cases, or type a new person.", "Agrega a cada uno. Elige a alguien que ya tienes en tus casos, o escribe a una persona nueva."))
    show_page_any(b, "i_family_page", [[("i_family_q", "equals", "yes")], [("i_principal", "equals", "no")]])

    # ================================================================== PART 5 — household
    page(b, "h_marital", ("Your household — marital status", "Tu hogar — estado civil"), ("The household size counts each person once. We do the arithmetic for you.", "El tamaño del hogar cuenta a cada persona una sola vez. Nosotros hacemos la aritmética."), group="household", ctx="sponsor")
    b.field("h_married", "single_choice", ("Are you currently married?", "¿Estás casado(a) actualmente?"), ref="Part 5, Item 3", req=True, opts=YES_NO)
    choice(b, "h_spouse", ("Your spouse…", "Tu cónyuge…"), "Part 5, Item 3 (already counted in Item 1?)", [
        ("principal", "Is the principal immigrant I am sponsoring", "Es el inmigrante principal que estoy patrocinando"),
        ("sponsored", "Is one of the other family members I am sponsoring", "Es uno de los otros familiares que estoy patrocinando"),
        ("other", "Is not being sponsored on this affidavit", "No está siendo patrocinado(a) en este affidavit")],
        help=("The form says to enter 0 for your spouse if you already counted them among the persons you are sponsoring.", "El formulario indica poner 0 para tu cónyuge si ya lo contaste entre las personas que patrocinas."))
    only_if(b, "h_spouse", ("h_married", "equals", "yes"))
    page(b, "h_people_page", ("Other people in your household", "Otras personas en tu hogar"),
         ("Add your spouse (if not sponsored), dependent children, other dependents, people you sponsored before and still support, and relatives combining income with you. Do not add yourself or people you are already sponsoring here.",
          "Agrega a tu cónyuge (si no está patrocinado), hijos dependientes, otros dependientes, personas que patrocinaste antes y aún mantienes, y familiares que combinan ingresos contigo. No te agregues a ti ni a las personas que ya patrocinas aquí."),
         group="household", ctx="sponsor")
    records(b, "h_people", ("People in your household who are not sponsored on this affidavit", "Personas de tu hogar que no son patrocinadas en este affidavit"), "Part 5, Items 3–7", "i864_household", max=30,
            help=("If the person is already counted (for example the principal immigrant), we will not count them twice and will tell you why.", "Si la persona ya está contada (por ejemplo el inmigrante principal), no la contaremos dos veces y te diremos por qué."))
    page(b, "h_summary", ("Your household", "Tu hogar"), group="household", ctx="sponsor")
    b.field("h_card", "paragraph", ("", ""), content=("", ""))
    b.fields["h_card"].config_json = json.dumps({"dynamic": {"kind": "i864_household"}})
    choice(b, "h_ok", ("Does this list look right?", "¿Esta lista se ve bien?"), "OG helper (household review)", [("yes", "Yes, it looks right", "Sí, se ve bien"), ("review", "Something is missing or wrong — OG will review it with me", "Falta algo o hay algo mal: OG lo revisará conmigo")],
           note_="Customer check of the calculated household; “review” is a workflow flag for OG.")
    calc_fields(b, [(f"c_hh_{i}", f"Part 5, Item {i} (calculated)", f"Parte 5, Ítem {i} (calculado)", f"Part 5, Item {i}") for i in range(1, 9)], "c_hh")

    # ================================================================== PART 6 — employment and current income
    page(b, "e_status_page", ("Your work situation", "Tu situación laboral"), ("Select everything that is true right now.", "Selecciona todo lo que sea cierto ahora."), group="income", ctx="sponsor")
    b.field("e_status", "multi_choice", ("I am currently…", "Actualmente estoy…"), ref="Part 6, Items 1, 4, 5, 6", req=True, opts=[
        ("employed", "Employed", "Empleado(a)"), ("self_employed", "Self-employed", "Trabajando por cuenta propia"), ("retired", "Retired", "Jubilado(a)"), ("unemployed", "Unemployed", "Desempleado(a)")])
    b.field("e_retired_since", "date", ("Retired since", "Jubilado(a) desde"), ref="Part 6, Item 5", req=True, date_rule="past", width="half")
    b.rule("show_field", "e_retired_since", [("e_status", "selected", "retired")])
    b.field("e_unemployed_since", "date", ("Unemployed since", "Desempleado(a) desde"), ref="Part 6, Item 6", req=True, date_rule="past", width="half")
    b.rule("show_field", "e_unemployed_since", [("e_status", "selected", "unemployed")])
    page(b, "e_income_page", ("Your income", "Tu ingreso"), ("Item 7 asks for your current individual annual income. Add each source; we add them up.", "El Ítem 7 pide tu ingreso anual individual actual. Agrega cada fuente; nosotros las sumamos."), group="income", ctx="sponsor")
    b.field("e_has_income", "single_choice", ("Do you currently have income of your own from any source?", "¿Actualmente tienes ingresos propios de alguna fuente?"), ref="Part 6, Item 7 (OG helper)", req=True, opts=YES_NO)
    records(b, "e_sources", ("Your income sources", "Tus fuentes de ingreso"), "Part 6, Items 1–4 and 7 (employer 1 and 2, occupation, self-employment, current individual annual income)", "i864_income_source", req=True, max=20,
            help=("The form lists up to two employers and one self-employment occupation. Your total is the sum of every source.", "El formulario lista hasta dos empleadores y una ocupación por cuenta propia. Tu total es la suma de todas las fuentes."))
    only_if(b, "e_sources", ("e_has_income", "equals", "yes"))
    b.fields["e_sources"].source_note = "Item 7 is one total: the intake keeps each source and calculates the total. The first two jobs map to Employer 1 / 2 (Items 2-3), the first job's occupation to Item 1, self-employment to Item 4."
    page(b, "e_totals", ("Your income so far", "Tu ingreso hasta ahora"), group="income", ctx="sponsor")
    b.field("e_totals_card", "paragraph", ("", ""), content=("", ""))
    b.fields["e_totals_card"].config_json = json.dumps({"dynamic": {"kind": "i864_income"}})
    calc_fields(b, [("c_inc_7", "Part 6, Item 7 (calculated): my current individual annual income", "Parte 6, Ítem 7 (calculado): mi ingreso anual individual actual", "Part 6, Item 7"),
                    ("c_inc_12", "Part 6, Item 12 (calculated): my current annual household income", "Parte 6, Ítem 12 (calculado): mi ingreso anual actual del hogar", "Part 6, Item 12")], "c_inc")

    # ================================================================== PART 6 — other people's income (Items 8-14)
    page(b, "hi_gate", ("Income from other people", "Ingreso de otras personas"), group="hh_income", ctx="sponsor")
    choice(b, "hi_use", ("Are you using income from any other person who was counted in your household size, including, in certain conditions, the intending immigrant?", "¿Estás usando el ingreso de alguna otra persona que se contó en el tamaño de tu hogar, incluido, en ciertas condiciones, el inmigrante?"), "Part 6, Items 8–11 (OG helper)", YN_UNSURE,
           help=("Do not include anyone's income unless you choose to. See the Form I-864 Instructions; OG will review this with you.", "No incluyas el ingreso de nadie a menos que lo elijas. Consulta las Instrucciones del Formulario I-864; OG lo revisará contigo."))
    page(b, "hi_people_page", ("Whose income are you using?", "¿El ingreso de quién estás usando?"), ("Name, relationship and current annual income. Each amount stays with the person who earns it.", "Nombre, relación e ingreso anual actual. Cada monto queda con la persona que lo gana."), group="hh_income", ctx="sponsor")
    records(b, "inc_people", ("People whose income you are using", "Personas cuyo ingreso estás usando"), "Part 6, Items 8–11 (Persons 1–4; more go in Part 11)", "i864_income_person", req=True, max=10)
    page(b, "hi_forms", ("Forms I-864A", "Formularios I-864A"), group="hh_income", ctx="sponsor")
    b.field("hi_i864a", "single_choice", ("The people listed have completed Form I-864A. I am filing along with this affidavit all necessary Forms I-864A completed by these people.", "Las personas listadas completaron el Formulario I-864A. Estoy presentando junto con este affidavit todos los Formularios I-864A necesarios completados por estas personas."), ref="Part 6, Item 13", req=True, opts=YES_NO)
    b.field("hi_i864a_exempt", "single_choice", ("One or more of the people listed do not need to complete Form I-864A because he or she is the intending immigrant and has no accompanying dependents.", "Una o más de las personas listadas no necesitan completar el Formulario I-864A porque es el inmigrante y no tiene dependientes que lo acompañen."), ref="Part 6, Item 14", req=True, opts=YES_NO)
    b.field("hi_i864a_exempt_name", "short_answer", ("Who is that person?", "¿Quién es esa persona?"), ref="Part 6, Item 14 (name)", maxlen=38)
    only_if(b, "hi_i864a_exempt_name", ("hi_i864a_exempt", "equals", "yes"))
    for pg in ("hi_people_page", "hi_forms"):
        show_page_any(b, pg, [[("hi_use", "equals", "yes")]])

    # ================================================================== PART 6 — federal tax return information (Items 15-17)
    page(b, "t_gate", ("Federal tax returns", "Declaraciones federales de impuestos"), group="tax", ctx="sponsor")
    b.field("t_three", "single_choice", ("Have you filed a Federal income tax return for each of the three most recent tax years?", "¿Has presentado una declaración federal de impuestos para cada uno de los tres años fiscales más recientes?"), ref="Part 6, Item 15", req=True, opts=YES_NO)
    b.field("t_norequire", "single_choice", ("I was not required to file a Federal income tax return as my income was below the IRS required level and I have attached evidence to support this.", "No estaba obligado(a) a presentar una declaración federal de impuestos porque mi ingreso estaba por debajo del nivel requerido por el IRS y he adjuntado evidencia que lo respalda."), ref="Part 6, Item 17", req=True, opts=YES_NO)
    page(b, "t_years_page", ("Your tax years", "Tus años fiscales"),
         ("Type the most recent tax year and your total income for it. The form only requires the most recent year; you may add up to two more. The years are yours — nothing is pre-filled.", "Escribe el año fiscal más reciente y tu ingreso total de ese año. El formulario solo requiere el año más reciente; puedes agregar hasta dos más. Los años son los tuyos: no hay nada pre-llenado."),
         group="tax", ctx="sponsor")
    records(b, "t_years", ("Federal tax return years", "Años de declaraciones federales de impuestos"), "Part 6, Items 16.a–16.c (Most Recent, 2nd Most Recent, 3rd Most Recent)", "i864_tax_year", max=10, help=WHERE_INCOME)
    b.fields["t_years"].source_note = "Records are ordered by tax year: the newest is Item 16.a, then 16.b, 16.c. The exact concept is 'total income (adjusted gross income on IRS Form 1040EZ)'; the form allows 'zero' or 'N/A'."

    # ================================================================== PART 7 — assets
    page(b, "a_gate", ("Assets", "Activos"), ("Part 7 is only for adding assets to your income. If your income (or your household's) exceeds the Federal Poverty Guidelines for your household size, the form says you are not required to complete it — OG checks that with you.", "La Parte 7 es solo para sumar activos a tu ingreso. Si tu ingreso (o el de tu hogar) supera las Pautas Federales de Pobreza para el tamaño de tu hogar, el formulario dice que no tienes que completarla: OG lo verifica contigo."), group="assets", ctx="sponsor")
    choice(b, "a_use", ("Do you want to include assets on this affidavit?", "¿Quieres incluir activos en este affidavit?"), "Part 7 (OG helper — whether Part 7 is completed)", YN_UNSURE)
    page(b, "a_list_page", ("Your assets", "Tus activos"), ("Add each asset once, with whose it is. Cash and accounts are balances; real estate is net of mortgage debt; stocks, bonds and other assets are net cash value.", "Agrega cada activo una vez, indicando de quién es. Efectivo y cuentas son saldos; bienes raíces es el valor neto después de la hipoteca; acciones, bonos y otros activos son valor neto en efectivo."), group="assets", ctx="sponsor")
    records(b, "a_assets", ("Assets", "Activos"), "Part 7, Items 1–3 (yours), 5 (household members'), 6–8 (principal immigrant's)", "i864_asset", max=30,
            help=("The principal immigrant's assets are only included if the principal immigrant is being sponsored on this affidavit.", "Los activos del inmigrante principal solo se incluyen si el inmigrante principal es patrocinado en este affidavit."))
    for pg in ("a_list_page",):
        show_page_any(b, pg, [[("a_use", "equals", "yes")], [("a_use", "equals", "unsure")]])
    page(b, "a_totals", ("Your asset totals", "Los totales de tus activos"), group="assets", ctx="sponsor")
    b.field("a_totals_card", "paragraph", ("", ""), content=("", ""))
    b.fields["a_totals_card"].config_json = json.dumps({"dynamic": {"kind": "i864_assets"}})
    calc_fields(b, [(f"c_ast_{i}", f"Part 7, Item {i} (calculated)", f"Parte 7, Ítem {i} (calculado)", f"Part 7, Item {i}") for i in range(1, 11)], "c_ast")
    show_page_any(b, "a_totals", [[("a_use", "equals", "yes")], [("a_use", "equals", "unsure")]])

    # ================================================================== PART 8 — the sponsor's contract, statement, contact
    C = "contract"
    page(b, "c1", ("The sponsor's contract — what signing means", "El contrato del patrocinador — qué significa firmar"),
         ("Part 8 of the form describes the obligations of a sponsor. Read it carefully. This is the official English text as printed on the form.", "La Parte 8 del formulario describe las obligaciones de un patrocinador. Léela con cuidado. Abajo aparece una traducción de cortesía hecha por OG; no es un texto oficial de USCIS. El texto oficial es el del formulario en inglés y es el que prevalece."), group=C, ctx="sponsor")
    for name, (en, es) in {
        "c1_n0": txt("<strong>NOTE:</strong> Read the Penalties section of the Form I-864 Instructions before completing this part.",
                     "<strong>NOTA:</strong> Lee la sección de Sanciones (Penalties) de las Instrucciones del Formulario I-864 antes de completar esta parte."),
        "c1_p0": txt("Please note that, by signing this Form I-864, you agree to assume certain specific obligations under the Immigration and Nationality Act (INA) and other Federal laws. The following paragraphs describe those obligations. Please read the following information carefully before you sign Form I-864. If you do not understand the obligations, you may wish to consult an attorney or accredited representative.",
                     "Ten en cuenta que, al firmar este Formulario I-864, aceptas asumir ciertas obligaciones específicas bajo la Ley de Inmigración y Nacionalidad (INA) y otras leyes federales. Los siguientes párrafos describen esas obligaciones. Lee con cuidado la siguiente información antes de firmar el Formulario I-864. Si no entiendes las obligaciones, puedes consultar a un abogado o representante acreditado."),
        "c1_h1": head("What is the Legal Effect of My Signing Form I-864?", "¿Cuál es el efecto legal de firmar el Formulario I-864?"),
        "c1_p1": txt("If you sign Form I-864 on behalf of any person (called the intending immigrant) who is applying for an immigrant visa or for adjustment of status to a lawful permanent resident, and that intending immigrant submits Form I-864 to the U.S. Government with his or her application for an immigrant visa or adjustment of status, under INA section 213A, these actions create a contract between you and the U.S. Government. The intending immigrant becoming a lawful permanent resident is the consideration for the contract.",
                     "Si firmas el Formulario I-864 a favor de cualquier persona (llamada el inmigrante) que solicita una visa de inmigrante o el ajuste de estatus a residente permanente legal, y ese inmigrante presenta el Formulario I-864 al Gobierno de EE. UU. con su solicitud de visa de inmigrante o de ajuste de estatus, bajo la sección 213A de la INA, estas acciones crean un contrato entre tú y el Gobierno de EE. UU. Que el inmigrante se convierta en residente permanente legal es la contraprestación del contrato."),
        "c1_p2": txt("Under this contract, you agree that, in deciding whether the intending immigrant can establish that he or she is not inadmissible to the United States as a person likely to become a public charge, the U.S. Government can consider your income and assets as available for the support of the intending immigrant.",
                     "Bajo este contrato, aceptas que, al decidir si el inmigrante puede establecer que no es inadmisible a los Estados Unidos como persona que probablemente se convierta en carga pública, el Gobierno de EE. UU. puede considerar tus ingresos y activos como disponibles para el sostenimiento del inmigrante."),
        "c1_h2": head("What If I Choose Not to Sign Form I-864?", "¿Qué pasa si decido no firmar el Formulario I-864?"),
        "c1_p3": txt("The U.S. Government cannot make you sign Form I-864 if you do not want to do so. But if you do not sign Form I-864, the intending immigrant may not become a lawful permanent resident in the United States.",
                     "El Gobierno de EE. UU. no puede obligarte a firmar el Formulario I-864 si no quieres hacerlo. Pero si no firmas el Formulario I-864, es posible que el inmigrante no pueda convertirse en residente permanente legal en los Estados Unidos."),
    }.items():
        b.field(name, "paragraph", ("", ""), content=(en, es))
    page(b, "c2", ("The sponsor's contract — what signing requires", "El contrato del patrocinador — lo que exige firmar"), ("The English is the official text as printed on the form; the Spanish is OG's courtesy translation.", 'El texto oficial es el del formulario en inglés; el español es una traducción de cortesía de OG, no un texto oficial de USCIS.'), group=C, ctx="sponsor")
    for name, (en, es) in {
        "c2_h1": head("What Does Signing Form I-864 Require Me To Do?", "¿Qué me exige hacer firmar el Formulario I-864?"),
        "c2_p1": txt("If an intending immigrant becomes a lawful permanent resident in the United States based on a Form I-864 that you have signed, then, until your obligations under Form I-864 terminate, you must:",
                     "Si un inmigrante se convierte en residente permanente legal en los Estados Unidos con base en un Formulario I-864 que firmaste, entonces, hasta que terminen tus obligaciones bajo el Formulario I-864, debes:"),
        "c2_a": txt("<strong>A.</strong> Provide the intending immigrant any support necessary to maintain him or her at an income that is at least 125 percent of the Federal Poverty Guidelines for his or her household size (100 percent if you are the petitioning sponsor and are on active duty in the U.S. Armed Forces or U.S. Coast Guard, and the person is your husband, wife, or unmarried child under 21 years of age); and",
                    "<strong>A.</strong> Proporcionar al inmigrante cualquier apoyo necesario para mantenerlo(a) con un ingreso de al menos 125 por ciento de las Pautas Federales de Pobreza para el tamaño de su hogar (100 por ciento si eres el patrocinador peticionario y estás en servicio activo en las Fuerzas Armadas o la Guardia Costera de EE. UU., y la persona es tu esposo(a) o hijo(a) soltero(a) menor de 21 años); y"),
        "c2_b": txt("<strong>B.</strong> Notify U.S. Citizenship and Immigration Services (USCIS) of any change in your address, within 30 days of the change, by filing Form I-865.",
                    "<strong>B.</strong> Notificar a los Servicios de Ciudadanía e Inmigración de EE. UU. (USCIS) cualquier cambio de tu dirección, dentro de los 30 días del cambio, presentando el Formulario I-865."),
        "c2_h2": head("What Other Consequences Are There?", "¿Qué otras consecuencias hay?"),
        "c2_p2": txt("If an intending immigrant becomes a lawful permanent resident in the United States based on a Form I-864 that you have signed, then, until your obligations under Form I-864 terminate, the U.S. Government may consider (deem) your income and assets as available to that person, in determining whether he or she is eligible for certain Federal means-tested public benefits and also for state or local means-tested public benefits, if the state or local government's rules provide for consideration (deeming) of your income and assets as available to the person. This provision does not apply to public benefits specified in section 403(c) of the Welfare Reform Act such as emergency Medicaid, short-term, non-cash emergency relief; services provided under the National School Lunch and Child Nutrition Acts; immunizations and testing and treatment for communicable diseases; and means-tested programs under the Elementary and Secondary Education Act.",
                     "Si un inmigrante se convierte en residente permanente legal en los Estados Unidos con base en un Formulario I-864 que firmaste, entonces, hasta que terminen tus obligaciones bajo el Formulario I-864, el Gobierno de EE. UU. puede considerar (atribuir) tus ingresos y activos como disponibles para esa persona al determinar si es elegible para ciertos beneficios públicos federales sujetos a verificación de recursos y también para beneficios públicos estatales o locales sujetos a verificación de recursos, si las reglas del gobierno estatal o local prevén la consideración (atribución) de tus ingresos y activos como disponibles para la persona. Esta disposición no aplica a los beneficios públicos especificados en la sección 403(c) de la Ley de Reforma de Bienestar Social, como Medicaid de emergencia, alivio de emergencia no monetario a corto plazo; servicios bajo las Leyes Nacionales de Almuerzo Escolar y Nutrición Infantil; vacunas y pruebas y tratamiento de enfermedades transmisibles; y programas sujetos a verificación de recursos bajo la Ley de Educación Primaria y Secundaria."),
    }.items():
        b.field(name, "paragraph", ("", ""), content=(en, es))
    page(b, "c3", ("The sponsor's contract — if obligations are not fulfilled, and when they end", "El contrato del patrocinador — si no se cumplen las obligaciones y cuándo terminan"), ("The English is the official text as printed on the form; the Spanish is OG's courtesy translation.", 'El texto oficial es el del formulario en inglés; el español es una traducción de cortesía de OG, no un texto oficial de USCIS.'), group=C, ctx="sponsor")
    for name, (en, es) in {
        "c3_h1": head("What If I Do Not Fulfill My Obligations?", "¿Qué pasa si no cumplo mis obligaciones?"),
        "c3_p1": txt("If you do not provide sufficient support to the person who becomes a lawful permanent resident based on a Form I-864 that you signed, that person may sue you for this support. If a Federal, state, local, or private agency provided any covered means-tested public benefit to the person who becomes a lawful permanent resident based on a Form I-864 that you signed, the agency may ask you to reimburse them for the amount of the benefits they provided. If you do not make the reimbursement, the agency may sue you for the amount that the agency believes you owe. If you are sued, and the court enters a judgment against you, the person or agency that sued you may use any legally permitted procedures for enforcing or collecting the judgment. You may also be required to pay the costs of collection, including attorney fees. If you do not file a properly completed Form I-865 within 30 days of any change of address, USCIS may impose a civil fine for your failing to do so.",
                     "Si no proporcionas apoyo suficiente a la persona que se convierte en residente permanente legal con base en un Formulario I-864 que firmaste, esa persona puede demandarte por ese apoyo. Si una agencia federal, estatal, local o privada proporcionó algún beneficio público cubierto sujeto a verificación de recursos a la persona que se convierte en residente permanente legal con base en un Formulario I-864 que firmaste, la agencia puede pedirte que le reembolses el monto de los beneficios que proporcionó. Si no haces el reembolso, la agencia puede demandarte por el monto que considere que debes. Si te demandan y el tribunal dicta una sentencia en tu contra, la persona o agencia que te demandó puede usar cualquier procedimiento legalmente permitido para hacer cumplir o cobrar la sentencia. También se te puede exigir pagar los costos de cobro, incluidos honorarios de abogados. Si no presentas un Formulario I-865 debidamente completado dentro de los 30 días de cualquier cambio de dirección, USCIS puede imponer una multa civil por no hacerlo."),
        "c3_h2": head("When Will These Obligations End?", "¿Cuándo terminarán estas obligaciones?"),
        "c3_p2": txt("Your obligations under a Form I-864 that you signed will end if the person who becomes a lawful permanent resident based on that affidavit: <strong>A.</strong> Becomes a U.S. citizen; <strong>B.</strong> Has worked, or can receive credit for, 40 quarters of coverage under the Social Security Act; <strong>C.</strong> No longer has lawful permanent resident status and has departed the United States; <strong>D.</strong> Is subject to removal, but applies for and obtains, in removal proceedings, a new grant of adjustment of status, based on a new affidavit of support, if one is required; or <strong>E.</strong> Dies.",
                     "Tus obligaciones bajo un Formulario I-864 que firmaste terminarán si la persona que se convierte en residente permanente legal con base en ese affidavit: <strong>A.</strong> Se convierte en ciudadano(a) de EE. UU.; <strong>B.</strong> Ha trabajado, o puede recibir crédito por, 40 trimestres de cobertura bajo la Ley del Seguro Social; <strong>C.</strong> Ya no tiene el estatus de residente permanente legal y ha salido de los Estados Unidos; <strong>D.</strong> Está sujeta a remoción, pero solicita y obtiene, en procedimientos de remoción, una nueva concesión de ajuste de estatus, con base en un nuevo affidavit de patrocinio, si se requiere uno; o <strong>E.</strong> Fallece."),
        "c3_n": txt("<strong>NOTE:</strong> Divorce does not terminate your obligations under Form I-864. Your obligations under a Form I-864 that you signed also end if you die. Therefore, if you die, your estate is not required to take responsibility for the person's support after your death. However, your estate may owe any support that you accumulated before you died.",
                    "<strong>NOTA:</strong> El divorcio no termina tus obligaciones bajo el Formulario I-864. Tus obligaciones bajo un Formulario I-864 que firmaste también terminan si falleces. Por lo tanto, si falleces, tu patrimonio no está obligado a hacerse responsable del sostenimiento de la persona después de tu muerte. Sin embargo, tu patrimonio puede deber cualquier apoyo que acumulaste antes de fallecer."),
    }.items():
        b.field(name, "paragraph", ("", ""), content=(en, es))
    b.field("c_read", "consent", ("Reading the contract", "Lectura del contrato"), ref="Part 8, Sponsor's Contract — customer acknowledgment only (not a form item)", note="Customer acknowledgment that the obligations were read; not a signature and not the certification under penalty of perjury.", req=True, content=(
        "I have read the obligations described in Part 8 of the form. I understand that I am not signing anything here, and that OG will tell me how the signature is handled.",
        "He leído las obligaciones descritas en la Parte 8 del formulario. Entiendo que aquí no firmo nada y que OG me dirá cómo se maneja la firma."))
    page(b, "c_cert", ("What you will be asked to certify and authorize", "Lo que se te pedirá certificar y autorizar"),
         ("This is the official declaration in Part 8, shown so you can read it now. You do not sign it here. The English is the official text as printed on the form.", "Esta es la declaración de la Parte 8, mostrada para que la leas ahora. No la firmas aquí. Abajo aparece una traducción de cortesía hecha por OG; no es un texto oficial de USCIS. El texto oficial es el del formulario en inglés y es el que prevalece."), group=C, ctx="sponsor")
    CC_ORDER = ["cc_1", "cc_4", "cc_1b", "cc_2", "cc_3", "cc_5", "cc_6"]
    for name, (en, es) in sorted({
        "cc_1": txt("Copies of any documents I have submitted are exact photocopies of unaltered, original documents, and I understand that USCIS or the U.S. Department of State (DOS) may require that I submit original documents to USCIS or DOS at a later date. Furthermore, I authorize the release of any information from any of my records that USCIS or DOS may need to determine my eligibility for the immigration benefit I seek.",
                    "Las copias de cualquier documento que he presentado son fotocopias exactas de documentos originales sin alterar, y entiendo que USCIS o el Departamento de Estado de EE. UU. (DOS) puede exigir que presente documentos originales a USCIS o al DOS en una fecha posterior. Además, autorizo la divulgación de cualquier información de cualquiera de mis registros que USCIS o el DOS puedan necesitar para determinar mi elegibilidad para el beneficio migratorio que busco."),
        "cc_1b": txt("I furthermore authorize release of information contained in this affidavit, in supporting documents, and in my USCIS or DOS records to other entities and persons where necessary for the administration and enforcement of U.S. immigration law.",
                     "Asimismo, autorizo la divulgación de la información contenida en este affidavit, en los documentos de respaldo y en mis registros de USCIS o del DOS a otras entidades y personas cuando sea necesario para la administración y aplicación de la ley de inmigración de EE. UU."),
        "cc_2": txt("I certify, under penalty of perjury, that all of the information in my affidavit and any document submitted with it were provided or authorized by me, that I reviewed and understand all of the information contained in, and submitted with, my affidavit, and that all of this information is complete, true, and correct.",
                    "Certifico, bajo pena de perjurio, que toda la información de mi affidavit y de cualquier documento presentado con él fue proporcionada o autorizada por mí, que revisé y entiendo toda la información contenida en mi affidavit y presentada con él, y que toda esta información es completa, verdadera y correcta."),
        "cc_3": txt("<strong>A.</strong> I know the contents of this affidavit of support that I signed; <strong>B.</strong> I have read and I understand each of the obligations described in Part 8., and I agree, freely and without any mental reservation or purpose of evasion, to accept each of those obligations in order to make it possible for the immigrant indicated in Part 3. to become a lawful permanent resident of the United States; <strong>C.</strong> I agree to submit to the personal jurisdiction of any Federal or state court that has subject matter jurisdiction of a lawsuit against me to enforce my obligations under this Form I-864EZ; <strong>D.</strong> Each of the Federal income tax returns submitted in support of this affidavit are true copies, or are unaltered tax transcripts, of the tax returns I filed with the IRS; <strong>E.</strong> I understand that, if I am related to the sponsored immigrant by marriage, the termination of the marriage (by divorce, dissolution, annulment, or other legal process) will not relieve me of my obligations under this Form I-864EZ; and <strong>F.</strong> I authorize the Social Security Administration to release information about me in its records to the USCIS and DOS.",
                    "<strong>A.</strong> Conozco el contenido de este affidavit de patrocinio que firmé; <strong>B.</strong> He leído y entiendo cada una de las obligaciones descritas en la Parte 8, y acepto, libremente y sin ninguna reserva mental ni propósito de evasión, cada una de esas obligaciones para hacer posible que el inmigrante indicado en la Parte 3 se convierta en residente permanente legal de los Estados Unidos; <strong>C.</strong> Acepto someterme a la jurisdicción personal de cualquier tribunal federal o estatal con jurisdicción sobre la materia de una demanda en mi contra para hacer cumplir mis obligaciones bajo este Formulario I-864EZ; <strong>D.</strong> Cada una de las declaraciones federales de impuestos presentadas en apoyo de este affidavit son copias fieles, o transcripciones sin alterar, de las declaraciones que presenté al IRS; <strong>E.</strong> Entiendo que, si estoy relacionado(a) con el inmigrante patrocinado por matrimonio, la terminación del matrimonio (por divorcio, disolución, anulación u otro proceso legal) no me liberará de mis obligaciones bajo este Formulario I-864EZ; y <strong>F.</strong> Autorizo a la Administración del Seguro Social a divulgar información sobre mí en sus registros a USCIS y al DOS."),
        "cc_4": txt("I authorize USCIS and DOS to request, and any consumer reporting agency to provide, information from one or more consumer reporting agencies in order to obtain or verify information, including credit reports and scores, in connection with the sufficiency determination of my Form I-864. I further authorize the disclosure of this information to the immigrant I am sponsoring for purposes of responding to any derogatory information pursuant to 8 C.F.R. 103.2(b)(16). Photocopies of this authorization bearing my handwritten signature are valid. This authorization shall remain in effect until the earliest of the following: (1) the application for visa, admission, or adjustment of status (s) of the beneficiary and accompanying derivative(s), if any, I have agreed to sponsor are approved; (2) the application(s) for visa, adjustment of status or admission are refused and the one-year period to overcome the refusal has lapsed pursuant to 22 CFR 42.81(e), provided that this authorization shall remain valid during any period in which an application is pending administrative processing; or (3) a properly submitted request to withdraw my Form I-864, been effectuated. I understand that a new authorization may be required if I wish to sponsor future individuals, including following-to-join derivative beneficiaries.",
                    "Autorizo a USCIS y al DOS a solicitar, y a cualquier agencia de informes del consumidor a proporcionar, información de una o más agencias de informes del consumidor para obtener o verificar información, incluidos informes y puntajes de crédito, en relación con la determinación de suficiencia de mi Formulario I-864. Además, autorizo la divulgación de esta información al inmigrante que patrocino con el fin de responder a cualquier información desfavorable conforme a 8 C.F.R. 103.2(b)(16). Las fotocopias de esta autorización con mi firma manuscrita son válidas. Esta autorización permanecerá vigente hasta lo primero que ocurra de lo siguiente: (1) que se aprueben las solicitudes de visa, admisión o ajuste de estatus del beneficiario y de los derivados que lo acompañen, si los hay, que acepté patrocinar; (2) que las solicitudes de visa, ajuste de estatus o admisión sean rechazadas y haya vencido el período de un año para superar el rechazo conforme a 22 CFR 42.81(e), siempre que esta autorización siga vigente durante cualquier período en que una solicitud esté pendiente de procesamiento administrativo; o (3) que se haya hecho efectiva una solicitud debidamente presentada para retirar mi Formulario I-864. Entiendo que puede requerirse una nueva autorización si deseo patrocinar a personas en el futuro, incluidos los beneficiarios derivados que siguen para unirse."),
        "cc_6": txt("<strong>NOTE TO ALL SPONSORS:</strong> If you do not completely fill out this affidavit or fail to submit required documents listed in the Instructions, USCIS or DOS may deny your request.",
                    "<strong>NOTA PARA TODOS LOS PATROCINADORES:</strong> Si no completas por completo este affidavit o no presentas los documentos requeridos que se enumeran en las Instrucciones, USCIS o el DOS pueden denegar tu solicitud."),
        "cc_5": txt("<strong>NOTE regarding consumer or credit report files:</strong> If you have a credit or security freeze on your consumer or credit report file, we may not be able to access the information necessary to assess the sufficiency of your Form I-864. To avoid any delays, you should expeditiously respond to any requests made to release the credit or security freeze.",
                    "<strong>NOTA sobre los archivos de informes del consumidor o de crédito:</strong> Si tienes un congelamiento de crédito o de seguridad en tu archivo de informe del consumidor o de crédito, es posible que no podamos acceder a la información necesaria para evaluar la suficiencia de tu Formulario I-864. Para evitar demoras, debes responder con prontitud a cualquier solicitud de levantar el congelamiento de crédito o de seguridad."),
    }.items(), key=lambda kv: CC_ORDER.index(kv[0])):
        b.field(name, "paragraph", ("", ""), content=(en, es))
    b.fields["cc_3"].source_note = "Reproduced as printed on edition 08/24/26, including its references to Form I-864EZ in items C and E."
    for fname, fld in b.fields.items():
        if fname.startswith(("c1_", "c2_", "c3_", "cc_")):
            fld.source_note = (COURTESY + " " + (fld.source_note or "")).strip()
    b.fields["c_read"].source_note = (b.fields["c_read"].source_note or "") + " " + COURTESY
    b.field("c_cert_ack", "consent", ("Reading the declaration", "Lectura de la declaración"), ref="Part 8 (Sponsor's Declaration and Certification) — customer acknowledgment only", note="Customer acknowledgment that the declaration was read; not a signature and not the certification.", req=True, content=(
        "I have read this declaration and authorization. I understand that I am not signing or certifying anything here, and that OG will explain how and when I sign.",
        "He leído esta declaración y autorización. Entiendo que aquí no firmo ni certifico nada y que OG me explicará cómo y cuándo firmo."))
    b.fields["c_cert_ack"].source_note = (b.fields["c_cert_ack"].source_note or "") + " " + COURTESY
    page(b, "c_lang", ("How you understood this form", "Cómo entendiste este formulario"), group="contact", ctx="sponsor")
    choice(b, "c_english_or_interpreter", ("Sponsor's statement regarding the interpreter — which is true for you?", "Declaración del patrocinador sobre el intérprete — ¿cuál es cierta para ti?"), "Part 8, Item 1.A / 1.B", [
        ("english", "I can read and understand English, and I have read and understand every question and instruction on this affidavit and my answer to every question.", "Puedo leer y entender inglés, y he leído y entendido cada pregunta e instrucción de este affidavit y mi respuesta a cada pregunta."),
        ("interpreter", "The interpreter named in Part 9 read to me every question and instruction on this affidavit and my answer to every question, in a language in which I am fluent, and I understood everything.", "El intérprete nombrado en la Parte 9 me leyó cada pregunta e instrucción de este affidavit y mi respuesta a cada pregunta, en un idioma en el que soy fluido(a), y lo entendí todo.")])
    page(b, "interp", ("Your interpreter", "Tu intérprete"), ("Information about the interpreter (Part 9 of the form).", "Información del intérprete (Parte 9 del formulario)."), group="contact", ctx="sponsor")
    b.field("int_family", "short_answer", ("Interpreter's family name (last name)", "Apellido del intérprete"), ref="Part 9, Item 1", req=True, width="half")
    b.field("int_given", "short_answer", ("Interpreter's given name (first name)", "Nombre del intérprete"), ref="Part 9, Item 1", req=True, width="half")
    b.field("int_org", "short_answer", ("Interpreter's business or organization name (if any)", "Empresa u organización del intérprete (si aplica)"), ref="Part 9, Item 2", maxlen=38)
    b.field("int_phone", "phone", ("Interpreter's daytime telephone number", "Teléfono de día del intérprete"), ref="Part 9, Item 3", req=True, width="half")
    b.field("int_mobile", "phone", ("Interpreter's mobile telephone number (if any)", "Teléfono móvil del intérprete (si tiene)"), ref="Part 9, Item 4", width="half")
    b.field("int_email", "email", ("Interpreter's email address (if any)", "Correo electrónico del intérprete (si tiene)"), ref="Part 9, Item 5")
    b.fields["int_email"].required = False
    b.field("int_language", "short_answer", ("Language the interpreter used", "Idioma que usó el intérprete"), ref="Part 8, Item 1.B (language) and Part 9, Interpreter's Certification (language)", req=True)
    for name, value in {"int_family": "@biz:INTERPRETER_LAST_NAME", "int_given": "@biz:INTERPRETER_FIRST_NAME", "int_org": "@biz:INTERPRETER_ORG", "int_phone": "@biz:INTERPRETER_PHONE", "int_email": "@biz:INTERPRETER_EMAIL"}.items():
        b.fields[name].default_value = value
    show_page_any(b, "interp", [[("c_english_or_interpreter", "equals", "interpreter")]])

    def edit_s_contact():
        b.field("s_phone", "phone", ("Sponsor's daytime telephone number", "Teléfono de día del patrocinador"), ref="Part 8, Item 3", req=True, width="half")
        b.field("s_mobile", "phone", ("Sponsor's mobile telephone number (if any)", "Teléfono móvil del patrocinador (si tiene)"), ref="Part 8, Item 4", width="half")
        b.field("s_email", "email", ("Sponsor's email address (if any)", "Correo electrónico del patrocinador (si tiene)"), ref="Part 8, Item 5")
        b.fields["s_email"].required = False
        mark_block_fields(b, "sb_s_contact", ["s_phone", "s_mobile", "s_email"])
    block_pair(b, "sb_s_contact", group="contact", ctx="sponsor", form_name="I-864",
               review_title=("We already have {sp}'s contact information", "Ya tenemos la información de contacto de {sp}"), review_desc=("Is it still current?", "¿Sigue vigente?"),
               edit_title=("The sponsor's contact information", "La información de contacto del patrocinador"), edit_desc=None, build_edit=edit_s_contact)
    page(b, "additional", ("Anything else?", "¿Algo más?"), group="contact", ctx="sponsor")
    b.field("additional_information", "long_answer", ("Is there anything else you want us to know?", "¿Hay algo más que quieras que sepamos?"), ref="Part 11. Additional Information", maxlen=3000,
            help=("If it relates to a specific question, say which one. OG places extra items (more than four family members, more than four people whose income you use, more tax years) in Part 11 for you — you never need a page, part or item number.", "Si se relaciona con una pregunta específica, dinos cuál. OG coloca los elementos extra (más de cuatro familiares, más de cuatro personas cuyo ingreso usas, más años fiscales) en la Parte 11 por ti; nunca necesitas un número de página, parte o ítem."))

    # ================================================================== documents
    page(b, "documents", ("Documents", "Documentos"), ("Documents are kept once in your case, so a document OG already has for this person is not asked for again.", "Los documentos se guardan una sola vez en tu caso, así que un documento que OG ya tiene de esta persona no se vuelve a pedir."), group="documents", ctx="sponsor")
    b.field("docs_scope_note", "paragraph", ("", ""), content=(
        _label("What OG asks for", "These are OG's requests to prepare and review your affidavit, plus the few documents the form itself says to attach. USCIS lists its required evidence in the Form I-864 Instructions; OG will confirm what applies to you."),
        _label("Lo que pide OG", "Son solicitudes de OG para preparar y revisar tu affidavit, más los pocos documentos que el propio formulario indica adjuntar. USCIS enumera su evidencia requerida en las Instrucciones del Formulario I-864; OG confirmará lo que aplica en tu caso.")))
    b.field("docs_list", "paragraph", ("", ""), content=("", ""))
    b.fields["docs_list"].config_json = json.dumps({"dynamic": {"kind": "documents"}})
    b.field("docs_tip", "paragraph", ("", ""), content=(
        _tip("Make sure each document is complete, readable, well lit and not cropped or blurry. Documents that are not in English may need a certified translation — OG can help."),
        _tip("Asegúrate de que cada documento esté completo, legible, bien iluminado y sin cortes ni desenfoque. Los documentos que no estén en inglés pueden necesitar una traducción certificada; OG puede ayudarte.")))

    _add_preparer_page(b)

    # ================================================================== confirm
    page(b, "confirm", ("Confirm and Send to OG", "Confirma y envía a OG"), group="confirm", ctx="sponsor",
         desc=("Review your information and confirm that it is complete and accurate. OG Multiservices will use the information you provided to assist with preparing your Form I-864 and related documents.",
               "Revisa tu información y confirma que esté completa y correcta. OG Multiservices utilizará la información proporcionada para ayudarte con la preparación de tu Formulario I-864 y los documentos relacionados."))
    note(b, "confirm_warning", "Sending this to OG does not file anything with USCIS, is not an electronic signature, is not the sponsor's contract or certification, and is not a decision about whether the sponsor qualifies or whether a joint sponsor is needed. OG will contact you about the next steps, including how signatures are handled.",
         "Enviar esto a OG no presenta nada ante USCIS, no es una firma electrónica, no es el contrato ni la certificación del patrocinador, y no es una decisión sobre si el patrocinador califica o si se necesita un patrocinador conjunto. OG te contactará sobre los siguientes pasos, incluido cómo se manejan las firmas.")
    b.field("preparer_request", "consent", ("Request for preparation", "Solicitud de preparación"), ref="Part 8, Item 2 (preparer prepared the affidavit at the sponsor's request)", note="Customer confirmation only; not a signature.", req=True, content=(
        "I ask OG Multiservices to assist with preparing this Form I-864 based only on the information I provided or authorized.",
        "Solicito a OG Multiservices que me ayude a preparar este Formulario I-864 con base únicamente en la información que proporcioné o autoricé."))
    b.field("confirm_accurate", "consent", ("Accuracy confirmation and authorization", "Confirmación de exactitud y autorización"), ref="Part 8 (certification wording)", note="Customer confirmation only; not a signature and not the certification under penalty of perjury.", req=True, content=(
        "I confirm that the information I provided is complete and correct to the best of my knowledge, and I authorize OG Multiservices to use it to assist with preparing Form I-864 and related documents.",
        "Confirmo que la información que proporcioné es completa y correcta según mi leal saber y entender, y autorizo a OG Multiservices a usarla para ayudarme a preparar el Formulario I-864 y los documentos relacionados."))
    return b


def _features():
    return {
        "completeness_check": True, "consistency": "i864", "documents_check": True,
        "sections": SECTIONS, "contexts": CONTEXTS, "context_roles": CONTEXT_ROLES,
        "name_tokens": {"sp": {"role": "sponsor", "fallback": {"en": "the sponsor", "es": "el patrocinador"}},
                        "pi": {"role": "principal_immigrant", "fallback": {"en": "the principal immigrant", "es": "el inmigrante principal"}}},
        "sync": [
            {"kind": "person_records", "fields": ["i_family", "h_people", "inc_people"]},
            {"kind": "current_address", "record_field": "__none__", "prefix": "sp", "when": {"field": "b_basis", "equals": "__never__"}},
            {"kind": "i864_calc"},
            {"kind": "requirements_i864"},
        ],
    }


def ensure_i864_intake():
    """Create the production I-864 intake and connect it to the Affidavit of Support service (idempotent; never rebuilt over submissions)."""
    if Form.query.filter_by(slug=I864_SLUG).first():
        return False
    category = ServiceCategory.query.filter_by(slug="immigration").first()
    if category is None:
        return False
    service = Service.query.filter_by(category_id=category.id, slug="affidavit-of-support").first()
    if service is None:
        top = db.session.query(db.func.max(Service.sort_order)).filter(Service.category_id == category.id).scalar() or 0
        service = Service(
            category_id=category.id, slug="affidavit-of-support", admin_name="Affidavit of Support (Form I-864) Preparation", icon="immigration",
            is_published=True, sort_order=top + 10,
            title_en="Affidavit of Support (Form I-864) Preparation", title_es="Preparación de Declaración Jurada de Patrocinio (Formulario I-864)",
            short_en="Document preparation support for the Form I-864 Affidavit of Support that accompanies many family-based green card cases.",
            short_es="Apoyo en la preparación de documentos para el Formulario I-864, la Declaración Jurada de Patrocinio que acompaña muchos casos de residencia por familia.",
            hero_text_en="Support organizing the sponsor's information, household, income, tax and asset details, and supporting documents for Form I-864.",
            hero_text_es="Apoyo organizando la información del patrocinador, el hogar, los ingresos, impuestos, activos y los documentos de respaldo del Formulario I-864.",
            content_title_en="What is Form I-864?", content_title_es="¿Qué es el Formulario I-864?",
            content_en="<p>Form I-864, Affidavit of Support Under Section 213A of the INA, is the form in which a sponsor promises financial support to an immigrant. It is used with many family-based green card cases. OG Multiservices helps you gather and organize the information and documents so the form can be prepared. OG provides document preparation and administrative assistance only; we are not a law firm and do not provide legal advice.</p>",
            content_es="<p>El Formulario I-864, Declaración Jurada de Patrocinio bajo la Sección 213A de la INA, es el formulario en el que un patrocinador promete apoyo económico a un inmigrante. Se usa en muchos casos de residencia por familia. OG Multiservices te ayuda a reunir y organizar la información y los documentos para que el formulario pueda prepararse. OG ofrece solo preparación de documentos y asistencia administrativa; no somos un bufete de abogados ni brindamos asesoría legal.</p>",
            nj_in_person=True, remote_nationwide=True)
        db.session.add(service)
        db.session.flush()
    form = Form(slug=I864_SLUG, name_admin="I-864 Client Intake")
    db.session.add(form)
    form.form_type = "service_intake"
    form.status = "published"
    form.source_form_name = SOURCE_NAME
    form.source_edition = SOURCE_EDITION
    form.version = 1
    form.published_at = datetime.utcnow()
    form.title_en, form.title_es = "Affidavit of Support — Form I-864", "Declaración Jurada de Patrocinio — Formulario I-864"
    form.description_en = "Guided intake for OG Multiservices to prepare your Form I-864. Your progress is saved automatically."
    form.description_es = "Solicitud guiada para que OG Multiservices prepare tu Formulario I-864. Tu progreso se guarda automáticamente."
    form.submit_label_en, form.submit_label_es = "Send to OG", "Enviar a OG"
    form.success_message_en = "OG Multiservices has your information and will review it. We'll contact you if we need anything else."
    form.success_message_es = "OG Multiservices tiene tu información y la revisará. Te contactaremos si necesitamos algo más."
    form.show_progress = True
    form.features_json = json.dumps(_features(), ensure_ascii=False)
    db.session.flush()
    build_i864(form)
    service.requires_intake = True
    service.form_id = form.id
    service.requires_account = True
    service.intake_label = "I-864 Client Intake"
    db.session.commit()
    return True


COURTESY = "OFFICIAL TEXT = the English as printed on Form I-864 edition 08/24/26. The Spanish is OG's courtesy translation only (not USCIS text); the English prevails."
_NOT_OFFICIAL_ES = "Abajo aparece una traducción de cortesía hecha por OG; no es un texto oficial de USCIS. El texto oficial es el del formulario en inglés y es el que prevalece."
_SHORT_ES = "El texto oficial es el del formulario en inglés; el español es una traducción de cortesía de OG, no un texto oficial de USCIS."
_SHORT_EN = "The English is the official text as printed on the form; the Spanish is OG's courtesy translation."


def ensure_i864_refinements():
    """In-place upgrade of an ALREADY deployed I-864 intake (drafts and answers are never edited):
    * adds the Part 10 preparer page (information only) before the confirmation step;
    * labels the Spanish contract / certification text as OG's courtesy translation (page text + internal source notes).
    Idempotent."""
    from app.models import FormPage, FormSubmission
    from app.seed_i90 import Builder

    form = Form.query.filter_by(slug=I864_SLUG).first()
    if form is None:
        return False
    changed = False
    fields = {f.internal_name: f for f in form.all_fields}
    if "prep_family" not in fields and "preparer_request" in fields:
        pages = sorted(form.pages, key=lambda p: p.sort_order)
        confirm = next(p for p in pages if any(f.internal_name == "preparer_request" for f in p.fields))
        at = pages.index(confirm)
        b = Builder(form)
        b.page_order = max(p.sort_order for p in pages) + 1
        _add_preparer_page(b)
        new = b.pages["preparer"]
        for p in pages[at:]:
            p.sort_order += 1
        new.sort_order = confirm.sort_order - 1
        db.session.flush()
        for sub in FormSubmission.query.filter_by(form_id=form.id).all():  # a saved position after the insertion point moves with its page
            if (sub.current_page or 1) > at:
                sub.current_page += 1
        form.version = (form.version or 1) + 1
        changed = True
    fields = {f.internal_name: f for f in form.all_fields}
    for name, f in fields.items():
        if name.startswith(("c1_", "c2_", "c3_", "cc_")) or name in ("c_read", "c_cert_ack"):
            if "courtesy translation" not in (f.source_note or "").lower():
                f.source_note = (COURTESY + " " + (f.source_note or "")).strip()
                changed = True
    by_title = {p.title_en: p for p in form.pages}
    for title, marker in (("The sponsor's contract — what signing requires", _SHORT_ES), ("The sponsor's contract — if obligations are not fulfilled, and when they end", _SHORT_ES)):
        p = by_title.get(title)
        if p is not None and not p.description_es:
            p.description_en, p.description_es = _SHORT_EN, marker
            changed = True
    for title in ("The sponsor's contract — what signing means", "What you will be asked to certify and authorize"):
        p = by_title.get(title)
        if p is not None and "no es un texto oficial de USCIS" not in (p.description_es or ""):
            if title.startswith("The sponsor's"):
                p.description_en = "Part 8 of the form describes the obligations of a sponsor. Read it carefully. This is the official English text as printed on the form."
                p.description_es = "La Parte 8 del formulario describe las obligaciones de un patrocinador. Léela con cuidado. " + _NOT_OFFICIAL_ES
            else:
                p.description_en = "This is the official declaration in Part 8, shown so you can read it now. You do not sign it here. The English is the official text as printed on the form."
                p.description_es = "Esta es la declaración de la Parte 8, mostrada para que la leas ahora. No la firmas aquí. " + _NOT_OFFICIAL_ES
            changed = True
    if changed:
        db.session.commit()
    return changed
