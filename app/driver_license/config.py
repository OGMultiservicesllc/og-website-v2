"""NJ Driver License Assistance — the guided intake: one plain-language question per screen, automatic branching, nothing the customer
must calculate. Reuses the SAME generic Step/Q/Ctx interview engine the Tax Smart Intake built (`app/tax/questions.py`) — that engine has
no tax-specific logic in it, only a declarative "step -> questions -> show conditions" shape, so it is imported directly rather than
copied a second time.
"""

from app.driver_license import rules as dl_rules
from app.driver_license.countries import COUNTRIES
from app.tax.questions import O, Opt, Q, Step, YN3

VERSION = "v1"

# ------------------------------------------------------------------ option lists
PROGRESS = [
    O("not_started", "I haven't started yet", "No he comenzado todavía", "🆕"),
    O("need_permit_appt", "I need my Initial Permit appointment", "Necesito mi cita para el Initial Permit", "📅"),
    O("have_permit", "I already have my Initial Permit", "Ya tengo mi Initial Permit", "✅"),
    O("need_kt_appt", "I need my Knowledge Test appointment", "Necesito mi cita para el examen teórico", "📅"),
    O("passed_kt", "I passed my Knowledge Test", "Ya aprobé el examen teórico", "🎉"),
    O("need_road_test", "I need a Road Test", "Necesito el examen práctico", "🚗"),
    O("passed_road_test", "I already passed my Road Test", "Ya aprobé el examen práctico", "🏆"),
    O("unsure", "I'm not sure", "No estoy seguro", "🤔"),
]
DOC_OPTIONS = [
    O("passport", "Passport", "Pasaporte", "🛂"),
    O("foreign_license", "Driver License from your country", "Licencia de conducir de tu país", "🚗"),
    O("national_id", "National ID / Cédula / DNI", "Identificación nacional / Cédula / DNI", "🪪"),
    O("birth_certificate", "Birth Certificate", "Acta de Nacimiento", "📄"),
    O("permanent_resident_card", "Permanent Resident Card", "Tarjeta de Residente Permanente", "🟢"),
    O("ead_card", "Employment Authorization Document", "Documento de Autorización de Empleo", "🪪"),
    O("other", "Other", "Otro", "📎"),
    O("unsure", "I'm not sure", "No estoy seguro", "🤔", exclusive=True),
]
SSN_ITIN = [O("ssn", "Social Security Number", "Número de Seguro Social", "🇺🇸"), O("itin", "ITIN", "ITIN", "🧾"), O("neither", "Neither", "Ninguno", "🚫"), O("unsure", "I'm not sure", "No estoy seguro", "🤔")]
ITIN_EVIDENCE = [O(k, en, es) for k, en, es in dl_rules.ITIN_EVIDENCE_DOCS]
ADDRESS_DOCS = [O(k, en, es) for k, en, es in dl_rules.NJ_ADDRESS_DOCS]
LANGUAGES = [O(k, en, es) for k, en, es in dl_rules.LANGUAGES]
APPT_HELP = [O("yes", "Yes, please help me", "Sí, ayúdenme", "🙋"), O("no", "No, I'll do it myself", "No, yo lo haré", "🙅"), O("unsure", "Not sure yet", "No estoy seguro todavía", "🤔")]
COUNTRY_OPTS = [O(en, en, es) for en, es in COUNTRIES]

LANG_QUESTION_FOR = {"national_id": "lang_national_id", "birth_certificate": "lang_birth_certificate", "foreign_license": "fl_lang"}
# "Other document" translation checks that are NOT part of the identity-document priority plan (item 4): NJ address
# proof and ITIN evidence can also need translation, priced the SAME "configured price, else OG Review" way.
OTHER_TRANSLATABLE = {"address_proof": ("addr_lang", "addr_long"), "itin_evidence": ("itin_lang", None)}


def _mvc_locations(ctx):
    from app.models import MvcLocation

    rows = MvcLocation.query.filter_by(active=True).order_by(MvcLocation.sort_order, MvcLocation.name).all()
    return [Opt(str(r.id), r.name, r.name) for r in rows]


def has_translatable_selection(c):
    return any(c.has("documents", d) for d in LANG_QUESTION_FOR)


def _needs_lang(doc_key):
    return lambda c: c.has("documents", doc_key)


def yn(key, label, **kw):
    return Q(key, "yn3", label, options=YN3, **kw)


STEPS = [
    Step("intro", ("Get Your NJ Driver License", "Obtén Tu Licencia de Conducir de NJ"), "🚗", [], kind="special"),
    Step("progress", ("Where are you in the process?", "¿En qué parte del proceso estás?"), "🧭", [
        Q("where", "choice", ("Where are you in the process?", "¿En qué parte del proceso estás?"), options=PROGRESS, req=True,
          miss=("choose where you are in the process.", "elige en qué parte del proceso estás.")),
    ]),
    Step("about", ("A few basics", "Algunos datos básicos"), "👤", [
        Q("a_given", "text", ("First name", "Nombre"), req=True, bind="given_name", maxlen=120, miss=("your first name.", "tu nombre.")),
        Q("a_family", "text", ("Last name", "Apellido"), req=True, bind="family_name", maxlen=120, miss=("your last name.", "tu apellido.")),
        Q("a_dob", "date", ("Date of birth", "Fecha de nacimiento"), req=True, bind="date_of_birth", miss=("your date of birth.", "tu fecha de nacimiento.")),
        Q("a_birth_country", "select", ("Country of birth", "País de nacimiento"), req=True, bind="birth_country", options=COUNTRY_OPTS,
          miss=("your country of birth.", "tu país de nacimiento.")),
        Q("a_phone", "phone", ("Phone number", "Número de teléfono"), req=True, bind="phone_daytime", miss=("your phone number.", "tu número de teléfono.")),
        Q("a_wa_same", "yn3", ("Can we contact you on WhatsApp at this number?", "¿Podemos contactarte por WhatsApp a este número?"), options=YN3, req=True,
          miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        Q("a_wa_number", "phone", ("WhatsApp number", "Número de WhatsApp"), show=lambda c: c.v("a_wa_same") == "no",
          miss=("your WhatsApp number, or go back and choose 'Yes'.", "tu número de WhatsApp, o regresa y elige 'Sí'.")),
        Q("a_email", "email", ("Email", "Correo electrónico"), req=True, bind="email", miss=("your email.", "tu correo electrónico.")),
        Q("a_street", "text", ("New Jersey street address", "Dirección en Nueva Jersey"), req=True, bind="address.street", maxlen=200, miss=("your street address.", "tu dirección.")),
        Q("a_unit", "text", ("Apt / Unit (optional)", "Apto / Unidad (opcional)"), bind="address.unit_number", maxlen=40),
        Q("a_city", "text", ("City", "Ciudad"), req=True, bind="address.city", maxlen=100, miss=("your city.", "tu ciudad.")),
        Q("a_zip", "text", ("ZIP code", "Código postal"), req=True, bind="address.zip", maxlen=10, miss=("your ZIP code.", "tu código postal.")),
    ]),
    Step("documents", ("Which of these documents do you have?", "¿Cuáles de estos documentos tienes?"), "📋", [
        Q("documents", "multi", ("Which of these documents do you have?", "¿Cuáles de estos documentos tienes?"), options=DOC_OPTIONS, req=True,
          help=("Select everything you have. It's okay if it's not everything on the list.", "Selecciona todo lo que tengas. Está bien si no es todo lo de la lista."),
          miss=("select at least one option (or 'I'm not sure').", "elige al menos una opción (o 'No estoy seguro').")),
    ]),
    Step("ssn_itin", ("Social Security or ITIN", "Seguro Social o ITIN"), "🧾", [
        Q("ssn_itin_path", "choice", ("Do you have a Social Security Number or ITIN?", "¿Tienes un Número de Seguro Social o ITIN?"), options=SSN_ITIN, req=True,
          miss=("choose one option.", "elige una opción.")),
    ]),
    Step("itin_evidence", ("Your ITIN document", "Tu documento de ITIN"), "🧾", [
        Q("itin_evidence", "choice", ("Which document do you have showing your ITIN?", "¿Qué documento tienes que muestre tu ITIN?"), options=ITIN_EVIDENCE, req=True,
          miss=("choose one option.", "elige una opción.")),
        Q("itin_lang", "choice", ("What language is that document in?", "¿En qué idioma está ese documento?"), options=LANGUAGES, req=True,
          show=lambda c: c.v("itin_evidence") not in (None, "", "unsure"), miss=("choose a language.", "elige un idioma.")),
    ], show=lambda c: c.v("ssn_itin_path") == "itin"),
    Step("affidavit_note", ("About the affidavit option", "Sobre la opción de declaración jurada"), "ℹ️", [
        Q("affidavit_note", "note", (
            "You may be able to use an affidavit if you have never been issued an SSN or ITIN and meet the applicable MVC requirements. OG will review this with you.",
            "Es posible que puedas usar una declaración jurada si nunca te han emitido un SSN o ITIN y cumples con los requisitos aplicables del MVC. OG revisará esto contigo.")),
    ], show=lambda c: c.v("ssn_itin_path") == "neither"),
    Step("foreign_license_details", ("Your foreign driver license", "Tu licencia de conducir extranjera"), "🚗", [
        Q("fl_country", "text", ("What country issued your license?", "¿Qué país emitió tu licencia?"), req=True, maxlen=80, miss=("the country.", "el país.")),
        yn("fl_valid", ("Is it currently valid?", "¿Está vigente actualmente?"), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        Q("fl_lang", "choice", ("What language is it written in?", "¿En qué idioma está escrita?"), options=LANGUAGES, req=True, miss=("choose a language.", "elige un idioma.")),
    ], show=lambda c: c.has("documents", "foreign_license")),
    Step("doc_languages", ("Document language", "Idioma del documento"), "🌐", [
        Q("lang_national_id", "choice", ("What language is your National ID / Cédula in?", "¿En qué idioma está tu identificación nacional / cédula?"), options=LANGUAGES, req=True,
          show=_needs_lang("national_id"), miss=("choose a language.", "elige un idioma.")),
        Q("lang_birth_certificate", "choice", ("What language is your Birth Certificate in?", "¿En qué idioma está tu Acta de Nacimiento?"), options=LANGUAGES, req=True,
          show=_needs_lang("birth_certificate"), miss=("choose a language.", "elige un idioma.")),
        yn("bc_standard", ("Is it a standard, single-page birth certificate?", "¿Es un acta de nacimiento estándar de una sola página?"),
           show=lambda c: c.has("documents", "birth_certificate") and c.v("lang_birth_certificate") not in (None, "en"), req=True,
           miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
    ], show=has_translatable_selection),
    Step("address_proof", ("Proof of New Jersey address", "Comprobante de dirección de Nueva Jersey"), "🏠", [
        Q("address_doc", "choice", ("What do you have showing your New Jersey address?", "¿Qué tienes que muestre tu dirección de Nueva Jersey?"), options=ADDRESS_DOCS, req=True,
          miss=("choose one option.", "elige una opción.")),
        Q("addr_lang", "choice", ("What language is that document in?", "¿En qué idioma está ese documento?"), options=LANGUAGES, req=True,
          show=lambda c: c.v("address_doc") not in (None, "", "none", "unsure"), miss=("choose a language.", "elige un idioma.")),
        yn("addr_long", ("Is it more than one page?", "¿Tiene más de una página?"),
           show=lambda c: c.v("address_doc") not in (None, "", "none", "unsure") and c.v("addr_lang") not in (None, "en"),
           req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
    ]),
    Step("appointment", ("Appointment assistance", "Asistencia con la cita"), "📅", [
        Q("wants_appointment_help", "yn3", ("OG can assist you with scheduling your Initial Permit appointment based on MVC availability. Would you like help?",
                                             "OG puede ayudarte a programar tu cita del Initial Permit según la disponibilidad del MVC. ¿Te gustaría ayuda?"),
          options=APPT_HELP, req=True, miss=("choose one option.", "elige una opción.")),
        Q("loc1", "select", ("First choice location", "Primera opción de ubicación"), options=_mvc_locations, req=True, show=lambda c: c.v("wants_appointment_help") == "yes",
          miss=("choose a location.", "elige una ubicación.")),
        Q("loc2", "select", ("Second choice (optional)", "Segunda opción (opcional)"), options=_mvc_locations, show=lambda c: c.v("wants_appointment_help") == "yes"),
        Q("loc3", "select", ("Third choice (optional)", "Tercera opción (opcional)"), options=_mvc_locations, show=lambda c: c.v("wants_appointment_help") == "yes"),
    ], show=lambda c: c.v("where") in ("not_started", "need_permit_appt", "unsure")),
    Step("notes", ("Anything else OG should know?", "¿Algo más que OG deba saber?"), "📝", [
        Q("notes_text", "textarea", ("Anything else OG should know? (optional)", "¿Algo más que OG deba saber? (opcional)"), maxlen=2000),
    ]),
    Step("documents_vault", ("Your documents", "Tus documentos"), "📄", [], kind="docs"),
    Step("price", ("Estimated OG services", "Servicios estimados de OG"), "💲", [], kind="special"),
    Step("review", ("Your NJ Driver License Plan", "Tu Plan de Licencia de Conducir de NJ"), "📋", [], kind="special"),
    Step("send", ("Send to OG", "Enviar a OG"), "📨", [], kind="special"),
]


class Config:
    version = VERSION
    steps = STEPS

    def __init__(self):
        self._index, self.step_of, self.record_keys = {}, {}, set()
        for s in STEPS:
            for q in s.questions:
                self._index[q.key] = q
                self.step_of[q.key] = s
        self.step_by_key = {s.key: s for s in STEPS}

    def index(self):
        return self._index


CONFIG = Config()
