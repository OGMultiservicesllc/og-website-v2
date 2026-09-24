"""OG Consent to Travel terms (versioned). Acceptance is recorded in `terms_acceptances` (shared table, same
as Tax/NJ Driver License). All notarizations are in person, by confirmed appointment only — nothing here
implies an online/remote notarization, and picking a location does not confirm an appointment."""

TERMS_KEY = "consent_travel"
VERSION = "consent-travel-v1"

CERTIFICATION = ("I confirm that the information I provided is correct to the best of my knowledge and authorize OG Multiservices to prepare my Consent to Travel Authorization document(s) based on it.",
                 "Confirmo que la información que proporcioné es correcta según mi leal saber y entender, y autorizo a OG Multiservices a preparar mi(s) documento(s) de Autorización de Viaje con base en ella.")
ACCEPTANCE = ("I understand and accept OG Multiservices' Consent to Travel preparation terms.", "Entiendo y acepto los términos de preparación de Autorización de Viaje de OG Multiservices.")

SECTIONS = [
    (("What OG does", "Qué hace OG"),
     ("OG Multiservices prepares your Consent to Travel Authorization document(s) from the information and documents you give us, and reviews your case before confirming a price. Sending your information to OG is not an appointment and does not notarize anything.",
      "OG Multiservices prepara tu(s) documento(s) de Autorización de Viaje con la información y los documentos que nos das, y revisa tu caso antes de confirmar un precio. Enviar tu información a OG no es una cita y no notariza nada.")),
    (("Price", "Precio"),
     ("The price you see before sending is an estimate. OG reviews your case and confirms the final price before any payment is requested. Payment is never requested before OG's review is complete.",
      "El precio que ves antes de enviar es un estimado. OG revisa tu caso y confirma el precio final antes de solicitar cualquier pago. Nunca se solicita el pago antes de que OG termine su revisión.")),
    (("Notarization", "Notarización"),
     ("All notarizations are done in person, at the location you select, by confirmed appointment only. Selecting a location does not confirm an appointment — OG will contact you to confirm.",
      "Todas las notarizaciones se realizan en persona, en la ubicación que selecciones, únicamente con cita confirmada. Seleccionar una ubicación no confirma una cita — OG te contactará para confirmarla.")),
    (("Payment", "Pago"),
     ("Payment does not mean your notarization or appointment is completed. OG will confirm your appointment separately.",
      "El pago no significa que tu notarización o cita esté completada. OG confirmará tu cita por separado.")),
    (("Your information", "Tu información"),
     ("OG uses your information and documents only to provide the services you request, keeps them private and protects them. OG staff who work on your case can see them.",
      "OG usa tu información y tus documentos solo para dar los servicios que solicitas, los mantiene privados y los protege. El personal de OG que trabaja en tu caso puede verlos.")),
]


def version_for(*_a, **_kw):
    return VERSION
