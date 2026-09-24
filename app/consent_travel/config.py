"""Consent to Travel Authorization for Minors — the guided intake. Reuses the SAME generic Step/Q/Ctx
interview engine the Tax Smart Intake built (`app/tax/questions.py`), exactly like NJ Driver License does —
that engine has no tax-specific logic in it.
"""

from app.consent_travel import rules as ct_rules
from app.tax.questions import O, Opt, Q, Step, YN3

VERSION = "v1"

TRAVELING_WITH = [O("mother", "Mother", "Madre", "👩"), O("father", "Father", "Padre", "👨"), O("other", "Another person", "Otra persona", "🧑")]
YOUR_ROLE_ALL = [O("mother", "I am the mother", "Soy la madre"), O("father", "I am the father", "Soy el padre"),
                 O("accompanying", "I am the accompanying adult", "Soy el adulto acompañante"), O("arranging", "I am arranging this for someone else", "Estoy organizando esto para alguien más")]
FATHER_ON_CERT = YN3
# NOTE: this is the Q's list of CHOICE OPTIONS, not the address/metadata dict — that's
# app.models.CT_LOCATIONS (models/consent_travel.py LOCATIONS, aliased on import to avoid the name clash
# that caused a live 500 on the Review page: summary.py once imported THIS list by the same bare name).
LOCATIONS = [O("nj", "New Jersey — Paterson", "Nueva Jersey — Paterson", "📍"), O("tx", "Texas — Spring", "Texas — Spring", "📍")]


def your_role_options(c):
    tw = c.v("traveling_with")
    if tw == "other":
        return YOUR_ROLE_ALL
    return [o for o in YOUR_ROLE_ALL if o.value != "accompanying"]


def _relevant(name):
    return lambda c: c.v("traveling_with") == name


def child_needs_father_question(c):
    return c.v("traveling_with") in ("mother", "other")


def known_fathers_opts(c):
    from app.consent_travel import people as ct_people

    if c.tax is None or c.record is None:
        return []
    fathers = ct_people.known_fathers(c.tax, exclude_child_id=c.record.id)
    return [O(str(f["person_id"]), f["name"], f["name"]) for f in fathers] + [O("new", "A different father", "Un padre diferente")]


def has_known_fathers(c):
    return child_needs_father_question(c) and c.v("father_on_cert") == "yes" and len(known_fathers_opts(c)) > 1


def needs_new_father_name(c):
    if not child_needs_father_question(c) or c.v("father_on_cert") != "yes":
        return False
    opts = known_fathers_opts(c)
    if len(opts) <= 1:
        return True  # no known fathers yet -> always ask the name
    return c.v("father_pick") == "new"


CHILD_FLOW = [
    Step("child_who", ("Child's name", "Nombre del menor"), "🧒", [
        Q("c_given", "text", ("First name", "Nombre"), req=True, bind="given_name", maxlen=120, miss=("the child's first name.", "el nombre del menor.")),
        Q("c_family", "text", ("Last name", "Apellido"), req=True, bind="family_name", maxlen=120, miss=("the child's last name.", "el apellido del menor.")),
        Q("c_dob", "date", ("Date of birth", "Fecha de nacimiento"), req=True, bind="date_of_birth", miss=("the child's date of birth.", "la fecha de nacimiento del menor.")),
    ], scope="record"),
    Step("child_docs", ("Child's documents", "Documentos del menor"), "📄", [], kind="docs", scope="record"),
    Step("child_father", ("Is the father on the birth certificate?", "¿El padre aparece en el acta de nacimiento?"), "👨", [
        Q("father_on_cert", "yn3", ("Is the father listed on this child's birth certificate?", "¿El padre aparece en el acta de nacimiento de este menor?"), options=FATHER_ON_CERT, req=True,
          show=child_needs_father_question, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        Q("father_pick", "choice", ("Is it the same father as an earlier child?", "¿Es el mismo padre que el de un menor anterior?"), options=known_fathers_opts, req=True,
          show=has_known_fathers, miss=("choose one option.", "elige una opción.")),
        Q("f_given", "text", ("Father's first name", "Nombre del padre"), req=True, maxlen=120, show=needs_new_father_name, miss=("the father's first name.", "el nombre del padre.")),
        Q("f_family", "text", ("Father's last name", "Apellido del padre"), req=True, maxlen=120, show=needs_new_father_name, miss=("the father's last name.", "el apellido del padre.")),
    ], scope="record"),
]

ADULT_FLOW = [
    Step("adult_address", ("Current address", "Dirección actual"), "🏠", [
        Q("a_street", "text", ("Street address", "Dirección"), req=True, maxlen=200, bind="address.street", miss=("the street address.", "la dirección.")),
        Q("a_unit", "text", ("Apt / Unit (optional)", "Apto / Unidad (opcional)"), bind="address.unit_number", maxlen=40),
        Q("a_city", "text", ("City", "Ciudad"), req=True, maxlen=100, bind="address.city", miss=("the city.", "la ciudad.")),
        Q("a_state", "state", ("State", "Estado"), req=True, bind="address.state", miss=("the state.", "el estado.")),
        Q("a_zip", "text", ("ZIP code", "Código postal"), req=True, maxlen=10, bind="address.zip", miss=("the ZIP code.", "el código postal.")),
    ], scope="record"),
    Step("adult_docs", ("Photo ID", "Identificación con foto"), "🪪", [], kind="docs", scope="record"),
]


def yn(key, label, **kw):
    return Q(key, "yn3", label, options=YN3, **kw)


def _layover_qs(prefix, n):
    out = []
    for i in range(1, n + 1):
        out.append(Q(f"{prefix}_lo{i}_city", "text", (f"Layover {i} — city", f"Escala {i} — ciudad"), maxlen=100,
                     show=(lambda c, i=i, prefix=prefix: c.v(f"{prefix}_layovers") not in (None, "", "0") and int(c.v(f"{prefix}_layovers") or 0) >= i),
                     req=True, miss=("the layover city.", "la ciudad de la escala.")))
        out.append(Q(f"{prefix}_lo{i}_airport", "text", (f"Layover {i} — airport", f"Escala {i} — aeropuerto"), maxlen=100,
                     show=(lambda c, i=i, prefix=prefix: c.v(f"{prefix}_layovers") not in (None, "", "0") and int(c.v(f"{prefix}_layovers") or 0) >= i),
                     req=True, miss=("the layover airport.", "el aeropuerto de la escala.")))
    return out


LAYOVER_COUNT = [O("0", "None", "Ninguna"), O("1", "1", "1"), O("2", "2", "2"), O("3", "3 or more", "3 o más")]

STEPS = [
    Step("intro", ("Consent to Travel Authorization for Minors", "Autorización de Viaje para Menores"), "✈️", [], kind="special"),
    Step("who_travels", ("Who will the minor(s) travel with?", "¿Con quién viajará el menor o los menores?"), "🧭", [
        Q("traveling_with", "choice", ("With whom will the minor(s) travel?", "¿Con quién viajará el menor o los menores?"), options=TRAVELING_WITH, req=True,
          miss=("choose who the child will travel with.", "elige con quién viajará el menor.")),
        Q("your_role", "choice", ("What is your role in this trip?", "¿Cuál es tu rol en este viaje?"), options=your_role_options, req=True,
          show=lambda c: c.v("traveling_with") is not None, miss=("choose your role.", "elige tu rol.")),
    ]),
    Step("mother_name", ("The mother's name", "El nombre de la madre"), "👩", [
        Q("mo_given", "text", ("Mother's first name", "Nombre de la madre"), req=True, maxlen=120, miss=("the mother's first name.", "el nombre de la madre.")),
        Q("mo_family", "text", ("Mother's last name", "Apellido de la madre"), req=True, maxlen=120, miss=("the mother's last name.", "el apellido de la madre.")),
    ], show=lambda c: c.v("your_role") not in (None, "mother")),
    Step("father_traveler_name", ("The father's name", "El nombre del padre"), "👨", [
        Q("fa_given", "text", ("Father's first name", "Nombre del padre"), req=True, maxlen=120, miss=("the father's first name.", "el nombre del padre.")),
        Q("fa_family", "text", ("Father's last name", "Apellido del padre"), req=True, maxlen=120, miss=("the father's last name.", "el apellido del padre.")),
    ], show=lambda c: c.v("traveling_with") == "father" and c.v("your_role") not in (None, "father")),
    Step("third_traveler_info", ("The accompanying adult", "El adulto acompañante"), "🧑", [
        Q("th_relationship", "text", ("Their relationship to the child(ren)", "Su relación con el menor o los menores"), req=True, maxlen=100,
          miss=("their relationship to the child(ren).", "su relación con el menor o los menores.")),
        Q("th_given", "text", ("Their first name", "Su nombre"), req=True, maxlen=120, show=lambda c: c.v("your_role") not in (None, "accompanying"),
          miss=("their first name.", "su nombre.")),
        Q("th_family", "text", ("Their last name", "Su apellido"), req=True, maxlen=120, show=lambda c: c.v("your_role") not in (None, "accompanying"),
          miss=("their last name.", "su apellido.")),
    ], show=lambda c: c.v("traveling_with") == "other"),
    Step("traveler_docs", ("Traveling adult's photo ID", "Identificación del adulto que viaja"), "🪪", [], kind="docs"),
    Step("children", ("Children traveling", "Menores que viajan"), "🧒", [
        Q("children_list", "records", ("Add each child one by one.", "Agrega a cada menor uno por uno."), record="child"),
    ], kind="records", record="child"),
    Step("adults", ("Consenting adults", "Adultos que consienten"), "✍️", [
        Q("adults_list", "records", ("These adults need to provide their address and a photo ID because their consent is required.",
                                     "Estos adultos deben proporcionar su dirección y una identificación con foto porque se requiere su consentimiento."), record="adult"),
    ], kind="records", record="adult", show=lambda c: bool(c.tax and c.tax.adult_records)),
    Step("contact", ("Contact information", "Información de contacto"), "📞", [
        Q("phone", "phone", ("Phone number", "Número de teléfono"), req=True, miss=("your phone number.", "tu número de teléfono.")),
        Q("wa_consent", "yn3", ("Can OG Multiservices LLC contact you via WhatsApp at this phone number?", "¿OG Multiservices LLC puede contactarle por WhatsApp a este número de teléfono?"),
          options=YN3, req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
    ]),
    Step("itinerary_out", ("Departure flight", "Vuelo de ida"), "🛫", [
        Q("out_date", "date", ("Departure date", "Fecha de salida"), req=True, flag="future_ok", miss=("the departure date.", "la fecha de salida.")),
        Q("out_dep_city", "text", ("Departure city", "Ciudad de salida"), req=True, maxlen=100, miss=("the departure city.", "la ciudad de salida.")),
        Q("out_dep_airport", "text", ("Departure airport", "Aeropuerto de salida"), req=True, maxlen=100, miss=("the departure airport.", "el aeropuerto de salida.")),
        Q("out_dest_city", "text", ("Destination city", "Ciudad de destino"), req=True, maxlen=100, miss=("the destination city.", "la ciudad de destino.")),
        Q("out_dest_country", "text", ("Destination country", "País de destino"), req=True, maxlen=100, miss=("the destination country.", "el país de destino.")),
        Q("out_arr_airport", "text", ("Arrival airport", "Aeropuerto de llegada"), req=True, maxlen=100, miss=("the arrival airport.", "el aeropuerto de llegada.")),
        Q("out_layovers", "choice", ("How many layovers on the way there?", "¿Cuántas escalas en el viaje de ida?"), options=LAYOVER_COUNT, req=True,
          miss=("choose the number of layovers.", "elige el número de escalas.")),
        *_layover_qs("out", 3),
    ]),
    Step("has_return", ("Return flight", "Vuelo de regreso"), "🛬", [
        yn("has_return", ("Does the child have a return flight?", "¿El menor tiene vuelo de regreso?"), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
    ]),
    Step("itinerary_return", ("Return flight details", "Detalles del vuelo de regreso"), "🛬", [
        Q("ret_date", "date", ("Return date", "Fecha de regreso"), req=True, flag="future_ok", miss=("the return date.", "la fecha de regreso.")),
        Q("ret_dep_city", "text", ("Departure city", "Ciudad de salida"), req=True, maxlen=100, miss=("the departure city.", "la ciudad de salida.")),
        Q("ret_dep_airport", "text", ("Departure airport", "Aeropuerto de salida"), req=True, maxlen=100, miss=("the departure airport.", "el aeropuerto de salida.")),
        Q("ret_dest_city", "text", ("Final destination city", "Ciudad de destino final"), req=True, maxlen=100, miss=("the final destination city.", "la ciudad de destino final.")),
        Q("ret_dest_airport", "text", ("Final destination airport", "Aeropuerto de destino final"), req=True, maxlen=100, miss=("the final destination airport.", "el aeropuerto de destino final.")),
        Q("ret_layovers", "choice", ("How many layovers on the way back?", "¿Cuántas escalas en el viaje de regreso?"), options=LAYOVER_COUNT, req=True,
          miss=("choose the number of layovers.", "elige el número de escalas.")),
        *_layover_qs("ret", 3),
    ], show=lambda c: c.v("has_return") == "yes"),
    Step("location", ("Notarization location", "Lugar de notarización"), "📍", [
        Q("location", "choice", ("Where would you like the notarization done?", "¿Dónde le gustaría hacer la notarización?"), options=LOCATIONS, req=True,
          miss=("choose a location.", "elige una ubicación.")),
    ]),
    Step("notes", ("Anything else OG should know?", "¿Algo más que OG deba saber?"), "📝", [
        Q("notes_text", "textarea", ("Anything else OG should know? (optional)", "¿Algo más que OG deba saber? (opcional)"), maxlen=2000),
    ]),
    Step("documents_vault", ("Your documents", "Tus documentos"), "📄", [], kind="docs"),
    Step("price", ("Estimated price", "Precio estimado"), "💲", [], kind="special"),
    Step("review", ("Your Consent to Travel Plan", "Tu Plan de Autorización de Viaje"), "📋", [], kind="special"),
    Step("send", ("Send to OG", "Enviar a OG"), "📨", [], kind="special"),
]


class Config:
    version = VERSION
    steps = STEPS
    record_flows = {"child": CHILD_FLOW, "adult": ADULT_FLOW}

    def __init__(self):
        self._index, self.step_of, self.record_keys = {}, {}, set()
        for s in STEPS + CHILD_FLOW + ADULT_FLOW:
            for q in s.questions:
                self._index[q.key] = q
                self.step_of.setdefault(q.key, s)
                if s in CHILD_FLOW or s in ADULT_FLOW:
                    self.record_keys.add(q.key)
        self.step_by_key = {s.key: s for s in STEPS}

    def index(self):
        return self._index


CONFIG = Config()
