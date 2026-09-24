"""Reorganizes the existing Citizenship course into four real, separately-
trackable sections/lessons — Study, Practice, Test Yourself, Virtual
Interview — per the approved OG Academy architecture plan.

Purely additive and idempotent: the existing "Civics Test" section and its
civics_test lesson (id preserved) are NOT deleted or recreated — any existing
CivicsTestSession/LessonProgress rows that reference them keep working
unchanged. This script only retitles that section/lesson, adds three new
sections+lessons around it, and seeds one default (non-real-person) Officer
Profile if none exist yet.

Safe to re-run: if the course already has 4 sections, it prints a message
and exits without changing anything.

Run once: .venv/Scripts/python.exe scripts/reorganize_citizenship_course.py
"""

from app import create_app
from app.extensions import db
from app.models import Course, CourseSection, InterviewScenario, Lesson, OfficerProfile
from app.models import CIVICS_MAX_QUESTIONS, CIVICS_PASSING_SCORE

SLUG = "practica-examen-simulacion-entrevista-ciudadania"

DEFAULT_OFFICER_NAME = "Officer Rivera"
DEFAULT_OFFICER_TONE_EN = "Calm, professional, and reassuring — like a considerate real USCIS officer conducting a routine interview."
DEFAULT_OFFICER_TONE_ES = "Calmado, profesional y tranquilizador — como un oficial de USCIS considerado en una entrevista de rutina."


def run():
    app = create_app()
    with app.app_context():
        course = Course.query.filter_by(slug=SLUG).first()
        if not course:
            print("Citizenship course not found (run scripts/seed_civics_course.py first) — nothing to do.")
            return

        if len(course.sections) >= 4:
            print("Course already has 4+ sections — assuming it's already reorganized. Nothing to do.")
            return

        if len(course.sections) != 1 or len(course.sections[0].lessons) != 1:
            print(f"Unexpected course shape ({len(course.sections)} section(s)) — stopping without changes. "
                  "Inspect manually before proceeding.")
            return

        existing_section = course.sections[0]
        existing_lesson = existing_section.lessons[0]
        if existing_lesson.lesson_type != "civics_test":
            print(f"Existing lesson is type={existing_lesson.lesson_type!r}, not civics_test — stopping without changes.")
            return

        # 1. Default Officer Profile (only if none exist yet) — a configurable
        #    persona, never a real person; no avatar means the UI shows a
        #    neutral placeholder icon.
        officer = OfficerProfile.query.order_by(OfficerProfile.sort_order, OfficerProfile.id).first()
        if not officer:
            officer = OfficerProfile(
                name=DEFAULT_OFFICER_NAME,
                voice="onyx",
                languages="en,es",
                tone_en=DEFAULT_OFFICER_TONE_EN,
                tone_es=DEFAULT_OFFICER_TONE_ES,
                is_active=True,
                sort_order=0,
            )
            db.session.add(officer)
            db.session.flush()
            print(f"Created default Officer Profile: {officer.name} (id={officer.id})")

        # 2. Retitle the existing section/lesson in place — Section 3, Test Yourself.
        existing_section.title_en = "Test Yourself"
        existing_section.title_es = "Evalúate a Ti Mismo"
        existing_section.sort_order = 2
        existing_lesson.title_en = "Test Yourself — Civics Test Simulation"
        existing_lesson.title_es = "Evalúate a Ti Mismo — Simulación del Examen de Civismo"
        existing_lesson.sort_order = 0

        # 3. Section 1 — Study.
        study_section = CourseSection(course_id=course.id, title_en="Study the 128 Civics Questions",
                                       title_es="Estudia las 128 Preguntas de Civismo", sort_order=0)
        study_section.lessons.append(Lesson(
            lesson_type="civics_study", title_en="Study the 128 Civics Questions",
            title_es="Estudia las 128 Preguntas de Civismo", sort_order=0, is_preview=False,
        ))
        db.session.add(study_section)

        # 4. Section 2 — Practice.
        practice_section = CourseSection(course_id=course.id, title_en="Practice",
                                          title_es="Práctica", sort_order=1)
        practice_section.lessons.append(Lesson(
            lesson_type="civics_practice", title_en="Practice", title_es="Práctica",
            sort_order=0, is_preview=False,
        ))
        db.session.add(practice_section)

        # 5. Section 4 — Virtual Interview (+ its InterviewScenario, wired to the officer).
        interview_section = CourseSection(course_id=course.id, title_en="Virtual Interview",
                                           title_es="Entrevista Virtual", sort_order=3)
        interview_lesson = Lesson(
            lesson_type="interview_simulation", title_en="Virtual Interview", title_es="Entrevista Virtual",
            sort_order=0, is_preview=False,
        )
        interview_section.lessons.append(interview_lesson)
        db.session.add(interview_section)
        db.session.flush()

        db.session.add(InterviewScenario(
            lesson_id=interview_lesson.id,
            officer_profile_id=officer.id,
            scenario_type="civics",
            max_questions=CIVICS_MAX_QUESTIONS,
            passing_score=CIVICS_PASSING_SCORE,
        ))

        db.session.commit()
        print("Reorganized Citizenship course into 4 sections: Study, Practice, Test Yourself, Virtual Interview.")
        print(f"Existing lesson id={existing_lesson.id} (civics_test) preserved — its prior sessions/progress still resolve correctly.")


if __name__ == "__main__":
    run()
