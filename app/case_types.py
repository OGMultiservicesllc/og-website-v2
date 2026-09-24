"""Registries for the case architecture (code, not database, so existing forms are never edited).

  CASE_TYPES       what kind of matter a case is.
  ROLE_LABELS      what a person can be inside one application.
  RELATIONSHIPS    how a case person relates to the customer.
  FACTS            the canonical person facts and how they are shown.
  FORM_CASE_CONFIG which case type a form belongs to, who the people are in that form's answers, and which
                   of its answers are the SAME real-world fact as a person fact. This is deliberately a
                   short, explicit allow-list: anything not listed stays application-specific.
  DOCUMENT_CATEGORIES generic vault categories (not tied to any one kind of case).

A future form (I-485, I-864, I-765...) plugs in by adding one entry to FORM_CASE_CONFIG.
"""

CASE_TYPES = {
    "green_card_renewal": {"en": "Green Card Renewal", "es": "Renovación de Green Card"},
    "naturalization": {"en": "Naturalization", "es": "Naturalización"},
    "family_petition": {"en": "Family Petition", "es": "Petición familiar"},
    "adjustment_of_status": {"en": "Adjustment of Status", "es": "Ajuste de estatus"},
    "employment_authorization": {"en": "Employment Authorization", "es": "Autorización de empleo"},
    "removal_of_conditions": {"en": "Removal of Conditions on Residence", "es": "Remoción de condiciones de la residencia"},
    "other": {"en": "Other matter", "es": "Otro trámite"},
}

ROLE_LABELS = {
    "applicant": {"en": "Applicant", "es": "Solicitante"},
    "petitioner": {"en": "Petitioner", "es": "Peticionario"},
    "beneficiary": {"en": "Beneficiary", "es": "Beneficiario"},
    "spouse_beneficiary": {"en": "Spouse beneficiary", "es": "Cónyuge beneficiario"},
    "spouse": {"en": "Spouse", "es": "Cónyuge"},
    "parent": {"en": "Parent", "es": "Padre o madre"},
    "child": {"en": "Child", "es": "Hijo(a)"},
    "sponsor": {"en": "Sponsor", "es": "Patrocinador"},
    "joint_sponsor": {"en": "Joint sponsor", "es": "Patrocinador conjunto"},
    "substitute_sponsor": {"en": "Substitute sponsor", "es": "Patrocinador sustituto"},
    "sponsored_immigrant": {"en": "Sponsored immigrant", "es": "Inmigrante patrocinado"},
    "principal_immigrant": {"en": "Principal immigrant", "es": "Inmigrante principal"},
    "household_member": {"en": "Household member", "es": "Miembro del hogar"},
    "conditional_resident": {"en": "Conditional resident", "es": "Residente condicional"},
    "relevant_individual": {"en": "Spouse / relevant individual (Part 4)", "es": "Cónyuge / persona relevante (Parte 4)"},
    "joint_petitioner": {"en": "Joint filing spouse", "es": "Cónyuge que presenta en conjunto"},
    "former_spouse": {"en": "Former spouse", "es": "Excónyuge"},
    "parent_spouse": {"en": "Parent's spouse", "es": "Cónyuge del padre o la madre"},
    "other": {"en": "Other participant", "es": "Otro participante"},
}

RELATIONSHIPS = {
    "self": {"en": "Customer (account holder)", "es": "Cliente (titular de la cuenta)"},
    "spouse": {"en": "Spouse", "es": "Cónyuge"},
    "parent": {"en": "Parent", "es": "Padre o madre"},
    "child": {"en": "Child", "es": "Hijo(a)"},
    "sibling": {"en": "Brother or sister", "es": "Hermano(a)"},
    "petitioner": {"en": "Petitioner", "es": "Peticionario"},
    "joint_sponsor": {"en": "Joint sponsor", "es": "Patrocinador conjunto"},
    "household_member": {"en": "Household member", "es": "Miembro del hogar"},
    "other": {"en": "Other", "es": "Otro"},
}

# fact_key -> label, kind, sensitive
FACTS = {
    "family_name": {"en": "Family name", "es": "Apellido", "kind": "text"},
    "given_name": {"en": "Given name", "es": "Nombre", "kind": "text"},
    "middle_name": {"en": "Middle name", "es": "Segundo nombre", "kind": "text"},
    "date_of_birth": {"en": "Date of birth", "es": "Fecha de nacimiento", "kind": "date"},
    "birth_city": {"en": "City of birth", "es": "Ciudad de nacimiento", "kind": "text"},
    "birth_country": {"en": "Country of birth", "es": "País de nacimiento", "kind": "text"},
    "sex": {"en": "Sex", "es": "Sexo", "kind": "choice", "options": {"male": ("Male", "Masculino"), "female": ("Female", "Femenino")}},
    "a_number": {"en": "A-Number", "es": "Número A", "kind": "text", "sensitive": True},
    "uscis_account_number": {"en": "USCIS Online Account Number", "es": "Número de cuenta en línea de USCIS", "kind": "text"},
    "ssn": {"en": "Social Security number", "es": "Número de Seguro Social", "kind": "text", "sensitive": True},
    "phone_daytime": {"en": "Daytime phone", "es": "Teléfono de día", "kind": "text"},
    "phone_mobile": {"en": "Mobile phone", "es": "Teléfono móvil", "kind": "text"},
    "email": {"en": "Email", "es": "Correo electrónico", "kind": "text"},
    "current_address": {"en": "Current address", "es": "Dirección actual", "kind": "address"},
}
FACT_ORDER = list(FACTS)

# Person facts an applicant/customer answers about themselves (I-90 and N-400 use the same internal names).
_APPLICANT_FACTS = {
    "family_name": "name_family", "given_name": "name_given", "middle_name": "name_middle", "date_of_birth": "dob",
    "sex": "sex", "a_number": "a_number", "uscis_account_number": "uscis_account", "ssn": "ssn",
    "phone_daytime": "phone_daytime", "phone_mobile": "phone_mobile", "email": "contact_email",
}

# A fact is either a field name (str) or {"address_prefix": "x"} (a block of x_street, x_city ...) or
# {"record_present": "field"} (the `present` entry of a record_list).
FORM_CASE_CONFIG = {
    "I-90": {
        "case_type": "green_card_renewal",
        "people": [{"key": "applicant", "who": "customer", "roles": ["applicant"]}],
        "facts": {"applicant": dict(_APPLICANT_FACTS, birth_city="birth_city", birth_country="birth_country")},
    },
    "N-400": {
        "case_type": "naturalization",
        "people": [{"key": "applicant", "who": "customer", "roles": ["applicant"]}],
        "facts": {"applicant": dict(_APPLICANT_FACTS, birth_country="country_birth")},
    },
    "I-130": {
        "case_type": "family_petition",
        "people": [
            {"key": "petitioner", "who": "customer", "roles": ["petitioner"]},
            {"key": "beneficiary", "who": "named", "names": ("ben_given", "ben_family"), "roles": ["beneficiary"],
             "extra_roles": [{"role": "spouse_beneficiary", "when": ("relationship_type", "spouse")}],
             "relationship_field": "relationship_type", "a_number_field": "ben_a_number", "dob_field": "ben_dob"},
        ],
        "facts": {
            "petitioner": {
                "family_name": "pet_family", "given_name": "pet_given", "middle_name": "pet_middle", "date_of_birth": "pet_dob",
                "birth_city": "pet_birth_city", "birth_country": "pet_birth_country", "sex": "pet_sex", "a_number": "pet_a_number",
                "uscis_account_number": "pet_uscis_account", "ssn": "pet_ssn", "phone_daytime": "pet_phone", "phone_mobile": "pet_mobile",
                "email": "pet_email", "current_address": {"record_present": "pet_address_history"},
            },
            "beneficiary": {
                "family_name": "ben_family", "given_name": "ben_given", "middle_name": "ben_middle", "date_of_birth": "ben_dob",
                "birth_city": "ben_birth_city", "birth_country": "ben_birth_country", "sex": "ben_sex", "a_number": "ben_a_number",
                "uscis_account_number": "ben_uscis_account", "ssn": "ben_ssn", "phone_daytime": "ben_phone", "phone_mobile": "ben_mobile",
                "email": "ben_email", "current_address": {"address_prefix": "ben_phys"},
            },
        },
    },
}


def config_for(form):
    """Case configuration for a form, or None (a form that is not part of the case architecture)."""
    return FORM_CASE_CONFIG.get(form.source_form_name) if form is not None else None


def type_title(case_type, lang="en"):
    return CASE_TYPES.get(case_type, CASE_TYPES["other"])[lang if lang in ("en", "es") else "en"]


def role_label(role, lang="en"):
    return ROLE_LABELS.get(role, ROLE_LABELS["other"])[lang if lang in ("en", "es") else "en"]


DOCUMENT_CATEGORIES = {
    "passport": {"en": "Passport", "es": "Pasaporte"},
    "photo_id": {"en": "Photo ID", "es": "Identificación con foto"},
    "birth_certificate": {"en": "Birth certificate", "es": "Acta de nacimiento"},
    "marriage_certificate": {"en": "Marriage certificate", "es": "Acta de matrimonio"},
    "divorce_death_certificate": {"en": "Divorce decree or death certificate", "es": "Decreto de divorcio o acta de defunción"},
    "proof_of_status": {"en": "Proof of immigration or citizenship status", "es": "Prueba de estatus migratorio o ciudadanía"},
    "immigration_document": {"en": "Immigration document (I-94, visa, notice)", "es": "Documento migratorio (I-94, visa, notificación)"},
    "relationship_evidence": {"en": "Relationship evidence", "es": "Evidencia de la relación"},
    "financial_document": {"en": "Financial or tax document", "es": "Documento financiero o de impuestos"},
    "translation": {"en": "Certified translation", "es": "Traducción certificada"},
    "photos": {"en": "Photographs", "es": "Fotografías"},
    "police_certificate": {"en": "Police certificate", "es": "Certificado de antecedentes policiales"},
    "other": {"en": "Other document", "es": "Otro documento"},
}


def category_label(key, lang="en"):
    return DOCUMENT_CATEGORIES.get(key, DOCUMENT_CATEGORIES["other"])[lang if lang in ("en", "es") else "en"]


# ---------------------------------------------------------------- more canonical facts (I-485 phase)
FACTS.update({
    "nationality": {"en": "Country of citizenship or nationality", "es": "País de ciudadanía o nacionalidad", "kind": "text"},
    "i94_number": {"en": "Form I-94 number", "es": "Número del Formulario I-94", "kind": "text"},
    "class_of_admission": {"en": "Immigration status on Form I-94 / class of admission", "es": "Estatus migratorio en el I-94 / clase de admisión", "kind": "text"},
    "authorized_stay_type": {"en": "Authorized stay shown on Form I-94", "es": "Estadía autorizada según el I-94", "kind": "choice",
                             "options": {"date": ("Until a specific date", "Hasta una fecha específica"), "ds": ("Duration of status (D/S)", "Duración del estatus (D/S)")}},
    "authorized_stay_expiry": {"en": "Authorized stay expires", "es": "La estadía autorizada vence", "kind": "date"},
    "last_arrival_date": {"en": "Date of last arrival", "es": "Fecha de la última llegada", "kind": "date"},
    "other_names": {"en": "Other names used", "es": "Otros nombres usados", "kind": "records", "record": "other_name"},
    "address_history": {"en": "Address history", "es": "Historial de direcciones", "kind": "records", "record": "address"},
    "employment_history": {"en": "Employment / education history", "es": "Historial de empleo / estudios", "kind": "records", "record": "employment"},
    "parents": {"en": "Parents", "es": "Padres", "kind": "records", "record": "parent"},
})
FACT_ORDER = list(FACTS)

# I-130 answers that are the same real-world fact as the new facts above (explicit, like everything here).
FORM_CASE_CONFIG["I-130"]["facts"]["petitioner"].update({
    "other_names": "pet_other_names", "address_history": "pet_address_history", "employment_history": "pet_employment_history", "parents": "pet_parents",
})
FORM_CASE_CONFIG["I-130"]["facts"]["beneficiary"].update({
    "other_names": "ben_other_names", "address_history": "ben_address_history", "employment_history": "ben_employment_history", "parents": "ben_parents",
    "i94_number": "ben_i94", "class_of_admission": "ben_class_admission", "authorized_stay_type": "ben_stay_type",
    "authorized_stay_expiry": "ben_stay_date", "last_arrival_date": "ben_arrival_date",
})

# ---------------------------------------------------------------- Form I-485
def _blk(role, fields, require=(), *, related=None, only=None, also=None):
    return {"role": role, "fields": fields, "require": list(require), "related": related, "only": only or {}, "also": also or {}}


_SPOUSE_VIA = {"via": ("beneficiary", "spouse_beneficiary"), "to": "petitioner"}

FORM_CASE_CONFIG["I-485"] = {
    "case_type": "adjustment_of_status",
    "case_setup": True,
    "people": [{"key": "applicant", "who": "chosen", "names": ("a_given", "a_family"), "roles": ["applicant"], "relationship_field": None}],
    "record_people": [
        {"field": "s_spouse_marker", "relationship": "spouse", "role": "spouse", "kind": "scalar", "given": "s_given", "family": "s_family", "a_number": "s_anumber", "dob": "s_dob"},
        {"field": "a_children", "relationship": "child", "role": "child", "kind": "records", "given": "given", "family": "family", "a_number": "a_number", "dob": "dob"},
        {"field": "a_parents", "relationship": "parent", "role": "parent", "kind": "records", "given": "given", "family": "family", "dob": "dob"},
    ],
    "facts": {
        "applicant": {
            "family_name": "a_family", "given_name": "a_given", "middle_name": "a_middle", "date_of_birth": "a_dob", "sex": "a_sex",
            "birth_city": "a_birth_city", "birth_country": "a_birth_country", "nationality": "a_citizenship", "a_number": "a_anumber",
            "uscis_account_number": "a_uscis_account", "ssn": "a_ssn", "phone_daytime": "a_phone", "phone_mobile": "a_mobile", "email": "a_email",
            "current_address": {"address_prefix": "cur"}, "i94_number": "a_i94_number", "class_of_admission": "a_i94_status",
            "authorized_stay_type": "a_i94_stay_type", "authorized_stay_expiry": "a_i94_stay_date", "last_arrival_date": "a_arr_date",
            "address_history": "a_address_history", "employment_history": "a_employment_history", "parents": "a_parents", "other_names": "a_other_names",
        },
    },
    # Shared-review blocks: a page that shows what the case already knows ("We already have this ..."), lets the
    # applicant confirm or edit it, and records the confirmation / correction against the canonical fact.
    "blocks": {
        "sb_name": _blk("applicant", {"family_name": "a_family", "given_name": "a_given", "middle_name": "a_middle"}, ["family_name", "given_name"]),
        "sb_birth": _blk("applicant", {"date_of_birth": "a_dob", "sex": "a_sex", "birth_city": "a_birth_city", "birth_country": "a_birth_country",
                                       "nationality": "a_citizenship"}, ["date_of_birth", "sex", "birth_country"]),
        "sb_othernames": _blk("applicant", {"other_names": {"records": "a_other_names", "record": "other_name"}}, ["other_names"]),
        "sb_ids": _blk("applicant", {"a_number": "a_anumber"}, ["a_number"], also={"a_has_anumber": ("a_number", "yes")}),
        "sb_uscis": _blk("applicant", {"uscis_account_number": "a_uscis_account"}, ["uscis_account_number"]),
        "sb_ssn": _blk("applicant", {"ssn": "a_ssn"}, ["ssn"], also={"a_ssn_issued": ("ssn", "yes")}),
        "sb_arrival": _blk("applicant", {"last_arrival_date": "a_arr_date"}, ["last_arrival_date"]),
        "sb_i94": _blk("applicant", {"i94_number": "a_i94_number", "class_of_admission": "a_i94_status", "authorized_stay_type": "a_i94_stay_type",
                                     "authorized_stay_expiry": "a_i94_stay_date"}, [], also={"a_i94_issued": ("i94_number", "yes")}),
        "sb_address": _blk("applicant", {"current_address": {"address_prefix": "cur"}}, ["current_address"], only={"current_address": "us"}),
        "sb_addr_history": _blk("applicant", {"address_history": {"records": "a_address_history", "record": "address"}}, ["address_history"]),
        "sb_employment": _blk("applicant", {"employment_history": {"records": "a_employment_history", "record": "i485_activity",
                                                                    "map": {"type": "type", "name": "name", "occupation": "occupation", "street": "street",
                                                                            "unit_number": "unit_number", "city": "city", "state": "state", "zip": "zip",
                                                                            "country": "country", "from": "from", "to": "to", "present": "present"}}}, ["employment_history"]),
        "sb_parents": _blk("applicant", {"parents": {"records": "a_parents", "record": "i485_parent",
                                                     "map": {"family": "family", "given": "given", "middle": "middle", "dob": "dob", "country_birth": "country_birth"}}}, ["parents"]),
        "sb_spouse": _blk(None, {"family_name": "s_family", "given_name": "s_given", "middle_name": "s_middle", "date_of_birth": "s_dob",
                                 "birth_country": "s_birth_country", "a_number": "s_anumber"}, ["family_name", "given_name", "date_of_birth"], related=_SPOUSE_VIA),
        "sb_contact": _blk("applicant", {"phone_daytime": "a_phone", "phone_mobile": "a_mobile", "email": "a_email"}, ["phone_daytime"]),
    },
}


# ---------------------------------------------------------------- fact scopes (Person facts follow the real person; the rest stays isolated)
#   stable       identity facts. They may follow the same Person across cases; different values from different sources are a
#                CONFLICT that is never resolved silently.
#   situational  time-sensitive facts (address, phone, employment, arrival, I-94). Reusable, but always shown with their date and
#                confirmed again; a newer value is not a conflict, it is simply the most recent thing we were told.
# Case data (relationships/roles in ONE case) and application data (every other answer) are never globalised.
FACT_SCOPE = {
    "family_name": "stable", "given_name": "stable", "middle_name": "stable", "other_names": "stable", "date_of_birth": "stable", "sex": "stable",
    "birth_city": "stable", "birth_country": "stable", "nationality": "stable", "a_number": "stable", "uscis_account_number": "stable", "ssn": "stable",
    "parents": "stable",
    "phone_daytime": "situational", "phone_mobile": "situational", "email": "situational", "current_address": "situational",
    "address_history": "situational", "employment_history": "situational", "i94_number": "situational", "class_of_admission": "situational",
    "authorized_stay_type": "situational", "authorized_stay_expiry": "situational", "last_arrival_date": "situational",
}
for _k in FACTS:
    FACTS[_k]["scope"] = FACT_SCOPE.get(_k, "situational")
STALE_DAYS = 180  # a situational fact confirmed/provided longer ago than this is shown with "please check it is still current"


def scope_of(key):
    return FACTS.get(key, {}).get("scope", "situational")


def conflict_capable(key):
    """Only stable, scalar facts can be in conflict (a different address is just a newer address)."""
    return scope_of(key) == "stable" and FACTS.get(key, {}).get("kind") in ("text", "date", "choice")


# ---------------------------------------------------------------- semantic mappings added for cross-form reuse (explicit, never by label matching)
FORM_CASE_CONFIG["N-400"]["facts"]["applicant"].update({
    "nationality": "country_citizenship", "other_names": "other_names", "address_history": "residence_history",
    "current_address": {"record_present": "residence_history"}, "employment_history": "employment_history",
})
FORM_CASE_CONFIG["I-90"]["facts"]["applicant"].update({"current_address": {"address_prefix": "phys"}})

# ---------------------------------------------------------------- which case types an application may live in (data-driven)
FORM_CASE_CONFIG["I-90"]["case_types"] = ["green_card_renewal"]
FORM_CASE_CONFIG["N-400"]["case_types"] = ["naturalization"]
FORM_CASE_CONFIG["I-130"]["case_types"] = ["family_petition", "adjustment_of_status"]
FORM_CASE_CONFIG["I-485"]["case_types"] = ["adjustment_of_status"]


def compatible_case_types(form_name):
    """[case_type, ...] a form may be attached to, or None when the form is not part of the case architecture."""
    cfg = FORM_CASE_CONFIG.get(form_name)
    if cfg is None:
        return None
    return cfg.get("case_types") or [cfg["case_type"]]


def is_compatible(form_name, case_type):
    allowed = compatible_case_types(form_name)
    return allowed is None or case_type in allowed


# ---------------------------------------------------------------- Form I-864 (Affidavit of Support): its OWN application; sponsor and principal immigrant are REAL people
FORM_CASE_CONFIG["I-864"] = {
    "case_type": "adjustment_of_status",
    "case_types": ["adjustment_of_status", "family_petition"],
    "case_setup": True,
    "setup": "sponsor_principal",
    "people": [
        {"key": "sponsor", "who": "chosen", "names": ("s_given", "s_family"), "roles": ["sponsor"], "relationship_field": None,
         "extra_roles": [{"role": "joint_sponsor", "when": ("b_basis", "1d")}, {"role": "joint_sponsor", "when": ("b_basis", "1e")},
                         {"role": "substitute_sponsor", "when": ("b_basis", "1f")}]},
        {"key": "principal", "who": "chosen", "names": ("p_given", "p_family"), "roles": ["principal_immigrant"], "relationship_field": None},
    ],
    "record_people": [
        {"field": "i_family", "relationship": "other", "role": "sponsored_immigrant", "kind": "records", "given": "given", "family": "family", "a_number": "a_number", "dob": "dob", "person_link": "person_id", "match_core": True},
        {"field": "h_people", "relationship": "other", "role": "household_member", "kind": "records", "given": "given", "family": "family", "dob": "dob", "person_link": "person_id", "match_core": True},
        {"field": "inc_people", "relationship": "other", "role": "household_member", "kind": "records", "given": "given", "family": "family", "person_link": "person_id", "match_core": True},
    ],
    "facts": {
        "sponsor": {
            "family_name": "s_family", "given_name": "s_given", "middle_name": "s_middle", "date_of_birth": "s_dob", "birth_country": "s_birth_country", "ssn": "s_ssn",
            "a_number": "s_anumber", "uscis_account_number": "s_uscis", "current_address": {"address_prefix": "sp"},
            "phone_daytime": "s_phone", "phone_mobile": "s_mobile", "email": "s_email",
        },
        "principal": {
            "family_name": "p_family", "given_name": "p_given", "middle_name": "p_middle", "date_of_birth": "p_dob", "nationality": "p_citizenship",
            "a_number": "p_anumber", "uscis_account_number": "p_uscis", "phone_daytime": "p_phone",
        },
    },
    "blocks": {
        "sb_s_name": _blk("sponsor", {"family_name": "s_family", "given_name": "s_given", "middle_name": "s_middle"}, ["family_name", "given_name"]),
        "sb_s_birth": _blk("sponsor", {"date_of_birth": "s_dob", "birth_country": "s_birth_country"}, ["date_of_birth", "birth_country"]),
        "sb_s_ssn": _blk("sponsor", {"ssn": "s_ssn"}, ["ssn"]),
        "sb_s_ids": _blk("sponsor", {"a_number": "s_anumber", "uscis_account_number": "s_uscis"}, []),
        "sb_s_address": _blk("sponsor", {"current_address": {"address_prefix": "sp"}}, ["current_address"]),
        "sb_s_contact": _blk("sponsor", {"phone_daytime": "s_phone", "phone_mobile": "s_mobile", "email": "s_email"}, ["phone_daytime"]),
        "sb_p_name": _blk("principal_immigrant", {"family_name": "p_family", "given_name": "p_given", "middle_name": "p_middle"}, ["family_name", "given_name"]),
        "sb_p_birth": _blk("principal_immigrant", {"date_of_birth": "p_dob", "nationality": "p_citizenship"}, ["date_of_birth"]),
        "sb_p_ids": _blk("principal_immigrant", {"a_number": "p_anumber", "uscis_account_number": "p_uscis"}, []),
        "sb_p_phone": _blk("principal_immigrant", {"phone_daytime": "p_phone"}, ["phone_daytime"]),
    },
}


# ---------------------------------------------------------------- Form I-765 (Application for Employment Authorization): its OWN application; the applicant is a REAL person
FACTS.update({
    "birth_state": {"en": "State or province of birth", "es": "Estado o provincia de nacimiento", "kind": "text", "scope": "stable"},
    "marital_status": {"en": "Marital status", "es": "Estado civil", "kind": "choice", "scope": "situational",
                       "options": {"single": ("Single", "Soltero(a)"), "married": ("Married", "Casado(a)"), "divorced": ("Divorced", "Divorciado(a)"),
                                   "widowed": ("Widowed", "Viudo(a)"), "annulled": ("Marriage annulled", "Matrimonio anulado"), "separated": ("Legally separated", "Legalmente separado(a)")}},
    "arrival_place": {"en": "Place of last arrival", "es": "Lugar de la última llegada", "kind": "text", "scope": "situational"},
    "current_status": {"en": "Current immigration status or category", "es": "Estatus o categoría migratoria actual", "kind": "text", "scope": "situational"},
    "sevis_number": {"en": "SEVIS number", "es": "Número SEVIS", "kind": "text", "scope": "situational"},
    "passport_number": {"en": "Passport number (most recently issued passport)", "es": "Número de pasaporte (pasaporte emitido más recientemente)", "kind": "text", "scope": "situational", "sensitive": True},
    "travel_document_number": {"en": "Travel document number", "es": "Número del documento de viaje", "kind": "text", "scope": "situational", "sensitive": True},
    "document_country": {"en": "Country that issued the passport or travel document", "es": "País que emitió el pasaporte o documento de viaje", "kind": "text", "scope": "situational"},
    "document_expiry": {"en": "Passport or travel document expires", "es": "El pasaporte o documento de viaje vence", "kind": "date", "scope": "situational"},
    "arrival_document_number": {"en": "Passport or travel document number used at last arrival", "es": "Número del pasaporte o documento de viaje usado en la última llegada", "kind": "text", "scope": "situational", "sensitive": True},
    "arrival_document_country": {"en": "Country that issued the document used at last arrival", "es": "País que emitió el documento usado en la última llegada", "kind": "text", "scope": "situational"},
    "arrival_document_expiry": {"en": "Expiration of the document used at last arrival", "es": "Vencimiento del documento usado en la última llegada", "kind": "date", "scope": "situational"},
})
FACT_ORDER = list(FACTS)
# class of admission IS "Immigration Status at Your Last Arrival" (I-765 Item 24): one fact, relabelled where it is shown for this purpose only.

# Mappings from OTHER applications into the new facts (explicit; never by label matching). Application-specific meaning is preserved:
#   arrival_document_* = "passport OR travel document used at last arrival" (I-485 Item 10). It is NOT the same concept as the I-765
#   "most recently issued passport" (Item 18), so the I-765 shows it as context and the applicant says which document it is.
FORM_CASE_CONFIG["I-485"]["facts"]["applicant"].update({
    "arrival_place": {"compose": ["a_arr_city", "a_arr_state"], "sep": ", "},
    "current_status": "a_current_status",
    "arrival_document_number": "a_pp_number", "arrival_document_country": "a_pp_country", "arrival_document_expiry": "a_pp_expiry",
    "marital_status": "m_status",
})
FORM_CASE_CONFIG["N-400"]["facts"]["applicant"].update({"marital_status": "marital_status"})

FORM_CASE_CONFIG["I-765"] = {
    "case_type": "employment_authorization",
    "case_types": ["employment_authorization", "adjustment_of_status"],  # an I-765 has uses outside adjustment of status; it joins an AoS case only by explicit choice
    "case_setup": True,
    "allow_repeat_in_case": True,  # an initial and a later renewal I-765 may live in one case; only an UNFINISHED draft blocks another
    "people": [{"key": "applicant", "who": "chosen", "names": ("a_given", "a_family"), "roles": ["applicant"], "relationship_field": None}],
    "facts": {
        "applicant": {
            "family_name": "a_family", "given_name": "a_given", "middle_name": "a_middle", "other_names": "a_other_names", "date_of_birth": "a_dob", "sex": "a_sex",
            "birth_city": "a_birth_city", "birth_state": "a_birth_state", "birth_country": "a_birth_country", "nationality": "a_citizenship",
            "a_number": "a_anumber", "uscis_account_number": "a_uscis_account", "ssn": "a_ssn", "marital_status": "a_marital",
            "current_address": {"address_prefix": "ph"}, "i94_number": "a_i94_number", "class_of_admission": "a_arr_status", "last_arrival_date": "a_arr_date",
            "arrival_place": "a_arr_place", "current_status": "a_current_status", "sevis_number": "a_sevis",
            "passport_number": "a_passport", "travel_document_number": "a_travel_doc", "document_country": "a_doc_country", "document_expiry": "a_doc_expiry",
            "phone_daytime": "a_phone", "phone_mobile": "a_mobile", "email": "a_email",
        },
    },
    "blocks": {
        "sb_identity": _blk("applicant", {"family_name": "a_family", "given_name": "a_given", "middle_name": "a_middle", "date_of_birth": "a_dob", "sex": "a_sex",
                                          "birth_city": "a_birth_city", "birth_country": "a_birth_country", "nationality": "a_citizenship", "birth_state": "a_birth_state"},
                            ["family_name", "given_name", "date_of_birth"]),
        "sb_othernames": _blk("applicant", {"other_names": {"records": "a_other_names", "record": "other_name"}}, ["other_names"]),
        "sb_address": _blk("applicant", {"current_address": {"address_prefix": "ph"}}, ["current_address"], only={"current_address": "us"}),
        "sb_ids": _blk("applicant", {"a_number": "a_anumber", "uscis_account_number": "a_uscis_account", "ssn": "a_ssn"}, []),
        "sb_marital": _blk("applicant", {"marital_status": "a_marital"}, ["marital_status"], only={"marital_status": ("single", "married", "divorced", "widowed")}),
        "sb_arrival": _blk("applicant", {"i94_number": "a_i94_number", "last_arrival_date": "a_arr_date", "arrival_place": "a_arr_place", "class_of_admission": "a_arr_status",
                                         "current_status": "a_current_status"}, ["last_arrival_date"]),
        "sb_contact": _blk("applicant", {"phone_daytime": "a_phone", "phone_mobile": "a_mobile", "email": "a_email"}, ["phone_daytime"]),
        "sb_docs": _blk("applicant", {"passport_number": "a_passport", "travel_document_number": "a_travel_doc", "document_country": "a_doc_country", "document_expiry": "a_doc_expiry"}, []),
        # availability only (no review step): does another application state a passport OR travel document used at the last arrival?
        "sb_arrdoc": _blk("applicant", {"arrival_document_number": "x_arr_num", "arrival_document_country": "x_arr_country", "arrival_document_expiry": "x_arr_expiry"}, ["arrival_document_number"]),
    },
}
# The known "passport or travel document at last arrival" prefills the passport OR travel-document details ONLY after the applicant says which it is.
FORM_CASE_CONFIG["I-765"]["blocks"]["sb_identity"]["ask"] = ["sex", "birth_city", "birth_state", "birth_country", "nationality"]
FORM_CASE_CONFIG["I-765"]["blocks"]["sb_arrival"]["ask"] = ["last_arrival_date", "arrival_place", "class_of_admission", "current_status"]
FORM_CASE_CONFIG["I-765"]["blocks"]["sb_docs"]["prefill"] = {
    "choice_field": "d_kind", "source_block": "sb_arrdoc",
    "from": {"passport": {"passport_number": "arrival_document_number", "document_country": "arrival_document_country", "document_expiry": "arrival_document_expiry"},
             "travel_document": {"travel_document_number": "arrival_document_number", "document_country": "arrival_document_country", "document_expiry": "arrival_document_expiry"}},
}


# ---------------------------------------------------------------- Form I-751 (Petition to Remove Conditions on Residence): its OWN case type and application
FACTS.update({
    "ethnicity": {"en": "Ethnicity", "es": "Etnia", "kind": "choice", "scope": "situational",
                  "options": {"hispanic": ("Hispanic or Latino", "Hispano o Latino"), "not_hispanic": ("Not Hispanic or Latino", "No hispano ni latino")}},
    "race": {"en": "Race", "es": "Raza", "kind": "list", "scope": "situational",
             "options": {"american_indian": ("American Indian or Alaska Native", "Indígena americano o nativo de Alaska"), "asian": ("Asian", "Asiático"),
                         "black": ("Black or African American", "Negro o afroamericano"), "pacific_islander": ("Native Hawaiian or Other Pacific Islander", "Nativo de Hawái u otra isla del Pacífico"),
                         "white": ("White", "Blanco")}},
    "height_feet": {"en": "Height — feet", "es": "Estatura — pies", "kind": "text", "scope": "situational"},
    "height_inches": {"en": "Height — inches", "es": "Estatura — pulgadas", "kind": "text", "scope": "situational"},
    "weight_lbs": {"en": "Weight (pounds)", "es": "Peso (libras)", "kind": "text", "scope": "situational"},
    "eye_color": {"en": "Eye color", "es": "Color de ojos", "kind": "choice", "scope": "situational",
                  "options": {"BLK": ("Black", "Negros"), "BLU": ("Blue", "Azules"), "BRO": ("Brown", "Marrones"), "GRY": ("Gray", "Grises"), "GRN": ("Green", "Verdes"),
                              "HAZ": ("Hazel", "Color avellana"), "MAR": ("Maroon", "Granate"), "PNK": ("Pink", "Rosados"), "UNK": ("Unknown / Other", "Desconocido / Otro")}},
    "hair_color": {"en": "Hair color", "es": "Color de cabello", "kind": "choice", "scope": "situational",
                   "options": {"BAL": ("Bald (no hair)", "Calvo (sin cabello)"), "BLK": ("Black", "Negro"), "BLN": ("Blond", "Rubio"), "BRO": ("Brown", "Castaño"), "GRY": ("Gray", "Gris"),
                               "RED": ("Red", "Pelirrojo"), "SDY": ("Sandy", "Arena"), "WHI": ("White", "Blanco"), "UNK": ("Unknown / Other", "Desconocido / Otro")}},
})
FACT_ORDER = list(FACTS)
FORM_CASE_CONFIG["N-400"]["facts"]["applicant"].update({
    "ethnicity": "ethnicity", "race": "race", "height_feet": "height_feet", "height_inches": "height_inches", "weight_lbs": "weight_lbs", "eye_color": "eye_color", "hair_color": "hair_color",
})
FORM_CASE_CONFIG["I-485"]["facts"]["applicant"].update({
    "ethnicity": "a_ethnicity", "race": "a_race", "height_feet": "a_height_ft", "height_inches": "a_height_in", "weight_lbs": "a_weight", "eye_color": "a_eye", "hair_color": "a_hair",
})

FORM_CASE_CONFIG["I-751"] = {
    "case_type": "removal_of_conditions",
    "case_types": ["removal_of_conditions"],  # never an Adjustment of Status / Naturalization / Renewal case: a NEW matter, the same real people
    "case_setup": True,
    "setup": "resident_spouse",
    "allow_repeat_in_case": False,
    "setup_pair": {
        "first": {"role": "conditional_resident",
                  "title": {"en": "WHOSE CONDITIONAL RESIDENCE IS THIS PETITION ABOUT?", "es": "¿DE QUIÉN ES LA RESIDENCIA CONDICIONAL DE ESTA PETICIÓN?"},
                  "subtitle": {"en": "The person who holds conditional permanent resident status (the petitioner).", "es": "La persona que tiene la residencia permanente condicional (el peticionario)."}},
        "second": {"role": "relevant_individual",
                   "title": {"en": "WHO IS THE SPOUSE (OR PARENT'S SPOUSE)?", "es": "¿QUIÉN ES EL CÓNYUGE (O EL CÓNYUGE DEL PADRE O LA MADRE)?"},
                   "subtitle": {"en": "The U.S. citizen or lawful permanent resident spouse — or, for a child filing separately, the stepparent through whom conditional residence was gained (Part 4).",
                                "es": "El cónyuge ciudadano de EE. UU. o residente permanente legal — o, si un hijo presenta por separado, el padrastro o madrastra a través de quien obtuvo la residencia condicional (Parte 4)."}},
        "heading": {"en": "Who is this petition about?", "es": "¿De quién es esta petición?"},
        "intro": {"en": "Pick real people you already have so we do not ask for their information again — this is a new case, but the same people. Nobody gets a login by being listed.",
                  "es": "Elige a personas reales que ya tienes para no pedir su información otra vez: es un caso nuevo, pero son las mismas personas. Nadie recibe un acceso por aparecer aquí."},
        "dup": {"en": "There is already a petition for this conditional resident and spouse in this case, or an unfinished one.", "es": "Ya existe una petición para este residente condicional y cónyuge en este caso, o una sin terminar."},
        "completed_elsewhere_ok": True,
        "same": {"en": "The conditional resident and the spouse (or parent's spouse) must be two different people.", "es": "El residente condicional y el cónyuge (o cónyuge del padre o la madre) deben ser dos personas distintas."},
    },
    "people": [
        {"key": "resident", "who": "chosen", "names": ("r_given", "r_family"), "roles": ["conditional_resident"], "relationship_field": None},
        {"key": "relevant", "who": "chosen", "names": ("s_given", "s_family"), "roles": ["relevant_individual"], "relationship_field": None,
         "extra_roles": [{"role": "joint_petitioner", "when": ("b_route", "joint")}, {"role": "spouse", "when": ("c_p4_role", "spouse")},
                         {"role": "former_spouse", "when": ("c_p4_role", "former_spouse")}, {"role": "parent_spouse", "when": ("c_p4_role", "parent_spouse")}]},
    ],
    "record_people": [
        {"field": "k_children", "relationship": "child", "role": "child", "kind": "records", "given": "given", "family": "family", "a_number": "a_number", "dob": "dob", "person_link": "person_id", "match_core": True, "dob_match": True, "dob_claim": True},
    ],
    "facts": {
        "resident": {
            "family_name": "r_family", "given_name": "r_given", "middle_name": "r_middle", "other_names": "r_other_names", "date_of_birth": "r_dob", "birth_country": "r_birth_country",
            "nationality": "r_citizenship", "a_number": "r_anumber", "uscis_account_number": "r_uscis", "ssn": "r_ssn", "marital_status": "r_marital",
            "current_address": {"address_prefix": "ph"}, "address_history": "r_history", "phone_daytime": "r_phone", "phone_mobile": "r_mobile", "email": "r_email",
            "ethnicity": "r_ethnicity", "race": "r_race", "height_feet": "r_height_ft", "height_inches": "r_height_in", "weight_lbs": "r_weight", "eye_color": "r_eye", "hair_color": "r_hair",
        },
        "relevant": {
            "family_name": "s_family", "given_name": "s_given", "middle_name": "s_middle", "date_of_birth": "s_dob", "ssn": "s_ssn", "a_number": "s_anumber",
            "current_address": {"address_prefix": "sa"}, "phone_daytime": "s_phone", "phone_mobile": "s_mobile", "email": "s_email",
        },
    },
    "blocks": {
        "sb_identity": _blk("conditional_resident", {"family_name": "r_family", "given_name": "r_given", "middle_name": "r_middle", "date_of_birth": "r_dob", "birth_country": "r_birth_country",
                                                     "nationality": "r_citizenship"}, ["family_name", "given_name", "date_of_birth"]),
        "sb_othernames": _blk("conditional_resident", {"other_names": {"records": "r_other_names", "record": "other_name"}}, ["other_names"]),
        "sb_ids": _blk("conditional_resident", {"a_number": "r_anumber", "ssn": "r_ssn", "uscis_account_number": "r_uscis"}, []),
        "sb_marital": _blk("conditional_resident", {"marital_status": "r_marital"}, ["marital_status"], only={"marital_status": ("single", "married", "divorced", "widowed")}),
        "sb_address": _blk("conditional_resident", {"current_address": {"address_prefix": "ph"}}, ["current_address"], only={"current_address": "us"}),
        "sb_residence": _blk("conditional_resident", {"address_history": {"records": "r_history", "record": "address"}}, ["address_history"]),
        "sb_bio": _blk("conditional_resident", {"ethnicity": "r_ethnicity", "race": "r_race", "height_feet": "r_height_ft", "height_inches": "r_height_in", "weight_lbs": "r_weight",
                                                "eye_color": "r_eye", "hair_color": "r_hair"}, ["ethnicity"]),
        "sb_contact": _blk("conditional_resident", {"phone_daytime": "r_phone", "phone_mobile": "r_mobile", "email": "r_email"}, ["phone_daytime"]),
        "sb_s_name": _blk("relevant_individual", {"family_name": "s_family", "given_name": "s_given", "middle_name": "s_middle"}, ["family_name", "given_name"]),
        "sb_s_birth": _blk("relevant_individual", {"date_of_birth": "s_dob"}, ["date_of_birth"]),
        "sb_s_ids": _blk("relevant_individual", {"ssn": "s_ssn", "a_number": "s_anumber"}, []),
        "sb_s_address": _blk("relevant_individual", {"current_address": {"address_prefix": "sa"}}, ["current_address"]),
        "sb_s_contact": _blk("relevant_individual", {"phone_daytime": "s_phone", "phone_mobile": "s_mobile", "email": "s_email"}, ["phone_daytime"]),
    },
}
FORM_CASE_CONFIG["I-751"]["blocks"]["sb_identity"]["ask"] = ["birth_country", "nationality"]
FORM_CASE_CONFIG["I-751"]["blocks"]["sb_bio"]["ask"] = ["ethnicity", "race", "height_feet", "height_inches", "weight_lbs", "eye_color", "hair_color"]


# ---------------------------------------------------------------- Consular processing (Form DS-260, Department of State / CEAC)
CASE_TYPES["consular_processing"] = {"en": "Consular Processing", "es": "Procesamiento consular"}
ROLE_LABELS.update({
    "visa_applicant": {"en": "Immigrant visa applicant", "es": "Solicitante de visa de inmigrante"},
    "principal_applicant": {"en": "Principal applicant", "es": "Solicitante principal"},
    "derivative_applicant": {"en": "Derivative applicant", "es": "Solicitante derivado"},
})
FACTS.update({
    "native_name": {"en": "Full name in native alphabet", "es": "Nombre completo en alfabeto nativo", "kind": "text", "scope": "stable"},
    "passport_issue_date": {"en": "Passport issue date", "es": "Fecha de emisión del pasaporte", "kind": "date", "scope": "situational"},
})
FACT_ORDER = list(FACTS)
FORM_CASE_CONFIG["I-864"]["case_types"] = ["adjustment_of_status", "family_petition", "consular_processing"]  # an affidavit of support may live in a consular case

FORM_CASE_CONFIG["DS-260"] = {
    "case_type": "consular_processing",
    "case_types": ["consular_processing"],  # never an USCIS case; the underlying petition is LINKED, not moved
    "case_setup": True,
    "setup": "visa_applicant",
    "allow_repeat_in_case": False,
    "multi_draft": True,  # one DS-260 per visa applicant: several drafts may be open at once (never two for the same applicant in one case)
    "people": [
        {"key": "applicant", "who": "chosen", "names": ("a_given", "a_family"), "roles": ["visa_applicant"], "relationship_field": None,
         "extra_roles": [{"role": "principal_applicant", "when": ("ds_role", "principal")}, {"role": "derivative_applicant", "when": ("ds_role", "derivative")}]},
        {"key": "petitioner", "who": "chosen", "names": ("pt_given", "pt_family"), "roles": ["petitioner"], "relationship_field": None},
    ],
    "record_people": [
        {"field": "pf_records", "relationship": "parent", "role": "parent", "kind": "records", "given": "given", "family": "family", "dob": "dob", "person_link": "person_id", "match_core": True, "dob_match": True, "dob_claim": True},
        {"field": "pm_records", "relationship": "parent", "role": "parent", "kind": "records", "given": "given", "family": "family", "dob": "dob", "person_link": "person_id", "match_core": True, "dob_match": True, "dob_claim": True},
        {"field": "s_records", "relationship": "spouse", "role": "spouse", "kind": "records", "given": "given", "family": "family", "dob": "dob", "person_link": "person_id", "match_core": True, "dob_match": True, "dob_claim": True},
        {"field": "ps_records", "relationship": "other", "role": "former_spouse", "kind": "records", "given": "given", "family": "family", "dob": "dob", "person_link": "person_id", "match_core": True, "dob_match": True, "dob_claim": True},
        {"field": "k_children", "relationship": "child", "role": "child", "kind": "records", "given": "given", "family": "family", "dob": "dob", "person_link": "person_id", "match_core": True, "dob_match": True, "dob_claim": True},
    ],
    "facts": {
        "applicant": {
            "family_name": "a_family", "given_name": "a_given", "date_of_birth": "a_dob", "sex": "a_sex", "birth_city": "a_birth_city", "birth_state": "a_birth_state",
            "birth_country": "a_birth_country", "nationality": "a_nationality", "native_name": "a_native", "other_names": "a_other_names", "marital_status": "a_marital",
            "passport_number": "a_doc_number", "document_country": "a_doc_country", "passport_issue_date": "a_doc_issued", "document_expiry": "a_doc_expiry",
            "current_address": {"address_prefix": "pa"}, "address_history": "a_addr_history", "phone_daytime": "a_phone_primary", "phone_mobile": "a_phone_secondary", "email": "a_email",
        },
        "petitioner": {
            "family_name": "pt_family", "given_name": "pt_given", "current_address": {"address_prefix": "pta"}, "phone_daytime": "pt_phone", "phone_mobile": "pt_mobile", "email": "pt_email",
        },
    },
    "blocks": {
        "sb_identity": _blk("visa_applicant", {"family_name": "a_family", "given_name": "a_given", "date_of_birth": "a_dob", "sex": "a_sex", "birth_city": "a_birth_city", "birth_state": "a_birth_state",
                                               "birth_country": "a_birth_country", "nationality": "a_nationality", "native_name": "a_native"}, ["family_name", "given_name", "date_of_birth"]),
        "sb_othernames": _blk("visa_applicant", {"other_names": {"records": "a_other_names", "record": "other_name"}}, ["other_names"]),
        "sb_marital": _blk("visa_applicant", {"marital_status": "a_marital"}, ["marital_status"]),
        "sb_passport": _blk("visa_applicant", {"passport_number": "a_doc_number", "document_country": "a_doc_country", "passport_issue_date": "a_doc_issued", "document_expiry": "a_doc_expiry"}, ["passport_number"]),
        "sb_address": _blk("visa_applicant", {"current_address": {"address_prefix": "pa"}}, ["current_address"]),
        "sb_addr_history": _blk("visa_applicant", {"address_history": {"records": "a_addr_history", "record": "address"}}, ["address_history"]),
        "sb_contact": _blk("visa_applicant", {"phone_daytime": "a_phone_primary", "phone_mobile": "a_phone_secondary", "email": "a_email"}, ["phone_daytime"]),
        "sb_pt_name": _blk("petitioner", {"family_name": "pt_family", "given_name": "pt_given"}, ["family_name", "given_name"]),
        "sb_pt_address": _blk("petitioner", {"current_address": {"address_prefix": "pta"}}, ["current_address"]),
        "sb_pt_contact": _blk("petitioner", {"phone_daytime": "pt_phone", "phone_mobile": "pt_mobile", "email": "pt_email"}, ["phone_daytime"]),
    },
}
FORM_CASE_CONFIG["DS-260"]["blocks"]["sb_identity"]["ask"] = ["sex", "birth_city", "birth_country", "nationality"]


# ---------------------------------------------------------------- Tax & ITIN Services (Form W-7): ITIN Application case type; NOT an immigration case
CASE_TYPES["itin_application"] = {"en": "ITIN Application", "es": "Solicitud de ITIN"}
CASE_DOMAINS = {"itin_application": {"key": "tax_itin", "en": "Tax & ITIN Services", "es": "Servicios de impuestos e ITIN"}}
ROLE_LABELS.update({
    "itin_applicant": {"en": "ITIN applicant", "es": "Solicitante de ITIN"},
    "primary_taxpayer": {"en": "Primary taxpayer", "es": "Contribuyente principal"},
    "spouse_applicant": {"en": "Spouse (ITIN applicant)", "es": "Cónyuge (solicitante de ITIN)"},
    "dependent_applicant": {"en": "Dependent (ITIN applicant)", "es": "Dependiente (solicitante de ITIN)"},
    "taxpayer": {"en": "Taxpayer", "es": "Contribuyente"},
})
DOCUMENT_CATEGORIES.update({
    "w2": {"en": "W-2 wage statement", "es": "Formulario W-2"},
    "id_document": {"en": "Identification document", "es": "Documento de identificación"},
    "school_record": {"en": "School record", "es": "Registro escolar"},
    "medical_record": {"en": "Medical record", "es": "Registro médico"},
    "residency_proof": {"en": "Proof of U.S. residency", "es": "Prueba de residencia en EE. UU."},
    "visa_page": {"en": "U.S. visa page", "es": "Página de la visa de EE. UU."},
    "name_change": {"en": "Legal name change document", "es": "Documento de cambio de nombre legal"},
    "income_records": {"en": "Income records", "es": "Registros de ingresos"},
})


def domain_of(case_type, lang="en"):
    d = CASE_DOMAINS.get(case_type)
    return d[lang if lang in ("en", "es") else "en"] if d else None


FORM_CASE_CONFIG["W-7"] = {
    "case_type": "itin_application",
    "case_types": ["itin_application"],
    "case_setup": True,
    "setup": "itin_case",
    "allow_repeat_in_case": False,
    "multi_draft": True,  # one W-7 application per ITIN applicant Person
    "people": [
        {"key": "applicant", "who": "chosen", "names": ("a_given", "a_family"), "roles": ["itin_applicant"], "relationship_field": None,
         "extra_roles": [{"role": "primary_taxpayer", "when": ("w_kind", "primary")}, {"role": "spouse_applicant", "when": ("w_kind", "spouse")},
                         {"role": "dependent_applicant", "when": ("w_kind", "dependent")}]},
    ],
    "record_people": [],
    "facts": {
        "applicant": {
            "family_name": "a_family", "given_name": "a_given", "middle_name": "a_middle", "date_of_birth": "a_dob", "sex": "a_sex", "birth_city": "a_birth_city",
            "birth_country": "a_birth_country", "nationality": "a_nationality", "passport_number": "a_pp_number", "document_country": "a_pp_country",
            "passport_issue_date": "a_pp_issued", "document_expiry": "a_pp_expiry", "current_address": {"address_prefix": "ua"}, "phone_daytime": "a_phone", "email": "a_email",
            "last_arrival_date": "a_entry_date",
        },
    },
    "blocks": {
        "sb_identity": _blk("itin_applicant", {"family_name": "a_family", "given_name": "a_given", "middle_name": "a_middle", "date_of_birth": "a_dob", "sex": "a_sex",
                                               "birth_city": "a_birth_city", "birth_country": "a_birth_country", "nationality": "a_nationality"}, ["family_name", "given_name", "date_of_birth"]),
        "sb_address": _blk("itin_applicant", {"current_address": {"address_prefix": "ua"}}, ["current_address"], only={"current_address": "us"}),
        "sb_contact": _blk("itin_applicant", {"phone_daytime": "a_phone", "email": "a_email"}, ["phone_daytime"]),
        "sb_entry": _blk("itin_applicant", {"last_arrival_date": "a_entry_date"}, ["last_arrival_date"]),
    },
}


# ---------------------------------------------------------------- Tax & ITIN Services: Individual & Family Tax Return (a tax case is NOT an immigration case)
CASE_TYPES["tax_return"] = {"en": "Tax Return", "es": "Declaración de impuestos"}
CASE_DOMAINS["tax_return"] = {"key": "tax_itin", "en": "Tax & ITIN Services", "es": "Servicios de impuestos e ITIN"}
ROLE_LABELS.update({
    "tax_dependent": {"en": "Potential dependent", "es": "Posible dependiente"},
    "tax_spouse": {"en": "Spouse", "es": "Cónyuge"},
})
DOCUMENT_CATEGORIES.update({
    "tax_document": {"en": "Tax document", "es": "Documento de impuestos"},
    "tax_return_copy": {"en": "Prior-year tax return", "es": "Declaración del año anterior"},
    "expense_records": {"en": "Expense records", "es": "Registros de gastos"},
    "platform_summary": {"en": "Platform annual summary", "es": "Resumen anual de la plataforma"},
})

# ---------------------------------------------------------------- My Account redesign: group every immigration case type under one customer-facing domain
# (Tax Return / ITIN already share "tax_itin" above; this is the same additive CASE_DOMAINS dict, just more entries — nothing here changes a case's own case_type.)
CASE_DOMAINS.update({k: {"key": "immigration", "en": "Immigration", "es": "Inmigración"} for k in (
    "green_card_renewal", "naturalization", "family_petition", "adjustment_of_status",
    "employment_authorization", "removal_of_conditions", "consular_processing",
)})

# ---------------------------------------------------------------- NJ Driver License Assistance (its own domain; not tax/itin, not immigration)
CASE_TYPES["nj_driver_license"] = {"en": "NJ Driver License", "es": "Licencia de Conducir de NJ"}
CASE_DOMAINS["nj_driver_license"] = {"key": "nj_driver_license", "en": "NJ Driver License", "es": "Licencia de Conducir de NJ"}
DOCUMENT_CATEGORIES.update({
    "foreign_license": {"en": "Foreign driver license", "es": "Licencia de conducir extranjera"},
    "national_id": {"en": "National ID / Cédula", "es": "Identificación nacional / Cédula"},
    "nj_address_proof": {"en": "Proof of New Jersey address", "es": "Comprobante de dirección de Nueva Jersey"},
    "ssn_itin_document": {"en": "SSN / ITIN document", "es": "Documento de SSN / ITIN"},
})

# ---------------------------------------------------------------- General paid services without their own Smart Intake yet (OG Payments, 2026-09-22).
# Certified Translations, Notary, Apostille, Wedding Officiant, Document & Office Services: today these are a
# public "request a quote" Inquiry (app/blueprints/public/routes.py translation_quote), not a Case — building a
# full Smart Intake for each is explicitly out of scope for the payments task. When one of these needs a priced,
# payable record tied to the customer's account, Admin creates an ordinary Case of this type (the existing
# "+ New Case" action already supports an arbitrary case_type) and attaches a Charge to it — no new architecture.
CASE_TYPES["general_service"] = {"en": "OG Service", "es": "Servicio de OG"}
CASE_DOMAINS["general_service"] = {"key": "other", "en": "Other Services", "es": "Otros Servicios"}
