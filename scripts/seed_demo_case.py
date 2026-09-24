"""Creates ONE minimal, clearly-fictional demo Case Simulation to verify OG
Forensic Training's Case Simulation MVP end-to-end. Lives in its own
unpublished course (is_published=False) so it never appears in course
listings or sitemap.xml — this is a QA fixture, not real curriculum, never
presented as official course content. No real client data of any kind is
used; every document is a generated placeholder image stamped "FICTITIOUS —
FOR TRAINING ONLY". Use /admin/cases/<id>/preview to review it (works
regardless of publish state) — to exercise the full real student flow
(enrollment, access checks, document serving), temporarily flip is_published
to True, enroll a test student, then set it back to False when done.

Run once: .venv/Scripts/python.exe scripts/seed_demo_case.py
"""

import io

from PIL import Image, ImageDraw
from werkzeug.datastructures import FileStorage

from app import create_app
from app.extensions import db
from app.models import (
    CaseSimulation,
    CaseSimulationDocument,
    CaseSimulationTask,
    CaseSimulationTaskAcceptedAnswer,
    CaseSimulationTaskOption,
    Course,
    CourseSection,
    Lesson,
)
from app.uploads import save_course_media

SLUG = "og-forensic-training-demo"


def _placeholder_document(title, lines):
    img = Image.new("RGB", (900, 1100), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 899, 1099], outline=(200, 200, 200), width=3)
    draw.text((40, 30), "FICTITIOUS — FOR TRAINING ONLY", fill=(200, 60, 60))
    draw.text((40, 70), title, fill=(20, 30, 60))
    draw.line([40, 105, 860, 105], fill=(220, 220, 220), width=2)
    y = 140
    for line in lines:
        draw.text((40, y), line, fill=(40, 45, 60))
        y += 36
    draw.text((40, 1050), "This document is a generated training placeholder. No real person or filing is represented.", fill=(160, 160, 160))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return FileStorage(stream=buffer, filename=f"{title.lower().replace(' ', '_')}.png", content_type="image/png")


def run():
    app = create_app()
    with app.app_context():
        if Course.query.filter_by(slug=SLUG).first():
            print("Demo case already exists — nothing to do.")
            return

        course = Course(
            slug=SLUG,
            category="Forensic Training",
            title_en="OG Forensic Training (Demo)",
            title_es="OG Forensic Training (Demostración)",
            subtitle_en="Internal QA fixture for the Case Simulation MVP — not published curriculum.",
            subtitle_es="Fixture interno de QA para el MVP de Case Simulation — no es contenido publicado.",
            description_en="Unpublished internal course holding one demo Case Simulation used to verify the feature end-to-end.",
            description_es="Curso interno no publicado con un caso de demostración para verificar la función de principio a fin.",
            is_published=False,
            sort_order=999,
        )
        section = CourseSection(title_en="Demo", title_es="Demostración", sort_order=0)
        lesson = Lesson(
            lesson_type="case_simulation",
            title_en="Demo Case — Training Only",
            title_es="Caso de Demostración — Solo para Entrenamiento",
            sort_order=0,
            is_preview=False,
        )
        section.lessons.append(lesson)
        course.sections.append(section)
        db.session.add(course)
        db.session.flush()

        case = CaseSimulation(
            lesson_id=lesson.id,
            title_en="Demo Case — Training Only",
            title_es="Caso de Demostración — Solo para Entrenamiento",
            description_en="A short, entirely fictional practice case used only to verify the Case Simulation feature.",
            description_es="Un caso corto y totalmente ficticio usado solo para verificar la función de Case Simulation.",
            client_profile_en=(
                "Client: Jordan Rivera (fictional). Came in for a tax prep intake appointment. Provided a W-2 from "
                "one employer and a 1099-NEC from freelance design work. Intake notes mention Jordan also drove for "
                "a food delivery app for part of the year."
            ),
            client_profile_es=(
                "Cliente: Jordan Rivera (ficticio). Llegó a una cita de admisión para preparación de impuestos. "
                "Entregó un W-2 de un empleador y un 1099-NEC de trabajo de diseño independiente. Las notas de "
                "admisión mencionan que Jordan también manejó para una app de entrega de comida parte del año."
            ),
            instructions_en="Review the documents below, then complete every task.",
            instructions_es="Revisa los documentos a continuación y completa cada tarea.",
            passing_score=70,
            max_attempts=None,
            is_active=True,
        )
        db.session.add(case)
        db.session.flush()

        w2 = save_course_media(
            _placeholder_document("Form W-2 (Fictional)", [
                "Employer: Sample Employer LLC (fictional)", "Employee: Jordan Rivera (fictional)",
                "Box 1 - Wages: $45,000.00", "Box 2 - Federal tax withheld: $4,100.00",
            ]),
            "document",
        )
        c1099 = save_course_media(
            _placeholder_document("Form 1099-NEC (Fictional)", [
                "Payer: Sample Design Client (fictional)", "Recipient: Jordan Rivera (fictional)",
                "Box 1 - Nonemployee compensation: $8,500.00",
            ]),
            "document",
        )
        notes = save_course_media(
            _placeholder_document("Client Intake Notes (Fictional)", [
                "Client mentioned driving for a food delivery app for about 4 months this year.",
                "No 1099 provided for delivery app income.", "Client unsure if they kept mileage records.",
            ]),
            "document",
        )

        case.documents.append(CaseSimulationDocument(label_en="W-2", label_es="W-2", doc_type="W-2", file_filename=w2, sort_order=0))
        case.documents.append(CaseSimulationDocument(label_en="1099-NEC", label_es="1099-NEC", doc_type="1099-NEC", file_filename=c1099, sort_order=1))
        case.documents.append(CaseSimulationDocument(label_en="Client Intake Notes", label_es="Notas de Admisión", doc_type="Notes", file_filename=notes, sort_order=2))

        mc_task = CaseSimulationTask(
            task_type="multiple_choice", points=2, sort_order=0,
            prompt_en="Based on the W-2 and 1099-NEC, which best describes Jordan's income sources this year?",
            prompt_es="Según el W-2 y el 1099-NEC, ¿cuál describe mejor las fuentes de ingreso de Jordan este año?",
            explanation_en="The W-2 shows wage income and the 1099-NEC shows separate self-employment income — both apply.",
            explanation_es="El W-2 muestra ingreso por salario y el 1099-NEC muestra ingreso de trabajo independiente — ambos aplican.",
        )
        mc_task.options = [
            CaseSimulationTaskOption(text_en="W-2 wages only", text_es="Solo salario de W-2", is_correct=False, sort_order=0),
            CaseSimulationTaskOption(text_en="W-2 wages and 1099-NEC self-employment income", text_es="Salario de W-2 e ingreso independiente de 1099-NEC", is_correct=True, sort_order=1),
            CaseSimulationTaskOption(text_en="1099-NEC income only", text_es="Solo ingreso de 1099-NEC", is_correct=False, sort_order=2),
            CaseSimulationTaskOption(text_en="No income to report", text_es="Ningún ingreso que declarar", is_correct=False, sort_order=3),
        ]
        case.tasks.append(mc_task)

        ms_task = CaseSimulationTask(
            task_type="multi_select", points=2, sort_order=1,
            prompt_en="Which documents did Jordan actually provide at this intake? Select all that apply.",
            prompt_es="¿Qué documentos entregó Jordan realmente en esta admisión? Selecciona todas las que apliquen.",
            explanation_en="Only the W-2 and 1099-NEC were provided — no prior return or ID was mentioned in the documents.",
            explanation_es="Solo se entregaron el W-2 y el 1099-NEC — no se mencionó una declaración anterior ni identificación.",
        )
        ms_task.options = [
            CaseSimulationTaskOption(text_en="W-2", text_es="W-2", is_correct=True, sort_order=0),
            CaseSimulationTaskOption(text_en="1099-NEC", text_es="1099-NEC", is_correct=True, sort_order=1),
            CaseSimulationTaskOption(text_en="Prior year tax return", text_es="Declaración del año anterior", is_correct=False, sort_order=2),
            CaseSimulationTaskOption(text_en="Passport / photo ID", text_es="Pasaporte / identificación con foto", is_correct=False, sort_order=3),
        ]
        case.tasks.append(ms_task)

        sa_task = CaseSimulationTask(
            task_type="short_answer", points=2, sort_order=2,
            prompt_en="What is the total reported income across the W-2 and 1099-NEC? (numbers only)",
            prompt_es="¿Cuál es el ingreso total declarado entre el W-2 y el 1099-NEC? (solo números)",
            explanation_en="$45,000 (W-2 Box 1) + $8,500 (1099-NEC Box 1) = $53,500.",
            explanation_es="$45,000 (W-2 Casilla 1) + $8,500 (1099-NEC Casilla 1) = $53,500.",
        )
        sa_task.accepted_answers = [
            CaseSimulationTaskAcceptedAnswer(answer_en="53500", answer_es="53500"),
            CaseSimulationTaskAcceptedAnswer(answer_en="$53,500", answer_es="$53,500"),
            CaseSimulationTaskAcceptedAnswer(answer_en="53,500", answer_es="53.500"),
        ]
        case.tasks.append(sa_task)

        fr_task = CaseSimulationTask(
            task_type="free_response", points=3, sort_order=3, requires_justification=False,
            prompt_en="Jordan's intake notes mention driving for a delivery app, but no 1099 was provided for it. What would you do next, and why?",
            prompt_es="Las notas de admisión de Jordan mencionan que manejó para una app de entrega, pero no se entregó un 1099 por eso. ¿Qué harías a continuación, y por qué?",
            expected_response_en=(
                "Ask the client directly whether they received a 1099 for the delivery app income, or whether they "
                "kept their own records (mileage, deposits) even without one. Self-employment income must be "
                "reported whether or not a 1099 was issued, so this should be clarified and documented before "
                "continuing rather than ignored."
            ),
            expected_response_es=(
                "Preguntarle directamente al cliente si recibió un 1099 por el ingreso de la app de entrega, o si "
                "llevó sus propios registros (millaje, depósitos) aunque no lo tenga. El ingreso de trabajo "
                "independiente debe declararse aunque no se haya emitido un 1099, así que esto debe aclararse y "
                "documentarse antes de continuar, en vez de ignorarse."
            ),
            rubric_notes_en="Look for: recognizing the under-reported income risk, proactively requesting clarification/records from the client, not simply ignoring the gap or filing without addressing it.",
            rubric_notes_es="Buscar: reconocer el riesgo de ingreso no declarado, pedir proactivamente aclaración/registros al cliente, no ignorar el vacío ni presentar sin resolverlo.",
        )
        case.tasks.append(fr_task)

        db.session.commit()
        print(f"Created demo course id={course.id} slug={course.slug}, lesson id={lesson.id}, case id={case.id} (unpublished).")


if __name__ == "__main__":
    run()
