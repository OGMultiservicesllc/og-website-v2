"""Form I-130 Client Intake — the third production Smart Intake.

SOURCE OF TRUTH: the supplied USCIS "Form I-130, Petition for Alien Relative",
Edition 04/01/24 (OMB No. 1615-0012, expires 02/28/2027), 12 pages. Every question
carries the Part/Item it maps to in `FormField.source_ref` (admin-only). Where the
printed layout does not make the exact sub-letter of an item certain (for example the
address blocks), the reference cites the item and its range, e.g. "Part 2, Items 10.a–10.i".

Part map (as printed):
  Part 1   Relationship (petitioner -> beneficiary)             -> relationship steps
  Part 2   Information About You (Petitioner)                   -> PETITIONER steps
             items 1-9 identity/birth, 10-11 mailing address, 12-15 address history,
             16-23 marital history, 24-35 parents, 36-41 citizenship / LPR, 42-49 employment
  Part 3   Biographic Information (petitioner)
  Part 4   Information About Beneficiary                        -> BENEFICIARY steps
             items 1-10 identity, 11-13 addresses, 14-16 contact, 17-24 marital,
             25-44 family, 45-50 entry / documents, 51-52 employment, 53-56 proceedings,
             57-58 native-script name/address, 59-60 spouses' last shared address,
             61-62 where the beneficiary will apply
  Part 5   Other Information (previous petitions, other relatives being petitioned)
  Part 6   Petitioner's Statement, Contact Information, Declaration, Signature
  Part 7   Interpreter                                          -> interpreter steps
  Part 8   Preparer (OG) — completed by OG, not asked of the customer
  Part 9   Additional Information

Not customer questions on purpose: every signature and date (Part 6 item 6, Part 7 item 7,
Part 8 item 8), Part 8 (OG prepares), the attorney/G-28 box and every "For USCIS Use Only" box.

Form I-130A is a separate form and is NOT built here.

OG does not decide the customer's processing route (Part 4 items 61-62), eligibility or
relationship category: it collects the facts the form asks for and flags anything unsure
for OG review.

The document checklist is OG's request for preparing the case. The USCIS Instructions (which
list the required evidence) are not part of the supplied PDF, so nothing here claims that USCIS
requires a particular document.
"""

import json
from datetime import datetime

from app.extensions import db
from app.i130_data import CLASS_OF_ADMISSION
from app.models import Form, Service, ServiceCategory
from app.seed_i90 import EYE, HAIR, STATE_OPTIONS, YES_NO, Builder, _address_fields  # noqa: F401
from app.seed_i90_refine import _label, _tip
from app.seed_n400 import _cfg, intro, note, show_any, show_page_any, yesno

I130_SLUG = "i-130-client-intake"
SOURCE_NAME = "I-130"
SOURCE_EDITION = "04/01/24"

SECTIONS = [
    {"key": "relationship", "title": {"en": "Relationship", "es": "Relación"}},
    {"key": "petitioner", "title": {"en": "Petitioner Information", "es": "Información del peticionario"}},
    {"key": "pet_address", "title": {"en": "Petitioner Address History", "es": "Historial de direcciones del peticionario"}},
    {"key": "pet_employment", "title": {"en": "Petitioner Employment History", "es": "Historial de empleo del peticionario"}},
    {"key": "pet_family", "title": {"en": "Petitioner Marriage & Family", "es": "Matrimonio y familia del peticionario"}},
    {"key": "beneficiary", "title": {"en": "Beneficiary Information", "es": "Información del beneficiario"}},
    {"key": "ben_address", "title": {"en": "Beneficiary Address & Contact", "es": "Dirección y contacto del beneficiario"}},
    {"key": "ben_family", "title": {"en": "Beneficiary Marriage & Family", "es": "Matrimonio y familia del beneficiario"}},
    {"key": "ben_immigration", "title": {"en": "Immigration Information", "es": "Información migratoria"}},
    {"key": "other_info", "title": {"en": "Other Information", "es": "Otra información"}},
    {"key": "contact", "title": {"en": "Contact & Interpreter", "es": "Contacto e intérprete"}},
    {"key": "documents", "title": {"en": "Documents", "es": "Documentos"}},
    {"key": "confirm", "title": {"en": "Confirmation", "es": "Confirmación"}},
]

CONTEXTS = {
    "relationship": {"title": {"en": "Relationship", "es": "Relación"},
                     "subtitle": {"en": "Who you are petitioning for.", "es": "Por quién estás presentando la petición."}, "tone": "slate", "icon": "link"},
    "petitioner": {"title": {"en": "Petitioner", "es": "Peticionario"},
                   "subtitle": {"en": "You — the person filing this petition.", "es": "Tú: la persona que presenta esta petición."}, "tone": "accent", "icon": "person"},
    "beneficiary": {"title": {"en": "Beneficiary", "es": "Beneficiario"},
                    "subtitle": {"en": "Your family member — the person you are petitioning for.", "es": "Tu familiar: la persona por quien estás presentando la petición."}, "tone": "brand", "icon": "people"},
}
CONTEXT_NAMES = {"petitioner": ["pet_given", "pet_family"], "beneficiary": ["ben_given", "ben_family"]}

REVIEW_NOTE = ("This answer may require additional review by OG Multiservices.", "Esta respuesta puede requerir revisión adicional por OG Multiservices.")
STATUSES = [("single", "Single, Never Married", "Soltero(a), nunca casado(a)"), ("married", "Married", "Casado(a)"), ("divorced", "Divorced", "Divorciado(a)"),
            ("widowed", "Widowed", "Viudo(a)"), ("separated", "Separated", "Separado(a)"), ("annulled", "Annulled", "Matrimonio anulado")]


def page(b, key, title, desc=None, group=None, ctx=None):
    p = b.new_page(key, title, desc)
    p.group_key = group
    p.context_key = ctx
    return p


def where(b, name, en, es):
    f = b.fields[name]
    f.help_where_en, f.help_where_es = en, es


def records(b, name, label, ref, record, *, req=False, help=None, **cfg):
    f = b.field(name, "record_list", label, ref=ref, req=req, help=help)
    f.config_json = _cfg(record=record, **cfg)
    return f


def _check_icon():
    return ('<svg class="w-5 h-5 shrink-0 text-emerald-600" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" aria-hidden="true">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>')


def transition(en_title, es_title, en_sub, es_sub, en_next, es_next, en_role, es_role, en_desc, es_desc):
    def block(done, sub, nxt, role, desc):
        return (f'<div class="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 flex items-center gap-2.5 text-[15px] font-semibold text-emerald-800">{_check_icon()}<span>{done}</span></div>'
                f'<p class="mt-4 text-sm text-slate-500">{sub}</p><p class="mt-0.5 text-xl font-extrabold tracking-tight text-brand-800">{nxt}</p>'
                f'<p class="mt-4 text-xs font-bold uppercase tracking-wider text-brand-700">{role}</p><p class="mt-0.5 text-[15px] text-slate-600">{desc}</p>')
    return (block(en_title, en_sub, en_next, en_role, en_desc), block(es_title, es_sub, es_next, es_role, es_desc))


WHERE_A = ("Your A-Number (Alien Registration Number) is 7 to 9 digits and usually starts with “A”. It may appear on a Green Card, a work permit (EAD) or other USCIS documents, where it can be labelled “A-Number”, “Alien Registration Number” or “USCIS #”, and on USCIS notices. If the person has none, leave it blank.",
           "El Número A (Número de Registro de Extranjero) tiene de 7 a 9 dígitos y normalmente empieza con “A”. Puede aparecer en una Green Card, un permiso de trabajo (EAD) u otros documentos de USCIS, donde puede llamarse “A-Number”, “Alien Registration Number” o “USCIS #”, y en las notificaciones de USCIS. Si la persona no tiene, déjalo en blanco.")
WHERE_ACCT = ("If you or your family member has a USCIS online account, the number appears in that account and on some USCIS notices. Leave it blank if there is no account.",
              "Si tú o tu familiar tienen una cuenta en línea de USCIS, el número aparece en esa cuenta y en algunas notificaciones de USCIS. Déjalo en blanco si no hay cuenta.")
WHERE_SSN = ("A Social Security number has 9 digits. It is on a Social Security card. Leave it blank if the person does not have one.",
             "Un número de Seguro Social tiene 9 dígitos. Aparece en la tarjeta del Seguro Social. Déjalo en blanco si la persona no tiene.")
WHERE_I94 = ("The Form I-94 Arrival/Departure Record number identifies a person's admission to the United States. It is on the I-94 record: many people can get their electronic I-94 from U.S. Customs and Border Protection's official I-94 website, or it may be on a paper I-94 card stapled in the passport.",
             "El número del Formulario I-94 (Registro de Llegada/Salida) identifica la admisión de una persona a los Estados Unidos. Aparece en el registro I-94: muchas personas pueden obtener su I-94 electrónico en el sitio web oficial de I-94 de la Oficina de Aduanas y Protección Fronteriza (CBP), o puede estar en una tarjeta I-94 de papel grapada al pasaporte.")
WHERE_CLASS = ("The class of admission is the visa category or status under which the person was admitted, for example B-2 (visitor). It is usually shown on the I-94 record and on the visa in the passport.",
               "La clase de admisión es la categoría de visa o estatus con el que la persona fue admitida, por ejemplo B-2 (visitante). Normalmente aparece en el registro I-94 y en la visa del pasaporte.")
WHERE_PASSPORT = ("The passport number is on the passport's photo page. A travel document number is on a document that is used instead of a passport (for example a refugee travel document).",
                  "El número de pasaporte está en la página con la foto del pasaporte. El número de documento de viaje está en un documento que se usa en lugar del pasaporte (por ejemplo, un documento de viaje de refugiado).")
WHERE_CERT = ("The certificate number is printed on the Certificate of Naturalization or Certificate of Citizenship, along with the place and date it was issued.",
              "El número del certificado está impreso en el Certificado de Naturalización o de Ciudadanía, junto con el lugar y la fecha en que se emitió.")
WHERE_LPR = ("On a Green Card, the “Category” (class of admission) and “Resident Since” (date of admission) are printed on the card.",
             "En una Green Card, la “Category” (clase de admisión) y “Resident Since” (fecha de admisión) están impresas en la tarjeta.")

WARNING_EN = ("WARNING: USCIS investigates the claimed relationships and verifies the validity of documents you submit. If you falsify a family relationship to obtain a visa, USCIS may seek to have you criminally prosecuted.")
WARNING_ES = ("ADVERTENCIA (traducción de cortesía; el texto oficial está en inglés): USCIS investiga las relaciones familiares declaradas y verifica la validez de los documentos que presentas. Si falseas una relación familiar para obtener una visa, USCIS puede buscar que se te procese penalmente.")


def build_i130(form):
    b = Builder(form)

    # ================================================================== intro
    page(b, "intro", ("Before you start", "Antes de empezar"))
    b.field("intro_1", "paragraph", ("", ""), content=(
        "This intake collects what OG Multiservices needs to prepare your Form I-130, Petition for Alien Relative (USCIS edition 04/01/24). Your answers save automatically, so you can stop and come back anytime.",
        "Este formulario reúne lo que OG Multiservices necesita para preparar tu Formulario I-130, Petición para Familiar Extranjero (edición USCIS 04/01/24). Tus respuestas se guardan automáticamente, así que puedes parar y volver cuando quieras."))
    b.field("intro_2", "paragraph", ("", ""), content=(
        "<strong>Two people</strong> appear in this petition. The <strong>petitioner</strong> is the person filing it (you). The <strong>beneficiary</strong> is the family member you are petitioning for. A label at the top of every step tells you whose information you are giving.",
        "En esta petición aparecen <strong>dos personas</strong>. El <strong>peticionario</strong> es la persona que la presenta (tú). El <strong>beneficiario</strong> es el familiar por quien presentas la petición. Una etiqueta en la parte superior de cada paso te indica de quién es la información que estás dando."))
    b.field("intro_3", "paragraph", ("", ""), content=(
        "OG Multiservices provides document preparation and administrative assistance. We are not a law firm and do not provide legal advice or representation, and we cannot tell you whether a petition will qualify or which processing route to use. Sending this to OG does not file anything with USCIS.",
        "OG Multiservices ofrece preparación de documentos y asistencia administrativa. No somos un bufete de abogados, no brindamos asesoría ni representación legal, y no podemos decirte si una petición calificará ni qué vía de trámite usar. Enviar esto a OG no presenta nada ante USCIS."))

    # ================================================================== Part 1
    page(b, "relationship", ("Who are you petitioning for?", "¿Por quién estás presentando la petición?"), group="relationship", ctx="relationship")
    b.field("relationship_type", "single_choice", ("I am filing this petition for my…", "Estoy presentando esta petición para mi…"), ref="Part 1, Item 1", req=True,
            help=("Select only one.", "Selecciona solo una."),
            opts=[("spouse", "Spouse", "Cónyuge"), ("parent", "Parent", "Padre o madre"), ("child", "Child", "Hijo(a)"), ("sibling", "Brother or Sister", "Hermano(a)")])

    page(b, "rel_basis", ("About this relationship", "Sobre esta relación"), group="relationship", ctx="relationship")
    b.field("relationship_basis", "single_choice", ("Which of these describes your relationship?", "¿Cuál de estas describe tu relación?"), ref="Part 1, Item 2", req=True,
            help=("The form asks this when you are filing for your child or your parent. Select only one.", "El formulario pregunta esto cuando presentas la petición para tu hijo(a) o para tu padre o madre. Selecciona solo una."),
            opts=[("born_in_wedlock", "Child was born to parents who were married to each other at the time of the child's birth", "El hijo(a) nació de padres que estaban casados entre sí al momento del nacimiento"),
                  ("born_out_of_wedlock", "Child was born to parents who were not married to each other at the time of the child's birth", "El hijo(a) nació de padres que no estaban casados entre sí al momento del nacimiento"),
                  ("stepchild", "Stepchild/Stepparent", "Hijastro(a) / padrastro o madrastra"),
                  ("adopted", "Child was adopted (not an Orphan or Hague Convention adoptee)", "El hijo(a) fue adoptado(a) (no es huérfano ni adoptado bajo el Convenio de La Haya)")])
    note(b, "rel_review_note", REVIEW_NOTE[0], REVIEW_NOTE[1])
    show_any(b, "rel_review_note", [[("relationship_basis", "equals", "stepchild")], [("relationship_basis", "equals", "adopted")]])
    show_page_any(b, "rel_basis", [[("relationship_type", "equals", "child")], [("relationship_type", "equals", "parent")]])

    page(b, "rel_adoption", ("Adoption", "Adopción"), group="relationship", ctx="relationship")
    b.field("sibling_adopted", "single_choice", ("If the beneficiary is your brother or sister, are you related by adoption?", "Si el beneficiario es tu hermano(a), ¿están relacionados por adopción?"), ref="Part 1, Item 3", req=True, opts=YES_NO)
    b.field("pet_adopted_status", "single_choice", ("Did you gain lawful permanent resident status or citizenship through adoption?", "¿Obtuviste la residencia permanente legal o la ciudadanía por medio de una adopción?"), ref="Part 1, Item 4", req=True, opts=YES_NO)
    b.rule("show_field", "sibling_adopted", [("relationship_type", "equals", "sibling")])
    note(b, "adopt_review_note", REVIEW_NOTE[0], REVIEW_NOTE[1])
    show_any(b, "adopt_review_note", [[("sibling_adopted", "equals", "yes")], [("pet_adopted_status", "equals", "yes")]])

    # ================================================================== PETITIONER — Part 2
    page(b, "pet_name", ("Your legal name", "Tu nombre legal"), ("You are the petitioner: the person filing this petition.", "Tú eres el peticionario: la persona que presenta esta petición."), group="petitioner", ctx="petitioner")
    b.field("pet_family", "short_answer", ("Family name (last name)", "Apellido"), ref="Part 2, Item 4.a", req=True, width="half")
    b.field("pet_given", "short_answer", ("Given name (first name)", "Nombre(s)"), ref="Part 2, Item 4.b", req=True, width="half")
    b.field("pet_middle", "short_answer", ("Middle name (if applicable)", "Segundo nombre (si aplica)"), ref="Part 2, Item 4.c", width="half")

    page(b, "pet_other_names", ("Other names you have used", "Otros nombres que has usado"), group="petitioner", ctx="petitioner")
    records(b, "pet_other_names", ("Other names you have ever used", "Otros nombres que has usado alguna vez"), "Part 2, Item 5", "other_name", max=10,
            help=("Include all other names you have ever used, including aliases, maiden name and nicknames. If none, just continue.", "Incluye todos los demás nombres que hayas usado alguna vez, incluidos alias, apellido de soltera y apodos. Si no tienes, solo continúa."))

    page(b, "pet_ids", ("Your identification numbers", "Tus números de identificación"), group="petitioner", ctx="petitioner")
    b.field("pet_a_number", "short_answer", ("Alien Registration Number (A-Number), if any", "Número de Registro de Extranjero (Número A), si tienes"), ref="Part 2, Item 1", sensitive=True, pattern=r"A?-?\d{7,9}", maxlen=12,
            msg=("Enter 7 to 9 digits, with or without “A-”.", "Ingresa 7 a 9 dígitos, con o sin “A-”."))
    where(b, "pet_a_number", *WHERE_A)
    b.field("pet_uscis_account", "short_answer", ("USCIS Online Account Number, if any", "Número de cuenta en línea de USCIS, si tienes"), ref="Part 2, Item 2", maxlen=12, pattern=r"\d{1,12}", msg=("Use digits only (up to 12).", "Usa solo dígitos (hasta 12)."))
    where(b, "pet_uscis_account", *WHERE_ACCT)
    b.field("pet_ssn", "short_answer", ("U.S. Social Security Number, if any", "Número de Seguro Social de EE. UU., si tienes"), ref="Part 2, Item 3", sensitive=True, pattern=r"\d{3}-?\d{2}-?\d{4}", msg=("Enter 9 digits.", "Ingresa 9 dígitos."))
    where(b, "pet_ssn", *WHERE_SSN)

    page(b, "pet_birth", ("Where and when you were born", "Dónde y cuándo naciste"), group="petitioner", ctx="petitioner")
    b.field("pet_birth_city", "short_answer", ("City, town or village of birth", "Ciudad, pueblo o aldea de nacimiento"), ref="Part 2, Item 6", req=True, width="half")
    b.field("pet_birth_country", "short_answer", ("Country of birth", "País de nacimiento"), ref="Part 2, Item 7", req=True, width="half")
    b.field("pet_dob", "date", ("Date of birth", "Fecha de nacimiento"), ref="Part 2, Item 8", req=True, date_rule="past", width="half")
    b.field("pet_sex", "single_choice", ("Sex", "Sexo"), ref="Part 2, Item 9", req=True, opts=[("male", "Male", "Masculino"), ("female", "Female", "Femenino")])

    page(b, "pet_mailing", ("Your mailing address", "Tu dirección postal"), ("Where should USCIS mail things to you?", "¿A dónde deben enviarte el correo?"), group="pet_address", ctx="petitioner")
    b.field("pet_mail_in_care_of", "short_answer", ("In care of name (if any)", "A cargo de (si aplica)"), ref="Part 2, Items 10.a–10.i", maxlen=34)
    _address_fields(b, "pet_mail", "Part 2, Items 10.a–10.i")
    page(b, "pet_mail_gate", ("Where you live", "Dónde vives"), group="pet_address", ctx="petitioner")
    b.field("pet_mail_same", "single_choice", ("Is your current mailing address the same as your physical address?", "¿Tu dirección postal actual es la misma que tu dirección física?"), ref="Part 2, Item 11", req=True, opts=YES_NO)

    page(b, "pet_addresses", ("Where you have lived", "Dónde has vivido"),
         ("Start with where you live now, then add each previous address until the last five years are covered — inside or outside the United States.", "Empieza con donde vives ahora y agrega cada dirección anterior hasta cubrir los últimos cinco años, dentro o fuera de los Estados Unidos."),
         group="pet_address", ctx="petitioner")
    records(b, "pet_address_history", ("Physical addresses for the last five years", "Direcciones físicas de los últimos cinco años"), "Part 2, Items 12.a–15.b", "address", req=True, max=20,
            timeline={"years": 5, "gap_days": 3, "overlap_days": 31},
            default_from={"prefix": "pet_mail", "when": {"field": "pet_mail_same", "equals": "yes"}, "present": True},
            intro={"en": "If your mailing address is also where you live, we start you off with it — just add the date you began living there.",
                   "es": "Si tu dirección postal es también donde vives, empezamos con ella: solo agrega la fecha en que empezaste a vivir ahí."})

    page(b, "pet_marital", ("Your marital history", "Tu historial matrimonial"), group="pet_family", ctx="petitioner")
    b.field("pet_times_married", "number", ("How many times have you been married?", "¿Cuántas veces te has casado?"), ref="Part 2, Item 16", req=True, minv=0, maxv=99, width="half")
    b.field("pet_marital_status", "single_choice", ("What is your current marital status?", "¿Cuál es tu estado civil actual?"), ref="Part 2, Item 17", req=True, opts=STATUSES)
    page(b, "pet_marriage", ("Your current marriage", "Tu matrimonio actual"), group="pet_family", ctx="petitioner")
    b.field("pet_marriage_date", "date", ("Date of your current marriage", "Fecha de tu matrimonio actual"), ref="Part 2, Item 18", req=True, date_rule="past", width="half")
    b.field("pet_marriage_city", "short_answer", ("City or town where you married", "Ciudad o pueblo donde te casaste"), ref="Part 2, Item 19.a", req=True, maxlen=20, width="half")
    b.field("pet_marriage_state", "dropdown", ("State (if in the U.S.)", "Estado (si fue en EE. UU.)"), ref="Part 2, Item 19.b", opts=STATE_OPTIONS, width="half")
    b.field("pet_marriage_province", "short_answer", ("Province (if outside the U.S.)", "Provincia (si fue fuera de EE. UU.)"), ref="Part 2, Item 19.c", maxlen=20, width="half")
    b.field("pet_marriage_country", "short_answer", ("Country", "País"), ref="Part 2, Item 19.d", req=True)
    b.rule("show_page", "pet_marriage", [("pet_marital_status", "equals", "married")])
    page(b, "pet_spouses", ("Your spouses", "Tus cónyuges"), group="pet_family", ctx="petitioner")
    records(b, "pet_spouses", ("Your current spouse and any prior spouses", "Tu cónyuge actual y tus cónyuges anteriores"), "Part 2, Items 20.a–23", "spouse", req=True, max=12,
            help=("List your current spouse first (if married), then each prior spouse and the date each marriage ended.", "Anota primero a tu cónyuge actual (si estás casado(a)) y luego a cada cónyuge anterior con la fecha en que terminó cada matrimonio."))
    b.rule("show_page", "pet_spouses", [("pet_times_married", "greater_than", "0")])
    note(b, "spouse_note", "If you are petitioning for your spouse, OG will review whether additional spouse information or a separate document is needed.",
         "Si presentas la petición para tu cónyuge, OG revisará si se necesita información o un documento adicional sobre el cónyuge.")
    b.rule("show_field", "spouse_note", [("relationship_type", "equals", "spouse")])

    page(b, "pet_parents", ("Your parents", "Tus padres"), group="pet_family", ctx="petitioner")
    records(b, "pet_parents", ("Information about your parents", "Información sobre tus padres"), "Part 2, Items 24.a–35", "parent", max=2,
            help=("Add each parent you have information about. If you don't know something, leave it blank.", "Agrega a cada padre o madre de quien tengas información. Si no sabes algo, déjalo en blanco."))

    page(b, "pet_citizen", ("Your U.S. status", "Tu estatus en EE. UU."), group="petitioner", ctx="petitioner")
    b.field("pet_status", "single_choice", ("I am a…", "Soy…"), ref="Part 2, Item 36", req=True, help=("Select only one.", "Selecciona solo una."),
            opts=[("us_citizen", "U.S. Citizen", "Ciudadano(a) de EE. UU."), ("lpr", "Lawful Permanent Resident", "Residente Permanente Legal")])
    b.field("pet_citizenship_via", "single_choice", ("My citizenship was acquired through…", "Mi ciudadanía se adquirió por…"), ref="Part 2, Item 37", req=True, help=("Select only one.", "Selecciona solo una."),
            opts=[("birth_us", "Birth in the United States", "Nacimiento en los Estados Unidos"), ("naturalization", "Naturalization", "Naturalización"), ("parents", "Parents", "Padres")])
    b.field("pet_has_certificate", "single_choice", ("Have you obtained a Certificate of Naturalization or a Certificate of Citizenship?", "¿Has obtenido un Certificado de Naturalización o un Certificado de Ciudadanía?"), ref="Part 2, Item 38", req=True, opts=YES_NO)
    b.field("pet_cert_number", "short_answer", ("Certificate number", "Número del certificado"), ref="Part 2, Item 39.a", req=True, width="half")
    where(b, "pet_cert_number", *WHERE_CERT)
    b.field("pet_cert_place", "short_answer", ("Place of issuance", "Lugar de emisión"), ref="Part 2, Item 39.b", req=True, width="half")
    b.field("pet_cert_date", "date", ("Date of issuance", "Fecha de emisión"), ref="Part 2, Item 39.c", req=True, date_rule="past", width="half")
    for n in ("pet_citizenship_via", "pet_has_certificate"):
        b.rule("show_field", n, [("pet_status", "equals", "us_citizen")])
    for n in ("pet_cert_number", "pet_cert_place", "pet_cert_date"):
        b.rule("show_field", n, [("pet_status", "equals", "us_citizen"), ("pet_has_certificate", "equals", "yes")], "all")

    page(b, "pet_lpr", ("Your permanent residence", "Tu residencia permanente"), group="petitioner", ctx="petitioner")
    b.field("pet_lpr_class", "short_answer", ("Class of admission", "Clase de admisión"), ref="Part 2, Item 40.a", req=True, width="half")
    where(b, "pet_lpr_class", *WHERE_LPR)
    b.field("pet_lpr_date", "date", ("Date of admission", "Fecha de admisión"), ref="Part 2, Item 40.b", req=True, date_rule="past", width="half")
    b.field("pet_lpr_city", "short_answer", ("City or town of admission", "Ciudad o pueblo de admisión"), ref="Part 2, Item 40.c", req=True, width="half")
    b.field("pet_lpr_state", "dropdown", ("State of admission", "Estado de admisión"), ref="Part 2, Item 40.d", req=True, opts=STATE_OPTIONS, width="half")
    b.field("pet_lpr_marriage", "single_choice", ("Did you gain lawful permanent resident status through marriage to a U.S. citizen or lawful permanent resident?", "¿Obtuviste la residencia permanente legal por matrimonio con un ciudadano de EE. UU. o residente permanente legal?"), ref="Part 2, Item 41", req=True, opts=YES_NO)
    b.rule("show_page", "pet_lpr", [("pet_status", "equals", "lpr")])

    page(b, "pet_employment", ("Where you have worked", "Dónde has trabajado"),
         ("Start with your current employment, then go back through the last five years — inside or outside the United States.", "Empieza con tu empleo actual y ve hacia atrás durante los últimos cinco años, dentro o fuera de los Estados Unidos."),
         group="pet_employment", ctx="petitioner")
    records(b, "pet_employment_history", ("Your employment for the last five years", "Tu empleo durante los últimos cinco años"), "Part 2, Items 42–49.b", "employment", req=True, max=15,
            timeline={"years": 5, "gap_days": 3, "overlap_days": 31}, types=["employed", "self_employed", "unemployed"],
            help=("The form asks for employers only. If you were self-employed or not working, pick that option and we'll record it for you. If you were retired or a student, choose Unemployed and tell us in the last step.",
                  "El formulario pide solo empleadores. Si trabajaste por cuenta propia o no trabajabas, elige esa opción y lo anotaremos por ti. Si estabas jubilado(a) o estudiando, elige Desempleado(a) y cuéntanoslo en el último paso."))

    page(b, "pet_bio1", ("Ethnicity and race", "Etnia y raza"), ("Biographic information about you, the petitioner.", "Información biográfica sobre ti, el peticionario."), group="petitioner", ctx="petitioner")
    b.field("pet_ethnicity", "single_choice", ("Ethnicity", "Etnia"), ref="Part 3, Item 1", req=True, help=("Select only one.", "Selecciona solo una."),
            opts=[("hispanic", "Hispanic or Latino", "Hispano o Latino"), ("not_hispanic", "Not Hispanic or Latino", "No hispano ni latino")])
    b.field("pet_race", "multi_choice", ("Race", "Raza"), ref="Part 3, Item 2", req=True, help=("Select all that apply.", "Selecciona todas las que apliquen."),
            opts=[("white", "White", "Blanca"), ("asian", "Asian", "Asiática"), ("black", "Black or African American", "Negra o afroamericana"),
                  ("american_indian", "American Indian or Alaska Native", "Indígena americana o nativa de Alaska"), ("pacific_islander", "Native Hawaiian or Other Pacific Islander", "Nativa de Hawái u otra isla del Pacífico")])
    page(b, "pet_bio2", ("Your physical description", "Tu descripción física"), group="petitioner", ctx="petitioner")
    b.field("pet_height_feet", "dropdown", ("Height — feet", "Estatura — pies"), ref="Part 3, Item 3", req=True, width="half", opts=[(str(n), str(n), str(n)) for n in range(2, 9)])
    b.field("pet_height_inches", "dropdown", ("Height — inches", "Estatura — pulgadas"), ref="Part 3, Item 3", req=True, width="half", opts=[(str(n), str(n), str(n)) for n in range(0, 12)])
    b.field("pet_weight", "number", ("Weight (pounds)", "Peso (libras)"), ref="Part 3, Item 4", req=True, minv=1, maxv=999, width="half")
    b.field("pet_eye", "dropdown", ("Eye color", "Color de ojos"), ref="Part 3, Item 5", req=True, opts=EYE, width="half")
    b.field("pet_hair", "dropdown", ("Hair color", "Color de cabello"), ref="Part 3, Item 6", req=True, opts=HAIR, width="half")

    # ================================================================== transition
    tr_en, tr_es = transition("Petitioner information complete", "Información del peticionario completa", "Next:", "Ahora:",
                              "Tell us about your family member", "Cuéntanos sobre tu familiar", "BENEFICIARY", "BENEFICIARIO",
                              "The person you are petitioning for.", "La persona por quien estás presentando esta petición.")
    page(b, "ben_intro", ("Now, your family member", "Ahora, tu familiar"), group="beneficiary", ctx="beneficiary")
    b.field("ben_intro_block", "paragraph", ("", ""), content=(tr_en, tr_es))

    # ================================================================== BENEFICIARY — Part 4
    page(b, "ben_name", ("Your family member's name", "El nombre de tu familiar"), ("The beneficiary's legal name.", "El nombre legal del beneficiario."), group="beneficiary", ctx="beneficiary")
    b.field("ben_family", "short_answer", ("Family name (last name)", "Apellido"), ref="Part 4, Item 4.a", req=True, width="half")
    b.field("ben_given", "short_answer", ("Given name (first name)", "Nombre(s)"), ref="Part 4, Item 4.b", req=True, width="half")
    b.field("ben_middle", "short_answer", ("Middle name (if applicable)", "Segundo nombre (si aplica)"), ref="Part 4, Item 4.c", width="half")
    page(b, "ben_other_names", ("Other names your family member has used", "Otros nombres que ha usado tu familiar"), group="beneficiary", ctx="beneficiary")
    records(b, "ben_other_names", ("Other names the beneficiary has ever used", "Otros nombres que el beneficiario ha usado alguna vez"), "Part 4, Item 5", "other_name", max=10,
            help=("Include aliases, maiden name and nicknames. If none, just continue.", "Incluye alias, apellido de soltera y apodos. Si no tiene, solo continúa."))
    page(b, "ben_ids", ("Identification numbers", "Números de identificación"), group="beneficiary", ctx="beneficiary")
    b.field("ben_a_number", "short_answer", ("Alien Registration Number (A-Number), if any", "Número de Registro de Extranjero (Número A), si tiene"), ref="Part 4, Item 1", sensitive=True, pattern=r"A?-?\d{7,9}", maxlen=12,
            msg=("Enter 7 to 9 digits, with or without “A-”.", "Ingresa 7 a 9 dígitos, con o sin “A-”."))
    where(b, "ben_a_number", *WHERE_A)
    b.field("ben_uscis_account", "short_answer", ("USCIS Online Account Number, if any", "Número de cuenta en línea de USCIS, si tiene"), ref="Part 4, Item 2", maxlen=12, pattern=r"\d{1,12}", msg=("Use digits only (up to 12).", "Usa solo dígitos (hasta 12)."))
    where(b, "ben_uscis_account", *WHERE_ACCT)
    b.field("ben_ssn", "short_answer", ("U.S. Social Security Number, if any", "Número de Seguro Social de EE. UU., si tiene"), ref="Part 4, Item 3", sensitive=True, pattern=r"\d{3}-?\d{2}-?\d{4}", msg=("Enter 9 digits.", "Ingresa 9 dígitos."))
    where(b, "ben_ssn", *WHERE_SSN)
    page(b, "ben_birth", ("Where and when they were born", "Dónde y cuándo nació"), group="beneficiary", ctx="beneficiary")
    b.field("ben_birth_city", "short_answer", ("City, town or village of birth", "Ciudad, pueblo o aldea de nacimiento"), ref="Part 4, Item 6", req=True, maxlen=38, width="half")
    b.field("ben_birth_country", "short_answer", ("Country of birth", "País de nacimiento"), ref="Part 4, Item 7", req=True, width="half")
    b.field("ben_dob", "date", ("Date of birth", "Fecha de nacimiento"), ref="Part 4, Item 8", req=True, date_rule="past", width="half")
    b.field("ben_sex", "single_choice", ("Sex", "Sexo"), ref="Part 4, Item 9", req=True, opts=[("male", "Male", "Masculino"), ("female", "Female", "Femenino")])
    page(b, "ben_prior_petition", ("Other petitions for them", "Otras peticiones para esta persona"), group="beneficiary", ctx="beneficiary")
    b.field("ben_petition_filed", "single_choice", ("Has anyone else ever filed a petition for the beneficiary?", "¿Alguien más ha presentado alguna vez una petición para el beneficiario?"), ref="Part 4, Item 10", req=True,
            opts=[("yes", "Yes", "Sí"), ("no", "No", "No"), ("unknown", "Unknown", "No sé")],
            detail=("USCIS note on the form: select “Unknown” only if you do not know, and the beneficiary also does not know, if anyone else has ever filed a petition for the beneficiary.",
                    "Nota de USCIS en el formulario: selecciona “No sé” solo si tú no sabes, y el beneficiario tampoco sabe, si alguien más ha presentado alguna vez una petición para el beneficiario."))

    page(b, "ben_physical", ("Where your family member lives", "Dónde vive tu familiar"), ("The beneficiary's physical address.", "La dirección física del beneficiario."), group="ben_address", ctx="beneficiary")
    _address_fields(b, "ben_phys", "Part 4, Items 11.a–11.h")
    b.fields["ben_phys_street"].required = False
    b.fields["ben_phys_street"].help_text_en = "Leave the street blank if the beneficiary lives outside the United States in a home without a street number or name."
    b.fields["ben_phys_street"].help_text_es = "Deja la calle en blanco si el beneficiario vive fuera de los Estados Unidos en una vivienda sin número ni nombre de calle."

    page(b, "ben_us_address", ("Where they intend to live in the U.S.", "Dónde piensa vivir en EE. UU."), group="ben_address", ctx="beneficiary")
    b.field("ben_us_same", "single_choice", ("Is the address in the United States where the beneficiary intends to live the same as the address above?", "¿La dirección en los Estados Unidos donde el beneficiario piensa vivir es la misma que la dirección de arriba?"), ref="Part 4, Item 12.a (“SAME”)", req=True,
            opts=[("same", "Yes, it is the same (“SAME”)", "Sí, es la misma (“SAME”)"), ("different", "No, it is a different U.S. address", "No, es una dirección diferente en EE. UU."), ("not_sure", "Not sure? Save this for OG review.", "¿No estás seguro? Déjalo para revisión de OG.")])
    b.field("ben_us_street", "short_answer", ("Street number and name", "Número y nombre de la calle"), ref="Part 4, Items 12.a–12.e", req=True, maxlen=34)
    b.field("ben_us_unit_type", "dropdown", ("Unit type (if any)", "Tipo de unidad (si aplica)"), ref="Part 4, Item 12.b", opts=[("apt", "Apt.", "Apto."), ("ste", "Ste.", "Ste."), ("flr", "Flr.", "Piso")], width="half")
    b.field("ben_us_unit_number", "short_answer", ("Unit number", "Número de unidad"), ref="Part 4, Item 12.b", maxlen=6, width="half")
    b.field("ben_us_city", "short_answer", ("City or town", "Ciudad o pueblo"), ref="Part 4, Item 12.c", req=True, maxlen=20)
    b.field("ben_us_state", "dropdown", ("State", "Estado"), ref="Part 4, Item 12.d", req=True, opts=STATE_OPTIONS, width="half")
    b.field("ben_us_zip", "short_answer", ("ZIP code", "Código postal (ZIP)"), ref="Part 4, Item 12.e", req=True, maxlen=5, pattern=r"\d{5}", width="half", msg=("Enter a 5-digit ZIP code.", "Ingresa un ZIP de 5 dígitos."))
    for n in ("ben_us_street", "ben_us_unit_type", "ben_us_unit_number", "ben_us_city", "ben_us_state", "ben_us_zip"):
        b.rule("show_field", n, [("ben_us_same", "equals", "different")])

    page(b, "ben_outside", ("Their address outside the U.S.", "Su dirección fuera de EE. UU."), group="ben_address", ctx="beneficiary")
    b.field("ben_out_same", "single_choice", ("Is the beneficiary's address outside the United States the same as the physical address above?", "¿La dirección del beneficiario fuera de los Estados Unidos es la misma que la dirección física de arriba?"), ref="Part 4, Item 13.a (“SAME”)", req=True, opts=YES_NO)
    b.field("ben_out_street", "short_answer", ("Street number and name", "Número y nombre de la calle"), ref="Part 4, Items 13.a–13.f", req=True, maxlen=34)
    b.field("ben_out_unit_type", "dropdown", ("Unit type (if any)", "Tipo de unidad (si aplica)"), ref="Part 4, Item 13.b", opts=[("apt", "Apt.", "Apto."), ("ste", "Ste.", "Ste."), ("flr", "Flr.", "Piso")], width="half")
    b.field("ben_out_unit_number", "short_answer", ("Unit number", "Número de unidad"), ref="Part 4, Item 13.b", maxlen=6, width="half")
    b.field("ben_out_city", "short_answer", ("City or town", "Ciudad o pueblo"), ref="Part 4, Item 13.c", req=True, maxlen=20)
    b.field("ben_out_province", "short_answer", ("Province", "Provincia"), ref="Part 4, Item 13.d", maxlen=20, width="half")
    b.field("ben_out_postal", "short_answer", ("Postal code", "Código postal"), ref="Part 4, Item 13.e", maxlen=9, width="half")
    b.field("ben_out_country", "short_answer", ("Country", "País"), ref="Part 4, Item 13.f", req=True)
    for n in ("ben_out_street", "ben_out_unit_type", "ben_out_unit_number", "ben_out_city", "ben_out_province", "ben_out_postal", "ben_out_country"):
        b.rule("show_field", n, [("ben_out_same", "equals", "no")])

    page(b, "ben_contact", ("How to reach your family member", "Cómo contactar a tu familiar"), group="ben_address", ctx="beneficiary")
    b.field("ben_phone", "phone", ("Daytime telephone number (if any)", "Teléfono de día (si tiene)"), ref="Part 4, Item 14", width="half")
    b.field("ben_mobile", "phone", ("Mobile telephone number (if any)", "Teléfono móvil (si tiene)"), ref="Part 4, Item 15", width="half")
    b.field("ben_email", "email", ("Email address (if any)", "Correo electrónico (si tiene)"), ref="Part 4, Item 16")
    b.fields["ben_email"].required = False

    page(b, "ben_marital", ("Their marital history", "Su historial matrimonial"), group="ben_family", ctx="beneficiary")
    b.field("ben_times_married", "number", ("How many times has the beneficiary been married?", "¿Cuántas veces se ha casado el beneficiario?"), ref="Part 4, Item 17", req=True, minv=0, maxv=99, width="half")
    b.field("ben_marital_status", "single_choice", ("What is the beneficiary's current marital status?", "¿Cuál es el estado civil actual del beneficiario?"), ref="Part 4, Item 18", req=True, opts=STATUSES)
    page(b, "ben_marriage", ("Their current marriage", "Su matrimonio actual"), group="ben_family", ctx="beneficiary")
    b.field("ben_marriage_date", "date", ("Date of the beneficiary's current marriage", "Fecha del matrimonio actual del beneficiario"), ref="Part 4, Item 19", req=True, date_rule="past", width="half")
    b.field("ben_marriage_city", "short_answer", ("City or town where they married", "Ciudad o pueblo donde se casaron"), ref="Part 4, Item 20.a", req=True, maxlen=20, width="half")
    b.field("ben_marriage_state", "dropdown", ("State (if in the U.S.)", "Estado (si fue en EE. UU.)"), ref="Part 4, Item 20.b", opts=STATE_OPTIONS, width="half")
    b.field("ben_marriage_province", "short_answer", ("Province (if outside the U.S.)", "Provincia (si fue fuera de EE. UU.)"), ref="Part 4, Item 20.c", maxlen=20, width="half")
    b.field("ben_marriage_country", "short_answer", ("Country", "País"), ref="Part 4, Item 20.d", req=True)
    b.rule("show_page", "ben_marriage", [("ben_marital_status", "equals", "married")])
    page(b, "ben_spouses", ("Their spouses", "Sus cónyuges"), group="ben_family", ctx="beneficiary")
    records(b, "ben_spouses", ("The beneficiary's current spouse and any prior spouses", "El cónyuge actual del beneficiario y sus cónyuges anteriores"), "Part 4, Items 21.a–24", "spouse", req=True, max=12,
            help=("List the current spouse first (if married), then each prior spouse and the date each marriage ended.", "Anota primero al cónyuge actual (si está casado(a)) y luego a cada cónyuge anterior con la fecha en que terminó cada matrimonio."))
    b.rule("show_page", "ben_spouses", [("ben_times_married", "greater_than", "0")])
    page(b, "ben_family", ("Their spouse and children", "Su cónyuge e hijos"), group="ben_family", ctx="beneficiary")
    records(b, "ben_family_members", ("The beneficiary's spouse and children", "El cónyuge e hijos del beneficiario"), "Part 4, Items 25.a–44", "relative", max=25,
            help=("Add the beneficiary's spouse and each child, one at a time. There is no fixed number.", "Agrega al cónyuge del beneficiario y a cada hijo(a), uno por uno. No hay un número fijo."))

    page(b, "ben_us_ever", ("Has your family member been in the U.S.?", "¿Tu familiar ha estado en EE. UU.?"), group="ben_immigration", ctx="beneficiary")
    b.field("ben_ever_in_us", "single_choice", ("Was the beneficiary EVER in the United States?", "¿El beneficiario ha estado ALGUNA VEZ en los Estados Unidos?"), ref="Part 4, Item 45", req=True, opts=YES_NO)
    b.field("ben_in_us_now", "single_choice", ("Is the beneficiary in the United States now?", "¿El beneficiario está actualmente en los Estados Unidos?"), ref="OG helper (Part 4, Items 46.a–46.d apply if currently in the U.S.)", req=True, opts=YES_NO,
            help=("The form asks for the current-stay details only if the beneficiary is currently in the United States.", "El formulario pide los datos de la estadía actual solo si el beneficiario está actualmente en los Estados Unidos."))
    b.rule("show_field", "ben_in_us_now", [("ben_ever_in_us", "equals", "yes")])

    page(b, "ben_us_current", ("Their current stay in the U.S.", "Su estadía actual en EE. UU."), group="ben_immigration", ctx="beneficiary")
    b.field("ben_class_admission", "dropdown", ("He or she arrived as a (class of admission)", "Llegó como (clase de admisión)"), ref="Part 4, Item 46.a", req=True, opts=[(c, l, l) for c, l in CLASS_OF_ADMISSION])
    where(b, "ben_class_admission", *WHERE_CLASS)
    b.field("ben_i94", "short_answer", ("Form I-94 Arrival-Departure Record number", "Número del Registro de Llegada/Salida (Formulario I-94)"), ref="Part 4, Item 46.b", maxlen=11, pattern=r"[A-Za-z0-9]{1,11}",
            msg=("Use letters and numbers only (up to 11).", "Usa solo letras y números (hasta 11)."), help=("If the beneficiary doesn't have it handy, leave it blank and OG will follow up.", "Si el beneficiario no lo tiene a la mano, déjalo en blanco y OG dará seguimiento."))
    where(b, "ben_i94", *WHERE_I94)
    b.field("ben_arrival_date", "date", ("Date of arrival", "Fecha de llegada"), ref="Part 4, Item 46.c", req=True, date_rule="past", width="half")
    b.field("ben_stay_type", "single_choice", ("Date the authorized stay expired, or will expire, as shown on Form I-94 or I-95", "Fecha en que venció, o vencerá, la estadía autorizada según el Formulario I-94 o I-95"), ref="Part 4, Item 46.d", req=True,
            opts=[("date", "A specific date", "Una fecha específica"), ("ds", "“D/S” — Duration of Status", "“D/S” — Duración del estatus")])
    b.field("ben_stay_date", "date", ("Authorized stay expiration date", "Fecha de vencimiento de la estadía autorizada"), ref="Part 4, Item 46.d", req=True, width="half")
    b.rule("show_field", "ben_stay_date", [("ben_stay_type", "equals", "date")])
    show_page_any(b, "ben_us_current", [[("ben_ever_in_us", "equals", "yes"), ("ben_in_us_now", "equals", "yes")]])

    page(b, "ben_passport", ("Passport or travel document", "Pasaporte o documento de viaje"), group="ben_immigration", ctx="beneficiary")
    b.field("ben_passport_number", "short_answer", ("Passport number", "Número de pasaporte"), ref="Part 4, Item 47", maxlen=30, width="half")
    where(b, "ben_passport_number", *WHERE_PASSPORT)
    b.field("ben_travel_doc", "short_answer", ("Travel document number", "Número de documento de viaje"), ref="Part 4, Item 48", width="half")
    b.field("ben_doc_country", "short_answer", ("Country of issuance for the passport or travel document", "País de emisión del pasaporte o documento de viaje"), ref="Part 4, Item 49", width="half")
    b.field("ben_doc_expiry", "date", ("Expiration date of the passport or travel document", "Fecha de vencimiento del pasaporte o documento de viaje"), ref="Part 4, Item 50", width="half")

    page(b, "ben_employment", ("Their current work", "Su trabajo actual"), group="ben_immigration", ctx="beneficiary")
    b.field("ben_employed", "single_choice", ("Is the beneficiary currently employed (inside or outside the U.S.)?", "¿El beneficiario tiene empleo actualmente (dentro o fuera de EE. UU.)?"), ref="Part 4, Item 51.a", req=True, opts=YES_NO,
            help=("If not, OG will record “Unemployed” as the form asks.", "Si no, OG anotará “Unemployed” como pide el formulario."))
    b.field("ben_emp_name", "short_answer", ("Name of current employer", "Nombre del empleador actual"), ref="Part 4, Item 51.a", req=True, maxlen=38)
    _address_fields(b, "ben_emp", "Part 4, Items 51.b–51.i")
    b.field("ben_emp_start", "date", ("Date employment began", "Fecha en que empezó el empleo"), ref="Part 4, Item 52", req=True, date_rule="past", width="half")
    for n in ("ben_emp_name", "ben_emp_is_us", "ben_emp_street", "ben_emp_unit_type", "ben_emp_unit_number", "ben_emp_city", "ben_emp_start"):
        b.rule("show_field", n, [("ben_employed", "equals", "yes")])
    for n in ("ben_emp_state", "ben_emp_zip"):
        b.rule("show_field", n, [("ben_employed", "equals", "yes"), ("ben_emp_is_us", "equals", "yes")], "all")
    for n in ("ben_emp_province", "ben_emp_postal_code", "ben_emp_country"):
        b.rule("show_field", n, [("ben_employed", "equals", "yes"), ("ben_emp_is_us", "equals", "no")], "all")

    page(b, "ben_proceedings", ("Immigration proceedings", "Procesos migratorios"), group="ben_immigration", ctx="beneficiary")
    b.field("ben_proceedings", "single_choice", ("Was the beneficiary EVER in immigration proceedings?", "¿El beneficiario ha estado ALGUNA VEZ en procesos migratorios?"), ref="Part 4, Item 53", req=True, opts=YES_NO)
    b.field("ben_proc_type", "single_choice", ("Type of proceedings", "Tipo de proceso"), ref="Part 4, Item 54", req=True,
            opts=[("removal", "Removal", "Remoción"), ("exclusion_deportation", "Exclusion/Deportation", "Exclusión / Deportación"), ("rescission", "Rescission", "Rescisión"), ("other_judicial", "Other Judicial Proceedings", "Otros procesos judiciales")])
    b.field("ben_proc_city", "short_answer", ("City or town of the proceedings", "Ciudad o pueblo del proceso"), ref="Part 4, Item 55.a", req=True, maxlen=20, width="half")
    b.field("ben_proc_state", "dropdown", ("State", "Estado"), ref="Part 4, Item 55.b", req=True, opts=STATE_OPTIONS, width="half")
    b.field("ben_proc_date", "date", ("Date of the proceedings", "Fecha del proceso"), ref="Part 4, Item 56", req=True, date_rule="past", width="half")
    for n in ("ben_proc_type", "ben_proc_city", "ben_proc_state", "ben_proc_date"):
        b.rule("show_field", n, [("ben_proceedings", "equals", "yes")])
    note(b, "proc_review_note", REVIEW_NOTE[0], REVIEW_NOTE[1])
    b.rule("show_field", "proc_review_note", [("ben_proceedings", "equals", "yes")])

    page(b, "ben_native", ("Name and address in their own alphabet", "Nombre y dirección en su propio alfabeto"), group="ben_immigration", ctx="beneficiary")
    b.field("ben_native_needed", "single_choice", ("Does the beneficiary's native written language use letters other than Roman (English) letters?", "¿El idioma escrito nativo del beneficiario usa letras distintas de las romanas (del inglés)?"), ref="OG helper (Part 4, Items 57–58)", req=True, opts=YES_NO,
            help=("If yes, the form asks for their name and foreign address written in that language.", "Si es así, el formulario pide su nombre y su dirección en el extranjero escritos en ese idioma."))
    b.field("ben_native_family", "short_answer", ("Family name (in their native language)", "Apellido (en su idioma nativo)"), ref="Part 4, Item 57.a", req=True, width="half")
    b.field("ben_native_given", "short_answer", ("Given name (in their native language)", "Nombre (en su idioma nativo)"), ref="Part 4, Item 57.b", req=True, width="half")
    b.field("ben_native_middle", "short_answer", ("Middle name (in their native language)", "Segundo nombre (en su idioma nativo)"), ref="Part 4, Item 57.c", width="half")
    b.field("ben_native_street", "short_answer", ("Street number and name (native language)", "Número y nombre de la calle (idioma nativo)"), ref="Part 4, Items 58.a–58.f", req=True, maxlen=34)
    b.field("ben_native_unit", "short_answer", ("Apt./Ste./Flr. and number", "Apto./Ste./Piso y número"), ref="Part 4, Item 58.b", maxlen=12, width="half")
    b.field("ben_native_city", "short_answer", ("City or town (native language)", "Ciudad o pueblo (idioma nativo)"), ref="Part 4, Item 58.c", req=True, maxlen=20, width="half")
    b.field("ben_native_province", "short_answer", ("Province (native language)", "Provincia (idioma nativo)"), ref="Part 4, Item 58.d", maxlen=20, width="half")
    b.field("ben_native_postal", "short_answer", ("Postal code", "Código postal"), ref="Part 4, Item 58.e", maxlen=9, width="half")
    b.field("ben_native_country", "short_answer", ("Country (native language)", "País (idioma nativo)"), ref="Part 4, Item 58.f", req=True)
    for n in ("ben_native_family", "ben_native_given", "ben_native_middle", "ben_native_street", "ben_native_unit", "ben_native_city", "ben_native_province", "ben_native_postal", "ben_native_country"):
        b.rule("show_field", n, [("ben_native_needed", "equals", "yes")])

    page(b, "ben_together", ("The last address you lived together", "La última dirección en la que vivieron juntos"), ("The form asks this when you are filing for your spouse.", "El formulario pregunta esto cuando presentas la petición para tu cónyuge."), group="ben_family", ctx="beneficiary")
    b.field("ben_lived_together", "single_choice", ("Have you and the beneficiary ever lived together?", "¿Tú y el beneficiario han vivido juntos alguna vez?"), ref="Part 4, Item 59.a (“Never lived together”)", req=True, opts=YES_NO)
    _address_fields(b, "tog", "Part 4, Items 59.a–59.h")
    b.field("tog_from", "date", ("Date you began living at this address", "Fecha en que empezaron a vivir en esta dirección"), ref="Part 4, Item 60.a", req=True, date_rule="past", width="half")
    b.field("tog_to", "date", ("Date you stopped living at this address", "Fecha en que dejaron de vivir en esta dirección"), ref="Part 4, Item 60.b", req=True, date_rule="past", width="half")
    for n in ("tog_is_us", "tog_street", "tog_unit_type", "tog_unit_number", "tog_city", "tog_from", "tog_to"):
        b.rule("show_field", n, [("ben_lived_together", "equals", "yes")])
    for n in ("tog_state", "tog_zip"):
        b.rule("show_field", n, [("ben_lived_together", "equals", "yes"), ("tog_is_us", "equals", "yes")], "all")
    for n in ("tog_province", "tog_postal_code", "tog_country"):
        b.rule("show_field", n, [("ben_lived_together", "equals", "yes"), ("tog_is_us", "equals", "no")], "all")
    b.rule("show_page", "ben_together", [("relationship_type", "equals", "spouse")])

    page(b, "processing", ("Where the beneficiary will apply", "Dónde solicitará el beneficiario"),
         ("The form asks where the beneficiary will apply. OG does not choose this for you.", "El formulario pregunta dónde solicitará el beneficiario. OG no lo elige por ti."), group="ben_immigration", ctx="beneficiary")
    b.field("processing_choice", "single_choice", ("Which of these applies?", "¿Cuál de estas aplica?"), ref="Part 4, Items 61–62", req=True,
            opts=[("adjustment_in_us", "The beneficiary is in the United States and will apply for adjustment of status at a USCIS office", "El beneficiario está en los Estados Unidos y solicitará el ajuste de estatus en una oficina de USCIS"),
                  ("consular_abroad", "The beneficiary will not apply for adjustment of status in the U.S., but will apply for an immigrant visa abroad at a U.S. Embassy or Consulate", "El beneficiario no solicitará el ajuste de estatus en EE. UU., sino que solicitará una visa de inmigrante en el extranjero en una Embajada o Consulado de EE. UU."),
                  ("not_sure", "Not sure? Save this for OG review.", "¿No estás seguro? Déjalo para revisión de OG.")],
            detail=("USCIS note on the form: choosing a U.S. Embassy or U.S. Consulate outside the country of the beneficiary's last residence does not guarantee that it will accept the beneficiary's case for processing. In these situations, the designated Embassy or Consulate has discretion over whether or not to accept the case.",
                    "Nota de USCIS en el formulario: elegir una Embajada o Consulado de EE. UU. fuera del país de la última residencia del beneficiario no garantiza que acepte el caso para su trámite. En estas situaciones, la Embajada o Consulado designado tiene discreción para aceptar o no el caso."))
    b.field("adj_city", "short_answer", ("USCIS office — city or town", "Oficina de USCIS: ciudad o pueblo"), ref="Part 4, Item 61.a", req=True, maxlen=20, width="half")
    b.field("adj_state", "dropdown", ("State", "Estado"), ref="Part 4, Item 61.b", req=True, opts=STATE_OPTIONS, width="half")
    b.field("cons_city", "short_answer", ("U.S. Embassy or Consulate — city or town", "Embajada o Consulado de EE. UU.: ciudad o pueblo"), ref="Part 4, Item 62.a", req=True, maxlen=20, width="half")
    b.field("cons_province", "short_answer", ("Province", "Provincia"), ref="Part 4, Item 62.b", maxlen=20, width="half")
    b.field("cons_country", "short_answer", ("Country", "País"), ref="Part 4, Item 62.c", req=True)
    for n in ("adj_city", "adj_state"):
        b.rule("show_field", n, [("processing_choice", "equals", "adjustment_in_us")])
    for n in ("cons_city", "cons_province", "cons_country"):
        b.rule("show_field", n, [("processing_choice", "equals", "consular_abroad")])
    note(b, "processing_note", "Saved for OG review — we'll go over this with you.", "Guardado para revisión de OG: lo revisaremos contigo.")
    b.rule("show_field", "processing_note", [("processing_choice", "equals", "not_sure")])

    # ================================================================== Part 5 (petitioner again)
    page(b, "prior_petitions", ("Petitions you have filed before", "Peticiones que has presentado antes"), group="other_info", ctx="petitioner")
    b.field("pet_prior_filed", "single_choice", ("Have you EVER previously filed a petition for this beneficiary or any other alien?", "¿Has presentado ALGUNA VEZ antes una petición para este beneficiario o para cualquier otro extranjero?"), ref="Part 5, Item 1", req=True, opts=YES_NO)
    records(b, "prior_petitions", ("Your previous petitions", "Tus peticiones anteriores"), "Part 5, Items 2.a–5", "prior_petition", req=True, max=15,
            help=("For each one: the name of the person it was for, where and when it was filed, and the result.", "Para cada una: el nombre de la persona para quien fue, dónde y cuándo se presentó, y el resultado."))
    b.rule("show_field", "prior_petitions", [("pet_prior_filed", "equals", "yes")])
    page(b, "other_petitions", ("Other relatives you are petitioning for", "Otros familiares por quienes presentas peticiones"), group="other_info", ctx="petitioner")
    b.field("other_petitions_now", "single_choice", ("Are you also submitting separate petitions for other relatives?", "¿También estás presentando peticiones separadas para otros familiares?"), ref="OG helper (Part 5, Items 6.a–9)", req=True, opts=YES_NO,
            help=("If yes, the form asks for each relative's name and your relationship.", "Si es así, el formulario pide el nombre de cada familiar y tu relación con él o ella."))
    records(b, "other_relatives", ("The other relatives", "Los otros familiares"), "Part 5, Items 6.a–9", "other_relative", req=True, max=10)
    b.rule("show_field", "other_relatives", [("other_petitions_now", "equals", "yes")])

    # ================================================================== Part 6 / 7
    page(b, "pet_contact", ("Your contact information", "Tu información de contacto"), group="contact", ctx="petitioner")
    b.field("pet_phone", "phone", ("Daytime telephone number", "Teléfono de día"), ref="Part 6, Item 3", req=True, width="half")
    b.field("pet_mobile", "phone", ("Mobile telephone number (if any)", "Teléfono móvil (si tienes)"), ref="Part 6, Item 4", width="half")
    b.field("pet_email", "email", ("Email address (if any)", "Correo electrónico (si tienes)"), ref="Part 6, Item 5")
    b.fields["pet_email"].required = False
    page(b, "language", ("Language", "Idioma"), group="contact", ctx="petitioner")
    b.field("english_or_interpreter", "single_choice", ("Which of these is true for you?", "¿Cuál de estas opciones es cierta para ti?"), ref="Part 6, Items 1.a / 1.b", req=True,
            opts=[("english", "I can read and understand English, and I have read and understand every question and instruction on this petition and my answer to every question.", "Puedo leer y entender inglés, y he leído y entendido cada pregunta e instrucción de esta petición y mi respuesta a cada pregunta."),
                  ("interpreter", "An interpreter read to me every question and instruction on this petition and my answer to every question in a language in which I am fluent, and I understood all of this information as interpreted.", "Un intérprete me leyó cada pregunta e instrucción de esta petición y mi respuesta a cada pregunta en un idioma en el que soy fluido(a), y entendí toda esta información tal como fue interpretada.")])
    page(b, "interp", ("Your interpreter", "Tu intérprete"), ("Information about the interpreter (Part 7 of the form).", "Información del intérprete (Parte 7 del formulario)."), group="contact", ctx="petitioner")
    b.field("int_family", "short_answer", ("Interpreter's family name (last name)", "Apellido del intérprete"), ref="Part 7, Item 1.a", req=True, width="half")
    b.field("int_given", "short_answer", ("Interpreter's given name (first name)", "Nombre del intérprete"), ref="Part 7, Item 1.b", req=True, width="half")
    b.field("int_org", "short_answer", ("Interpreter's business or organization name (if any)", "Empresa u organización del intérprete (si aplica)"), ref="Part 7, Item 2", maxlen=38)
    b.field("int_phone", "phone", ("Interpreter's daytime telephone number", "Teléfono de día del intérprete"), ref="Part 7, Item 4", req=True, width="half")
    b.field("int_mobile", "phone", ("Interpreter's mobile telephone number (if any)", "Teléfono móvil del intérprete (si tiene)"), ref="Part 7, Item 5", width="half")
    b.field("int_email", "email", ("Interpreter's email address (if any)", "Correo electrónico del intérprete (si tiene)"), ref="Part 7, Item 6")
    b.fields["int_email"].required = False
    b.field("int_language", "short_answer", ("Language the interpreter used", "Idioma que usó el intérprete"), ref="Part 6, Item 1.b (language)", req=True)
    page(b, "interp_addr", ("Interpreter's mailing address", "Dirección postal del intérprete"), group="contact", ctx="petitioner")
    _address_fields(b, "int", "Part 7, Items 3.a–3.h")
    for name, value in {"int_family": "@biz:INTERPRETER_LAST_NAME", "int_given": "@biz:INTERPRETER_FIRST_NAME", "int_org": "@biz:INTERPRETER_ORG", "int_phone": "@biz:INTERPRETER_PHONE",
                        "int_email": "@biz:INTERPRETER_EMAIL", "int_is_us": "yes", "int_street": "@biz:OFFICE_STREET", "int_unit_type": "@biz:OFFICE_UNIT_TYPE",
                        "int_unit_number": "@biz:OFFICE_UNIT_NUMBER", "int_city": "@biz:OFFICE_CITY", "int_state": "@biz:OFFICE_STATE", "int_zip": "@biz:OFFICE_ZIP"}.items():
        b.fields[name].default_value = value
    b.rule("show_page", "interp", [("english_or_interpreter", "equals", "interpreter")])
    b.rule("show_page", "interp_addr", [("english_or_interpreter", "equals", "interpreter")])

    page(b, "additional", ("Anything else?", "¿Algo más?"), group="other_info", ctx="petitioner")
    b.field("additional_information", "long_answer", ("Is there anything else you want us to know?", "¿Hay algo más que quieras que sepamos?"), ref="Part 9. Additional Information",
            help=("If it relates to a specific question, say which one. This can also be where you tell us more about a work or address period.", "Si se relaciona con una pregunta específica, dinos cuál. Aquí también puedes contarnos más sobre un período de trabajo o de domicilio."))

    # ================================================================== documents (dynamic)
    page(b, "documents", ("Documents", "Documentos"),
         ("Upload what you have now; you can add more before you send. Only the documents that fit your answers appear here.", "Sube lo que tengas ahora; puedes agregar más antes de enviar. Aquí solo aparecen los documentos que corresponden a tus respuestas."), group="documents")
    single = dict(files=("pdf,jpg,jpeg,png", 1, 10))
    multi = dict(files=("pdf,jpg,jpeg,png", 5, 10))
    b.field("docs_scope_note", "paragraph", ("", ""), content=(
        _label("What OG asks for", "These are OG's requests to prepare and review your case. USCIS lists the required evidence in the Form I-130 Instructions; OG will confirm what applies to you."),
        _label("Lo que pide OG", "Son solicitudes de OG para preparar y revisar tu caso. USCIS enumera la evidencia requerida en las Instrucciones del Formulario I-130; OG confirmará lo que aplica en tu caso.")))
    b.field("docs_tip", "paragraph", ("", ""), content=(
        _tip("Make sure each document is complete, readable, well lit and not cropped or blurry. Documents that are not in English may need a certified translation — OG can help."),
        _tip("Asegúrate de que cada documento esté completo, legible, bien iluminado y sin cortes ni desenfoque. Los documentos que no estén en inglés pueden necesitar una traducción certificada; OG puede ayudarte.")))

    def group_label(name, en, es):
        b.field(name, "paragraph", ("", ""), content=(f'<span class="block pt-2 text-xs font-bold uppercase tracking-wider text-accent-700">{en}</span>', f'<span class="block pt-2 text-xs font-bold uppercase tracking-wider text-accent-700">{es}</span>'))

    def doc(name, en, es, ref, hen=None, hes=None, multi_=False, note_=None):
        b.field(name, "file_upload", (en, es), ref=ref, note=note_ or "OG document request; not a statement of what USCIS requires.",
                help=(hen, hes) if hen else None, **(multi if multi_ else single))

    group_label("g_pet", "Petitioner (you)", "Peticionario (tú)")
    doc("doc_pet_id", "Your government photo ID", "Tu identificación oficial con foto", "OG request", "For example a driver's license, state ID or passport.", "Por ejemplo una licencia de conducir, una identificación estatal o un pasaporte.")
    doc("doc_pet_citizen", "Proof of your U.S. citizenship", "Prueba de tu ciudadanía de EE. UU.", "OG request (Part 2, Items 36–39)", "For example a U.S. passport, birth certificate, or Certificate of Naturalization / Citizenship.", "Por ejemplo un pasaporte de EE. UU., acta de nacimiento, o Certificado de Naturalización / Ciudadanía.", True)
    doc("doc_pet_lpr", "Your Green Card (front and back)", "Tu Green Card (frente y reverso)", "OG request (Part 2, Items 36, 40–41)", "A clear photo of both sides of your Permanent Resident Card.", "Una foto clara de ambos lados de tu Tarjeta de Residente Permanente.", True)
    doc("doc_pet_names", "Documents for your other names", "Documentos de tus otros nombres", "OG request (Part 2, Item 5)", "For example a marriage certificate or court order showing a name change.", "Por ejemplo un acta de matrimonio u orden judicial que muestre un cambio de nombre.", True)
    b.rule("show_field", "doc_pet_citizen", [("pet_status", "equals", "us_citizen")])
    b.rule("show_field", "doc_pet_lpr", [("pet_status", "equals", "lpr")])
    b.rule("show_field", "doc_pet_names", [("pet_other_names", "is_not_empty", "")])

    group_label("g_ben", "Beneficiary (your family member)", "Beneficiario (tu familiar)")
    doc("doc_ben_passport", "Passport (photo page) or travel document", "Pasaporte (página con la foto) o documento de viaje", "OG request (Part 4, Items 47–50)")
    doc("doc_ben_birth", "Birth certificate", "Acta de nacimiento", "OG request (Part 4, Items 6–8)", "For a child, it should show you as the parent.", "Para un hijo(a), debe mostrarte a ti como padre o madre.", True)
    doc("doc_ben_i94", "Form I-94 record and visa / status documents", "Registro I-94 y documentos de visa / estatus", "OG request (Part 4, Items 46.a–46.d)", None, None, True)
    doc("doc_ben_names", "Documents for their other names", "Documentos de sus otros nombres", "OG request (Part 4, Item 5)", None, None, True)
    doc("doc_ben_prior", "Papers about earlier petitions for the beneficiary", "Documentos de peticiones anteriores para el beneficiario", "OG request (Part 4, Item 10 / Part 5, Item 1)", "For example receipt or approval notices.", "Por ejemplo notificaciones de recibo o de aprobación.", True)
    show_any(b, "doc_ben_i94", [[("ben_ever_in_us", "equals", "yes"), ("ben_in_us_now", "equals", "yes")]])
    b.rule("show_field", "doc_ben_names", [("ben_other_names", "is_not_empty", "")])
    show_any(b, "doc_ben_prior", [[("ben_petition_filed", "equals", "yes")], [("pet_prior_filed", "equals", "yes")]])

    group_label("g_rel", "The relationship", "La relación")
    doc("doc_rel_marriage", "Marriage certificate", "Acta de matrimonio", "OG request (Part 2, Items 18–19; Part 4, Items 59–60)", None, None, True)
    doc("doc_rel_marriage_proof", "Evidence of your life together as a married couple", "Evidencia de su vida juntos como pareja casada", "OG request",
        "For example joint documents or photos of you together.", "Por ejemplo documentos conjuntos o fotos de ustedes juntos.", True)
    doc("doc_rel_pet_birth", "Your own birth certificate", "Tu propia acta de nacimiento", "OG request (Part 2, Items 24–35)", "It should show the parent's name.", "Debe mostrar el nombre del padre o la madre.", True)
    doc("doc_rel_step", "Marriage certificate of the parent and stepparent", "Acta de matrimonio del padre o madre y del padrastro o madrastra", "OG request (Part 1, Item 2)", None, None, True)
    doc("doc_rel_adoption", "Adoption decree", "Decreto de adopción", "OG request (Part 1, Items 2–4)", None, None, True)
    b.rule("show_field", "doc_rel_marriage", [("relationship_type", "equals", "spouse")])
    b.rule("show_field", "doc_rel_marriage_proof", [("relationship_type", "equals", "spouse")])
    show_any(b, "doc_rel_pet_birth", [[("relationship_type", "equals", "parent")], [("relationship_type", "equals", "sibling")]])
    b.rule("show_field", "doc_rel_step", [("relationship_basis", "equals", "stepchild")])
    show_any(b, "doc_rel_adoption", [[("relationship_basis", "equals", "adopted")], [("sibling_adopted", "equals", "yes")], [("pet_adopted_status", "equals", "yes")]])

    group_label("g_prior", "Prior marriages", "Matrimonios anteriores")
    doc("doc_pet_prior_marriages", "Divorce decree, annulment decree or death certificate for your prior marriages", "Decreto de divorcio, decreto de anulación o acta de defunción de tus matrimonios anteriores", "OG request (Part 2, Items 16–23)", None, None, True)
    doc("doc_ben_prior_marriages", "Divorce decree, annulment decree or death certificate for the beneficiary's prior marriages", "Decreto de divorcio, decreto de anulación o acta de defunción de los matrimonios anteriores del beneficiario", "OG request (Part 4, Items 17–24)", None, None, True)
    show_any(b, "doc_pet_prior_marriages", [[("pet_marital_status", "equals", v)] for v in ("divorced", "widowed", "annulled")] + [[("pet_times_married", "greater_than", "1")]])
    show_any(b, "doc_ben_prior_marriages", [[("ben_marital_status", "equals", v)] for v in ("divorced", "widowed", "annulled")] + [[("ben_times_married", "greater_than", "1")]])
    for name in ("g_pet", "g_ben", "g_rel", "g_prior"):
        pass
    b.field("g_other", "paragraph", ("", ""), content=('<span class="block pt-2 text-xs font-bold uppercase tracking-wider text-accent-700">Other documents</span><span class="block mt-1 text-[13px] text-slate-600">Do you have any other document that could help us?</span>',
                                                      '<span class="block pt-2 text-xs font-bold uppercase tracking-wider text-accent-700">Otros documentos</span><span class="block mt-1 text-[13px] text-slate-600">¿Tienes algún otro documento que pueda ayudarnos?</span>'))
    b.field("documents_other", "file_upload", ("Other Supporting Documents (optional)", "Otros documentos de apoyo (opcional)"), ref="OG addition", files=("pdf,jpg,jpeg,png", 10, 10))
    # the group headings only make sense when at least one document of the group shows
    show_any(b, "g_prior", [[("pet_marital_status", "equals", v)] for v in ("divorced", "widowed", "annulled")] + [[("pet_times_married", "greater_than", "1")]]
             + [[("ben_marital_status", "equals", v)] for v in ("divorced", "widowed", "annulled")] + [[("ben_times_married", "greater_than", "1")]])

    # ================================================================== confirm
    page(b, "confirm", ("Confirm and Send to OG", "Confirma y envía a OG"), group="confirm",
         desc=("Review your information and confirm that it is complete and accurate. OG Multiservices will prepare your Form I-130 and guide you through the required signatures based on how the petition will be filed.",
               "Revisa tu información y confirma que esté completa y correcta. OG Multiservices preparará tu Formulario I-130 y te indicará cómo completar las firmas requeridas según la forma en que se presente la petición."))
    note(b, "confirm_warning", WARNING_EN, WARNING_ES)
    b.field("preparer_request", "consent", ("Request for preparation", "Solicitud de preparación"), ref="Part 6, Item 2", note="Preparer prepared the petition at the petitioner's request.", req=True, content=(
        "I ask OG Multiservices to prepare my Form I-130 based only on the information I provided or authorized.",
        "Solicito a OG Multiservices que prepare mi Formulario I-130 con base únicamente en la información que proporcioné o autoricé."))
    b.field("confirm_accurate", "consent", ("Accuracy confirmation and authorization", "Confirmación de exactitud y autorización"), ref="Part 6 (declaration wording)", note="Customer confirmation only; not a signature.", req=True, content=(
        "I confirm that the information I provided is complete, true, and correct to the best of my knowledge, and I authorize OG Multiservices to use this information to prepare my Form I-130 and related documents.",
        "Confirmo que la información que proporcioné es completa, verdadera y correcta según mi leal saber y entender, y autorizo a OG Multiservices a usar esta información para preparar mi Formulario I-130 y los documentos relacionados."))
    return b


def ensure_i130_intake():
    """Create the production I-130 intake and connect it to the I-130 service page."""
    service = (
        Service.query.join(ServiceCategory)
        .filter(ServiceCategory.slug == "immigration", Service.slug == "i-130-petition")
        .first()
    )
    if not service:
        return False
    if Form.query.filter_by(slug=I130_SLUG).first():
        return False
    form = Form(slug=I130_SLUG, name_admin="I-130 Client Intake")
    db.session.add(form)
    form.form_type = "service_intake"
    form.status = "published"
    form.source_form_name = SOURCE_NAME
    form.source_edition = SOURCE_EDITION
    form.version = 1
    form.published_at = datetime.utcnow()
    form.title_en, form.title_es = "Family Petition — Form I-130", "Petición Familiar — Formulario I-130"
    form.description_en = "Guided intake for OG Multiservices to prepare your Form I-130. Your progress is saved automatically."
    form.description_es = "Solicitud guiada para que OG Multiservices prepare tu Formulario I-130. Tu progreso se guarda automáticamente."
    form.submit_label_en, form.submit_label_es = "Send to OG", "Enviar a OG"
    form.success_message_en = "OG Multiservices has your information and will review it. We'll contact you if we need anything else."
    form.success_message_es = "OG Multiservices tiene tu información y la revisará. Te contactaremos si necesitamos algo más."
    form.show_progress = True
    form.features_json = json.dumps({"completeness_check": True, "consistency": "i130", "sections": SECTIONS, "contexts": CONTEXTS, "context_names": CONTEXT_NAMES}, ensure_ascii=False)
    db.session.flush()
    build_i130(form)
    service.requires_intake = True
    service.form_id = form.id
    service.requires_account = True
    service.intake_label = "I-130 Client Intake"
    db.session.commit()
    return True
