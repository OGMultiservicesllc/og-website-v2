"""OG NJ Driver License Assistance terms (versioned). Acceptance is recorded in the SAME `terms_acceptances` table Tax uses
(`terms_key="nj_driver_license"`) — no new table. Sending information to OG is never filing anything with NJ MVC."""

TERMS_KEY = "nj_driver_license"
VERSION = "dl-v1"

CERTIFICATION = ("I confirm that the information I provided is correct to the best of my knowledge and authorize OG Multiservices to use it to help me prepare for my NJ Driver License.",
                 "Confirmo que la información que di es correcta según mi leal saber y entender, y autorizo a OG Multiservices a usarla para ayudarme a preparar mi Licencia de Conducir de NJ.")
ACCEPTANCE = ("I understand and accept OG Multiservices' Driver License Assistance terms.", "Entiendo y acepto los términos de Asistencia con la Licencia de Conducir de OG Multiservices.")

SECTIONS = [
    (("What OG does", "Qué hace OG"),
     ("OG Multiservices reviews the documents and information you give us and helps you understand your next steps with the New Jersey MVC. Sending your information to OG is not an application to the MVC and does not schedule anything by itself.",
      "OG Multiservices revisa los documentos e información que nos das y te ayuda a entender tus próximos pasos con el MVC de Nueva Jersey. Enviar tu información a OG no es una solicitud al MVC ni programa nada por sí sola.")),
    (("Your part", "Tu parte"),
     ("You are responsible for giving OG complete and correct information and the documents OG asks for. If something is missing, OG will tell you.",
      "Eres responsable de darle a OG información completa y correcta y los documentos que OG te pida. Si falta algo, OG te lo dirá.")),
    (("Price", "Precio"),
     ("The price you see is an estimate based on your answers. OG confirms the final price before doing the work. Some documents need a closer look before OG can give a price.",
      "El precio que ves es un estimado basado en tus respuestas. OG confirma el precio final antes de hacer el trabajo. Algunos documentos necesitan una revisión más de cerca antes de que OG pueda dar un precio.")),
    (("MVC decisions", "Decisiones del MVC"),
     ("OG helps you prepare and understand the process. The New Jersey MVC makes the final decisions about your documents, your appointment and your Driver License. OG cannot guarantee appointment availability, MVC approval, or any specific outcome.",
      "OG te ayuda a preparar y entender el proceso. El MVC de Nueva Jersey toma las decisiones finales sobre tus documentos, tu cita y tu licencia de conducir. OG no puede garantizar disponibilidad de citas, aprobación del MVC, ni ningún resultado específico.")),
    (("Your information", "Tu información"),
     ("OG uses your information and documents only to provide the services you request, keeps them private and protects them. OG staff who work on your case can see them.",
      "OG usa tu información y tus documentos solo para dar los servicios que solicitas, los mantiene privados y los protege. El personal de OG que trabaja en tu caso puede verlos.")),
]


def version_for():
    return VERSION
