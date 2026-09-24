"""Form I-751 Client Intake — the seventh production Smart Intake, built natively on the Case + Person architecture.

SOURCE OF TRUTH: the supplied USCIS "Form I-751, Petition to Remove Conditions on Residence", Edition 04/01/24 (OMB No. 1615-0038, expires 03/31/2027),
11 pages, Parts 1-11. Item numbers are the ones printed on that PDF; every question carries its Part/Item in `FormField.source_ref` (admin-only).

Part map (as printed):
  Part 1   Information About You, the Conditional Resident   Items 1.a-1.c name · 2-3 other names · 4 DOB · 5 country of birth · 6 citizenship · 7 A-Number
                                                             · 8 SSN · 9 USCIS account · 10 marital status · 11 date of marriage · 12 place of marriage
                                                             · 13 date the marriage ended · 14 conditional residence expires · 15.a-15.f mailing address
                                                             · 16 physical different? · 17.a-17.f physical address · 18 proceedings · 19 fee to non-attorney
                                                             · 20 arrests · 21 different marriage? · 22 other addresses since permanent residence · 23 spouse serving abroad
  Part 2   Biographic Information                            Items 1 ethnicity · 2 race · 3 height · 4 weight · 5 eye color · 6 hair color
  Part 3   Basis for Petition                                Items 1.a-1.b joint filing (select ONE) · 1.c-1.g waiver / individual filing (select ALL that apply)
  Part 4   The U.S. citizen or LPR spouse (or stepparent)    Item 1 relationship · 2.a-2.c name · 3 DOB · 4 SSN · 5 A-Number · 6.a-6.h physical address
  Part 5   Information About Your Children                   Child 1-5 = Items 1-30 (name, DOB, A-Number, living with you, applying with you, physical address); more go in Part 11
  Part 6   Accommodations                                    Items 1-3 (own / spouse's / included children's) · 4.a-4.c
  Part 7   Petitioner's statement, contact, ASC acknowledgement, certification, signature   1.a/1.b · 2 · 3-5 contact · 6 signature
  Part 8   Spouse's / individual's statement (if applicable) 1.a/1.b · 2 · 3-5 contact · 6 signature
  Part 9   Interpreter    Part 10  Preparer (OG)    Part 11  Additional Information

NOT customer questions: every signature and date of signature (Part 7 Item 6, Part 8 Item 6, Part 9 Item 6, Part 10 Item 8), the G-28 box and every
"For USCIS Use Only" box. Part 10 Item 7 (the preparer's statement) comes from the central OG configuration, never a customer answer. The Part 8
statement belongs to the Part 4 spouse: this intake records what the petitioner knows and never collects the spouse's certification or signature.

THE FILING BASIS (Part 3) IS NEVER DECIDED BY THIS INTAKE. It stores what the customer (or OG) says, in the printed boxes: exactly one joint-filing
box, OR any number of waiver / individual-filing boxes, OR "not sure — OG will review". No timeliness, good-faith, hardship or eligibility conclusion
is drawn anywhere. The Form I-751 Instructions (which list required evidence) are NOT part of the supplied PDF.

Flow note: the customer answers Part 3 (how they are filing) FIRST because it drives what else is asked (Part 4 relationship, Part 8, Item 21);
every question still carries its own Part/Item reference, so the interview order differs from the printed order without losing traceability.
"""

import json
from datetime import datetime

from app import i751_text as T
from app.extensions import db
from app.models import Form, Service, ServiceCategory
from app.seed_i130 import page, records, where
from app.seed_i485 import (UNSURE, WHERE_A, WHERE_ACCT, WHERE_SSN, YN_UNSURE, block_pair, choice, kp, mark_block_fields, only_if)
from app.seed_i90 import EYE, HAIR, STATE_OPTIONS, UNIT_TYPES, YES_NO, Builder, _address_fields
from app.seed_i90_refine import _label, _tip
from app.seed_n400 import note, show_any, show_page_any

I751_SLUG = "i-751-client-intake"
SOURCE_NAME = "I-751"
SOURCE_EDITION = "04/01/24"
NEVER = ("b_route", "equals", "__never__")

SECTIONS = [
    {"key": "before", "title": {"en": "Before You Begin", "es": "Antes de empezar"}},
    {"key": "basis", "title": {"en": "How You Are Filing", "es": "Cómo presentas"}},
    {"key": "resident", "title": {"en": "About the Conditional Resident", "es": "Sobre el residente condicional"}},
    {"key": "marriage", "title": {"en": "The Marriage & Conditional Residence", "es": "El matrimonio y la residencia condicional"}},
    {"key": "addresses", "title": {"en": "Addresses", "es": "Direcciones"}},
    {"key": "additional_q", "title": {"en": "Additional Questions", "es": "Preguntas adicionales"}},
    {"key": "bio", "title": {"en": "Biographic Information", "es": "Información biográfica"}},
    {"key": "spouse", "title": {"en": "The Spouse (or Parent's Spouse)", "es": "El cónyuge (o cónyuge del padre o la madre)"}},
    {"key": "children", "title": {"en": "Children", "es": "Hijos"}},
    {"key": "accommodations", "title": {"en": "Accommodations", "es": "Adaptaciones"}},
    {"key": "statement", "title": {"en": "Your Statement", "es": "Tu declaración"}},
    {"key": "part8", "title": {"en": "Your Spouse's Statement", "es": "La declaración de tu cónyuge"}},
    {"key": "interpreter", "title": {"en": "Interpreter", "es": "Intérprete"}},
    {"key": "preparer", "title": {"en": "Preparer", "es": "Preparador"}},
    {"key": "additional", "title": {"en": "Additional Information", "es": "Información adicional"}},
    {"key": "documents", "title": {"en": "Documents", "es": "Documentos"}},
    {"key": "confirm", "title": {"en": "Confirmation", "es": "Confirmación"}},
]
CONTEXTS = {
    "resident": {"title": {"en": "Conditional resident", "es": "Residente condicional"}, "subtitle": {"en": "The person who holds conditional permanent resident status.", "es": "La persona que tiene la residencia permanente condicional."},
                 "tone": "accent", "icon": "person"},
    "spouse": {"title": {"en": "Spouse or parent's spouse", "es": "Cónyuge o cónyuge del padre o la madre"},
               "subtitle": {"en": "The U.S. citizen or permanent resident through whom conditional residence was gained (Part 4).", "es": "El ciudadano de EE. UU. o residente permanente a través de quien se obtuvo la residencia condicional (Parte 4)."},
               "tone": "brand", "icon": "people"},
}
CONTEXT_ROLES = {"resident": "conditional_resident", "spouse": "relevant_individual"}

WHERE_RESIDENT_SINCE = ("Look at your conditional Permanent Resident Card: the date after “Resident Since” is the date you became a permanent resident. This is an OG helper, not a numbered item on the form.",
                        "Mira tu Tarjeta de Residente Permanente condicional: la fecha después de “Resident Since” es la fecha en que te hiciste residente permanente. Es una ayuda de OG, no un ítem numerado del formulario.")
WHERE_EXPIRES = ("It is printed on your conditional Permanent Resident Card as “Card Expires”. OG does not draw any conclusion from this date here; OG looks at the timing with you.",
                 "Está impresa en tu Tarjeta de Residente Permanente condicional como “Card Expires”. OG no saca aquí ninguna conclusión de esta fecha; OG revisa contigo los plazos.")

VERBATIM_NOTE = "Text as printed on Form I-751 edition 04/01/24; OG's Spanish is a courtesy translation."


def txt(en, es, cls="text-[15px] leading-relaxed text-slate-700"):
    return (f'<span class="block {cls}">{en}</span>', f'<span class="block {cls}">{es}</span>')


def para(b, name, en, es):
    b.field(name, "paragraph", ("", ""), content=(en, es))


def dyn(b, name, kind):
    b.field(name, "paragraph", ("", ""), content=("", ""))
    b.fields[name].config_json = json.dumps({"dynamic": {"kind": kind}})


def flag(b, name, **flags):
    f = b.fields[name]
    cfg = json.loads(f.config_json) if f.config_json else {}
    cfg.update(flags)
    f.config_json = json.dumps(cfg, ensure_ascii=False)


def private(b, *names):
    """Customer-visible only while the customer is working in the intake; hidden in later customer views (My Applications) and never in shared summaries."""
    for n in names:
        b.fields[n].is_sensitive = True
        flag(b, n, private=True)


def only_missing(b, key, names):
    """On a shared block's edit step, show a field only when it is the customer's turn to give it (nothing known, they chose to edit, or the case
    could not supply that detail). A confirmed value is never asked again."""
    from app.case_types import FORM_CASE_CONFIG

    block = FORM_CASE_CONFIG["I-751"]["blocks"][key]
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
    """A U.S. address (Part 1 Items 15 and 17 are U.S. addresses)."""
    if in_care_of:
        b.field(f"{prefix}_in_care_of", "short_answer", ("In care of name (if any)", "A cargo de (si aplica)"), ref=ref + " — In Care Of Name", maxlen=34)
    b.field(f"{prefix}_street", "short_answer", ("Street number and name", "Número y nombre de la calle"), ref=ref + " — Street Number and Name", req=required)
    b.field(f"{prefix}_unit_type", "dropdown", ("Unit type (if any)", "Tipo de unidad (si aplica)"), ref=ref + " — Apt./Ste./Flr.", opts=UNIT_TYPES, width="half")
    b.field(f"{prefix}_unit_number", "short_answer", ("Unit number", "Número de unidad"), ref=ref + " — Number", width="half")
    b.field(f"{prefix}_city", "short_answer", ("City or town", "Ciudad o pueblo"), ref=ref + " — City or Town", req=required)
    b.field(f"{prefix}_state", "dropdown", ("State", "Estado"), ref=ref + " — State", req=required, opts=STATE_OPTIONS, width="half")
    b.field(f"{prefix}_zip", "short_answer", ("ZIP code", "Código postal (ZIP)"), ref=ref + " — ZIP Code", req=required, width="half", pattern=r"\d{5}", maxlen=5,
            msg=("Enter a 5-digit ZIP code.", "Ingresa un ZIP de 5 dígitos."))


def calc_field(b, name, label, ref):
    """Hidden calculated / configured answer (never asked); kept, shown only in Review, Admin and the snapshot when it is not `system`."""
    b.field(name, "short_answer", (label, label), ref=ref, note="Calculated or configured by the platform; not a question.")
    kp(b, name, system=True)


def yesno(b, name, label, ref, *, req=True, help=None, note_=None):
    b.field(name, "single_choice", label, ref=ref, req=req, opts=YES_NO, help=help, note=note_)


def explain(b, name, ref, when_field, label=None, help=None, sensitive=False):
    b.field(name, "long_answer", label or ("Please explain your answer", "Explica tu respuesta"), ref=ref, req=True, maxlen=3000, help=help)
    b.rule("show_field", name, [(when_field, "equals", "yes")])
    if sensitive:
        private(b, name)


def _add_preparer_page(b):
    """PART 10 — the preparer (OG). INFORMATION only (Items 1-6); the statement (Item 7) is derived from the central configuration and the preparer's
    signature and date (Item 8) are never collected."""
    page(b, "preparer", ("Who prepares your petition", "Quién prepara tu petición"),
         ("OG Multiservices prepares this petition for you, so OG is listed as the preparer. These details come from OG's own settings — you normally do not need to change anything. OG does not sign for you, and the preparer's signature is handled by OG separately.",
          "OG Multiservices prepara esta petición por ti, así que OG figura como preparador. Estos datos vienen de la configuración propia de OG: normalmente no necesitas cambiar nada. OG no firma por ti, y la firma del preparador la maneja OG por separado."),
         group="preparer", ctx="resident")
    b.field("prep_family", "short_answer", ("Preparer's family name (last name)", "Apellido del preparador"), ref="Part 10, Item 1.a", req=True, width="half", maxlen=30)
    b.field("prep_given", "short_answer", ("Preparer's given name (first name)", "Nombre del preparador"), ref="Part 10, Item 1.b", req=True, width="half", maxlen=18)
    b.field("prep_org", "short_answer", ("Preparer's business or organization name (if any)", "Empresa u organización del preparador (si aplica)"), ref="Part 10, Item 2", maxlen=38)
    _address_fields(b, "prep", "Part 10, Item 3 (Preparer's Mailing Address, 3.a–3.h)")
    b.field("prep_phone", "phone", ("Preparer's daytime telephone number", "Teléfono de día del preparador"), ref="Part 10, Item 4", req=True, width="half")
    b.field("prep_fax", "phone", ("Preparer's fax number (if any)", "Fax del preparador (si tiene)"), ref="Part 10, Item 5", width="half")
    b.field("prep_email", "email", ("Preparer's email address (if any)", "Correo electrónico del preparador (si tiene)"), ref="Part 10, Item 6")
    b.fields["prep_email"].required = False
    defaults = {"prep_family": "@biz:PREPARER_LAST_NAME", "prep_given": "@biz:PREPARER_FIRST_NAME", "prep_org": "@biz:PREPARER_ORG", "prep_phone": "@biz:PREPARER_PHONE",
                "prep_fax": "@biz:PREPARER_FAX", "prep_email": "@biz:PREPARER_EMAIL", "prep_is_us": "yes", "prep_street": "@biz:OFFICE_STREET",
                "prep_unit_type": "@biz:OFFICE_UNIT_TYPE", "prep_unit_number": "@biz:OFFICE_UNIT_NUMBER", "prep_city": "@biz:OFFICE_CITY", "prep_state": "@biz:OFFICE_STATE",
                "prep_zip": "@biz:OFFICE_ZIP"}
    for name, value in defaults.items():
        b.fields[name].default_value = value
    dyn(b, "prep_statement_card", "i751_preparer")
    para(b, "prep_cert", *txt(f"<strong>Preparer's Certification (as printed on the form; OG signs it separately):</strong> {T.PREP_CERT_EN}",
                              f"<strong>Certificación del preparador (tal como está impresa en el formulario; OG la firma por separado):</strong> {T.PREP_CERT_ES} <em>{T.COURTESY_SHORT_ES}</em>", "text-[13px] leading-relaxed text-slate-600"))
    b.fields["prep_cert"].source_note = T.COURTESY


def build_i751(form):
    b = Builder(form)
    from app.case_types import FORM_CASE_CONFIG

    cfg = FORM_CASE_CONFIG["I-751"]
    blocks = ["sb_identity", "sb_othernames", "sb_ids", "sb_marital", "sb_address", "sb_residence", "sb_bio", "sb_contact", "sb_s_name", "sb_s_birth", "sb_s_ids", "sb_s_address", "sb_s_contact"]
    page(b, "sys", ("Case information", "Información del caso"), group=None)
    for k in blocks:
        b.field(f"{k}_avail", "short_answer", (f"{k} available", f"{k} disponible"), ref="OG system flag (never shown)")
        kp(b, f"{k}_avail", system=True)
        if cfg["blocks"][k].get("ask") or k == "sb_address":
            facts = list(cfg["blocks"][k]["fields"])
            b.field(f"{k}_missing", "multi_choice", (f"{k} missing", f"{k} faltante"), ref="OG system flag (never shown)", opts=[(f, f, f) for f in facts])
            kp(b, f"{k}_missing", system=True)
    for name, ref in (("c_route", "Part 3 (route chosen)"), ("c_basis", "Part 3, Items 1.a–1.g (boxes chosen)"), ("c_part8", "Part 8 (whether asked)"), ("c_p4_role", "Part 4, Item 1 (time-aware role)"),
                      ("c_kids", "Part 5 (number of children)"), ("c_kids_applying", "Part 5 (children applying with the petitioner)"), ("c_hist", "Part 1, Item 22 (residence history coverage)"),
                      ("c_addl", "Part 11, Items 3–7 (entries generated from the answers)"), ("prep_status", "Part 10, Item 7.a / 7.b"), ("prep_extends", "Part 10, Item 7.b")):
        b.field(name, "short_answer", (name, name), ref="OG system value (never shown): " + ref)
        kp(b, name, system=True)
    show_page_any(b, "sys", [[("sb_identity_avail", "equals", "__never__")]])

    # ================================================================== Before you begin
    page(b, "intro", ("Before you begin", "Antes de empezar"), group="before", ctx="resident")
    para(b, "intro_1", "This intake collects what OG Multiservices needs to prepare Form I-751, Petition to Remove Conditions on Residence (USCIS edition 04/01/24). Your answers save automatically, so you can stop and come back anytime.",
         "Este formulario reúne lo que OG Multiservices necesita para preparar el Formulario I-751, Petición para Eliminar las Condiciones de la Residencia (edición USCIS 04/01/24). Tus respuestas se guardan automáticamente, así que puedes parar y volver cuando quieras.")
    dyn(b, "intro_case", "context")
    para(b, "intro_2", "This is a new case. If OG already has information about the people involved from another application — even in a different case — we show it to you first so you can confirm it instead of typing it again. Nothing is reused without your confirmation, and anything that changes over time is checked with you first.",
         "Este es un caso nuevo. Si OG ya tiene información de las personas involucradas de otra solicitud —incluso en otro caso— te la mostramos primero para que la confirmes en lugar de escribirla otra vez. Nada se reutiliza sin tu confirmación, y lo que cambia con el tiempo se verifica contigo primero.")
    para(b, "intro_3", "OG Multiservices provides document preparation and administrative assistance. We are not a law firm and do not provide legal advice or representation. We cannot tell you whether you qualify, whether your petition is on time, or which way of filing applies to you: OG reviews that with you. Sending this to OG does not file anything with USCIS.",
         "OG Multiservices ofrece preparación de documentos y asistencia administrativa. No somos un bufete de abogados ni brindamos asesoría o representación legal. No podemos decirte si calificas, si tu petición está a tiempo ni qué forma de presentar te corresponde: OG lo revisa contigo. Enviar esto a OG no presenta nada ante USCIS.")
    page(b, "smart_start", ("We already have information", "Ya tenemos información"),
         ("This is what OG already knows. You will review it before it is used — nothing is copied without your confirmation.", "Esto es lo que OG ya sabe. Lo revisarás antes de usarlo: nada se copia sin tu confirmación."), group="before", ctx="resident")
    dyn(b, "smart_card", "i751_start")
    show_page_any(b, "smart_start", [[(f"{k}_avail", "equals", "yes")] for k in ("sb_identity", "sb_othernames", "sb_address", "sb_ids", "sb_marital", "sb_residence", "sb_bio", "sb_contact", "sb_s_name", "sb_s_birth", "sb_s_address")])

    # ================================================================== PART 3 — basis for petition (asked first: it drives the rest)
    page(b, "basis_route", ("How are you filing?", "¿Cómo presentas?"),
         ("The form has two ways: together with your spouse, or without your spouse (a waiver or individual filing request). OG does not choose this for you — if you are not sure, say so and OG will go through it with you.",
          "El formulario tiene dos formas: junto con tu cónyuge, o sin tu cónyuge (una dispensa o solicitud de presentación individual). OG no elige esto por ti: si no estás seguro(a), dilo y OG lo revisará contigo."), group="basis", ctx="resident")
    choice(b, "b_route", ("My conditional residence is based on my marriage or my parent's marriage to a U.S. citizen or lawful permanent resident, and I am…", "Mi residencia condicional se basa en mi matrimonio o en el matrimonio de mi padre o madre con un ciudadano de EE. UU. o residente permanente legal, y yo estoy…"),
           "Part 3 (Joint Filing / Waiver or Individual Filing Request)", [
               ("joint", "Filing this joint petition together with my spouse (or my parent's spouse)", "Presentando esta petición conjunta junto con mi cónyuge (o el cónyuge de mi padre o madre)"),
               ("waiver", "Filing without my spouse (or my parent's spouse): a waiver or individual filing request", "Presentando sin mi cónyuge (o el cónyuge de mi padre o madre): una dispensa o solicitud de presentación individual"),
               ("unsure", "Not sure — OG will review this with me", "No estoy seguro(a) — OG lo revisará conmigo")],
           help=("This is private. OG never decides for you, and nothing here says whether you qualify.", "Esto es privado. OG nunca decide por ti, y nada aquí dice si calificas."))
    flag(b, "b_route", private=True)
    note(b, "b_unsure_note", "That is fine. OG will go through how you are filing with you before anything is prepared. You can keep going: the next steps ask only what every case needs.",
         "Está bien. OG revisará contigo cómo presentas antes de preparar nada. Puedes seguir: los siguientes pasos piden solo lo que todo caso necesita.")
    only_if(b, "b_unsure_note", ("b_route", "equals", "unsure"))

    page(b, "basis_joint", ("Filing together", "Presentando en conjunto"), (T.JOINT_INTRO[0], T.JOINT_INTRO[1]), group="basis", ctx="resident")
    choice(b, "b_joint", ("Select only one box", "Selecciona solo una casilla"), "Part 3, Items 1.a–1.b (Joint Filing)", [(v, en, es) for v, en, es in T.JOINT_OPTIONS])
    flag(b, "b_joint", private=True)
    b.fields["b_joint"].source_note = VERBATIM_NOTE
    show_page_any(b, "basis_joint", [[("b_route", "equals", "joint")]])

    page(b, "basis_waiver", ("Filing without your spouse", "Presentando sin tu cónyuge"), (T.WAIVER_INTRO[0], T.WAIVER_INTRO[1]), group="basis", ctx="resident")
    note(b, "b_waiver_private", "Your answers on this page are private: they are shown only to you and OG staff, never in your case summary or in a list of documents. Select all that apply. If you are not sure which apply, choose that option and OG will review it with you.",
         "Tus respuestas en esta página son privadas: solo las ven tú y el personal de OG, nunca en el resumen de tu caso ni en una lista de documentos. Selecciona todas las que apliquen. Si no estás seguro(a) de cuáles aplican, elige esa opción y OG lo revisará contigo.")
    b.field("b_waiver", "multi_choice", ("Select all applicable boxes", "Selecciona todas las casillas que apliquen"), ref="Part 3, Items 1.c–1.g (Waiver or Individual Filing Request)", req=True,
            opts=[(v, en, es) for v, en, es in T.WAIVER_OPTIONS] + [("unsure", "Not sure which apply — OG will review with me", "No estoy seguro(a) de cuáles aplican — OG lo revisará conmigo")],
            note=VERBATIM_NOTE + " Several boxes may be selected at once.")
    private(b, "b_waiver")
    show_page_any(b, "basis_waiver", [[("b_route", "equals", "waiver")]])

    # ================================================================== PART 1 — the conditional resident
    def edit_identity():
        b.field("r_family", "short_answer", ("Family name (last name)", "Apellido"), ref="Part 1, Item 1.a", req=True, width="half", maxlen=60)
        b.field("r_given", "short_answer", ("Given name (first name)", "Nombre(s)"), ref="Part 1, Item 1.b", req=True, width="half", maxlen=60)
        b.field("r_middle", "short_answer", ("Middle name (if applicable)", "Segundo nombre (si aplica)"), ref="Part 1, Item 1.c", width="half", maxlen=60)
        b.field("r_dob", "date", ("Date of birth", "Fecha de nacimiento"), ref="Part 1, Item 4", req=True, date_rule="past", width="half")
        b.field("r_birth_country", "short_answer", ("Country of birth", "País de nacimiento"), ref="Part 1, Item 5", req=True, width="half", maxlen=60)
        b.field("r_citizenship", "short_answer", ("Country of citizenship or nationality (provide all that apply)", "País de ciudadanía o nacionalidad (indica todos los que apliquen)"), ref="Part 1, Item 6", req=True, maxlen=120,
                help=("If more than one, separate them with commas.", "Si son varios, sepáralos con comas."))
        names = ["r_family", "r_given", "r_middle", "r_dob", "r_birth_country", "r_citizenship"]
        mark_block_fields(b, "sb_identity", names)
        only_missing(b, "sb_identity", names)
    block_pair(b, "sb_identity", group="resident", form_name="I-751", ask_missing=True, ctx="resident",
               review_title=("We already have {res}'s identity information", "Ya tenemos los datos de identidad de {res}"),
               review_desc=("Name, date of birth, country of birth and citizenship. Confirm them or change them.", "Nombre, fecha de nacimiento, país de nacimiento y ciudadanía. Confírmalos o cámbialos."),
               edit_title=("About the conditional resident", "Sobre el residente condicional"),
               edit_desc=("Use the name exactly as it is on the conditional Permanent Resident Card. Only what is still missing is asked.", "Usa el nombre exactamente como aparece en la Tarjeta de Residente Permanente condicional. Solo se pregunta lo que aún falta."), build_edit=edit_identity)

    def edit_othernames():
        records(b, "r_other_names", ("Other names ever used", "Otros nombres usados alguna vez"), "Part 1, Items 2–3 (two name boxes; more go in Part 11)", "other_name", max=12,
                help=("List all other names you have ever used, including aliases, maiden name and nicknames. If none, just continue.", "Indica todos los demás nombres que has usado alguna vez, incluidos alias, apellido de soltera y apodos. Si no tienes, solo continúa."))
        mark_block_fields(b, "sb_othernames", ["r_other_names"])
    block_pair(b, "sb_othernames", group="resident", form_name="I-751", ctx="resident",
               review_title=("We already have the other names {res} has used", "Ya tenemos los otros nombres que ha usado {res}"), review_desc=("Confirm this list or change it.", "Confirma esta lista o cámbiala."),
               edit_title=("Other names used", "Otros nombres usados"), edit_desc=None, build_edit=edit_othernames)

    def edit_ids():
        b.field("r_anumber", "short_answer", ("A-Number (if any)", "Número A (si tienes)"), ref="Part 1, Item 7", sensitive=True, pattern=r"A?-?\d{7,9}", maxlen=12, msg=("Enter 7 to 9 digits, with or without “A-”.", "Ingresa 7 a 9 dígitos, con o sin “A-”."))
        where(b, "r_anumber", *WHERE_A)
        b.field("r_ssn", "short_answer", ("U.S. Social Security number (if any)", "Número de Seguro Social de EE. UU. (si tienes)"), ref="Part 1, Item 8", sensitive=True, pattern=r"\d{3}-?\d{2}-?\d{4}", msg=("Enter 9 digits.", "Ingresa 9 dígitos."))
        where(b, "r_ssn", *WHERE_SSN)
        b.field("r_uscis", "short_answer", ("USCIS Online Account Number (if any)", "Número de cuenta en línea de USCIS (si tienes)"), ref="Part 1, Item 9", maxlen=12, pattern=r"\d{1,12}", msg=("Use digits only (up to 12).", "Usa solo dígitos (hasta 12)."))
        where(b, "r_uscis", *WHERE_ACCT)
        mark_block_fields(b, "sb_ids", ["r_anumber", "r_ssn", "r_uscis"])
    block_pair(b, "sb_ids", group="resident", form_name="I-751", ctx="resident",
               review_title=("We already have {res}'s identification numbers", "Ya tenemos los números de identificación de {res}"),
               review_desc=("A-Number, Social Security number and USCIS online account (partly hidden). Confirm them or change them.", "Número A, Seguro Social y cuenta en línea de USCIS (parcialmente ocultos). Confírmalos o cámbialos."),
               edit_title=("Identification numbers", "Números de identificación"), edit_desc=("Give the ones you have. Leave the rest blank.", "Indica los que tienes. Deja en blanco los demás."), build_edit=edit_ids)

    def edit_marital():
        b.field("r_marital", "single_choice", ("Marital status", "Estado civil"), ref="Part 1, Item 10", req=True,
                opts=[("single", "Single", "Soltero(a)"), ("married", "Married", "Casado(a)"), ("divorced", "Divorced", "Divorciado(a)"), ("widowed", "Widowed", "Viudo(a)")])
        mark_block_fields(b, "sb_marital", ["r_marital"])
    block_pair(b, "sb_marital", group="marriage", form_name="I-751", ctx="resident",
               review_title=("{res}'s marital status", "Estado civil de {res}"), review_desc=("Marital status can change. Is this still correct?", "El estado civil puede cambiar. ¿Sigue siendo correcto?"),
               edit_title=("Marital status", "Estado civil"), edit_desc=None, build_edit=edit_marital)

    page(b, "marriage", ("The marriage through which conditional residence was gained", "El matrimonio por el cual se obtuvo la residencia condicional"),
         ("These details are about that marriage (for a child filing separately, the marriage of the parent through which the child gained status).", "Estos datos son sobre ese matrimonio (si un hijo(a) presenta por separado, el matrimonio del padre o madre por el cual el hijo(a) obtuvo el estatus)."), group="marriage", ctx="resident")
    b.field("r_marriage_date", "date", ("Date of marriage", "Fecha del matrimonio"), ref="Part 1, Item 11", req=True, date_rule="past", width="half")
    b.field("r_marriage_place", "short_answer", ("Place of marriage", "Lugar del matrimonio"), ref="Part 1, Item 12", req=True, maxlen=120, width="half",
            help=("City, state or province, and country.", "Ciudad, estado o provincia, y país."))
    b.field("r_marriage_ended", "single_choice", ("Has that marriage ended?", "¿Ese matrimonio ya terminó?"), ref="Part 1, Item 13 (OG helper: whether the marriage ended)", req=True, opts=YES_NO)
    b.field("r_marriage_end_date", "date", ("Date the marriage ended (date of divorce or date of death)", "Fecha en que terminó el matrimonio (fecha del divorcio o de la muerte)"), ref="Part 1, Item 13", req=True, date_rule="past",
            help=("If the marriage through which you gained conditional residence has ended, provide the date it ended (date of divorce or date of death).", "Si el matrimonio por el cual obtuviste la residencia condicional terminó, indica la fecha en que terminó (fecha del divorcio o de la muerte)."))
    b.rule("show_field", "r_marriage_end_date", [("r_marriage_ended", "equals", "yes")])

    page(b, "conditional", ("Your conditional residence", "Tu residencia condicional"), group="marriage", ctx="resident")
    b.field("r_expires", "date", ("Conditional residence expires on", "La residencia condicional vence el"), ref="Part 1, Item 14", req=True, width="half", help=WHERE_EXPIRES)
    b.field("r_resident_since", "date", ("The date you became a permanent resident (“Resident Since”)", "La fecha en que te hiciste residente permanente (“Resident Since”)"), ref="OG helper (used to check the address history for Item 22; not a numbered item)", date_rule="past", width="half", help=WHERE_RESIDENT_SINCE)
    where(b, "r_resident_since", *WHERE_RESIDENT_SINCE)

    # ---- addresses (Items 15-17)
    def edit_address():
        us_address(b, "ph", "Part 1, Item 17 (Physical Address; also Item 15 when they are the same)")
        names = [n for n in b.fields if n.startswith("ph_")]
        mark_block_fields(b, "sb_address", names)
        only_missing(b, "sb_address", names)
    block_pair(b, "sb_address", group="addresses", form_name="I-751", ask_missing=True, ctx="resident",
               review_title=("{res}'s U.S. physical address", "Dirección física de {res} en EE. UU."), review_desc=("Is this still where you live?", "¿Sigues viviendo aquí?"),
               edit_title=("Where you live now (U.S. physical address)", "Donde vives ahora (dirección física en EE. UU.)"), edit_desc=("Where you live now. Do not use an older address.", "Donde vives ahora. No uses una dirección anterior."), build_edit=edit_address)
    page(b, "mail_gate", ("Mailing address", "Dirección postal"), group="addresses", ctx="resident")
    b.field("m_diff", "single_choice", ("Is your physical address different than your mailing address?", "¿Tu dirección física es diferente de tu dirección postal?"), ref="Part 1, Item 16", req=True, opts=YES_NO,
            help=("Choose No if you receive your mail where you live.", "Elige No si recibes tu correo donde vives."))
    page(b, "mailing", ("Your mailing address", "Tu dirección postal"), group="addresses", ctx="resident")
    us_address(b, "ml", "Part 1, Item 15 (Mailing Address)", in_care_of=True)
    show_page_any(b, "mailing", [[("m_diff", "equals", "yes")]])

    page(b, "res_gate", ("Other addresses since you became a resident", "Otras direcciones desde que te hiciste residente"), group="addresses", ctx="resident")
    b.field("r_other_addr", "single_choice", ("Have you resided at any other address since you became a permanent resident?", "¿Has residido en alguna otra dirección desde que te hiciste residente permanente?"), ref="Part 1, Item 22", req=True, opts=YES_NO,
            help=("If you answer Yes, the next step lists every address since you became a permanent resident, with dates. OG adds that list to Part 11 for you.", "Si respondes Sí, el siguiente paso enumera cada dirección desde que te hiciste residente permanente, con fechas. OG agrega esa lista a la Parte 11 por ti."))

    def edit_residence():
        dyn(b, "r_history_card", "i751_history")
        records(b, "r_history", ("Every address since you became a permanent resident", "Cada dirección desde que te hiciste residente permanente"), "Part 1, Item 22 (list goes in Part 11)", "address", req=True, max=30,
                timeline={"years": 5, "gap_days": 3, "overlap_days": 31, "since_field": "r_resident_since"},
                default_from={"prefix": "ph", "present": True},
                intro={"en": "Start with where you live now, then add each earlier address, back to the day you became a permanent resident.", "es": "Empieza con donde vives ahora y agrega cada dirección anterior, hasta el día en que te hiciste residente permanente."})
        mark_block_fields(b, "sb_residence", ["r_history"])
    block_pair(b, "sb_residence", group="addresses", form_name="I-751", ctx="resident", gates=[[("r_other_addr", "equals", "yes")]], extra_edit=[[("c_hist", "not_equals", "ok")]],
               review_title=("We already have addresses for {res}", "Ya tenemos direcciones de {res}"),
               review_desc=("These may not cover the whole period since you became a resident, so the next step lets you add anything missing. Use them as your starting point, or start over.", "Puede que no cubran todo el período desde que te hiciste residente, así que el siguiente paso te deja agregar lo que falte. Úsalas como punto de partida o empieza de nuevo."),
               edit_title=("Addresses since you became a permanent resident", "Direcciones desde que te hiciste residente permanente"),
               edit_desc=("This history starts on the day you became a permanent resident (not a fixed number of years).", "Este historial empieza el día en que te hiciste residente permanente (no un número fijo de años)."), build_edit=edit_residence)

    # ---- additional questions (Items 18-23)
    page(b, "add_q1", ("Proceedings and fees", "Procesos y honorarios"), ("Answer each question about you. These are questions from the form (Part 1, Items 18–19).", "Responde cada pregunta sobre ti. Son preguntas del formulario (Parte 1, Ítems 18–19)."), group="additional_q", ctx="resident")
    yesno(b, "q18", ("Are you in removal, deportation, or rescission proceedings?", "¿Estás en procesos de expulsión, deportación o rescisión?"), "Part 1, Item 18")
    explain(b, "q18_details", "Part 11 (explanation for Part 1, Item 18)", "q18", label=("Tell OG about it", "Cuéntale a OG al respecto"),
            help=("For example where, when it started, and what the status of the case is. OG will ask for anything else it needs.", "Por ejemplo dónde, cuándo empezó y cuál es el estado del caso. OG pedirá lo demás que necesite."), sensitive=True)
    yesno(b, "q19", ("Was a fee paid to anyone other than an attorney in connection with this petition?", "¿Se pagó una tarifa a alguien que no sea un abogado en relación con esta petición?"), "Part 1, Item 19",
          help=("This can include a fee paid to a preparer who is not an attorney. OG will go over this answer with you.", "Esto puede incluir una tarifa pagada a un preparador que no sea abogado. OG revisará contigo esta respuesta."))
    explain(b, "q19_details", "Part 11 (explanation for Part 1, Item 19)", "q19", label=("Who was paid, for what, and how much?", "¿A quién se pagó, por qué y cuánto?"))
    page(b, "add_q2", ("Arrests and similar events", "Arrestos y eventos similares"), group="additional_q", ctx="resident")
    yesno(b, "q20", ("Have you ever been arrested, detained, charged, indicted, fined, or imprisoned for breaking or violating any law or ordinance (excluding traffic regulations), or committed any crime which you were not arrested in the United States or abroad?",
                     "¿Alguna vez has sido arrestado(a), detenido(a), acusado(a), procesado(a), multado(a) o encarcelado(a) por romper o violar alguna ley u ordenanza (excluyendo las regulaciones de tránsito), o has cometido algún delito por el cual no fuiste arrestado(a) en los Estados Unidos o en el extranjero?"),
          "Part 1, Item 20")
    note(b, "q20_note", "Note from the form: if you answered Yes, provide a detailed explanation in Part 11 or on a separate sheet of paper, and refer to the What Initial Evidence Is Required section of the Form I-751 instructions to determine what criminal history document to include with your petition. OG will review this with you.",
         "Nota del formulario: si respondiste Sí, proporciona una explicación detallada en la Parte 11 o en una hoja aparte, y consulta la sección What Initial Evidence Is Required de las instrucciones del Formulario I-751 para determinar qué documento de antecedentes penales incluir con tu petición. OG lo revisará contigo.")
    only_if(b, "q20_note", ("q20", "equals", "yes"))
    explain(b, "q20_details", "Part 11 (explanation for Part 1, Item 20)", "q20", label=("Please give a detailed explanation", "Por favor da una explicación detallada"),
            help=("Where and when it happened and what the result was, as far as you remember. OG will not judge it; it is copied to the Additional Information page.", "Dónde y cuándo ocurrió y cuál fue el resultado, hasta donde recuerdes. OG no lo juzga; se copia a la página de Información adicional."), sensitive=True)
    page(b, "add_q3", ("Your marriage and your spouse", "Tu matrimonio y tu cónyuge"), group="additional_q", ctx="resident")
    yesno(b, "q21", ("If you are married, is this a different marriage than the one through which you gained conditional resident status?", "Si estás casado(a), ¿es este un matrimonio diferente al matrimonio por el cual obtuviste el estatus de residente condicional?"), "Part 1, Item 21")
    b.rule("show_field", "q21", [("r_marital", "equals", "married")])
    explain(b, "q21_details", "Part 11 (explanation for Part 1, Item 21)", "q21", label=("Tell OG about your current marriage", "Cuéntale a OG sobre tu matrimonio actual"))
    yesno(b, "q23", ("Is your spouse or parent's spouse currently serving with or employed by the U.S. Government and serving outside the United States?", "¿Tu cónyuge o el cónyuge de tu padre o madre está actualmente sirviendo con o empleado por el Gobierno de EE. UU. y sirviendo fuera de los Estados Unidos?"), "Part 1, Item 23")
    explain(b, "q23_details", "Part 11 (explanation for Part 1, Item 23)", "q23", label=("Tell OG where and for which agency", "Cuéntale a OG dónde y para qué agencia"))

    # ================================================================== PART 2 — biographic
    def edit_bio():
        b.field("r_ethnicity", "single_choice", ("Ethnicity (select only one box)", "Etnia (selecciona solo una casilla)"), ref="Part 2, Item 1", req=True,
                opts=[("hispanic", "Hispanic or Latino", "Hispano o Latino"), ("not_hispanic", "Not Hispanic or Latino", "No hispano ni latino")])
        b.field("r_race", "multi_choice", ("Race (select all applicable boxes)", "Raza (selecciona todas las casillas que apliquen)"), ref="Part 2, Item 2", req=True,
                opts=[("white", "White", "Blanco"), ("asian", "Asian", "Asiático"), ("black", "Black or African American", "Negro o afroamericano"),
                      ("american_indian", "American Indian or Alaska Native", "Indígena americano o nativo de Alaska"), ("pacific_islander", "Native Hawaiian or Other Pacific Islander", "Nativo de Hawái u otra isla del Pacífico")])
        b.field("r_height_ft", "dropdown", ("Height — feet", "Estatura — pies"), ref="Part 2, Item 3", req=True, width="half", opts=[(str(n), str(n), str(n)) for n in range(2, 9)])
        b.field("r_height_in", "dropdown", ("Height — inches", "Estatura — pulgadas"), ref="Part 2, Item 3", req=True, width="half", opts=[(str(n), str(n), str(n)) for n in range(0, 12)])
        b.field("r_weight", "number", ("Weight (pounds)", "Peso (libras)"), ref="Part 2, Item 4", req=True, minv=1, maxv=999, width="half")
        b.field("r_eye", "dropdown", ("Eye color (select only one box)", "Color de ojos (selecciona solo una casilla)"), ref="Part 2, Item 5", req=True, opts=EYE, width="half")
        b.field("r_hair", "dropdown", ("Hair color (select only one box)", "Color de cabello (selecciona solo una casilla)"), ref="Part 2, Item 6", req=True, opts=HAIR, width="half")
        names = ["r_ethnicity", "r_race", "r_height_ft", "r_height_in", "r_weight", "r_eye", "r_hair"]
        mark_block_fields(b, "sb_bio", names)
        only_missing(b, "sb_bio", names)
    block_pair(b, "sb_bio", group="bio", form_name="I-751", ask_missing=True, ctx="resident",
               review_title=("{res}'s biographic information", "Información biográfica de {res}"), review_desc=("Height, weight and hair color can change. Is this still current?", "La estatura, el peso y el color de cabello pueden cambiar. ¿Sigue vigente?"),
               edit_title=("Biographic information", "Información biográfica"),
               edit_desc=("Answer these yourself — OG never guesses ethnicity or race. Only what is still missing is asked.", "Responde tú mismo(a): OG nunca adivina la etnia ni la raza. Solo se pregunta lo que aún falta."), build_edit=edit_bio)

    # ================================================================== PART 4 — the spouse / relevant individual
    page(b, "p4_rel", ("Who is this person to you?", "¿Quién es esta persona para ti?"),
         ("Part 4 is about the U.S. citizen or lawful permanent resident spouse — or, if you are a child filing separately, the stepparent through whom you gained conditional residence.", "La Parte 4 trata del cónyuge ciudadano de EE. UU. o residente permanente legal — o, si eres un hijo(a) que presenta por separado, el padrastro o madrastra a través de quien obtuviste la residencia condicional."), group="spouse", ctx="spouse")
    dyn(b, "p4_route_card", "i751_route")
    choice(b, "p4_rel", ("Relationship", "Relación"), "Part 4, Items 1.a–1.b", [("spouse", "Spouse or Former Spouse", "Cónyuge o excónyuge"), ("parent_spouse", "Parent's Spouse or Former Spouse", "Cónyuge o excónyuge de mi padre o madre")])

    def edit_s_name():
        b.field("s_family", "short_answer", ("Family name (last name)", "Apellido"), ref="Part 4, Item 2.a", req=True, width="half", maxlen=60)
        b.field("s_given", "short_answer", ("Given name (first name)", "Nombre(s)"), ref="Part 4, Item 2.b", req=True, width="half", maxlen=60)
        b.field("s_middle", "short_answer", ("Middle name (if applicable)", "Segundo nombre (si aplica)"), ref="Part 4, Item 2.c", width="half", maxlen=60)
        mark_block_fields(b, "sb_s_name", ["s_family", "s_given", "s_middle"])
    block_pair(b, "sb_s_name", group="spouse", form_name="I-751", ctx="spouse",
               review_title=("We already have {rel}'s name", "Ya tenemos el nombre de {rel}"), review_desc=("Confirm it or change it.", "Confírmalo o cámbialo."),
               edit_title=("Name of the person in Part 4", "Nombre de la persona de la Parte 4"), edit_desc=None, build_edit=edit_s_name)

    def edit_s_birth():
        b.field("s_dob", "date", ("Date of birth", "Fecha de nacimiento"), ref="Part 4, Item 3", req=True, date_rule="past", width="half")
        mark_block_fields(b, "sb_s_birth", ["s_dob"])
    block_pair(b, "sb_s_birth", group="spouse", form_name="I-751", ctx="spouse",
               review_title=("We already have {rel}'s date of birth", "Ya tenemos la fecha de nacimiento de {rel}"), review_desc=("Confirm it or change it.", "Confírmala o cámbiala."),
               edit_title=("Date of birth", "Fecha de nacimiento"), edit_desc=None, build_edit=edit_s_birth)

    def edit_s_ids():
        b.field("s_ssn", "short_answer", ("U.S. Social Security number (if any)", "Número de Seguro Social de EE. UU. (si tiene)"), ref="Part 4, Item 4", sensitive=True, pattern=r"\d{3}-?\d{2}-?\d{4}", msg=("Enter 9 digits.", "Ingresa 9 dígitos."))
        b.field("s_anumber", "short_answer", ("A-Number (if any)", "Número A (si tiene)"), ref="Part 4, Item 5", sensitive=True, pattern=r"A?-?\d{7,9}", maxlen=12, msg=("Enter 7 to 9 digits, with or without “A-”.", "Ingresa 7 a 9 dígitos, con o sin “A-”."))
        mark_block_fields(b, "sb_s_ids", ["s_ssn", "s_anumber"])
    block_pair(b, "sb_s_ids", group="spouse", form_name="I-751", ctx="spouse",
               review_title=("We already have {rel}'s Social Security number and A-Number", "Ya tenemos el Seguro Social y el número A de {rel}"), review_desc=("Partly hidden. Confirm them or change them.", "Parcialmente ocultos. Confírmalos o cámbialos."),
               edit_title=("Identification numbers", "Números de identificación"), edit_desc=("Give the ones you know. Leave the rest blank.", "Indica los que conoces. Deja en blanco los demás."), build_edit=edit_s_ids)

    def edit_s_address():
        _address_fields(b, "sa", "Part 4, Item 6 (Physical Address, 6.a–6.h)")
        names = [n for n in b.fields if n.startswith("sa_")]
        mark_block_fields(b, "sb_s_address", names)
    block_pair(b, "sb_s_address", group="spouse", form_name="I-751", ctx="spouse",
               review_title=("{rel}'s physical address", "Dirección física de {rel}"), review_desc=("Is this still where they live? If you do not know, choose the last option.", "¿Todavía viven aquí? Si no lo sabes, elige la última opción."),
               edit_title=("Physical address of the person in Part 4", "Dirección física de la persona de la Parte 4"), edit_desc=("Where they live now, as far as you know.", "Donde viven ahora, hasta donde sepas."), build_edit=edit_s_address)

    # ================================================================== PART 5 — children
    page(b, "kids_gate", ("Your children", "Tus hijos"), ("Provide information on all of your children (Part 5). Children are recorded as real people, so nobody is asked for twice.", "Proporciona información sobre todos tus hijos (Parte 5). Los hijos se registran como personas reales, así que a nadie se le pide dos veces."), group="children", ctx="resident")
    b.field("k_has", "single_choice", ("Do you have any children?", "¿Tienes hijos?"), ref="Part 5 (OG helper: whether any child is listed)", req=True, opts=YES_NO)
    page(b, "kids", ("Your children", "Tus hijos"), ("Add each child. There is no limit here: the printed form has room for five, and OG adds the rest to Part 11 for you.", "Agrega a cada hijo(a). Aquí no hay límite: el formulario impreso tiene espacio para cinco, y OG agrega los demás a la Parte 11 por ti."), group="children", ctx="resident")
    records(b, "k_children", ("Children", "Hijos"), "Part 5, Child 1–5 (Items 1–30; more go in Part 11)", "i751_child", req=True, max=25,
            help=("If a child is already in one of your cases, pick them instead of typing again.", "Si un hijo(a) ya está en uno de tus casos, elígelo en lugar de escribirlo otra vez."))
    dyn(b, "k_overflow", "i751_kids")
    show_page_any(b, "kids", [[("k_has", "equals", "yes")]])

    # ================================================================== PART 6 — accommodations
    page(b, "acc_gate", ("Accommodations", "Adaptaciones"), (T.ACC_NOTE_EN, T.ACC_NOTE_ES), group="accommodations", ctx="resident")
    note(b, "acc_private", "Your answers about disabilities or impairments are private: they are shown only to you and OG staff.", "Tus respuestas sobre discapacidades o impedimentos son privadas: solo las ven tú y el personal de OG.")
    yesno(b, "acc_own", ("Are you requesting an accommodation because of your disabilities and/or impairments?", "¿Solicitas una adaptación debido a tus discapacidades y/o impedimentos?"), "Part 6, Item 1")
    yesno(b, "acc_spouse", ("Are you requesting an accommodation because of your spouse's disabilities and/or impairments?", "¿Solicitas una adaptación debido a las discapacidades y/o impedimentos de tu cónyuge?"), "Part 6, Item 2")
    b.rule("show_field", "acc_spouse", [("b_route", "equals", "joint")])
    b.rule("show_field", "acc_spouse", [("b_route", "equals", "unsure")])
    yesno(b, "acc_children", ("Are you requesting an accommodation because of your included children's disabilities and/or impairments?", "¿Solicitas una adaptación debido a las discapacidades y/o impedimentos de tus hijos incluidos?"), "Part 6, Item 3")
    b.rule("show_field", "acc_children", [("k_has", "equals", "yes")])
    private(b, "acc_own", "acc_spouse", "acc_children")
    page(b, "acc_detail", ("Accommodation details", "Detalles de la adaptación"), ("If you answered Yes, select any applicable box (Items 4.a–4.c) and provide information on the disabilities and/or impairments for each person.", "Si respondiste Sí, selecciona cualquier casilla que aplique (Ítems 4.a–4.c) y proporciona información sobre las discapacidades y/o impedimentos de cada persona."), group="accommodations", ctx="resident")
    b.field("acc_types", "multi_choice", ("Select any applicable box", "Selecciona cualquier casilla que aplique"), ref="Part 6, Items 4.a–4.c", req=True, opts=[(v, en, es) for v, en, es in T.ACC_TYPES], note=VERBATIM_NOTE)
    for key, (v, en, es) in zip(("a", "b", "c"), T.ACC_TYPES):
        label = {"a": ("Accommodation requested (and language, if a sign-language interpreter)", "Adaptación solicitada (e idioma, si es un intérprete de lenguaje de señas)"),
                 "b": ("Accommodation requested", "Adaptación solicitada"), "c": ("Nature of the disability and/or impairment and the accommodation requested", "Naturaleza de la discapacidad y/o impedimento y adaptación solicitada")}[key]
        b.field(f"acc_{key}_text", "long_answer", label, ref=f"Part 6, Item 4.{key}", req=True, maxlen=1500)
        b.rule("show_field", f"acc_{key}_text", [("acc_types", "selected", key)])
        private(b, f"acc_{key}_text")
    b.field("acc_persons", "long_answer", ("For your spouse or children: whose disability or impairment, and what accommodation", "Para tu cónyuge o hijos: de quién es la discapacidad o impedimento y qué adaptación"), ref="Part 6, Items 4.a–4.c (information for each person; goes to Part 11)", maxlen=1500)
    b.rule("show_field", "acc_persons", [("acc_spouse", "equals", "yes")])
    b.rule("show_field", "acc_persons", [("acc_children", "equals", "yes")])
    private(b, "acc_types", "acc_persons")
    show_page_any(b, "acc_detail", [[("acc_own", "equals", "yes")], [("acc_spouse", "equals", "yes")], [("acc_children", "equals", "yes")]])

    # ================================================================== PART 7 — petitioner's statement, contact, ASC acknowledgement, certification
    page(b, "statement", ("Your statement", "Tu declaración"), ("Select the one that is true for you (Part 7, Items 1.a / 1.b). An interpreter is never assumed.", "Selecciona la que sea cierta para ti (Parte 7, Ítems 1.a / 1.b). Nunca se asume un intérprete."), group="statement", ctx="resident")
    para(b, "p7_note", *txt(T.P7_NOTE_EN, T.P7_NOTE_ES, "text-[13px] leading-relaxed text-slate-600"))
    choice(b, "s_statement", ("Petitioner's statement", "Declaración del peticionario"), "Part 7, Items 1.a / 1.b", [
        ("english", T.P7_STATEMENT_A_EN, T.P7_STATEMENT_A_ES),
        ("interpreter", T.P7_STATEMENT_B_EN.replace("in {language}, a language", "in the language you name below, a language"), T.P7_STATEMENT_B_ES.replace("en {language}, un idioma", "en el idioma que indicas abajo, un idioma"))])
    b.fields["s_statement"].source_note = T.COURTESY
    b.field("int_language", "short_answer", ("The language in which you are fluent", "El idioma en el que eres fluido(a)"), ref="Part 7, Item 1.b (language) and Part 9, Interpreter's Certification (language)", req=True, maxlen=60)
    b.rule("show_field", "int_language", [("s_statement", "equals", "interpreter")])
    dyn(b, "p7_prep_card", "i751_p7prep")

    def edit_contact():
        b.field("r_phone", "phone", ("Petitioner's daytime telephone number", "Teléfono de día del peticionario"), ref="Part 7, Item 3", req=True, width="half")
        b.field("r_mobile", "phone", ("Petitioner's mobile telephone number (if any)", "Teléfono móvil del peticionario (si tiene)"), ref="Part 7, Item 4", width="half")
        b.field("r_email", "email", ("Petitioner's email address (if any)", "Correo electrónico del peticionario (si tiene)"), ref="Part 7, Item 5")
        b.fields["r_email"].required = False
        mark_block_fields(b, "sb_contact", ["r_phone", "r_mobile", "r_email"])
    block_pair(b, "sb_contact", group="statement", form_name="I-751", ctx="resident",
               review_title=("We already have {res}'s contact information", "Ya tenemos la información de contacto de {res}"), review_desc=("Is it still current?", "¿Sigue vigente?"),
               edit_title=("Your contact information", "Tu información de contacto"), edit_desc=None, build_edit=edit_contact)
    page(b, "asc", ("Acknowledgement of Appointment at the USCIS Application Support Center", "Reconocimiento de la cita en el Centro de Servicio de Solicitudes de USCIS"),
         ("This is printed on the form so you can read it now. You do not sign anything here. " + "The English is the official text.", "Esto está impreso en el formulario para que lo leas ahora. Aquí no firmas nada. " + T.COURTESY_NOTE_ES), group="statement", ctx="resident")
    dyn(b, "asc_card", "i751_asc")
    b.field("c_asc_ack", "consent", ("Reading the acknowledgement", "Lectura del reconocimiento"), ref="Part 7 (Acknowledgement of Appointment at USCIS ASC) — customer acknowledgment only", req=True,
            note="Customer acknowledgment that the text was read; not a signature and not the acknowledgement itself. " + T.COURTESY,
            content=("I have read this acknowledgement. I understand that I am not signing or declaring anything here, and that OG will explain how and when I sign.", "He leído este reconocimiento. Entiendo que aquí no firmo ni declaro nada y que OG me explicará cómo y cuándo firmo."))
    page(b, "cert", ("What you will be asked to certify", "Lo que se te pedirá certificar"),
         ("This is the Petitioner's Certification printed on the form, shown so you can read it now. You do not sign it here. The English is the official text as printed on the form.", "Esta es la Certificación del Peticionario impresa en el formulario, mostrada para que la leas ahora. No la firmas aquí. " + T.COURTESY_NOTE_ES), group="statement", ctx="resident")
    for i, (en, es) in enumerate(zip(T.CERT_EN, T.CERT_ES), 1):
        para(b, f"cert_{i}", *txt(en, es))
        b.fields[f"cert_{i}"].source_note = T.COURTESY + " Part 7, Petitioner's Certification."
    b.field("c_cert_ack", "consent", ("Reading the certification", "Lectura de la certificación"), ref="Part 7 (Petitioner's Certification) — customer acknowledgment only", req=True,
            note="Customer acknowledgment that the certification was read; not a signature and not the certification itself. " + T.COURTESY,
            content=("I have read this certification. I understand that I am not signing or certifying anything here, and that OG will explain how and when I sign.", "He leído esta certificación. Entiendo que aquí no firmo ni certifico nada y que OG me explicará cómo y cuándo firmo."))

    # ================================================================== PART 8 — the spouse's / individual's own statement (joint filing only)
    page(b, "p8_intro", ("Your spouse's part of the petition", "La parte de tu cónyuge en la petición"), (T.P8_INTRO_EN + " Your spouse reads and signs this part themselves; you only tell us what you know.", T.P8_INTRO_ES + " Tu cónyuge lee y firma esta parte por sí mismo(a); tú solo nos dices lo que sabes."), group="part8", ctx="spouse")
    para(b, "p8_note", *txt("The form's note says the spouse must also read and sign the petition in Part 8 when the joint petition is with a spouse (Box 1.a). OG will confirm with your spouse and explain how their signature is handled.",
                            "La nota del formulario indica que el cónyuge también debe leer y firmar la petición en la Parte 8 cuando la petición conjunta es con un cónyuge (casilla 1.a). OG lo confirmará con tu cónyuge y te explicará cómo se maneja su firma.", "text-[13px] leading-relaxed text-slate-600"))
    choice(b, "s8_statement", ("Spouse's or individual's statement (as far as you know)", "Declaración del cónyuge o de la persona (hasta donde sepas)"), "Part 8, Items 1.a / 1.b", [
        ("english", T.P8_STATEMENT_A_EN, T.P8_STATEMENT_A_ES),
        ("interpreter", T.P8_STATEMENT_B_EN.replace("in {language}, a language", "in the language named below, a language"), T.P8_STATEMENT_B_ES.replace("en {language}, un idioma", "en el idioma indicado abajo, un idioma")),
        ("unsure", "I do not know — OG will ask them", "No lo sé — OG se lo preguntará")])
    b.fields["s8_statement"].source_note = T.COURTESY
    b.field("s8_language", "short_answer", ("The language in which they are fluent", "El idioma en el que son fluidos"), ref="Part 8, Item 1.b (language)", req=True, maxlen=60)
    b.rule("show_field", "s8_language", [("s8_statement", "equals", "interpreter")])
    dyn(b, "p8_prep_card", "i751_p8prep")
    show_page_any(b, "p8_intro", [[("b_route", "equals", "joint")]])

    def edit_s_contact():
        b.field("s_phone", "phone", ("Spouse's or individual's daytime telephone number", "Teléfono de día del cónyuge o de la persona"), ref="Part 8, Item 3", req=True, width="half")
        b.field("s_mobile", "phone", ("Spouse's or individual's mobile telephone number (if any)", "Teléfono móvil del cónyuge o de la persona (si tiene)"), ref="Part 8, Item 4", width="half")
        b.field("s_email", "email", ("Spouse's or individual's email address (if any)", "Correo electrónico del cónyuge o de la persona (si tiene)"), ref="Part 8, Item 5")
        b.fields["s_email"].required = False
        mark_block_fields(b, "sb_s_contact", ["s_phone", "s_mobile", "s_email"])
    block_pair(b, "sb_s_contact", group="part8", form_name="I-751", ctx="spouse", gates=[[("b_route", "equals", "joint")]],
               review_title=("We already have {rel}'s contact information", "Ya tenemos la información de contacto de {rel}"), review_desc=("Is it still current?", "¿Sigue vigente?"),
               edit_title=("Your spouse's contact information", "Información de contacto de tu cónyuge"), edit_desc=None, build_edit=edit_s_contact)
    page(b, "p8_read", ("What your spouse will read and sign", "Lo que tu cónyuge leerá y firmará"),
         ("This is printed in Part 8 of the form. Your spouse reads it and signs it themselves; nothing here is signed or acknowledged for them. " + "The English is the official text.", "Esto está impreso en la Parte 8 del formulario. Tu cónyuge lo lee y lo firma por sí mismo(a); aquí no se firma ni se reconoce nada en su nombre. " + T.COURTESY_NOTE_ES), group="part8", ctx="spouse")
    dyn(b, "asc8_card", "i751_asc8")
    para(b, "p8_cert_note", *txt(T.P8_CERT_NOTE_EN, T.P8_CERT_NOTE_ES, "text-[13px] leading-relaxed text-slate-600"))
    show_page_any(b, "p8_read", [[("b_route", "equals", "joint")]])

    # ================================================================== PART 9 — interpreter (only when someone used one)
    page(b, "interp", ("Your interpreter", "Tu intérprete"), ("Information about the interpreter (Part 9 of the form).", "Información del intérprete (Parte 9 del formulario)."), group="interpreter", ctx="resident")
    b.field("int_family", "short_answer", ("Interpreter's family name (last name)", "Apellido del intérprete"), ref="Part 9, Item 1.a", req=True, width="half")
    b.field("int_given", "short_answer", ("Interpreter's given name (first name)", "Nombre del intérprete"), ref="Part 9, Item 1.b", req=True, width="half")
    b.field("int_org", "short_answer", ("Interpreter's business or organization name (if any)", "Empresa u organización del intérprete (si aplica)"), ref="Part 9, Item 2", maxlen=38)
    _address_fields(b, "int", "Part 9, Item 3 (Interpreter's Mailing Address, 3.a–3.h)")
    b.field("int_phone", "phone", ("Interpreter's daytime telephone number", "Teléfono de día del intérprete"), ref="Part 9, Item 4", req=True, width="half")
    b.field("int_email", "email", ("Interpreter's email address (if any)", "Correo electrónico del intérprete (si tiene)"), ref="Part 9, Item 5")
    b.fields["int_email"].required = False
    para(b, "int_cert", *txt(f"<strong>Interpreter's Certification (as printed on the form; the interpreter signs it separately):</strong> {T.INTERP_CERT_EN.format(language='[the language named in Part 7, Item 1.b]')}",
                              f"<strong>Certificación del intérprete (tal como está impresa en el formulario; el intérprete la firma por separado):</strong> {T.INTERP_CERT_ES.format(language='[el idioma indicado en la Parte 7, Ítem 1.b]')} <em>{T.COURTESY_SHORT_ES}</em>", "text-[13px] leading-relaxed text-slate-600"))
    b.fields["int_cert"].source_note = T.COURTESY
    for name, value in {"int_family": "@biz:INTERPRETER_LAST_NAME", "int_given": "@biz:INTERPRETER_FIRST_NAME", "int_org": "@biz:INTERPRETER_ORG", "int_phone": "@biz:INTERPRETER_PHONE",
                        "int_email": "@biz:INTERPRETER_EMAIL", "int_is_us": "yes", "int_street": "@biz:OFFICE_STREET", "int_unit_type": "@biz:OFFICE_UNIT_TYPE",
                        "int_unit_number": "@biz:OFFICE_UNIT_NUMBER", "int_city": "@biz:OFFICE_CITY", "int_state": "@biz:OFFICE_STATE", "int_zip": "@biz:OFFICE_ZIP"}.items():
        b.fields[name].default_value = value
    show_page_any(b, "interp", [[("s_statement", "equals", "interpreter")], [("b_route", "equals", "joint"), ("s8_statement", "equals", "interpreter")]])

    # ================================================================== PART 10 — preparer (OG)
    _add_preparer_page(b)

    # ================================================================== PART 11 — additional information
    page(b, "additional", ("Anything else?", "¿Algo más?"), group="additional", ctx="resident")
    dyn(b, "add_card", "i751_additional")
    b.field("additional_information", "long_answer", ("Is there anything else you want us to know?", "¿Hay algo más que quieras que sepamos?"), ref="Part 11. Additional Information (Items 3–7)", maxlen=3000,
            help=("You never need to know a page, part or item number. When your answers do not fit on the printed form (for example more than two other names or five children), or a question asks for an explanation, OG adds it to Part 11 for you.",
                  "Nunca necesitas saber un número de página, parte o ítem. Cuando tus respuestas no caben en el formulario impreso (por ejemplo más de dos otros nombres o cinco hijos), o una pregunta pide una explicación, OG lo agrega a la Parte 11 por ti."))

    # ================================================================== documents
    page(b, "documents", ("Documents", "Documentos"), ("Documents are kept once in your case, so a document OG already has for this case is not asked for again.", "Los documentos se guardan una sola vez en tu caso, así que un documento que OG ya tiene de este caso no se vuelve a pedir."), group="documents", ctx="resident")
    b.field("docs_scope_note", "paragraph", ("", ""), content=(
        _label("What OG asks for", "These are OG's requests to prepare and review your petition. USCIS lists its required evidence in the Form I-751 Instructions, which are not part of this intake; OG will confirm what applies to you."),
        _label("Lo que pide OG", "Son solicitudes de OG para preparar y revisar tu petición. USCIS enumera su evidencia requerida en las Instrucciones del Formulario I-751, que no forman parte de este formulario; OG confirmará lo que aplica en tu caso.")))
    dyn(b, "docs_list", "documents")
    b.field("docs_tip", "paragraph", ("", ""), content=(
        _tip("Make sure each document is complete, readable, well lit and not cropped or blurry. Documents that are not in English may need a certified translation — OG can help."),
        _tip("Asegúrate de que cada documento esté completo, legible, bien iluminado y sin cortes ni desenfoque. Los documentos que no estén en inglés pueden necesitar una traducción certificada; OG puede ayudarte.")))

    # ================================================================== confirm
    page(b, "confirm", ("Confirm and Send to OG", "Confirma y envía a OG"), group="confirm", ctx="resident",
         desc=("Review your information and confirm that it is complete and accurate. OG Multiservices will use the information you provided to assist with preparing your Form I-751 and related documents.",
               "Revisa tu información y confirma que esté completa y correcta. OG Multiservices utilizará la información proporcionada para ayudarte con la preparación de tu Formulario I-751 y los documentos relacionados."))
    note(b, "confirm_warning", "Sending this to OG does not file anything with USCIS, is not an electronic signature, is not the Petitioner's Certification, and is not a decision about whether you qualify, whether your petition is on time, or which way of filing applies. OG will contact you about the next steps, including how signatures are handled.",
         "Enviar esto a OG no presenta nada ante USCIS, no es una firma electrónica, no es la Certificación del Peticionario y no es una decisión sobre si calificas, si tu petición está a tiempo o qué forma de presentar aplica. OG te contactará sobre los siguientes pasos, incluido cómo se manejan las firmas.")
    b.field("preparer_request", "consent", ("Request for preparation", "Solicitud de preparación"), ref="Part 7, Item 2 (preparer prepared the petition at the petitioner's request)", req=True,
            note="Customer confirmation only; not a signature.", content=("I ask OG Multiservices to assist with preparing this Form I-751 based only on the information I provided or authorized.",
                                                                          "Solicito a OG Multiservices que me ayude a preparar este Formulario I-751 con base únicamente en la información que proporcioné o autoricé."))
    b.field("confirm_accurate", "consent", ("Accuracy confirmation and authorization", "Confirmación de exactitud y autorización"), ref="Part 7 (Petitioner's Certification wording)", req=True,
            note="Customer confirmation only; not a signature and not the certification under penalty of perjury.", content=("I confirm that the information I provided is complete and correct to the best of my knowledge, and I authorize OG Multiservices to use it to assist with preparing Form I-751 and related documents.",
                                                                                                                             "Confirmo que la información que proporcioné es completa y correcta según mi leal saber y entender, y autorizo a OG Multiservices a usarla para ayudarme a preparar el Formulario I-751 y los documentos relacionados."))
    return b


def _features():
    return {
        "completeness_check": True, "consistency": "i751", "documents_check": True,
        "sections": SECTIONS, "contexts": CONTEXTS, "context_roles": CONTEXT_ROLES,
        "name_tokens": {"res": {"role": "conditional_resident", "fallback": {"en": "the conditional resident", "es": "el residente condicional"}},
                        "rel": {"role": "relevant_individual", "fallback": {"en": "the spouse", "es": "el cónyuge"}}},
        "sync": [
            {"kind": "current_address", "record_field": "r_history", "prefix": "ph"},
            {"kind": "person_records", "fields": ["k_children"]},
            {"kind": "i751_calc"},
            {"kind": "requirements_i751"},
        ],
    }


def ensure_i751_intake():
    """Create the production I-751 intake and connect it to a Removal-of-Conditions service (idempotent; never rebuilt over submissions)."""
    if Form.query.filter_by(slug=I751_SLUG).first():
        return False
    category = ServiceCategory.query.filter_by(slug="immigration").first()
    if category is None:
        return False
    service = Service.query.filter_by(category_id=category.id, slug="removal-of-conditions").first()
    if service is None:
        top = db.session.query(db.func.max(Service.sort_order)).filter(Service.category_id == category.id).scalar() or 0
        service = Service(
            category_id=category.id, slug="removal-of-conditions", admin_name="Removal of Conditions on Residence (Form I-751) Preparation", icon="immigration",
            is_published=True, sort_order=top + 10,
            title_en="Removal of Conditions on Residence (Form I-751)", title_es="Remoción de condiciones de la residencia (Formulario I-751)",
            short_en="Document preparation support for Form I-751, the petition to remove the conditions on a two-year Green Card.",
            short_es="Apoyo en la preparación de documentos para el Formulario I-751, la petición para eliminar las condiciones de una Green Card de dos años.",
            hero_text_en="Support organizing your information and documents for a Form I-751 petition, whether you file with your spouse or on your own.",
            hero_text_es="Apoyo organizando tu información y documentos para una petición I-751, ya sea que presentes con tu cónyuge o por tu cuenta.",
            content_title_en="What is Form I-751?", content_title_es="¿Qué es el Formulario I-751?",
            content_en="<p>Form I-751, Petition to Remove Conditions on Residence, is the form used by people who received conditional permanent residence (a two-year Green Card) through marriage to ask USCIS to remove those conditions. It can be filed together with a spouse, or without a spouse in some situations. OG Multiservices helps you gather and organize the information and documents so the form can be prepared. OG provides document preparation and administrative assistance only; we are not a law firm and do not provide legal advice.</p>",
            content_es="<p>El Formulario I-751, Petición para Eliminar las Condiciones de la Residencia, es el formulario que usan las personas que recibieron residencia permanente condicional (una Green Card de dos años) por matrimonio para pedir a USCIS que elimine esas condiciones. Puede presentarse junto con el cónyuge, o sin el cónyuge en algunas situaciones. OG Multiservices te ayuda a reunir y organizar la información y los documentos para que el formulario pueda prepararse. OG ofrece solo preparación de documentos y asistencia administrativa; no somos un bufete de abogados ni brindamos asesoría legal.</p>",
            nj_in_person=True, remote_nationwide=True)
        db.session.add(service)
        db.session.flush()
    form = Form(slug=I751_SLUG, name_admin="I-751 Client Intake")
    db.session.add(form)
    form.form_type = "service_intake"
    form.status = "published"
    form.source_form_name = SOURCE_NAME
    form.source_edition = SOURCE_EDITION
    form.version = 1
    form.published_at = datetime.utcnow()
    form.title_en, form.title_es = "Removal of Conditions — Form I-751", "Remoción de condiciones — Formulario I-751"
    form.description_en = "Guided intake for OG Multiservices to prepare your Form I-751. Your progress is saved automatically."
    form.description_es = "Solicitud guiada para que OG Multiservices prepare tu Formulario I-751. Tu progreso se guarda automáticamente."
    form.submit_label_en, form.submit_label_es = "Send to OG", "Enviar a OG"
    form.success_message_en = "OG Multiservices has your information and will review it. We'll contact you if we need anything else."
    form.success_message_es = "OG Multiservices tiene tu información y la revisará. Te contactaremos si necesitamos algo más."
    form.show_progress = True
    form.features_json = json.dumps(_features(), ensure_ascii=False)
    db.session.flush()
    build_i751(form)
    db.session.flush()
    service.requires_intake = True
    service.form_id = form.id
    service.requires_account = True
    service.intake_label = "I-751 Client Intake"
    db.session.commit()
    return True
