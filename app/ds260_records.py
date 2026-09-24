"""DS-260 (Department of State / CEAC) record types, registered into `intake_records.RECORD_TYPES`.

Text answered here is prepared for CEAC in English by OG; every person-shaped record may point at a real Person of the customer (`person_id`, verified
server-side, never trusted on its own). Fields the 2019 sample lets the applicant answer "Do Not Know" are simply optional: a blank one is entered as
"Do Not Know" by OG only where CEAC allows it (see `ds260_ceac`).
"""

from app.intake_records import RECORD_TYPES, _f, _person_select

_NEW = {"field": "person_id", "values": ["", None]}
NAMES = [
    _person_select(),
    _f("family", "text", "Surnames (family name)", "Apellidos", maxlen=60, width="half", show=_NEW),
    _f("given", "text", "Given names", "Nombres", maxlen=60, width="half", show=_NEW),
]
BIRTH = [
    _f("dob", "date", "Date of birth", "Fecha de nacimiento", width="half"),
    _f("birth_city", "text", "City of birth", "Ciudad de nacimiento", maxlen=60, width="half"),
    _f("birth_state", "text", "State / province of birth", "Estado / provincia de nacimiento", maxlen=60, width="half"),
    _f("birth_country", "text", "Country of birth", "País de nacimiento", maxlen=60, width="half"),
]
YN = [("yes", "Yes", "Sí"), ("no", "No", "No")]
IMMIGRATING = [("now", "Yes — together with me", "Sí — junto conmigo"), ("later", "Later (separate application)", "Más adelante (solicitud aparte)"), ("no", "No", "No"),
               ("unsure", "Not sure — OG will review", "No estoy seguro(a) — OG lo revisará")]
FILL_EXTRA = {"birth_city": "birth_city", "birth_state": "birth_state", "birth_country": "birth_country"}


def loc(show, prefix="addr_", req=True):
    return [
        _f(prefix + "street", "text", "Street address (line 1)", "Dirección (línea 1)", req=req, maxlen=80, show=show),
        _f(prefix + "street2", "text", "Street address (line 2, optional)", "Dirección (línea 2, opcional)", maxlen=80, show=show),
        _f(prefix + "city", "text", "City", "Ciudad", req=req, maxlen=60, show=show, width="half"),
        _f(prefix + "state", "text", "State / province (if any)", "Estado / provincia (si aplica)", maxlen=60, show=show, width="half"),
        _f(prefix + "postal", "text", "Postal / ZIP code (if any)", "Código postal / ZIP (si aplica)", maxlen=20, show=show, width="half"),
        _f(prefix + "country", "text", "Country / region", "País / región", req=req, maxlen=60, show=show, width="half"),
    ]


def _type(kind, title_en, title_es, fields, card, *, date_fields=(), add=None, empty=None):
    add = add or {"en": "Add", "es": "Agregar"}
    return {"kind": kind, "title": {"en": title_en, "es": title_es}, "timeline": False, "date_fields": date_fields, "fields": fields, "card": card,
            "add": add, "add_first": add, "empty": empty or {"en": "Nothing added yet.", "es": "Aún no has agregado nada."}}


RECORD_TYPES["ds_parent"] = _type(
    "ds_person", "Parent", "Padre o madre",
    NAMES + BIRTH + [_f("living", "choice", "Is this parent still living?", "¿Este padre o madre sigue con vida?", req=True, options=YN + [("unknown", "I do not know", "No lo sé")])]
    + loc({"field": "living", "values": ["yes"]}, req=False),
    {"title": ["given", "family"], "sub": ["dob", "birth_country"]}, add={"en": "Add this parent", "es": "Agregar a este padre o madre"})
RECORD_TYPES["ds_spouse"] = _type(
    "ds_person", "Spouse", "Cónyuge",
    NAMES + BIRTH + [_f("addr", "choice", "Where does your spouse live?", "¿Dónde vive tu cónyuge?", req=True,
                        options=[("same", "Same as my present address", "La misma que mi dirección actual"), ("other", "A different address", "Una dirección diferente")])]
    + loc({"field": "addr", "values": ["other"]}) + [
        _f("occupation", "text", "Spouse's occupation (or “Not employed”)", "Ocupación del cónyuge (o “Sin empleo”)", maxlen=60),
        _f("marriage_date", "date", "Date of marriage", "Fecha del matrimonio", req=True, width="half"),
        _f("marriage_city", "text", "City where you married", "Ciudad donde se casaron", maxlen=60, width="half"),
        _f("marriage_state", "text", "State / province where you married", "Estado / provincia donde se casaron", maxlen=60, width="half"),
        _f("marriage_country", "text", "Country where you married", "País donde se casaron", req=True, maxlen=60, width="half"),
        _f("immigrating", "choice", "Is your spouse applying for a U.S. immigrant visa with you?", "¿Tu cónyuge solicita una visa de inmigrante de EE. UU. contigo?", req=True, options=IMMIGRATING)],
    {"title": ["given", "family"], "sub": ["marriage_date", "marriage_country"]}, add={"en": "Add your spouse", "es": "Agregar a tu cónyuge"})
RECORD_TYPES["ds_prev_spouse"] = _type(
    "ds_person", "Previous spouse", "Cónyuge anterior",
    NAMES + [
        _f("dob", "date", "Date of birth", "Fecha de nacimiento", width="half"),
        _f("marriage_date", "date", "Date of marriage", "Fecha del matrimonio", req=True, width="half"),
        _f("ended_date", "date", "Date the marriage ended", "Fecha en que terminó el matrimonio", req=True, width="half"),
        _f("how_ended", "select", "How did the marriage end?", "¿Cómo terminó el matrimonio?", req=True,
           options=[("death", "Death of spouse", "Fallecimiento del cónyuge"), ("divorce", "Divorce", "Divorcio"), ("annulment", "Annulment", "Anulación"), ("other", "Other", "Otro")]),
        _f("how_other", "text", "Explain (other)", "Explica (otro)", req=True, maxlen=120, show={"field": "how_ended", "values": ["other"]}),
        _f("end_country", "text", "Country / region where the marriage ended", "País / región donde terminó el matrimonio", req=True, maxlen=60)],
    {"title": ["given", "family"], "sub": ["marriage_date", "ended_date", "how_ended"]}, add={"en": "Add a previous spouse", "es": "Agregar un cónyuge anterior"})
RECORD_TYPES["ds_child"] = _type(
    "ds_person", "Child", "Hijo(a)",
    NAMES + BIRTH + [
        _f("relationship", "select", "Relationship to you", "Relación contigo", req=True,
           options=[("biological", "Biological son or daughter", "Hijo(a) biológico(a)"), ("adopted", "Adopted son or daughter", "Hijo(a) adoptado(a)"), ("stepchild", "Stepchild", "Hijastro(a)")]),
        _f("lives_with", "choice", "Does this child live with you?", "¿Este hijo(a) vive contigo?", req=True, options=YN),
        _f("immigrating", "choice", "Is this child applying for a U.S. immigrant visa with you?", "¿Este hijo(a) solicita una visa de inmigrante de EE. UU. contigo?", req=True, options=IMMIGRATING)],
    {"title": ["given", "family"], "sub": ["dob", "relationship"]}, add={"en": "Add another child", "es": "Agregar otro hijo(a)"})
RECORD_TYPES["ds_visit"] = _type(
    "ds_generic", "U.S. visit", "Visita a EE. UU.",
    [_f("arrived", "date", "Date arrived", "Fecha de llegada", req=True, width="half"),
     _f("stay_number", "text", "Length of stay (number)", "Duración de la estadía (número)", req=True, maxlen=4, width="half", pattern=r"\d{1,4}"),
     _f("stay_unit", "select", "Length of stay (unit)", "Duración de la estadía (unidad)", req=True,
        options=[("days", "Day(s)", "Día(s)"), ("weeks", "Week(s)", "Semana(s)"), ("months", "Month(s)", "Mes(es)"), ("years", "Year(s)", "Año(s)"), ("lt24", "Less than 24 hours", "Menos de 24 horas")])],
    {"title": ["arrived"], "sub": ["stay_number", "stay_unit"]}, add={"en": "Add another visit", "es": "Agregar otra visita"})
RECORD_TYPES["ds_phone"] = _type("ds_generic", "Telephone number", "Número de teléfono", [_f("number", "text", "Telephone number", "Número de teléfono", req=True, maxlen=30)], {"title": ["number"]},
                                 add={"en": "Add another number", "es": "Agregar otro número"})
RECORD_TYPES["ds_email"] = _type("ds_generic", "Email address", "Correo electrónico", [_f("email", "text", "Email address", "Correo electrónico", req=True, maxlen=80)], {"title": ["email"]},
                                 add={"en": "Add another email", "es": "Agregar otro correo"})
_SOCIAL = [_f("platform", "text", "Platform (as CEAC lists it)", "Plataforma (como la lista CEAC)", req=True, maxlen=60, width="half"),
           _f("identifier", "text", "Username or handle (never a password)", "Usuario o identificador (nunca una contraseña)", req=True, maxlen=80, width="half")]
RECORD_TYPES["ds_social"] = _type("ds_generic", "Social media", "Red social", _SOCIAL, {"title": ["platform"], "sub": ["identifier"]}, add={"en": "Add another account", "es": "Agregar otra cuenta"})
RECORD_TYPES["ds_social_other"] = _type(
    "ds_generic", "Other website or application", "Otro sitio web o aplicación",
    [dict(_SOCIAL[0], label={"en": "Website or application name", "es": "Nombre del sitio web o aplicación"}), _SOCIAL[1]],
    {"title": ["platform"], "sub": ["identifier"]}, add={"en": "Add another", "es": "Agregar otro"})
RECORD_TYPES["ds_prev_job"] = _type(
    "ds_generic", "Previous employer", "Empleador anterior",
    [_f("employer", "text", "Employer name", "Nombre del empleador", req=True, maxlen=80)] + loc(None) + [
        _f("phone", "text", "Telephone number", "Teléfono", maxlen=30, width="half"),
        _f("title", "text", "Job title", "Cargo", req=True, maxlen=60, width="half"),
        _f("sup_family", "text", "Supervisor's surnames (leave blank if you do not know)", "Apellidos del supervisor (deja en blanco si no lo sabes)", maxlen=60, width="half"),
        _f("sup_given", "text", "Supervisor's given names (leave blank if you do not know)", "Nombres del supervisor (deja en blanco si no lo sabes)", maxlen=60, width="half")],
    {"title": ["employer"], "sub": ["title"], "period": True}, date_fields=("from", "to"), add={"en": "Add another employer", "es": "Agregar otro empleador"})
RECORD_TYPES["ds_school"] = _type(
    "ds_generic", "School (secondary level or above)", "Escuela (nivel secundario o superior)",
    [_f("name", "text", "Name of institution", "Nombre de la institución", req=True, maxlen=80)] + loc(None) + [
        _f("course", "text", "Course of study", "Área de estudio", req=True, maxlen=80),
        _f("degree", "text", "Degree or diploma", "Título o diploma", maxlen=80)],
    {"title": ["name"], "sub": ["course"], "period": True}, date_fields=("from", "to"), add={"en": "Add another school", "es": "Agregar otra escuela"})
RECORD_TYPES["ds_other_occ"] = _type(
    "ds_generic", "Other occupation", "Otra ocupación",
    [_f("occupation", "text", "Occupation", "Ocupación", req=True, maxlen=60),
     _f("employer", "text", "Employer or school name (if any)", "Nombre del empleador o escuela (si aplica)", maxlen=80)] + loc(None, req=False),
    {"title": ["occupation"], "sub": ["employer"]}, add={"en": "Add another occupation", "es": "Agregar otra ocupación"})
RECORD_TYPES["ds_country"] = _type("country", "Country / region", "País / región", [_f("country", "text", "Country / region", "País / región", req=True, maxlen=60)], {"title": ["country"]},
                                   add={"en": "Add another country", "es": "Agregar otro país"})
RECORD_TYPES["ds_military"] = _type(
    "ds_generic", "Military service", "Servicio militar",
    [_f("country", "text", "Country / region", "País / región", req=True, maxlen=60, width="half"),
     _f("branch", "text", "Branch of service", "Rama del servicio", req=True, maxlen=60, width="half"),
     _f("rank", "text", "Rank / position", "Rango / posición", req=True, maxlen=60, width="half"),
     _f("specialty", "text", "Military specialty", "Especialidad militar", maxlen=60, width="half")],
    {"title": ["branch"], "sub": ["country", "rank"], "period": True}, date_fields=("from", "to"), add={"en": "Add another service", "es": "Agregar otro servicio"})
RECORD_TYPES["ds_org"] = _type("organization", "Organization", "Organización", [_f("name", "text", "Organization name", "Nombre de la organización", req=True, maxlen=100)], {"title": ["name"]},
                               add={"en": "Add another organization", "es": "Agregar otra organización"})
