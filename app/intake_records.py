"""Reusable record / timeline components for Smart Intakes.

A `record_list` field stores a list of small records (addresses, jobs/schools, trips,
children, offenses...) as JSON. The record type decides which sub-fields exist; the
field's `config_json` decides the timeline rules (how many years must be covered, how
much overlap is tolerated, ...). Nothing here is N-400 specific: I-130, I-485 and other
intakes reuse the same building blocks:

    AddressHistoryBuilder    -> record "address"  + timeline coverage
    EmploymentEducation...   -> record "activity" + timeline coverage
    TravelHistoryBuilder     -> record "trip"     + duration totals
    RepeatableRecords        -> "child", "other_name", "offense", ...
    TimelineCoverageValidator / DateGapOverlapDetection / CompletenessCheck -> `analyze`

All of it is DATA CONSISTENCY guidance ("please review these dates"). It never says a
person is or is not eligible for anything.

The browser component (static/js/og_records.js) only edits records; every date
calculation happens here, in one place, and is served through the small analyze
endpoint, so the review page, the completeness check and Admin see the same results.
"""

import json
from datetime import date, datetime, timedelta

MAX_RECORDS = 40
MAX_TEXT = 300
DAY = timedelta(days=1)

STATES = [
    ("AL", "Alabama"), ("AK", "Alaska"), ("AS", "American Samoa"), ("AZ", "Arizona"), ("AR", "Arkansas"),
    ("AA", "Armed Forces Americas"), ("AE", "Armed Forces Europe, Middle East, Africa, Canada"),
    ("AP", "Armed Forces Pacific"), ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"),
    ("DE", "Delaware"), ("DC", "District of Columbia"), ("FL", "Florida"), ("FM", "Federated States of Micronesia"),
    ("GA", "Georgia"), ("GU", "Guam"), ("HI", "Hawaii"), ("ID", "Idaho"), ("IL", "Illinois"), ("IN", "Indiana"),
    ("IA", "Iowa"), ("KS", "Kansas"), ("KY", "Kentucky"), ("LA", "Louisiana"), ("ME", "Maine"),
    ("MH", "Marshall Islands"), ("MD", "Maryland"), ("MA", "Massachusetts"), ("MI", "Michigan"),
    ("MN", "Minnesota"), ("MS", "Mississippi"), ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"),
    ("NV", "Nevada"), ("NH", "New Hampshire"), ("NJ", "New Jersey"), ("NM", "New Mexico"), ("NY", "New York"),
    ("NC", "North Carolina"), ("ND", "North Dakota"), ("MP", "Northern Mariana Islands"), ("OH", "Ohio"),
    ("OK", "Oklahoma"), ("OR", "Oregon"), ("PW", "Palau"), ("PA", "Pennsylvania"), ("PR", "Puerto Rico"),
    ("RI", "Rhode Island"), ("SC", "South Carolina"), ("SD", "South Dakota"), ("TN", "Tennessee"), ("TX", "Texas"),
    ("UT", "Utah"), ("VT", "Vermont"), ("VI", "U.S. Virgin Islands"), ("VA", "Virginia"), ("WA", "Washington"),
    ("WV", "West Virginia"), ("WI", "Wisconsin"), ("WY", "Wyoming"),
]
_STATE_OPTIONS = [(c, f"{n} ({c})", f"{n} ({c})") for c, n in STATES]
_YES_NO = [("yes", "Yes", "Sí"), ("no", "No", "No")]
_UNITS = [("apt", "Apt.", "Apto."), ("ste", "Ste.", "Ste."), ("flr", "Flr.", "Piso")]


def _f(name, ftype, en, es, *, req=False, options=None, show=None, maxlen=None, width="full", help=None, pattern=None):
    return {
        "name": name, "type": ftype, "label": {"en": en, "es": es}, "required": req, "options": options or [],
        "show_if": show, "maxlength": maxlen, "width": width, "help": help, "pattern": pattern,
    }


_ADDRESS_FIELDS = [
    _f("is_us", "choice", "Is this address in the United States?", "¿Esta dirección está en los Estados Unidos?", req=True, options=_YES_NO),
    _f("street", "text", "Street number and name", "Número y nombre de la calle", req=True, maxlen=120),
    _f("unit_type", "select", "Unit type (if any)", "Tipo de unidad (si aplica)", options=_UNITS, width="half"),
    _f("unit_number", "text", "Unit number", "Número de unidad", maxlen=20, width="half"),
    _f("city", "text", "City or town", "Ciudad o pueblo", req=True, maxlen=80),
    _f("state", "select", "State", "Estado", req=True, options=_STATE_OPTIONS, show={"field": "is_us", "values": ["yes"]}, width="half"),
    _f("zip", "text", "ZIP code", "Código postal (ZIP)", req=True, maxlen=5, pattern=r"\d{5}", show={"field": "is_us", "values": ["yes"]}, width="half"),
    _f("province", "text", "Province", "Provincia", maxlen=60, show={"field": "is_us", "values": ["no"]}, width="half"),
    _f("postal_code", "text", "Postal code", "Código postal", maxlen=20, show={"field": "is_us", "values": ["no"]}, width="half"),
    _f("country", "text", "Country", "País", req=True, maxlen=60, show={"field": "is_us", "values": ["no"]}),
]

_ACTIVITY_TYPES = [
    ("employed", "Employed", "Empleado(a)"),
    ("self_employed", "Self-employed", "Trabajo por cuenta propia"),
    ("student", "Student / school", "Estudiante / escuela"),
    ("unemployed", "Unemployed", "Desempleado(a)"),
    ("retired", "Retired", "Jubilado(a)"),
]
_WORKS = ["employed", "student"]
_HAS_PLACE = ["employed", "self_employed", "student"]

RECORD_TYPES = {
    "address": {
        "title": {"en": "Address", "es": "Dirección"},
        "timeline": True,
        "date_fields": ("from", "to"),
        "fields": _ADDRESS_FIELDS,
        "add": {"en": "Add previous address", "es": "Agregar dirección anterior"},
        "add_first": {"en": "Add your current address", "es": "Agregar tu dirección actual"},
        "empty": {"en": "Where do you live now?", "es": "¿Dónde vives ahora?"},
    },
    "activity": {
        "title": {"en": "Activity", "es": "Actividad"},
        "timeline": True,
        "date_fields": ("from", "to"),
        "fields": [
            _f("type", "choice", "What were you doing?", "¿Qué estabas haciendo?", req=True, options=_ACTIVITY_TYPES),
            _f("name", "text", "Employer or school name", "Nombre del empleador o de la escuela", req=True, maxlen=120, show={"field": "type", "values": _WORKS}),
            _f("occupation", "text", "Occupation or field of study", "Ocupación o campo de estudio", req=True, maxlen=120, show={"field": "type", "values": _HAS_PLACE}),
            _f("city", "text", "City or town", "Ciudad o pueblo", req=True, maxlen=80, show={"field": "type", "values": _HAS_PLACE}, width="half"),
            _f("state", "text", "State / province", "Estado / provincia", maxlen=60, show={"field": "type", "values": _HAS_PLACE}, width="half"),
            _f("zip", "text", "ZIP / postal code", "Código postal", maxlen=20, show={"field": "type", "values": _HAS_PLACE}, width="half"),
            _f("country", "text", "Country", "País", req=True, maxlen=60, show={"field": "type", "values": _HAS_PLACE}, width="half"),
        ],
        "add": {"en": "Add activity", "es": "Agregar actividad"},
        "add_first": {"en": "Add your current or most recent activity", "es": "Agregar tu actividad actual o más reciente"},
        "empty": {"en": "What are you doing now?", "es": "¿Qué haces actualmente?"},
    },
    "employment": {
        "kind": "activity",
        "title": {"en": "Employment", "es": "Empleo"},
        "timeline": True,
        "date_fields": ("from", "to"),
        "fields": [
            _f("type", "choice", "What were you doing?", "¿Qué estabas haciendo?", req=True, options=_ACTIVITY_TYPES),
            _f("name", "text", "Employer or company name", "Nombre del empleador o de la empresa", req=True, maxlen=34, show={"field": "type", "values": ["employed"]}),
            _f("occupation", "text", "Your occupation", "Tu ocupación", req=True, maxlen=80, show={"field": "type", "values": ["employed", "self_employed"]}),
            _f("street", "text", "Street number and name", "Número y nombre de la calle", maxlen=34, show={"field": "type", "values": ["employed", "self_employed"]}),
            _f("unit_number", "text", "Suite / unit (if any)", "Suite / unidad (si aplica)", maxlen=6, show={"field": "type", "values": ["employed", "self_employed"]}, width="half"),
            _f("city", "text", "City or town", "Ciudad o pueblo", req=True, maxlen=20, show={"field": "type", "values": ["employed", "self_employed"]}, width="half"),
            _f("state", "text", "State / province", "Estado / provincia", maxlen=30, show={"field": "type", "values": ["employed", "self_employed"]}, width="half"),
            _f("zip", "text", "ZIP / postal code", "Código postal", maxlen=9, show={"field": "type", "values": ["employed", "self_employed"]}, width="half"),
            _f("country", "text", "Country", "País", req=True, maxlen=60, show={"field": "type", "values": ["employed", "self_employed"]}),
        ],
        "add": {"en": "Add employment", "es": "Agregar empleo"},
        "add_first": {"en": "Add your current employment", "es": "Agregar tu empleo actual"},
        "empty": {"en": "What is your work situation now?", "es": "¿Cuál es tu situación laboral actual?"},
    },
    "spouse": {
        "title": {"en": "Spouse", "es": "Cónyuge"},
        "timeline": False,
        "date_fields": (),
        "fields": [
            _f("current", "choice", "Is this the current spouse?", "¿Es el cónyuge actual?", req=True, options=_YES_NO),
            _f("family", "text", "Family name (last name)", "Apellido", req=True, maxlen=60, width="half"),
            _f("given", "text", "Given name (first name)", "Nombre", req=True, maxlen=60, width="half"),
            _f("middle", "text", "Middle name (if applicable)", "Segundo nombre (si aplica)", maxlen=60, width="half"),
            _f("date_ended", "date", "Date the marriage ended", "Fecha en que terminó el matrimonio", show={"field": "current", "values": ["no"]}, width="half"),
        ],
        "add": {"en": "Add another spouse", "es": "Agregar otro cónyuge"},
        "add_first": {"en": "Add a spouse", "es": "Agregar un cónyuge"},
        "empty": {"en": "No spouses added yet.", "es": "Aún no has agregado cónyuges."},
    },
    "parent": {
        "title": {"en": "Parent", "es": "Padre o madre"},
        "timeline": False,
        "date_fields": (),
        "fields": [
            _f("family", "text", "Family name (last name)", "Apellido", req=True, maxlen=60, width="half"),
            _f("given", "text", "Given name (first name)", "Nombre", req=True, maxlen=60, width="half"),
            _f("middle", "text", "Middle name (if applicable)", "Segundo nombre (si aplica)", maxlen=60, width="half"),
            _f("dob", "date", "Date of birth", "Fecha de nacimiento", width="half"),
            _f("sex", "choice", "Sex", "Sexo", options=[("male", "Male", "Masculino"), ("female", "Female", "Femenino")]),
            _f("country_birth", "text", "Country of birth", "País de nacimiento", maxlen=60, width="half"),
            _f("city_residence", "text", "City, town or village of residence", "Ciudad, pueblo o aldea de residencia", maxlen=60, width="half"),
            _f("country_residence", "text", "Country of residence", "País de residencia", maxlen=60),
        ],
        "add": {"en": "Add the other parent", "es": "Agregar al otro padre o madre"},
        "add_first": {"en": "Add a parent", "es": "Agregar un padre o madre"},
        "empty": {"en": "No parents added yet.", "es": "Aún no has agregado a tus padres."},
    },
    "relative": {
        "title": {"en": "Family member", "es": "Familiar"},
        "timeline": False,
        "date_fields": (),
        "fields": [
            _f("family", "text", "Family name (last name)", "Apellido", req=True, maxlen=60, width="half"),
            _f("given", "text", "Given name (first name)", "Nombre", req=True, maxlen=60, width="half"),
            _f("middle", "text", "Middle name (if applicable)", "Segundo nombre (si aplica)", maxlen=60, width="half"),
            _f("relationship", "text", "Relationship to the beneficiary", "Relación con el beneficiario", req=True, maxlen=29, width="half",
               help={"en": "For example: spouse, son, daughter.", "es": "Por ejemplo: cónyuge, hijo, hija."}),
            _f("dob", "date", "Date of birth", "Fecha de nacimiento", req=True, width="half"),
            _f("country_birth", "text", "Country of birth", "País de nacimiento", req=True, maxlen=60, width="half"),
        ],
        "add": {"en": "Add another family member", "es": "Agregar otro familiar"},
        "add_first": {"en": "Add a family member", "es": "Agregar un familiar"},
        "empty": {"en": "No family members added yet.", "es": "Aún no has agregado familiares."},
    },
    "prior_petition": {
        "title": {"en": "Previous petition", "es": "Petición anterior"},
        "timeline": False,
        "date_fields": (),
        "fields": [
            _f("family", "text", "Family name (last name) of the person the petition was for", "Apellido de la persona para quien fue la petición", req=True, maxlen=60, width="half"),
            _f("given", "text", "Given name (first name)", "Nombre", req=True, maxlen=60, width="half"),
            _f("middle", "text", "Middle name (if applicable)", "Segundo nombre (si aplica)", maxlen=60, width="half"),
            _f("city", "text", "City or town where it was filed", "Ciudad o pueblo donde se presentó", req=True, maxlen=20, width="half"),
            _f("state", "select", "State", "Estado", options=_STATE_OPTIONS, width="half"),
            _f("date_filed", "date", "Date filed", "Fecha de presentación", req=True, width="half"),
            _f("result", "text", "Result", "Resultado", req=True, maxlen=33, width="half",
               help={"en": "For example: approved, denied, withdrawn.", "es": "Por ejemplo: aprobada, denegada, retirada."}),
        ],
        "add": {"en": "Add another previous petition", "es": "Agregar otra petición anterior"},
        "add_first": {"en": "Add a previous petition", "es": "Agregar una petición anterior"},
        "empty": {"en": "No previous petitions added yet.", "es": "Aún no has agregado peticiones anteriores."},
    },
    "other_relative": {
        "title": {"en": "Other relative", "es": "Otro familiar"},
        "timeline": False,
        "date_fields": (),
        "fields": [
            _f("family", "text", "Family name (last name)", "Apellido", req=True, maxlen=60, width="half"),
            _f("given", "text", "Given name (first name)", "Nombre", req=True, maxlen=60, width="half"),
            _f("middle", "text", "Middle name (if applicable)", "Segundo nombre (si aplica)", maxlen=60, width="half"),
            _f("relationship", "text", "Your relationship to this relative", "Tu relación con este familiar", req=True, maxlen=29, width="half"),
        ],
        "add": {"en": "Add another relative", "es": "Agregar otro familiar"},
        "add_first": {"en": "Add a relative", "es": "Agregar un familiar"},
        "empty": {"en": "No relatives added yet.", "es": "Aún no has agregado familiares."},
    },
    "trip": {
        "title": {"en": "Trip", "es": "Viaje"},
        "timeline": False,
        "date_fields": ("from", "to"),
        "fields": [
            _f("countries", "text", "Country or countries you traveled to", "País o países a los que viajaste", req=True, maxlen=55),
        ],
        "add": {"en": "Add another trip", "es": "Agregar otro viaje"},
        "add_first": {"en": "Add a trip", "es": "Agregar un viaje"},
        "empty": {"en": "No trips added yet.", "es": "Aún no has agregado viajes."},
    },
    "child": {
        "title": {"en": "Child", "es": "Hijo(a)"},
        "timeline": False,
        "date_fields": (),
        "fields": [
            _f("given", "text", "First name", "Nombre", req=True, maxlen=60, width="half"),
            _f("family", "text", "Family name (last name)", "Apellido", req=True, maxlen=60, width="half"),
            _f("dob", "date", "Date of birth", "Fecha de nacimiento", req=True),
            _f("residence", "select", "Where does this child live?", "¿Dónde vive este hijo(a)?", req=True, options=[
                ("resides_with_me", "Resides with me", "Reside conmigo"),
                ("does_not_reside_with_me", "Does not reside with me", "No reside conmigo"),
                ("unknown_missing", "Unknown / missing", "Desconocido / desaparecido")]),
            _f("residence_address", "text", "Where does this child live? (address)", "¿Dónde vive este hijo(a)? (dirección)", maxlen=200, show={"field": "residence", "values": ["does_not_reside_with_me"]}),
            _f("relationship", "select", "Relationship to you", "Relación contigo", req=True, options=[
                ("biological", "Biological son or daughter", "Hijo(a) biológico(a)"),
                ("stepchild", "Stepchild", "Hijastro(a)"),
                ("adopted", "Legally adopted son or daughter", "Hijo(a) legalmente adoptado(a)")]),
            _f("support", "choice", "Are you providing support for this child?", "¿Le brindas manutención a este hijo(a)?", req=True, options=_YES_NO),
        ],
        "add": {"en": "Add another child", "es": "Agregar otro hijo(a)"},
        "add_first": {"en": "Add a child", "es": "Agregar un hijo(a)"},
        "empty": {"en": "No children added yet.", "es": "Aún no has agregado hijos."},
    },
    "other_name": {
        "title": {"en": "Other name", "es": "Otro nombre"},
        "timeline": False,
        "date_fields": (),
        "fields": [
            _f("family", "text", "Family name (last name)", "Apellido", req=True, maxlen=60),
            _f("given", "text", "Given name (first name)", "Nombre", req=True, maxlen=60),
            _f("middle", "text", "Middle name (if applicable)", "Segundo nombre (si aplica)", maxlen=60),
        ],
        "add": {"en": "Add another name", "es": "Agregar otro nombre"},
        "add_first": {"en": "Add a name", "es": "Agregar un nombre"},
        "empty": {"en": "No other names added.", "es": "No has agregado otros nombres."},
    },
    "offense": {
        "title": {"en": "Arrest, charge or offense", "es": "Arresto, cargo o delito"},
        "timeline": False,
        "date_fields": (),
        "fields": [
            _f("place", "text", "Where did it happen? (city or town, state, country)", "¿Dónde ocurrió? (ciudad o pueblo, estado, país)", req=True, maxlen=150),
            _f("offense", "text", "What was the crime or offense?", "¿Cuál fue el delito o la infracción?", req=True, maxlen=200,
               help={"en": "If convicted, the crime of conviction. If not convicted, the crime or offense listed in the arrest, citation, charging document, or the crime committed.",
                     "es": "Si fue condenado(a), el delito de la condena. Si no, el delito o infracción indicado en el arresto, la citación, el documento de cargos, o el delito cometido."}),
            _f("date", "date", "Date of the crime or offense", "Fecha del delito o infracción", req=True, width="half"),
            _f("conviction_date", "date", "Date of conviction or guilty plea (if applicable)", "Fecha de la condena o de declararte culpable (si aplica)", width="half"),
            _f("sentence", "text", "Sentence (if applicable)", "Sentencia (si aplica)", maxlen=150,
               help={"en": "For example: 90 days in jail, 90 days on probation.", "es": "Por ejemplo: 90 días en la cárcel, 90 días de libertad condicional."}),
            _f("result", "text", "Result or disposition", "Resultado o disposición", req=True, maxlen=200,
               help={"en": "For example: no charges filed, convicted, charges dismissed, detention, jail, probation.",
                     "es": "Por ejemplo: sin cargos, condenado(a), cargos desestimados, detención, cárcel, libertad condicional."}),
        ],
        "add": {"en": "Add another", "es": "Agregar otro"},
        "add_first": {"en": "Add one", "es": "Agregar uno"},
        "empty": {"en": "Nothing added yet.", "es": "Aún no has agregado nada."},
    },
}

_SEX = [("male", "Male", "Masculino"), ("female", "Female", "Femenino")]

# I-130A: the beneficiary's parents (the I-130 itself only asks about the petitioner's parents).
RECORD_TYPES["ben_parent"] = {
    "kind": "parent",
    "title": {"en": "Parent", "es": "Padre o madre"},
    "timeline": False,
    "date_fields": (),
    "fields": [
        _f("family", "text", "Family name (last name)", "Apellido", req=True, maxlen=60, width="half",
           help={"en": "The form asks for Parent 1's maiden name (birth family name). Add that parent first.",
                 "es": "El formulario pide el apellido de soltero(a) (apellido de nacimiento) del Padre/Madre 1. Agrega primero a ese padre o madre."}),
        _f("given", "text", "Given name (first name)", "Nombre", req=True, maxlen=60, width="half"),
        _f("middle", "text", "Middle name (if applicable)", "Segundo nombre (si aplica)", maxlen=60, width="half"),
        _f("dob", "date", "Date of birth", "Fecha de nacimiento", width="half"),
        _f("sex", "choice", "Sex", "Sexo", options=_SEX),
        _f("city_birth", "text", "City, town or village of birth", "Ciudad, pueblo o aldea de nacimiento", maxlen=38, width="half"),
        _f("country_birth", "text", "Country of birth", "País de nacimiento", maxlen=60, width="half"),
        _f("city_residence", "text", "City, town or village of residence", "Ciudad, pueblo o aldea de residencia", maxlen=60, width="half"),
        _f("country_residence", "text", "Country of residence", "País de residencia", maxlen=60, width="half"),
    ],
    "add": {"en": "Add the other parent", "es": "Agregar al otro padre o madre"},
    "add_first": {"en": "Add a parent", "es": "Agregar un padre o madre"},
    "empty": {"en": "No parents added yet.", "es": "Aún no has agregado a los padres."},
}

# A single address outside the U.S. with the dates lived there (I-130A Part 1, Items 8-9).
RECORD_TYPES["foreign_address"] = {
    "kind": "address",
    "title": {"en": "Address outside the U.S.", "es": "Dirección fuera de EE. UU."},
    "timeline": False,
    "date_fields": ("from", "to"),
    "fields": [
        _f("street", "text", "Street number and name", "Número y nombre de la calle", req=True, maxlen=120),
        _f("unit_type", "select", "Unit type (if any)", "Tipo de unidad (si aplica)", options=_UNITS, width="half"),
        _f("unit_number", "text", "Unit number", "Número de unidad", maxlen=20, width="half"),
        _f("city", "text", "City or town", "Ciudad o pueblo", req=True, maxlen=80),
        _f("province", "text", "Province", "Provincia", maxlen=60, width="half"),
        _f("postal_code", "text", "Postal code", "Código postal", maxlen=20, width="half"),
        _f("country", "text", "Country", "País", req=True, maxlen=60),
    ],
    "add": {"en": "Add the address", "es": "Agregar la dirección"},
    "add_first": {"en": "Add the address", "es": "Agregar la dirección"},
    "empty": {"en": "No address added yet.", "es": "Aún no has agregado la dirección."},
}

# A single job outside the U.S. (I-130A Part 3): same fields as the employment timeline, no coverage rules.
RECORD_TYPES["foreign_employment"] = dict(
    RECORD_TYPES["employment"],
    timeline=False,
    title={"en": "Employment outside the U.S.", "es": "Empleo fuera de EE. UU."},
    add={"en": "Add the job", "es": "Agregar el empleo"},
    add_first={"en": "Add the job", "es": "Agregar el empleo"},
    empty={"en": "No job added yet.", "es": "Aún no has agregado el empleo."},
)

# ---------------------------------------------------------------- Form I-485 record types
_SEL_HOW_ENDED = [("deceased", "Spouse deceased", "Cónyuge fallecido(a)"), ("annulled", "Annulled", "Anulado"),
                  ("divorced", "Divorced", "Divorciado(a)"), ("other", "Other (explain)", "Otro (explicar)")]
_ACT_TYPES_485 = [("employed", "Employed", "Empleado(a)"), ("self_employed", "Self-employed", "Trabajo por cuenta propia"),
                  ("student", "Student / school", "Estudiante / escuela"), ("unemployed", "Unemployed", "Desempleado(a)"), ("retired", "Retired", "Jubilado(a)")]
_PLACE = ["employed", "self_employed", "student"]

_ACTIVITY_485_FIELDS = [
    _f("type", "choice", "What were you doing?", "¿Qué hacías?", req=True, options=_ACT_TYPES_485),
    _f("name", "text", "Name of employer, company or school", "Nombre del empleador, empresa o escuela", req=True, maxlen=80, show={"field": "type", "values": ["employed", "student"]}),
    _f("occupation", "text", "Your occupation", "Tu ocupación", req=True, maxlen=80, show={"field": "type", "values": ["employed", "self_employed"]},
       help={"en": "For a student, the field of study is fine. If unemployed or retired, just choose that option above.", "es": "Para un estudiante basta el campo de estudio. Si estabas desempleado(a) o jubilado(a), solo elige esa opción arriba."}),
    _f("street", "text", "Street number and name", "Número y nombre de la calle", maxlen=34, show={"field": "type", "values": _PLACE}),
    _f("unit_number", "text", "Suite / unit (if any)", "Suite / unidad (si aplica)", maxlen=6, show={"field": "type", "values": _PLACE}, width="half"),
    _f("city", "text", "City or town", "Ciudad o pueblo", req=True, maxlen=28, show={"field": "type", "values": _PLACE}, width="half"),
    _f("state", "text", "State or province", "Estado o provincia", maxlen=30, show={"field": "type", "values": _PLACE}, width="half"),
    _f("zip", "text", "ZIP or postal code", "Código postal", maxlen=9, show={"field": "type", "values": _PLACE}, width="half"),
    _f("country", "text", "Country", "País", req=True, maxlen=60, show={"field": "type", "values": _PLACE}),
    _f("support", "text", "Source of financial support", "Fuente de sustento económico", req=True, maxlen=120, show={"field": "type", "values": ["unemployed", "retired"]},
       help={"en": "The form asks for the source of financial support for each period of unemployment or retirement.", "es": "El formulario pide la fuente de sustento económico en cada período de desempleo o jubilación."}),
]

RECORD_TYPES["i485_activity"] = {
    "kind": "activity",
    "title": {"en": "Employment or school", "es": "Empleo o escuela"},
    "timeline": True,
    "date_fields": ("from", "to"),
    "fields": _ACTIVITY_485_FIELDS,
    "add": {"en": "Add another period", "es": "Agregar otro período"},
    "add_first": {"en": "Add current employment or school", "es": "Agregar el empleo o la escuela actual"},
    "empty": {"en": "What are you doing now?", "es": "¿Qué haces actualmente?"},
}
RECORD_TYPES["i485_foreign_activity"] = dict(
    RECORD_TYPES["i485_activity"], timeline=False,
    title={"en": "Employer or school outside the U.S.", "es": "Empleador o escuela fuera de EE. UU."},
    add={"en": "Add it", "es": "Agregarlo"}, add_first={"en": "Add it", "es": "Agregarlo"},
    empty={"en": "Nothing added yet.", "es": "Aún no has agregado nada."},
)
RECORD_TYPES["i485_parent"] = {
    "kind": "parent",
    "title": {"en": "Parent", "es": "Padre o madre"},
    "timeline": False, "date_fields": (),
    "fields": [
        _f("family", "text", "Legal family name (last name)", "Apellido legal", req=True, maxlen=60, width="half"),
        _f("given", "text", "Legal given name (first name)", "Nombre legal", req=True, maxlen=60, width="half"),
        _f("middle", "text", "Middle name (if applicable)", "Segundo nombre (si aplica)", maxlen=60),
        _f("birth_family", "text", "Family name at birth (only if different)", "Apellido al nacer (solo si es diferente)", maxlen=60, width="half"),
        _f("birth_given", "text", "Given name at birth (only if different)", "Nombre al nacer (solo si es diferente)", maxlen=60, width="half"),
        _f("birth_middle", "text", "Middle name at birth (only if different)", "Segundo nombre al nacer (solo si es diferente)", maxlen=60),
        _f("dob", "date", "Date of birth", "Fecha de nacimiento", width="half"),
        _f("country_birth", "text", "Country of birth", "País de nacimiento", maxlen=60, width="half"),
    ],
    "add": {"en": "Add the other parent", "es": "Agregar al otro padre o madre"},
    "add_first": {"en": "Add a parent", "es": "Agregar un padre o madre"},
    "empty": {"en": "No parents added yet.", "es": "Aún no has agregado a tus padres."},
}
RECORD_TYPES["i485_prior_marriage"] = {
    "kind": "prior_marriage",
    "title": {"en": "Prior marriage", "es": "Matrimonio anterior"},
    "timeline": False, "date_fields": (),
    "fields": [
        _f("family", "text", "Prior spouse's family name (before marriage)", "Apellido del cónyuge anterior (antes del matrimonio)", req=True, maxlen=60, width="half"),
        _f("given", "text", "Prior spouse's given name", "Nombre del cónyuge anterior", req=True, maxlen=60, width="half"),
        _f("middle", "text", "Middle name (if applicable)", "Segundo nombre (si aplica)", maxlen=60),
        _f("dob", "date", "Prior spouse's date of birth", "Fecha de nacimiento del cónyuge anterior", width="half"),
        _f("birth_country", "text", "Country of birth", "País de nacimiento", maxlen=60, width="half"),
        _f("citizenship", "text", "Country of citizenship or nationality", "País de ciudadanía o nacionalidad", maxlen=60),
        _f("date_married", "date", "Date of marriage", "Fecha del matrimonio", req=True, width="half"),
        _f("married_city", "text", "City or town where you married", "Ciudad o pueblo donde se casaron", maxlen=60, width="half"),
        _f("married_state", "text", "State or province", "Estado o provincia", maxlen=60, width="half"),
        _f("married_country", "text", "Country", "País", maxlen=60, width="half"),
        _f("ended_city", "text", "City or town where the marriage legally ended", "Ciudad o pueblo donde terminó legalmente el matrimonio", maxlen=60, width="half"),
        _f("ended_state", "text", "State or province", "Estado o provincia", maxlen=60, width="half"),
        _f("ended_country", "text", "Country", "País", maxlen=60, width="half"),
        _f("date_ended", "date", "Date the marriage legally ended", "Fecha en que terminó legalmente el matrimonio", req=True, width="half"),
        _f("how_ended", "choice", "How did the marriage end?", "¿Cómo terminó el matrimonio?", req=True, options=_SEL_HOW_ENDED),
        _f("how_other", "text", "Explain", "Explica", req=True, maxlen=200, show={"field": "how_ended", "values": ["other"]}),
    ],
    "add": {"en": "Add another prior marriage", "es": "Agregar otro matrimonio anterior"},
    "add_first": {"en": "Add a prior marriage", "es": "Agregar un matrimonio anterior"},
    "empty": {"en": "No prior marriages added yet.", "es": "Aún no has agregado matrimonios anteriores."},
}
RECORD_TYPES["i485_child"] = {
    "kind": "i485_child",
    "title": {"en": "Child", "es": "Hijo(a)"},
    "timeline": False, "date_fields": (),
    "fields": [
        _f("family", "text", "Current legal family name (last name)", "Apellido legal actual", req=True, maxlen=60, width="half"),
        _f("given", "text", "Given name (first name)", "Nombre", req=True, maxlen=60, width="half"),
        _f("middle", "text", "Middle name (if applicable)", "Segundo nombre (si aplica)", maxlen=60),
        _f("a_number", "text", "A-Number (if any)", "Número A (si tiene)", maxlen=12, width="half", pattern=r"A?-?\d{7,9}"),
        _f("dob", "date", "Date of birth", "Fecha de nacimiento", req=True, width="half"),
        _f("country_birth", "text", "Country of birth", "País de nacimiento", req=True, maxlen=60),
        _f("relationship", "text", "Relationship to you", "Relación contigo", req=True, maxlen=60,
           help={"en": "For example: biological child, stepchild, legally adopted child.", "es": "Por ejemplo: hijo(a) biológico(a), hijastro(a), hijo(a) legalmente adoptado(a)."}),
        _f("applying", "choice", "Is this child also applying now on a separate Form I-485?", "¿Este hijo(a) también solicita ahora en un Formulario I-485 aparte?", req=True, options=_YES_NO),
    ],
    "add": {"en": "Add another child", "es": "Agregar otro hijo(a)"},
    "add_first": {"en": "Add a child", "es": "Agregar un hijo(a)"},
    "empty": {"en": "No children added yet.", "es": "Aún no has agregado hijos."},
}
RECORD_TYPES["i485_org"] = {
    "kind": "organization",
    "title": {"en": "Organization", "es": "Organización"},
    "timeline": False, "date_fields": ("from", "to"),
    "fields": [
        _f("name", "text", "Name of organization", "Nombre de la organización", req=True, maxlen=120),
        _f("city", "text", "City or town", "Ciudad o pueblo", req=True, maxlen=60, width="half"),
        _f("state", "text", "State or province", "Estado o provincia", maxlen=60, width="half"),
        _f("country", "text", "Country", "País", req=True, maxlen=60),
        _f("nature", "text", "Nature of the organization, including its purposes and activities, whether illicit or legitimate", "Naturaleza de la organización, incluidos sus propósitos y actividades, sean ilícitos o legítimos", req=True, maxlen=300),
        _f("involvement", "text", "Your involvement, including role or positions held, whether illicit or legitimate", "Tu participación, incluido tu cargo o puestos, sea ilícita o legítima", req=True, maxlen=300),
    ],
    "add": {"en": "Add another organization", "es": "Agregar otra organización"},
    "add_first": {"en": "Add an organization", "es": "Agregar una organización"},
    "empty": {"en": "No organizations added yet.", "es": "Aún no has agregado organizaciones."},
}
RECORD_TYPES["i485_benefit"] = {
    "kind": "benefit",
    "title": {"en": "Public benefit", "es": "Beneficio público"},
    "timeline": False, "date_fields": (),
    "fields": [
        _f("benefit", "text", "Means-tested public benefit received", "Beneficio público sujeto a verificación de recursos recibido", req=True, maxlen=120),
        _f("start", "date", "Start date", "Fecha de inicio", req=True, width="half"),
        _f("end", "date", "End date", "Fecha de fin", width="half"),
        _f("amount", "text", "Dollar amount (if applicable)", "Monto en dólares (si aplica)", maxlen=30),
        _f("reason", "text", "Reason you received the benefit", "Motivo por el que recibiste el beneficio", req=True, maxlen=200),
    ],
    "add": {"en": "Add another benefit", "es": "Agregar otro beneficio"},
    "add_first": {"en": "Add a benefit", "es": "Agregar un beneficio"},
    "empty": {"en": "No benefits added yet.", "es": "Aún no has agregado beneficios."},
}

RECORD_TYPES["i485_other_dob"] = {
    "kind": "other_dob",
    "title": {"en": "Other date of birth", "es": "Otra fecha de nacimiento"},
    "timeline": False, "date_fields": (),
    "fields": [_f("dob", "date", "Other date of birth", "Otra fecha de nacimiento", req=True)],
    "add": {"en": "Add another date", "es": "Agregar otra fecha"},
    "add_first": {"en": "Add a date of birth", "es": "Agregar una fecha de nacimiento"},
    "empty": {"en": "No other dates added yet.", "es": "Aún no has agregado otras fechas."},
}

def last_foreign_activity(records, today=None):
    """The most recent employer/school outside the U.S. (I-485 Part 4 Item 8) found in an employment/education history."""
    today = today or date.today()
    best = None
    for rec in records:
        if rec.get("type") not in ("employed", "self_employed", "student") or not rec.get("country") or is_us_country(rec.get("country")):
            continue
        a, b = _span(rec, today)
        key = (b or date.min, a or date.min)
        if best is None or key > best[0]:
            best = (key, rec)
    return best[1] if best else None


# ---------------------------------------------------------------- Form I-864 record types
def parse_money(value):
    """Decimal dollars from what a customer typed ('$1,250.50'), or None. Never guesses: 'N/A' / 'zero' are not numbers here."""
    text = str(value if value is not None else "").replace("$", "").replace(",", "").replace(" ", "").strip()
    if not text:
        return None
    try:
        amount = float(text)
    except ValueError:
        return None
    return amount if amount >= 0 else None


def _money(name, en, es, *, req=False, show=None, help=None):
    d = _f(name, "text", en, es, req=req, maxlen=20, width="half", show=show, help=help)
    d["money"] = True
    return d


def _person_select():
    """Optional link to a real Person the customer already has (never matched by name). Options are filled per request."""
    d = _f("person_id", "select", "Is this someone you already have in your cases?", "¿Es alguien que ya tienes en tus casos?", options=[])
    d["dynamic_options"] = "persons"
    return d


_NEW_PERSON = {"field": "person_id", "values": ["", None]}  # the name fields are typed only for someone new

_PERSON_NAME_FIELDS = [
    _person_select(),
    _f("family", "text", "Family name (last name)", "Apellido", req=True, maxlen=30, width="half", show=_NEW_PERSON),
    _f("given", "text", "Given name (first name)", "Nombre(s)", req=True, maxlen=18, width="half", show=_NEW_PERSON),
    _f("middle", "text", "Middle name (if applicable)", "Segundo nombre (si aplica)", maxlen=18, show=_NEW_PERSON),
]

RECORD_TYPES["i864_family"] = {
    "kind": "i864_person", "title": {"en": "Family member you are sponsoring", "es": "Familiar que estás patrocinando"},
    "timeline": False, "date_fields": (),
    "fields": _PERSON_NAME_FIELDS + [
        _f("relationship", "text", "Relationship to the principal immigrant", "Relación con el inmigrante principal", req=True, maxlen=30),
        _f("dob", "date", "Date of birth", "Fecha de nacimiento", req=True, width="half"),
        _f("a_number", "text", "A-Number (if any)", "Número A (si tiene)", maxlen=12, width="half", pattern=r"A?-?\d{7,9}"),
        _f("uscis", "text", "USCIS Online Account Number (if any)", "Número de cuenta en línea de USCIS (si tiene)", maxlen=12, pattern=r"\d{1,12}"),
    ],
    "add": {"en": "Add another family member", "es": "Agregar otro familiar"}, "add_first": {"en": "Add a family member", "es": "Agregar un familiar"},
    "empty": {"en": "No family members added yet.", "es": "Aún no has agregado familiares."},
}
_HH_CATS = [("spouse", "My spouse", "Mi cónyuge"), ("dependent_child", "A dependent child", "Un hijo(a) dependiente"), ("other_dependent", "Another dependent", "Otro dependiente"),
            ("previous_sponsored", "Someone I sponsored before who is now a lawful permanent resident and I am still obligated to support", "Alguien a quien patrociné antes, que ahora es residente permanente legal y sigo obligado(a) a mantener"),
            ("i864a_member", "A sibling, parent or adult child with the same principal residence who is combining income with mine (Form I-864A)", "Un hermano(a), padre/madre o hijo(a) adulto(a) con la misma residencia principal que combina sus ingresos con los míos (Formulario I-864A)")]
RECORD_TYPES["i864_household"] = {
    "kind": "i864_person", "title": {"en": "Household member", "es": "Miembro del hogar"},
    "timeline": False, "date_fields": (),
    "fields": _PERSON_NAME_FIELDS + [
        _f("category", "choice", "Who is this to you?", "¿Quién es para ti?", req=True, options=_HH_CATS),
        _f("dob", "date", "Date of birth", "Fecha de nacimiento", width="half"),
    ],
    "add": {"en": "Add another person", "es": "Agregar otra persona"}, "add_first": {"en": "Add a household member", "es": "Agregar un miembro del hogar"},
    "empty": {"en": "No other household members added yet.", "es": "Aún no has agregado otros miembros del hogar."},
}
RECORD_TYPES["i864_income_person"] = {
    "kind": "i864_income", "title": {"en": "Household member's income", "es": "Ingreso de un miembro del hogar"},
    "timeline": False, "date_fields": (),
    "fields": _PERSON_NAME_FIELDS + [
        _f("relationship", "text", "Relationship to you", "Relación contigo", req=True, maxlen=38),
        _money("income", "Current annual income being used", "Ingreso anual actual que se usa", req=True),
    ],
    "add": {"en": "Add another person's income", "es": "Agregar el ingreso de otra persona"}, "add_first": {"en": "Add a person whose income you are using", "es": "Agregar a una persona cuyo ingreso usas"},
    "empty": {"en": "No one else's income is being used.", "es": "No se está usando el ingreso de otra persona."},
}
RECORD_TYPES["i864_income_source"] = {
    "kind": "i864_source", "title": {"en": "Your income", "es": "Tu ingreso"},
    "timeline": False, "date_fields": (),
    "fields": [
        _f("type", "choice", "What is this income from?", "¿De qué es este ingreso?", req=True, options=[
            ("employed", "A job (employer)", "Un empleo (empleador)"), ("self_employed", "Working for myself", "Trabajo por cuenta propia"),
            ("other", "Other income (for example a pension)", "Otro ingreso (por ejemplo una pensión)")]),
        _f("name", "text", "Name of employer", "Nombre del empleador", req=True, maxlen=34, show={"field": "type", "values": ["employed"]}),
        _f("occupation", "text", "Occupation", "Ocupación", req=True, maxlen=60, show={"field": "type", "values": ["employed", "self_employed"]}),
        _f("description", "text", "Describe this income", "Describe este ingreso", req=True, maxlen=80, show={"field": "type", "values": ["other"]}),
        _money("income", "Annual income from this source", "Ingreso anual de esta fuente", req=True),
    ],
    "add": {"en": "Add another income source", "es": "Agregar otra fuente de ingreso"}, "add_first": {"en": "Add an income source", "es": "Agregar una fuente de ingreso"},
    "empty": {"en": "No income sources added yet.", "es": "Aún no has agregado fuentes de ingreso."},
}
RECORD_TYPES["i864_tax_year"] = {
    "kind": "tax_year", "title": {"en": "Federal tax return year", "es": "Año de la declaración federal de impuestos"},
    "timeline": False, "date_fields": (),
    "fields": [
        _f("year", "text", "Tax year", "Año fiscal", req=True, maxlen=4, width="half", pattern=r"(19|20)\d\d"),
        _f("income_kind", "choice", "Total income for that year", "Ingreso total de ese año", req=True, options=[
            ("amount", "An amount", "Una cantidad"), ("zero", "The amount was zero", "La cantidad fue cero"),
            ("na", "N/A (not applicable) — for example, I was not required to file, or I am not submitting this additional return", "N/A (no aplica) — por ejemplo, no estaba obligado(a) a presentar declaración, o no estoy presentando esta declaración adicional")]),
        _money("income", "Total income (adjusted gross income on IRS Form 1040EZ), as reported on the return", "Ingreso total (ingreso bruto ajustado en el Formulario 1040EZ del IRS), según la declaración", req=True, show={"field": "income_kind", "values": ["amount"]}),
    ],
    "add": {"en": "Add another tax year", "es": "Agregar otro año fiscal"}, "add_first": {"en": "Add your most recent tax year", "es": "Agregar tu año fiscal más reciente"},
    "empty": {"en": "No tax years added yet.", "es": "Aún no has agregado años fiscales."},
}
RECORD_TYPES["i864_asset"] = {
    "kind": "asset", "title": {"en": "Asset", "es": "Activo"},
    "timeline": False, "date_fields": (),
    "fields": [
        _f("owner", "choice", "Whose asset is it?", "¿De quién es el activo?", req=True, options=[
            ("sponsor", "Mine (the sponsor)", "Mío (el patrocinador)"), ("principal", "The principal immigrant's", "Del inmigrante principal"),
            ("household", "A household member combining income with mine (Form I-864A)", "De un miembro del hogar que combina ingresos con los míos (Formulario I-864A)")]),
        _f("kind", "choice", "What kind of asset?", "¿Qué tipo de activo es?", req=True, options=[
            ("cash", "Cash, savings or checking accounts (balance)", "Efectivo, cuentas de ahorros o de cheques (saldo)"),
            ("real_estate", "Real estate (net value: value minus mortgage debt)", "Bienes raíces (valor neto: valor menos deuda hipotecaria)"),
            ("investments", "Stocks, bonds, certificates of deposit or other assets (net cash value)", "Acciones, bonos, certificados de depósito u otros activos (valor neto en efectivo)")]),
        _f("holder", "text", "Name of the household member", "Nombre del miembro del hogar", req=True, maxlen=60, show={"field": "owner", "values": ["household"]}),
        _f("description", "text", "Short description (optional)", "Descripción breve (opcional)", maxlen=80),
        _money("value", "Value", "Valor", req=True),
    ],
    "add": {"en": "Add another asset", "es": "Agregar otro activo"}, "add_first": {"en": "Add an asset", "es": "Agregar un activo"},
    "empty": {"en": "No assets added yet.", "es": "Aún no has agregado activos."},
}

# ---------------------------------------------------------------- Form I-765 record types
RECORD_TYPES["i765_country"] = {
    "kind": "country", "title": {"en": "Country", "es": "País"},
    "timeline": False, "date_fields": (),
    "fields": [_f("country", "text", "Country of citizenship or nationality", "País de ciudadanía o nacionalidad", req=True, maxlen=60)],
    "add": {"en": "Add another country", "es": "Agregar otro país"}, "add_first": {"en": "Add a country", "es": "Agregar un país"},
    "empty": {"en": "No other countries added.", "es": "No has agregado otros países."},
}


# ---------------------------------------------------------------- Form I-751 record types
_CH_ELSEWHERE = {"field": "where", "values": ["us", "abroad"]}
_CH_US = {"field": "where", "values": ["us"]}
_CH_ABROAD = {"field": "where", "values": ["abroad"]}
RECORD_TYPES["i751_child"] = {
    "kind": "i751_child", "title": {"en": "Child", "es": "Hijo(a)"},
    "timeline": False, "date_fields": (),
    "fields": _PERSON_NAME_FIELDS + [
        _f("dob", "date", "Date of birth", "Fecha de nacimiento", req=True, width="half"),
        _f("a_number", "text", "A-Number (if any)", "Número A (si tiene)", maxlen=12, width="half", pattern=r"A?-?\d{7,9}"),
        _f("where", "choice", "Is this child living with you?", "¿Este hijo(a) vive contigo?", req=True, options=[
            ("with_me", "Yes — lives with me (at my physical address)", "Sí — vive conmigo (en mi dirección física)"),
            ("us", "No — lives at another address in the United States", "No — vive en otra dirección en los Estados Unidos"),
            ("abroad", "No — lives outside the United States", "No — vive fuera de los Estados Unidos")]),
        _f("street", "text", "Street number and name", "Número y nombre de la calle", req=True, maxlen=120, show=_CH_ELSEWHERE),
        _f("unit_type", "select", "Unit type (if any)", "Tipo de unidad (si aplica)", options=_UNITS, width="half", show=_CH_ELSEWHERE),
        _f("unit_number", "text", "Unit number", "Número de unidad", maxlen=20, width="half", show=_CH_ELSEWHERE),
        _f("city", "text", "City or town", "Ciudad o pueblo", req=True, maxlen=80, show=_CH_ELSEWHERE),
        _f("state", "select", "State", "Estado", req=True, options=_STATE_OPTIONS, show=_CH_US, width="half"),
        _f("zip", "text", "ZIP code", "Código postal (ZIP)", req=True, maxlen=5, pattern=r"\d{5}", show=_CH_US, width="half"),
        _f("province", "text", "Province", "Provincia", maxlen=60, show=_CH_ABROAD, width="half"),
        _f("postal_code", "text", "Postal code", "Código postal", maxlen=20, show=_CH_ABROAD, width="half"),
        _f("country", "text", "Country", "País", req=True, maxlen=60, show=_CH_ABROAD),
        _f("applying", "choice", "Is this child applying with you (included in this petition)?", "¿Este hijo(a) solicita contigo (está incluido en esta petición)?", req=True, options=_YES_NO),
    ],
    "add": {"en": "Add another child", "es": "Agregar otro hijo(a)"}, "add_first": {"en": "Add a child", "es": "Agregar un hijo(a)"},
    "empty": {"en": "No children added yet.", "es": "Aún no has agregado hijos."},
}


# Issue texts (EN, ES). `{}` placeholders are filled from each issue's args.
MESSAGES = {
    "required": ("Please complete: {label}.", "Completa: {label}."),
    "bad_date": ("Enter a valid date for {label}.", "Ingresa una fecha válida para {label}."),
    "missing_from": ("Add the start date.", "Agrega la fecha de inicio."),
    "missing_to": ("Add the end date, or choose “Present”.", "Agrega la fecha de fin, o elige “Actual”."),
    "reversed": ("The end date is before the start date. Please review these dates.", "La fecha de fin es anterior a la de inicio. Revisa estas fechas."),
    "future": ("This date is in the future. Please review it.", "Esta fecha está en el futuro. Revísala."),
    "many_present": ("Only your current address can be “Present”. Please review these dates.", "Solo tu dirección actual puede ser “Actual”. Revisa estas fechas."),
    "gap": ("We found a gap from {start} to {end}. Please review your dates or add what you were doing during this period.",
            "Encontramos un vacío del {start} al {end}. Revisa tus fechas o agrega lo que hacías en este período."),
    "gap_address": ("We found a gap in your residence history from {start} to {end}. Please review your dates or add the address where you lived during this period.",
                    "Encontramos un vacío en tu historial de residencia del {start} al {end}. Revisa tus fechas o agrega la dirección donde viviste en este período."),
    "gap_activity": ("We still need information for {start} to {end}. Add where you worked, studied, or whether you were self-employed, unemployed, or retired.",
                     "Aún necesitamos información del {start} al {end}. Agrega dónde trabajaste o estudiaste, o si trabajaste por cuenta propia, estabas desempleado(a) o jubilado(a)."),
    "overlap": ("These two entries overlap by {days} days ({start} to {end}). Please review these dates.",
                "Estas dos entradas se traslapan {days} días ({start} al {end}). Revisa estas fechas."),
    "duplicate": ("This looks like a duplicate of another entry. Please review it.", "Esto parece un duplicado de otra entrada. Revísalo."),
    "trip_overlap": ("This trip overlaps another trip ({start} to {end}). Please review these dates.",
                     "Este viaje se traslapa con otro ({start} al {end}). Revisa estas fechas."),
    "day_trip": ("Trips completed within 24 hours do not need to be listed.", "Los viajes de un solo día (menos de 24 horas) no necesitan listarse."),
    "long_trip": ("This trip may require additional review by OG Multiservices.", "Este viaje puede requerir una revisión adicional por parte de OG Multiservices."),
    "old_trip": ("This trip is before the period requested, so you may not need to list it.", "Este viaje es anterior al período solicitado, así que quizá no necesites listarlo."),
    "child_18": ("This child appears to be 18 or older; this section asks about children under 18. Please review.",
                 "Este hijo(a) parece tener 18 años o más; esta sección pregunta por hijos menores de 18. Revísalo."),
    "min_records": ("Add at least one entry.", "Agrega al menos una entrada."),
    "many_current": ("Only one spouse can be your current spouse. Please review these answers.", "Solo un cónyuge puede ser tu cónyuge actual. Revisa estas respuestas."),
    "no_current": ("We still need your current entry.", "Aún necesitamos tu entrada actual."),
    "bad_amount": ("Enter {label} as a dollar amount, for example 12500 or 12,500.50.", "Ingresa {label} como una cantidad en dólares, por ejemplo 12500 o 12,500.50."),
    "bad_year": ("Enter a four-digit tax year that is not in the future.", "Ingresa un año fiscal de cuatro dígitos que no esté en el futuro."),
    "dup_person": ("This person is already listed above, so they are counted only once. Please review.", "Esta persona ya aparece arriba, así que se cuenta una sola vez. Revísalo."),
    "dup_income": ("This person's income is already listed above, so it is counted only once. Please review.", "El ingreso de esta persona ya aparece arriba, así que se cuenta una sola vez. Revísalo."),
    "dup_year": ("This tax year is listed more than once. Please review.", "Este año fiscal aparece más de una vez. Revísalo."),
}

UI = {
    "en": {
        "add": "Add", "save": "Save", "cancel": "Cancel", "edit": "Edit", "remove": "Remove", "present": "Present", "current": "Current",
        "from": "From", "to": "To", "left": "Date you left the U.S.", "returned": "Date you returned to the U.S.",
        "present_check": "I still live/work/study here (Present)", "covered": "covered", "of": "of", "years": "years", "months": "months",
        "need_more": "We still need more history to cover the period requested.", "complete": "This period is fully covered.",
        "trips": "Trips recorded", "days_outside": "Total days outside the U.S.", "days": "days", "day": "day",
        "memory": "Not sure of your travel dates? You may want to check your passport, airline emails, tickets, calendar, photos, or travel confirmations.",
        "saving": "Checking…", "fix_form": "Please complete the highlighted fields.", "required": "Required",
        "window": "Period requested", "gap_label": "Missing", "covered_label": "Covered", "add_more_prompt": "Add another",
        "select": "— Select —", "yes": "Yes", "no": "No", "check_dates": "Please review these dates.",
    },
    "es": {
        "add": "Agregar", "save": "Guardar", "cancel": "Cancelar", "edit": "Editar", "remove": "Quitar", "present": "Actual", "current": "Actual",
        "from": "Desde", "to": "Hasta", "left": "Fecha en que saliste de EE. UU.", "returned": "Fecha en que regresaste a EE. UU.",
        "present_check": "Todavía vivo/trabajo/estudio aquí (Actual)", "covered": "cubiertos", "of": "de", "years": "años", "months": "meses",
        "need_more": "Aún necesitamos más historial para cubrir el período solicitado.", "complete": "Este período está completamente cubierto.",
        "trips": "Viajes registrados", "days_outside": "Total de días fuera de EE. UU.", "days": "días", "day": "día",
        "memory": "¿No recuerdas las fechas de tus viajes? Puedes revisar tu pasaporte, correos de aerolíneas, boletos, calendario, fotos o confirmaciones de viaje.",
        "saving": "Revisando…", "fix_form": "Completa los campos resaltados.", "required": "Obligatorio",
        "window": "Período solicitado", "gap_label": "Falta", "covered_label": "Cubierto", "add_more_prompt": "Agregar otro",
        "select": "— Selecciona —", "yes": "Sí", "no": "No", "check_dates": "Revisa estas fechas.",
    },
}


# ------------------------------------------------------------------ config / parsing
def _kind(rtype):
    """The behaviour family of a record type (several types can share one, e.g. the
    N-400 "activity" and the I-130 "employment" both behave as timelines of activities)."""
    return RECORD_TYPES.get(rtype, {}).get("kind", rtype)


def field_config(field):
    """The record_list settings of a field: record type + timeline rules + limits."""
    try:
        cfg = json.loads(field.config_json) if field.config_json else {}
    except ValueError:
        cfg = {}
    cfg.setdefault("record", "address")
    rtype = RECORD_TYPES.get(cfg["record"], RECORD_TYPES["address"])
    cfg.setdefault("max", 20)
    tl = cfg.get("timeline")
    if rtype["timeline"] and tl is None:
        cfg["timeline"] = {"years": 5}
    if cfg.get("timeline") is not None:
        cfg["timeline"].setdefault("years", 5)
        cfg["timeline"].setdefault("gap_days", 3)
        cfg["timeline"].setdefault("overlap_days", 31)
    return cfg


def parse_date(value):
    if isinstance(value, date):
        return value
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def subtract_years(d, years):
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # Feb 29
        return d.replace(year=d.year - years, day=28)


def fmt(d, lang):
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec") if lang == "en" else \
             ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    return f"{months[d.month - 1]} {d.day}, {d.year}" if lang == "en" else f"{d.day} {months[d.month - 1]} {d.year}"


def fmt_month(d, lang):
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec") if lang == "en" else \
             ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    return f"{months[d.month - 1]} {d.year}"


def parse_records(raw):
    """A list of dicts from stored/submitted JSON; anything else -> []."""
    if isinstance(raw, list):
        data = raw
    else:
        try:
            data = json.loads(raw) if raw else []
        except (TypeError, ValueError):
            return []
    return [r for r in data if isinstance(r, dict)][:MAX_RECORDS] if isinstance(data, list) else []


def sanitize_records(records, cfg):
    """Keep only known keys with short string values; dates must parse (else dropped)."""
    rtype = RECORD_TYPES.get(cfg["record"], RECORD_TYPES["address"])
    names = {f["name"]: f for f in rtype["fields"]}
    date_names = {f["name"] for f in rtype["fields"] if f["type"] == "date"} | set(rtype["date_fields"])
    clean = []
    for rec in records[: cfg.get("max", 20)]:
        out = {}
        for key, value in rec.items():
            if key == "present":
                out["present"] = bool(value)
            elif key in date_names:
                d = parse_date(value)
                out[key] = d.isoformat() if d else ""
            elif key in names and isinstance(value, (str, int, float)):
                out[key] = str(value).strip()[: names[key].get("maxlength") or MAX_TEXT]
        if any(v not in ("", None, False) for v in out.values()):
            clean.append(out)
    return clean


# ------------------------------------------------------------------ text for one record
def _unit(rec):
    labels = {"apt": "Apt.", "ste": "Ste.", "flr": "Flr."}
    if rec.get("unit_number"):
        return f" {labels.get(rec.get('unit_type'), '')} {rec['unit_number']}".rstrip()
    return ""


def _option_label(rtype, fname, value, lang):
    for f in RECORD_TYPES[rtype]["fields"]:
        if f["name"] == fname:
            for v, en, es in f["options"]:
                if v == value:
                    return es if lang == "es" else en
    return value or ""


def period_text(rec, lang):
    a, b = parse_date(rec.get("from")), parse_date(rec.get("to"))
    present = "Present" if lang == "en" else "Actual"
    start = fmt_month(a, lang) if a else "?"
    end = present if rec.get("present") else (fmt_month(b, lang) if b else "?")
    return f"{start} – {end}"


def _usd(value):
    m = parse_money(value)
    return f"${m:,.2f}".replace(".00", "") if m is not None else ""


def _record_person_name(rec):
    """Name of a person record: what was typed, or (for a linked real Person) what the server copied from the Person."""
    return _full_name(rec) or ("(linked person)" if rec.get("person_id") else "")


def _full_name(rec):
    return " ".join(x for x in (rec.get("given"), rec.get("middle"), rec.get("family")) if x)


def card_for(rtype, rec, lang):
    """(title, subtitle) shown on a compact record card and in review/admin."""
    kind = _kind(rtype)
    en = lang == "en"
    if kind == "address":
        parts = [rec.get("street", "") + _unit(rec), rec.get("city", "")]
        if rec.get("is_us") == "yes":
            parts.append(f"{rec.get('state', '')} {rec.get('zip', '')}".strip())
        else:
            parts += [rec.get("province", ""), rec.get("postal_code", ""), rec.get("country", "")]
        return ", ".join(p for p in parts if p), period_text(rec, lang)
    if kind == "activity":
        atype = rec.get("type")
        label = _option_label(rtype, "type", atype, lang)
        if atype in ("employed", "student"):
            title = rec.get("name") or label
        elif atype == "self_employed":
            title = "Self-employed" if en else "Por cuenta propia"
        elif atype == "unemployed":
            title = "Unemployed" if en else "Desempleado(a)"
        elif atype == "retired":
            title = "Retired" if en else "Jubilado(a)"
        else:
            title = label
        place = ", ".join(x for x in (rec.get("street"), rec.get("city"), rec.get("state"), rec.get("country")) if x)
        sub = " · ".join(p for p in (rec.get("occupation"), place) if p)
        return title, (sub + " · " if sub else "") + period_text(rec, lang)
    if kind == "trip":
        a, b = parse_date(rec.get("from")), parse_date(rec.get("to"))
        dur = (b - a).days if a and b and b >= a else None
        ds = f"{fmt(a, lang) if a else '?'} → {fmt(b, lang) if b else '?'}"
        if dur is not None:
            ds += f" · {dur} {UI[lang]['day'] if dur == 1 else UI[lang]['days']}"
        return rec.get("countries", ""), ds
    if kind == "child":
        name = f"{rec.get('given', '')} {rec.get('family', '')}".strip()
        bits = [_option_label(rtype, "relationship", rec.get("relationship"), lang), _option_label(rtype, "residence", rec.get("residence"), lang)]
        return name, " · ".join(b for b in bits if b)
    if kind == "other_name":
        return _full_name(rec), ""
    if kind == "offense":
        d = parse_date(rec.get("date"))
        return rec.get("offense", ""), " · ".join(x for x in (rec.get("place"), fmt(d, lang) if d else "", rec.get("result")) if x)
    if kind == "spouse":
        ended = parse_date(rec.get("date_ended"))
        if rec.get("current") == "yes":
            sub = "Current spouse" if en else "Cónyuge actual"
        else:
            sub = ("Prior spouse" if en else "Cónyuge anterior") + (f" · {'Marriage ended' if en else 'Terminó'} {fmt(ended, lang)}" if ended else "")
        return _full_name(rec), sub
    if kind == "parent":
        d = parse_date(rec.get("dob"))
        return _full_name(rec), " · ".join(b for b in (fmt(d, lang) if d else "", rec.get("country_birth", "")) if b)
    if kind == "prior_marriage":
        ended = parse_date(rec.get("date_ended"))
        how = _option_label(rtype, "how_ended", rec.get("how_ended"), lang)
        sub = " · ".join(x for x in (how, (f"{'Ended' if en else 'Terminó'} {fmt(ended, lang)}") if ended else "") if x)
        return _full_name(rec), sub
    if kind == "i485_child":
        d = parse_date(rec.get("dob"))
        return _full_name(rec), " · ".join(b for b in (rec.get("relationship", ""), fmt(d, lang) if d else "", rec.get("country_birth", "")) if b)
    if kind == "organization":
        place = ", ".join(x for x in (rec.get("city"), rec.get("state"), rec.get("country")) if x)
        return rec.get("name", ""), " · ".join(x for x in (place, period_text(rec, lang) if rec.get("from") else "") if x)
    if kind == "other_dob":
        d = parse_date(rec.get("dob"))
        return (fmt(d, lang) if d else ""), ""
    if kind == "benefit":
        d = parse_date(rec.get("start"))
        return rec.get("benefit", ""), " · ".join(x for x in (fmt(d, lang) if d else "", rec.get("amount", "")) if x)
    if kind == "i864_person":
        d = parse_date(rec.get("dob"))
        cat = _option_label(rtype, "category", rec.get("category"), lang) if rec.get("category") else rec.get("relationship", "")
        cat = cat.split(" who ")[0].split(" with ")[0] if len(cat) > 48 else cat
        return _record_person_name(rec), " · ".join(b for b in (cat, fmt(d, lang) if d else "") if b)
    if kind == "i751_child":
        d = parse_date(rec.get("dob"))
        lives = {"with_me": "Lives with you" if en else "Vive contigo", "us": "Lives elsewhere in the U.S." if en else "Vive en otro lugar de EE. UU.",
                 "abroad": "Lives outside the U.S." if en else "Vive fuera de EE. UU."}.get(rec.get("where"), "")
        app = {"yes": "Applying with you" if en else "Solicita contigo", "no": "Not applying with you" if en else "No solicita contigo"}.get(rec.get("applying"), "")
        return _record_person_name(rec), " · ".join(b for b in (fmt(d, lang) if d else "", lives, app) if b)
    if kind == "country":
        return rec.get("country", ""), ""
    if kind == "i864_income":
        return _record_person_name(rec), " · ".join(b for b in (rec.get("relationship", ""), _usd(rec.get("income"))) if b)
    if kind == "i864_source":
        title = rec.get("name") or rec.get("description") or _option_label(rtype, "type", rec.get("type"), lang)
        return title, " · ".join(b for b in (rec.get("occupation", ""), _usd(rec.get("income"))) if b)
    if kind == "tax_year":
        inc = {"zero": "Zero" if en else "Cero", "na": "N/A"}.get(rec.get("income_kind")) or _usd(rec.get("income"))
        return (f"Tax year {rec.get('year', '?')}" if en else f"Año fiscal {rec.get('year', '?')}"), inc
    if kind == "asset":
        owner = _option_label(rtype, "owner", rec.get("owner"), lang).split(" (")[0].split(" who ")[0]
        what = _option_label(rtype, "kind", rec.get("kind"), lang).split(" (")[0]
        return f"{what} · {rec.get('holder') or owner}", " · ".join(b for b in (rec.get("description", ""), _usd(rec.get("value"))) if b)
    if kind == "relative":
        d = parse_date(rec.get("dob"))
        return _full_name(rec), " · ".join(b for b in (rec.get("relationship", ""), fmt(d, lang) if d else "", rec.get("country_birth", "")) if b)
    if kind == "prior_petition":
        d = parse_date(rec.get("date_filed"))
        place = ", ".join(x for x in (rec.get("city"), rec.get("state")) if x)
        return _full_name(rec), " · ".join(b for b in (place, fmt(d, lang) if d else "", rec.get("result", "")) if b)
    if kind == "other_relative":
        return _full_name(rec), rec.get("relationship", "")
    card = RECORD_TYPES.get(rtype, {}).get("card")
    if card:  # declarative card (DS-260 record types): fields joined for the title and the subtitle
        def part(name):
            value = rec.get(name)
            if not value:
                return ""
            ftype = next((f["type"] for f in RECORD_TYPES[rtype]["fields"] if f["name"] == name), "text")
            if ftype == "date":
                d = parse_date(value)
                return fmt(d, lang) if d else str(value)
            if ftype in ("select", "choice"):
                return _option_label(rtype, name, value, lang)
            return str(value)

        title = " ".join(x for x in (part(n) for n in card["title"]) if x)
        if not title and rec.get("person_id"):
            title = "(linked person)" if en else "(persona vinculada)"
        sub = " · ".join(x for x in (part(n) for n in card.get("sub", [])) if x)
        if card.get("period") and (rec.get("from") or rec.get("to")):
            sub = " · ".join(x for x in (sub, period_text(rec, lang)) if x)
        return title, sub
    return "", ""


# ------------------------------------------------------------------ analysis
def _issue(level, code, lang, index=None, **args):
    en, es = MESSAGES[code]
    text = (es if lang == "es" else en).format(**args) if args else (es if lang == "es" else en)
    return {"level": level, "code": code, "message": text, "index": index}


def _record_errors(rtype, cfg, records, today, lang):
    spec = RECORD_TYPES[rtype]
    kind = _kind(rtype)
    issues = []
    for i, rec in enumerate(records):
        vis = {}
        for f in spec["fields"]:
            show = f.get("show_if")
            if show and rec.get(show["field"]) not in show["values"]:
                continue
            if f["required"] and not str(rec.get(f["name"], "")).strip():
                issues.append(_issue("error", "required", lang, i, label=f["label"][lang]))
        if "from" in spec["date_fields"]:
            a, b = parse_date(rec.get("from")), parse_date(rec.get("to"))
            if not a:
                issues.append(_issue("error", "missing_from", lang, i))
            elif a > today:
                issues.append(_issue("error", "future", lang, i))
            if kind == "trip":
                if not b:
                    issues.append(_issue("error", "missing_to", lang, i))
                elif b > today:
                    issues.append(_issue("error", "future", lang, i))
            elif not rec.get("present") and not b:
                issues.append(_issue("error", "missing_to", lang, i))
            elif b and b > today and not rec.get("present"):
                issues.append(_issue("error", "future", lang, i))
            if a and b and not rec.get("present") and b < a:
                issues.append(_issue("error", "reversed", lang, i))
        for f in spec["fields"]:
            show = f.get("show_if")
            if f.get("money") and rec.get(f["name"]) not in (None, "") and not (show and rec.get(show["field"]) not in show["values"]):
                if parse_money(rec.get(f["name"])) is None:
                    issues.append(_issue("error", "bad_amount", lang, i, label=f["label"][lang]))
        if kind == "tax_year" and rec.get("year"):
            y = str(rec.get("year"))
            if not (y.isdigit() and len(y) == 4 and 1990 <= int(y) <= today.year):
                issues.append(_issue("error", "bad_year", lang, i))
        for f in spec["fields"]:
            if f["type"] == "date" and rec.get(f["name"]):
                d = parse_date(rec.get(f["name"]))
                if d and d > today:
                    issues.append(_issue("error", "future", lang, i))
    return issues


def _merge(intervals):
    merged = []
    for s, e in sorted(intervals):
        if merged and s <= merged[-1][1] + DAY:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def _norm(text):
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


def analyze(cfg, records, lang="en", today=None, since=None):
    """Everything the UI, the review, the completeness check and Admin need to know
    about a list of records.

    {"issues": [{level, code, message, index}], "cards": [{title, subtitle, flags}],
     "timeline": {start, end, segments:[{start, end, covered}]} | None,
     "summary": {...}, "complete": bool}
    """
    today = today or date.today()
    rtype = cfg["record"]
    spec = RECORD_TYPES[rtype]
    kind = _kind(rtype)
    issues = _record_errors(rtype, cfg, records, today, lang)
    cards = [{"title": t, "subtitle": s, "flags": []} for t, s in (card_for(rtype, r, lang) for r in records)]
    summary, timeline = {}, None
    tl = cfg.get("timeline")

    valid = []  # (index, start, end)
    for i, r in enumerate(records):
        a = parse_date(r.get("from"))
        b = today if r.get("present") else parse_date(r.get("to"))
        if a and b and b >= a and (kind != "trip" or not r.get("present")):
            valid.append((i, a, b))

    if spec["timeline"] and tl:
        years, gap_tol, ov_tol = tl["years"], tl["gap_days"], tl["overlap_days"]
        if tl.get("since_field"):  # the period starts at a date the customer gave (e.g. when they became a resident), not a fixed number of years
            since = parse_date(since)
            if since is not None and since > today:
                since = None
            w_start = since or (min(a for _i, a, _b in valid) if valid else today)
            years = round((today - w_start).days / 365.25, 1)
        else:
            w_start = subtract_years(today, years)
        if kind == "address" and sum(1 for r in records if r.get("present")) > 1:
            issues.append(_issue("error", "many_present", lang, [i for i, r in enumerate(records) if r.get("present")][-1]))
        # overlaps (addresses only: working and studying at once is normal)
        if kind == "address":
            ordered = sorted(valid, key=lambda x: x[1])
            for x in range(len(ordered)):
                for y in range(x + 1, len(ordered)):
                    (i1, a1, b1), (i2, a2, b2) = ordered[x], ordered[y]
                    if a2 > b1:
                        break
                    days = (min(b1, b2) - max(a1, a2)).days + 1
                    if days > ov_tol:
                        issues.append(_issue("warn", "overlap", lang, i2, days=days, start=fmt(max(a1, a2), lang), end=fmt(min(b1, b2), lang)))
        seen = {}
        for i, r in enumerate(records):
            key = (_norm(r.get("street")) + _norm(r.get("city")) + (r.get("from") or "")) if kind == "address" else \
                  (_norm(r.get("name")) + _norm(r.get("type")) + (r.get("from") or "") + (r.get("to") or ""))
            if key and key in seen:
                issues.append(_issue("warn", "duplicate", lang, i))
            seen[key] = i
        intervals = [(max(a, w_start), b) for _i, a, b in valid if b >= w_start]
        merged = _merge(intervals)
        gaps = []
        if not records:
            pass
        elif not merged:
            gaps.append((w_start, today))
        else:
            if merged[0][0] - w_start > timedelta(days=gap_tol):
                gaps.append((w_start, merged[0][0] - DAY))
            for k in range(1, len(merged)):
                if merged[k][0] - merged[k - 1][1] - DAY > timedelta(days=gap_tol):
                    gaps.append((merged[k - 1][1] + DAY, merged[k][0] - DAY))
            if today - merged[-1][1] > timedelta(days=gap_tol):
                gaps.append((merged[-1][1] + DAY, today))
        code = "gap_address" if kind == "address" else "gap_activity"
        for s, e in gaps:
            issues.append(_issue("warn", code, lang, None, start=fmt(s, lang), end=fmt(e, lang)))
        covered = sum((e - s).days + 1 for s, e in merged)
        total = (today - w_start).days + 1
        segments = []
        cursor = w_start
        for s, e in merged:
            if s > cursor:
                segments.append({"start": cursor.isoformat(), "end": (s - DAY).isoformat(), "covered": False})
            segments.append({"start": s.isoformat(), "end": e.isoformat(), "covered": True})
            cursor = e + DAY
        if cursor <= today:
            segments.append({"start": cursor.isoformat(), "end": today.isoformat(), "covered": False})
        months = int(covered / 30.4375)
        summary = {"covered_days": covered, "total_days": total, "percent": min(100, round(covered / total * 100)) if total else 0,
                   "years": months // 12, "months": months % 12, "gaps": len(gaps), "window_years": years}
        timeline = {"start": w_start.isoformat(), "end": today.isoformat(), "segments": segments}
        if not records:
            summary["percent"] = 0

    if kind == "trip":
        total_days, count = 0, 0
        w_start = subtract_years(today, (tl or {}).get("years", cfg.get("years", 5))) if (tl or cfg.get("years")) else None
        seen = set()
        ordered = sorted(valid, key=lambda x: x[1])
        for i, a, b in valid:
            count += 1
            days = (b - a).days
            total_days += days
            if days == 0:
                issues.append(_issue("warn", "day_trip", lang, i))
                cards[i]["flags"].append("day_trip")
            if days > 180:
                issues.append(_issue("review", "long_trip", lang, i))
                cards[i]["flags"].append("long_trip")
            if w_start and b < w_start:
                issues.append(_issue("info", "old_trip", lang, i))
            key = (a, b)
            if key in seen:
                issues.append(_issue("warn", "duplicate", lang, i))
            seen.add(key)
        for x in range(len(ordered)):
            for y in range(x + 1, len(ordered)):
                (i1, a1, b1), (i2, a2, b2) = ordered[x], ordered[y]
                if a2 >= b1:
                    break
                issues.append(_issue("warn", "trip_overlap", lang, i2, start=fmt(max(a1, a2), lang), end=fmt(min(b1, b2), lang)))
        summary = {"trips": count, "days_outside": total_days}

    if kind == "spouse":
        currents = [i for i, r in enumerate(records) if r.get("current") == "yes"]
        if len(currents) > 1:
            issues.append(_issue("error", "many_current", lang, currents[-1]))
        for i, r in enumerate(records):
            if r.get("current") == "no" and not parse_date(r.get("date_ended")):
                issues.append(_issue("error", "required", lang, i, label=("Date the marriage ended" if lang == "en" else "Fecha en que terminó el matrimonio")))

    if kind in ("i864_person", "i864_income", "i751_child", "ds_person"):
        def same_person(a, b):
            if a.get("person_id") and str(a.get("person_id")) == str(b.get("person_id")):
                return True
            na, nb = _norm(a.get("given")) + _norm(a.get("family")), _norm(b.get("given")) + _norm(b.get("family"))
            return bool(na) and na == nb and not (a.get("dob") and b.get("dob") and a.get("dob") != b.get("dob"))

        for i, r in enumerate(records):
            if any(same_person(r, records[j]) for j in range(i)):
                issues.append(_issue("warn", "dup_income" if kind == "i864_income" else "dup_person", lang, i))
    if kind == "tax_year":
        seen = set()
        for i, r in enumerate(records):
            if r.get("year") in seen:
                issues.append(_issue("warn", "dup_year", lang, i))
            seen.add(r.get("year"))

    if kind == "child":
        for i, r in enumerate(records):
            d = parse_date(r.get("dob"))
            if d and (today.year - d.year - ((today.month, today.day) < (d.month, d.day))) >= 18:
                issues.append(_issue("review", "child_18", lang, i))

    for issue in issues:
        if issue["index"] is not None and 0 <= issue["index"] < len(cards):
            cards[issue["index"]]["flags"].append(issue["level"])

    blocking = [i for i in issues if i["level"] == "error"]
    needs = [i for i in issues if i["level"] in ("warn", "error")]
    complete = bool(records) and not needs if spec["timeline"] else not needs
    return {"issues": issues, "cards": cards, "timeline": timeline, "summary": summary, "complete": complete,
            "blocking": len(blocking), "needs_attention": len(needs), "record": rtype}


def records_error(field, records, lang):
    """A message that must block saving this step (bad/missing data), or None.
    Coverage gaps and other 'please review' items never block; they show up in the
    completeness check instead."""
    cfg = field_config(field)
    if field.required and not records:
        return field.validation_message(lang) or MESSAGES["min_records"][1 if lang == "es" else 0]
    if not records:
        return None
    result = analyze(cfg, records, lang)
    errors = [i["message"] for i in result["issues"] if i["level"] == "error"]
    return " ".join(errors[:2]) if errors else None


def display_records(field, records, lang):
    """One line per record, for review pages, snapshots and Admin."""
    cfg = field_config(field)
    lines = []
    for rec in records:
        title, sub = card_for(cfg["record"], rec, lang)
        lines.append(f"{title} ({sub})" if sub else title)
    return "\n".join(lines)


def _with_names(text, lang):
    from app.intake_shared import apply_tokens

    return apply_tokens(text, lang)


def _since_input(field, cfg):
    """Input name of the field whose value starts this timeline (config `timeline.since_field`), so the browser can send it with each analysis."""
    name = ((cfg.get("timeline") or {}).get("since_field"))
    if not name:
        return None
    other = next((f for f in field.page.form.all_fields if f.internal_name == name), None)
    return other.input_name() if other is not None else None


def since_from_answers(cfg, answers_by_internal_name):
    """The parsed start date of a timeline whose window starts at an answer (None when not configured or not given)."""
    name = (cfg.get("timeline") or {}).get("since_field")
    return parse_date(answers_by_internal_name.get(name)) if name else None


def client_spec(field, lang):
    """JSON handed to the browser component: labels for the current language only."""
    cfg = field_config(field)
    rtype = cfg["record"]
    spec = RECORD_TYPES[rtype]

    def pick(d):
        return d[lang] if isinstance(d, dict) else d

    fields = []
    allowed = cfg.get("types")
    for f in spec["fields"]:
        if f.get("internal"):
            continue
        options = [o for o in f["options"] if not (allowed and f["name"] == "type" and o[0] not in allowed)]
        if f.get("dynamic_options") == "persons":
            from flask import g

            options = [("", "Someone new — I will type their details", "Alguien nuevo: escribiré sus datos")] + list(getattr(g, "person_options", None) or [])
        fields.append({
            "name": f["name"], "type": f["type"], "label": pick(f["label"]), "required": f["required"], "show_if": f["show_if"],
            "maxlength": f["maxlength"], "width": f["width"], "help": pick(f["help"]) if f["help"] else None, "pattern": f["pattern"],
            "options": [{"value": v, "label": es if lang == "es" else en} for v, en, es in options],
        })
    return {
        "record": rtype, "max": cfg["max"], "timeline": cfg.get("timeline"), "has_dates": "from" in spec["date_fields"],
        "kind_trip": _kind(rtype) == "trip", "fields": fields, "ui": UI[lang], "today": date.today().isoformat(), "since_input": _since_input(field, cfg),
        "add": pick(spec["add"]), "add_first": pick(spec["add_first"]), "empty": pick(spec["empty"]),
        "intro": _with_names(cfg.get("intro", {}).get(lang), lang) if isinstance(cfg.get("intro"), dict) else None,
    }


_US_NAMES = {"us", "usa", "unitedstates", "unitedstatesofamerica", "eeuu", "estadosunidos"}


def is_us_country(text):
    return "".join(ch for ch in (text or "").lower() if ch.isalnum()) in _US_NAMES


def _span(rec, today):
    a = parse_date(rec.get("from"))
    b = today if rec.get("present") else parse_date(rec.get("to"))
    return (a, b) if a and b and b >= a else (None, None)


def last_foreign_address(records, today=None):
    """The most recent address OUTSIDE the U.S. where the person lived for more than one
    year (I-130A Part 1, Item 8), taken from an address history; None when none clearly
    qualifies."""
    today = today or date.today()
    best = None
    for rec in records:
        if rec.get("is_us") != "no":
            continue
        a, b = _span(rec, today)
        if a and (b - a).days > 365 and (best is None or (b, a) > best[0]):
            best = ((b, a), rec)
    return best[1] if best else None


def last_foreign_job(records, today=None):
    """The most recent job outside the U.S. in an employment history (I-130A Part 3)."""
    today = today or date.today()
    best = None
    for rec in records:
        if rec.get("type") not in ("employed", "self_employed") or not rec.get("country") or is_us_country(rec.get("country")):
            continue
        a, b = _span(rec, today)
        key = (b or date.min, a or date.min)
        if best is None or key > best[0]:
            best = (key, rec)
    return best[1] if best else None


CANDIDATES = {"last_foreign_address": last_foreign_address, "last_foreign_job": last_foreign_job, "last_foreign_activity": last_foreign_activity}

_KEEP = ("street", "unit_type", "unit_number", "city", "province", "postal_code", "country", "from", "to", "present")


def _default_employment(spec, named):
    """Starting job entry from the current-employment answers the intake already has."""
    flag = named.get(spec["employed"])
    if flag == "no":
        return [{"type": "unemployed", "present": True}]
    if flag != "yes":
        return []
    prefix = spec["prefix"]
    rec = {"type": "employed", "present": True}
    for key, src in (("name", spec["name"]), ("street", f"{prefix}_street"), ("unit_number", f"{prefix}_unit_number"), ("city", f"{prefix}_city"), ("from", spec["start"])):
        if named.get(src):
            rec[key] = named[src]
    if named.get(f"{prefix}_is_us") == "yes":
        rec.update(state=named.get(f"{prefix}_state") or "", zip=named.get(f"{prefix}_zip") or "", country="United States")
    else:
        rec.update(state=named.get(f"{prefix}_province") or "", zip=named.get(f"{prefix}_postal_code") or "", country=named.get(f"{prefix}_country") or "")
    return [rec]


def default_records(field, named):
    """Starting records for an empty list, copied from answers given elsewhere in the
    intake (for example: the mailing address is also where the person lives, so the
    current-address entry starts pre-filled). Only used while nothing is saved yet; the
    customer can edit or remove anything. `named` maps internal field names to answers."""
    cfg = field_config(field)
    src = cfg.get("default_from")
    if not src:
        return []
    when = src.get("when")
    if when and named.get(when["field"]) != when["equals"]:
        return []
    if src.get("employment"):
        return _default_employment(src["employment"], named)
    if src.get("candidate"):
        found = CANDIDATES[src["candidate"]](parse_records(named.get(src["source"])))
        return [{k: found[k] for k in _KEEP if found.get(k)}] if found else []
    prefix = src["prefix"]
    rec = {"is_us": named.get(f"{prefix}_is_us") or "yes"}
    for key in ("street", "unit_type", "unit_number", "city", "state", "zip", "province", "postal_code", "country"):
        value = named.get(f"{prefix}_{key}")
        if value:
            rec[key] = value
    if not rec.get("street") and not rec.get("city"):
        return []
    if src.get("present"):
        rec["present"] = True
    return [rec]


from app import ds260_records  # noqa: E402,F401  (registers the DS-260 record types)
