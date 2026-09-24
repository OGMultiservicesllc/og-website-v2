import secrets
from datetime import datetime

from app.activity import log_event
from app.extensions import db
from app.models import Certificate, LessonProgress


def course_lessons(course):
    return [lesson for section in course.sections for lesson in section.lessons]


def course_progress(student, course):
    lessons = course_lessons(course)
    total = len(lessons)
    if total == 0 or not student:
        return {"completed": 0, "total": total, "percent": 0, "is_complete": False}

    lesson_ids = [lesson.id for lesson in lessons]
    completed = LessonProgress.query.filter(
        LessonProgress.student_id == student.id,
        LessonProgress.lesson_id.in_(lesson_ids),
        LessonProgress.is_completed.is_(True),
    ).count()
    percent = round(completed / total * 100)
    return {"completed": completed, "total": total, "percent": percent, "is_complete": completed == total}


def is_lesson_completed(student, lesson):
    if not student:
        return False
    progress = LessonProgress.query.filter_by(student_id=student.id, lesson_id=lesson.id).first()
    return bool(progress and progress.is_completed)


def unlocked_lesson_ids(student, course):
    """Sequential progression: a lesson is unlocked once every lesson before
    it (in course order) is completed. The first lesson is always unlocked,
    and anything already completed stays reviewable even if it was completed
    out of order before this gating existed."""
    lessons = course_lessons(course)
    if not student:
        return set()

    completed_ids = {
        row.lesson_id
        for row in LessonProgress.query.filter_by(student_id=student.id, is_completed=True).all()
    }
    unlocked = set(completed_ids)
    blocked = False
    for lesson in lessons:
        if not blocked:
            unlocked.add(lesson.id)
        if lesson.id not in completed_ids:
            blocked = True
    return unlocked


def is_lesson_unlocked(student, course, lesson):
    return lesson.id in unlocked_lesson_ids(student, course)


def mark_lesson_complete(student, lesson):
    progress = LessonProgress.query.filter_by(student_id=student.id, lesson_id=lesson.id).first()
    if not progress:
        progress = LessonProgress(student_id=student.id, lesson_id=lesson.id)
        db.session.add(progress)
    was_completed = progress.is_completed
    if not progress.is_completed:
        progress.is_completed = True
        progress.completed_at = datetime.utcnow()
        db.session.commit()

    if not was_completed:
        course = lesson.section.course
        meta = {"course": course.title_en}
        entity = ("course", course.id)
        done_before = LessonProgress.query.filter(
            LessonProgress.student_id == student.id,
            LessonProgress.lesson_id.in_([l.id for l in course_lessons(course)]),
            LessonProgress.is_completed.is_(True),
        ).count()
        if done_before == 1:
            log_event(student.id, "course_started", entity=entity, meta=meta)
        if lesson.lesson_type == "quiz" and lesson.quiz_kind == "final":
            log_event(student.id, "final_exam_completed", entity=entity, meta=meta)
        if course_progress(student, course)["is_complete"]:
            log_event(student.id, "course_completed", entity=entity, meta=meta)
        if course.certificate_enabled:
            if course.certificate_trigger == "final_exam_passed":
                if lesson.lesson_type == "quiz" and lesson.quiz_kind == "final":
                    get_or_create_certificate(student, course)
            elif course_progress(student, course)["is_complete"]:
                get_or_create_certificate(student, course)

    return progress


def generate_certificate_code():
    return "OG-" + secrets.token_hex(4).upper()


def get_or_create_certificate(student, course):
    cert = Certificate.query.filter_by(student_id=student.id, course_id=course.id).first()
    if cert:
        return cert

    code = generate_certificate_code()
    while Certificate.query.filter_by(code=code).first():
        code = generate_certificate_code()

    cert = Certificate(student_id=student.id, course_id=course.id, code=code)
    db.session.add(cert)
    db.session.commit()
    log_event(student.id, "certificate_issued", entity=("course", course.id), meta={"course": course.title_en, "code": code})
    try:
        from app.email_service import send_transactional_email

        send_transactional_email(student, "certificate_available", student.preferred_language or "en",
                                 ref={"certificate_id": cert.id}, related_type="certificate", related_id=cert.id,
                                 dedupe_key=f"certificate_available:{cert.id}")
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("og_email").exception("[progress] certificate_available email failed to queue")
    return cert
