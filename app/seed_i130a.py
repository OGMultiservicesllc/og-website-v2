"""Form I-130A (Supplemental Information for Spouse Beneficiary) inside the EXISTING I-130 intake.

SOURCE OF TRUTH: the supplied USCIS "Form I-130A, Supplemental Information for Spouse
Beneficiary", Edition 04/01/24 (OMB No. 1615-0012, expires 02/28/2027), 6 pages. Part map:

  Part 1  Information About You (Spouse Beneficiary)
            1 A-Number, 2 USCIS account, 3.a-c name            -> ALREADY in the I-130 (Part 4, Items 1-4)
            4-7  physical address history, last 5 years         -> ben_address_history  (current entry = I-130 Part 4 Item 11)
            8-9  last address outside the U.S. (> 1 year)       -> ben_foreign_addr_status / ben_foreign_addr
            10-23 Parent 1 / Parent 2                            -> ben_parents (NOT in the I-130)
  Part 2  Employment history, last 5 years (Items 1-8)          -> ben_employment_history (current job = I-130 Part 4 Items 51-52)
  Part 3  Last occupation outside the U.S. if not shown above   -> ben_foreign_job_status / ben_foreign_job
  Part 4  Statement, contact, certification, signature
            1.a/1.b language, 2 preparer request                 -> sp_eoi / sp_language_name / spouse_preparer_request
            3-5 phone / mobile / email                           -> ALREADY in the I-130 (Part 4, Items 14-16)
            6.a/6.b signature and date                           -> not collected: OG guides the signature
  Part 5  Interpreter (only if different from the I-130's)      -> spint_*
  Part 6  Preparer (only if different from the I-130's)         -> not collected: OG prepares both forms
  Part 7  Additional Information                                -> shares the I-130 "Anything else?" answer

ONE application: the I-130A steps live in the same Form (`i-130-client-intake`), shown only when
`relationship_type == spouse`. A fact both forms need is stored ONCE and lists every form it maps
to (`FormField.source_form/source_edition/source_extra_json`). Two facts that live in two shapes
(the current address / current job) are kept identical by `intake_shared.sync_after_save`.

Nothing here decides eligibility. Existing spouse DRAFTS pick the new steps up automatically;
already SUBMITTED spouse applications are never edited: their frozen snapshot is untouched and
Admin sees a "supplemental information may still be needed" flag.
"""

import json

from app.extensions import db
from app.models import Form, FormPage, FormSubmission
from app.seed_i130 import I130_SLUG, SOURCE_EDITION as _I130_EDITION, page, records, where  # noqa: F401
from app.seed_i90 import STATE_OPTIONS, YES_NO, Builder, _address_fields  # noqa: F401
from app.seed_n400 import _cfg, note, show_page_any

I130A_EDITION = "04/01/24"
I130A = "I-130A"
ANCHOR_TITLE = "Where the beneficiary will apply"
SP = ("relationship_type", "equals", "spouse")

SECTIONS_A = [
    {"key": "spouse_address", "title": {"en": "Spouse Address History", "es": "Historial de direcciones del cónyuge"}, "supplement": "i130a"},
    {"key": "spouse_foreign_address", "title": {"en": "Last Address Outside the U.S.", "es": "Última dirección fuera de EE. UU."}, "supplement": "i130a"},
    {"key": "spouse_parents", "title": {"en": "Spouse Parents", "es": "Padres del cónyuge"}, "supplement": "i130a"},
    {"key": "spouse_employment", "title": {"en": "Spouse Employment History", "es": "Historial de empleo del cónyuge"}, "supplement": "i130a"},
    {"key": "spouse_foreign_employment", "title": {"en": "Last Employment Outside the U.S.", "es": "Último empleo fuera de EE. UU."}, "supplement": "i130a"},
    {"key": "spouse_statement", "title": {"en": "Spouse Language & Interpreter", "es": "Idioma e intérprete del cónyuge"}, "supplement": "i130a"},
]

SUPPLEMENT = {
    "form": I130A, "edition": I130A_EDITION,
    "title": {"en": "Supplemental Information for Spouse Beneficiary", "es": "Información suplementaria para el cónyuge beneficiario"},
    "customer_title": {"en": "Additional spouse information", "es": "Información adicional del cónyuge"},
    "groups": [s["key"] for s in SECTIONS_A],
    "when": {"field": "relationship_type", "equals": "spouse"},
    "required_field": "ben_address_history",
    "since_version": 2,
}

WHEN_SPOUSE = {"field": "relationship_type", "equals": "spouse"}
SYNC = [
    {"kind": "current_address", "record_field": "ben_address_history", "prefix": "ben_phys", "when": WHEN_SPOUSE},
    {"kind": "current_employment", "record_field": "ben_employment_history", "prefix": "ben_emp", "employed": "ben_employed",
     "name": "ben_emp_name", "start": "ben_emp_start", "when": WHEN_SPOUSE},
    {"kind": "drop_stale_candidate", "status_field": "ben_foreign_addr_status", "status_value": "different", "record_field": "ben_foreign_addr",
     "source": "ben_address_history", "candidate": "last_foreign_address", "when": WHEN_SPOUSE},
    {"kind": "completed_event", "field": "sp_statement_note", "event": "spouse_supplement_completed", "when": WHEN_SPOUSE},
]

# An answer the I-130 already collects that Form I-130A also needs: (field, I-130A reference).
SHARED = [
    ("ben_family", "Part 1, Item 3.a"), ("ben_given", "Part 1, Item 3.b"), ("ben_middle", "Part 1, Item 3.c"),
    ("ben_a_number", "Part 1, Item 1"), ("ben_uscis_account", "Part 1, Item 2"),
    ("ben_phone", "Part 4, Item 3"), ("ben_mobile", "Part 4, Item 4"), ("ben_email", "Part 4, Item 5"),
    ("ben_phys_street", "Part 1, Item 4.a (current address = Physical Address 1)"), ("ben_phys_unit_type", "Part 1, Item 4.b"),
    ("ben_phys_unit_number", "Part 1, Item 4.b"), ("ben_phys_city", "Part 1, Item 4.c"), ("ben_phys_state", "Part 1, Item 4.d"),
    ("ben_phys_zip", "Part 1, Item 4.e"), ("ben_phys_province", "Part 1, Item 4.f"), ("ben_phys_postal_code", "Part 1, Item 4.g"),
    ("ben_phys_country", "Part 1, Item 4.h"),
    ("ben_emp_name", "Part 2, Item 1 (current employer = Employer 1)"), ("ben_emp_street", "Part 2, Item 2.a"), ("ben_emp_unit_number", "Part 2, Item 2.b"),
    ("ben_emp_city", "Part 2, Item 2.c"), ("ben_emp_state", "Part 2, Item 2.d"), ("ben_emp_zip", "Part 2, Item 2.e"),
    ("ben_emp_province", "Part 2, Item 2.f"), ("ben_emp_postal_code", "Part 2, Item 2.g"), ("ben_emp_country", "Part 2, Item 2.h"),
    ("ben_emp_start", "Part 2, Item 4.a"), ("additional_information", "Part 7. Additional Information"),
]


def _mark(b, name, *, note_=None):
    """The field's PRIMARY mapping is Form I-130A (not the intake's own I-130)."""
    f = b.fields[name]
    f.source_form, f.source_edition = I130A, I130A_EDITION
    if note_:
        f.source_note = note_
    return f


def fld(b, name, ftype, label, ref, **kw):
    b.field(name, ftype, label, ref=ref, **kw)
    return _mark(b, name)


def rec(b, name, label, ref, record, **kw):
    records(b, name, label, ref, record, **kw)
    return _mark(b, name)


def para(b, name, en, es):
    b.field(name, "paragraph", ("", ""), content=(en, es))


SMALL = 'class="text-[13px] text-slate-500"'
CHIP = ('<span class="inline-flex items-center rounded-full border border-slate-200 bg-fog-50 px-2.5 py-1 text-[11px] font-bold '
        'uppercase tracking-wider text-slate-600">Form I-130A &middot; {t}</span>')


def build_supplement(form):
    b = Builder(form)
    b.fields = {f.internal_name: f for f in form.all_fields}
    b.page_order = 10000
    kw = dict(ctx="beneficiary")

    # ------------------------------------------------------------ 1. intro (customer-friendly, conversational)
    page(b, "sp_intro", ("Additional information about your spouse", "Información adicional sobre tu cónyuge"), group="spouse_address", **kw)
    para(b, "sp_intro_body",
         CHIP.format(t="Supplemental information") + '<span class="block mt-3 text-[15px] text-slate-700">Because this petition is for your spouse, we need some additional '
         'information about {ben} to complete the spouse portion of your petition.</span>'
         '<span class="block mt-3 text-[13px] text-slate-500">We already have {ben}\'s name, A-Number and USCIS account number, contact details and '
         'current address from the earlier steps, so we will not ask for them again.</span>',
         CHIP.format(t="Información suplementaria") + '<span class="block mt-3 text-[15px] text-slate-700">Como esta petición es para tu cónyuge, necesitamos información '
         'adicional sobre {ben} para completar la información correspondiente a tu petición.</span>'
         '<span class="block mt-3 text-[13px] text-slate-500">Ya tenemos el nombre, el Número A y el número de cuenta de USCIS, los datos de contacto y la '
         'dirección actual de {ben} de los pasos anteriores, así que no los pediremos de nuevo.</span>')
    b.rule("show_page", "sp_intro", [SP])

    # ------------------------------------------------------------ 2. physical address history (Part 1, Items 4-7)
    page(b, "sp_addresses", ("Where {ben} has lived", "Dónde ha vivido {ben}"),
         ("Start with where {ben} lives now, then add each previous address until the last five years are covered — inside or outside the United States.",
          "Empieza con donde vive {ben} ahora y agrega cada dirección anterior hasta cubrir los últimos cinco años, dentro o fuera de los Estados Unidos."),
         group="spouse_address", **kw)
    f = rec(b, "ben_address_history", ("Physical addresses for the last five years", "Direcciones físicas de los últimos cinco años"), "Part 1, Items 4.a–7.b", "address",
            req=True, max=20, timeline={"years": 5, "gap_days": 3, "overlap_days": 31},
            default_from={"prefix": "ben_phys", "present": True},
            intro={"en": "We started with {ben}'s current address from the earlier steps — just add the date {ben} began living there.",
                   "es": "Empezamos con la dirección actual de {ben} de los pasos anteriores; solo agrega la fecha en que {ben} empezó a vivir ahí."},
            help=("Add where {ben} lived before this address, one at a time, until the period is covered.",
                  "Agrega dónde vivía {ben} antes de esta dirección, una por una, hasta cubrir el período."))
    f.source_note = ("The form has two address blocks (Items 4-5 and 6-7): the first two entries map there, any further entries go in Part 7. "
                     "The current entry is the same fact as I-130 Part 4 Item 11 (stored once, kept in sync).")
    b.rule("show_page", "sp_addresses", [SP])

    # ------------------------------------------------------------ 3. last address outside the U.S. (Items 8-9)
    page(b, "sp_fa_q", ("{ben}'s last address outside the U.S.", "Última dirección de {ben} fuera de EE. UU."), group="spouse_foreign_address", **kw)
    para(b, "sp_fa_intro",
         "The form also asks for {ben}'s last address outside the United States where {ben} lived for more than one year — even if it is already in the history you just entered.",
         "El formulario también pide la última dirección de {ben} fuera de los Estados Unidos donde {ben} vivió por más de un año, aunque ya esté en el historial que acabas de ingresar.")
    para(b, "sp_fa_found", "", "")
    b.fields["sp_fa_found"].config_json = json.dumps({"dynamic": {
        "candidate": "last_foreign_address", "source": "ben_address_history", "record": "address",
        "none": {"en": "We did not find an address outside the U.S. of more than one year in {ben}'s history.",
                 "es": "No encontramos en el historial de {ben} una dirección fuera de EE. UU. de más de un año."}}})
    fld(b, "ben_foreign_addr_status", "single_choice", ("Did {ben} live at an address outside the United States for more than one year?", "¿{ben} vivió en una dirección fuera de los Estados Unidos por más de un año?"),
        "Part 1, Items 8–9 (OG helper)", req=True,
        opts=[("yes_history", "Yes — it is the address shown above", "Sí — es la dirección que aparece arriba"),
              ("different", "Yes — at a different address (for example, an older one)", "Sí — en otra dirección (por ejemplo, una más antigua)"),
              ("never", "No — has not lived outside the U.S. for more than one year", "No — no ha vivido fuera de EE. UU. por más de un año")],
        help=("If the address is older than the five years above, choose the second option and enter it next.",
              "Si la dirección es anterior a los cinco años de arriba, elige la segunda opción y la ingresas a continuación."))
    b.fields["ben_foreign_addr_status"].source_note = "Confirms (or replaces) the address reused from the history for Items 8-9; “No” leaves Items 8-9 blank."
    b.rule("show_page", "sp_fa_q", [SP])

    page(b, "sp_fa", ("The address where {ben} lived outside the U.S.", "La dirección donde {ben} vivió fuera de EE. UU."),
         ("Check the address and the dates, or enter the correct one.", "Revisa la dirección y las fechas, o ingresa la correcta."), group="spouse_foreign_address", **kw)
    rec(b, "ben_foreign_addr", ("Last address outside the United States (more than one year)", "Última dirección fuera de los Estados Unidos (más de un año)"),
        "Part 1, Items 8.a–9.b", "foreign_address", req=True, max=1,
        default_from={"candidate": "last_foreign_address", "source": "ben_address_history", "when": {"field": "ben_foreign_addr_status", "equals": "yes_history"}})
    show_page_any(b, "sp_fa", [[SP, ("ben_foreign_addr_status", "equals", "yes_history")], [SP, ("ben_foreign_addr_status", "equals", "different")]])

    # ------------------------------------------------------------ 4. parents (Items 10-23)
    page(b, "sp_parents", ("About {ben}'s parents", "Sobre los padres de {ben}"),
         ("The form asks for information about both of {ben}'s parents. Leave blank anything you do not know.",
          "El formulario pide información sobre ambos padres de {ben}. Deja en blanco lo que no sepas."), group="spouse_parents", **kw)
    rec(b, "ben_parents", ("{ben}'s parents", "Los padres de {ben}"), "Part 1, Items 10.a–23", "ben_parent", max=2,
        help=("Add each parent, one at a time.", "Agrega a cada padre o madre, uno por uno."))
    b.rule("show_page", "sp_parents", [SP])

    # ------------------------------------------------------------ 5. employment history (Part 2)
    page(b, "sp_employment", ("Where {ben} has worked", "Dónde ha trabajado {ben}"),
         ("Start with {ben}'s current work, then go back through the last five years — inside or outside the United States. If {ben} is not working, add “Unemployed”.",
          "Empieza con el trabajo actual de {ben} y ve hacia atrás durante los últimos cinco años, dentro o fuera de los Estados Unidos. Si {ben} no trabaja, agrega “Desempleado(a)”."),
         group="spouse_employment", **kw)
    f = rec(b, "ben_employment_history", ("{ben}'s employment for the last five years", "El empleo de {ben} durante los últimos cinco años"), "Part 2, Items 1–8.b", "employment",
            req=True, max=15, timeline={"years": 5, "gap_days": 3, "overlap_days": 31}, types=["employed", "self_employed", "unemployed"],
            default_from={"employment": {"employed": "ben_employed", "name": "ben_emp_name", "prefix": "ben_emp", "start": "ben_emp_start"}},
            intro={"en": "We started with {ben}'s current job from the earlier steps — add what is missing, such as the occupation.",
                   "es": "Empezamos con el trabajo actual de {ben} de los pasos anteriores; agrega lo que falte, como la ocupación."},
            help=("The form asks for employers only. If {ben} was self-employed or not working, choose that option and we will record it for you.",
                  "El formulario pide solo empleadores. Si {ben} trabajó por cuenta propia o no trabajaba, elige esa opción y lo anotaremos por ti."))
    f.source_note = ("The form has two employer blocks (Items 1-4 and 5-8): the first two entries map there, further entries go in Part 7. "
                     "The current job is the same fact as I-130 Part 4 Items 51-52 (stored once, kept in sync). Unemployed is typed in Item 1.")
    b.rule("show_page", "sp_employment", [SP])

    # ------------------------------------------------------------ 6. last employment outside the U.S. (Part 3)
    page(b, "sp_fj_q", ("{ben}'s work outside the U.S.", "Trabajo de {ben} fuera de EE. UU."), group="spouse_foreign_employment", **kw)
    para(b, "sp_fj_intro", "The form also asks for {ben}'s last job outside the United States, if it is not already in the history above.",
         "El formulario también pide el último empleo de {ben} fuera de los Estados Unidos, si no está ya en el historial de arriba.")
    para(b, "sp_fj_found", "", "")
    b.fields["sp_fj_found"].config_json = json.dumps({"dynamic": {
        "candidate": "last_foreign_job", "source": "ben_employment_history", "record": "employment",
        "none": {"en": "We did not find a job outside the U.S. in {ben}'s history.", "es": "No encontramos un empleo fuera de EE. UU. en el historial de {ben}."}}})
    fld(b, "ben_foreign_job_status", "single_choice", ("Has {ben} ever worked outside the United States?", "¿{ben} ha trabajado alguna vez fuera de los Estados Unidos?"),
        "Part 3 (OG helper; if none, Part 7)", req=True,
        opts=[("yes_history", "Yes — it is the job shown above", "Sí — es el empleo que aparece arriba"),
              ("different", "Yes — a different job that is not shown above", "Sí — otro empleo que no aparece arriba"),
              ("never", "No — never worked outside the U.S.", "No — nunca ha trabajado fuera de EE. UU.")],
        help=("If {ben} never worked outside the U.S., the form asks for that to be noted in Additional Information — OG will take care of it.",
              "Si {ben} nunca trabajó fuera de EE. UU., el formulario pide anotarlo en Información adicional; OG se encargará."))
    b.fields["ben_foreign_job_status"].source_note = "Part 3 is only completed when the last job outside the U.S. is not already shown in Part 2."
    b.rule("show_page", "sp_fj_q", [SP])

    page(b, "sp_fj", ("{ben}'s last job outside the U.S.", "Último empleo de {ben} fuera de EE. UU."), group="spouse_foreign_employment", **kw)
    rec(b, "ben_foreign_job", ("Last job outside the United States", "Último empleo fuera de los Estados Unidos"), "Part 3, Items 1–4.b", "foreign_employment",
        req=True, max=1, types=["employed", "self_employed"])
    show_page_any(b, "sp_fj", [[SP, ("ben_foreign_job_status", "equals", "different")]])

    # ------------------------------------------------------------ 7. language / interpreter (Parts 4-5)
    page(b, "sp_language", ("How {ben} will review the form", "Cómo revisará el formulario {ben}"),
         ("Form I-130A has its own statement for {ben}. We only need to know the language {ben} understands.",
          "El Formulario I-130A tiene su propia declaración para {ben}. Solo necesitamos saber en qué idioma entiende {ben}."), group="spouse_statement", **kw)
    fld(b, "sp_eoi", "single_choice", ("Which of these is true for {ben}?", "¿Cuál de estas opciones es cierta para {ben}?"), "Part 4, Items 1.a / 1.b", req=True,
        opts=[("english", "The spouse can read and understand English, and has read and understands every question and instruction on this form and the answer to every question.",
               "El cónyuge puede leer y entender inglés, y ha leído y entiende cada pregunta e instrucción de este formulario y la respuesta a cada pregunta."),
              ("interpreter", "An interpreter read to the spouse every question and instruction on this form and the answer to every question, in a language the spouse is fluent in, and the spouse understood everything.",
               "Un intérprete le leyó al cónyuge cada pregunta e instrucción de este formulario y la respuesta a cada pregunta, en un idioma en el que el cónyuge es fluido, y el cónyuge entendió todo.")])
    fld(b, "sp_language_name", "short_answer", ("Language in which {ben} is fluent", "Idioma en el que {ben} es fluente"), "Part 4, Item 1.b (language)", req=True)
    fld(b, "sp_interp_same", "single_choice", ("Is the interpreter the same one used for your Form I-130?", "¿El intérprete es el mismo que se usó para tu Formulario I-130?"),
        "OG helper (Part 5 applies only if different from the I-130 interpreter)", req=True, opts=YES_NO,
        help=("The form asks for a separate interpreter only when it is a different person.", "El formulario pide un intérprete aparte solo cuando es una persona distinta."))
    b.rule("show_field", "sp_language_name", [("sp_eoi", "equals", "interpreter")])
    b.rule("show_field", "sp_interp_same", [("sp_eoi", "equals", "interpreter"), ("english_or_interpreter", "equals", "interpreter")], "all")
    para(b, "sp_contact_note", f'<span {SMALL}>Form I-130A also asks for {{ben}}\'s phone and email. We already have them from the earlier steps, so we will not ask again.</span>',
         f'<span {SMALL}>El Formulario I-130A también pide el teléfono y el correo electrónico de {{ben}}. Ya los tenemos de los pasos anteriores, así que no los pediremos de nuevo.</span>')
    b.rule("show_page", "sp_language", [SP])

    page(b, "sp_interp", ("The interpreter for {ben}", "El intérprete de {ben}"),
         ("Information about the interpreter used for Form I-130A (Part 5).", "Información del intérprete usado para el Formulario I-130A (Parte 5)."), group="spouse_statement", **kw)
    fld(b, "spint_family", "short_answer", ("Interpreter's family name (last name)", "Apellido del intérprete"), "Part 5, Item 1.a", req=True, width="half")
    fld(b, "spint_given", "short_answer", ("Interpreter's given name (first name)", "Nombre del intérprete"), "Part 5, Item 1.b", req=True, width="half")
    fld(b, "spint_org", "short_answer", ("Interpreter's business or organization name (if any)", "Empresa u organización del intérprete (si aplica)"), "Part 5, Item 2", maxlen=38)
    fld(b, "spint_phone", "phone", ("Interpreter's daytime telephone number", "Teléfono de día del intérprete"), "Part 5, Item 4", req=True, width="half")
    fld(b, "spint_mobile", "phone", ("Interpreter's mobile telephone number (if any)", "Teléfono móvil del intérprete (si tiene)"), "Part 5, Item 5", width="half")
    fld(b, "spint_email", "email", ("Interpreter's email address (if any)", "Correo electrónico del intérprete (si tiene)"), "Part 5, Item 6")
    b.fields["spint_email"].required = False
    page(b, "sp_interp_addr", ("Interpreter's mailing address", "Dirección postal del intérprete"), group="spouse_statement", **kw)
    _address_fields(b, "spint", "Part 5, Items 3.a–3.h")
    for name in [n for n in b.fields if n.startswith("spint_") and n not in ("spint_family", "spint_given", "spint_org", "spint_phone", "spint_mobile", "spint_email")]:
        _mark(b, name)
    for name, value in {"spint_family": "@biz:INTERPRETER_LAST_NAME", "spint_given": "@biz:INTERPRETER_FIRST_NAME", "spint_org": "@biz:INTERPRETER_ORG",
                        "spint_phone": "@biz:INTERPRETER_PHONE", "spint_email": "@biz:INTERPRETER_EMAIL", "spint_is_us": "yes", "spint_street": "@biz:OFFICE_STREET",
                        "spint_unit_type": "@biz:OFFICE_UNIT_TYPE", "spint_unit_number": "@biz:OFFICE_UNIT_NUMBER", "spint_city": "@biz:OFFICE_CITY",
                        "spint_state": "@biz:OFFICE_STATE", "spint_zip": "@biz:OFFICE_ZIP"}.items():
        b.fields[name].default_value = value
    interp_alts = [[SP, ("sp_eoi", "equals", "interpreter"), ("english_or_interpreter", "equals", "english")],
                   [SP, ("sp_eoi", "equals", "interpreter"), ("sp_interp_same", "equals", "no")]]
    show_page_any(b, "sp_interp", interp_alts)
    show_page_any(b, "sp_interp_addr", interp_alts)

    # ------------------------------------------------------------ 8. signature (explanation only)
    page(b, "sp_statement", ("About {ben}'s signature", "Sobre la firma de {ben}"), group="spouse_statement", **kw)
    para(b, "sp_statement_note",
         "Form I-130A includes a statement, certification and signature section for {ben}. You do not sign or certify anything here. The form itself says a spouse who lives "
         "overseas still completes the form but does not need to sign it. OG will tell you whether a signature is needed, and how to provide it, once we know how the petition will be filed.",
         "El Formulario I-130A incluye una sección de declaración, certificación y firma para {ben}. Aquí no firmas ni certificas nada. El propio formulario indica que un cónyuge que vive "
         "en el extranjero igual completa el formulario pero no necesita firmarlo. OG te dirá si se necesita una firma, y cómo darla, cuando sepamos cómo se presentará la petición.")
    b.rule("show_page", "sp_statement", [SP])

    # ------------------------------------------------------------ 9. two confirmations on the existing last step
    confirm = next(p for p in form.pages if p.title_en == "Confirm and Send to OG")
    b.page = confirm
    b._order = max(f.sort_order for f in confirm.fields) + 1
    fld(b, "spouse_preparer_request", "consent", ("Request for preparation — spouse information", "Solicitud de preparación — información del cónyuge"), "Part 4, Item 2",
        req=True, note="Preparer prepared the form at the spouse beneficiary's request. Customer confirmation only; not a signature.",
        content=("I ask OG Multiservices to prepare the Form I-130A information about my spouse based only on the information provided or authorized.",
                 "Solicito a OG Multiservices que prepare la información del Formulario I-130A sobre mi cónyuge con base únicamente en la información proporcionada o autorizada."))
    fld(b, "confirm_spouse_info", "consent", ("Accuracy confirmation — spouse information", "Confirmación de exactitud — información del cónyuge"), "Part 4 (statement wording)",
        req=True, note="Customer confirmation only; not a signature and not the beneficiary's certification.",
        content=("I confirm that the additional information I provided about my spouse is complete, true, and correct to the best of my knowledge, and I authorize OG Multiservices "
                 "to use it to prepare Form I-130A and related documents.",
                 "Confirmo que la información adicional que proporcioné sobre mi cónyuge es completa, verdadera y correcta según mi leal saber y entender, y autorizo a OG Multiservices "
                 "a usarla para preparar el Formulario I-130A y los documentos relacionados."))
    for name in ("spouse_preparer_request", "confirm_spouse_info"):
        b.rule("show_field", name, [SP])
    return b


# Two blocks: the history steps follow the beneficiary section; the spouse's language / interpreter / signature steps
# follow the PETITIONER's own interpreter steps (Part 5's "same interpreter as the I-130?" depends on that answer).
BLOCK_1 = ["sp_intro", "sp_addresses", "sp_fa_q", "sp_fa", "sp_parents", "sp_employment", "sp_fj_q", "sp_fj"]
BLOCK_2 = ["sp_language", "sp_interp", "sp_interp_addr", "sp_statement"]


def ensure_i130a_supplement():
    """Add the I-130A spouse supplement to the existing I-130 intake (idempotent)."""
    form = Form.query.filter_by(slug=I130_SLUG).first()
    if not form or not form.source_edition:
        return False
    feats = form.features
    if "i130a" in (feats.get("supplements") or {}):
        return False
    old_pages = sorted(form.pages, key=lambda p: p.sort_order)
    anchor = next((i for i, p in enumerate(old_pages) if p.title_en == ANCHOR_TITLE), None)
    anchor2 = next((i for i, p in enumerate(old_pages) if any(f.internal_name == "int_state" for f in p.fields)), None)
    if anchor is None or anchor2 is None or anchor2 < anchor:
        return False

    b = build_supplement(form)

    # -- the same answer maps to both forms
    fields = b.fields
    for name, ref in SHARED:
        f = fields.get(name)
        if f is not None:
            extra = json.loads(f.source_extra_json) if f.source_extra_json else []
            extra.append({"form": I130A, "edition": I130A_EDITION, "ref": ref})
            f.source_extra_json = json.dumps(extra, ensure_ascii=False)

    # -- place the new steps right after the beneficiary section and renumber
    block1 = [b.pages[k] for k in BLOCK_1]
    block2 = [b.pages[k] for k in BLOCK_2]
    final = old_pages[: anchor + 1] + block1 + old_pages[anchor + 1: anchor2 + 1] + block2 + old_pages[anchor2 + 1:]
    for i, p in enumerate(final):
        p.sort_order = i
    old_index = {p.id: i + 1 for i, p in enumerate(old_pages)}  # 1-based position before the change
    new_index = {p.id: i + 1 for i, p in enumerate(final)}
    for sub in FormSubmission.query.filter_by(form_id=form.id).all():  # keep every saved position pointing at the same step
        if sub.is_complete or sub.status == "reopened":
            sub.current_page = len(final)
        else:
            current = (sub.current_page or 1)
            page = old_pages[min(current, len(old_pages)) - 1]
            sub.current_page = new_index[page.id]

    # -- form-level configuration
    sections = list(feats.get("sections") or [])
    at = next((i for i, s in enumerate(sections) if s["key"] == "ben_immigration"), len(sections) - 1) + 1
    feats["sections"] = sections[:at] + SECTIONS_A + sections[at:]
    feats["supplements"] = dict(feats.get("supplements") or {}, i130a=SUPPLEMENT)
    feats["name_tokens"] = {"ben": {"field": "ben_given", "fallback": {"en": "your spouse", "es": "tu cónyuge"}}}
    feats["sync"] = SYNC
    form.features_json = json.dumps(feats, ensure_ascii=False)
    form.version = (form.version or 1) + 1
    db.session.commit()
    return True
