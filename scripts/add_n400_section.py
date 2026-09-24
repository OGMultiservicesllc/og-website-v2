"""Adds "Section 5 — N-400 Interview Practice" to the existing Citizenship
course — purely additive, does not touch the existing 4 sections/lessons or
any student data. Safe to re-run (skips if the section already exists).

Run once: .venv/Scripts/python.exe scripts/add_n400_section.py
"""

from app import create_app
from app.extensions import db
from app.models import Course, CourseSection, InterviewScenario, Lesson, OfficerProfile
from app.models import N400_MAX_QUESTIONS, CIVICS_PASSING_SCORE

SLUG = "practica-examen-simulacion-entrevista-ciudadania"


def run():
    app = create_app()
    with app.app_context():
        course = Course.query.filter_by(slug=SLUG).first()
        if not course:
            print("Citizenship course not found — nothing to do.")
            return

        if any(s.title_en == "N-400 Interview Practice" for s in course.sections):
            print("Section already exists — nothing to do.")
            return

        officer = OfficerProfile.query.filter_by(is_active=True).order_by(OfficerProfile.sort_order, OfficerProfile.id).first()
        if not officer:
            print("No active Officer Profile found — create one first (see scripts/reorganize_citizenship_course.py).")
            return

        section = CourseSection(
            course_id=course.id, title_en="N-400 Interview Practice", title_es="Práctica de Entrevista N-400",
            sort_order=4,
        )
        lesson = Lesson(
            lesson_type="interview_simulation", title_en="N-400 Interview Practice",
            title_es="Práctica de Entrevista N-400", sort_order=0, is_preview=False,
        )
        section.lessons.append(lesson)
        db.session.add(section)
        db.session.flush()

        db.session.add(InterviewScenario(
            lesson_id=lesson.id, officer_profile_id=officer.id, scenario_type="n400",
            max_questions=N400_MAX_QUESTIONS, passing_score=CIVICS_PASSING_SCORE,
        ))
        db.session.commit()
        print(f"Added Section 5 — N-400 Interview Practice (lesson id={lesson.id}) using officer '{officer.name}'.")


if __name__ == "__main__":
    run()
