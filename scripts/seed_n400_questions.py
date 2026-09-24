"""Seeds a small starter bank of general N-400 naturalization interview
PRACTICE questions — illustrative sample questions and coaching notes only,
never official legal guidance, eligibility criteria, or guaranteed real
interview content. Safe to extend/edit afterward from /admin/n400/questions.

Run once: .venv/Scripts/python.exe scripts/seed_n400_questions.py
"""

from app import create_app
from app.extensions import db
from app.models import N400Question

QUESTIONS = [
    dict(
        number=1, category="Motivation",
        question_en="Why do you want to become a United States citizen?",
        question_es="¿Por qué quiere convertirse en ciudadano de los Estados Unidos?",
        sample_answer_en="I want to vote, have a U.S. passport, and fully participate in my community as a citizen.",
        sample_answer_es="Quiero votar, tener un pasaporte estadounidense y participar plenamente en mi comunidad como ciudadano.",
        rubric_notes_en="A strong answer is personal, specific, and confidently stated — not memorized-sounding or vague.",
        rubric_notes_es="Una buena respuesta es personal, específica y segura — no debe sonar memorizada ni vaga.",
    ),
    dict(
        number=2, category="Oath / Constitution",
        question_en="Do you support the Constitution and form of government of the United States?",
        question_es="¿Apoya usted la Constitución y la forma de gobierno de los Estados Unidos?",
        sample_answer_en="Yes, I do.",
        sample_answer_es="Sí, la apoyo.",
        rubric_notes_en="This should be a clear, direct 'yes' answer, stated without hesitation.",
        rubric_notes_es="Debe ser un 'sí' claro y directo, dicho sin dudar.",
    ),
    dict(
        number=3, category="Oath / Constitution",
        question_en="Are you willing to bear arms on behalf of the United States when required by law?",
        question_es="¿Está dispuesto a portar armas en nombre de los Estados Unidos cuando la ley lo requiera?",
        sample_answer_en="Yes, I am.",
        sample_answer_es="Sí, lo estoy.",
        rubric_notes_en="A clear, direct answer. If the applicant has religious/moral objections, this is a real legal topic they should discuss with an accredited immigration professional, not resolve based on this practice tool.",
        rubric_notes_es="Una respuesta clara y directa. Si el solicitante tiene objeciones religiosas o morales, es un tema legal real que debe consultar con un profesional de inmigración acreditado, no resolverlo con esta herramienta de práctica.",
    ),
    dict(
        number=4, category="Moral Character",
        question_en="Have you ever been arrested, cited, or detained by any law enforcement officer for any reason?",
        question_es="¿Alguna vez ha sido arrestado, citado o detenido por algún oficial de la ley por cualquier motivo?",
        sample_answer_en="No, I have not. (If yes: clearly state what happened, when, and the outcome — do not leave out details.)",
        sample_answer_es="No, no lo he sido. (Si es sí: indique claramente qué pasó, cuándo, y el resultado — no omita detalles.)",
        rubric_notes_en="Answer should be direct (yes/no) and, if yes, include enough detail to be complete rather than vague or evasive.",
        rubric_notes_es="La respuesta debe ser directa (sí/no) y, si es sí, incluir suficiente detalle para ser completa, no vaga ni evasiva.",
    ),
    dict(
        number=5, category="Moral Character",
        question_en="Have you ever claimed to be a U.S. citizen (in writing or any other way) when you were not a U.S. citizen?",
        question_es="¿Alguna vez ha afirmado ser ciudadano de EE. UU. (por escrito o de cualquier otra forma) sin serlo?",
        sample_answer_en="No, I have not.",
        sample_answer_es="No, no lo he hecho.",
        rubric_notes_en="A clear, direct answer.",
        rubric_notes_es="Una respuesta clara y directa.",
    ),
    dict(
        number=6, category="Application Review",
        question_en="Have you ever failed to file a required federal, state, or local tax return since becoming a permanent resident?",
        question_es="¿Alguna vez ha dejado de presentar una declaración de impuestos federal, estatal o local requerida desde que es residente permanente?",
        sample_answer_en="No, I have filed every year. (If not: be ready to explain clearly and honestly.)",
        sample_answer_es="No, he declarado todos los años. (Si no: esté preparado para explicarlo con claridad y honestidad.)",
        rubric_notes_en="Direct answer expected; if there's a gap, a strong answer explains it plainly rather than avoiding the topic.",
        rubric_notes_es="Se espera una respuesta directa; si hay un vacío, una buena respuesta lo explica con claridad en vez de evitar el tema.",
    ),
    dict(
        number=7, category="Eligibility",
        question_en="Since becoming a lawful permanent resident, have you ever been absent from the United States for more than six months in a row?",
        question_es="Desde que es residente permanente legal, ¿alguna vez ha estado ausente de los Estados Unidos por más de seis meses seguidos?",
        sample_answer_en="No. (If yes: be ready to state the dates and reason for each trip.)",
        sample_answer_es="No. (Si es sí: esté preparado para indicar las fechas y el motivo de cada viaje.)",
        rubric_notes_en="Applicants with long absences should mention dates/reasons clearly — this is a real eligibility topic best confirmed with an accredited professional, not resolved here.",
        rubric_notes_es="Los solicitantes con ausencias largas deben mencionar fechas/motivos con claridad — es un tema real de elegibilidad que debe confirmarse con un profesional acreditado, no resolverse aquí.",
    ),
    dict(
        number=8, category="Background",
        question_en="What is your current job, and how long have you worked there?",
        question_es="¿Cuál es su trabajo actual, y cuánto tiempo lleva trabajando ahí?",
        sample_answer_en="I work as a [job title] at [employer] — I've been there for [length of time].",
        sample_answer_es="Trabajo como [puesto] en [empleador] — llevo [tiempo] ahí.",
        rubric_notes_en="A confident, specific, complete answer — this is a simple background/application-review question, mainly practicing clear spoken English.",
        rubric_notes_es="Una respuesta segura, específica y completa — es una pregunta simple de antecedentes/revisión de la solicitud, principalmente para practicar hablar inglés con claridad.",
    ),
]


def run():
    app = create_app()
    with app.app_context():
        if N400Question.query.count() > 0:
            print("N-400 questions already exist — nothing to do.")
            return

        for i, q in enumerate(QUESTIONS):
            db.session.add(N400Question(sort_order=i, is_active=True, **q))
        db.session.commit()
        print(f"Seeded {len(QUESTIONS)} N-400 practice questions.")


if __name__ == "__main__":
    run()
