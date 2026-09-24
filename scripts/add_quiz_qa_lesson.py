"""Adds a "Quiz Builder QA" section+lesson to the existing (unpublished) demo
course, purely as a QA fixture to exercise all 8 quiz question types through
the real Admin UI — does not touch Notary or any other real course content.
Safe to re-run (skips if it already exists).

Run once: .venv/Scripts/python.exe scripts/add_quiz_qa_lesson.py
"""

from app import create_app
from app.extensions import db
from app.models import Course, CourseSection, Lesson

SLUG = "og-forensic-training-demo"


def run():
    app = create_app()
    with app.app_context():
        course = Course.query.filter_by(slug=SLUG).first()
        if not course:
            print("Demo course not found — run scripts/seed_demo_case.py first.")
            return

        if any(s.title_en == "Quiz Builder QA" for s in course.sections):
            print("Section already exists — nothing to do.")
            return

        section = CourseSection(course_id=course.id, title_en="Quiz Builder QA", title_es="QA del Constructor de Evaluaciones", sort_order=1)
        lesson = Lesson(
            lesson_type="quiz", title_en="Quiz Builder QA — All Question Types",
            title_es="QA del Constructor — Todos los Tipos de Pregunta",
            sort_order=0, is_preview=False,
        )
        section.lessons.append(lesson)
        db.session.add(section)
        db.session.commit()
        print(f"Added Quiz Builder QA lesson id={lesson.id}.")


if __name__ == "__main__":
    run()
