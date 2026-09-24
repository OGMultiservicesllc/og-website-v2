"""Data-driven registry for the SEO subpages nested under each primary service
category (/services/certified-translations/<slug>, /services/taxes-itin/<slug>,
/services/immigration/<slug>, /services/notary/<slug>).

These are hand-built pages sharing one Jinja template (public/service_subpage.html)
— the same "hand-built flagship template" pattern already used by
translations.html/taxes_itin.html/immigration.html, just one level deeper. Content
lives here as plain Python data rather than admin-editable PageBlock/builder
content, matching the existing precedent of the structured lists already on those
flagship pages (tr_doc_*, tr_faq_*, etc. in app/i18n.py) — those are static too.

OG provides document preparation / immigration assistance, never legal
representation or guaranteed outcomes — copy here is worded accordingly (see
CLAUDE.md). No claims of universal acceptance by any institution.
"""

from flask import url_for


def _loc(en, es):
    return {"en": en, "es": es}


CATEGORY_META = {
    "certified-translations": {
        "endpoint": "public.translations",
        "subpage_endpoint": "public.translation_subpage",
        "title": _loc("Certified Translations", "Traducciones Certificadas"),
        "cta_endpoint": "public.translations",
        "cta_anchor": "#quote",
        "cta_label": _loc("Request a Quote", "Solicitar Cotización"),
    },
    "taxes-itin": {
        "endpoint": "public.taxes_itin",
        "subpage_endpoint": "public.taxes_subpage",
        "title": _loc("Taxes & ITIN", "Impuestos e ITIN"),
        "cta_endpoint": "public.contact",
        "cta_anchor": "",
        "cta_label": _loc("Start Tax Service", "Comenzar Servicio de Impuestos"),
    },
    "immigration": {
        "endpoint": "public.immigration",
        "subpage_endpoint": "public.immigration_subpage",
        "title": _loc("Immigration Services", "Servicios de Inmigración"),
        "cta_endpoint": "public.immigration",
        "cta_anchor": "#inquiry",
        "cta_label": _loc("Get Started", "Comenzar"),
    },
    "notary": {
        "endpoint": "public.notary",
        "subpage_endpoint": "public.notary_subpage",
        "title": _loc("Notary Services", "Servicios Notariales"),
        "cta_endpoint": "public.contact",
        "cta_anchor": "",
        "cta_label": _loc("Contact / Visit Office", "Contactar / Visitar Oficina"),
    },
    "apostille": {
        "endpoint": "public.apostille",
        "subpage_endpoint": "public.apostille_subpage",
        "title": _loc("Apostille Assistance", "Asistencia con Apostilla"),
        "cta_endpoint": "public.contact",
        "cta_anchor": "",
        "cta_label": _loc("Start My Apostille", "Comenzar Mi Apostilla"),
    },
    "document-office-services": {
        "endpoint": "public.document_office_services",
        "subpage_endpoint": "public.document_office_subpage",
        "title": _loc("Document & Office Services", "Servicios de Documentos y Oficina"),
        "cta_endpoint": "public.contact",
        "cta_anchor": "",
        "cta_label": _loc("Visit Our Office", "Visitar Nuestra Oficina"),
    },
}

_INCLUDED_TRANSLATION = [
    _loc("Complete translation of all visible text", "Traducción completa de todo el texto visible"),
    _loc(
        "Signed certification of translation accuracy",
        "Certificación firmada de exactitud de la traducción",
    ),
    _loc(
        "Digital PDF delivery, with pickup available",
        "Entrega digital en PDF, con opción de recogerla en persona",
    ),
    _loc("Confidential handling of your documents", "Manejo confidencial de tus documentos"),
]

SUBPAGES = {
    # ---------------------------------------------------------------- Certified Translations
    "certified-translations": [
        {
            "slug": "certified-birth-certificate-translation",
            "icon": "translations",
            "title": _loc(
                "Certified Birth Certificate Translation",
                "Traducción Certificada de Acta de Nacimiento",
            ),
            "meta_description": _loc(
                "Certified English translation of birth certificates for USCIS, schools, courts, and other institutions. Fast turnaround, digital delivery.",
                "Traducción certificada al inglés de actas de nacimiento para USCIS, escuelas, tribunales y otras instituciones. Entrega rápida y digital.",
            ),
            "hero_text": _loc(
                "Complete, certified translations of birth certificates for immigration applications, school enrollment, court proceedings, and other official uses across the United States.",
                "Traducciones completas y certificadas de actas de nacimiento para trámites migratorios, inscripción escolar, procesos judiciales y otros usos oficiales en Estados Unidos.",
            ),
            "what_is_title": _loc(
                "What is a certified birth certificate translation?",
                "¿Qué es una traducción certificada de acta de nacimiento?",
            ),
            "what_is_body": _loc(
                "A certified translation is a complete, word-for-word rendering of your birth certificate from its original language into English, accompanied by a signed statement attesting to its accuracy and the translator's competence. It is not a legal document itself — it accompanies the original certificate when submitted to an institution.",
                "Una traducción certificada es una versión completa y fiel de tu acta de nacimiento, del idioma original al inglés, acompañada de una declaración firmada que certifica su exactitud y la competencia del traductor. No es un documento legal en sí misma, sino que acompaña al acta original al presentarla ante una institución.",
            ),
            "when_needed": [
                _loc("USCIS and immigration applications", "Solicitudes de USCIS y trámites migratorios"),
                _loc("Passport applications", "Solicitudes de pasaporte"),
                _loc("School enrollment", "Inscripción escolar"),
                _loc("Court or legal matters", "Asuntos judiciales o legales"),
                _loc("DMV and government agencies", "El DMV y agencias gubernamentales"),
            ],
            "included": _INCLUDED_TRANSLATION,
            "faq": [
                {
                    "q": _loc(
                        "Will this translation be accepted by USCIS?",
                        "¿Esta traducción será aceptada por USCIS?",
                    ),
                    "a": _loc(
                        "Our certified translations are accepted by many institutions, including USCIS, schools, courts, and DMV requirements where applicable. Requirements can vary by institution, so confirm specific requirements with the receiving office if you're unsure.",
                        "Nuestras traducciones certificadas son aceptadas por muchas instituciones, incluyendo USCIS, escuelas, tribunales y los requisitos del DMV cuando aplica. Los requisitos pueden variar según la institución, así que te recomendamos confirmarlos con la oficina receptora si tienes dudas.",
                    ),
                },
                {
                    "q": _loc(
                        "How long does it take to get my translation?",
                        "¿Cuánto tiempo toma recibir mi traducción?",
                    ),
                    "a": _loc(
                        "Most birth certificate translations are completed within 1–2 business days. Rush service may be available — ask us on WhatsApp.",
                        "La mayoría de las traducciones de actas de nacimiento se completan en 1–2 días hábiles. Es posible que haya servicio urgente disponible — pregúntanos por WhatsApp.",
                    ),
                },
                {
                    "q": _loc("Do I need to send the original document?", "¿Necesito enviar el documento original?"),
                    "a": _loc(
                        "No — a clear photo or scan of your birth certificate is enough for us to prepare the translation.",
                        "No — una foto o escaneo claro de tu acta de nacimiento es suficiente para preparar la traducción.",
                    ),
                },
                {
                    "q": _loc("Is my information kept confidential?", "¿Mi información se mantiene confidencial?"),
                    "a": _loc(
                        "Yes. All documents you share with us are handled confidentially and are only used to prepare your translation.",
                        "Sí. Todos los documentos que compartes con nosotros se manejan de forma confidencial y solo se usan para preparar tu traducción.",
                    ),
                },
            ],
            "related": [
                "marriage-certificate-translation",
                "divorce-certificate-translation",
                "academic-transcript-translation",
                "driver-license-translation",
            ],
        },
        {
            "slug": "marriage-certificate-translation",
            "icon": "translations",
            "title": _loc(
                "Certified Marriage Certificate Translation",
                "Traducción Certificada de Acta de Matrimonio",
            ),
            "meta_description": _loc(
                "Certified English translation of marriage certificates for immigration petitions, benefits applications, and legal use.",
                "Traducción certificada al inglés de actas de matrimonio para peticiones migratorias, solicitudes de beneficios y uso legal.",
            ),
            "hero_text": _loc(
                "Accurate, certified translations of marriage certificates for immigration petitions, name changes, benefits applications, and other official processes.",
                "Traducciones certificadas y precisas de actas de matrimonio para peticiones migratorias, cambios de nombre, solicitudes de beneficios y otros trámites oficiales.",
            ),
            "what_is_title": _loc(
                "What is a certified marriage certificate translation?",
                "¿Qué es una traducción certificada de acta de matrimonio?",
            ),
            "what_is_body": _loc(
                "It's a complete English translation of your marriage certificate, paired with a signed certification of accuracy. It's typically submitted alongside the original document to the requesting institution.",
                "Es una traducción completa al inglés de tu acta de matrimonio, junto con una certificación firmada de exactitud. Normalmente se presenta junto con el documento original ante la institución que lo solicita.",
            ),
            "when_needed": [
                _loc("Family-based immigration petitions", "Peticiones migratorias familiares"),
                _loc("Name change requests", "Solicitudes de cambio de nombre"),
                _loc("Social Security or benefits applications", "Solicitudes del Seguro Social o beneficios"),
                _loc("School or employer records", "Registros escolares o laborales"),
                _loc("Court or legal proceedings", "Procesos judiciales o legales"),
            ],
            "included": _INCLUDED_TRANSLATION,
            "faq": [
                {
                    "q": _loc(
                        "Is this translation valid for USCIS immigration petitions?",
                        "¿Esta traducción es válida para peticiones migratorias de USCIS?",
                    ),
                    "a": _loc(
                        "Our certified translations are prepared to meet the format institutions like USCIS commonly request. Acceptance can vary by case, so confirm specific requirements with your attorney or the receiving agency if you have questions.",
                        "Nuestras traducciones certificadas se preparan según el formato que instituciones como USCIS suelen solicitar. La aceptación puede variar según el caso, así que confirma los requisitos específicos con tu abogado o la agencia receptora si tienes dudas.",
                    ),
                },
                {
                    "q": _loc(
                        "Can you translate a marriage certificate issued outside the U.S.?",
                        "¿Pueden traducir un acta de matrimonio emitida fuera de EE. UU.?",
                    ),
                    "a": _loc(
                        "Yes, we regularly translate marriage certificates issued in Spanish-speaking countries, as well as other languages upon request.",
                        "Sí, traducimos regularmente actas de matrimonio emitidas en países de habla hispana, así como en otros idiomas bajo solicitud.",
                    ),
                },
                {
                    "q": _loc("How fast can I get it done?", "¿Qué tan rápido puedo tenerla lista?"),
                    "a": _loc(
                        "Most marriage certificate translations are ready within 1–2 business days.",
                        "La mayoría de las traducciones de actas de matrimonio están listas en 1–2 días hábiles.",
                    ),
                },
                {
                    "q": _loc("Do you also translate divorce decrees?", "¿También traducen sentencias de divorcio?"),
                    "a": _loc(
                        "Yes — see our certified divorce decree translation service.",
                        "Sí — consulta nuestro servicio de traducción certificada de sentencias de divorcio.",
                    ),
                },
            ],
            "related": [
                "certified-birth-certificate-translation",
                "divorce-certificate-translation",
                "immigration-document-translation",
            ],
        },
        {
            "slug": "divorce-certificate-translation",
            "icon": "translations",
            "title": _loc(
                "Certified Divorce Decree Translation",
                "Traducción Certificada de Sentencia de Divorcio",
            ),
            "meta_description": _loc(
                "Certified English translation of divorce decrees for immigration, remarriage, and legal purposes.",
                "Traducción certificada al inglés de sentencias de divorcio para trámites migratorios, nuevo matrimonio y fines legales.",
            ),
            "hero_text": _loc(
                "Certified translations of divorce decrees and final judgments, prepared for immigration cases, remarriage, and court or agency requirements.",
                "Traducciones certificadas de sentencias de divorcio y resoluciones finales, preparadas para casos migratorios, nuevo matrimonio y requisitos de tribunales o agencias.",
            ),
            "what_is_title": _loc(
                "What is a certified divorce decree translation?",
                "¿Qué es una traducción certificada de sentencia de divorcio?",
            ),
            "what_is_body": _loc(
                "It's a full English translation of your divorce decree or final judgment, with a signed certification of accuracy attached, ready to submit alongside the original document.",
                "Es una traducción completa al inglés de tu sentencia de divorcio o resolución final, con una certificación firmada de exactitud adjunta, lista para presentarse junto con el documento original.",
            ),
            "when_needed": [
                _loc("Proving marital status for immigration cases", "Comprobar estado civil en casos migratorios"),
                _loc("Applying for a new marriage license", "Solicitar una nueva licencia de matrimonio"),
                _loc("Name change or benefits applications", "Cambio de nombre o solicitudes de beneficios"),
                _loc("Court or legal proceedings", "Procesos judiciales o legales"),
            ],
            "included": _INCLUDED_TRANSLATION,
            "faq": [
                {
                    "q": _loc(
                        "My decree has multiple pages — is everything translated?",
                        "Mi sentencia tiene varias páginas — ¿se traduce todo?",
                    ),
                    "a": _loc(
                        "Yes, we translate every page and every visible section of the document, including stamps and certifications on the original.",
                        "Sí, traducimos cada página y cada sección visible del documento, incluyendo sellos y certificaciones del original.",
                    ),
                },
                {
                    "q": _loc(
                        "Do you translate decrees issued in Latin American countries?",
                        "¿Traducen sentencias emitidas en países latinoamericanos?",
                    ),
                    "a": _loc(
                        "Yes, this is one of our most common requests, along with decrees in other languages upon request.",
                        "Sí, esta es una de nuestras solicitudes más comunes, además de sentencias en otros idiomas bajo pedido.",
                    ),
                },
                {
                    "q": _loc("How quickly can this be ready?", "¿Qué tan rápido puede estar lista?"),
                    "a": _loc(
                        "Most divorce decree translations are completed within 1–2 business days depending on document length.",
                        "La mayoría de las traducciones de sentencias de divorcio se completan en 1–2 días hábiles, según la extensión del documento.",
                    ),
                },
            ],
            "related": [
                "marriage-certificate-translation",
                "certified-birth-certificate-translation",
                "legal-document-translation",
            ],
        },
        {
            "slug": "academic-transcript-translation",
            "icon": "translations",
            "title": _loc(
                "Certified Academic Transcript Translation",
                "Traducción Certificada de Certificado de Notas / Kárdex",
            ),
            "meta_description": _loc(
                "Certified translation of academic transcripts for U.S. schools, universities, and credential evaluation services.",
                "Traducción certificada de certificados de notas para escuelas, universidades y servicios de evaluación de credenciales en EE. UU.",
            ),
            "hero_text": _loc(
                "Certified translations of academic transcripts and grade reports for school enrollment, university applications, and credential evaluation.",
                "Traducciones certificadas de certificados de notas y kárdex académicos para inscripción escolar, solicitudes universitarias y evaluación de credenciales.",
            ),
            "what_is_title": _loc(
                "What is a certified academic transcript translation?",
                "¿Qué es una traducción certificada de certificado de notas?",
            ),
            "what_is_body": _loc(
                "It's a complete English translation of your academic transcript — courses, grades, and grading scale included — with a signed certification of accuracy, formatted to be easy for admissions offices and evaluators to review.",
                "Es una traducción completa al inglés de tu certificado de notas — cursos, calificaciones y escala de calificación incluidos — con una certificación firmada de exactitud, presentada de forma clara para que oficinas de admisión y evaluadores puedan revisarla fácilmente.",
            ),
            "when_needed": [
                _loc("K-12 school enrollment", "Inscripción escolar (primaria y secundaria)"),
                _loc("College or university applications", "Solicitudes universitarias"),
                _loc("Credential evaluation services", "Servicios de evaluación de credenciales"),
                _loc("Employer or licensing requirements", "Requisitos de empleadores o licencias profesionales"),
            ],
            "included": _INCLUDED_TRANSLATION,
            "faq": [
                {
                    "q": _loc(
                        "Do you also translate the diploma that goes with the transcript?",
                        "¿También traducen el diploma que acompaña al certificado de notas?",
                    ),
                    "a": _loc(
                        "Yes — see our certified diploma translation service, or ask us to bundle both together.",
                        "Sí — consulta nuestro servicio de traducción certificada de diplomas, o pídenos que las combinemos en una sola entrega.",
                    ),
                },
                {
                    "q": _loc(
                        "Will a credential evaluation agency accept this?",
                        "¿Una agencia de evaluación de credenciales aceptará esta traducción?",
                    ),
                    "a": _loc(
                        "Our certified translations follow standard formatting accepted by many evaluation services and schools. Since requirements vary by agency, confirm the specific format they require before submitting.",
                        "Nuestras traducciones certificadas siguen un formato estándar aceptado por muchos servicios de evaluación y escuelas. Como los requisitos varían según la agencia, confirma el formato específico que solicitan antes de enviarla.",
                    ),
                },
                {
                    "q": _loc("How many pages can you handle?", "¿Cuántas páginas pueden traducir?"),
                    "a": _loc(
                        "Transcripts of any length are welcome — pricing and turnaround are based on document length and complexity.",
                        "Aceptamos certificados de notas de cualquier extensión — el precio y el tiempo de entrega dependen de la extensión y complejidad del documento.",
                    ),
                },
            ],
            "related": ["diploma-translation", "certified-birth-certificate-translation", "legal-document-translation"],
        },
        {
            "slug": "diploma-translation",
            "icon": "translations",
            "title": _loc("Certified Diploma Translation", "Traducción Certificada de Diploma"),
            "meta_description": _loc(
                "Certified English translation of diplomas and degrees for school, university, and employment purposes.",
                "Traducción certificada al inglés de diplomas y títulos para fines escolares, universitarios y laborales.",
            ),
            "hero_text": _loc(
                "Certified translations of high school diplomas, college and university degrees, and professional certificates.",
                "Traducciones certificadas de diplomas de secundaria, títulos universitarios y certificados profesionales.",
            ),
            "what_is_title": _loc(
                "What is a certified diploma translation?",
                "¿Qué es una traducción certificada de diploma?",
            ),
            "what_is_body": _loc(
                "It's a complete English translation of your diploma or degree, including seals, signatures, and issuing institution details described in text, paired with a signed certification of accuracy.",
                "Es una traducción completa al inglés de tu diploma o título, incluyendo sellos, firmas y los datos de la institución emisora descritos en texto, junto con una certificación firmada de exactitud.",
            ),
            "when_needed": [
                _loc("University or college applications", "Solicitudes universitarias"),
                _loc("Credential evaluation services", "Servicios de evaluación de credenciales"),
                _loc("Employer verification", "Verificación por parte de empleadores"),
                _loc("Professional licensing applications", "Solicitudes de licencias profesionales"),
            ],
            "included": _INCLUDED_TRANSLATION,
            "faq": [
                {
                    "q": _loc(
                        "Can you translate a diploma with a seal or watermark?",
                        "¿Pueden traducir un diploma con sello o marca de agua?",
                    ),
                    "a": _loc(
                        "Yes — we describe seals, stamps, and any handwritten elements in the translation, exactly as they appear on the original.",
                        "Sí — describimos sellos, timbres y cualquier elemento manuscrito en la traducción, tal como aparecen en el original.",
                    ),
                },
                {
                    "q": _loc(
                        "Should I order the transcript translation too?",
                        "¿Debería pedir también la traducción del certificado de notas?",
                    ),
                    "a": _loc(
                        "Most schools and evaluators ask for both the diploma and transcript together — we're happy to prepare them as one order.",
                        "La mayoría de las escuelas y evaluadores piden el diploma y el certificado de notas juntos — con gusto los preparamos como un solo pedido.",
                    ),
                },
                {
                    "q": _loc("How fast is turnaround?", "¿Cuál es el tiempo de entrega?"),
                    "a": _loc(
                        "Diplomas are usually translated within 1–2 business days.",
                        "Los diplomas normalmente se traducen en 1–2 días hábiles.",
                    ),
                },
            ],
            "related": ["academic-transcript-translation", "legal-document-translation"],
        },
        {
            "slug": "driver-license-translation",
            "icon": "translations",
            "title": _loc(
                "Certified Driver's License Translation",
                "Traducción Certificada de Licencia de Conducir",
            ),
            "meta_description": _loc(
                "Certified translation of a foreign driver's license for NJ MVC / DMV requirements and identification purposes.",
                "Traducción certificada de una licencia de conducir extranjera para requisitos del DMV/MVC de NJ y fines de identificación.",
            ),
            "hero_text": _loc(
                "Certified English translations of foreign driver's licenses, often used alongside our New Jersey driver license assistance service.",
                "Traducciones certificadas al inglés de licencias de conducir extranjeras, frecuentemente usadas junto con nuestro servicio de asistencia con la licencia de conducir de Nueva Jersey.",
            ),
            "what_is_title": _loc(
                "What is a certified driver's license translation?",
                "¿Qué es una traducción certificada de licencia de conducir?",
            ),
            "what_is_body": _loc(
                "It's a complete English translation of the information on a foreign driver's license, paired with a signed certification of accuracy — commonly requested as part of a 6-point identification document checklist.",
                "Es una traducción completa al inglés de la información en una licencia de conducir extranjera, junto con una certificación firmada de exactitud — comúnmente solicitada como parte de la lista de 6 puntos de identificación.",
            ),
            "when_needed": [
                _loc("New Jersey MVC 6-point ID verification", "Verificación de identidad de 6 puntos del MVC de NJ"),
                _loc("Applying for a new state driver's license", "Solicitar una nueva licencia de conducir estatal"),
                _loc("Insurance or rental car requirements", "Requisitos de seguros o alquiler de autos"),
                _loc("General identification purposes", "Fines generales de identificación"),
            ],
            "included": _INCLUDED_TRANSLATION,
            "faq": [
                {
                    "q": _loc(
                        "Does this replace the 6-point document checklist?",
                        "¿Esto reemplaza la lista de verificación de 6 puntos?",
                    ),
                    "a": _loc(
                        "No — the translation is one document you can use as part of that checklist. See our New Jersey Driver License Assistance service for the full checklist and guidance.",
                        "No — la traducción es un documento que puedes usar como parte de esa lista. Consulta nuestro servicio de Asistencia con la Licencia de Conducir de Nueva Jersey para la lista completa y orientación.",
                    ),
                },
                {
                    "q": _loc("Which countries' licenses do you translate?", "¿De qué países traducen licencias?"),
                    "a": _loc(
                        "We regularly translate licenses from Spanish-speaking countries and handle other languages upon request.",
                        "Traducimos regularmente licencias de países de habla hispana y manejamos otros idiomas bajo solicitud.",
                    ),
                },
                {
                    "q": _loc("How fast can I get it?", "¿Qué tan rápido puedo obtenerla?"),
                    "a": _loc(
                        "Driver's license translations are typically ready the same or next business day.",
                        "Las traducciones de licencias de conducir generalmente están listas el mismo día hábil o al siguiente.",
                    ),
                },
            ],
            "related": ["legal-document-translation", "certified-birth-certificate-translation"],
        },
        {
            "slug": "legal-document-translation",
            "icon": "translations",
            "title": _loc("Certified Legal Document Translation", "Traducción Certificada de Documentos Legales"),
            "meta_description": _loc(
                "Certified translation of contracts, powers of attorney, court filings, and other legal documents.",
                "Traducción certificada de contratos, poderes notariales, documentos judiciales y otros documentos legales.",
            ),
            "hero_text": _loc(
                "Certified translations of contracts, powers of attorney, affidavits, court filings, and other legal paperwork, prepared for use with courts, attorneys, and government agencies.",
                "Traducciones certificadas de contratos, poderes notariales, declaraciones juradas, documentos judiciales y otros papeles legales, preparadas para uso ante tribunales, abogados y agencias gubernamentales.",
            ),
            "what_is_title": _loc(
                "What is a certified legal document translation?",
                "¿Qué es una traducción certificada de un documento legal?",
            ),
            "what_is_body": _loc(
                "It's a complete, accurate English translation of a legal document, paired with a signed certification of accuracy. This service is document preparation only — we don't provide legal advice or representation; for legal questions about your document, consult an attorney.",
                "Es una traducción completa y precisa al inglés de un documento legal, junto con una certificación firmada de exactitud. Este servicio es solo de preparación de documentos — no ofrecemos asesoría legal ni representación; para preguntas legales sobre tu documento, consulta a un abogado.",
            ),
            "when_needed": [
                _loc("Contracts and agreements", "Contratos y acuerdos"),
                _loc("Powers of attorney", "Poderes notariales"),
                _loc("Court filings and affidavits", "Documentos judiciales y declaraciones juradas"),
                _loc("Business and corporate documents", "Documentos comerciales y corporativos"),
            ],
            "included": _INCLUDED_TRANSLATION,
            "faq": [
                {
                    "q": _loc(
                        "Can you translate documents with legal terminology?",
                        "¿Pueden traducir documentos con terminología legal?",
                    ),
                    "a": _loc(
                        "Yes, our team is experienced translating legal and official documents accurately, preserving their original meaning and structure.",
                        "Sí, nuestro equipo tiene experiencia traduciendo documentos legales y oficiales con precisión, preservando su significado y estructura original.",
                    ),
                },
                {
                    "q": _loc(
                        "Can you give me legal advice about my document?",
                        "¿Pueden darme asesoría legal sobre mi documento?",
                    ),
                    "a": _loc(
                        "No — we provide translation and document preparation only, not legal advice or representation. For legal questions, please consult a licensed attorney.",
                        "No — solo ofrecemos traducción y preparación de documentos, no asesoría legal ni representación. Para preguntas legales, consulta a un abogado con licencia.",
                    ),
                },
                {
                    "q": _loc("Is pricing based on page count?", "¿El precio se basa en el número de páginas?"),
                    "a": _loc(
                        "Yes, pricing depends on document length and complexity. Message us on WhatsApp with your document for a quote.",
                        "Sí, el precio depende de la extensión y complejidad del documento. Escríbenos por WhatsApp con tu documento para una cotización.",
                    ),
                },
            ],
            "related": ["immigration-document-translation", "divorce-certificate-translation"],
        },
        {
            "slug": "immigration-document-translation",
            "icon": "translations",
            "title": _loc(
                "Certified Immigration Document Translation",
                "Traducción Certificada de Documentos Migratorios",
            ),
            "meta_description": _loc(
                "Certified translation of passports, ID cards, and supporting documents for USCIS immigration applications.",
                "Traducción certificada de pasaportes, cédulas y documentos de respaldo para solicitudes migratorias ante USCIS.",
            ),
            "hero_text": _loc(
                "Certified translations of passports, national ID cards, police records, and other supporting documents commonly required for immigration applications.",
                "Traducciones certificadas de pasaportes, cédulas de identidad, antecedentes policiales y otros documentos de respaldo comúnmente requeridos en trámites migratorios.",
            ),
            "what_is_title": _loc(
                "What is a certified immigration document translation?",
                "¿Qué es una traducción certificada de un documento migratorio?",
            ),
            "what_is_body": _loc(
                "It's a complete English translation of a supporting document for your immigration case, paired with a signed certification of accuracy. We prepare the translation only — we don't file forms or provide legal representation.",
                "Es una traducción completa al inglés de un documento de respaldo para tu caso migratorio, junto con una certificación firmada de exactitud. Solo preparamos la traducción — no presentamos formularios ni ofrecemos representación legal.",
            ),
            "when_needed": [
                _loc("Family or employment-based petitions", "Peticiones familiares o de empleo"),
                _loc("Adjustment of status applications", "Solicitudes de ajuste de estatus"),
                _loc("Naturalization applications", "Solicitudes de naturalización"),
                _loc("Supporting evidence for any USCIS filing", "Evidencia de respaldo para cualquier trámite de USCIS"),
            ],
            "included": _INCLUDED_TRANSLATION,
            "faq": [
                {
                    "q": _loc(
                        "Which documents do you translate for immigration cases?",
                        "¿Qué documentos traducen para casos migratorios?",
                    ),
                    "a": _loc(
                        "Passports, national IDs, police clearance certificates, birth and marriage certificates, and most other supporting documents requested by USCIS.",
                        "Pasaportes, cédulas de identidad, certificados de antecedentes policiales, actas de nacimiento y matrimonio, y la mayoría de otros documentos de respaldo solicitados por USCIS.",
                    ),
                },
                {
                    "q": _loc(
                        "Can you help me fill out my immigration forms too?",
                        "¿Pueden ayudarme también a llenar mis formularios migratorios?",
                    ),
                    "a": _loc(
                        "Yes — see our immigration document preparation services for help organizing and preparing forms alongside your translations.",
                        "Sí — consulta nuestros servicios de preparación de documentos migratorios para ayuda organizando y preparando formularios junto con tus traducciones.",
                    ),
                },
                {
                    "q": _loc("How quickly can I get these done?", "¿Qué tan rápido pueden estar listos?"),
                    "a": _loc(
                        "Most documents are translated within 1–2 business days; message us on WhatsApp if your case has a deadline.",
                        "La mayoría de los documentos se traducen en 1–2 días hábiles; escríbenos por WhatsApp si tu caso tiene una fecha límite.",
                    ),
                },
            ],
            "related": [
                "certified-birth-certificate-translation",
                "marriage-certificate-translation",
                "legal-document-translation",
            ],
        },
    ],
    # ---------------------------------------------------------------- Taxes & ITIN
    "taxes-itin": [
        {
            "slug": "tax-preparation",
            "icon": "taxes",
            "title": _loc("Individual & Family Tax Preparation", "Preparación de Impuestos Individuales y Familiares"),
            "meta_description": _loc(
                "Personal income tax preparation and filing for individuals and families, in English or Spanish.",
                "Preparación y declaración de impuestos personales para individuos y familias, en inglés o español.",
            ),
            "hero_text": _loc(
                "Accurate, bilingual income tax preparation for individuals and families, including credits and deductions you may qualify for.",
                "Preparación de impuestos personales precisa y bilingüe para individuos y familias, incluyendo créditos y deducciones que podrías calificar.",
            ),
            "what_is_title": _loc("What's included in tax preparation?", "¿Qué incluye la preparación de impuestos?"),
            "what_is_body": _loc(
                "We review your income documents, identify credits and deductions you may qualify for, prepare your federal and state returns, and file electronically once you approve them.",
                "Revisamos tus documentos de ingresos, identificamos créditos y deducciones que podrías calificar, preparamos tus declaraciones federales y estatales, y las presentamos electrónicamente una vez que las apruebes.",
            ),
            "when_needed": [
                _loc("W-2 or 1099 income", "Ingresos por W-2 o 1099"),
                _loc("Self-employment or gig income", "Trabajo independiente o ingresos de plataformas"),
                _loc("Dependents and family tax credits", "Dependientes y créditos fiscales familiares"),
                _loc("Multiple states or part-year residency", "Varios estados o residencia parcial del año"),
            ],
            "included": [
                _loc("Review of your income and expense documents", "Revisión de tus documentos de ingresos y gastos"),
                _loc("Federal and state return preparation", "Preparación de declaraciones federales y estatales"),
                _loc("Electronic filing once you approve", "Presentación electrónica una vez que apruebes"),
                _loc("Guidance in English or Spanish", "Orientación en inglés o español"),
            ],
            "faq": [
                {
                    "q": _loc("What documents do I need to bring?", "¿Qué documentos necesito traer?"),
                    "a": _loc(
                        "Typically your ID, Social Security number or ITIN, W-2s/1099s, and any documents for deductions or credits (childcare, tuition, etc.). We'll confirm exactly what applies to your situation.",
                        "Generalmente tu identificación, número de Seguro Social o ITIN, formularios W-2/1099, y documentos para deducciones o créditos (cuidado infantil, matrícula, etc.). Confirmaremos exactamente lo que aplica a tu situación.",
                    ),
                },
                {
                    "q": _loc("Can you help if I don't have a Social Security number?", "¿Pueden ayudarme si no tengo número de Seguro Social?"),
                    "a": _loc(
                        "Yes — we're an IRS Certified Acceptance Agent and can help you apply for an ITIN alongside your tax return. See our ITIN application service.",
                        "Sí — somos un Agente Certificado de Aceptación del IRS y podemos ayudarte a solicitar un ITIN junto con tu declaración de impuestos. Consulta nuestro servicio de solicitud de ITIN.",
                    ),
                },
                {
                    "q": _loc("Do you offer remote service?", "¿Ofrecen servicio remoto?"),
                    "a": _loc(
                        "Yes, we serve clients both in person at our Paterson, NJ office and remotely nationwide.",
                        "Sí, atendemos a clientes tanto en persona en nuestra oficina en Paterson, NJ, como de forma remota en todo el país.",
                    ),
                },
            ],
            "related": ["itin-application", "business-tax-preparation"],
        },
        {
            "slug": "itin-application",
            "icon": "taxes",
            "title": _loc("ITIN Application (Certified Acceptance Agent)", "Solicitud de ITIN (Agente Certificado de Aceptación)"),
            "meta_description": _loc(
                "ITIN application and renewal assistance from an IRS Certified Acceptance Agent — no need to mail original documents.",
                "Asistencia con la solicitud y renovación de ITIN por un Agente Certificado de Aceptación del IRS — sin necesidad de enviar documentos originales por correo.",
            ),
            "hero_text": _loc(
                "As an IRS Certified Acceptance Agent (CAA), we verify your original identification documents in person and help you complete Form W-7 for a new or renewed ITIN.",
                "Como Agente Certificado de Aceptación (CAA) del IRS, verificamos tus documentos de identificación originales en persona y te ayudamos a completar el Formulario W-7 para un ITIN nuevo o renovado.",
            ),
            "what_is_title": _loc("What is an ITIN and why does it matter?", "¿Qué es un ITIN y por qué es importante?"),
            "what_is_body": _loc(
                "An Individual Taxpayer Identification Number (ITIN) is issued by the IRS to people who need to file a U.S. tax return but aren't eligible for a Social Security number. As a Certified Acceptance Agent, we can verify your original documents ourselves, so in most cases you don't need to mail your passport or ID to the IRS.",
                "Un Número de Identificación Personal del Contribuyente (ITIN) es emitido por el IRS para personas que necesitan presentar una declaración de impuestos de EE. UU. pero no califican para un número de Seguro Social. Como Agente Certificado de Aceptación, podemos verificar tus documentos originales nosotros mismos, por lo que en la mayoría de los casos no necesitas enviar tu pasaporte o identificación por correo al IRS.",
            ),
            "when_needed": [
                _loc("Filing a tax return without a Social Security number", "Presentar una declaración de impuestos sin número de Seguro Social"),
                _loc("Claiming a spouse or dependent on a tax return", "Reclamar a un cónyuge o dependiente en una declaración"),
                _loc("Renewing an expired ITIN", "Renovar un ITIN vencido"),
                _loc("Opening certain U.S. bank accounts", "Abrir ciertas cuentas bancarias en EE. UU."),
            ],
            "included": [
                _loc("In-person review of your original documents", "Revisión en persona de tus documentos originales"),
                _loc("Form W-7 preparation", "Preparación del Formulario W-7"),
                _loc("Submission guidance with your tax return", "Orientación para presentarlo junto con tu declaración"),
                _loc("Bilingual support throughout the process", "Apoyo bilingüe durante todo el proceso"),
            ],
            "faq": [
                {
                    "q": _loc("Do I need to mail my passport to the IRS?", "¿Necesito enviar mi pasaporte al IRS por correo?"),
                    "a": _loc(
                        "In most cases, no. As a Certified Acceptance Agent, we can verify your original documents in person and return them to you the same day.",
                        "En la mayoría de los casos, no. Como Agentes Certificados de Aceptación, podemos verificar tus documentos originales en persona y devolvértelos el mismo día.",
                    ),
                },
                {
                    "q": _loc("How long does it take to get an ITIN?", "¿Cuánto tiempo tarda en llegar un ITIN?"),
                    "a": _loc(
                        "The IRS typically takes several weeks to process an ITIN application once submitted. We'll let you know what to expect for your specific situation.",
                        "El IRS generalmente tarda varias semanas en procesar una solicitud de ITIN una vez presentada. Te informaremos qué esperar según tu situación específica.",
                    ),
                },
                {
                    "q": _loc("Can I apply for an ITIN without filing a tax return?", "¿Puedo solicitar un ITIN sin presentar una declaración de impuestos?"),
                    "a": _loc(
                        "In most cases an ITIN application must be submitted together with a tax return, though there are some exceptions. We'll help confirm what applies to you.",
                        "En la mayoría de los casos, la solicitud de ITIN debe presentarse junto con una declaración de impuestos, aunque existen algunas excepciones. Te ayudaremos a confirmar qué aplica en tu caso.",
                    ),
                },
            ],
            "related": ["tax-preparation", "business-tax-preparation"],
        },
        {
            "slug": "business-tax-preparation",
            "icon": "taxes",
            "title": _loc("Small Business Tax Preparation", "Preparación de Impuestos para Pequeños Negocios"),
            "meta_description": _loc(
                "Tax preparation for self-employed workers and small businesses, including Schedule C filings.",
                "Preparación de impuestos para trabajadores independientes y pequeños negocios, incluyendo declaraciones del Anexo C.",
            ),
            "hero_text": _loc(
                "Tax preparation for self-employed individuals, freelancers, and small businesses — organized, accurate, and filed on time.",
                "Preparación de impuestos para trabajadores independientes, freelancers y pequeños negocios — organizada, precisa y presentada a tiempo.",
            ),
            "what_is_title": _loc("What's included for small business owners?", "¿Qué incluye para dueños de pequeños negocios?"),
            "what_is_body": _loc(
                "We help you organize your business income and expenses, prepare your Schedule C or business return, and identify deductions you may qualify for as a self-employed worker or small business owner.",
                "Te ayudamos a organizar los ingresos y gastos de tu negocio, preparamos tu Anexo C o declaración empresarial, e identificamos deducciones que podrías calificar como trabajador independiente o dueño de un pequeño negocio.",
            ),
            "when_needed": [
                _loc("Self-employed or freelance income", "Ingresos independientes o de freelance"),
                _loc("Single-member LLCs and sole proprietorships", "LLCs de un solo miembro y negocios propios"),
                _loc("Business expense and deduction tracking", "Seguimiento de gastos y deducciones del negocio"),
                _loc("Quarterly estimated tax questions", "Preguntas sobre pagos trimestrales estimados"),
            ],
            "included": [
                _loc("Review of business income and expenses", "Revisión de ingresos y gastos del negocio"),
                _loc("Schedule C / business return preparation", "Preparación del Anexo C o declaración empresarial"),
                _loc("Deduction guidance specific to your business", "Orientación sobre deducciones específicas de tu negocio"),
                _loc("Bilingual, year-round support", "Apoyo bilingüe durante todo el año"),
            ],
            "faq": [
                {
                    "q": _loc("I don't have organized records — can you still help?", "No tengo mis registros organizados — ¿aún pueden ayudarme?"),
                    "a": _loc(
                        "Yes, we regularly help clients organize receipts and records as part of preparing their return.",
                        "Sí, ayudamos regularmente a clientes a organizar recibos y registros como parte de la preparación de su declaración.",
                    ),
                },
                {
                    "q": _loc("Do you help with quarterly estimated taxes?", "¿Ayudan con los pagos trimestrales estimados?"),
                    "a": _loc(
                        "Yes, we can help you estimate and plan for quarterly payments to avoid surprises at filing time.",
                        "Sí, podemos ayudarte a estimar y planificar los pagos trimestrales para evitar sorpresas al momento de presentar tu declaración.",
                    ),
                },
                {
                    "q": _loc("Can you help me get an ITIN for my business too?", "¿Pueden ayudarme a obtener un ITIN para mi negocio también?"),
                    "a": _loc(
                        "Yes — see our ITIN application service, which we often prepare alongside a business tax return.",
                        "Sí — consulta nuestro servicio de solicitud de ITIN, que frecuentemente preparamos junto con una declaración de impuestos de negocio.",
                    ),
                },
            ],
            "related": ["tax-preparation", "itin-application"],
        },
        {
            "slug": "gig-economy-tax-preparation",
            "icon": "taxes",
            "title": _loc(
                "Uber, Lyft & DoorDash Driver Tax Preparation",
                "Preparación de Impuestos para Conductores de Uber, Lyft y DoorDash",
            ),
            "meta_description": _loc(
                "Tax preparation for rideshare and delivery drivers — Uber, Lyft, DoorDash, Instacart, and similar platforms.",
                "Preparación de impuestos para conductores y repartidores de Uber, Lyft, DoorDash, Instacart y plataformas similares.",
            ),
            "hero_text": _loc(
                "Specialized tax preparation for rideshare and delivery drivers — we help you track mileage and expenses and file the 1099 forms these platforms send you.",
                "Preparación de impuestos especializada para conductores de plataformas de transporte y entrega — te ayudamos a llevar el registro de millaje y gastos, y a presentar los formularios 1099 que envían estas plataformas.",
            ),
            "what_is_title": _loc(
                "What's different about gig economy taxes?",
                "¿Qué es diferente en los impuestos de la economía gig?",
            ),
            "what_is_body": _loc(
                "Uber, Lyft, DoorDash, Instacart, and similar platforms classify drivers as independent contractors, not employees — no taxes are withheld from your pay, and you're responsible for self-employment tax. We help you organize your 1099-K/1099-NEC forms, mileage log, and deductible expenses (gas, phone, car maintenance, etc.) into an accurate return.",
                "Uber, Lyft, DoorDash, Instacart y plataformas similares clasifican a los conductores como contratistas independientes, no empleados — no se retienen impuestos de tu pago, y eres responsable del impuesto de trabajo independiente. Te ayudamos a organizar tus formularios 1099-K/1099-NEC, tu registro de millaje y tus gastos deducibles (gasolina, teléfono, mantenimiento del carro, etc.) en una declaración precisa.",
            ),
            "when_needed": [
                _loc("Driving for Uber, Lyft, or a similar rideshare app", "Manejar para Uber, Lyft o una app de transporte similar"),
                _loc("Delivering for DoorDash, Instacart, or Amazon Flex", "Repartir para DoorDash, Instacart o Amazon Flex"),
                _loc("Tracking mileage and vehicle expenses", "Llevar el registro de millaje y gastos del vehículo"),
                _loc("Making quarterly estimated tax payments", "Hacer pagos trimestrales estimados de impuestos"),
            ],
            "included": [
                _loc("Review of your 1099-K / 1099-NEC forms from each platform", "Revisión de tus formularios 1099-K / 1099-NEC de cada plataforma"),
                _loc("Mileage and vehicle expense deduction guidance", "Orientación sobre deducciones de millaje y gastos del vehículo"),
                _loc("Self-employment tax calculation", "Cálculo del impuesto de trabajo independiente"),
                _loc("Help planning quarterly estimated payments", "Ayuda planificando los pagos trimestrales estimados"),
            ],
            "faq": [
                {
                    "q": _loc("I drive for more than one app — is that a problem?", "Manejo para más de una aplicación — ¿es un problema?"),
                    "a": _loc(
                        "No, this is common. We combine income and expenses from all your platforms into one accurate return.",
                        "No, esto es común. Combinamos los ingresos y gastos de todas tus plataformas en una sola declaración precisa.",
                    ),
                },
                {
                    "q": _loc("I didn't track my mileage carefully — now what?", "No llevé un buen registro de mi millaje — ¿ahora qué?"),
                    "a": _loc(
                        "We'll help you reconstruct a reasonable estimate from your app trip history and other records, and talk about how to track it going forward.",
                        "Te ayudaremos a reconstruir un estimado razonable con el historial de viajes de tu app y otros registros, y te orientamos sobre cómo llevarlo de ahora en adelante.",
                    ),
                },
                {
                    "q": _loc("Do I need to make quarterly payments?", "¿Necesito hacer pagos trimestrales?"),
                    "a": _loc(
                        "Many gig drivers do, to avoid a penalty at filing time — we can help you estimate what to set aside.",
                        "Muchos conductores de plataformas sí, para evitar una multa al momento de presentar — podemos ayudarte a estimar cuánto apartar.",
                    ),
                },
            ],
            "related": ["tax-preparation", "business-tax-preparation", "tax-amendments"],
        },
        {
            "slug": "tax-amendments",
            "icon": "taxes",
            "title": _loc("Amended Tax Return Preparation", "Preparación de Declaraciones de Impuestos Enmendadas"),
            "meta_description": _loc(
                "Help correcting a previously filed tax return (Form 1040-X) — missed income, credits, or filing status errors.",
                "Ayuda para corregir una declaración de impuestos ya presentada (Formulario 1040-X) — ingresos no declarados, créditos o errores en el estado civil.",
            ),
            "hero_text": _loc(
                "If you need to correct a tax return you already filed — this year's or a prior year's — we help you prepare an amended return with the right documentation.",
                "Si necesitas corregir una declaración de impuestos que ya presentaste — de este año o de un año anterior — te ayudamos a preparar una declaración enmendada con la documentación correcta.",
            ),
            "what_is_title": _loc(
                "What is an amended return (Form 1040-X)?",
                "¿Qué es una declaración enmendada (Formulario 1040-X)?",
            ),
            "what_is_body": _loc(
                "Form 1040-X is used to correct a federal tax return after it's been filed — for example, income you forgot to report, a credit or deduction you missed, or an incorrect filing status or number of dependents. We review what changed and prepare the amendment with the supporting explanation the IRS requires.",
                "El Formulario 1040-X se usa para corregir una declaración de impuestos federal después de haberla presentado — por ejemplo, ingresos que olvidaste reportar, un crédito o deducción que no reclamaste, o un estado civil o número de dependientes incorrecto. Revisamos qué cambió y preparamos la enmienda con la explicación de respaldo que requiere el IRS.",
            ),
            "when_needed": [
                _loc("You received a late or corrected W-2 or 1099", "Recibiste un W-2 o 1099 tardío o corregido"),
                _loc("You forgot to claim a credit or deduction", "Olvidaste reclamar un crédito o deducción"),
                _loc("Your filing status or dependents were incorrect", "Tu estado civil o dependientes estaban incorrectos"),
                _loc("The IRS or state sent a notice about your return", "El IRS o el estado te envió un aviso sobre tu declaración"),
            ],
            "included": [
                _loc("Review of your originally filed return", "Revisión de tu declaración originalmente presentada"),
                _loc("Identification of what needs to be corrected", "Identificación de lo que necesita corregirse"),
                _loc("Form 1040-X preparation with supporting explanation", "Preparación del Formulario 1040-X con la explicación de respaldo"),
                _loc("Guidance on state amended return requirements, if applicable", "Orientación sobre requisitos de enmienda estatal, si aplica"),
            ],
            "faq": [
                {
                    "q": _loc("How long do I have to file an amended return?", "¿Cuánto tiempo tengo para presentar una declaración enmendada?"),
                    "a": _loc(
                        "The IRS generally allows amendments within 3 years of the original filing date — we can help you confirm your specific deadline.",
                        "El IRS generalmente permite enmiendas dentro de los 3 años posteriores a la fecha de presentación original — podemos ayudarte a confirmar tu fecha límite específica.",
                    ),
                },
                {
                    "q": _loc("Will amending my return trigger an audit?", "¿Enmendar mi declaración provocará una auditoría?"),
                    "a": _loc(
                        "Filing an accurate amendment is a normal, routine process and is not, by itself, a red flag for an audit.",
                        "Presentar una enmienda precisa es un proceso normal y rutinario, y por sí solo no es una señal de alerta para una auditoría.",
                    ),
                },
                {
                    "q": _loc("Didn't you prepare my original return? Can you still help?", "¿No prepararon ustedes mi declaración original? ¿Aún pueden ayudarme?"),
                    "a": _loc(
                        "Yes, we regularly prepare amendments for returns filed elsewhere — bring a copy of the original return and we'll take it from there.",
                        "Sí, preparamos regularmente enmiendas de declaraciones presentadas en otro lugar — trae una copia de la declaración original y nosotros continuamos desde ahí.",
                    ),
                },
            ],
            "related": ["tax-preparation", "gig-economy-tax-preparation"],
        },
    ],
    # ---------------------------------------------------------------- Immigration
    "immigration": [
        {
            "slug": "i-130-petition",
            "icon": "immigration",
            "title": _loc("Form I-130 Family Petition Preparation", "Preparación de la Petición Familiar I-130"),
            "meta_description": _loc(
                "Help organizing and preparing Form I-130 (Petition for Alien Relative) and its supporting documents.",
                "Ayuda organizando y preparando el Formulario I-130 (Petición para Familiar Extranjero) y sus documentos de respaldo.",
            ),
            "hero_text": _loc(
                "Document preparation support for Form I-130, filed by U.S. citizens and permanent residents to petition for an eligible family member.",
                "Apoyo en la preparación de documentos para el Formulario I-130, presentado por ciudadanos y residentes permanentes de EE. UU. para peticionar a un familiar elegible.",
            ),
            "what_is_title": _loc("What is Form I-130?", "¿Qué es el Formulario I-130?"),
            "what_is_body": _loc(
                "Form I-130 is filed with USCIS to establish a qualifying family relationship as the first step toward a relative's immigrant visa or green card. We help you organize the form and its supporting evidence — we don't provide legal advice or file as your attorney.",
                "El Formulario I-130 se presenta ante USCIS para establecer una relación familiar calificada como primer paso hacia la visa de inmigrante o green card de un familiar. Te ayudamos a organizar el formulario y su evidencia de respaldo — no ofrecemos asesoría legal ni actuamos como tu abogado.",
            ),
            "when_needed": [
                _loc("Petitioning for a spouse", "Peticionar a un cónyuge"),
                _loc("Petitioning for a parent or child", "Peticionar a un padre, madre o hijo/a"),
                _loc("Petitioning for a sibling", "Peticionar a un hermano/a"),
                _loc("Gathering evidence of the family relationship", "Reunir evidencia de la relación familiar"),
            ],
            "included": [
                _loc("Review of your eligibility documents", "Revisión de tus documentos de elegibilidad"),
                _loc("Form I-130 organization and preparation support", "Apoyo en la organización y preparación del Formulario I-130"),
                _loc("Guidance on required supporting evidence", "Orientación sobre la evidencia de respaldo requerida"),
                _loc("Certified translation of any foreign-language documents", "Traducción certificada de documentos en otro idioma"),
            ],
            "faq": [
                {
                    "q": _loc("Are you an immigration attorney?", "¿Son abogados de inmigración?"),
                    "a": _loc(
                        "No. We provide document preparation and organization support, not legal advice or representation. For legal questions about your case, consult a licensed immigration attorney.",
                        "No. Ofrecemos apoyo en la preparación y organización de documentos, no asesoría legal ni representación. Para preguntas legales sobre tu caso, consulta a un abogado de inmigración con licencia.",
                    ),
                },
                {
                    "q": _loc("What documents prove a family relationship?", "¿Qué documentos comprueban una relación familiar?"),
                    "a": _loc(
                        "This depends on the relationship — typically certified birth or marriage certificates, and sometimes additional evidence. We'll help you understand what's commonly requested.",
                        "Depende de la relación — normalmente actas de nacimiento o matrimonio certificadas, y a veces evidencia adicional. Te ayudamos a entender lo que comúnmente se solicita.",
                    ),
                },
                {
                    "q": _loc("Can you translate my documents too?", "¿También pueden traducir mis documentos?"),
                    "a": _loc(
                        "Yes — see our certified immigration document translation service.",
                        "Sí — consulta nuestro servicio de traducción certificada de documentos migratorios.",
                    ),
                },
            ],
            "related": ["adjustment-of-status", "naturalization-citizenship"],
        },
        {
            "slug": "adjustment-of-status",
            "icon": "immigration",
            "title": _loc("Adjustment of Status (Form I-485) Preparation", "Preparación de Ajuste de Estatus (Formulario I-485)"),
            "meta_description": _loc(
                "Document preparation support for adjustment of status (Form I-485) applications for permanent residency.",
                "Apoyo en la preparación de documentos para solicitudes de ajuste de estatus (Formulario I-485) hacia la residencia permanente.",
            ),
            "hero_text": _loc(
                "Support organizing and preparing the forms and supporting documents involved in an adjustment of status application.",
                "Apoyo organizando y preparando los formularios y documentos de respaldo involucrados en una solicitud de ajuste de estatus.",
            ),
            "what_is_title": _loc("What is adjustment of status?", "¿Qué es el ajuste de estatus?"),
            "what_is_body": _loc(
                "Adjustment of status is the process some individuals already in the U.S. can use to apply for permanent resident status (a green card) without leaving the country. We help organize the required forms and documents — we don't provide legal advice about eligibility or represent you before USCIS.",
                "El ajuste de estatus es el proceso que algunas personas que ya están en EE. UU. pueden usar para solicitar la residencia permanente (green card) sin salir del país. Te ayudamos a organizar los formularios y documentos requeridos — no ofrecemos asesoría legal sobre elegibilidad ni te representamos ante USCIS.",
            ),
            "when_needed": [
                _loc("An approved family or employment petition", "Una petición familiar o de empleo aprobada"),
                _loc("Preparing Form I-485 and supporting forms", "Preparar el Formulario I-485 y formularios de apoyo"),
                _loc("Organizing medical exam and civil documents", "Organizar el examen médico y documentos civiles"),
                _loc("Preparing for biometrics and interview appointments", "Prepararse para citas biométricas y de entrevista"),
            ],
            "included": [
                _loc("Review of your document checklist", "Revisión de tu lista de documentos"),
                _loc("Form I-485 organization and preparation support", "Apoyo en la organización y preparación del Formulario I-485"),
                _loc("Guidance on commonly required supporting evidence", "Orientación sobre evidencia de respaldo comúnmente requerida"),
                _loc("Certified translation of any foreign-language documents", "Traducción certificada de documentos en otro idioma"),
            ],
            "faq": [
                {
                    "q": _loc("Can you tell me if I'm eligible to adjust status?", "¿Pueden decirme si soy elegible para ajustar mi estatus?"),
                    "a": _loc(
                        "Eligibility questions are legal in nature — we recommend consulting a licensed immigration attorney for that determination. We can help once you're ready to organize your paperwork.",
                        "Las preguntas de elegibilidad son de naturaleza legal — recomendamos consultar a un abogado de inmigración con licencia para esa determinación. Podemos ayudarte una vez que estés listo para organizar tu papeleo.",
                    ),
                },
                {
                    "q": _loc("Do you fill out the forms for me?", "¿Llenan los formularios por mí?"),
                    "a": _loc(
                        "We help you organize your information and prepare the forms accurately based on what you provide — the final application remains your responsibility to review and sign.",
                        "Te ayudamos a organizar tu información y preparar los formularios con precisión según lo que proporciones — la solicitud final sigue siendo tu responsabilidad revisarla y firmarla.",
                    ),
                },
                {
                    "q": _loc("Can you translate my supporting documents?", "¿Pueden traducir mis documentos de respaldo?"),
                    "a": _loc(
                        "Yes — see our certified immigration document translation service.",
                        "Sí — consulta nuestro servicio de traducción certificada de documentos migratorios.",
                    ),
                },
            ],
            "related": ["i-130-petition", "green-card-renewal"],
        },
        {
            "slug": "naturalization-citizenship",
            "icon": "immigration",
            "title": _loc("Naturalization (Form N-400) Preparation", "Preparación de Naturalización (Formulario N-400)"),
            "meta_description": _loc(
                "Document preparation support for U.S. citizenship applications (Form N-400).",
                "Apoyo en la preparación de documentos para solicitudes de ciudadanía estadounidense (Formulario N-400).",
            ),
            "hero_text": _loc(
                "Support organizing your Form N-400 application and supporting documents on your path to U.S. citizenship.",
                "Apoyo organizando tu solicitud del Formulario N-400 y documentos de respaldo en tu camino hacia la ciudadanía estadounidense.",
            ),
            "what_is_title": _loc("What is Form N-400?", "¿Qué es el Formulario N-400?"),
            "what_is_body": _loc(
                "Form N-400 is the application permanent residents file with USCIS to become U.S. citizens. We help you organize your residency history, documents, and the application itself — we don't provide legal advice about eligibility.",
                "El Formulario N-400 es la solicitud que los residentes permanentes presentan ante USCIS para convertirse en ciudadanos estadounidenses. Te ayudamos a organizar tu historial de residencia, documentos y la solicitud misma — no ofrecemos asesoría legal sobre elegibilidad.",
            ),
            "when_needed": [
                _loc("Meeting permanent residency time requirements", "Cumplir con los requisitos de tiempo de residencia permanente"),
                _loc("Organizing travel and residency history", "Organizar el historial de viajes y residencia"),
                _loc("Preparing supporting documents for your application", "Preparar documentos de respaldo para tu solicitud"),
                _loc("Preparing for the civics and English interview", "Prepararte para la entrevista de cívica e inglés"),
            ],
            "included": [
                _loc("Review of your residency and travel history", "Revisión de tu historial de residencia y viajes"),
                _loc("Form N-400 organization and preparation support", "Apoyo en la organización y preparación del Formulario N-400"),
                _loc("Document checklist guidance", "Orientación sobre la lista de documentos"),
                _loc("Certified translation of any foreign-language documents", "Traducción certificada de documentos en otro idioma"),
            ],
            "faq": [
                {
                    "q": _loc("How long do I need to have my green card first?", "¿Cuánto tiempo necesito tener mi green card primero?"),
                    "a": _loc(
                        "Time requirements depend on your specific situation. This is a legal eligibility question — we recommend confirming details with a licensed immigration attorney.",
                        "Los requisitos de tiempo dependen de tu situación específica. Esta es una pregunta de elegibilidad legal — recomendamos confirmar los detalles con un abogado de inmigración con licencia.",
                    ),
                },
                {
                    "q": _loc("Can you help me study for the citizenship test?", "¿Pueden ayudarme a estudiar para el examen de ciudadanía?"),
                    "a": _loc(
                        "We focus on document preparation, but can point you to study resources for the civics and English portions of the interview.",
                        "Nos enfocamos en la preparación de documentos, pero podemos guiarte hacia recursos de estudio para las partes de cívica e inglés de la entrevista.",
                    ),
                },
                {
                    "q": _loc("Do you offer this service in Spanish?", "¿Ofrecen este servicio en español?"),
                    "a": _loc(
                        "Yes, our team works with you fully in English or Spanish.",
                        "Sí, nuestro equipo trabaja contigo completamente en inglés o español.",
                    ),
                },
            ],
            "related": ["adjustment-of-status", "green-card-renewal"],
        },
        {
            "slug": "work-permit-renewal",
            "icon": "immigration",
            "title": _loc("Work Permit (EAD) Renewal Preparation", "Preparación de Renovación de Permiso de Trabajo (EAD)"),
            "meta_description": _loc(
                "Help preparing Form I-765 to renew your Employment Authorization Document (work permit).",
                "Ayuda preparando el Formulario I-765 para renovar tu Documento de Autorización de Empleo (permiso de trabajo).",
            ),
            "hero_text": _loc(
                "Document preparation support for renewing your Employment Authorization Document (EAD / work permit) before it expires.",
                "Apoyo en la preparación de documentos para renovar tu Documento de Autorización de Empleo (EAD / permiso de trabajo) antes de que venza.",
            ),
            "what_is_title": _loc("What is Form I-765?", "¿Qué es el Formulario I-765?"),
            "what_is_body": _loc(
                "Form I-765 is used to apply for or renew an Employment Authorization Document. We help you organize the form and supporting documents so your renewal is submitted with everything USCIS typically requests.",
                "El Formulario I-765 se usa para solicitar o renovar un Documento de Autorización de Empleo. Te ayudamos a organizar el formulario y los documentos de respaldo para que tu renovación se presente con todo lo que USCIS suele solicitar.",
            ),
            "when_needed": [
                _loc("Your current work permit is approaching expiration", "Tu permiso de trabajo actual está por vencer"),
                _loc("Renewing based on a pending adjustment of status case", "Renovar con base en un caso de ajuste de estatus pendiente"),
                _loc("Renewing based on an existing eligibility category", "Renovar con base en una categoría de elegibilidad existente"),
                _loc("Updating personal information on your EAD", "Actualizar información personal en tu EAD"),
            ],
            "included": [
                _loc("Review of your current work permit and eligibility category", "Revisión de tu permiso de trabajo actual y categoría de elegibilidad"),
                _loc("Form I-765 organization and preparation support", "Apoyo en la organización y preparación del Formulario I-765"),
                _loc("Guidance on required supporting documents", "Orientación sobre documentos de respaldo requeridos"),
                _loc("Certified translation of any foreign-language documents", "Traducción certificada de documentos en otro idioma"),
            ],
            "faq": [
                {
                    "q": _loc("When should I start my renewal?", "¿Cuándo debo comenzar mi renovación?"),
                    "a": _loc(
                        "USCIS generally recommends starting a renewal several months before your current work permit expires — we can help you organize your documents as soon as you're ready.",
                        "USCIS generalmente recomienda comenzar una renovación varios meses antes de que venza tu permiso de trabajo actual — podemos ayudarte a organizar tus documentos tan pronto como estés listo.",
                    ),
                },
                {
                    "q": _loc("Can I keep working while my renewal is pending?", "¿Puedo seguir trabajando mientras mi renovación está pendiente?"),
                    "a": _loc(
                        "This depends on your eligibility category and current rules — we recommend confirming your specific situation with a licensed immigration attorney.",
                        "Esto depende de tu categoría de elegibilidad y las reglas vigentes — recomendamos confirmar tu situación específica con un abogado de inmigración con licencia.",
                    ),
                },
                {
                    "q": _loc("What if my address or name changed?", "¿Qué pasa si cambió mi dirección o nombre?"),
                    "a": _loc(
                        "Let us know — we'll help make sure your renewal reflects your current information correctly.",
                        "Avísanos — te ayudaremos a asegurarnos de que tu renovación refleje correctamente tu información actual.",
                    ),
                },
            ],
            "related": ["green-card-renewal", "adjustment-of-status"],
        },
        {
            "slug": "green-card-renewal",
            "icon": "immigration",
            "title": _loc("Green Card Renewal Preparation", "Preparación de Renovación de Green Card"),
            "meta_description": _loc(
                "Help preparing Form I-90 to renew or replace your Permanent Resident Card (green card).",
                "Ayuda preparando el Formulario I-90 para renovar o reemplazar tu Tarjeta de Residente Permanente (green card).",
            ),
            "hero_text": _loc(
                "Document preparation support for renewing or replacing your Permanent Resident Card before or after it expires.",
                "Apoyo en la preparación de documentos para renovar o reemplazar tu Tarjeta de Residente Permanente antes o después de que venza.",
            ),
            "what_is_title": _loc("What is Form I-90?", "¿Qué es el Formulario I-90?"),
            "what_is_body": _loc(
                "Form I-90 is used to renew an expiring green card or replace one that was lost, stolen, or damaged. We help you organize the form and supporting documents for submission.",
                "El Formulario I-90 se usa para renovar una green card que está por vencer o reemplazar una que se perdió, fue robada o dañada. Te ayudamos a organizar el formulario y los documentos de respaldo para su presentación.",
            ),
            "when_needed": [
                _loc("Your green card is expiring within 6 months", "Tu green card vence dentro de los próximos 6 meses"),
                _loc("Your green card was already expired", "Tu green card ya venció"),
                _loc("Your card was lost, stolen, or damaged", "Tu tarjeta se perdió, fue robada o dañada"),
                _loc("Your name or other information needs correcting", "Tu nombre u otra información necesita corregirse"),
            ],
            "included": [
                _loc("Review of your current card and situation", "Revisión de tu tarjeta actual y situación"),
                _loc("Form I-90 organization and preparation support", "Apoyo en la organización y preparación del Formulario I-90"),
                _loc("Guidance on required supporting documents", "Orientación sobre documentos de respaldo requeridos"),
                _loc("Certified translation of any foreign-language documents", "Traducción certificada de documentos en otro idioma"),
            ],
            "faq": [
                {
                    "q": _loc("My card already expired — can I still renew?", "Mi tarjeta ya venció — ¿aún puedo renovarla?"),
                    "a": _loc(
                        "Yes, Form I-90 is used both for renewals before expiration and for replacing an already-expired card.",
                        "Sí, el Formulario I-90 se usa tanto para renovaciones antes del vencimiento como para reemplazar una tarjeta ya vencida.",
                    ),
                },
                {
                    "q": _loc("What if my card was stolen?", "¿Qué pasa si robaron mi tarjeta?"),
                    "a": _loc(
                        "We can help you prepare Form I-90 to request a replacement — let us know the details of your situation.",
                        "Podemos ayudarte a preparar el Formulario I-90 para solicitar un reemplazo — cuéntanos los detalles de tu situación.",
                    ),
                },
                {
                    "q": _loc("Do you handle the biometrics appointment too?", "¿También se encargan de la cita biométrica?"),
                    "a": _loc(
                        "USCIS schedules biometrics appointments directly — we'll help make sure your application is ready before that step.",
                        "USCIS programa las citas biométricas directamente — te ayudaremos a asegurarnos de que tu solicitud esté lista antes de ese paso.",
                    ),
                },
            ],
            "related": ["work-permit-renewal", "naturalization-citizenship"],
        },
        {
            "slug": "consular-processing",
            "icon": "immigration",
            "title": _loc("Consular Processing Petition Preparation", "Preparación de Peticiones para Proceso Consular"),
            "meta_description": _loc(
                "Document preparation support for family petitions where the relative will complete their immigrant visa abroad through consular processing.",
                "Apoyo en la preparación de documentos para peticiones familiares donde el familiar completará su visa de inmigrante en el extranjero mediante proceso consular.",
            ),
            "hero_text": _loc(
                "Support organizing the petition and supporting documents when an approved relative will finish their immigrant visa process at a U.S. consulate abroad, rather than adjusting status inside the U.S.",
                "Apoyo organizando la petición y los documentos de respaldo cuando un familiar aprobado completará su proceso de visa de inmigrante en un consulado de EE. UU. en el extranjero, en lugar de ajustar su estatus dentro de EE. UU.",
            ),
            "what_is_title": _loc(
                "What is consular processing?",
                "¿Qué es el proceso consular?",
            ),
            "what_is_body": _loc(
                "Consular processing is the path a relative living outside the U.S. follows to receive an immigrant visa — after a petition like Form I-130 is approved, the case moves to the National Visa Center and then to a U.S. embassy or consulate for an interview. We help you organize the petition and prepare the civil documents and forms NVC typically requests — we don't provide legal advice or represent you before the consulate.",
                "El proceso consular es el camino que sigue un familiar que vive fuera de EE. UU. para recibir una visa de inmigrante — después de que se aprueba una petición como el Formulario I-130, el caso pasa al Centro Nacional de Visas (NVC) y luego a una embajada o consulado de EE. UU. para una entrevista. Te ayudamos a organizar la petición y a preparar los documentos civiles y formularios que el NVC suele solicitar — no ofrecemos asesoría legal ni te representamos ante el consulado.",
            ),
            "when_needed": [
                _loc("Your relative lives outside the United States", "Tu familiar vive fuera de los Estados Unidos"),
                _loc("An I-130 or other qualifying petition was approved", "Se aprobó un I-130 u otra petición calificada"),
                _loc("Organizing civil documents for the National Visa Center", "Organizar documentos civiles para el Centro Nacional de Visas"),
                _loc("Preparing for the consular interview appointment", "Prepararse para la cita de entrevista consular"),
            ],
            "included": [
                _loc("Review of your petition approval and next steps", "Revisión de la aprobación de tu petición y los próximos pasos"),
                _loc("Organization of civil documents (birth, marriage, police records, etc.)", "Organización de documentos civiles (nacimiento, matrimonio, antecedentes policiales, etc.)"),
                _loc("Guidance on NVC forms and document submission", "Orientación sobre los formularios del NVC y el envío de documentos"),
                _loc("Certified translation of any foreign-language documents", "Traducción certificada de documentos en otro idioma"),
            ],
            "faq": [
                {
                    "q": _loc("How is this different from adjustment of status?", "¿En qué se diferencia del ajuste de estatus?"),
                    "a": _loc(
                        "Adjustment of status is for relatives already living in the U.S.; consular processing is for relatives who will complete their visa interview at a U.S. embassy or consulate abroad. We support both paths with document preparation.",
                        "El ajuste de estatus es para familiares que ya viven en EE. UU.; el proceso consular es para familiares que completarán su entrevista de visa en una embajada o consulado de EE. UU. en el extranjero. Apoyamos ambos caminos con preparación de documentos.",
                    ),
                },
                {
                    "q": _loc("Can you represent my relative at the consular interview?", "¿Pueden representar a mi familiar en la entrevista consular?"),
                    "a": _loc(
                        "No — we prepare documents only, we don't provide legal representation. The interview itself is conducted directly between your relative and consular officials.",
                        "No — solo preparamos documentos, no ofrecemos representación legal. La entrevista en sí se realiza directamente entre tu familiar y los funcionarios consulares.",
                    ),
                },
                {
                    "q": _loc("Can you translate the civil documents needed?", "¿Pueden traducir los documentos civiles necesarios?"),
                    "a": _loc(
                        "Yes — see our certified immigration document translation service.",
                        "Sí — consulta nuestro servicio de traducción certificada de documentos migratorios.",
                    ),
                },
            ],
            "related": ["i-130-petition", "adjustment-of-status", "fiancee-visa-k1"],
        },
        {
            "slug": "fiancee-visa-k1",
            "icon": "immigration",
            "title": _loc("Fiancé(e) Visa (K-1) Petition Preparation", "Preparación de Petición de Visa de Prometido(a) (K-1)"),
            "meta_description": _loc(
                "Help organizing and preparing Form I-129F for a K-1 fiancé(e) visa, so your partner can join you in the U.S. to marry.",
                "Ayuda organizando y preparando el Formulario I-129F para una visa de prometido(a) K-1, para que tu pareja pueda reunirse contigo en EE. UU. para casarse.",
            ),
            "hero_text": _loc(
                "Document preparation support for Form I-129F, filed by U.S. citizens to bring a foreign fiancé(e) to the United States to marry within 90 days of arrival.",
                "Apoyo en la preparación de documentos para el Formulario I-129F, presentado por ciudadanos de EE. UU. para traer a un(a) prometido(a) extranjero(a) a los Estados Unidos para casarse dentro de los 90 días de su llegada.",
            ),
            "what_is_title": _loc(
                "What is the K-1 fiancé(e) visa process?",
                "¿Qué es el proceso de visa de prometido(a) K-1?",
            ),
            "what_is_body": _loc(
                "The K-1 visa lets the fiancé(e) of a U.S. citizen enter the U.S. to marry within 90 days. It starts with Form I-129F, filed by the U.S. citizen petitioner, followed by consular processing abroad for the fiancé(e). We help you organize the petition, relationship evidence, and eligibility documents — we don't provide legal advice or file as your attorney.",
                "La visa K-1 permite que el(la) prometido(a) de un ciudadano de EE. UU. ingrese al país para casarse dentro de los 90 días. Comienza con el Formulario I-129F, presentado por el ciudadano de EE. UU. que peticiona, seguido de proceso consular en el extranjero para el(la) prometido(a). Te ayudamos a organizar la petición, la evidencia de la relación y los documentos de elegibilidad — no ofrecemos asesoría legal ni actuamos como tu abogado.",
            ),
            "when_needed": [
                _loc("You're a U.S. citizen engaged to a foreign national", "Eres ciudadano de EE. UU. y estás comprometido(a) con un(a) extranjero(a)"),
                _loc("Gathering evidence of an in-person meeting and relationship", "Reunir evidencia de un encuentro en persona y de la relación"),
                _loc("Preparing Form I-129F and supporting documents", "Preparar el Formulario I-129F y los documentos de respaldo"),
                _loc("Planning for the K-1 consular interview abroad", "Planificar la entrevista consular K-1 en el extranjero"),
            ],
            "included": [
                _loc("Review of your eligibility and relationship evidence", "Revisión de tu elegibilidad y evidencia de la relación"),
                _loc("Form I-129F organization and preparation support", "Apoyo en la organización y preparación del Formulario I-129F"),
                _loc("Guidance on commonly required supporting documents", "Orientación sobre los documentos de respaldo comúnmente requeridos"),
                _loc("Certified translation of any foreign-language documents", "Traducción certificada de documentos en otro idioma"),
            ],
            "faq": [
                {
                    "q": _loc("Do we have to have met in person?", "¿Tenemos que habernos conocido en persona?"),
                    "a": _loc(
                        "USCIS generally requires evidence you've met in person within the last two years, with limited exceptions. This is a legal eligibility question — we recommend confirming your specific situation with a licensed immigration attorney.",
                        "USCIS generalmente requiere evidencia de que se conocieron en persona dentro de los últimos dos años, con excepciones limitadas. Esta es una pregunta de elegibilidad legal — recomendamos confirmar tu situación específica con un abogado de inmigración con licencia.",
                    ),
                },
                {
                    "q": _loc("How long does the K-1 process take?", "¿Cuánto tiempo toma el proceso K-1?"),
                    "a": _loc(
                        "Processing times vary and depend on USCIS and consular workloads — we'll help you understand what to expect once your petition is filed.",
                        "Los tiempos de procesamiento varían y dependen de la carga de trabajo de USCIS y del consulado — te ayudaremos a entender qué esperar una vez que se presente tu petición.",
                    ),
                },
                {
                    "q": _loc("What happens after my fiancé(e) arrives?", "¿Qué pasa después de que llegue mi prometido(a)?"),
                    "a": _loc(
                        "You must marry within 90 days, after which your spouse can apply to adjust status — see our adjustment of status service for that next step.",
                        "Deben casarse dentro de los 90 días, después de lo cual tu cónyuge puede solicitar el ajuste de estatus — consulta nuestro servicio de ajuste de estatus para ese siguiente paso.",
                    ),
                },
            ],
            "related": ["adjustment-of-status", "i-130-petition"],
        },
    ],
    # ---------------------------------------------------------------- Notary
    "notary": [
        {
            "slug": "notarization",
            "icon": "notary",
            "title": _loc("General Document Notarization", "Notarización General de Documentos"),
            "meta_description": _loc(
                "Notary public services in New Jersey for acknowledgments, jurats, affidavits, and powers of attorney.",
                "Servicios de notario público en Nueva Jersey para reconocimientos, juramentos, declaraciones juradas y poderes notariales.",
            ),
            "hero_text": _loc(
                "Reliable notary public services for acknowledgments, jurats, affidavits, powers of attorney, and other documents that require notarization.",
                "Servicios confiables de notario público para reconocimientos, juramentos, declaraciones juradas, poderes notariales y otros documentos que requieren notarización.",
            ),
            "what_is_title": _loc("What does a notary do?", "¿Qué hace un notario?"),
            "what_is_body": _loc(
                "A notary public witnesses the signing of a document and verifies the identity of the signer, helping deter fraud. A notary does not provide legal advice or determine whether a document meets your legal needs — for that, consult an attorney.",
                "Un notario público presencia la firma de un documento y verifica la identidad del firmante, ayudando a prevenir el fraude. Un notario no ofrece asesoría legal ni determina si un documento cumple con tus necesidades legales — para eso, consulta a un abogado.",
            ),
            "when_needed": [
                _loc("Powers of attorney", "Poderes notariales"),
                _loc("Affidavits and sworn statements", "Declaraciones juradas"),
                _loc("Real estate and loan documents", "Documentos de bienes raíces y préstamos"),
                _loc("Business and personal agreements", "Acuerdos comerciales y personales"),
            ],
            "included": [
                _loc("Verification of your identification", "Verificación de tu identificación"),
                _loc("Witnessing your signature", "Presenciar tu firma"),
                _loc("Completing the notarial certificate", "Completar el certificado notarial"),
                _loc("Service available at our Paterson, NJ office", "Servicio disponible en nuestra oficina en Paterson, NJ"),
            ],
            "faq": [
                {
                    "q": _loc("What do I need to bring?", "¿Qué necesito traer?"),
                    "a": _loc(
                        "A valid government-issued photo ID and the unsigned document — sign it in front of the notary, not before.",
                        "Una identificación válida con foto emitida por el gobierno y el documento sin firmar — fírmalo frente al notario, no antes.",
                    ),
                },
                {
                    "q": _loc("Can you tell me what kind of document I need?", "¿Pueden decirme qué tipo de documento necesito?"),
                    "a": _loc(
                        "That's a legal question best answered by an attorney — we're happy to notarize the document once you know what you need.",
                        "Esa es una pregunta legal que un abogado puede responder mejor — con gusto notarizamos el documento una vez que sepas lo que necesitas.",
                    ),
                },
                {
                    "q": _loc("Do you offer notary services in Texas too?", "¿También ofrecen servicios de notario en Texas?"),
                    "a": _loc(
                        "Yes, corresponding notary services are available in Texas — message us for details.",
                        "Sí, hay servicios de notario correspondientes disponibles en Texas — escríbenos para más detalles.",
                    ),
                },
            ],
            "related": ["minor-travel-consent", "remote-online-notarization"],
        },
        {
            "slug": "minor-travel-consent",
            "icon": "notary",
            # Superseded by the Smart Intake service "consent-to-travel-authorization" (app/consent_travel/seed.py) —
            # kept only as seed history; never published on a fresh install so /notary never shows two equivalent
            # entries. Same non-destructive guard `consent_travel.seed.ensure_no_duplicate()` also applies to any
            # already-seeded database.
            "is_published": False,
            "title": _loc("Minor Travel Consent Notarization", "Notarización de Autorización de Viaje para Menores"),
            "meta_description": _loc(
                "Notarized travel consent letters for minors traveling without both parents or legal guardians.",
                "Cartas de autorización de viaje notariadas para menores que viajan sin ambos padres o tutores legales.",
            ),
            "hero_text": _loc(
                "Notarization of travel consent letters for children traveling with only one parent, a relative, or another authorized adult.",
                "Notarización de cartas de autorización de viaje para niños que viajan con solo un padre, un familiar u otro adulto autorizado.",
            ),
            "what_is_title": _loc("What is a minor travel consent letter?", "¿Qué es una carta de autorización de viaje para menores?"),
            "what_is_body": _loc(
                "It's a letter, typically signed by a parent or legal guardian who isn't traveling, authorizing a child to travel with another adult. Airlines, border agents, and some countries may request this document, though requirements vary — we recommend confirming what's needed for your specific trip in advance.",
                "Es una carta, generalmente firmada por un padre o tutor legal que no viaja, que autoriza a un menor a viajar con otro adulto. Las aerolíneas, agentes fronterizos y algunos países pueden solicitar este documento, aunque los requisitos varían — recomendamos confirmar con anticipación lo que se necesita para tu viaje específico.",
            ),
            "when_needed": [
                _loc("A child traveling with only one parent", "Un menor que viaja con solo uno de los padres"),
                _loc("A child traveling with a relative or family friend", "Un menor que viaja con un familiar o amigo de la familia"),
                _loc("International travel requiring proof of consent", "Viajes internacionales que requieren comprobante de autorización"),
                _loc("School or group trips abroad", "Viajes escolares o grupales al extranjero"),
            ],
            "included": [
                _loc("Notarization of the signed consent letter", "Notarización de la carta de consentimiento firmada"),
                _loc("Verification of the signing parent's identification", "Verificación de la identificación del padre firmante"),
                _loc("Guidance on commonly included information", "Orientación sobre información comúnmente incluida"),
                _loc("Same-day service in most cases", "Servicio el mismo día en la mayoría de los casos"),
            ],
            "faq": [
                {
                    "q": _loc("Do all countries require this letter?", "¿Todos los países requieren esta carta?"),
                    "a": _loc(
                        "Requirements vary by country and airline. We recommend checking with your airline and destination country's consulate before you travel.",
                        "Los requisitos varían según el país y la aerolínea. Te recomendamos verificar con tu aerolínea y el consulado del país de destino antes de viajar.",
                    ),
                },
                {
                    "q": _loc("Do I need to write the letter myself?", "¿Necesito escribir la carta yo mismo?"),
                    "a": _loc(
                        "You can bring your own letter, or we can help you organize the commonly included information before notarizing it.",
                        "Puedes traer tu propia carta, o podemos ayudarte a organizar la información comúnmente incluida antes de notarizarla.",
                    ),
                },
                {
                    "q": _loc("Does the traveling adult need to be present?", "¿El adulto que viaja necesita estar presente?"),
                    "a": _loc(
                        "No, typically only the signing parent or guardian needs to appear before the notary.",
                        "No, generalmente solo el padre o tutor que firma necesita presentarse ante el notario.",
                    ),
                },
            ],
            "related": ["notarization", "remote-online-notarization"],
        },
        {
            "slug": "remote-online-notarization",
            "icon": "notary",
            "title": _loc("Remote Online Notarization", "Notarización Remota en Línea"),
            "meta_description": _loc(
                "Remote online notarization (RON) for signers who can't visit our office in person, where available.",
                "Notarización remota en línea (RON) para firmantes que no pueden visitar nuestra oficina en persona, cuando está disponible.",
            ),
            "hero_text": _loc(
                "For signers who can't come to our office in person, remote online notarization lets you complete the process securely by video, where available.",
                "Para firmantes que no pueden venir a nuestra oficina en persona, la notarización remota en línea te permite completar el proceso de forma segura por video, cuando está disponible.",
            ),
            "what_is_title": _loc("What is remote online notarization?", "¿Qué es la notarización remota en línea?"),
            "what_is_body": _loc(
                "Remote online notarization (RON) allows a notary to witness a signature and verify identity through a secure live video session instead of an in-person meeting. Availability depends on the type of document and applicable state rules — message us to confirm whether your document qualifies.",
                "La notarización remota en línea (RON) permite que un notario presencie una firma y verifique la identidad a través de una sesión de video en vivo y segura, en lugar de una reunión en persona. La disponibilidad depende del tipo de documento y las reglas estatales aplicables — escríbenos para confirmar si tu documento califica.",
            ),
            "when_needed": [
                _loc("Signers who live far from our office", "Firmantes que viven lejos de nuestra oficina"),
                _loc("Signers with limited mobility or scheduling constraints", "Firmantes con movilidad limitada o restricciones de horario"),
                _loc("Time-sensitive documents", "Documentos con plazos ajustados"),
                _loc("Out-of-state or international signers, where eligible", "Firmantes fuera del estado o internacionales, cuando sea elegible"),
            ],
            "included": [
                _loc("A secure live video notarization session", "Una sesión de notarización en vivo y segura por video"),
                _loc("Identity verification appropriate for remote signing", "Verificación de identidad adecuada para firma remota"),
                _loc("Guidance on eligible document types", "Orientación sobre tipos de documentos elegibles"),
                _loc("Digital record of the notarization session", "Registro digital de la sesión de notarización"),
            ],
            "faq": [
                {
                    "q": _loc("Is remote notarization available for my document?", "¿La notarización remota está disponible para mi documento?"),
                    "a": _loc(
                        "It depends on the document type and current state requirements. Message us with details about your document and we'll confirm availability.",
                        "Depende del tipo de documento y los requisitos estatales vigentes. Escríbenos con los detalles de tu documento y confirmaremos la disponibilidad.",
                    ),
                },
                {
                    "q": _loc("What do I need for the video session?", "¿Qué necesito para la sesión de video?"),
                    "a": _loc(
                        "A stable internet connection, a device with a camera, and a valid government-issued photo ID.",
                        "Una conexión a internet estable, un dispositivo con cámara y una identificación válida con foto emitida por el gobierno.",
                    ),
                },
                {
                    "q": _loc("Will the document be accepted everywhere?", "¿El documento será aceptado en todas partes?"),
                    "a": _loc(
                        "Acceptance of remotely notarized documents can vary by recipient and jurisdiction — we recommend confirming with the receiving party before your session.",
                        "La aceptación de documentos notarizados remotamente puede variar según el destinatario y la jurisdicción — te recomendamos confirmar con la parte receptora antes de tu sesión.",
                    ),
                },
            ],
            "related": ["notarization", "minor-travel-consent"],
        },
    ],
    # ---------------------------------------------------------------- Apostille
    "apostille": [
        {
            "slug": "nj-state-document-apostille",
            "icon": "apostille",
            "title": _loc("New Jersey State Document Apostille", "Apostilla de Documentos Estatales de Nueva Jersey"),
            "meta_description": _loc(
                "Assistance obtaining an apostille for New Jersey state-issued documents — birth certificates, marriage certificates, diplomas, and notarized documents.",
                "Asistencia para obtener una apostilla para documentos emitidos por el estado de Nueva Jersey — actas de nacimiento, actas de matrimonio, diplomas y documentos notariados.",
            ),
            "hero_text": _loc(
                "Help preparing and submitting New Jersey state-issued documents to the NJ Department of the Treasury for an apostille, so they're recognized abroad.",
                "Ayuda preparando y enviando documentos emitidos por el estado de Nueva Jersey al Departamento del Tesoro de NJ para obtener una apostilla, para que sean reconocidos en el extranjero.",
            ),
            "what_is_title": _loc(
                "What is an apostille and when do I need one?",
                "¿Qué es una apostilla y cuándo la necesito?",
            ),
            "what_is_body": _loc(
                "An apostille is a certification that authenticates a document for use in another country that participates in the Hague Apostille Convention. NJ state-issued documents — like a NJ birth or marriage certificate, or a document notarized in NJ — need to go through the New Jersey Department of the Treasury for this certification. We help you prepare and submit the request correctly.",
                "Una apostilla es una certificación que autentica un documento para su uso en otro país que participa en el Convenio de La Haya sobre Apostilla. Los documentos emitidos por el estado de NJ — como un acta de nacimiento o matrimonio de NJ, o un documento notariado en NJ — deben pasar por el Departamento del Tesoro de Nueva Jersey para esta certificación. Te ayudamos a preparar y enviar la solicitud correctamente.",
            ),
            "when_needed": [
                _loc("Using a NJ birth or marriage certificate abroad", "Usar un acta de nacimiento o matrimonio de NJ en el extranjero"),
                _loc("A document notarized in New Jersey", "Un documento notariado en Nueva Jersey"),
                _loc("A diploma or transcript from a NJ school", "Un diploma o certificado de notas de una escuela de NJ"),
                _loc("Power of attorney or business documents for use overseas", "Poder notarial o documentos comerciales para uso en el extranjero"),
            ],
            "included": [
                _loc("Review of your document and eligibility for apostille", "Revisión de tu documento y elegibilidad para apostilla"),
                _loc("Preparation of the apostille request", "Preparación de la solicitud de apostilla"),
                _loc("Guidance on submission to the NJ Department of the Treasury", "Orientación sobre el envío al Departamento del Tesoro de NJ"),
                _loc("Certified translation, if the destination country requires one", "Traducción certificada, si el país de destino la requiere"),
            ],
            "faq": [
                {
                    "q": _loc("How long does an apostille take?", "¿Cuánto tiempo tarda una apostilla?"),
                    "a": _loc(
                        "Processing time depends on the New Jersey Department of the Treasury's current workload — we'll let you know what to expect, including any expedited options.",
                        "El tiempo de procesamiento depende de la carga de trabajo actual del Departamento del Tesoro de Nueva Jersey — te informaremos qué esperar, incluyendo opciones de trámite urgente si están disponibles.",
                    ),
                },
                {
                    "q": _loc("Does the destination country accept apostilles?", "¿El país de destino acepta apostillas?"),
                    "a": _loc(
                        "Most countries do, since they participate in the Hague Apostille Convention — for countries that don't, a different authentication process (legalization) applies. We can help you confirm which applies to your situation.",
                        "La mayoría de los países sí, ya que participan en el Convenio de La Haya sobre Apostilla — para los que no participan, aplica un proceso de autenticación diferente (legalización). Podemos ayudarte a confirmar cuál aplica a tu situación.",
                    ),
                },
                {
                    "q": _loc("My document isn't from New Jersey — can you still help?", "Mi documento no es de Nueva Jersey — ¿aún pueden ayudarme?"),
                    "a": _loc(
                        "If it's a federal document (like an FBI background check), see our federal document apostille service. For documents from other states, message us and we'll point you in the right direction.",
                        "Si es un documento federal (como una verificación de antecedentes del FBI), consulta nuestro servicio de apostilla de documentos federales. Para documentos de otros estados, escríbenos y te orientamos hacia el proceso correcto.",
                    ),
                },
            ],
            "related": ["federal-document-apostille"],
        },
        {
            "slug": "federal-document-apostille",
            "icon": "apostille",
            "title": _loc("Federal Document Apostille", "Apostilla de Documentos Federales"),
            "meta_description": _loc(
                "Assistance obtaining an apostille for federal documents — FBI background checks, USCIS documents, and other U.S. federal records.",
                "Asistencia para obtener una apostilla de documentos federales — verificaciones de antecedentes del FBI, documentos de USCIS y otros registros federales de EE. UU.",
            ),
            "hero_text": _loc(
                "Help preparing federal documents — like an FBI background check or other federal record — for authentication by the U.S. Department of State, so they're recognized abroad.",
                "Ayuda preparando documentos federales — como una verificación de antecedentes del FBI u otro registro federal — para su autenticación por el Departamento de Estado de EE. UU., para que sean reconocidos en el extranjero.",
            ),
            "what_is_title": _loc(
                "How is a federal apostille different?",
                "¿En qué se diferencia una apostilla federal?",
            ),
            "what_is_body": _loc(
                "Documents issued by a federal agency (an FBI identity history summary, for example) are authenticated by the U.S. Department of State rather than a state office. The process and required cover paperwork are different from a state-level apostille — we help you prepare the request correctly for the type of document you have.",
                "Los documentos emitidos por una agencia federal (como un resumen de antecedentes del FBI) se autentican por el Departamento de Estado de EE. UU., y no por una oficina estatal. El proceso y el papeleo de portada requerido son diferentes de una apostilla a nivel estatal — te ayudamos a preparar la solicitud correctamente según el tipo de documento que tengas.",
            ),
            "when_needed": [
                _loc("FBI identity history summary (background check)", "Resumen de antecedentes del FBI (verificación de antecedentes)"),
                _loc("Documents issued by a federal court", "Documentos emitidos por un tribunal federal"),
                _loc("Certain federal agency records", "Ciertos registros de agencias federales"),
                _loc("Documents for use in a country requiring federal authentication", "Documentos para uso en un país que requiere autenticación federal"),
            ],
            "included": [
                _loc("Review of your federal document and its requirements", "Revisión de tu documento federal y sus requisitos"),
                _loc("Preparation of the required cover letter and forms", "Preparación de la carta de portada y formularios requeridos"),
                _loc("Guidance on submission to the U.S. Department of State", "Orientación sobre el envío al Departamento de Estado de EE. UU."),
                _loc("Certified translation, if the destination country requires one", "Traducción certificada, si el país de destino la requiere"),
            ],
            "faq": [
                {
                    "q": _loc("I need an FBI background check first — can you help?", "Necesito primero una verificación de antecedentes del FBI — ¿pueden ayudarme?"),
                    "a": _loc(
                        "We can guide you on how to request your FBI identity history summary directly from the FBI, then help you prepare it for apostille once you receive it.",
                        "Podemos orientarte sobre cómo solicitar tu resumen de antecedentes del FBI directamente con el FBI, y luego ayudarte a prepararlo para la apostilla una vez que lo recibas.",
                    ),
                },
                {
                    "q": _loc("How long does federal authentication take?", "¿Cuánto tarda la autenticación federal?"),
                    "a": _loc(
                        "Processing time depends on the U.S. Department of State's current workload — we'll let you know what to expect for your document.",
                        "El tiempo de procesamiento depende de la carga de trabajo actual del Departamento de Estado de EE. UU. — te informaremos qué esperar para tu documento.",
                    ),
                },
                {
                    "q": _loc("My document was issued by New Jersey, not the federal government — what should I use?", "Mi documento fue emitido por Nueva Jersey, no por el gobierno federal — ¿qué debo usar?"),
                    "a": _loc(
                        "See our New Jersey state document apostille service instead — the right process depends on which government issued your document.",
                        "Consulta mejor nuestro servicio de apostilla de documentos estatales de Nueva Jersey — el proceso correcto depende de qué gobierno emitió tu documento.",
                    ),
                },
            ],
            "related": ["nj-state-document-apostille"],
        },
    ],
    # ---------------------------------------------------------------- Document & Office Services
    "document-office-services": [
        {
            "slug": "passport-photo-services",
            "icon": "documents",
            "title": _loc("Passport & ID Photo Services", "Servicios de Fotos para Pasaporte e Identificación"),
            "meta_description": _loc(
                "Passport-compliant photos taken and printed in minutes, meeting U.S. State Department and immigration photo requirements.",
                "Fotos que cumplen con los requisitos de pasaporte, tomadas e impresas en minutos, según las especificaciones del Departamento de Estado de EE. UU. y de inmigración.",
            ),
            "hero_text": _loc(
                "Passport and ID-style photos taken and printed on the spot, sized and formatted to meet U.S. passport, visa, and immigration application requirements.",
                "Fotos tipo pasaporte e identificación tomadas e impresas en el momento, con el tamaño y formato que cumplen los requisitos de pasaportes, visas y solicitudes migratorias de EE. UU.",
            ),
            "what_is_title": _loc(
                "What photo requirements do you follow?",
                "¿Qué requisitos de fotos siguen?",
            ),
            "what_is_body": _loc(
                "We take and print photos to the size and format the U.S. State Department requires for passports, and the formats commonly required for visa and immigration applications, driver's licenses, and other ID needs.",
                "Tomamos e imprimimos fotos con el tamaño y formato que requiere el Departamento de Estado de EE. UU. para pasaportes, y los formatos comúnmente requeridos para solicitudes de visa e inmigración, licencias de conducir y otras necesidades de identificación.",
            ),
            "when_needed": [
                _loc("New or renewed U.S. passport applications", "Solicitudes de pasaporte de EE. UU. nuevo o renovado"),
                _loc("Visa and immigration form photo requirements", "Requisitos de foto para formularios de visa e inmigración"),
                _loc("Driver's license or state ID applications", "Solicitudes de licencia de conducir o identificación estatal"),
                _loc("Employment badges and other ID cards", "Gafetes de trabajo y otras tarjetas de identificación"),
            ],
            "included": [
                _loc("Photo taken on site, no appointment needed", "Foto tomada en el lugar, sin necesidad de cita"),
                _loc("Sized and formatted to your document's requirements", "Con el tamaño y formato que requiere tu documento"),
                _loc("Printed copies ready the same visit", "Copias impresas listas en la misma visita"),
                _loc("Available alongside our other document services", "Disponible junto con nuestros otros servicios de documentos"),
            ],
            "faq": [
                {
                    "q": _loc("Do I need an appointment for a passport photo?", "¿Necesito cita para una foto de pasaporte?"),
                    "a": _loc(
                        "No, walk-ins are welcome during our business hours.",
                        "No, puedes venir sin cita durante nuestro horario de atención.",
                    ),
                },
                {
                    "q": _loc("How fast can I get my photo?", "¿Qué tan rápido puedo obtener mi foto?"),
                    "a": _loc(
                        "Photos are taken and printed within a few minutes, right in our office.",
                        "Las fotos se toman e imprimen en pocos minutos, en nuestra oficina.",
                    ),
                },
                {
                    "q": _loc("Can you also help with the rest of my passport application?", "¿También pueden ayudarme con el resto de mi solicitud de pasaporte?"),
                    "a": _loc(
                        "We can help with photos, copies, and general document preparation, though the passport application itself is submitted directly to the State Department.",
                        "Podemos ayudarte con fotos, copias y preparación general de documentos, aunque la solicitud de pasaporte en sí se presenta directamente al Departamento de Estado.",
                    ),
                },
            ],
            "related": ["document-services", "forms-applications-assistance"],
        },
        {
            "slug": "document-services",
            "icon": "documents",
            "title": _loc("Copies, Fax, Scan & Printing Services", "Servicios de Copias, Fax, Escaneo e Impresión"),
            "meta_description": _loc(
                "Document copies, faxing, scanning, emailing, and printing services for personal and business needs.",
                "Servicios de copias de documentos, fax, escaneo, envío por correo electrónico e impresión para necesidades personales y de negocio.",
            ),
            "hero_text": _loc(
                "Everyday document support — copies, fax, scan-to-email, and printing — for personal paperwork, business needs, and anything else you need handled quickly.",
                "Apoyo cotidiano con documentos — copias, fax, escaneo a correo electrónico e impresión — para papeleo personal, necesidades de negocio y cualquier otra cosa que necesites resolver rápido.",
            ),
            "what_is_title": _loc(
                "What document services do you offer?",
                "¿Qué servicios de documentos ofrecen?",
            ),
            "what_is_body": _loc(
                "We handle the everyday document tasks that come up constantly — making copies, sending or receiving a fax, scanning a document to email it, or printing something you need. Walk in with what you need, and we'll take care of it.",
                "Nos encargamos de las tareas cotidianas de documentos que surgen constantemente — hacer copias, enviar o recibir un fax, escanear un documento para enviarlo por correo, o imprimir algo que necesites. Ven con lo que necesitas y nosotros nos encargamos.",
            ),
            "when_needed": [
                _loc("Copies of ID, forms, or other paperwork", "Copias de identificación, formularios u otro papeleo"),
                _loc("Sending or receiving a fax", "Enviar o recibir un fax"),
                _loc("Scanning a document to send by email", "Escanear un documento para enviarlo por correo electrónico"),
                _loc("Printing forms, resumes, or other documents", "Imprimir formularios, currículums u otros documentos"),
            ],
            "included": [
                _loc("Black & white and color copies", "Copias en blanco y negro y a color"),
                _loc("Send and receive fax service", "Servicio de envío y recepción de fax"),
                _loc("Scan-to-email for any document", "Escaneo a correo electrónico para cualquier documento"),
                _loc("Printing from a file, USB, or email attachment", "Impresión desde un archivo, USB o adjunto de correo"),
            ],
            "faq": [
                {
                    "q": _loc("Do I need an appointment?", "¿Necesito una cita?"),
                    "a": _loc(
                        "No, these services are available on a walk-in basis during business hours.",
                        "No, estos servicios están disponibles sin cita durante nuestro horario de atención.",
                    ),
                },
                {
                    "q": _loc("Can you scan and email a document for me right now?", "¿Pueden escanear y enviarme un documento por correo ahora mismo?"),
                    "a": _loc(
                        "Yes, bring the document in and we'll scan and email it to you or anyone else while you wait.",
                        "Sí, trae el documento y lo escaneamos y enviamos por correo a ti o a quien necesites mientras esperas.",
                    ),
                },
                {
                    "q": _loc("Do you have a fax number I can receive documents at?", "¿Tienen un número de fax donde pueda recibir documentos?"),
                    "a": _loc(
                        "Yes — message us on WhatsApp and we'll share our fax number for incoming documents.",
                        "Sí — escríbenos por WhatsApp y te compartimos nuestro número de fax para documentos entrantes.",
                    ),
                },
            ],
            "related": ["passport-photo-services", "forms-applications-assistance"],
        },
        {
            "slug": "forms-applications-assistance",
            "icon": "documents",
            "title": _loc("Forms & Applications Assistance", "Asistencia con Formularios y Solicitudes"),
            "meta_description": _loc(
                "Help completing applications for Medicaid, SNAP, unemployment benefits, the NJ ANCHOR program, and other administrative forms.",
                "Ayuda completando solicitudes de Medicaid, SNAP, beneficios de desempleo, el programa NJ ANCHOR y otros formularios administrativos.",
            ),
            "hero_text": _loc(
                "Help understanding and completing common administrative forms and benefit applications — Medicaid, SNAP, unemployment, the NJ ANCHOR property tax relief program, and more.",
                "Ayuda entendiendo y completando formularios administrativos y solicitudes de beneficios comunes — Medicaid, SNAP, desempleo, el programa de alivio de impuestos a la propiedad NJ ANCHOR y más.",
            ),
            "what_is_title": _loc(
                "What kind of forms can you help with?",
                "¿Con qué tipo de formularios pueden ayudar?",
            ),
            "what_is_body": _loc(
                "Many government and benefits applications are long, confusing, or only available online — we help you gather what's needed and complete the form accurately, in English or Spanish. We help you fill out and submit the application; eligibility decisions are always made by the issuing agency, not by us.",
                "Muchas solicitudes gubernamentales y de beneficios son largas, confusas o solo están disponibles en línea — te ayudamos a reunir lo necesario y completar el formulario con precisión, en inglés o español. Te ayudamos a llenar y enviar la solicitud; las decisiones de elegibilidad siempre las toma la agencia correspondiente, no nosotros.",
            ),
            "when_needed": [
                _loc("Medicaid applications and renewals", "Solicitudes y renovaciones de Medicaid"),
                _loc("SNAP (food stamps) applications", "Solicitudes de SNAP (cupones de alimentos)"),
                _loc("Unemployment benefits applications", "Solicitudes de beneficios de desempleo"),
                _loc("NJ ANCHOR property tax relief applications", "Solicitudes del programa de alivio NJ ANCHOR"),
            ],
            "included": [
                _loc("Review of what documents the application requires", "Revisión de los documentos que requiere la solicitud"),
                _loc("Help completing the form accurately", "Ayuda para completar el formulario con precisión"),
                _loc("Guidance on how and where to submit it", "Orientación sobre cómo y dónde presentarlo"),
                _loc("Bilingual support throughout", "Apoyo bilingüe durante todo el proceso"),
            ],
            "faq": [
                {
                    "q": _loc("Can you tell me if I qualify for these programs?", "¿Pueden decirme si califico para estos programas?"),
                    "a": _loc(
                        "Eligibility is determined by the issuing agency, not by us — we help you complete and submit the application accurately based on your information.",
                        "La elegibilidad la determina la agencia correspondiente, no nosotros — te ayudamos a completar y enviar la solicitud con precisión según tu información.",
                    ),
                },
                {
                    "q": _loc("What is the NJ ANCHOR program?", "¿Qué es el programa NJ ANCHOR?"),
                    "a": _loc(
                        "It's a New Jersey property tax relief program for homeowners and renters — we can help you understand the application and complete it.",
                        "Es un programa de alivio de impuestos a la propiedad de Nueva Jersey para propietarios e inquilinos — podemos ayudarte a entender la solicitud y completarla.",
                    ),
                },
                {
                    "q": _loc("Do I need to bring documents with me?", "¿Necesito traer documentos conmigo?"),
                    "a": _loc(
                        "Typically yes — ID, proof of income, and other supporting documents depending on the program. Message us on WhatsApp and we'll confirm what to bring for your specific application.",
                        "Generalmente sí — identificación, comprobante de ingresos y otros documentos de respaldo según el programa. Escríbenos por WhatsApp y confirmamos qué traer para tu solicitud específica.",
                    ),
                },
            ],
            "related": ["document-services", "passport-photo-services"],
        },
    ],
}


def get_service_subpage(category, slug):
    for page in SUBPAGES.get(category, []):
        if page["slug"] == slug:
            return page
    return None


def _resolve(value, lang):
    if isinstance(value, dict):
        if set(value.keys()) == {"en", "es"}:
            return value.get(lang, value.get("en"))
        return {k: _resolve(v, lang) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, lang) for v in value]
    return value


def service_subpage_context(lang, category, page):
    from app.service_areas import get_scope

    meta = CATEGORY_META[category]
    resolved = _resolve(page, lang)
    related_pages = []
    for slug in page.get("related", []):
        rp = get_service_subpage(category, slug)
        if rp:
            related_pages.append(
                {
                    "title": rp["title"].get(lang, rp["title"]["en"]),
                    "url": url_for(meta["subpage_endpoint"], lang=lang, slug=slug),
                }
            )

    scope = get_scope(category, page["slug"])
    scope_note = _resolve(scope["note"], lang) if scope.get("note") else None

    from app import business_info as biz

    area_served_json = []
    if scope["nj_in_person"]:
        area_served_json += [{"@type": "City", "name": f"{c}, NJ"} for c in biz.NJ_SERVICE_CITIES]
    if scope["tx_in_person"]:
        area_served_json += [{"@type": "City", "name": f"{c}, TX"} for c in biz.TX_SERVICE_CITIES]
    if scope["remote_nationwide"]:
        area_served_json.append({"@type": "Country", "name": "United States"})

    return {
        "page": resolved,
        "category_title": meta["title"].get(lang, meta["title"]["en"]),
        "category_url": url_for(meta["endpoint"], lang=lang, _external=True),
        "primary_cta_url": url_for(meta["cta_endpoint"], lang=lang) + meta.get("cta_anchor", ""),
        "primary_cta_label": meta["cta_label"].get(lang, meta["cta_label"]["en"]),
        "related_pages": related_pages,
        "area_scope": scope,
        "area_scope_note": scope_note,
        "area_served_json": area_served_json,
    }


def all_subpage_slugs():
    """(category, slug) pairs for every registered subpage — used by the sitemap."""
    return [(category, page["slug"]) for category, pages in SUBPAGES.items() for page in pages]
