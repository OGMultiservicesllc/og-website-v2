"""Original default wording of the former "Flagship Page Text" blocks.

No longer an admin feature: that text now lives in the structured Services and
Website editors. This module is only the source the one-time content migration
(app/seed_content.py) reads, so nothing written before the change is lost.
"""

from app.models import PageBlock

# Registry of the former editable text blocks, grouped by the page they belonged to.
BLOCK_REGISTRY = {
    "translations_intro": {
        "group": "Translations Page",
        "label": "Intro text (left column, next to the quote form)",
        "default_en": (
            "We translate a wide range of personal and official documents — birth and "
            "marriage certificates, diplomas, legal and immigration paperwork, and more. "
            "While most requests are Spanish ↔ English, our team also handles French, "
            "Italian, Portuguese, and other languages upon request."
        ),
        "default_es": (
            "Traducimos una amplia variedad de documentos personales y oficiales — actas "
            "de nacimiento y matrimonio, diplomas, documentos legales y de inmigración, "
            "y más. Aunque la mayoría de las solicitudes son español ↔ inglés, "
            "nuestro equipo también maneja francés, italiano, portugués y otros idiomas "
            "bajo solicitud."
        ),
    },
    "translations_whatsapp_note": {
        "group": "Translations Page",
        "label": "WhatsApp callout (left column)",
        "default_en": "Prefer to talk it through? Message us on WhatsApp for faster, more direct service.",
        "default_es": "¿Prefieres hablarlo directamente? Escríbenos por WhatsApp para un servicio más rápido y directo.",
    },

    # ---------------------------------------------------------------- Services page
    "sv_title": {
        "group": "Other Services Page",
        "label": "Page title (H1)",
        "default_en": "Other Services",
        "default_es": "Otros Servicios",
    },
    "sv_subtitle": {
        "group": "Other Services Page",
        "label": "Page subtitle",
        "default_en": "Apostille assistance, wedding officiant services, and document & office services — in one place.",
        "default_es": "Asistencia con apostilla, servicios de oficiante de bodas y servicios de documentos y oficina — todo en un solo lugar.",
    },
    "sv_notary_title": {
        "group": "Notary Page",
        "label": "Title (H1)",
        "default_en": "Notary Public",
        "default_es": "Notaría Pública",
    },
    "sv_notary_body": {
        "group": "Notary Page",
        "label": "Subtitle / body",
        "default_en": "Acknowledgments, jurats, affidavits, sworn statements, powers of attorney, travel authorizations for minors, and general document notarization. Available in New Jersey, with corresponding services available in Texas.",
        "default_es": "Reconocimientos, juramentos, declaraciones juradas, poderes notariales, autorizaciones de viaje para menores y notarización general de documentos. Disponible en Nueva Jersey, con servicios correspondientes disponibles en Texas.",
    },
    "sv_notary_cta": {
        "group": "Notary Page",
        "label": "Button text",
        "default_en": "Contact / Visit Office",
        "default_es": "Contactar / Visitar Oficina",
    },
    "sv_apostille_title": {
        "group": "Apostille Page",
        "label": "Title (H1)",
        "default_en": "Apostille Assistance",
        "default_es": "Asistencia con Apostilla",
    },
    "sv_apostille_body": {
        "group": "Apostille Page",
        "label": "Subtitle / body",
        "default_en": "Help authenticating New Jersey state-issued and federal documents for use abroad, including document preparation, submission guidance, and certified translation if needed.",
        "default_es": "Ayuda para autenticar documentos emitidos por el estado de Nueva Jersey y documentos federales para su uso en el extranjero, incluyendo preparación de documentos, orientación para el envío y traducción certificada si es necesario.",
    },
    "sv_apostille_cta": {
        "group": "Apostille Page",
        "label": "Button text",
        "default_en": "Start My Apostille",
        "default_es": "Comenzar Mi Apostilla",
    },
    "sv_license_title": {
        "group": "NJ Driver License Page",
        "label": "Title (H1)",
        "default_en": "NJ Driver License Assistance",
        "default_es": "Asistencia con Licencia de Conducir NJ",
    },
    "sv_license_body": {
        "group": "NJ Driver License Page",
        "label": "Subtitle / body",
        "default_en": "Document checklist and 6-Points documentation guidance, foreign driver license documentation, certified translation of foreign licenses, and appointment guidance.",
        "default_es": "Lista de verificación de documentos y orientación sobre los 6 puntos, documentación de licencias extranjeras, traducción certificada de licencias extranjeras y orientación de citas.",
    },
    "sv_license_cta": {
        "group": "NJ Driver License Page",
        "label": "Button text",
        "default_en": "Get the Document Checklist",
        "default_es": "Obtener la Lista de Documentos",
    },
    "sv_officiant_title": {
        "group": "Wedding Officiant Page",
        "label": "Title (H1)",
        "default_en": "Wedding Officiant Services",
        "default_es": "Oficiante de Bodas",
    },
    "sv_officiant_body": {
        "group": "Wedding Officiant Page",
        "label": "Subtitle / body",
        "default_en": "A bilingual, licensed wedding officiant for your ceremony — intimate elopements, courthouse-style ceremonies, and full weddings, in English or Spanish.",
        "default_es": "Un oficiante de bodas bilingüe y con licencia para tu ceremonia — bodas íntimas, ceremonias estilo civil y bodas completas, en inglés o español.",
    },
    "sv_officiant_cta": {
        "group": "Wedding Officiant Page",
        "label": "Button text",
        "default_en": "Check Availability",
        "default_es": "Consultar Disponibilidad",
    },
    "sv_docs_title": {
        "group": "Document & Office Services Page",
        "label": "Title (H1)",
        "default_en": "Document & Office Services",
        "default_es": "Servicios de Documentos y Oficina",
    },
    "sv_docs_body": {
        "group": "Document & Office Services Page",
        "label": "Subtitle / body",
        "default_en": "Forms & administrative assistance (Medicaid, SNAP, Unemployment, NJ ANCHOR, and more), plus copies, fax, scan, email, passport-style photos, and printing.",
        "default_es": "Asistencia con formularios administrativos (Medicaid, SNAP, desempleo, NJ ANCHOR y más), además de copias, fax, escaneo, correo electrónico, fotos tipo pasaporte e impresión.",
    },
    "sv_docs_cta": {
        "group": "Document & Office Services Page",
        "label": "Button text",
        "default_en": "Visit Our Office",
        "default_es": "Visitar Nuestra Oficina",
    },

    # ---------------------------------------------------------------- Taxes & ITIN page
    "tx_title": {
        "group": "Taxes & ITIN Page",
        "label": "Page title (H1)",
        "default_en": "Taxes & ITIN",
        "default_es": "Impuestos e ITIN",
    },
    "tx_hero_subtitle": {
        "group": "Taxes & ITIN Page",
        "label": "Page subtitle",
        "default_en": "Tax preparation and ITIN/CAA services for individuals, families, self-employed, and small businesses.",
        "default_es": "Preparación de impuestos y servicios de ITIN/CAA para individuos, familias, trabajadores independientes y pequeños negocios.",
    },
    "tx_taxes_title": {
        "group": "Taxes & ITIN Page",
        "label": "Income Tax section — title",
        "default_en": "Income Tax Preparation",
        "default_es": "Preparación de Impuestos",
    },
    "tx_taxes_body": {
        "group": "Taxes & ITIN Page",
        "label": "Income Tax section — body",
        "default_en": "We prepare accurate tax returns for individuals, families, self-employed and independent contractors, 1099 / gig workers (Uber, Lyft, and similar), small businesses, and prior-year or amended returns.",
        "default_es": "Preparamos declaraciones de impuestos precisas para individuos, familias, trabajadores independientes y contratistas, trabajadores 1099 / gig (Uber, Lyft y similares), pequeños negocios, y declaraciones de años anteriores o enmendadas.",
    },
    "tx_itin_title": {
        "group": "Taxes & ITIN Page",
        "label": "ITIN/CAA section — title",
        "default_en": "ITIN / Certified Acceptance Agent (CAA)",
        "default_es": "ITIN / Agente Certificado de Aceptación (CAA)",
    },
    "tx_itin_body": {
        "group": "Taxes & ITIN Page",
        "label": "ITIN/CAA section — body",
        "default_en": "OG Multiservices is an IRS Certified Acceptance Agent, authorized to verify certain original documents as part of the ITIN application process — in most cases, without you having to mail your original passport to the IRS.",
        "default_es": "OG Multiservices es un Agente Certificado de Aceptación del IRS, autorizado para verificar ciertos documentos originales como parte del proceso de solicitud de ITIN — en la mayoría de los casos, sin que tengas que enviar tu pasaporte original al IRS.",
    },

    # ---------------------------------------------------------------- Immigration page
    "sv_immigration_title": {
        "group": "Immigration Page",
        "label": "Page title (H1)",
        "default_en": "Immigration Document Preparation & Assistance",
        "default_es": "Preparación y Asistencia de Documentos Migratorios",
    },
    "ig_hero_subtitle": {
        "group": "Immigration Page",
        "label": "Page subtitle",
        "default_en": "Document preparation and administrative support for common immigration processes — in English or Spanish.",
        "default_es": "Preparación de documentos y apoyo administrativo para trámites migratorios comunes — en inglés o español.",
    },
    "ig_service1_title": {
        "group": "Immigration Page",
        "label": "Service 1 — title",
        "default_en": "Consular Petitions",
        "default_es": "Peticiones Consulares",
    },
    "ig_service1_body": {
        "group": "Immigration Page",
        "label": "Service 1 — body",
        "default_en": "Help preparing family-based petitions and the supporting documentation for consular processing abroad.",
        "default_es": "Ayuda preparando peticiones familiares y la documentación de respaldo para el procesamiento consular en el extranjero.",
    },
    "ig_service2_title": {
        "group": "Immigration Page",
        "label": "Service 2 — title",
        "default_en": "Adjustment of Status",
        "default_es": "Ajustes de Estatus",
    },
    "ig_service2_body": {
        "group": "Immigration Page",
        "label": "Service 2 — body",
        "default_en": "Document preparation and checklist guidance for adjustment of status applications filed with USCIS.",
        "default_es": "Preparación de documentos y orientación con la lista de verificación para solicitudes de ajuste de estatus ante USCIS.",
    },
    "ig_service3_title": {
        "group": "Immigration Page",
        "label": "Service 3 — title",
        "default_en": "Green Card Renewal",
        "default_es": "Renovación de Residencia",
    },
    "ig_service3_body": {
        "group": "Immigration Page",
        "label": "Service 3 — body",
        "default_en": "Assistance preparing renewal or replacement paperwork for permanent resident cards.",
        "default_es": "Asistencia preparando los documentos para renovar o reemplazar la tarjeta de residente permanente (green card).",
    },
    "ig_service4_title": {
        "group": "Immigration Page",
        "label": "Service 4 — title",
        "default_en": "Citizenship / Naturalization",
        "default_es": "Ciudadanía / Naturalización",
    },
    "ig_service4_body": {
        "group": "Immigration Page",
        "label": "Service 4 — body",
        "default_en": "Application preparation and document checklist support for the naturalization process.",
        "default_es": "Preparación de la solicitud y apoyo con la lista de documentos para el proceso de naturalización.",
    },
    "ig_service5_title": {
        "group": "Immigration Page",
        "label": "Service 5 — title",
        "default_en": "Fiancé(e) Visa",
        "default_es": "Visa de Novios",
    },
    "ig_service5_body": {
        "group": "Immigration Page",
        "label": "Service 5 — body",
        "default_en": "Help organizing and preparing the paperwork for the K-1 fiancé(e) visa process.",
        "default_es": "Ayuda organizando y preparando los documentos para el proceso de visa de prometido(a) K-1.",
    },
}


def get_block(key, lang):
    entry = BLOCK_REGISTRY.get(key, {})
    default = entry.get(f"default_{lang}") or entry.get("default_en", "")
    block = PageBlock.query.filter_by(key=key).first()
    if not block:
        return default
    value = block.content_es if lang == "es" else block.content_en
    return value or default


def get_block_editable_value(key, lang):
    """Same as get_block, used by the admin form so it pre-fills with the
    current effective value (saved override, or the default if none yet)."""
    return get_block(key, lang)
