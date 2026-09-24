"""DS-260 Client Intake — the Consular Processing Smart Intake, built natively on the Case + Person architecture.

The DS-260 (Immigrant Visa and Alien Registration Application) is an ONLINE Department of State form completed in CEAC. It is NOT a USCIS form, has no
edition number, and OG never completes, signs, certifies or submits it. This intake PREPARES the answers: it collects them once (reusing the real People,
addresses and histories OG already has), prepares an English CEAC-ready value for each one, and gives staff a section-by-section CEAC Preparation View.

SOURCE: see `ds260_text.py` and `ds260_source.py` (2019 DOS sample read page by page + newer official DOS material where it could be reached). Every question
carries its CEAC section and question in `FormField.source_ref` (admin-only) and, in `Form.features["ceac"]`, the canonical key and CEAC-ready transform.

NOT customer questions (CEAC-only): the applicant's own review, the E-Signature and certification, "Sign and Submit Application", the NVC case number +
passport number + CAPTCHA entered at signing, the FGM/C fact-sheet certification, the Selective Service notice acknowledgement, the confirmation page
and the Medical Examination Disclosure and Consent. CEAC passwords are never asked for or stored.

One DS-260 per VISA APPLICANT (a real Person): principal, spouse and each child who applies are separate applications in the same Consular Processing case.
"""

import json
from datetime import datetime

from app import ds260_text as T
from app.extensions import db
from app.models import Form, Service, ServiceCategory
from app.seed_i130 import page, records, where
from app.seed_i485 import (UNSURE, WHERE_A, WHERE_SSN, block_pair, choice, kp, mark_block_fields, only_if)
from app.seed_i90 import STATE_OPTIONS, YES_NO, Builder, _address_fields
from app.seed_i90_refine import _label, _tip
from app.seed_n400 import note, show_any, show_page_any

DS260_SLUG = "ds-260-client-intake"
SOURCE_NAME = "DS-260"
SOURCE_EDITION = "CEAC online (no edition)"
NEVER = ("ds_role", "equals", "__never__")

SECTIONS = [
    {"key": "before", "title": {"en": "Before You Begin", "es": "Antes de empezar"}},
    {"key": "about", "title": {"en": "About You", "es": "Sobre ti"}},
    {"key": "passport", "title": {"en": "Passport & Nationality", "es": "Pasaporte y nacionalidad"}},
    {"key": "contact", "title": {"en": "Address & Contact", "es": "Dirección y contacto"}},
    {"key": "family", "title": {"en": "Your Family", "es": "Tu familia"}},
    {"key": "travel", "title": {"en": "U.S. Travel", "es": "Viajes a EE. UU."}},
    {"key": "work", "title": {"en": "Work & Education", "es": "Trabajo y estudios"}},
    {"key": "petitioner", "title": {"en": "Petitioner", "es": "Peticionario"}},
    {"key": "security", "title": {"en": "Security & Background", "es": "Seguridad y antecedentes"}},
    {"key": "ssn", "title": {"en": "Social Security", "es": "Seguro Social"}},
    {"key": "assist", "title": {"en": "Who Helped You", "es": "Quién te ayudó"}},
    {"key": "documents", "title": {"en": "Documents", "es": "Documentos"}},
    {"key": "confirm", "title": {"en": "Confirmation", "es": "Confirmación"}},
]
CONTEXTS = {
    "applicant": {"title": {"en": "Visa applicant", "es": "Solicitante de visa"}, "subtitle": {"en": "The person this DS-260 is for.", "es": "La persona para quien es este DS-260."}, "tone": "accent", "icon": "person"},
    "petitioner": {"title": {"en": "Petitioner", "es": "Peticionario"}, "subtitle": {"en": "The person or business that filed the petition.", "es": "La persona o empresa que presentó la petición."}, "tone": "brand", "icon": "people"},
}
CONTEXT_ROLES = {"applicant": "visa_applicant", "petitioner": "petitioner"}

WHERE_ARN = ("An Alien Registration Number is 7 to 9 digits, usually starting with “A”. It appears on U.S. immigration documents such as a Green Card or work permit.", "Un Número de Registro de Extranjero tiene de 7 a 9 dígitos, normalmente con “A”. Aparece en documentos migratorios de EE. UU., como una Green Card o un permiso de trabajo.")


class DS(Builder):
    """Builder that also records, for every customer question, where it goes in CEAC (section, question, transform)."""

    def __init__(self, form):
        super().__init__(form)
        self.ceac = {}
        self.sec = "Getting Started"

    def field(self, name, ftype, label, *, cx=None, **kw):
        if kw.get("ref") is None and ftype != "paragraph":
            kw["ref"] = f"{self.sec} — {(cx or {}).get('q') or (label[0] if label else name)}"
        f = super().field(name, ftype, label, **kw)
        if ftype not in ("paragraph", "consent"):
            self.ceac[name] = dict({"sec": self.sec, "label": (cx or {}).get("q") or (label[0] if label else name), "n": len(self.ceac)}, **{k: v for k, v in (cx or {}).items() if k != "q"})
        return f


def sec(b, name):
    b.sec = name


def cfg_merge(b, name, **flags):
    f = b.fields[name]
    cfg = json.loads(f.config_json) if f.config_json else {}
    cfg.update(flags)
    f.config_json = json.dumps(cfg, ensure_ascii=False)


def private(b, *names):
    for n in names:
        b.fields[n].is_sensitive = True
        cfg_merge(b, n, private=True)


def para(b, name, en, es, cls="text-[15px] leading-relaxed text-slate-700"):
    b.field(name, "paragraph", ("", ""), content=(f'<span class="block {cls}">{en}</span>', f'<span class="block {cls}">{es}</span>'))


def dyn(b, name, kind):
    b.field(name, "paragraph", ("", ""), content=("", ""))
    cfg_merge(b, name, dynamic={"kind": kind})


def calc_field(b, name, label, ref):
    b.field(name, "short_answer", (label, label), ref=ref, note="Calculated or configured by the platform; not a question.")
    kp(b, name, system=True)


def yn(b, name, label, *, req=True, help=None, cx=None, ref=None, note_=None):
    return b.field(name, "single_choice", label, req=req, opts=YES_NO, help=help, cx=cx, ref=ref, note=note_)


def explain(b, name, when_field, when_value="yes", label=None, help=None, cx=None, sens=False):
    b.field(name, "long_answer", label or ("Please explain your answer", "Explica tu respuesta"), req=True, maxlen=3000, help=help, cx=dict(cx or {}, t="free"))
    b.rule("show_field", name, [(when_field, "equals", when_value)])
    if sens:
        private(b, name)


def only_missing(b, key, names):
    """On a shared block's edit step show a field only when it is the customer's turn to give it (nothing known, they chose to edit, or the case could
    not supply that detail). Address fields keep their U.S. / not-U.S. condition inside every rule (several show rules aimed at one field combine with OR)."""
    from app.case_types import FORM_CASE_CONFIG

    block = FORM_CASE_CONFIG["DS-260"]["blocks"][key]
    owner, prefixes = {}, []
    for fact_key, target in block["fields"].items():
        if isinstance(target, str):
            owner[target] = fact_key
        elif isinstance(target, dict) and "address_prefix" in target:
            prefixes.append(target["address_prefix"])
            for n in names:
                if n.startswith(target["address_prefix"] + "_"):
                    owner[n] = fact_key
    for n in names:
        extra = []
        for prefix in prefixes:
            if n.startswith(prefix + "_"):
                suffix = n[len(prefix) + 1:]
                if suffix in ("state", "zip"):
                    extra = [(f"{prefix}_is_us", "equals", "yes")]
                elif suffix in ("province", "postal_code", "country"):
                    extra = [(f"{prefix}_is_us", "equals", "no")]
        b.rule("show_field", n, [(f"{key}_avail", "equals", "no")] + extra)
        b.rule("show_field", n, [(key, "equals", "edit")] + extra)
        if n in owner:
            b.rule("show_field", n, [(key, "equals", "correct"), (f"{key}_missing", "selected", owner[n])] + extra)


def addr(b, prefix, ref, *, us_label=None, cx_sec=None):
    before = set(b.fields)
    _address_fields(b, prefix, ref, us_label=us_label)
    labels = {"is_us": "Address is in the United States (OG helper)", "street": "Street Address (Line 1)", "unit_type": "Unit type", "unit_number": "Street Address (Line 2)", "city": "City",
              "state": "State", "zip": "Postal Zone / ZIP Code", "province": "State / Province", "postal_code": "Postal Zone / ZIP Code", "country": "Country / Region"}
    for n in set(b.fields) - before:
        suffix = n[len(prefix) + 1:]
        if suffix in labels and n in b.ceac:
            b.ceac[n].update({"label": labels[suffix], "t": "proper", "addr": prefix, "hide": suffix == "is_us"})


# ================================================================== the intake
def build_ds260(form):
    b = DS(form)
    from app.case_types import FORM_CASE_CONFIG

    cfg = FORM_CASE_CONFIG["DS-260"]
    blocks = ["sb_identity", "sb_othernames", "sb_marital", "sb_passport", "sb_address", "sb_addr_history", "sb_contact", "sb_pt_name", "sb_pt_address", "sb_pt_contact"]

    # ---------------------------------------------------------------- never-shown system page
    page(b, "sys", ("Case information", "Información del caso"), group=None)
    for k in blocks:
        b.field(f"{k}_avail", "short_answer", (f"{k} available", f"{k} disponible"), ref="OG system flag (never shown)")
        kp(b, f"{k}_avail", system=True)
        if cfg["blocks"][k].get("ask") or k == "sb_address":
            b.field(f"{k}_missing", "multi_choice", (f"{k} missing", f"{k} faltante"), ref="OG system flag (never shown)", opts=[(f, f, f) for f in cfg["blocks"][k]["fields"]])
            kp(b, f"{k}_missing", system=True)
    for name, ref in (("ds_role", "principal | derivative (set at setup)"), ("c_age", "age in years from the date of birth"), ("c_age14", "over age 14 (2019 sample rule)"),
                      ("c_age16", "age 16 or over (address-history start)"), ("c_since16", "date the applicant turned 16"), ("c_rules", "2019-sample section visibility hints (UNVERIFIED for the current system)"),
                      ("c_sec_flags", "Security & Background: number of Yes answers per section (OG review count; never a conclusion)"),
                      ("c_prep", "preparer defaults (central OG configuration)"), ("c_fgmc", "FGM/C country flag (2019 sample list; UNVERIFIED)"),
                      ("pf_seen", "pick applied: father"), ("pm_seen", "pick applied: mother")):
        calc_field(b, name, name, "OG system value (never shown): " + ref)
    show_page_any(b, "sys", [[("sb_identity_avail", "equals", "__never__")]])

    # ---------------------------------------------------------------- Before you begin
    page(b, "intro", ("Before you begin", "Antes de empezar"), group="before", ctx="applicant")
    dyn(b, "intro_case", "ds_context")
    para(b, "intro_1", "This intake collects what OG Multiservices needs to prepare the Immigrant Visa and Alien Registration Application (DS-260) for one visa applicant. Your answers save automatically, so you can stop and come back anytime. Each person who is applying for an immigrant visa has their own DS-260.",
         "Este formulario reúne lo que OG Multiservices necesita para preparar la Solicitud de Visa de Inmigrante y Registro de Extranjero (DS-260) de un solicitante de visa. Tus respuestas se guardan automáticamente, así que puedes parar y volver cuando quieras. Cada persona que solicita una visa de inmigrante tiene su propio DS-260.")
    para(b, "intro_2", T.ENGLISH_NOTE[0], T.ENGLISH_NOTE[1])
    para(b, "intro_3", "If OG already has information about the people involved from another application — even in a different case — we show it to you first so you can confirm it instead of typing it again. Nothing is reused without your confirmation, and anything that changes over time is checked with you first. Never share a CEAC password, an email password or any login with OG: we never need them.",
         "Si OG ya tiene información de las personas involucradas de otra solicitud —incluso en otro caso— te la mostramos primero para que la confirmes en lugar de escribirla otra vez. Nada se reutiliza sin tu confirmación, y lo que cambia con el tiempo se verifica contigo primero. Nunca compartas con OG una contraseña de CEAC, de tu correo ni ningún acceso: nunca los necesitamos.")
    para(b, "intro_4", "OG Multiservices provides document preparation and administrative assistance. We are not a law firm and do not provide legal advice or representation. We cannot tell you whether you qualify for a visa. " + T.CEAC_ONLY_NOTE[0],
         "OG Multiservices ofrece preparación de documentos y asistencia administrativa. No somos un bufete de abogados ni brindamos asesoría o representación legal. No podemos decirte si calificas para una visa. " + T.CEAC_ONLY_NOTE[1])
    page(b, "smart_start", ("We already have information", "Ya tenemos información"), ("This is what OG already knows. You will review it before it is used — nothing is copied without your confirmation.", "Esto es lo que OG ya sabe. Lo revisarás antes de usarlo: nada se copia sin tu confirmación."), group="before", ctx="applicant")
    dyn(b, "smart_card", "ds_start")
    show_page_any(b, "smart_start", [[(f"{k}_avail", "equals", "yes")] for k in ("sb_identity", "sb_othernames", "sb_marital", "sb_passport", "sb_address", "sb_addr_history", "sb_contact", "sb_pt_name", "sb_pt_address")])

    # ================================================================== PERSONAL 1
    sec(b, "Personal 1")

    def edit_identity():
        para(b, "id_note", "Use the name exactly as it appears on the passport or travel document. If the applicant has no given name, use FNU (“first name unknown”).",
             "Usa el nombre exactamente como aparece en el pasaporte o documento de viaje. Si el solicitante no tiene nombre de pila, usa FNU (“first name unknown”).", "text-[13px] leading-relaxed text-slate-600")
        b.field("a_family", "short_answer", ("Surnames (family name)", "Apellidos"), req=True, width="half", maxlen=60, cx={"q": "Surnames", "t": "name"})
        b.field("a_given", "short_answer", ("Given names", "Nombres"), req=True, width="half", maxlen=60, cx={"q": "Given Names", "t": "name"})
        b.field("a_native", "short_answer", ("Full name in your native alphabet (only if it is not the Latin alphabet)", "Nombre completo en tu alfabeto nativo (solo si no usa el alfabeto latino)"), maxlen=120,
                help=("If your language uses the Latin alphabet, leave this blank: CEAC then gets “Does Not Apply”. OG never translates or changes a name.", "Si tu idioma usa el alfabeto latino, déjalo en blanco: en CEAC se registra “Does Not Apply”. OG nunca traduce ni cambia un nombre."),
                cx={"q": "Full Name in Native Alphabet", "t": "native", "dna": True})
        b.field("a_dob", "date", ("Date of birth", "Fecha de nacimiento"), req=True, date_rule="past", width="half", cx={"q": "Date of Birth", "t": "date"})
        b.field("a_sex", "single_choice", ("Sex", "Sexo"), req=True, opts=T.SEX, width="half", cx={"q": "Sex", "t": "choice"})
        b.field("a_birth_city", "short_answer", ("City of birth", "Ciudad de nacimiento"), req=True, width="half", maxlen=60, cx={"q": "City of Birth", "t": "proper"})
        b.field("a_birth_state", "short_answer", ("State / province of birth (if any)", "Estado / provincia de nacimiento (si aplica)"), width="half", maxlen=60, cx={"q": "State/Province of Birth", "t": "proper", "dna": True})
        b.field("a_birth_country", "short_answer", ("Country / region of birth", "País / región de nacimiento"), req=True, width="half", maxlen=60, cx={"q": "Country/Region of Birth", "t": "proper"})
        b.field("a_nationality", "short_answer", ("Country / region of origin (nationality)", "País / región de origen (nacionalidad)"), req=True, maxlen=60, cx={"q": "Country/Region of Origin (Nationality)", "t": "proper"})
        names = ["a_family", "a_given", "a_native", "a_dob", "a_sex", "a_birth_city", "a_birth_state", "a_birth_country", "a_nationality"]
        mark_block_fields(b, "sb_identity", names)
        only_missing(b, "sb_identity", names)
    block_pair(b, "sb_identity", group="about", form_name="DS-260", ask_missing=True, ctx="applicant",
               review_title=("We already have {ap}'s identity information", "Ya tenemos los datos de identidad de {ap}"),
               review_desc=("Name, date of birth, place of birth and nationality. Confirm them or change them.", "Nombre, fecha de nacimiento, lugar de nacimiento y nacionalidad. Confírmalos o cámbialos."),
               edit_title=("About the applicant", "Sobre el solicitante"), edit_desc=("Only what is still missing is asked when OG already has the rest.", "Solo se pregunta lo que aún falta cuando OG ya tiene el resto."), build_edit=edit_identity)

    def edit_othernames():
        records(b, "a_other_names", ("Other names used", "Otros nombres usados"), "Personal 1 — Other Names Used", "other_name", max=12,
                help=("Maiden, religious, professional, alias or any other name ever used. If none, just continue.", "Apellido de soltera, religioso, profesional, alias u otro nombre que hayas usado. Si no tienes, solo continúa."))
        b.ceac["a_other_names"] = {"sec": b.sec, "label": "Other Names Used (Other Surnames / Other Given Names)", "n": len(b.ceac), "t": "records"}
        mark_block_fields(b, "sb_othernames", ["a_other_names"])
    block_pair(b, "sb_othernames", group="about", form_name="DS-260", ctx="applicant", review_title=("We already have the other names {ap} has used", "Ya tenemos los otros nombres que ha usado {ap}"),
               review_desc=("Confirm this list or change it.", "Confirma esta lista o cámbiala."), edit_title=("Other names used", "Otros nombres usados"), edit_desc=None, build_edit=edit_othernames)

    def edit_marital():
        b.field("a_marital", "single_choice", ("Current marital status", "Estado civil actual"), req=True, opts=T.MARITAL, cx={"q": "Current Marital Status", "t": "choice"})
        mark_block_fields(b, "sb_marital", ["a_marital"])
    block_pair(b, "sb_marital", group="about", form_name="DS-260", ctx="applicant", review_title=("{ap}'s marital status", "Estado civil de {ap}"), review_desc=("Marital status can change. Is this still correct?", "El estado civil puede cambiar. ¿Sigue siendo correcto?"),
               edit_title=("Marital status", "Estado civil"), edit_desc=None, build_edit=edit_marital)

    # ================================================================== PERSONAL 2 — passport & nationality
    sec(b, "Personal 2")

    def edit_passport():
        b.field("a_doc_type", "single_choice", ("Travel document type", "Tipo de documento de viaje"), req=True, opts=T.DOC_TYPES, cx={"q": "Document Type", "t": "choice"})
        b.field("a_doc_number", "short_answer", ("Document number", "Número del documento"), req=True, sensitive=True, width="half", maxlen=20, cx={"q": "Document ID", "t": "proper"})
        b.field("a_doc_country", "short_answer", ("Country / authority that issued the document", "País / autoridad que emitió el documento"), req=True, width="half", maxlen=60, cx={"q": "Country/Authority that Issued Document", "t": "proper"})
        b.field("a_doc_issued", "date", ("Issue date", "Fecha de emisión"), req=True, date_rule="past", width="half", cx={"q": "Issuance Date", "t": "date"})
        b.field("a_doc_expiry", "date", ("Expiration date", "Fecha de vencimiento"), req=True, width="half", cx={"q": "Expiration Date", "t": "date"})
        where(b, "a_doc_number", *("The number is printed on the photo page of the passport or travel document.", "El número está impreso en la página con la foto del pasaporte o documento de viaje."))
        mark_block_fields(b, "sb_passport", ["a_doc_type", "a_doc_number", "a_doc_country", "a_doc_issued", "a_doc_expiry"])
    block_pair(b, "sb_passport", group="passport", form_name="DS-260", ctx="applicant", review_title=("{ap}'s passport or travel document", "Pasaporte o documento de viaje de {ap}"),
               review_desc=("Passports are renewed. Is this the document {ap} will use?", "Los pasaportes se renuevan. ¿Es este el documento que usará {ap}?"), edit_title=("Passport or travel document", "Pasaporte o documento de viaje"),
               edit_desc=("This must match the document exactly.", "Debe coincidir exactamente con el documento."), build_edit=edit_passport)
    page(b, "other_nat", ("Other nationalities", "Otras nacionalidades"), group="passport", ctx="applicant")
    yn(b, "a_other_nat", ("Do you hold, or have you ever held, any nationality other than the one you gave above?", "¿Tienes o has tenido alguna nacionalidad distinta a la que indicaste arriba?"), cx={"q": "Do you hold or have you held any nationality other than the one you have indicated above?", "t": "yn"})
    b.field("a_other_nat_country", "short_answer", ("Other country / region of origin (nationality)", "Otro país / región de origen (nacionalidad)"), req=True, maxlen=60, cx={"q": "Other Country/Region of Origin", "t": "proper"})
    yn(b, "a_other_nat_passport", ("Do you hold a passport from that country?", "¿Tienes un pasaporte de ese país?"), cx={"q": "Do you hold a passport from that country?", "t": "yn"})
    b.field("a_other_nat_passport_no", "short_answer", ("Passport number", "Número de pasaporte"), req=True, sensitive=True, maxlen=20, cx={"q": "Passport Number", "t": "proper"})
    only_if(b, "a_other_nat_country", ("a_other_nat", "equals", "yes"))
    only_if(b, "a_other_nat_passport", ("a_other_nat", "equals", "yes"))
    only_if(b, "a_other_nat_passport_no", ("a_other_nat", "equals", "yes"), ("a_other_nat_passport", "equals", "yes"))

    # ================================================================== ADDRESS & PHONE
    sec(b, "Address and Phone")

    def edit_address():
        addr(b, "pa", "Address and Phone — Present Address")
        b.field("pa_since", "date", ("Started living here", "Empezó a vivir aquí"), req=True, date_rule="past", width="half", cx={"q": "Started Living Here", "t": "month_year"})
        names = [n for n in b.fields if n.startswith("pa_")]
        mark_block_fields(b, "sb_address", names)
        only_missing(b, "sb_address", names)
    block_pair(b, "sb_address", group="contact", form_name="DS-260", ask_missing=True, ctx="applicant", review_title=("{ap}'s present address", "Dirección actual de {ap}"), review_desc=("Is this still where {ap} lives?", "¿Sigue viviendo {ap} aquí?"),
               edit_title=("Present address", "Dirección actual"), edit_desc=("Where the applicant lives now. Do not use an older address.", "Donde vive el solicitante ahora. No uses una dirección anterior."), build_edit=edit_address)

    def edit_history():
        records(b, "a_addr_history", ("Every address since age 16", "Cada dirección desde los 16 años"), "Address and Phone — Previous Addresses", "address", req=True, max=30,
                timeline={"years": 10, "gap_days": 31, "overlap_days": 31, "since_field": "c_since16"},
                help=("Include the present address and every other address the applicant has had since turning 16.", "Incluye la dirección actual y cada otra dirección que el solicitante ha tenido desde los 16 años."))
        b.ceac["a_addr_history"] = {"sec": b.sec, "label": "Previous addresses since the age of sixteen", "n": len(b.ceac), "t": "records"}
        mark_block_fields(b, "sb_addr_history", ["a_addr_history"])
    block_pair(b, "sb_addr_history", group="contact", form_name="DS-260", ctx="applicant", gates=[[("c_age16", "equals", "yes")]], review_title=("We already have {ap}'s address history", "Ya tenemos el historial de direcciones de {ap}"),
               review_desc=("Confirm this list or change it.", "Confirma esta lista o cámbiala."), edit_title=("Addresses since age 16", "Direcciones desde los 16 años"), edit_desc=("Add the present address and every earlier one. Gaps never block you: OG reviews them.", "Agrega la dirección actual y cada una anterior. Los vacíos no te bloquean: OG los revisa."), build_edit=edit_history)

    sec(b, "Mailing / Permanent")
    page(b, "mail_gate", ("Mailing address", "Dirección postal"), group="contact", ctx="applicant")
    yn(b, "m_same", ("Is the mailing address the same as the present address?", "¿La dirección postal es la misma que la dirección actual?"), cx={"q": "Is your mailing address the same as your present address?", "t": "yn"})
    page(b, "mailing", ("Mailing address", "Dirección postal"), group="contact", ctx="applicant")
    addr(b, "ma", "Mailing / Permanent — Mailing Address")
    show_page_any(b, "mailing", [[("m_same", "equals", "no")]])
    page(b, "perm_us", ("Where will the applicant live in the United States?", "¿Dónde vivirá el solicitante en Estados Unidos?"),
         ("The permanent address in the United States. Use “I do not know yet” if the applicant does not have one.", "La dirección permanente en Estados Unidos. Usa “Aún no lo sé” si el solicitante no tiene una."), group="contact", ctx="applicant")
    b.field("us_known", "single_choice", ("Do you know the U.S. address where the applicant will live?", "¿Conoces la dirección de EE. UU. donde vivirá el solicitante?"), req=True, opts=[("yes", "Yes", "Sí"), ("no", "I do not know yet", "Aún no lo sé")],
            cx={"q": "Permanent Address in the U.S.", "t": "yn", "hide": True})
    b.field("us_person", "short_answer", ("Name of the person currently living at that address (if any)", "Nombre de la persona que vive actualmente en esa dirección (si aplica)"), maxlen=80, cx={"q": "Name of Person Currently Living at Address", "t": "proper", "dna": True})
    b.field("us_street", "short_answer", ("Street address (line 1)", "Dirección (línea 1)"), req=True, maxlen=80, cx={"q": "U.S. Street Address (Line 1)", "t": "proper"})
    b.field("us_street2", "short_answer", ("Street address (line 2, optional)", "Dirección (línea 2, opcional)"), maxlen=80, cx={"q": "U.S. Street Address (Line 2)", "t": "proper"})
    b.field("us_city", "short_answer", ("City", "Ciudad"), req=True, width="half", maxlen=60, cx={"q": "City", "t": "proper"})
    b.field("us_state", "dropdown", ("State", "Estado"), req=True, opts=STATE_OPTIONS, width="half", cx={"q": "State", "t": "choice"})
    b.field("us_zip", "short_answer", ("ZIP code", "Código postal (ZIP)"), req=True, width="half", pattern=r"\d{5}", maxlen=5, msg=("Enter a 5-digit ZIP code.", "Ingresa un ZIP de 5 dígitos."), cx={"q": "ZIP Code", "t": "proper"})
    b.field("us_phone", "phone", ("Telephone at that address (if any)", "Teléfono en esa dirección (si aplica)"), width="half", cx={"q": "Telephone", "t": "phone", "dna": True})
    for n in ("us_person", "us_street", "us_street2", "us_city", "us_state", "us_zip", "us_phone"):
        only_if(b, n, ("us_known", "equals", "yes"))
    page(b, "gc_mail", ("Where should the Green Card be mailed?", "¿Adónde debe enviarse la Green Card?"), group="contact", ctx="applicant")
    b.field("gc_same", "single_choice", ("Is the U.S. address you gave the address where the applicant wants the Green Card mailed?", "¿La dirección de EE. UU. que diste es donde el solicitante quiere que se envíe la Green Card?"), req=True,
            opts=[("yes", "Yes", "Sí"), ("no", "No — use a different U.S. address / contact person", "No — usar otra dirección de EE. UU. / persona de contacto"), ("unsure", "Not sure — OG will review", "No estoy seguro(a) — OG lo revisará")],
            cx={"q": "Is this address where you want your Green Card mailed?", "t": "choice"})
    b.field("gc_person", "short_answer", ("Contact person's name", "Nombre de la persona de contacto"), req=True, maxlen=80, cx={"q": "Contact Person Name", "t": "proper"})
    b.field("gc_street", "short_answer", ("Street address (line 1)", "Dirección (línea 1)"), req=True, maxlen=80, cx={"q": "Green Card Street Address (Line 1)", "t": "proper"})
    b.field("gc_street2", "short_answer", ("Street address (line 2, optional)", "Dirección (línea 2, opcional)"), maxlen=80, cx={"q": "Green Card Street Address (Line 2)", "t": "proper"})
    b.field("gc_city", "short_answer", ("City", "Ciudad"), req=True, width="half", maxlen=60, cx={"q": "City", "t": "proper"})
    b.field("gc_state", "dropdown", ("State", "Estado"), req=True, opts=STATE_OPTIONS, width="half", cx={"q": "State", "t": "choice"})
    b.field("gc_zip", "short_answer", ("ZIP code", "Código postal (ZIP)"), req=True, width="half", pattern=r"\d{5}", maxlen=5, msg=("Enter a 5-digit ZIP code.", "Ingresa un ZIP de 5 dígitos."), cx={"q": "ZIP Code", "t": "proper"})
    b.field("gc_phone", "phone", ("Contact person's telephone", "Teléfono de la persona de contacto"), width="half", cx={"q": "Telephone", "t": "phone", "dna": True})
    for n in ("gc_person", "gc_street", "gc_street2", "gc_city", "gc_state", "gc_zip", "gc_phone"):
        only_if(b, n, ("gc_same", "equals", "no"))

    sec(b, "Address and Phone")

    def edit_contact():
        b.field("a_phone_primary", "phone", ("Primary telephone number", "Teléfono principal"), req=True, width="half", cx={"q": "Primary Phone Number", "t": "phone"})
        b.field("a_phone_secondary", "phone", ("Secondary telephone number (if any)", "Teléfono secundario (si tiene)"), width="half", cx={"q": "Secondary Phone Number", "t": "phone", "dna": True})
        b.field("a_phone_work", "phone", ("Work telephone number (if any)", "Teléfono del trabajo (si tiene)"), width="half", cx={"q": "Work Phone Number", "t": "phone", "dna": True})
        b.field("a_email", "email", ("Email address", "Correo electrónico"), req=True, help=("An address the applicant can reach. Never share the email password with OG.", "Una dirección a la que el solicitante tenga acceso. Nunca compartas la contraseña del correo con OG."), cx={"q": "Email Address", "t": "raw"})
        mark_block_fields(b, "sb_contact", ["a_phone_primary", "a_phone_secondary", "a_phone_work", "a_email"])
    block_pair(b, "sb_contact", group="contact", form_name="DS-260", ctx="applicant", review_title=("We already have {ap}'s contact information", "Ya tenemos la información de contacto de {ap}"), review_desc=("Is it still current?", "¿Sigue vigente?"),
               edit_title=("Telephone and email", "Teléfono y correo electrónico"), edit_desc=None, build_edit=edit_contact)
    page(b, "contact_more", ("Other phone numbers and emails", "Otros teléfonos y correos"), ("List any others used in the last five years.", "Indica los demás que se hayan usado en los últimos cinco años."), group="contact", ctx="applicant")
    yn(b, "a_more_phones", ("Has the applicant used any other telephone numbers in the last five years?", "¿El solicitante ha usado otros números de teléfono en los últimos cinco años?"), cx={"q": "Have you used any other phone numbers in the last five years?", "t": "yn"})
    records(b, "a_other_phones", ("Additional telephone numbers", "Números de teléfono adicionales"), "Address and Phone — Additional Phone Number", "ds_phone", max=10, req=True)
    b.ceac["a_other_phones"] = {"sec": b.sec, "label": "Additional Phone Number", "n": len(b.ceac), "t": "records"}
    only_if(b, "a_other_phones", ("a_more_phones", "equals", "yes"))
    yn(b, "a_more_emails", ("Has the applicant used any other email addresses in the last five years?", "¿El solicitante ha usado otras direcciones de correo en los últimos cinco años?"), cx={"q": "Have you used any other email addresses in the last five years?", "t": "yn"})
    records(b, "a_other_emails", ("Additional email addresses", "Direcciones de correo adicionales"), "Address and Phone — Additional Email Address", "ds_email", max=10, req=True)
    b.ceac["a_other_emails"] = {"sec": b.sec, "label": "Additional Email Address", "n": len(b.ceac), "t": "records"}
    only_if(b, "a_other_emails", ("a_more_emails", "equals", "yes"))

    page(b, "social", ("Social media", "Redes sociales"), group="contact", ctx="applicant")
    para(b, "social_note", "List each social media platform the applicant has used in the last five years and the username or handle. <strong>Never give a password.</strong> The Department of State's list of platforms is shown in CEAC: write the platform's name here and staff will pick it in CEAC. Private person-to-person messaging (for example WhatsApp) is not included.",
         "Indica cada plataforma de redes sociales que el solicitante haya usado en los últimos cinco años y el usuario o identificador. <strong>Nunca des una contraseña.</strong> La lista de plataformas del Departamento de Estado aparece en CEAC: escribe aquí el nombre de la plataforma y el personal la elegirá en CEAC. La mensajería privada de persona a persona (por ejemplo WhatsApp) no se incluye.",
         "text-[14px] leading-relaxed text-slate-700")
    yn(b, "a_social_has", ("Has the applicant used any social media platform in the last five years?", "¿El solicitante ha usado alguna plataforma de redes sociales en los últimos cinco años?"), cx={"q": "Social Media (select None if none)", "t": "yn"})
    records(b, "a_social", ("Social media accounts", "Cuentas de redes sociales"), "Address and Phone — Social Media Provider/Platform and Identifier", "ds_social", max=20, req=True)
    b.ceac["a_social"] = {"sec": b.sec, "label": "Social Media Provider/Platform + Identifier", "n": len(b.ceac), "t": "records", "unv": "2019 sample; provider list not verified for the current system"}
    only_if(b, "a_social", ("a_social_has", "equals", "yes"))
    yn(b, "a_social_other_has", ("Has the applicant used any other website or application to create or share content (photos, videos, status updates)?", "¿El solicitante ha usado algún otro sitio web o aplicación para crear o compartir contenido (fotos, videos, estados)?"), cx={"q": "Other Social Media", "t": "yn"})
    records(b, "a_social_other", ("Other websites or applications", "Otros sitios web o aplicaciones"), "Address and Phone — Other Social Media Provider/Platform and Identifier", "ds_social_other", max=20, req=True)
    b.ceac["a_social_other"] = {"sec": b.sec, "label": "Other Social Media Provider/Platform + Identifier", "n": len(b.ceac), "t": "records", "unv": "2019 sample"}
    only_if(b, "a_social_other", ("a_social_other_has", "equals", "yes"))

    # ================================================================== FAMILY
    sec(b, "Family: Parents")
    page(b, "parents", ("Parents", "Padres"), ("Give the biological parents (adoptive parents if the applicant was adopted). If a detail is not known, leave it blank: OG enters “Do Not Know” in CEAC only where CEAC allows it.",
                                               "Indica a los padres biológicos (los adoptivos si el solicitante fue adoptado). Si no conoces un dato, déjalo en blanco: OG registra “Do Not Know” en CEAC solo donde CEAC lo permite."), group="family", ctx="applicant")
    records(b, "pf_records", ("Father", "Padre"), "Family: Parents — Father", "ds_parent", req=True, max=1, fill_extra={"birth_city": "birth_city", "birth_state": "birth_state", "birth_country": "birth_country"})
    b.ceac["pf_records"] = {"sec": b.sec, "label": "Father", "n": len(b.ceac), "t": "records", "dk": ["family", "given", "dob", "birth_city", "birth_state", "birth_country", "addr_street", "addr_city", "addr_state", "addr_postal", "addr_country"], "kind": "father"}
    records(b, "pm_records", ("Mother", "Madre"), "Family: Parents — Mother", "ds_parent", req=True, max=1, fill_extra={"birth_city": "birth_city", "birth_state": "birth_state", "birth_country": "birth_country"},
            help=("Use the mother's surnames AT BIRTH.", "Usa los apellidos de la madre AL NACER."))
    b.ceac["pm_records"] = {"sec": b.sec, "label": "Mother", "n": len(b.ceac), "t": "records", "dk": ["family", "given", "dob", "birth_city", "birth_state", "birth_country", "addr_street", "addr_city", "addr_state", "addr_postal", "addr_country"], "kind": "mother"}

    sec(b, "Family: Spouse")
    page(b, "spouse", ("Current spouse", "Cónyuge actual"), ("Only for an applicant who is married or legally separated. OG does not assume whether the spouse is applying too — tell us.", "Solo para un solicitante casado o legalmente separado. OG no asume si el cónyuge también solicita: dinos."), group="family", ctx="applicant")
    records(b, "s_records", ("Current spouse", "Cónyuge actual"), "Family: Spouse — Current Spouse", "ds_spouse", req=True, max=1, fill_extra={"birth_city": "birth_city", "birth_state": "birth_state", "birth_country": "birth_country"})
    b.ceac["s_records"] = {"sec": b.sec, "label": "Current Spouse", "n": len(b.ceac), "t": "records", "dk": ["birth_city"], "kind": "spouse"}
    show_page_any(b, "spouse", [[("a_marital", "equals", "married")], [("a_marital", "equals", "separated")]])

    sec(b, "Family: Previous Spouse")
    page(b, "prev_spouse", ("Previous spouses", "Cónyuges anteriores"), ("Include deceased spouses and marriages that ended by divorce or annulment.", "Incluye cónyuges fallecidos y matrimonios que terminaron por divorcio o anulación."), group="family", ctx="applicant")
    yn(b, "ps_has", ("Has the applicant been married before?", "¿El solicitante ha estado casado(a) antes?"), cx={"q": "Have you been married before?", "t": "yn"})
    records(b, "ps_records", ("Previous spouses", "Cónyuges anteriores"), "Family: Previous Spouse", "ds_prev_spouse", req=True, max=10)
    b.ceac["ps_records"] = {"sec": b.sec, "label": "Previous Spouse(s)", "n": len(b.ceac), "t": "records"}
    only_if(b, "ps_records", ("ps_has", "equals", "yes"))

    sec(b, "Family: Children")
    page(b, "children", ("Children", "Hijos"), ("Include natural, adopted and stepchildren. A child who is applying for an immigrant visa gets their own DS-260: OG links it to the same person.", "Incluye hijos biológicos, adoptados e hijastros. Un hijo que solicita una visa de inmigrante tiene su propio DS-260: OG lo vincula a la misma persona."), group="family", ctx="applicant")
    yn(b, "k_has", ("Does the applicant have any children?", "¿El solicitante tiene hijos?"), cx={"q": "Do you have any children?", "t": "yn"})
    records(b, "k_children", ("Children", "Hijos"), "Family: Children", "ds_child", req=True, max=20, fill_extra={"birth_city": "birth_city", "birth_state": "birth_state", "birth_country": "birth_country"})
    b.ceac["k_children"] = {"sec": b.sec, "label": "Children", "n": len(b.ceac), "t": "records", "dk": ["birth_city"], "kind": "children"}
    only_if(b, "k_children", ("k_has", "equals", "yes"))

    # ================================================================== PREVIOUS U.S. TRAVEL
    sec(b, "Previous U.S. Travel")
    page(b, "us_travel", ("Previous U.S. travel", "Viajes anteriores a EE. UU."), group="travel", ctx="applicant")
    yn(b, "t_been", ("Has the applicant ever been in the U.S.?", "¿El solicitante ha estado alguna vez en EE. UU.?"), cx={"q": "Have you ever been in the U.S.?", "t": "yn"})
    b.field("t_arn", "single_choice", ("Was the applicant ever issued an Alien Registration Number by the Department of Homeland Security?", "¿Alguna vez el Departamento de Seguridad Nacional le asignó al solicitante un Número de Registro de Extranjero?"), req=True,
            opts=T.YES_NO_UNSURE, help=WHERE_ARN, cx={"q": "Were you issued an Alien Registration Number by the Department of Homeland Security?", "t": "choice"})
    records(b, "t_visits", ("Last five U.S. visits", "Últimas cinco visitas a EE. UU."), "Previous U.S. Travel — Last five U.S. visits (Date Arrived, Length of Stay)", "ds_visit", max=5, req=True,
            help=("If you are unsure of the dates, give your best estimate.", "Si no estás seguro(a) de las fechas, da tu mejor estimación."))
    b.ceac["t_visits"] = {"sec": b.sec, "label": "Information on your last five U.S. visits", "n": len(b.ceac), "t": "records"}
    for n in ("t_arn", "t_visits"):
        only_if(b, n, ("t_been", "equals", "yes"))
    yn(b, "t_visa", ("Has the applicant ever been issued a U.S. visa?", "¿Alguna vez se le emitió al solicitante una visa de EE. UU.?"), cx={"q": "Have you ever been issued a U.S. Visa?", "t": "yn"})
    b.field("t_visa_date", "date", ("Date the last visa was issued", "Fecha en que se emitió la última visa"), req=True, date_rule="past", width="half", cx={"q": "Date Visa Was Issued", "t": "date"})
    b.field("t_visa_class", "short_answer", ("Visa classification (leave blank if you do not know)", "Clasificación de la visa (deja en blanco si no la sabes)"), maxlen=10, width="half", cx={"q": "Visa Classification", "t": "proper", "dk": True})
    b.field("t_visa_number", "short_answer", ("Visa number (leave blank if you do not know)", "Número de la visa (deja en blanco si no lo sabes)"), maxlen=20, width="half", cx={"q": "Visa Number", "t": "proper", "dk": True})
    yn(b, "t_visa_lost", ("Have any of the applicant's U.S. visas ever been lost or stolen?", "¿Alguna visa de EE. UU. del solicitante se ha perdido o ha sido robada?"), cx={"q": "Have any of your U.S. visas ever been lost or stolen?", "t": "yn"})
    yn(b, "t_visa_cancel", ("Have any of the applicant's U.S. visas ever been cancelled or revoked?", "¿Alguna visa de EE. UU. del solicitante ha sido cancelada o revocada?"), cx={"q": "Have any of your U.S. visas ever been cancelled or revoked?", "t": "yn"})
    for n in ("t_visa_date", "t_visa_class", "t_visa_number", "t_visa_lost", "t_visa_cancel"):
        only_if(b, n, ("t_visa", "equals", "yes"))
    yn(b, "t_refused", ("Has the applicant ever been refused a U.S. visa, been refused admission to the United States, or withdrawn an application for admission at the port of entry?", "¿Alguna vez se le negó al solicitante una visa de EE. UU., se le negó la admisión a Estados Unidos o retiró una solicitud de admisión en el puerto de entrada?"),
       cx={"q": "Have you ever been refused a U.S. Visa, been refused admission to the United States, or withdrawn your application for admission at the port of entry?", "t": "yn"})
    explain(b, "t_refused_explain", "t_refused", label=("What happened? (when, where, and why, as far as you know)", "¿Qué pasó? (cuándo, dónde y por qué, hasta donde sepas)"), cx={"q": "Explain"}, sens=True)

    # ================================================================== WORK / EDUCATION / TRAINING
    sec(b, "Work/Education/Training: Present")
    page(b, "work_present", ("Present work, education or training", "Trabajo, estudios o capacitación actuales"), ("For an applicant over 14. Choose what best describes what the applicant does now.", "Para un solicitante mayor de 14 años. Elige lo que mejor describe lo que hace el solicitante ahora."), group="work", ctx="applicant")
    b.field("w_occ", "dropdown", ("Primary occupation", "Ocupación principal"), req=True, opts=T.OCCUPATIONS, cx={"q": "Primary Occupation", "t": "choice"})
    b.field("w_occ_other", "short_answer", ("Specify other occupation", "Especifica la otra ocupación"), req=True, maxlen=60, cx={"q": "Specify Other", "t": "free"})
    only_if(b, "w_occ_other", ("w_occ", "equals", "other"))
    show_page_any(b, "work_present", [[("c_age14", "equals", "yes")]])
    page(b, "work_employer", ("Present employer or school", "Empleador o escuela actual"), group="work", ctx="applicant")
    b.field("w_employer", "short_answer", ("Present employer or school name", "Nombre del empleador o escuela actual"), req=True, maxlen=80, cx={"q": "Present Employer or School Name", "t": "proper"})
    addr(b, "pw", "Work/Education/Training: Present — Employer or School Address")
    b.field("w_start", "date", ("Start date", "Fecha de inicio"), date_rule="past", width="half", cx={"q": "Start Date", "t": "date", "dna": True})
    b.field("w_income", "short_answer", ("Monthly income in local currency (if any)", "Ingreso mensual en moneda local (si tiene)"), maxlen=20, width="half", cx={"q": "Monthly Income in Local Currency", "t": "raw", "dna": True})
    b.field("w_duties", "long_answer", ("Briefly describe your duties", "Describe brevemente tus funciones"), maxlen=300, cx={"q": "Briefly Describe Your Duties", "t": "free"})
    show_page_any(b, "work_employer", [[("c_age14", "equals", "yes"), ("w_occ", "equals", occ)] for occ, _en, _es in T.OCCUPATIONS if occ not in T.OCC_NO_EMPLOYER])
    page(b, "work_intend", ("Work in the U.S. and other occupations", "Trabajo en EE. UU. y otras ocupaciones"), group="work", ctx="applicant")
    b.field("w_intend", "dropdown", ("Occupation the applicant intends to have in the U.S.", "Ocupación que el solicitante piensa tener en EE. UU."), req=True, opts=T.OCCUPATIONS, cx={"q": "In which occupation do you intend to work in the U.S.?", "t": "choice"})
    b.field("w_intend_other", "short_answer", ("Specify other occupation", "Especifica la otra ocupación"), req=True, maxlen=60, cx={"q": "Specify Other", "t": "free"})
    only_if(b, "w_intend_other", ("w_intend", "equals", "other"))
    yn(b, "w_other_has", ("Does the applicant have other occupations?", "¿El solicitante tiene otras ocupaciones?"), cx={"q": "Do you have other occupations?", "t": "yn"})
    records(b, "w_other_occ", ("Other occupations", "Otras ocupaciones"), "Work/Education/Training: Present — Other Occupation", "ds_other_occ", max=10, req=True)
    b.ceac["w_other_occ"] = {"sec": b.sec, "label": "Other Occupation", "n": len(b.ceac), "t": "records"}
    only_if(b, "w_other_occ", ("w_other_has", "equals", "yes"))
    show_page_any(b, "work_intend", [[("c_age14", "equals", "yes")]])

    sec(b, "Work/Education/Training: Previous")
    page(b, "work_prev", ("Previous work and education", "Trabajos y estudios anteriores"),
         ("The 2019 sample shows this only to some applicants; OG asks everyone and confirms with CEAC what is needed.", "El ejemplo de 2019 lo muestra solo a algunos solicitantes; OG lo pregunta a todos y confirma con CEAC qué se necesita."), group="work", ctx="applicant")
    yn(b, "pv_has_job", ("Was the applicant previously employed?", "¿El solicitante tuvo empleos anteriores?"), cx={"q": "Were you previously employed?", "t": "yn", "unv": "shown only to some applicants in the 2019 sample (visibility rule unverified)"})
    records(b, "pv_jobs", ("Employers from the last ten years, most recent first", "Empleadores de los últimos diez años, el más reciente primero"), "Work/Education/Training: Previous — Previous employers", "ds_prev_job", max=15, req=True)
    b.ceac["pv_jobs"] = {"sec": b.sec, "label": "Previous employers (last ten years)", "n": len(b.ceac), "t": "records", "dk": ["sup_family", "sup_given"]}
    only_if(b, "pv_jobs", ("pv_has_job", "equals", "yes"))
    yn(b, "pv_has_school", ("Has the applicant attended any educational institution at a secondary level or above?", "¿El solicitante ha asistido a alguna institución educativa de nivel secundario o superior?"), cx={"q": "Have you attended any educational institutions at a secondary level or above?", "t": "yn"})
    records(b, "pv_schools", ("Educational institutions", "Instituciones educativas"), "Work/Education/Training: Previous — Educational institutions", "ds_school", max=15, req=True)
    b.ceac["pv_schools"] = {"sec": b.sec, "label": "Educational institutions attended", "n": len(b.ceac), "t": "records"}
    only_if(b, "pv_schools", ("pv_has_school", "equals", "yes"))
    show_page_any(b, "work_prev", [[("c_age14", "equals", "yes")]])

    sec(b, "Work/Education/Training: Additional")
    page(b, "work_more", ("Additional work, education and training", "Trabajo, estudios y capacitación adicionales"), group="work", ctx="applicant")
    yn(b, "aw_travel", ("Has the applicant traveled to any countries or regions other than the United States within the last fifteen years?", "¿El solicitante ha viajado a algún país o región distinto de Estados Unidos en los últimos quince años?"),
       cx={"q": "Have you traveled to any countries/regions, other than the United States, within the last fifteen years?", "t": "yn", "unv": "2019 sample says five years; Federal Register 2025-20231 says fifteen (newer source used)"})
    records(b, "aw_countries", ("Countries or regions visited", "Países o regiones visitados"), "Work/Education/Training: Additional — Countries/Regions Visited", "ds_country", max=40, req=True)
    b.ceac["aw_countries"] = {"sec": b.sec, "label": "Countries/Regions Visited", "n": len(b.ceac), "t": "records"}
    only_if(b, "aw_countries", ("aw_travel", "equals", "yes"))
    yn(b, "aw_mil", ("Has the applicant ever served in the military?", "¿El solicitante ha servido alguna vez en el ejército?"), cx={"q": "Have you ever served in the military?", "t": "yn"})
    records(b, "aw_mil_rec", ("Military service", "Servicio militar"), "Work/Education/Training: Additional — Military service", "ds_military", max=5, req=True)
    b.ceac["aw_mil_rec"] = {"sec": b.sec, "label": "Military service (country, branch, rank, specialty, dates)", "n": len(b.ceac), "t": "records"}
    only_if(b, "aw_mil_rec", ("aw_mil", "equals", "yes"))
    private(b, "aw_mil", "aw_mil_rec")
    yn(b, "aw_org", ("Has the applicant belonged to, contributed to, or worked for any professional, social, or charitable organization?", "¿El solicitante ha pertenecido, contribuido o trabajado para alguna organización profesional, social o benéfica?"),
       cx={"q": "Have you belonged to, contributed to, or worked for any professional, social, or charitable organization?", "t": "yn", "unv": "shown only to some applicants in the 2019 sample"})
    records(b, "aw_org_rec", ("Organizations", "Organizaciones"), "Work/Education/Training: Additional — Organization Name", "ds_org", max=15, req=True)
    b.ceac["aw_org_rec"] = {"sec": b.sec, "label": "Organization Name", "n": len(b.ceac), "t": "records"}
    only_if(b, "aw_org_rec", ("aw_org", "equals", "yes"))
    private(b, "aw_org", "aw_org_rec")
    yn(b, "aw_skills", ("Does the applicant have any specialized skills or training, such as firearms, explosives, nuclear, biological, or chemical experience?", "¿El solicitante tiene habilidades o capacitación especializadas, como experiencia con armas de fuego, explosivos, o nuclear, biológica o química?"),
       cx={"q": "Do you have any specialized skills or training, such as firearms, explosives, nuclear, biological, or chemical experience?", "t": "yn", "unv": "shown only to some applicants in the 2019 sample"})
    explain(b, "aw_skills_explain", "aw_skills", label=("Explain the skills or training", "Explica las habilidades o la capacitación"), cx={"q": "Explain Skills or Training"}, sens=True)
    yn(b, "aw_para", ("Has the applicant ever served in, been a member of, or been involved with a paramilitary unit, vigilante unit, rebel group, guerrilla group, or insurgent organization?", "¿El solicitante ha servido, ha sido miembro o ha estado involucrado con una unidad paramilitar, unidad de vigilantes, grupo rebelde, guerrillero u organización insurgente?"),
       cx={"q": "Have you ever served in, been a member of, or been involved with a paramilitary unit, vigilante unit, rebel group, guerrilla group, or insurgent organization?", "t": "yn", "unv": "shown only to some applicants in the 2019 sample"})
    explain(b, "aw_para_explain", "aw_para", cx={"q": "Explain"}, sens=True)
    yn(b, "aw_lang", ("Can the applicant speak or read languages other than their native language?", "¿El solicitante habla o lee idiomas distintos de su idioma nativo?"), cx={"q": "Can you speak and/or read languages other than your native language?", "t": "yn", "unv": "shown only to some applicants in the 2019 sample"})
    b.field("aw_languages", "long_answer", ("List the languages the applicant speaks or reads", "Indica los idiomas que el solicitante habla o lee"), req=True, maxlen=200, cx={"q": "List the languages that you speak and/or read", "t": "free"})
    only_if(b, "aw_languages", ("aw_lang", "equals", "yes"))
    private(b, "aw_para")
    show_page_any(b, "work_more", [[("c_age14", "equals", "yes")]])

    # ================================================================== PETITIONER
    sec(b, "Petitioner")
    page(b, "pet_rel", ("Who filed the petition?", "¿Quién presentó la petición?"), ("The individual or business that filed a petition on the applicant's behalf.", "La persona o empresa que presentó una petición en nombre del solicitante."), group="petitioner", ctx="petitioner")
    b.field("pt_relation", "dropdown", ("The petitioner is my…", "El peticionario es mi…"), req=True, opts=T.PETITIONER_RELATIONS, cx={"q": "Petitioner is my", "t": "choice"})
    b.field("pt_other", "short_answer", ("Specify other", "Especifica otro"), req=True, maxlen=60, cx={"q": "Specify Other", "t": "free"})
    only_if(b, "pt_other", ("pt_relation", "equals", "other"))
    ind = sorted(T.PETITIONER_INDIVIDUAL - {"other"})
    org = ["employer", "prospective_employer", "other"]

    def edit_pt_name():
        b.field("pt_family", "short_answer", ("Petitioner's surnames", "Apellidos del peticionario"), req=True, width="half", maxlen=60, cx={"q": "Petitioner Surnames", "t": "name"})
        b.field("pt_given", "short_answer", ("Petitioner's given names", "Nombres del peticionario"), req=True, width="half", maxlen=60, cx={"q": "Petitioner Given Names", "t": "name"})
        mark_block_fields(b, "sb_pt_name", ["pt_family", "pt_given"])
    block_pair(b, "sb_pt_name", group="petitioner", form_name="DS-260", ctx="petitioner", gates=[[("pt_relation", "equals", r)] for r in ind], review_title=("We already have the petitioner's name", "Ya tenemos el nombre del peticionario"),
               review_desc=("Confirm it or change it.", "Confírmalo o cámbialo."), edit_title=("The petitioner", "El peticionario"), edit_desc=None, build_edit=edit_pt_name)

    def edit_pt_address():
        addr(b, "pta", "Petitioner — Address and Phone Number of Petitioner")
        mark_block_fields(b, "sb_pt_address", [n for n in b.fields if n.startswith("pta_")])
    block_pair(b, "sb_pt_address", group="petitioner", form_name="DS-260", ctx="petitioner", gates=[[("pt_relation", "equals", r)] for r in ind], review_title=("The petitioner's address", "Dirección del peticionario"),
               review_desc=("Addresses change. Is this still current?", "Las direcciones cambian. ¿Sigue vigente?"), edit_title=("The petitioner's address", "Dirección del peticionario"), edit_desc=None, build_edit=edit_pt_address)

    def edit_pt_contact():
        b.field("pt_phone", "phone", ("Petitioner's telephone", "Teléfono del peticionario"), req=True, width="half", cx={"q": "Telephone", "t": "phone"})
        b.field("pt_mobile", "phone", ("Petitioner's mobile/cell telephone (if any)", "Teléfono móvil del peticionario (si tiene)"), width="half", cx={"q": "Mobile/Cell Telephone", "t": "phone", "dna": True})
        b.field("pt_email", "email", ("Petitioner's email address (if any)", "Correo electrónico del peticionario (si tiene)"), cx={"q": "Email Address", "t": "raw", "dna": True})
        mark_block_fields(b, "sb_pt_contact", ["pt_phone", "pt_mobile", "pt_email"])
    block_pair(b, "sb_pt_contact", group="petitioner", form_name="DS-260", ctx="petitioner", gates=[[("pt_relation", "equals", r)] for r in ind], review_title=("The petitioner's contact information", "Información de contacto del peticionario"),
               review_desc=("Is it still current?", "¿Sigue vigente?"), edit_title=("The petitioner's telephone and email", "Teléfono y correo del peticionario"), edit_desc=None, build_edit=edit_pt_contact)
    page(b, "pet_org", ("The petitioning business or organization", "La empresa u organización peticionaria"), group="petitioner", ctx="petitioner")
    b.field("pt_org", "short_answer", ("Organization name", "Nombre de la organización"), req=True, maxlen=80, cx={"q": "Organization Name", "t": "proper"})
    addr(b, "pto", "Petitioner — Address and Phone Number of Petitioner (organization)")
    b.field("pto_phone", "phone", ("Telephone", "Teléfono"), req=True, width="half", cx={"q": "Telephone", "t": "phone"})
    b.field("pto_mobile", "phone", ("Mobile/cell telephone (if any)", "Teléfono móvil (si tiene)"), width="half", cx={"q": "Mobile/Cell Telephone", "t": "phone", "dna": True})
    b.field("pto_email", "email", ("Email address (if any)", "Correo electrónico (si tiene)"), cx={"q": "Email Address", "t": "raw", "dna": True})
    show_page_any(b, "pet_org", [[("pt_relation", "equals", r)] for r in org])
    page(b, "pet_self", ("Petition filed by the applicant", "Petición presentada por el propio solicitante"), group="petitioner", ctx="petitioner")
    para(b, "pet_self_note", "You chose that the applicant filed the petition. No other petitioner details are needed here.", "Elegiste que el propio solicitante presentó la petición. Aquí no se necesitan más datos del peticionario.")
    show_page_any(b, "pet_self", [[("pt_relation", "equals", "self")]])

    # ================================================================== SECURITY & BACKGROUND
    for gkey, ceac_sec, title_en, title_es, questions in T.SECURITY_GROUPS:
        sec(b, ceac_sec)
        page(b, f"sec_{gkey}", (title_en, title_es), group="security", ctx="applicant")
        para(b, f"sec_{gkey}_note", *T.SECURITY_NOTE, cls="text-[13px] leading-relaxed text-slate-600")
        for key, en, es, polarity in questions:
            b.field(key, "single_choice", (en, es), req=True, opts=YES_NO, cx={"q": en, "t": "yn", "sec_key": True, "polarity": polarity})
            private(b, key)
            if key in T.SEC_NOTES:
                b.fields[key].source_note = T.SEC_NOTES[key]
            b.field(f"{key}_x", "long_answer", ("Please explain", "Explica"), req=True, maxlen=3000, cx={"q": "Explain", "t": "free", "follows": key})
            private(b, f"{key}_x")
            b.rule("show_field", f"{key}_x", [(key, "equals", "yes" if polarity == "yes" else "no")])
            if key in T.SECURITY_IN_US_ONLY:
                only_if(b, key, ("t_been", "equals", "yes"))
        if gkey == "immig2":
            show_page_any(b, f"sec_{gkey}", [[("t_been", "equals", "yes")]])

    # ================================================================== SOCIAL SECURITY
    sec(b, "Social Security Number")
    page(b, "ssn", ("Social Security number", "Número de Seguro Social"), ("As on the Department of State application. Do not give an ITIN here.", "Como en la solicitud del Departamento de Estado. No des un ITIN aquí."), group="ssn", ctx="applicant")
    yn(b, "ssn_applied", ("Has the applicant ever applied for a Social Security number?", "¿El solicitante ha solicitado alguna vez un número de Seguro Social?"), cx={"q": "Have you ever applied for a Social Security number?", "t": "yn"})
    yn(b, "ssn_issued", ("Was the applicant issued a number?", "¿Se le asignó un número al solicitante?"), cx={"q": "Were you issued a number?", "t": "yn"})
    only_if(b, "ssn_issued", ("ssn_applied", "equals", "yes"))
    b.field("ssn_number", "short_answer", ("Social Security number", "Número de Seguro Social"), sensitive=True, width="half", pattern=r"\d{3}-?\d{2}-?\d{4}", msg=("Enter 9 digits.", "Ingresa 9 dígitos."), cx={"q": "Social Security Number", "t": "ssn", "dk": True})
    where(b, "ssn_number", *WHERE_SSN)
    b.field("ssn_dk", "multi_choice", ("I do not know the number", "No sé el número"), opts=[("dk", "I do not know the number", "No sé el número")], cx={"q": "Do Not Know (Social Security number)", "t": "choice"})
    yn(b, "ssn_card", ("Does the applicant need a new card issued?", "¿El solicitante necesita que se le emita una tarjeta nueva?"), cx={"q": "Do you need a new card issued?", "t": "yn"})
    for n in ("ssn_number", "ssn_dk", "ssn_card"):
        only_if(b, n, ("ssn_applied", "equals", "yes"), ("ssn_issued", "equals", "yes"))
    yn(b, "ssn_want", ("Does the applicant want the Social Security Administration to issue a number and a card?", "¿El solicitante quiere que la Administración del Seguro Social le asigne un número y una tarjeta?"), cx={"q": "Do you want the Social Security Administration to issue a Social Security number and a card?", "t": "yn"})
    b.rule("show_field", "ssn_want", [("ssn_applied", "equals", "no")])
    b.rule("show_field", "ssn_want", [("ssn_applied", "equals", "yes"), ("ssn_issued", "equals", "no")])
    b.field("ssn_consent", "single_choice", ("Does the applicant authorize disclosure of information from the DS-260 to the Department of Homeland Security, the Social Security Administration, and such other U.S. Government agencies as may be required for the purposes of assigning a Social Security number (SSN) and issuing a Social Security card, and authorize the Social Security Administration to share the SSN with the Department of Homeland Security?",
                                                    "¿El solicitante autoriza la divulgación de la información del DS-260 al Departamento de Seguridad Nacional, a la Administración del Seguro Social y a otras agencias del Gobierno de EE. UU. que se requieran para asignar un número de Seguro Social (SSN) y emitir una tarjeta de Seguro Social, y autoriza a la Administración del Seguro Social a compartir el SSN con el Departamento de Seguridad Nacional?"),
            req=True, opts=YES_NO, help=("This is the applicant's own decision: OG never assumes it. As on the Department of State application, if the answer is No the applicant will not receive a Social Security card.", "Es una decisión del propio solicitante: OG nunca la asume. Como en la solicitud del Departamento de Estado, si la respuesta es No el solicitante no recibirá una tarjeta de Seguro Social."),
            cx={"q": "Do you authorize disclosure of information from this form to the Department of Homeland Security, the Social Security Administration...?", "t": "yn"})
    private(b, "ssn_number")

    # ================================================================== WHO HELPED YOU (preparer)
    sec(b, "Sign and Submit (preparer of application)")
    page(b, "assist", ("Who helped with this application?", "¿Quién ayudó con esta solicitud?"), group="assist", ctx="applicant")
    dyn(b, "assist_card", "ds_assist")
    b.field("as_helped", "single_choice", ("Did anyone assist the applicant in filling out this application?", "¿Alguien ayudó al solicitante a llenar esta solicitud?"), req=True,
            opts=[("yes", "Yes — OG Multiservices prepared it with me", "Sí — OG Multiservices lo preparó conmigo"), ("yes_other", "Yes — someone else also helped", "Sí — otra persona también ayudó"), ("no", "No", "No")],
            cx={"q": "Did anyone assist you in filling out this application?", "t": "choice"})
    b.field("as_other_name", "short_answer", ("Name of the other person who helped", "Nombre de la otra persona que ayudó"), req=True, maxlen=80, cx={"q": "Preparer (other)", "t": "name"})
    b.field("as_other_rel", "short_answer", ("Relationship to the applicant", "Relación con el solicitante"), req=True, maxlen=60, cx={"q": "Relationship to You", "t": "free"})
    for n in ("as_other_name", "as_other_rel"):
        only_if(b, n, ("as_helped", "equals", "yes_other"))
    para(b, "assist_cert", T.SIGN_CERT_EN + " " + T.CEAC_ONLY_NOTE[0], T.SIGN_CERT_ES + " " + T.CEAC_ONLY_NOTE[1], "text-[13px] leading-relaxed text-slate-600")

    # ================================================================== documents
    page(b, "documents", ("Documents", "Documentos"), ("Documents are kept once in your case, so a document OG already has is not asked for again.", "Los documentos se guardan una sola vez en tu caso, así que un documento que OG ya tiene no se vuelve a pedir."), group="documents", ctx="applicant")
    b.field("docs_scope_note", "paragraph", ("", ""), content=(
        _label("What OG asks for", "These are OG's requests to prepare the DS-260 and your civil documents. The National Visa Center (NVC) tells each case which documents it needs; OG confirms what applies to you."),
        _label("Lo que pide OG", "Son solicitudes de OG para preparar el DS-260 y tus documentos civiles. El Centro Nacional de Visas (NVC) indica a cada caso qué documentos necesita; OG confirmará lo que aplica en tu caso.")))
    dyn(b, "docs_list", "documents")
    b.field("docs_tip", "paragraph", ("", ""), content=(
        _tip("Make sure each document is complete, readable, well lit and not cropped or blurry. A document that is not in English may need a certified translation — OG can help."),
        _tip("Asegúrate de que cada documento esté completo, legible, bien iluminado y sin cortes ni desenfoque. Un documento que no esté en inglés puede necesitar una traducción certificada; OG puede ayudarte.")))

    # ================================================================== confirm
    page(b, "confirm", ("Confirm and Send to OG", "Confirma y envía a OG"), group="confirm", ctx="applicant",
         desc=("Review your information and confirm that it is complete and accurate. OG will use it to prepare the DS-260 answers for CEAC.", "Revisa tu información y confirma que esté completa y correcta. OG la usará para preparar las respuestas del DS-260 para CEAC."))
    note(b, "confirm_warning", "Sending this to OG is not a CEAC submission, is not an electronic signature or certification, and is not receipt by the National Visa Center. OG will review your answers and tell you when they are ready to be entered in CEAC. " + T.CEAC_ONLY_NOTE[0],
         "Enviar esto a OG no es enviar a CEAC, no es una firma electrónica ni una certificación, y no es recibo por parte del Centro Nacional de Visas. OG revisará tus respuestas y te avisará cuándo estén listas para ingresarse en CEAC. " + T.CEAC_ONLY_NOTE[1])
    b.field("c_prepare", "consent", ("Request for preparation", "Solicitud de preparación"), ref="OG confirmation", req=True, note="Customer confirmation only; not a signature.",
            content=("I ask OG Multiservices to prepare the DS-260 answers based only on the information provided or authorized.", "Solicito a OG Multiservices que prepare las respuestas del DS-260 con base únicamente en la información proporcionada o autorizada."))
    b.field("c_accurate", "consent", ("Accuracy confirmation", "Confirmación de exactitud"), ref="OG confirmation", req=True, note="Customer confirmation only; not the CEAC certification under penalty of perjury.",
            content=("I confirm that the information is complete and correct to the best of my knowledge. I understand that only I can sign and submit the DS-260 in CEAC, and that answers are prepared in English for CEAC.",
                     "Confirmo que la información es completa y correcta según mi leal saber y entender. Entiendo que solo yo puedo firmar y enviar el DS-260 en CEAC, y que las respuestas se preparan en inglés para CEAC."))
    b.field("c_no_creds", "consent", ("No passwords shared", "No compartí contraseñas"), ref="OG confirmation", req=True, note="Customer acknowledgement; OG never asks for CEAC or email passwords.",
            content=("I have not given OG a CEAC password, an email password or any login, and I understand OG will never ask for them.", "No le he dado a OG una contraseña de CEAC, de mi correo ni ningún acceso, y entiendo que OG nunca los pedirá."))
    return b


def _features(ceac):
    return {
        "completeness_check": True, "consistency": "ds260", "documents_check": True,
        "review_groups": {"security": {"en": "Review", "es": "Revisar"}}, "review_documents": True,
        "sections": SECTIONS, "contexts": CONTEXTS, "context_roles": CONTEXT_ROLES,
        "name_tokens": {"ap": {"role": "visa_applicant", "fallback": {"en": "the applicant", "es": "el solicitante"}}, "pt": {"role": "petitioner", "fallback": {"en": "the petitioner", "es": "el peticionario"}}},
        "sync": [
            {"kind": "ds260_calc"},
            {"kind": "current_address", "record_field": "a_addr_history", "prefix": "pa", "start_field": "pa_since", "create_present": True},
            {"kind": "person_records", "fields": ["pf_records", "pm_records", "s_records", "ps_records", "k_children"]},
            {"kind": "requirements_ds260"},
        ],
        "ceac": ceac,
    }


def ensure_ds260_intake():
    """Create the production DS-260 intake and its Consular Processing service (idempotent; never rebuilt over submissions)."""
    if Form.query.filter_by(slug=DS260_SLUG).first():
        return False
    category = ServiceCategory.query.filter_by(slug="immigration").first()
    if category is None:
        return False
    service = Service.query.filter_by(category_id=category.id, slug="immigrant-visa-ds-260").first()
    if service is None:
        top = db.session.query(db.func.max(Service.sort_order)).filter(Service.category_id == category.id).scalar() or 0
        service = Service(
            category_id=category.id, slug="immigrant-visa-ds-260", admin_name="Consular Processing — Immigrant Visa Application (DS-260) Preparation", icon="immigration", is_published=True, sort_order=top + 10,
            title_en="Immigrant Visa Application (DS-260)", title_es="Solicitud de visa de inmigrante (DS-260)",
            short_en="Document preparation support for the Department of State's DS-260 immigrant visa application, one for each family member who applies.",
            short_es="Apoyo en la preparación de documentos para la solicitud de visa de inmigrante DS-260 del Departamento de Estado, una para cada familiar que solicita.",
            hero_text_en="Organize the information for each immigrant visa applicant once, and get answers prepared for the Department of State's online system (CEAC).",
            hero_text_es="Organiza la información de cada solicitante de visa de inmigrante una sola vez y prepara las respuestas para el sistema en línea del Departamento de Estado (CEAC).",
            content_title_en="What is the DS-260?", content_title_es="¿Qué es el DS-260?",
            content_en="<p>The DS-260, Immigrant Visa and Alien Registration Application, is the online form each person applying for an immigrant visa completes in the Department of State's Consular Electronic Application Center (CEAC), after the National Visa Center opens the case. OG Multiservices helps you gather and organize the information for each applicant and prepares English answers for CEAC. The applicant reviews, signs and submits the application in CEAC personally. OG provides document preparation and administrative assistance only; we are not a law firm and do not provide legal advice.</p>",
            content_es="<p>El DS-260, Solicitud de Visa de Inmigrante y Registro de Extranjero, es el formulario en línea que completa cada persona que solicita una visa de inmigrante en el Centro Electrónico de Solicitudes Consulares (CEAC) del Departamento de Estado, una vez que el Centro Nacional de Visas abre el caso. OG Multiservices te ayuda a reunir y organizar la información de cada solicitante y prepara respuestas en inglés para CEAC. El solicitante revisa, firma y envía la solicitud en CEAC personalmente. OG ofrece solo preparación de documentos y asistencia administrativa; no somos un bufete de abogados ni brindamos asesoría legal.</p>",
            nj_in_person=True, remote_nationwide=True)
        db.session.add(service)
        db.session.flush()
    form = Form(slug=DS260_SLUG, name_admin="DS-260 Client Intake")
    db.session.add(form)
    form.form_type = "service_intake"
    form.status = "published"
    form.source_form_name = SOURCE_NAME
    form.source_edition = SOURCE_EDITION
    form.version = 1
    form.published_at = datetime.utcnow()
    form.title_en, form.title_es = "Immigrant Visa Application — DS-260", "Solicitud de visa de inmigrante — DS-260"
    form.description_en = "Guided intake for OG Multiservices to prepare one DS-260 for one visa applicant. Your progress is saved automatically."
    form.description_es = "Solicitud guiada para que OG Multiservices prepare un DS-260 para un solicitante de visa. Tu progreso se guarda automáticamente."
    form.submit_label_en, form.submit_label_es = "Send to OG", "Enviar a OG"
    form.success_message_en = "OG Multiservices has your information and will review it. This is not a CEAC submission. We'll contact you if we need anything else."
    form.success_message_es = "OG Multiservices tiene tu información y la revisará. Esto no es un envío a CEAC. Te contactaremos si necesitamos algo más."
    form.show_progress = True
    form.features_json = json.dumps({}, ensure_ascii=False)
    db.session.flush()
    b = build_ds260(form)
    _finalize_ceac(b, form)
    db.session.flush()
    service.requires_intake = True
    service.form_id = form.id
    service.requires_account = True
    service.intake_label = "DS-260 Client Intake"
    db.session.commit()
    from app.ds260_source import CURRENT_CODE, ensure_snapshot, registry_from_form

    ensure_snapshot(CURRENT_CODE, registry_from_form(form))
    return True


def _finalize_ceac(b, form):
    """Drop CEAC entries of system fields, stamp the features (incl. the CEAC map) on the form."""
    ceac = {}
    for name, meta in b.ceac.items():
        f = b.fields.get(name)
        cfgj = json.loads(f.config_json) if f is not None and f.config_json else {}
        if cfgj.get("system") or name.endswith("_avail") or name.endswith("_missing"):
            continue
        ceac[name] = meta
    form.features_json = json.dumps(_features(ceac), ensure_ascii=False)
