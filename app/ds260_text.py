"""DS-260 text: the Security & Background question tables, option lists and reconciliation notes.

SOURCE: the Department of State "Immigrant Visa and Alien Registration Application (DS-260)" SAMPLE, Bureau of Consular Affairs, Consular Systems and
Technology, October 2019 (111 pages, supplied), read page by page. Newer official Department of State material reconciled where it could be reached
(Federal Register 30-day notice 2025-20231 for OMB 1405-0185, reginfo.gov ICR 202605-1405-003 / 202606-1405-004, DOS/NVC public pages mirrored on
adoptions.state.gov). The June-2023 official sample and the live CEAC screens could NOT be retrieved (travel.state.gov blocks automated access): the
CEAC-facing wording of every question is therefore the 2019 wording unless a newer official source says otherwise, and the staff member who enters
the answers in CEAC always reads the live CEAC question. English is the official language of the DS-260; Spanish here is OG's courtesy translation.

Each Security & Background question is one row: (key, section, en, es, explain_on). `explain_on` is "yes" (a Yes needs an explanation) or "no" (the
vaccination question is INVERTED in the sample: the explanation box appears when the answer is No). No wording anywhere concludes inadmissibility,
ineligibility or a waiver: a Yes is "OG should review this answer".
"""

SEC_MEDICAL = [
    ("sec_med_1", "Do you have a communicable disease of public health significance such as tuberculosis (TB)?",
     "¿Tienes una enfermedad transmisible de importancia para la salud pública, como la tuberculosis (TB)?", "yes"),
    ("sec_med_2", "Do you have documentation to establish that you have received vaccinations in accordance with U.S. law?",
     "¿Tienes documentación que demuestre que has recibido las vacunas de acuerdo con la ley de EE. UU.?", "no"),
    ("sec_med_3", "Do you have a mental or physical disorder that poses or is likely to pose a threat to the safety or welfare of yourself or others?",
     "¿Tienes un trastorno mental o físico que representa o es probable que represente una amenaza para la seguridad o el bienestar de ti mismo(a) o de otras personas?", "yes"),
    ("sec_med_4", "Are you or have you ever been a drug abuser or addict?",
     "¿Eres o has sido alguna vez una persona que abusa de las drogas o adicta a ellas?", "yes"),
]

SEC_CRIMINAL = [
    ("sec_crim_1", "Have you ever been arrested or convicted for any offense or crime, even though subject of a pardon, amnesty, or other similar action?",
     "¿Alguna vez has sido arrestado(a) o condenado(a) por algún delito o infracción, aunque haya sido objeto de un indulto, amnistía u otra acción similar?", "yes"),
    ("sec_crim_2", "Have you ever violated, or engaged in a conspiracy to violate, any law relating to controlled substances?",
     "¿Alguna vez has violado, o participado en una conspiración para violar, alguna ley relacionada con sustancias controladas?", "yes"),
    ("sec_crim_3", "Are you the spouse, son, or daughter of an individual who has violated any controlled substance trafficking law, and have knowingly benefited from the trafficking activities in the past five years?",
     "¿Eres cónyuge, hijo(a) de una persona que ha violado alguna ley sobre tráfico de sustancias controladas y te has beneficiado a sabiendas de las actividades de tráfico en los últimos cinco años?", "yes"),
    ("sec_crim_4", "Are you coming to the United States to engage in prostitution or unlawful commercialized vice or have you been engaged in prostitution or procuring prostitutes within the past 10 years?",
     "¿Vienes a los Estados Unidos a dedicarte a la prostitución o al vicio comercializado ilegal, o te has dedicado a la prostitución o a procurar prostitutas en los últimos 10 años?", "yes"),
    ("sec_crim_5", "Have you ever been involved in, or do you seek to engage in, money laundering?",
     "¿Alguna vez has estado involucrado(a) en el lavado de dinero, o buscas participar en él?", "yes"),
    ("sec_crim_6", "Have you ever committed or conspired to commit a human trafficking offense in the United States or outside the United States?",
     "¿Alguna vez has cometido o conspirado para cometer un delito de trata de personas en los Estados Unidos o fuera de ellos?", "yes"),
    ("sec_crim_7", "Have you ever knowingly aided, abetted, assisted, or colluded with an individual who has been identified by the President of the United States as a person who plays a significant role in a severe form of trafficking in persons?",
     "¿Alguna vez has ayudado, instigado, asistido o actuado en connivencia, a sabiendas, con una persona identificada por el Presidente de los Estados Unidos como alguien que desempeña un papel importante en una forma grave de trata de personas?", "yes"),
    ("sec_crim_8", "Are you the spouse, son, or daughter of an individual who has committed or conspired to commit a human trafficking offense in the United States or outside the United States and have you within the last five years, knowingly benefited from the trafficking activities?",
     "¿Eres cónyuge, hijo(a) de una persona que ha cometido o conspirado para cometer un delito de trata de personas en los Estados Unidos o fuera de ellos y, en los últimos cinco años, te has beneficiado a sabiendas de las actividades de trata?", "yes"),
]

SEC_SECURITY1 = [
    ("sec_s1_1", "Do you seek to engage in espionage, sabotage, export control violations, or any other illegal activity while in the United States?",
     "¿Buscas participar en espionaje, sabotaje, violaciones de control de exportaciones o cualquier otra actividad ilegal mientras estés en los Estados Unidos?", "yes"),
    ("sec_s1_2", "Do you seek to engage in terrorist activities while in the United States or have you ever engaged in terrorist activities?",
     "¿Buscas participar en actividades terroristas mientras estés en los Estados Unidos o has participado alguna vez en actividades terroristas?", "yes"),
    ("sec_s1_3", "Have you ever or do you intend to provide financial assistance or other support to terrorists or terrorist organizations?",
     "¿Alguna vez has proporcionado, o tienes la intención de proporcionar, asistencia financiera u otro apoyo a terroristas o a organizaciones terroristas?", "yes"),
    ("sec_s1_4", "Are you the spouse, son, or daughter of an individual who has engaged in terrorist activity, including providing financial assistance or other support to terrorists or terrorist organizations, in the last five years?",
     "¿Eres cónyuge, hijo(a) de una persona que ha participado en actividades terroristas, incluido proporcionar asistencia financiera u otro apoyo a terroristas o a organizaciones terroristas, en los últimos cinco años?", "yes"),
    ("sec_s1_5", "Are you a member or representative of a terrorist organization?",
     "¿Eres miembro o representante de una organización terrorista?", "yes"),
    ("sec_s1_6", "Have you ever ordered, incited, committed, assisted, or otherwise participated in genocide?",
     "¿Alguna vez has ordenado, incitado, cometido, ayudado o participado de otra manera en un genocidio?", "yes"),
    ("sec_s1_7", "Have you ever committed, ordered, incited, assisted, or otherwise participated in torture?",
     "¿Alguna vez has cometido, ordenado, incitado, ayudado o participado de otra manera en actos de tortura?", "yes"),
    ("sec_s1_8", "Have you committed, ordered, incited, assisted, or otherwise participated in extrajudicial killings, political killings, or other acts of violence?",
     "¿Has cometido, ordenado, incitado, ayudado o participado de otra manera en ejecuciones extrajudiciales, asesinatos políticos u otros actos de violencia?", "yes"),
    ("sec_s1_9", "Have you ever engaged in the recruitment of or the use of child soldiers?",
     "¿Alguna vez has participado en el reclutamiento o en el uso de niños soldados?", "yes"),
    ("sec_s1_10", "Have you, while serving as a government official, been responsible for or directly carried out, at any time, particularly severe violations of religious freedom?",
     "¿Has sido, mientras ejercías como funcionario(a) del gobierno, responsable o has llevado a cabo directamente, en cualquier momento, violaciones particularmente graves de la libertad religiosa?", "yes"),
]

SEC_SECURITY2 = [
    ("sec_s2_1", "Are you a member of or affiliated with the Communist or other totalitarian party?",
     "¿Eres miembro del Partido Comunista o de otro partido totalitario, o estás afiliado(a) a ellos?", "yes"),
    ("sec_s2_2", "Have you ever directly or indirectly assisted or supported any of the groups in Colombia known as the Revolutionary Armed Forces of Colombia (FARC), National Liberation Army (ELN), or United Self-Defense Forces of Colombia (AUC)?",
     "¿Alguna vez has ayudado o apoyado, directa o indirectamente, a alguno de los grupos de Colombia conocidos como las Fuerzas Armadas Revolucionarias de Colombia (FARC), el Ejército de Liberación Nacional (ELN) o las Autodefensas Unidas de Colombia (AUC)?", "yes"),
    ("sec_s2_3", "Have you ever, through abuse of governmental or political position converted for personal gain, confiscated or expropriated property in a foreign nation to which a United States national had claim of ownership?",
     "¿Alguna vez, mediante abuso de un cargo gubernamental o político, has convertido en beneficio personal, confiscado o expropiado bienes en una nación extranjera sobre los cuales un nacional de los Estados Unidos tenía un reclamo de propiedad?", "yes"),
    ("sec_s2_4", "Are you the spouse, minor child, or agent of an individual who has through abuse of governmental or political position converted for personal gain, confiscated or expropriated property in a foreign nation to which a United States national had claim of ownership?",
     "¿Eres cónyuge, hijo(a) menor o agente de una persona que, mediante abuso de un cargo gubernamental o político, ha convertido en beneficio personal, confiscado o expropiado bienes en una nación extranjera sobre los cuales un nacional de los Estados Unidos tenía un reclamo de propiedad?", "yes"),
    ("sec_s2_5", "Have you ever been directly involved in the establishment or enforcement of population controls forcing a woman to undergo an abortion against her free choice or a man or a woman to undergo sterilization against his or her free choice?",
     "¿Alguna vez has estado directamente involucrado(a) en el establecimiento o la aplicación de controles de población que obliguen a una mujer a someterse a un aborto contra su libre elección, o a un hombre o una mujer a someterse a una esterilización contra su libre elección?", "yes"),
    ("sec_s2_6", "Have you ever disclosed or trafficked in confidential U.S. business information obtained in connection with U.S. participation in the Chemical Weapons Convention?",
     "¿Alguna vez has divulgado o traficado con información comercial confidencial de EE. UU. obtenida en relación con la participación de EE. UU. en la Convención sobre las Armas Químicas?", "yes"),
    ("sec_s2_7", "Are you the spouse, minor child, or agent of an individual who has disclosed or trafficked in confidential U.S. business information obtained in connection with U.S. participation in the Chemical Weapons Convention?",
     "¿Eres cónyuge, hijo(a) menor o agente de una persona que ha divulgado o traficado con información comercial confidencial de EE. UU. obtenida en relación con la participación de EE. UU. en la Convención sobre las Armas Químicas?", "yes"),
]

# Immigration Law Violations 1: the first two questions are shown to everyone; the rest only to applicants who have been to the U.S.
SEC_IMM1_ALL = [
    ("sec_i1_1", "Have you ever sought to obtain or assist others to obtain a visa, entry into the United States, or any other United States immigration benefit by fraud or willful misrepresentation or other unlawful means?",
     "¿Alguna vez has tratado de obtener, o ayudado a otros a obtener, una visa, la entrada a los Estados Unidos o cualquier otro beneficio migratorio de EE. UU. mediante fraude, tergiversación deliberada u otros medios ilegales?", "yes"),
    ("sec_i1_2", "Have you ever been removed or deported from any country?",
     "¿Alguna vez has sido expulsado(a) o deportado(a) de algún país?", "yes"),
]
SEC_IMM1_US = [
    ("sec_i1_3", "Have you ever been the subject of a removal or deportation hearing?",
     "¿Alguna vez has sido objeto de una audiencia de expulsión o deportación?", "yes"),
    ("sec_i1_4", "Have you failed to attend a hearing on removability or inadmissibility within the last five years?",
     "¿Has dejado de asistir a una audiencia sobre expulsabilidad o inadmisibilidad en los últimos cinco años?", "yes"),
    ("sec_i1_5", "Have you ever been unlawfully present, overstayed the amount of time granted by an immigration official or otherwise violated the terms of a U.S. visa?",
     "¿Alguna vez has estado presente ilegalmente, has excedido el tiempo otorgado por un funcionario de inmigración o has violado de otro modo los términos de una visa de EE. UU.?", "yes"),
    ("sec_i1_6", "Are you subject to a civil penalty under INA 274C?",
     "¿Estás sujeto(a) a una sanción civil bajo la sección 274C de la INA?", "yes"),
    ("sec_i1_7", "Have you been ordered removed from the U.S. during the last five years?",
     "¿Te han ordenado la expulsión de los EE. UU. durante los últimos cinco años?", "yes"),
    ("sec_i1_8", "Have you been ordered removed from the U.S. for a second time within the last 20 years?",
     "¿Te han ordenado la expulsión de los EE. UU. por segunda vez en los últimos 20 años?", "yes"),
]
SEC_IMM2 = [
    ("sec_i2_1", "Have you ever been unlawfully present and ordered removed from the U.S. during the last ten years?",
     "¿Alguna vez has estado presente ilegalmente y te han ordenado la expulsión de los EE. UU. durante los últimos diez años?", "yes"),
    ("sec_i2_2", "Have you ever been convicted of an aggravated felony and been ordered removed from the U.S.?",
     "¿Alguna vez has sido condenado(a) por un delito grave agravado y te han ordenado la expulsión de los EE. UU.?", "yes"),
    ("sec_i2_3", "Have you ever been unlawfully present in the U.S. for more than 180 days (but no more than one year) and have voluntarily departed the U.S. within the last three years?",
     "¿Alguna vez has estado presente ilegalmente en los EE. UU. por más de 180 días (pero no más de un año) y has salido voluntariamente de los EE. UU. en los últimos tres años?", "yes"),
    ("sec_i2_4", "Have you ever been unlawfully present in the U.S. for more than one year or more than one year in the aggregate at any time during the last 10 years?",
     "¿Alguna vez has estado presente ilegalmente en los EE. UU. por más de un año, o por más de un año en total, en cualquier momento durante los últimos 10 años?", "yes"),
]

SEC_MISC1 = [
    ("sec_m1_1", "Have you ever withheld custody of a U.S. citizen child outside the United States from a person granted legal custody by a U.S. court?",
     "¿Alguna vez has retenido fuera de los Estados Unidos la custodia de un(a) niño(a) ciudadano(a) de EE. UU. de una persona a quien un tribunal de EE. UU. otorgó la custodia legal?", "yes"),
    ("sec_m1_2", "Have you ever intentionally assisted another person in withholding custody of a U.S. citizen child outside the United States from a person granted legal custody by a U.S. court?",
     "¿Alguna vez has ayudado intencionalmente a otra persona a retener fuera de los Estados Unidos la custodia de un(a) niño(a) ciudadano(a) de EE. UU. de una persona a quien un tribunal de EE. UU. otorgó la custodia legal?", "yes"),
    ("sec_m1_3", "Have you voted in the United States in violation of any law or regulation?",
     "¿Has votado en los Estados Unidos violando alguna ley o reglamento?", "yes"),
    ("sec_m1_4", "Have you ever renounced United States citizenship for the purpose of avoiding taxation?",
     "¿Alguna vez has renunciado a la ciudadanía de los Estados Unidos con el fin de evitar impuestos?", "yes"),
    ("sec_m1_5", "Have you attended a public elementary school or a public secondary school on student (F) status after November 30, 1996 without reimbursing the school?",
     "¿Has asistido a una escuela primaria pública o a una escuela secundaria pública con estatus de estudiante (F) después del 30 de noviembre de 1996 sin reembolsar a la escuela?", "yes"),
    ("sec_m1_6", "Do you seek to enter the United States for the purpose of performing skilled or unskilled labor but have not yet been certified by the Secretary of Labor?",
     "¿Buscas entrar a los Estados Unidos para realizar trabajo calificado o no calificado, pero aún no has sido certificado(a) por el Secretario de Trabajo?", "yes"),
    ("sec_m1_7", "Are you a graduate of a foreign medical school seeking to perform medical services in the United States but have not yet passed the National Board of Medical Examiners examination or its equivalent?",
     "¿Eres graduado(a) de una escuela de medicina extranjera que busca prestar servicios médicos en los Estados Unidos pero aún no ha aprobado el examen de la Junta Nacional de Examinadores Médicos o su equivalente?", "yes"),
]

SEC_MISC2 = [
    ("sec_m2_1", "Are you a health care worker seeking to perform such work in the United States but have not yet received certification from the Commission on Graduates of Foreign Nursing Schools or from an equivalent approved independent credentialing organization?",
     "¿Eres trabajador(a) de la salud que busca realizar ese trabajo en los Estados Unidos pero aún no ha recibido la certificación de la Comisión de Graduados de Escuelas de Enfermería Extranjeras o de una organización independiente de acreditación equivalente aprobada?", "yes"),
    ("sec_m2_2", "Are you permanently ineligible for U.S. citizenship?",
     "¿Eres permanentemente inelegible para la ciudadanía de EE. UU.?", "yes"),
    ("sec_m2_3", "Have you ever departed the United States in order to evade military service during a time of war?",
     "¿Alguna vez saliste de los Estados Unidos para evadir el servicio militar durante un tiempo de guerra?", "yes"),
    ("sec_m2_4", "Are you coming to the U.S. to practice polygamy?",
     "¿Vienes a los EE. UU. a practicar la poligamia?", "yes"),
    ("sec_m2_5", "Are you a former exchange visitor (J) who has not yet fulfilled the two-year foreign residence requirement?",
     "¿Eres un(a) ex visitante de intercambio (J) que aún no ha cumplido el requisito de residencia en el extranjero de dos años?", "yes"),
    ("sec_m2_6", "Has an immigration judge or the Board of Immigration Appeals ever determined that you knowingly made a frivolous application for asylum?",
     "¿Alguna vez un juez de inmigración o la Junta de Apelaciones de Inmigración ha determinado que presentaste a sabiendas una solicitud de asilo frívola?", "yes"),
    ("sec_m2_7", "Are you likely to become a public charge after you are admitted to the United States?",
     "¿Es probable que te conviertas en una carga pública después de ser admitido(a) en los Estados Unidos?", "yes"),
]

# Wording reconciliation recorded for the coverage document (2019 sample vs newer official source).
SEC_NOTES = {
    "sec_m2_6": ("2019 sample: “Has the Secretary of Homeland Security of the United States ever determined that you knowingly made a frivolous application for asylum?”. "
                 "Federal Register 30-day notice 2025-20231 (OMB 1405-0185) says the question now refers to “an immigration judge or Board of Immigration Appeals”. OG uses the newer "
                 "official reference; the exact CEAC sentence could not be retrieved, so staff read the live CEAC question."),
    "sec_s1_4": "Present on the 2019 sample's ‘No’ screen (p. 77) but missing from its ‘Yes’ screen (p. 78): an internal inconsistency in the sample. Kept, because it is a real question on the ‘No’ screen.",
    "sec_med_2": "Inverted polarity in the sample: the explanation box appears when the answer is No (the applicant has no vaccination documentation).",
}

SECURITY_GROUPS = [
    # (group key, CEAC section, English title, Spanish title, questions)
    ("medical", "Security and Background: Medical and Health", "Health", "Salud", SEC_MEDICAL),
    ("criminal", "Security and Background: Criminal", "Criminal history", "Antecedentes penales", SEC_CRIMINAL),
    ("security1", "Security and Background: Security 1", "Security (1 of 2)", "Seguridad (1 de 2)", SEC_SECURITY1),
    ("security2", "Security and Background: Security 2", "Security (2 of 2)", "Seguridad (2 de 2)", SEC_SECURITY2),
    ("immig1", "Security and Background: Immigration Law Violations 1", "Immigration history", "Historial migratorio", SEC_IMM1_ALL + SEC_IMM1_US),
    ("immig2", "Security and Background: Immigration Law Violations 2", "Immigration history (continued)", "Historial migratorio (continuación)", SEC_IMM2),
    ("misc1", "Security and Background: Miscellaneous 1", "Other questions (1 of 2)", "Otras preguntas (1 de 2)", SEC_MISC1),
    ("misc2", "Security and Background: Miscellaneous 2", "Other questions (2 of 2)", "Otras preguntas (2 de 2)", SEC_MISC2),
]
SECURITY_IN_US_ONLY = {k for k, *_ in SEC_IMM1_US} | {k for k, *_ in SEC_IMM2}

SECURITY_NOTE = (
    "These questions come straight from the Department of State application (DS-260). Some are sensitive. A “Yes” does not by itself mean anything about your case: OG reviews every “Yes” with you privately before anything is entered anywhere. "
    "Your answers here are visible only to you and OG staff who work on your case, never in summaries, other people's applications, or lists.",
    "Estas preguntas vienen directamente de la solicitud del Departamento de Estado (DS-260). Algunas son delicadas. Un “Sí” no significa por sí solo nada sobre tu caso: OG revisa contigo en privado cada “Sí” antes de ingresar algo en cualquier lugar. "
    "Tus respuestas aquí solo las ven tú y el personal de OG que trabaja en tu caso, nunca en resúmenes, en solicitudes de otras personas ni en listas.")

# ------------------------------------------------------------------ option lists
MARITAL = [("married", "Married", "Casado(a)"), ("single", "Single (never married)", "Soltero(a) (nunca casado(a))"), ("widowed", "Widowed", "Viudo(a)"),
           ("divorced", "Divorced", "Divorciado(a)"), ("separated", "Legally separated", "Legalmente separado(a)"), ("annulled", "Marriage annulled", "Matrimonio anulado")]
SEX = [("male", "Male", "Masculino"), ("female", "Female", "Femenino")]
DOC_TYPES = [("passport", "Passport", "Pasaporte"), ("other", "Other travel document", "Otro documento de viaje")]

PETITIONER_RELATIONS = [
    ("father", "Father", "Padre"), ("mother", "Mother", "Madre"), ("brother", "Brother", "Hermano"), ("sister", "Sister", "Hermana"), ("spouse", "Spouse", "Cónyuge"),
    ("child", "Child", "Hijo(a)"), ("stepfather", "Stepfather", "Padrastro"), ("stepmother", "Stepmother", "Madrastra"), ("uncle", "Uncle", "Tío"), ("aunt", "Aunt", "Tía"),
    ("grandparent", "Grandparent", "Abuelo(a)"), ("inlaw", "In-law", "Pariente político"), ("employer", "Employer", "Empleador"),
    ("prospective_employer", "Prospective employer", "Empleador prospectivo"), ("self", "Myself (I filed my own petition)", "Yo mismo(a) (presenté mi propia petición)"),
    ("other", "Other", "Otro")]
PETITIONER_INDIVIDUAL = {"father", "mother", "brother", "sister", "spouse", "child", "stepfather", "stepmother", "uncle", "aunt", "grandparent", "inlaw"}
PETITIONER_ORG = {"employer", "prospective_employer", "other"}  # the 2019 sample shows the organization layout (plus “Specify Other”) for these

OCCUPATIONS = [
    ("agriculture", "Agriculture", "Agricultura"), ("business", "Business", "Negocios"), ("communications", "Communications", "Comunicaciones"),
    ("computer_science", "Computer Science", "Ciencias de la computación"), ("culinary", "Culinary / Food Services", "Culinaria / Servicios de alimentos"),
    ("education", "Education", "Educación"), ("engineering", "Engineering", "Ingeniería"), ("government", "Government", "Gobierno"), ("homemaker", "Homemaker", "Ama(o) de casa"),
    ("legal", "Legal Profession", "Profesión legal"), ("medical", "Medical / Health", "Medicina / Salud"), ("military", "Military", "Militar"),
    ("natural_science", "Natural Science", "Ciencias naturales"), ("physical_science", "Physical Sciences", "Ciencias físicas"), ("religious", "Religious Vocation", "Vocación religiosa"),
    ("research", "Research", "Investigación"), ("retired", "Retired", "Jubilado(a)"), ("not_employed", "Not Employed", "Sin empleo"), ("social_science", "Social Science", "Ciencias sociales"),
    ("student", "Student", "Estudiante"), ("other", "Other", "Otro")]
OCC_NO_EMPLOYER = {"homemaker", "retired", "not_employed"}  # 2019 sample: no employer/school block for these

TERMINATIONS = [("death", "Death of spouse", "Fallecimiento del cónyuge"), ("divorce", "Divorce", "Divorcio"), ("annulment", "Annulment", "Anulación"), ("other", "Other", "Otro")]
STAY_UNITS = [("days", "Day(s)", "Día(s)"), ("weeks", "Week(s)", "Semana(s)"), ("months", "Month(s)", "Mes(es)"), ("years", "Year(s)", "Año(s)"), ("lt24", "Less than 24 hours", "Menos de 24 horas")]
SPOUSE_ADDRESS = [("same", "Same as my present address", "La misma que mi dirección actual"), ("other", "A different address", "Una dirección diferente")]
YES_NO = [("yes", "Yes", "Sí"), ("no", "No", "No")]
YES_NO_UNSURE = YES_NO + [("unsure", "I am not sure — OG will review", "No estoy seguro(a) — OG lo revisará")]
CHILD_LIVES = [("yes", "Yes — lives with me", "Sí — vive conmigo"), ("no", "No", "No")]
CHILD_IMMIGRATING = [("now", "Yes — immigrating with me now", "Sí — inmigra conmigo ahora"), ("later", "Later (separate application)", "Más adelante (solicitud aparte)"),
                     ("no", "No", "No"), ("unsure", "Not sure — OG will review", "No estoy seguro(a) — OG lo revisará")]

# ------------------------------------------------------------------ static screens (English is official; Spanish is a courtesy)
ENGLISH_NOTE = (
    "The DS-260 is completed in English. The Department of State asks for answers in English and English characters only (for example Muñoz is entered as Munoz), unless a question asks for your native alphabet. "
    "You may answer here in Spanish — OG will prepare the English CEAC answers and mark anything that needs a human translation. Spanish text here is never pasted into CEAC as is.",
    "El DS-260 se completa en inglés. El Departamento de Estado pide las respuestas en inglés y solo con caracteres del inglés (por ejemplo, Muñoz se escribe Munoz), salvo que una pregunta pida tu alfabeto nativo. "
    "Puedes responder aquí en español: OG preparará las respuestas en inglés para CEAC y marcará lo que necesite traducción humana. El texto en español de aquí nunca se pega tal cual en CEAC.")

CEAC_ONLY_NOTE = (
    "The final steps of the DS-260 happen only in the Department of State's CEAC system: the applicant's own review, the E-signature and certification, and the “Sign and Submit” button. "
    "OG does not sign, certify or submit for you, does not ask for your CEAC password, and “Send to OG” is not a CEAC submission. After the DS-260 is submitted, only the appropriate government office can reopen it if something has to change.",
    "Los pasos finales del DS-260 se realizan solo en el sistema CEAC del Departamento de Estado: la revisión del propio solicitante, la firma electrónica y certificación, y el botón “Sign and Submit”. "
    "OG no firma, no certifica ni envía por ti, no te pide tu contraseña de CEAC, y “Enviar a OG” no es enviar a CEAC. Después de enviar el DS-260, solo la oficina gubernamental correspondiente puede reabrirlo si algo debe cambiar.")

SIGN_CERT_EN = ("By clicking “Sign and Submit Application” in CEAC the applicant electronically signs and certifies that the answers are true and correct, under penalty of perjury (28 U.S.C. 1746). "
                "This happens only in CEAC and only by the applicant; OG never does it and this intake never records it.")
SIGN_CERT_ES = ("Al hacer clic en “Sign and Submit Application” en CEAC, el solicitante firma electrónicamente y certifica que las respuestas son verdaderas y correctas, bajo pena de perjurio (28 U.S.C. 1746). "
                "Esto ocurre solo en CEAC y solo por el solicitante; OG nunca lo hace y este formulario nunca lo registra.")

# FGM/C certification: the 2019 sample lists 27 countries. Newer official sources could not be retrieved, so the list is a discrepancy to verify, never a rule.
FGMC_2019 = {"benin", "burkina faso", "cameroon", "central african republic", "chad", "cote d'ivoire", "democratic republic of the congo", "djibouti", "egypt", "eritrea", "ethiopia", "gambia",
             "ghana", "guinea", "guinea-bissau", "iraq", "kenya", "liberia", "mali", "mauritania", "niger", "nigeria", "senegal", "sierra leone", "somalia", "sudan", "tanzania", "togo", "uganda", "yemen"}

SELECTIVE_SERVICE_EN = "The sample tells male applicants aged 18 to 25 that U.S. law requires them to register with the Selective Service System if a visa is issued. It is information only; nothing is collected about it here."
SELECTIVE_SERVICE_ES = "El ejemplo informa a los solicitantes hombres de 18 a 25 años que la ley de EE. UU. exige registrarse en el Servicio Selectivo si se emite una visa. Es solo información; aquí no se recopila nada al respecto."

MEDICAL_DISCLOSURE_EN = ("Newer Department of State material (Federal Register notice 2025-20231) adds a “Medical Examination Disclosure and Consent” statement about how eMedical information is stored and shared. "
                         "The applicant reads and gives that consent only in CEAC; OG does not collect it.")
MEDICAL_DISCLOSURE_ES = ("Material más reciente del Departamento de Estado (aviso del Federal Register 2025-20231) agrega una declaración de “Divulgación y consentimiento del examen médico” sobre cómo se almacena y comparte la información de eMedical. "
                         "El solicitante la lee y da ese consentimiento solo en CEAC; OG no la recopila.")
