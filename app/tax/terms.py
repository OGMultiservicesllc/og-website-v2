"""OG tax preparation terms (versioned). Acceptance is recorded in `terms_acceptances` (version, timestamp, customer, tax case, language, salted IP hash). A new version is a new
entry here; earlier acceptances keep the version they accepted. The wording is deliberately short; the year-round follow-up promise never becomes unlimited free representation."""

TERMS_KEY = "tax_preparation"
VERSIONS = {2025: "tax-2025-v1"}

CERTIFICATION = ("I confirm that the information I provided is correct to the best of my knowledge and authorize OG Multiservices to use it to prepare my tax return.",
                 "Confirmo que la información que di es correcta según mi leal saber y entender, y autorizo a OG Multiservices a usarla para preparar mi declaración de impuestos.")
ACCEPTANCE = ("I understand and accept OG Multiservices' tax preparation terms.", "Entiendo y acepto los términos de preparación de impuestos de OG Multiservices.")

SECTIONS = [
    (("What OG does", "Qué hace OG"),
     ("OG Multiservices prepares your individual / family income tax return from the information and documents you give us. OG reviews everything before preparing. Sending your information to OG is not filing your return.",
      "OG Multiservices prepara tu declaración de impuestos individual / familiar con la información y los documentos que nos das. OG revisa todo antes de preparar. Enviar tu información a OG no es presentar tu declaración.")),
    (("Your part", "Tu parte"),
     ("You are responsible for giving OG complete and correct information and the documents OG asks for. If something is missing, OG will tell you, and preparation cannot finish until the necessary information arrives. Keep your original records.",
      "Eres responsable de darle a OG información completa y correcta y los documentos que OG te pida. Si falta algo, OG te lo dirá, y la preparación no puede terminar hasta recibir la información necesaria. Guarda tus documentos originales.")),
    (("Price", "Precio"),
     ("The price you see is an estimate based on your answers. OG confirms the final preparation fee before preparation begins. If information changes in a way that changes the work, OG will tell you about the new price before continuing. The returning client discount applies only to the preparation fee.",
      "El precio que ves es un estimado basado en tus respuestas. OG confirma el costo final de preparación antes de comenzar. Si la información cambia de manera que cambie el trabajo, OG te avisará del nuevo precio antes de continuar. El descuento de cliente recurrente aplica solo al costo de preparación.")),
    (("Filing and signatures", "Presentación y firmas"),
     ("OG prepares your return and shows it to you. Your return is only filed after you review it and give the required authorization or signature. OG cannot guarantee the amount or the date of any refund, and the IRS and states make their own decisions.",
      "OG prepara tu declaración y te la muestra. Tu declaración solo se presenta después de que la revises y des la autorización o firma requerida. OG no puede garantizar el monto ni la fecha de ningún reembolso, y el IRS y los estados toman sus propias decisiones.")),
    (("Year-round follow-up", "Seguimiento durante todo el año"),
     ("OG is available all year for personalized follow-up on the return we prepare. If you have a question or receive a communication related to your taxes, come back to OG and we will review the next step with you. If OG makes a mistake in preparing your return, we will correct our work at no charge. Some later work is a separate service; if it has an extra cost, we will tell you before doing it.",
      "OG está disponible durante todo el año para dar seguimiento personalizado a la declaración que preparamos. Si tienes una pregunta o recibes una comunicación relacionada con tus taxes, vuelve a OG y revisaremos contigo el siguiente paso. Si OG comete un error al preparar tu declaración, corregiremos nuestro trabajo sin cobrarte. Algunos trabajos posteriores son un servicio aparte; si tienen un costo adicional, te lo diremos antes de hacerlos.")),
    (("Your information", "Tu información"),
     ("OG uses your information and documents only to provide the services you request, keeps them private and protects them. OG staff who work on your case can see them.",
      "OG usa tu información y tus documentos solo para dar los servicios que solicitas, los mantiene privados y los protege. El personal de OG que trabaja en tu caso puede verlos.")),
]


def version_for(year):
    return VERSIONS.get(int(year), f"tax-{year}-v1")
