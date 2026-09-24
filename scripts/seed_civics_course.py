"""Creates the permanent, published OG Academy course that hosts the Civics Test
module — "Practice for Exam and Citizenship Interview Simulation" — requested
explicitly by the client so it shows up under Courses.

Run once: .venv/Scripts/python.exe scripts/seed_civics_course.py
"""

from app import create_app
from app.extensions import db
from app.models import Course, CourseSection, Lesson

SLUG = "practica-examen-simulacion-entrevista-ciudadania"


def run():
    app = create_app()
    with app.app_context():
        if Course.query.filter_by(slug=SLUG).first():
            print("Course already exists — nothing to do.")
            return

        course = Course(
            slug=SLUG,
            category="Citizenship",
            title_en="Citizenship Exam Practice & Interview Simulation",
            title_es="Práctica para Examen y Simulación de Entrevista de Ciudadanía",
            subtitle_en="Study the official 128 civics questions, then practice a real mock USCIS interview.",
            subtitle_es="Estudia las 128 preguntas oficiales de civismo y practica una entrevista simulada real de USCIS.",
            description_en=(
                "Prepare for the U.S. citizenship interview with the official USCIS civics questions. "
                "Use Study Mode to practice at your own pace with instant feedback, or take the Mock "
                "Interview Simulation for a realistic, timed practice run that mirrors the real exam."
            ),
            description_es=(
                "Prepárate para la entrevista de ciudadanía estadounidense con las preguntas oficiales de "
                "civismo de USCIS. Usa el Modo de Estudio para practicar a tu propio ritmo con "
                "retroalimentación inmediata, o toma la Simulación de Entrevista para una práctica "
                "realista que imita el examen real."
            ),
            is_published=True,
            sort_order=0,
        )
        section = CourseSection(title_en="Civics Test", title_es="Examen de Civismo", sort_order=0)
        lesson = Lesson(
            lesson_type="civics_test",
            title_en="Civics Test Practice & Simulation",
            title_es="Práctica y Simulación del Examen de Civismo",
            sort_order=0,
            is_preview=False,
        )
        section.lessons.append(lesson)
        course.sections.append(section)
        db.session.add(course)
        db.session.commit()
        print(f"Created course id={course.id} slug={course.slug} with lesson id={lesson.id}")


if __name__ == "__main__":
    run()
