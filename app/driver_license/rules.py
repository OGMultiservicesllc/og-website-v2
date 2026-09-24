"""NJ MVC 6-Point ID Verification document rules — a centralized, versioned classification, never scattered through templates or branching code.

*** SOURCE NOTE (read before relying on this for a real customer decision) ***
No official NJ MVC document was supplied for this build. The document categories, typical point values and general "6 points, at least one
Primary document, plus NJ residency and SSN/ITIN-or-affidavit" structure below reflect NJ's long-standing, publicly known 6-Point ID Verification
program, transcribed from general knowledge, NOT from an official MVC PDF checked against this session. Values are marked UNVERIFIED and must be
confirmed by OG against the current official NJ MVC 6 Points of ID document before RULES_VERSION is treated as authoritative. Nothing here is ever
shown to the customer as a point count or a worksheet (see app/driver_license/summary.py) — the customer only ever sees "Good" / "Still needed" /
"OG will review". Admin sees the underlying classification for staff judgment, not as an automatic determination.

Recording `RULES_VERSION` on every `DlCaseData` (`rules_version` column, set when documents are (re)assessed) means a future correction to this
file does NOT silently rewrite the classification an already-submitted customer saw — see `service.snapshot_rules_version`.
"""

RULES_VERSION = "unverified-2026-09-24"
RULES_SOURCE = "General public knowledge of the NJ 6-Point ID Verification program (no official MVC document supplied this session) — NEEDS OG VERIFICATION."

# category: identity_primary (UNVERIFIED ~4 pts) | identity_secondary (UNVERIFIED ~1-3 pts) | nj_residence | ssn | itin | other
DOCUMENT_TYPES = {
    "passport": {"category": "identity_primary", "points": 4, "label_en": "Passport", "label_es": "Pasaporte", "translatable": False},
    "foreign_license": {"category": "identity_secondary", "points": 3, "label_en": "Driver License from your country", "label_es": "Licencia de conducir de tu país", "translatable": True, "og_review": True},
    "national_id": {"category": "identity_secondary", "points": 2, "label_en": "National ID / Cédula / DNI", "label_es": "Identificación nacional / Cédula / DNI", "translatable": True},
    "birth_certificate": {"category": "identity_secondary", "points": 3, "label_en": "Birth Certificate", "label_es": "Acta de Nacimiento", "translatable": True},
    "permanent_resident_card": {"category": "identity_primary", "points": 4, "label_en": "Permanent Resident Card", "label_es": "Tarjeta de Residente Permanente", "translatable": False},
    "ead_card": {"category": "identity_primary", "points": 4, "label_en": "Employment Authorization Document", "label_es": "Documento de Autorización de Empleo", "translatable": False},
    "ssn_doc": {"category": "ssn", "points": 0, "label_en": "Social Security documentation", "label_es": "Documentación de Seguro Social", "translatable": False},
    "itin_doc": {"category": "itin", "points": 0, "label_en": "ITIN documentation", "label_es": "Documentación de ITIN", "translatable": False},
    "nj_address_proof": {"category": "nj_residence", "points": 0, "label_en": "Proof of New Jersey address", "label_es": "Comprobante de dirección de Nueva Jersey", "translatable": False},
    "other": {"category": "other", "points": 0, "label_en": "Other document", "label_es": "Otro documento", "translatable": True},
}

# NJ residence proof categories (task lists these as the common OG-customer examples; the rules engine is not limited to only these)
NJ_ADDRESS_DOCS = (
    ("bank_statement", "Bank statement", "Estado de cuenta bancaria"),
    ("electric_bill", "Electric bill", "Factura de electricidad"),
    ("water_bill", "Water bill", "Factura de agua"),
    ("lease", "Lease / rental agreement", "Contrato de alquiler"),
    ("credit_card_statement", "Credit card statement", "Estado de cuenta de tarjeta de crédito"),
    ("government_mail", "Government mail", "Correo del gobierno"),
    ("insurance_document", "Insurance document", "Documento de seguro"),
    ("tax_document", "Tax document", "Documento de impuestos"),
    ("other", "Other", "Otro"),
    ("none", "I don't have one yet", "No tengo uno todavía"),
    ("unsure", "I'm not sure", "No estoy seguro"),
)

ITIN_EVIDENCE_DOCS = (
    ("itin_letter", "IRS ITIN letter", "Carta de ITIN del IRS"),
    ("other_irs_document", "Other IRS document", "Otro documento del IRS"),
    ("nj_tax_document", "NJ tax document", "Documento de impuestos de NJ"),
    ("other", "Other", "Otro"),
    ("unsure", "I'm not sure", "No estoy seguro"),
)

LANGUAGES = (("en", "English", "Inglés"), ("es", "Spanish", "Español"), ("pt", "Portuguese", "Portugués"), ("fr", "French", "Francés"), ("other", "Other", "Otro"))

MIN_POINTS_REQUIRED = 6  # UNVERIFIED — the customer never sees this number (see SOURCE NOTE)

# OG's preferred priority among the identity documents that need a translation — see PLAN_2026-09-22 correction,
# refined 2026-09-24: OG recommends translating AT MOST MAX_TRANSLATABLE_NEEDED documents, chosen strictly in
# this priority order among whichever of the three the customer actually selected — never a points/threshold
# calculation. A passport (or another PRIMARY_KEYS document) never takes one of these slots: it isn't
# translatable and lives in a completely separate loop below.
PRIORITY_TRANSLATABLE = ("foreign_license", "national_id", "birth_certificate")
MAX_TRANSLATABLE_NEEDED = 2
PRIMARY_KEYS = ("passport", "permanent_resident_card", "ead_card")  # non-translatable, 4 pts each — any ONE is enough


def document_label(key, lang):
    row = DOCUMENT_TYPES.get(key, DOCUMENT_TYPES["other"])
    return row["label_es"] if lang == "es" else row["label_en"]


def document_plan(selected_docs):
    """{doc_key: "needed" | "alternative"} for every selected identity document — the smallest useful combination,
    not a blanket "everything is required". Two independent rules, never points-based:
      - PRIMARY_KEYS: only the first present one is "needed" — a second primary document is a backup, not a
        second requirement.
      - PRIORITY_TRANSLATABLE: at most MAX_TRANSLATABLE_NEEDED are "needed", chosen strictly in OG's stated
        priority order (foreign license, then national ID, then birth certificate) among whichever the customer
        actually has — e.g. license+cédula+birth certificate selects license+cédula; license+birth certificate
        (no cédula) selects both of those. A primary document's presence never changes this selection.
    Everything past that point is "alternative": the customer HAS it and OG can still ask for it on review, but
    it is never sold a translation or shown as mandatory just because they happen to have it. Never a legal/MVC
    eligibility determination — see the module SOURCE NOTE; OG reviews the actual combination."""
    selected = list(dict.fromkeys(selected_docs))  # de-dup, keep order
    plan = {}
    for key in PRIMARY_KEYS:
        if key not in selected:
            continue
        if not any(v == "needed" for k, v in plan.items() if k in PRIMARY_KEYS):
            plan[key] = "needed"
        else:
            plan[key] = "alternative"
    translatable_needed = 0
    for key in PRIORITY_TRANSLATABLE:
        if key not in selected:
            continue
        if translatable_needed < MAX_TRANSLATABLE_NEEDED:
            plan[key] = "needed"
            translatable_needed += 1
        else:
            plan[key] = "alternative"
    for key in selected:
        if key not in plan and key not in ("other", "unsure"):
            plan[key] = "needed"
    return plan


def assess(selected_docs, ssn_itin_path, address_doc, foreign_license_valid=None):
    """Internal classification (Admin-facing only; the customer never sees this). `selected_docs` = list of DOCUMENT_TYPES keys the
    customer said they have. Returns a dict OG/Admin can read at a glance — never a green-light auto-decision for the affidavit or Road Test."""
    rows = [DOCUMENT_TYPES[d] for d in selected_docs if d in DOCUMENT_TYPES]
    points = sum(r["points"] for r in rows)
    has_primary = any(r["category"] == "identity_primary" for r in rows)
    flags = []
    if points < MIN_POINTS_REQUIRED or not has_primary:
        flags.append("identity_documents_incomplete")
    if not has_primary:
        flags.append("no_primary_identity_document")
    if address_doc in (None, "", "none", "unsure"):
        flags.append("nj_address_proof_needed")
    if ssn_itin_path == "neither":
        flags.append("affidavit_review_required")
    elif ssn_itin_path == "unsure":
        flags.append("ssn_itin_status_unclear")
    if "foreign_license" in selected_docs:
        flags.append("foreign_license_review")  # Road Test is NEVER auto-waived — see service.py / summary.py wording
        if foreign_license_valid == "no":
            flags.append("foreign_license_expired")
    return {
        "rules_version": RULES_VERSION, "points": points, "has_primary": has_primary,
        "meets_minimum": points >= MIN_POINTS_REQUIRED and has_primary, "flags": flags,
        "documents": [{"key": d, "category": DOCUMENT_TYPES[d]["category"], "points": DOCUMENT_TYPES[d]["points"]} for d in selected_docs if d in DOCUMENT_TYPES],
        "plan": document_plan(selected_docs),
    }
