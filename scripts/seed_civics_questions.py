"""One-time loader for the official USCIS 2025 Civics Test — 128 Questions and Answers
(uscis.gov/citizenship). English question/answer text is transcribed verbatim from the
official PDF — nothing invented or reworded. Spanish text is an original translation
authored for this project.

Seven questions ask about a CURRENT officeholder or the student's own state/district
(U.S. senators #23, representative #29, Speaker of the House #30, President #38, Vice
President #39, Chief Justice #57, governor #61) — these have no single fixed answer and
change with elections/appointments, so they are loaded INACTIVE with a placeholder
answer. An admin must fill in the current, correct name/answer and flip them Active from
Admin -> Civics Questions before they appear in Practice or Simulation. Question #62
(state capital) is loaded ACTIVE with "Trenton, New Jersey" since OG Multiservices is
based in Paterson, NJ and a state capital is a permanent geographic fact, not an
election-dependent one — an admin can still edit it for a different state.

Run once: .venv/Scripts/python.exe scripts/seed_civics_questions.py
"""

from app import create_app
from app.extensions import db
from app.models import CivicsAnswer, CivicsQuestion

NEEDS_ADMIN_REVIEW = "[Admin: confirm and enter the current answer, then mark this question Active]"
NEEDS_ADMIN_REVIEW_ES = "[Admin: confirme e ingrese la respuesta actual, luego marque esta pregunta como Activa]"

# Each entry: (number, question_en, question_es, required_count, is_active, [(answer_en, answer_es), ...])
QUESTIONS = [
    (1, "What is the form of government of the United States?",
     "¿Cuál es la forma de gobierno de los Estados Unidos?", 1, True, [
        ("Republic", "República"),
        ("Constitution-based federal republic", "República federal basada en la Constitución"),
        ("Representative democracy", "Democracia representativa"),
    ]),
    (2, "What is the supreme law of the land?", "¿Cuál es la ley suprema del país?", 1, True, [
        ("(U.S.) Constitution", "(La) Constitución (de EE. UU.)"),
    ]),
    (3, "Name one thing the U.S. Constitution does.",
     "Mencione una cosa que hace la Constitución de EE. UU.", 1, True, [
        ("Forms the government", "Establece el gobierno"),
        ("Defines powers of government", "Define los poderes del gobierno"),
        ("Defines the parts of government", "Define las partes del gobierno"),
        ("Protects the rights of the people", "Protege los derechos del pueblo"),
    ]),
    (4, 'The U.S. Constitution starts with the words "We the People." What does "We the People" mean?',
     'La Constitución de EE. UU. comienza con las palabras "Nosotros el Pueblo". ¿Qué significa "Nosotros el Pueblo"?', 1, True, [
        ("Self-government", "Autogobierno"),
        ("Popular sovereignty", "Soberanía popular"),
        ("Consent of the governed", "Consentimiento de los gobernados"),
        ("People should govern themselves", "El pueblo debe gobernarse a sí mismo"),
        ("(Example of) social contract", "(Ejemplo de) contrato social"),
    ]),
    (5, "How are changes made to the U.S. Constitution?",
     "¿Cómo se hacen cambios a la Constitución de EE. UU.?", 1, True, [
        ("Amendments", "Enmiendas"),
        ("The amendment process", "El proceso de enmienda"),
    ]),
    (6, "What does the Bill of Rights protect?", "¿Qué protege la Carta de Derechos (Bill of Rights)?", 1, True, [
        ("(The basic) rights of Americans", "Los derechos (básicos) de los estadounidenses"),
        ("(The basic) rights of people living in the United States", "Los derechos (básicos) de las personas que viven en los Estados Unidos"),
    ]),
    (7, "How many amendments does the U.S. Constitution have?",
     "¿Cuántas enmiendas tiene la Constitución de EE. UU.?", 1, True, [
        ("Twenty-seven (27)", "Veintisiete (27)"),
    ]),
    (8, "Why is the Declaration of Independence important?",
     "¿Por qué es importante la Declaración de Independencia?", 1, True, [
        ("It says America is free from British control.", "Declara que Estados Unidos está libre del control británico."),
        ("It says all people are created equal.", "Declara que todas las personas son creadas iguales."),
        ("It identifies inherent rights.", "Identifica derechos inherentes."),
        ("It identifies individual freedoms.", "Identifica libertades individuales."),
    ]),
    (9, "What founding document said the American colonies were free from Britain?",
     "¿Qué documento fundacional declaró que las colonias americanas eran libres de Gran Bretaña?", 1, True, [
        ("Declaration of Independence", "Declaración de Independencia"),
    ]),
    (10, "Name two important ideas from the Declaration of Independence and the U.S. Constitution.",
     "Mencione dos ideas importantes de la Declaración de Independencia y la Constitución de EE. UU.", 2, True, [
        ("Equality", "Igualdad"),
        ("Liberty", "Libertad"),
        ("Social contract", "Contrato social"),
        ("Natural rights", "Derechos naturales"),
        ("Limited government", "Gobierno limitado"),
        ("Self-government", "Autogobierno"),
    ]),
    (11, 'The words "Life, Liberty, and the pursuit of Happiness" are in what founding document?',
     '¿En qué documento fundacional aparecen las palabras "Vida, Libertad y la búsqueda de la Felicidad"?', 1, True, [
        ("Declaration of Independence", "Declaración de Independencia"),
    ]),
    (12, "What is the economic system of the United States?",
     "¿Cuál es el sistema económico de los Estados Unidos?", 1, True, [
        ("Capitalism", "Capitalismo"),
        ("Free market economy", "Economía de mercado libre"),
    ]),
    (13, "What is the rule of law?", "¿Qué es el estado de derecho?", 1, True, [
        ("Everyone must follow the law.", "Todos deben cumplir la ley."),
        ("Leaders must obey the law.", "Los líderes deben obedecer la ley."),
        ("Government must obey the law.", "El gobierno debe obedecer la ley."),
        ("No one is above the law.", "Nadie está por encima de la ley."),
    ]),
    (14, "Many documents influenced the U.S. Constitution. Name one.",
     "Muchos documentos influyeron en la Constitución de EE. UU. Mencione uno.", 1, True, [
        ("Declaration of Independence", "Declaración de Independencia"),
        ("Articles of Confederation", "Artículos de la Confederación"),
        ("Federalist Papers", "Documentos Federalistas"),
        ("Anti-Federalist Papers", "Documentos Antifederalistas"),
        ("Virginia Declaration of Rights", "Declaración de Derechos de Virginia"),
        ("Fundamental Orders of Connecticut", "Órdenes Fundamentales de Connecticut"),
        ("Mayflower Compact", "Pacto del Mayflower"),
        ("Iroquois Great Law of Peace", "Gran Ley de la Paz Iroquesa"),
    ]),
    (15, "There are three branches of government. Why?",
     "Hay tres poderes (ramas) del gobierno. ¿Por qué?", 1, True, [
        ("So one part does not become too powerful", "Para que ninguna parte se vuelva demasiado poderosa"),
        ("Checks and balances", "Pesos y contrapesos"),
        ("Separation of powers", "Separación de poderes"),
    ]),
    (16, "Name the three branches of government.", "Mencione los tres poderes (ramas) del gobierno.", 1, True, [
        ("Legislative, executive, and judicial", "Legislativo, ejecutivo y judicial"),
        ("Congress, president, and the courts", "El Congreso, el presidente y los tribunales"),
    ]),
    (17, "The President of the United States is in charge of which branch of government?",
     "¿El presidente de los Estados Unidos está a cargo de qué poder del gobierno?", 1, True, [
        ("Executive branch", "El poder ejecutivo"),
    ]),
    (18, "What part of the federal government writes laws?",
     "¿Qué parte del gobierno federal escribe las leyes?", 1, True, [
        ("(U.S.) Congress", "El Congreso (de EE. UU.)"),
        ("(U.S. or national) legislature", "La legislatura (nacional)"),
        ("Legislative branch", "El poder legislativo"),
    ]),
    (19, "What are the two parts of the U.S. Congress?",
     "¿Cuáles son las dos partes del Congreso de EE. UU.?", 1, True, [
        ("Senate and House (of Representatives)", "El Senado y la Cámara (de Representantes)"),
    ]),
    (20, "Name one power of the U.S. Congress.", "Mencione un poder del Congreso de EE. UU.", 1, True, [
        ("Writes laws", "Escribe leyes"),
        ("Declares war", "Declara la guerra"),
        ("Makes the federal budget", "Elabora el presupuesto federal"),
    ]),
    (21, "How many U.S. senators are there?", "¿Cuántos senadores de EE. UU. hay?", 1, True, [
        ("One hundred (100)", "Cien (100)"),
    ]),
    (22, "How long is a term for a U.S. senator?", "¿Cuánto dura el período de un senador de EE. UU.?", 1, True, [
        ("Six (6) years", "Seis (6) años"),
    ]),
    (23, "Who is one of your state's U.S. senators now?",
     "¿Quién es uno de los senadores actuales de EE. UU. por su estado?", 1, False, [
        (NEEDS_ADMIN_REVIEW, NEEDS_ADMIN_REVIEW_ES),
    ]),
    (24, "How many voting members are in the House of Representatives?",
     "¿Cuántos miembros con derecho a voto tiene la Cámara de Representantes?", 1, True, [
        ("Four hundred thirty-five (435)", "Cuatrocientos treinta y cinco (435)"),
    ]),
    (25, "How long is a term for a member of the House of Representatives?",
     "¿Cuánto dura el período de un miembro de la Cámara de Representantes?", 1, True, [
        ("Two (2) years", "Dos (2) años"),
    ]),
    (26, "Why do U.S. representatives serve shorter terms than U.S. senators?",
     "¿Por qué los representantes de EE. UU. sirven períodos más cortos que los senadores?", 1, True, [
        ("To more closely follow public opinion", "Para seguir más de cerca la opinión pública"),
    ]),
    (27, "How many senators does each state have?", "¿Cuántos senadores tiene cada estado?", 1, True, [
        ("Two (2)", "Dos (2)"),
    ]),
    (28, "Why does each state have two senators?", "¿Por qué cada estado tiene dos senadores?", 1, True, [
        ("Equal representation (for small states)", "Representación igualitaria (para los estados pequeños)"),
        ("The Great Compromise (Connecticut Compromise)", "El Gran Compromiso (Compromiso de Connecticut)"),
    ]),
    (29, "Name your U.S. representative.", "Mencione a su representante de EE. UU.", 1, False, [
        (NEEDS_ADMIN_REVIEW, NEEDS_ADMIN_REVIEW_ES),
    ]),
    (30, "What is the name of the Speaker of the House of Representatives now?",
     "¿Cuál es el nombre del actual presidente de la Cámara de Representantes (Speaker of the House)?", 1, False, [
        (NEEDS_ADMIN_REVIEW, NEEDS_ADMIN_REVIEW_ES),
    ]),
    (31, "Who does a U.S. senator represent?", "¿A quién representa un senador de EE. UU.?", 1, True, [
        ("Citizens of their state", "A los ciudadanos de su estado"),
        ("People of their state", "A las personas de su estado"),
    ]),
    (32, "Who elects U.S. senators?", "¿Quién elige a los senadores de EE. UU.?", 1, True, [
        ("Citizens from their state", "Los ciudadanos de su estado"),
    ]),
    (33, "Who does a member of the House of Representatives represent?",
     "¿A quién representa un miembro de la Cámara de Representantes?", 1, True, [
        ("Citizens in their (congressional) district", "A los ciudadanos de su distrito (congresional)"),
        ("Citizens in their district", "A los ciudadanos de su distrito"),
        ("People from their (congressional) district", "A las personas de su distrito (congresional)"),
        ("People in their district", "A las personas de su distrito"),
    ]),
    (34, "Who elects members of the House of Representatives?",
     "¿Quién elige a los miembros de la Cámara de Representantes?", 1, True, [
        ("Citizens from their (congressional) district", "Los ciudadanos de su distrito (congresional)"),
    ]),
    (35, "Some states have more representatives than other states. Why?",
     "Algunos estados tienen más representantes que otros. ¿Por qué?", 1, True, [
        ("(Because of) the state's population", "(Debido a) la población del estado"),
        ("(Because) they have more people", "(Porque) tienen más habitantes"),
        ("(Because) some states have more people", "(Porque) algunos estados tienen más habitantes"),
    ]),
    (36, "The President of the United States is elected for how many years?",
     "¿Por cuántos años se elige al presidente de los Estados Unidos?", 1, True, [
        ("Four (4) years", "Cuatro (4) años"),
    ]),
    (37, "The President of the United States can serve only two terms. Why?",
     "El presidente de los Estados Unidos solo puede servir dos períodos. ¿Por qué?", 1, True, [
        ("(Because of) the 22nd Amendment", "(Debido a) la Vigesimosegunda Enmienda"),
        ("To keep the president from becoming too powerful", "Para evitar que el presidente se vuelva demasiado poderoso"),
    ]),
    (38, "What is the name of the President of the United States now?",
     "¿Cuál es el nombre del actual presidente de los Estados Unidos?", 1, False, [
        (NEEDS_ADMIN_REVIEW, NEEDS_ADMIN_REVIEW_ES),
    ]),
    (39, "What is the name of the Vice President of the United States now?",
     "¿Cuál es el nombre del actual vicepresidente de los Estados Unidos?", 1, False, [
        (NEEDS_ADMIN_REVIEW, NEEDS_ADMIN_REVIEW_ES),
    ]),
    (40, "If the president can no longer serve, who becomes president?",
     "Si el presidente ya no puede continuar en el cargo, ¿quién se convierte en presidente?", 1, True, [
        ("The Vice President (of the United States)", "El vicepresidente (de los Estados Unidos)"),
    ]),
    (41, "Name one power of the president.", "Mencione un poder del presidente.", 1, True, [
        ("Signs bills into law", "Firma proyectos de ley para convertirlos en ley"),
        ("Vetoes bills", "Veta proyectos de ley"),
        ("Enforces laws", "Hace cumplir las leyes"),
        ("Commander in Chief (of the military)", "Comandante en jefe (de las fuerzas armadas)"),
        ("Chief diplomat", "Jefe diplomático"),
        ("Appoints federal judges", "Nombra a jueces federales"),
    ]),
    (42, "Who is Commander in Chief of the U.S. military?",
     "¿Quién es el comandante en jefe de las fuerzas armadas de EE. UU.?", 1, True, [
        ("The President (of the United States)", "El presidente (de los Estados Unidos)"),
    ]),
    (43, "Who signs bills to become laws?", "¿Quién firma los proyectos de ley para que se conviertan en leyes?", 1, True, [
        ("The President (of the United States)", "El presidente (de los Estados Unidos)"),
    ]),
    (44, "Who vetoes bills?", "¿Quién veta los proyectos de ley?", 1, True, [
        ("The President (of the United States)", "El presidente (de los Estados Unidos)"),
    ]),
    (45, "Who appoints federal judges?", "¿Quién nombra a los jueces federales?", 1, True, [
        ("The President (of the United States)", "El presidente (de los Estados Unidos)"),
    ]),
    (46, "The executive branch has many parts. Name one.",
     "El poder ejecutivo tiene muchas partes. Mencione una.", 1, True, [
        ("President (of the United States)", "El presidente (de los Estados Unidos)"),
        ("Cabinet", "El gabinete"),
        ("Federal departments and agencies", "Los departamentos y agencias federales"),
    ]),
    (47, "What does the President's Cabinet do?", "¿Qué hace el gabinete del presidente?", 1, True, [
        ("Advises the President (of the United States)", "Asesora al presidente (de los Estados Unidos)"),
    ]),
    (48, "What are two Cabinet-level positions?", "¿Cuáles son dos puestos a nivel de gabinete?", 2, True, [
        ("Attorney General", "Fiscal General"),
        ("Secretary of Agriculture", "Secretario de Agricultura"),
        ("Secretary of Commerce", "Secretario de Comercio"),
        ("Secretary of Education", "Secretario de Educación"),
        ("Secretary of Energy", "Secretario de Energía"),
        ("Secretary of Health and Human Services", "Secretario de Salud y Servicios Humanos"),
        ("Secretary of Homeland Security", "Secretario de Seguridad Nacional"),
        ("Secretary of Housing and Urban Development", "Secretario de Vivienda y Desarrollo Urbano"),
        ("Secretary of the Interior", "Secretario del Interior"),
        ("Secretary of Labor", "Secretario del Trabajo"),
        ("Secretary of State", "Secretario de Estado"),
        ("Secretary of Transportation", "Secretario de Transporte"),
        ("Secretary of the Treasury", "Secretario del Tesoro"),
        ("Secretary of Veterans Affairs", "Secretario de Asuntos de Veteranos"),
        ("Secretary of War (Defense)", "Secretario de Guerra (Defensa)"),
        ("Vice-President", "Vicepresidente"),
        ("Administrator of the Environmental Protection Agency", "Administrador de la Agencia de Protección Ambiental"),
        ("Administrator of the Small Business Administration", "Administrador de la Administración de Pequeñas Empresas"),
        ("Director of the Central Intelligence Agency", "Director de la Agencia Central de Inteligencia"),
        ("Director of the Office of Management and Budget", "Director de la Oficina de Administración y Presupuesto"),
        ("Director of National Intelligence", "Director de Inteligencia Nacional"),
        ("United States Trade Representative", "Representante de Comercio de los Estados Unidos"),
    ]),
    (49, "Why is the Electoral College important?", "¿Por qué es importante el Colegio Electoral?", 1, True, [
        ("It decides who is elected president.", "Decide quién es elegido presidente."),
        ("It provides a compromise between the popular election of the president and congressional selection.",
         "Ofrece un equilibrio entre la elección popular del presidente y la selección por el Congreso."),
    ]),
    (50, "What is one part of the judicial branch?", "¿Cuál es una parte del poder judicial?", 1, True, [
        ("Supreme Court", "La Corte Suprema"),
        ("Federal Courts", "Los tribunales federales"),
    ]),
    (51, "What does the judicial branch do?", "¿Qué hace el poder judicial?", 1, True, [
        ("Reviews laws", "Revisa las leyes"),
        ("Explains laws", "Explica las leyes"),
        ("Resolves disputes (disagreements) about the law", "Resuelve disputas (desacuerdos) sobre la ley"),
        ("Decides if a law goes against the (U.S.) Constitution", "Decide si una ley va en contra de la Constitución (de EE. UU.)"),
    ]),
    (52, "What is the highest court in the United States?",
     "¿Cuál es el tribunal más alto de los Estados Unidos?", 1, True, [
        ("Supreme Court", "La Corte Suprema"),
    ]),
    (53, "How many seats are on the Supreme Court?", "¿Cuántos puestos (asientos) tiene la Corte Suprema?", 1, True, [
        ("Nine (9)", "Nueve (9)"),
    ]),
    (54, "How many Supreme Court justices are usually needed to decide a case?",
     "¿Cuántos jueces de la Corte Suprema se necesitan generalmente para decidir un caso?", 1, True, [
        ("Five (5)", "Cinco (5)"),
    ]),
    (55, "How long do Supreme Court justices serve?", "¿Por cuánto tiempo sirven los jueces de la Corte Suprema?", 1, True, [
        ("(For) life", "De por vida"),
        ("Lifetime appointment", "Nombramiento vitalicio"),
        ("(Until) retirement", "Hasta que se jubilan"),
    ]),
    (56, "Supreme Court justices serve for life. Why?",
     "Los jueces de la Corte Suprema sirven de por vida. ¿Por qué?", 1, True, [
        ("To be independent (of politics)", "Para ser independientes (de la política)"),
        ("To limit outside (political) influence", "Para limitar la influencia (política) externa"),
    ]),
    (57, "Who is the Chief Justice of the United States now?",
     "¿Quién es el actual presidente de la Corte Suprema (Chief Justice) de los Estados Unidos?", 1, False, [
        (NEEDS_ADMIN_REVIEW, NEEDS_ADMIN_REVIEW_ES),
    ]),
    (58, "Name one power that is only for the federal government.",
     "Mencione un poder que es solo del gobierno federal.", 1, True, [
        ("Print paper money", "Imprimir papel moneda"),
        ("Mint coins", "Acuñar monedas"),
        ("Declare war", "Declarar la guerra"),
        ("Create an army", "Crear un ejército"),
        ("Make treaties", "Hacer tratados"),
        ("Set foreign policy", "Establecer la política exterior"),
    ]),
    (59, "Name one power that is only for the states.", "Mencione un poder que es solo de los estados.", 1, True, [
        ("Provide schooling and education", "Proveer educación y escuelas"),
        ("Provide protection (police)", "Proveer protección (policía)"),
        ("Provide safety (fire departments)", "Proveer seguridad (departamentos de bomberos)"),
        ("Give a driver's license", "Otorgar licencias de conducir"),
        ("Approve zoning and land use", "Aprobar la zonificación y el uso de la tierra"),
    ]),
    (60, "What is the purpose of the 10th Amendment?", "¿Cuál es el propósito de la Décima Enmienda?", 1, True, [
        ("(It states that the) powers not given to the federal government belong to the states or to the people.",
         "(Establece que) los poderes que no se le otorgan al gobierno federal pertenecen a los estados o al pueblo."),
    ]),
    (61, "Who is the governor of your state now?", "¿Quién es el actual gobernador de su estado?", 1, False, [
        (NEEDS_ADMIN_REVIEW, NEEDS_ADMIN_REVIEW_ES),
    ]),
    (62, "What is the capital of your state?", "¿Cuál es la capital de su estado?", 1, True, [
        ("Trenton, New Jersey", "Trenton, Nueva Jersey"),
    ]),
    (63, "There are four amendments to the U.S. Constitution about who can vote. Describe one of them.",
     "Hay cuatro enmiendas a la Constitución de EE. UU. sobre quién puede votar. Describa una de ellas.", 1, True, [
        ("Citizens eighteen (18) and older (can vote).", "Los ciudadanos de dieciocho (18) años o más (pueden votar)."),
        ("You don't have to pay (a poll tax) to vote.", "No es necesario pagar (un impuesto electoral) para votar."),
        ("Any citizen can vote. (Women and men can vote.)", "Cualquier ciudadano puede votar. (Las mujeres y los hombres pueden votar.)"),
        ("A male citizen of any race (can vote).", "Un ciudadano varón de cualquier raza (puede votar)."),
    ]),
    (64, "Who can vote in federal elections, run for federal office, and serve on a jury in the United States?",
     "¿Quién puede votar en las elecciones federales, postularse para un cargo federal y servir en un jurado en los Estados Unidos?", 1, True, [
        ("Citizens", "Los ciudadanos"),
        ("Citizens of the United States", "Los ciudadanos de los Estados Unidos"),
        ("U.S. citizens", "Los ciudadanos de EE. UU."),
    ]),
    (65, "What are three rights of everyone living in the United States?",
     "¿Cuáles son tres derechos de todas las personas que viven en los Estados Unidos?", 3, True, [
        ("Freedom of expression", "Libertad de expresión"),
        ("Freedom of speech", "Libertad de palabra"),
        ("Freedom of assembly", "Libertad de reunión"),
        ("Freedom to petition the government", "Libertad para peticionar al gobierno"),
        ("Freedom of religion", "Libertad de religión"),
        ("The right to bear arms", "El derecho a portar armas"),
    ]),
    (66, "What do we show loyalty to when we say the Pledge of Allegiance?",
     "¿A qué mostramos lealtad cuando decimos el Juramento a la Bandera (Pledge of Allegiance)?", 1, True, [
        ("The United States", "A los Estados Unidos"),
        ("The flag", "A la bandera"),
    ]),
    (67, "Name two promises that new citizens make in the Oath of Allegiance.",
     "Mencione dos promesas que hacen los nuevos ciudadanos en el Juramento de Lealtad (Oath of Allegiance).", 2, True, [
        ("Give up loyalty to other countries", "Renunciar a la lealtad a otros países"),
        ("Defend the (U.S.) Constitution", "Defender la Constitución (de EE. UU.)"),
        ("Obey the laws of the United States", "Obedecer las leyes de los Estados Unidos"),
        ("Serve in the military (if needed)", "Servir en las fuerzas armadas (si es necesario)"),
        ("Serve (help, do important work for) the nation (if needed)", "Servir (ayudar, hacer trabajo importante para) la nación (si es necesario)"),
        ("Be loyal to the United States", "Ser leal a los Estados Unidos"),
    ]),
    (68, "How can people become United States citizens?",
     "¿Cómo pueden las personas convertirse en ciudadanos de los Estados Unidos?", 1, True, [
        ("Be born in the United States, under the conditions set by the 14th Amendment",
         "Nacer en los Estados Unidos, bajo las condiciones establecidas por la Decimocuarta Enmienda"),
        ("Naturalize", "Naturalizarse"),
        ("Derive citizenship (under conditions set by Congress)", "Derivar la ciudadanía (bajo las condiciones establecidas por el Congreso)"),
    ]),
    (69, "What are two examples of civic participation in the United States?",
     "¿Cuáles son dos ejemplos de participación cívica en los Estados Unidos?", 2, True, [
        ("Vote", "Votar"),
        ("Run for office", "Postularse para un cargo"),
        ("Join a political party", "Unirse a un partido político"),
        ("Help with a campaign", "Ayudar con una campaña"),
        ("Join a civic group", "Unirse a un grupo cívico"),
        ("Join a community group", "Unirse a un grupo comunitario"),
        ("Give an elected official your opinion (on an issue)", "Dar su opinión a un funcionario electo (sobre un tema)"),
        ("Contact elected officials", "Contactar a funcionarios electos"),
        ("Support or oppose an issue or policy", "Apoyar u oponerse a un tema o política"),
        ("Write to a newspaper", "Escribir a un periódico"),
    ]),
    (70, "What is one way Americans can serve their country?",
     "¿Cuál es una manera en que los estadounidenses pueden servir a su país?", 1, True, [
        ("Vote", "Votar"),
        ("Pay taxes", "Pagar impuestos"),
        ("Obey the law", "Obedecer la ley"),
        ("Serve in the military", "Servir en las fuerzas armadas"),
        ("Run for office", "Postularse para un cargo"),
        ("Work for local, state, or federal government", "Trabajar para el gobierno local, estatal o federal"),
    ]),
    (71, "Why is it important to pay federal taxes?", "¿Por qué es importante pagar impuestos federales?", 1, True, [
        ("Required by law", "Lo requiere la ley"),
        ("All people pay to fund the federal government", "Todas las personas pagan para financiar al gobierno federal"),
        ("Required by the (U.S.) Constitution (16th Amendment)", "Lo requiere la Constitución (de EE. UU.) (Decimosexta Enmienda)"),
        ("Civic duty", "Deber cívico"),
    ]),
    (72, "It is important for all men age 18 through 25 to register for the Selective Service. Name one reason why.",
     "Es importante que todos los hombres de 18 a 25 años se registren en el Servicio Selectivo. Mencione una razón por la cual.", 1, True, [
        ("Required by law", "Lo requiere la ley"),
        ("Civic duty", "Deber cívico"),
        ("Makes the draft fair, if needed", "Hace que el reclutamiento sea justo, si es necesario"),
    ]),
    (73, "The colonists came to America for many reasons. Name one.",
     "Los colonos vinieron a América por muchas razones. Mencione una.", 1, True, [
        ("Freedom", "Libertad"),
        ("Political liberty", "Libertad política"),
        ("Religious freedom", "Libertad religiosa"),
        ("Economic opportunity", "Oportunidad económica"),
        ("Escape persecution", "Escapar de la persecución"),
    ]),
    (74, "Who lived in America before the Europeans arrived?",
     "¿Quién vivía en América antes de que llegaran los europeos?", 1, True, [
        ("American Indians", "Indígenas americanos"),
        ("Native Americans", "Nativos americanos"),
    ]),
    (75, "What group of people was taken and sold as slaves?",
     "¿Qué grupo de personas fue tomado y vendido como esclavos?", 1, True, [
        ("Africans", "Africanos"),
        ("People from Africa", "Personas de África"),
    ]),
    (76, "What war did the Americans fight to win independence from Britain?",
     "¿Qué guerra lucharon los americanos para ganar la independencia de Gran Bretaña?", 1, True, [
        ("American Revolution", "La Revolución Americana"),
        ("The (American) Revolutionary War", "La Guerra Revolucionaria (Americana)"),
        ("War for (American) Independence", "La Guerra de Independencia (Americana)"),
    ]),
    (77, "Name one reason why the Americans declared independence from Britain.",
     "Mencione una razón por la que los americanos declararon su independencia de Gran Bretaña.", 1, True, [
        ("High taxes", "Impuestos altos"),
        ("Taxation without representation", "Impuestos sin representación"),
        ("British soldiers stayed in Americans' houses (boarding, quartering)", "Los soldados británicos se alojaban en las casas de los americanos (acuartelamiento)"),
        ("They did not have self-government", "No tenían autogobierno"),
        ("Boston Massacre", "La Masacre de Boston"),
        ("Boston Tea Party (Tea Act)", "El Motín del Té de Boston (Ley del Té)"),
        ("Stamp Act", "Ley del Timbre"),
        ("Sugar Act", "Ley del Azúcar"),
        ("Townshend Acts", "Leyes Townshend"),
        ("Intolerable (Coercive) Acts", "Leyes Intolerables (Coercitivas)"),
    ]),
    (78, "Who wrote the Declaration of Independence?", "¿Quién escribió la Declaración de Independencia?", 1, True, [
        ("(Thomas) Jefferson", "(Thomas) Jefferson"),
    ]),
    (79, "When was the Declaration of Independence adopted?",
     "¿Cuándo se adoptó la Declaración de Independencia?", 1, True, [
        ("July 4, 1776", "4 de julio de 1776"),
    ]),
    (80, "The American Revolution had many important events. Name one.",
     "La Revolución Americana tuvo muchos eventos importantes. Mencione uno.", 1, True, [
        ("(Battle of) Bunker Hill", "(Batalla de) Bunker Hill"),
        ("Declaration of Independence", "Declaración de Independencia"),
        ("Washington Crossing the Delaware (Battle of Trenton)", "Washington Cruzando el Delaware (Batalla de Trenton)"),
        ("(Battle of) Saratoga", "(Batalla de) Saratoga"),
        ("Valley Forge (Encampment)", "Valley Forge (Campamento)"),
        ("(Battle of) Yorktown (British surrender at Yorktown)", "(Batalla de) Yorktown (Rendición británica en Yorktown)"),
    ]),
    (81, "There were 13 original states. Name five.", "Hubo 13 estados originales. Mencione cinco.", 5, True, [
        ("New Hampshire", "New Hampshire"),
        ("Massachusetts", "Massachusetts"),
        ("Rhode Island", "Rhode Island"),
        ("Connecticut", "Connecticut"),
        ("New York", "Nueva York"),
        ("New Jersey", "Nueva Jersey"),
        ("Pennsylvania", "Pensilvania"),
        ("Delaware", "Delaware"),
        ("Maryland", "Maryland"),
        ("Virginia", "Virginia"),
        ("North Carolina", "Carolina del Norte"),
        ("South Carolina", "Carolina del Sur"),
        ("Georgia", "Georgia"),
    ]),
    (82, "What founding document was written in 1787?", "¿Qué documento fundacional se escribió en 1787?", 1, True, [
        ("(U.S.) Constitution", "La Constitución (de EE. UU.)"),
    ]),
    (83, "The Federalist Papers supported the passage of the U.S. Constitution. Name one of the writers.",
     "Los Documentos Federalistas apoyaron la aprobación de la Constitución de EE. UU. Mencione a uno de los autores.", 1, True, [
        ("(James) Madison", "(James) Madison"),
        ("(Alexander) Hamilton", "(Alexander) Hamilton"),
        ("(John) Jay", "(John) Jay"),
        ("Publius", "Publius"),
    ]),
    (84, "Why were the Federalist Papers important?", "¿Por qué fueron importantes los Documentos Federalistas?", 1, True, [
        ("They helped people understand the (U.S.) Constitution.", "Ayudaron a la gente a entender la Constitución (de EE. UU.)."),
        ("They supported passing the (U.S.) Constitution.", "Apoyaron la aprobación de la Constitución (de EE. UU.)."),
    ]),
    (85, "Benjamin Franklin is famous for many things. Name one.",
     "Benjamin Franklin es famoso por muchas cosas. Mencione una.", 1, True, [
        ("Founded the first free public libraries", "Fundó las primeras bibliotecas públicas gratuitas"),
        ("First Postmaster General of the United States", "Primer Director General de Correos de los Estados Unidos"),
        ("Helped write the Declaration of Independence", "Ayudó a escribir la Declaración de Independencia"),
        ("Inventor", "Inventor"),
        ("U.S. diplomat", "Diplomático de EE. UU."),
    ]),
    (86, "George Washington is famous for many things. Name one.",
     "George Washington es famoso por muchas cosas. Mencione una.", 1, True, [
        ('"Father of Our Country"', '"Padre de Nuestra Patria"'),
        ("First president of the United States", "Primer presidente de los Estados Unidos"),
        ("General of the Continental Army", "General del Ejército Continental"),
        ("President of the Constitutional Convention", "Presidente de la Convención Constitucional"),
    ]),
    (87, "Thomas Jefferson is famous for many things. Name one.",
     "Thomas Jefferson es famoso por muchas cosas. Mencione una.", 1, True, [
        ("Writer of the Declaration of Independence", "Autor de la Declaración de Independencia"),
        ("Third president of the United States", "Tercer presidente de los Estados Unidos"),
        ("Doubled the size of the United States (Louisiana Purchase)", "Duplicó el tamaño de los Estados Unidos (Compra de Luisiana)"),
        ("First Secretary of State", "Primer Secretario de Estado"),
        ("Founded the University of Virginia", "Fundó la Universidad de Virginia"),
        ("Writer of the Virginia Statute on Religious Freedom", "Autor del Estatuto de Virginia sobre la Libertad Religiosa"),
    ]),
    (88, "James Madison is famous for many things. Name one.",
     "James Madison es famoso por muchas cosas. Mencione una.", 1, True, [
        ('"Father of the Constitution"', '"Padre de la Constitución"'),
        ("Fourth president of the United States", "Cuarto presidente de los Estados Unidos"),
        ("President during the War of 1812", "Presidente durante la Guerra de 1812"),
        ("One of the writers of the Federalist Papers", "Uno de los autores de los Documentos Federalistas"),
    ]),
    (89, "Alexander Hamilton is famous for many things. Name one.",
     "Alexander Hamilton es famoso por muchas cosas. Mencione una.", 1, True, [
        ("First Secretary of the Treasury", "Primer Secretario del Tesoro"),
        ("One of the writers of the Federalist Papers", "Uno de los autores de los Documentos Federalistas"),
        ("Helped establish the First Bank of the United States", "Ayudó a establecer el Primer Banco de los Estados Unidos"),
        ("Aide to General George Washington", "Ayudante del General George Washington"),
        ("Member of the Continental Congress", "Miembro del Congreso Continental"),
    ]),
    (90, "What territory did the United States buy from France in 1803?",
     "¿Qué territorio compró Estados Unidos a Francia en 1803?", 1, True, [
        ("Louisiana Territory", "El Territorio de Luisiana"),
        ("Louisiana", "Luisiana"),
    ]),
    (91, "Name one war fought by the United States in the 1800s.",
     "Mencione una guerra que Estados Unidos libró en el siglo XIX (los años 1800).", 1, True, [
        ("War of 1812", "Guerra de 1812"),
        ("Mexican-American War", "Guerra México-Americana"),
        ("Civil War", "Guerra Civil"),
        ("Spanish-American War", "Guerra Hispanoamericana"),
    ]),
    (92, "Name the U.S. war between the North and the South.",
     "Mencione la guerra de EE. UU. entre el Norte y el Sur.", 1, True, [
        ("The Civil War", "La Guerra Civil"),
    ]),
    (93, "The Civil War had many important events. Name one.",
     "La Guerra Civil tuvo muchos eventos importantes. Mencione uno.", 1, True, [
        ("(Battle of) Fort Sumter", "(Batalla de) Fort Sumter"),
        ("Emancipation Proclamation", "Proclamación de Emancipación"),
        ("(Battle of) Vicksburg", "(Batalla de) Vicksburg"),
        ("(Battle of) Gettysburg", "(Batalla de) Gettysburg"),
        ("Sherman's March", "La Marcha de Sherman"),
        ("(Surrender at) Appomattox", "(Rendición en) Appomattox"),
        ("(Battle of) Antietam/Sharpsburg", "(Batalla de) Antietam/Sharpsburg"),
        ("Lincoln was assassinated.", "Lincoln fue asesinado."),
    ]),
    (94, "Abraham Lincoln is famous for many things. Name one.",
     "Abraham Lincoln es famoso por muchas cosas. Mencione una.", 1, True, [
        ("Freed the slaves (Emancipation Proclamation)", "Liberó a los esclavos (Proclamación de Emancipación)"),
        ("Saved (or preserved) the Union", "Salvó (o preservó) la Unión"),
        ("Led the United States during the Civil War", "Dirigió a los Estados Unidos durante la Guerra Civil"),
        ("16th president of the United States", "Decimosexto presidente de los Estados Unidos"),
        ("Delivered the Gettysburg Address", "Pronunció el Discurso de Gettysburg"),
    ]),
    (95, "What did the Emancipation Proclamation do?", "¿Qué hizo la Proclamación de Emancipación?", 1, True, [
        ("Freed the slaves", "Liberó a los esclavos"),
        ("Freed slaves in the Confederacy", "Liberó a los esclavos en la Confederación"),
        ("Freed slaves in the Confederate states", "Liberó a los esclavos en los estados confederados"),
        ("Freed slaves in most Southern states", "Liberó a los esclavos en la mayoría de los estados del sur"),
    ]),
    (96, "What U.S. war ended slavery?", "¿Qué guerra de EE. UU. terminó con la esclavitud?", 1, True, [
        ("The Civil War", "La Guerra Civil"),
    ]),
    (97, "What amendment says all persons born or naturalized in the United States, and subject to the "
         "jurisdiction thereof, are U.S. citizens?",
     "¿Qué enmienda establece que todas las personas nacidas o naturalizadas en los Estados Unidos, y sujetas a "
     "su jurisdicción, son ciudadanos de EE. UU.?", 1, True, [
        ("14th Amendment", "Decimocuarta Enmienda"),
    ]),
    (98, "When did all men get the right to vote?", "¿Cuándo obtuvieron todos los hombres el derecho al voto?", 1, True, [
        ("After the Civil War", "Después de la Guerra Civil"),
        ("During Reconstruction", "Durante la Reconstrucción"),
        ("(With the) 15th Amendment", "(Con la) Decimoquinta Enmienda"),
        ("1870", "1870"),
    ]),
    (99, "Name one leader of the women's rights movement in the 1800s.",
     "Mencione un líder del movimiento por los derechos de la mujer en el siglo XIX.", 1, True, [
        ("Susan B. Anthony", "Susan B. Anthony"),
        ("Elizabeth Cady Stanton", "Elizabeth Cady Stanton"),
        ("Sojourner Truth", "Sojourner Truth"),
        ("Harriet Tubman", "Harriet Tubman"),
        ("Lucretia Mott", "Lucretia Mott"),
        ("Lucy Stone", "Lucy Stone"),
    ]),
    (100, "Name one war fought by the United States in the 1900s.",
     "Mencione una guerra que Estados Unidos libró en el siglo XX (los años 1900).", 1, True, [
        ("World War I", "Primera Guerra Mundial"),
        ("World War II", "Segunda Guerra Mundial"),
        ("Korean War", "Guerra de Corea"),
        ("Vietnam War", "Guerra de Vietnam"),
        ("(Persian) Gulf War", "Guerra del Golfo (Pérsico)"),
    ]),
    (101, "Why did the United States enter World War I?", "¿Por qué entró Estados Unidos en la Primera Guerra Mundial?", 1, True, [
        ("Because Germany attacked U.S. (civilian) ships", "Porque Alemania atacó barcos (civiles) estadounidenses"),
        ("To support the Allied Powers (England, France, Italy, and Russia)", "Para apoyar a las Potencias Aliadas (Inglaterra, Francia, Italia y Rusia)"),
        ("To oppose the Central Powers (Germany, Austria-Hungary, the Ottoman Empire, and Bulgaria)", "Para oponerse a las Potencias Centrales (Alemania, Austria-Hungría, el Imperio Otomano y Bulgaria)"),
    ]),
    (102, "When did all women get the right to vote?", "¿Cuándo obtuvieron todas las mujeres el derecho al voto?", 1, True, [
        ("1920", "1920"),
        ("After World War I", "Después de la Primera Guerra Mundial"),
        ("(With the) 19th Amendment", "(Con la) Decimonovena Enmienda"),
    ]),
    (103, "What was the Great Depression?", "¿Qué fue la Gran Depresión?", 1, True, [
        ("Longest economic recession in modern history", "La recesión económica más larga de la historia moderna"),
    ]),
    (104, "When did the Great Depression start?", "¿Cuándo comenzó la Gran Depresión?", 1, True, [
        ("The Great Crash (1929)", "El Gran Colapso (1929)"),
        ("Stock market crash of 1929", "La caída de la bolsa de 1929"),
    ]),
    (105, "Who was president during the Great Depression and World War II?",
     "¿Quién fue presidente durante la Gran Depresión y la Segunda Guerra Mundial?", 1, True, [
        ("(Franklin) Roosevelt", "(Franklin) Roosevelt"),
    ]),
    (106, "Why did the United States enter World War II?", "¿Por qué entró Estados Unidos en la Segunda Guerra Mundial?", 1, True, [
        ("(Bombing of) Pearl Harbor", "(Bombardeo de) Pearl Harbor"),
        ("Japanese attacked Pearl Harbor", "Japón atacó Pearl Harbor"),
        ("To support the Allied Powers (England, France, and Russia)", "Para apoyar a las Potencias Aliadas (Inglaterra, Francia y Rusia)"),
        ("To oppose the Axis Powers (Germany, Italy, and Japan)", "Para oponerse a las Potencias del Eje (Alemania, Italia y Japón)"),
    ]),
    (107, "Dwight Eisenhower is famous for many things. Name one.",
     "Dwight Eisenhower es famoso por muchas cosas. Mencione una.", 1, True, [
        ("General during World War II", "General durante la Segunda Guerra Mundial"),
        ("President at the end of (during) the Korean War", "Presidente al final de (durante) la Guerra de Corea"),
        ("34th president of the United States", "Trigésimo cuarto presidente de los Estados Unidos"),
        ("Signed the Federal-Aid Highway Act of 1956 (Created the Interstate System)",
         "Firmó la Ley de Ayuda Federal para Carreteras de 1956 (creó el Sistema de Autopistas Interestatales)"),
    ]),
    (108, "Who was the United States' main rival during the Cold War?",
     "¿Quién fue el principal rival de los Estados Unidos durante la Guerra Fría?", 1, True, [
        ("Soviet Union", "Unión Soviética"),
        ("USSR", "URSS"),
        ("Russia", "Rusia"),
    ]),
    (109, "During the Cold War, what was one main concern of the United States?",
     "Durante la Guerra Fría, ¿cuál fue una de las principales preocupaciones de los Estados Unidos?", 1, True, [
        ("Communism", "El comunismo"),
        ("Nuclear war", "La guerra nuclear"),
    ]),
    (110, "Why did the United States enter the Korean War?", "¿Por qué entró Estados Unidos en la Guerra de Corea?", 1, True, [
        ("To stop the spread of communism", "Para detener la expansión del comunismo"),
    ]),
    (111, "Why did the United States enter the Vietnam War?", "¿Por qué entró Estados Unidos en la Guerra de Vietnam?", 1, True, [
        ("To stop the spread of communism", "Para detener la expansión del comunismo"),
    ]),
    (112, "What did the civil rights movement do?", "¿Qué hizo el movimiento de derechos civiles?", 1, True, [
        ("Fought to end racial discrimination", "Luchó para poner fin a la discriminación racial"),
    ]),
    (113, "Martin Luther King, Jr. is famous for many things. Name one.",
     "Martin Luther King, Jr. es famoso por muchas cosas. Mencione una.", 1, True, [
        ("Fought for civil rights", "Luchó por los derechos civiles"),
        ("Worked for equality for all Americans", "Trabajó por la igualdad de todos los estadounidenses"),
        ('Worked to ensure that people would "not be judged by the color of their skin, but by the content of their character"',
         'Trabajó para que las personas "no fueran juzgadas por el color de su piel, sino por el contenido de su carácter"'),
    ]),
    (114, "Why did the United States enter the Persian Gulf War?",
     "¿Por qué entró Estados Unidos en la Guerra del Golfo Pérsico?", 1, True, [
        ("To force the Iraqi military from Kuwait", "Para obligar a las fuerzas militares iraquíes a salir de Kuwait"),
    ]),
    (115, "What major event happened on September 11, 2001 in the United States?",
     "¿Qué evento importante ocurrió el 11 de septiembre de 2001 en los Estados Unidos?", 1, True, [
        ("Terrorists attacked the United States", "Terroristas atacaron a los Estados Unidos"),
        ("Terrorists took over two planes and crashed them into the World Trade Center in New York City",
         "Terroristas secuestraron dos aviones y los estrellaron contra el World Trade Center en la ciudad de Nueva York"),
        ("Terrorists took over a plane and crashed into the Pentagon in Arlington, Virginia",
         "Terroristas secuestraron un avión y lo estrellaron contra el Pentágono en Arlington, Virginia"),
        ("Terrorists took over a plane originally aimed at Washington, D.C., and crashed in a field in Pennsylvania",
         "Terroristas secuestraron un avión originalmente dirigido a Washington, D.C., que se estrelló en un campo en Pensilvania"),
    ]),
    (116, "Name one U.S. military conflict after the September 11, 2001 attacks.",
     "Mencione un conflicto militar de EE. UU. después de los ataques del 11 de septiembre de 2001.", 1, True, [
        ("(Global) War on Terror", "(Guerra Global) contra el Terrorismo"),
        ("War in Afghanistan", "Guerra en Afganistán"),
        ("War in Iraq", "Guerra en Irak"),
    ]),
    (117, "Name one American Indian tribe in the United States.",
     "Mencione una tribu indígena americana de los Estados Unidos.", 1, True, [
        ("Apache", "Apache"), ("Blackfeet", "Blackfeet"), ("Cayuga", "Cayuga"), ("Cherokee", "Cherokee"),
        ("Cheyenne", "Cheyenne"), ("Chippewa", "Chippewa"), ("Choctaw", "Choctaw"), ("Creek", "Creek"),
        ("Crow", "Crow"), ("Hopi", "Hopi"), ("Huron", "Huron"), ("Inupiat", "Inupiat"), ("Lakota", "Lakota"),
        ("Mohawk", "Mohawk"), ("Mohegan", "Mohegan"), ("Navajo", "Navajo"), ("Oneida", "Oneida"),
        ("Onondaga", "Onondaga"), ("Pueblo", "Pueblo"), ("Seminole", "Seminole"), ("Seneca", "Seneca"),
        ("Shawnee", "Shawnee"), ("Sioux", "Sioux"), ("Teton", "Teton"), ("Tuscarora", "Tuscarora"),
    ]),
    (118, "Name one example of an American innovation.", "Mencione un ejemplo de una innovación estadounidense.", 1, True, [
        ("Light bulb", "La bombilla (el foco)"),
        ("Automobile (cars, internal combustion engine)", "El automóvil (los carros, el motor de combustión interna)"),
        ("Skyscrapers", "Los rascacielos"),
        ("Airplane", "El avión"),
        ("Assembly line", "La línea de ensamblaje"),
        ("Landing on the moon", "El alunizaje (llegar a la luna)"),
        ("Integrated circuit (IC)", "El circuito integrado"),
    ]),
    (119, "What is the capital of the United States?", "¿Cuál es la capital de los Estados Unidos?", 1, True, [
        ("Washington, D.C.", "Washington, D.C."),
    ]),
    (120, "Where is the Statue of Liberty?", "¿Dónde está la Estatua de la Libertad?", 1, True, [
        ("New York (Harbor)", "El puerto de Nueva York"),
        ("Liberty Island", "Isla de la Libertad (también se aceptan Nueva Jersey, cerca de la ciudad de Nueva York, y sobre el río Hudson)"),
    ]),
    (121, "Why does the flag have 13 stripes?", "¿Por qué la bandera tiene 13 franjas?", 1, True, [
        ("(Because there were) 13 original colonies", "(Porque había) 13 colonias originales"),
        ("(Because the stripes) represent the original colonies", "(Porque las franjas) representan a las colonias originales"),
    ]),
    (122, "Why does the flag have 50 stars?", "¿Por qué la bandera tiene 50 estrellas?", 1, True, [
        ("(Because there is) one star for each state", "(Porque hay) una estrella por cada estado"),
        ("(Because) each star represents a state", "(Porque) cada estrella representa a un estado"),
        ("(Because there are) 50 states", "(Porque hay) 50 estados"),
    ]),
    (123, "What is the name of the national anthem?", "¿Cuál es el nombre del himno nacional?", 1, True, [
        ("The Star-Spangled Banner", "El Star-Spangled Banner (La Bandera de Estrellas)"),
    ]),
    (124, 'The Nation\'s first motto was "E Pluribus Unum." What does that mean?',
     'El primer lema de la Nación fue "E Pluribus Unum". ¿Qué significa eso?', 1, True, [
        ("Out of many, one", "De muchos, uno"),
        ("We all become one", "Todos nos convertimos en uno"),
    ]),
    (125, "What is Independence Day?", "¿Qué es el Día de la Independencia?", 1, True, [
        ("A holiday to celebrate U.S. independence (from Britain)", "Un día festivo para celebrar la independencia de EE. UU. (de Gran Bretaña)"),
        ("The country's birthday", "El cumpleaños del país"),
    ]),
    (126, "Name three national U.S. holidays.", "Mencione tres días festivos nacionales de EE. UU.", 3, True, [
        ("New Year's Day", "Año Nuevo"),
        ("Martin Luther King, Jr. Day", "Día de Martin Luther King, Jr."),
        ("Presidents Day (Washington's Birthday)", "Día de los Presidentes (Cumpleaños de Washington)"),
        ("Memorial Day", "Día de los Caídos"),
        ("Juneteenth", "Juneteenth (Día de la Emancipación)"),
        ("Independence Day", "Día de la Independencia"),
        ("Labor Day", "Día del Trabajo"),
        ("Columbus Day", "Día de la Raza (Columbus Day)"),
        ("Veterans Day", "Día de los Veteranos"),
        ("Thanksgiving Day", "Día de Acción de Gracias"),
        ("Christmas Day", "Navidad"),
    ]),
    (127, "What is Memorial Day?", "¿Qué es el Día de los Caídos (Memorial Day)?", 1, True, [
        ("A holiday to honor soldiers who died in military service", "Un día festivo para honrar a los soldados que murieron en servicio militar"),
    ]),
    (128, "What is Veterans Day?", "¿Qué es el Día de los Veteranos?", 1, True, [
        ("A holiday to honor people in the (U.S.) military", "Un día festivo para honrar a las personas en las fuerzas armadas (de EE. UU.)"),
        ("A holiday to honor people who have served (in the U.S. military)", "Un día festivo para honrar a las personas que han servido (en las fuerzas armadas de EE. UU.)"),
    ]),
]


def run():
    app = create_app()
    with app.app_context():
        if CivicsQuestion.query.count() > 0:
            print(f"Aborting: civics_questions already has {CivicsQuestion.query.count()} rows. "
                  "Delete them first if you want to reload from scratch.")
            return

        for number, q_en, q_es, required_count, is_active, answers in QUESTIONS:
            question = CivicsQuestion(
                number=number, question_en=q_en, question_es=q_es,
                required_count=required_count, is_active=is_active,
            )
            for a_en, a_es in answers:
                question.answers.append(CivicsAnswer(answer_en=a_en, answer_es=a_es))
            db.session.add(question)

        db.session.commit()
        total = CivicsQuestion.query.count()
        inactive = CivicsQuestion.query.filter_by(is_active=False).count()
        print(f"Loaded {total} civics questions ({total - inactive} active, {inactive} inactive "
              "pending admin review — current officeholder / district-specific questions).")


if __name__ == "__main__":
    run()
