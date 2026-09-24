"""Bilingual customer text for the ITIN / W-7 intake. English is the source; Spanish is OG's natural equivalent. Requirements wording follows the supplied
"Instructions for Form W-7 (Rev. December 2024)" (page numbers in `w7_rules.PAGE`)."""

from app import business_info as biz

SCOPE_MSG = ("This type of ITIN request is not currently handled through OG's online ITIN intake. Please contact OG Multiservices for assistance.",
             "Este tipo de solicitud de ITIN no se maneja actualmente a través del formulario en línea de ITIN de OG. Comunícate con OG Multiservices para recibir ayuda.")

PROCESSING = (
    "<strong>IRS Processing</strong><br>The IRS generally advises allowing approximately 7 weeks to receive information about an ITIN application. Processing may take approximately "
    "9–11 weeks during peak filing season or in other circumstances described by the IRS.<br><br>Once OG Multiservices sends your application package to the IRS, processing and the final "
    "decision are controlled by the IRS. OG cannot guarantee approval or a specific processing time.<br><br>OG can provide the USPS tracking number showing delivery of the package to the IRS.",
    "<strong>Procesamiento del IRS</strong><br>El IRS generalmente recomienda esperar aproximadamente 7 semanas para recibir información sobre una solicitud de ITIN. El procesamiento puede "
    "tardar aproximadamente de 9 a 11 semanas durante la temporada alta de presentación de impuestos o en otras circunstancias descritas por el IRS.<br><br>Una vez que OG Multiservices envíe tu "
    "paquete de solicitud al IRS, el procesamiento y la decisión final están a cargo del IRS. OG no puede garantizar la aprobación ni un tiempo de procesamiento específico.<br><br>"
    "OG puede darte el número de rastreo de USPS que muestra la entrega del paquete al IRS.")
DISCLAIMER = ("OG Multiservices does not approve or deny ITIN applications. The IRS makes the final determination. OG assists with preparation, the Certifying Acceptance Agent (CAA) and document "
              "workflow, tax preparation and the submission workflow, as applicable. Sending information to OG is not a promise that an ITIN will be issued.",
              "OG Multiservices no aprueba ni niega solicitudes de ITIN. El IRS toma la determinación final. OG ayuda con la preparación, el flujo de trabajo del Agente Certificador de Aceptación (CAA) y de "
              "documentos, la preparación de impuestos y el envío, según corresponda. Enviar información a OG no es una promesa de que se emitirá un ITIN.")
SEND_NOTE = ("Sending this to OG does not mean your ITIN is approved, that Form W-7 has been signed or filed, that the IRS received anything, that a tax return was filed, or that CAA "
             "certification is complete. OG will review your information and contact you about the next steps, including signatures and any original documents.",
             "Enviar esto a OG no significa que tu ITIN esté aprobado, que el Formulario W-7 esté firmado o presentado, que el IRS haya recibido algo, que se haya presentado una declaración de impuestos "
             "ni que la certificación del CAA esté completa. OG revisará tu información y te contactará sobre los siguientes pasos, incluidas las firmas y los documentos originales.")

OFFICE_ADDRESS_LINES = [biz.BUSINESS_NAME, f"{biz.OFFICE_STREET}, {biz.OFFICE_UNIT_TYPE.upper()} {biz.OFFICE_UNIT_NUMBER}", f"{biz.OFFICE_CITY}, {biz.OFFICE_STATE} {biz.OFFICE_ZIP}"]


def delivery_html(lang="en", esc=lambda x: x):
    en = lang == "en"
    lines = "<br>".join(esc(x) for x in OFFICE_ADDRESS_LINES)
    return (f'<p class="text-[13px] font-semibold text-brand-800">{esc("Two ways to give OG the original" if en else "Dos formas de entregar el original a OG")}</p>'
            f'<ol class="mt-1 list-decimal pl-5 text-[13px] text-slate-700 space-y-1.5"><li><span class="font-semibold">{esc("Mail it to OG:" if en else "Envíalo por correo a OG:")}</span><br>{lines}</li>'
            f'<li><span class="font-semibold">{esc("Bring it in person" if en else "Tráelo en persona")}</span> {esc("to our Paterson office, whichever is easier for you." if en else "a nuestra oficina de Paterson, lo que te resulte más fácil.")}</li></ol>'
            f'<p class="mt-2 text-[12px] text-slate-500">{esc("A photo you upload here is only a copy for OG to pre-review. It does not count as the original until OG marks the original as received." if en else "Una foto que subes aquí es solo una copia para que OG la revise previamente. No cuenta como el original hasta que OG marque el original como recibido.")}</p>')


# ---- source-driven record content (Instructions p. 4 and 16)
MEDICAL_HELP = (
    "For a child under 6, a medical record must include ALL of the following: an official document (a shot/immunization record, or a dated and signed letter from the medical provider on official letterhead); "
    "the child's name, date of birth and address (a U.S. address if proof of U.S. residency is required); a date of medical care within 12 months before the Form W-7 is filed; and the doctor's name and "
    "the medical facility's address where the care was given (a U.S. address if proof of U.S. residency is required). Several official documents together can cover everything.",
    "Para un niño menor de 6 años, un registro médico debe incluir TODO lo siguiente: un documento oficial (un registro de vacunas o una carta fechada y firmada del proveedor médico en papel membretado oficial); "
    "el nombre, la fecha de nacimiento y la dirección del niño (una dirección en EE. UU. si se requiere prueba de residencia en EE. UU.); una fecha de atención médica dentro de los 12 meses anteriores a la presentación "
    "del Formulario W-7; y el nombre del médico y la dirección del centro médico donde se dio la atención (una dirección en EE. UU. si se requiere prueba de residencia en EE. UU.). Varios documentos oficiales "
    "juntos pueden cubrir todo.")
SCHOOL_HELP = (
    "For a dependent under 24 who is a student, a school record must include ALL of the following: an official document (a report card, a transcript, or a dated and signed letter from a school official on "
    "letterhead); the student's name and address (a U.S. address if proof of U.S. residency is required); a record of attendance or coursework with grades; the school's name and address (a U.S. address if proof "
    "of U.S. residency is required); and school term dates ending no more than 12 months before the Form W-7 is filed. Several official documents together can cover everything.",
    "Para un dependiente menor de 24 años que es estudiante, un registro escolar debe incluir TODO lo siguiente: un documento oficial (una boleta de calificaciones, un expediente académico o una carta fechada y "
    "firmada de un funcionario escolar en papel membretado); el nombre y la dirección del estudiante (una dirección en EE. UU. si se requiere prueba de residencia en EE. UU.); un registro de asistencia o de cursos "
    "con calificaciones; el nombre y la dirección de la escuela (una dirección en EE. UU. si se requiere prueba de residencia en EE. UU.); y fechas del período escolar que terminen no más de 12 meses antes de la "
    "presentación del Formulario W-7. Varios documentos oficiales juntos pueden cubrir todo.")
RESIDENCY_HELP = (
    "The IRS asks a dependent to prove U.S. residency unless the passport shows a date of entry into the United States (or another exception applies). The documents that can show it depend on age. "
    "OG works out which ones apply from the date of birth.",
    "El IRS pide a un dependiente que pruebe su residencia en EE. UU. a menos que el pasaporte muestre una fecha de entrada a Estados Unidos (o aplique otra excepción). Los documentos que pueden probarla "
    "dependen de la edad. OG determina cuáles aplican según la fecha de nacimiento.")
BIRTH_CERT_HELP = ("The IRS requires an original birth certificate for an applicant under 18 who does not have a valid passport. If there is a valid passport, OG still asks for the birth certificate as part of its own "
                   "workflow to document the relationship.", "El IRS exige un acta de nacimiento original para un solicitante menor de 18 años que no tiene un pasaporte válido. Si hay un pasaporte válido, OG igual pide el acta de nacimiento como parte de su propio flujo de trabajo para documentar la relación.")
CAA_NOTE_DEPENDENT = ("OG, as a Certifying Acceptance Agent, can verify only passports and birth certificates for dependents. Other documents for a dependent must go to the IRS as originals with the package.",
                      "OG, como Agente Certificador de Aceptación, solo puede verificar pasaportes y actas de nacimiento de dependientes. Los demás documentos de un dependiente deben ir al IRS como originales con el paquete.")
W2_REVIEW = ("OG reviews W-2 statements as they were issued. We will look at the taxpayer identifier on it with you; this is not a conclusion about your case.",
             "OG revisa los formularios W-2 tal como fueron emitidos. Revisaremos contigo el identificador de contribuyente que aparece en él; esto no es una conclusión sobre tu caso.")
OG_REVIEW_W7 = ("OG REVIEW — ADDITIONAL W-7 INFORMATION REQUIRED", "REVISIÓN DE OG — SE REQUIERE INFORMACIÓN ADICIONAL PARA EL W-7")
SSN_NOTE = ("The Form W-7 says not to submit it if you have, are eligible for, or have applied for a U.S. Social Security number. OG will review this with you; it is not a decision about your case.",
            "El Formulario W-7 indica que no se debe presentar si tienes, eres elegible para o has solicitado un número de Seguro Social de EE. UU. OG lo revisará contigo; no es una decisión sobre tu caso.")


# ---- customer-facing document requests: plain language, EN/ES. The stored requirement (`DocumentRequirement.title / customer_message`) stays the English admin record;
# customers always see these (`w7_docs.req_text`). Keys are the requirement rule keys; `w7.alt.<doc>` and `w7.res.<doc>` are built from the evidence labels.
REQ_TEXT = {
    "w7.passport": ("Passport — photo page", "Pasaporte — página de la foto",
                    "Upload a clear photo of the page with the photo and personal details. We will also need to see the original passport before the process is complete.",
                    "Sube una foto clara de la página donde aparecen la foto y los datos. También necesitaremos revisar el pasaporte original antes de completar el proceso."),
    "w7.visa_page": ("U.S. visa — page with the visa", "Visa de EE. UU. — página con la visa",
                     "Upload a clear photo of the passport page that shows the U.S. visa.", "Sube una foto clara de la página del pasaporte donde aparece la visa de EE. UU."),
    "w7.alt.more": ("Another ID document", "Otro documento de identidad",
                    "Without a passport, OG needs at least two kinds of documents. OG will tell you which ones fit.", "Sin pasaporte, OG necesita al menos dos tipos de documentos. OG te dirá cuáles sirven."),
    "w7.res.choose": ("Proof of U.S. residency", "Prueba de residencia en EE. UU.",
                      "OG will tell you which document fits the child's age.", "OG te dirá qué documento sirve según la edad."),
    "w7.marriage_cert": ("Marriage certificate", "Acta de matrimonio", "A clear photo or scan is enough for now.", "Por ahora basta una foto o escaneo claro."),
    "w7.w2": ("W-2 (wages)", "W-2 (salarios)", "Upload each W-2 exactly as you received it.", "Sube cada W-2 tal como lo recibiste."),
    "w7.income_records": ("Proof of your income", "Comprobantes de tus ingresos",
                          "You can upload invoices, payment receipts, statements or other documents that help show how much you earned during the year.",
                          "Puedes subir facturas, recibos de pago, estados de cuenta u otros documentos que ayuden a mostrar cuánto ganaste durante el año."),
    "w7.name_change": ("Name change document", "Documento de cambio de nombre",
                       "If the name changed, upload the marriage certificate or the court order. A clear photo is enough for now.",
                       "Si el nombre cambió, sube el acta de matrimonio o la orden del tribunal. Por ahora basta una foto clara."),
}
BIRTH_CERT_TEXT = (("Birth certificate", "Acta de nacimiento"),
                   ("Upload a photo now. The original birth certificate is also needed.", "Sube una foto ahora. También se necesita el acta de nacimiento original."),
                   ("Upload a clear photo or scan. It helps OG document the family relationship.", "Sube una foto o escaneo claro. Ayuda a OG a documentar el parentesco."))
ALT_TEXT = ("Upload a clear photo. OG will tell you if this document is enough and how to bring the original.",
            "Sube una foto clara. OG te dirá si este documento es suficiente y cómo entregar el original.")
RES_TEXT = {
    "medical_record": ("It should show the child's name, date of birth and address, the date of the visit (within the last 12 months), and the doctor's name and clinic address.",
                       "Debe mostrar el nombre, la fecha de nacimiento y la dirección del niño, la fecha de la visita (dentro de los últimos 12 meses), y el nombre del médico y la dirección de la clínica."),
    "school_record": ("It should show the student's name and address, grades or attendance, the school's name and address, and the school term dates (ending within the last 12 months).",
                      "Debe mostrar el nombre y la dirección del estudiante, sus calificaciones o asistencia, el nombre y la dirección de la escuela, y las fechas del período escolar (que terminen dentro de los últimos 12 meses)."),
    "_default": ("Upload a clear photo. It should show the person's name and U.S. address.", "Sube una foto clara. Debe mostrar el nombre y la dirección en EE. UU. de la persona."),
}
RES_SUFFIX = ("proof of U.S. residency", "prueba de residencia en EE. UU.")

# ---- short "Before you start" page and the income note (customer wording; internal rules unchanged)
INTRO_LEAD = ("We'll collect the information OG needs to prepare your ITIN application and tax return.",
              "Vamos a reunir la información que OG necesita para preparar tu solicitud de ITIN y tu declaración de impuestos.")
INTRO_TIPS = ("📘 If you have your passport, you can upload it to complete your information faster.<br>⏰ Don't have it right now? No problem. You can continue and upload it later.",
              "📘 Si tienes tu pasaporte, podrás subirlo para completar tus datos más rápido.<br>⏰ ¿No lo tienes ahora? No hay problema. Puedes continuar y subirlo después.")
INTRO_SAVED = ("Your answers are saved automatically.", "Tus respuestas se guardan automáticamente.")
INTRO_NOTE = ("The IRS makes the final decision on ITIN applications. Sending your information to OG does not mean your ITIN has been approved.",
              "El IRS toma la decisión final sobre la solicitud de ITIN. Enviar tu información a OG no significa que el ITIN haya sido aprobado.")
GROSS_NOTE = ("Enter <strong>ALL the income you earned</strong> during the year, <strong>even if it was a small amount</strong>. For example, if you only earned $500, enter $500. Do not leave income out because you think the amount is too small.",
              "Escribe <strong>TODO lo que ganaste</strong> durante el año, <strong>aunque haya sido poco</strong>. Por ejemplo, si solo ganaste $500, escribe $500. No dejes este ingreso fuera por pensar que es muy poco.")
GROSS_NOTE2 = ("OG will use your income and other information to prepare your tax return correctly and determine any applicable taxes.",
               "OG usará tus ingresos y demás información para preparar correctamente tu declaración y determinar los impuestos que correspondan.")
