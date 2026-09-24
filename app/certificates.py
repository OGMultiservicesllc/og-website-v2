import base64
import io
from datetime import datetime

import qrcode
from flask import url_for

from app.progress import course_lessons, course_progress, is_lesson_completed

CERTIFICATE_DISCLAIMER = (
    "This certificate confirms completion of an OG Academy training course. It does not "
    "constitute a state license, notary commission, government certification, or "
    "professional license unless explicitly stated otherwise."
)


def is_certificate_eligible(student, course):
    """Whether the student currently satisfies this course's certificate
    trigger — used both to gate the student-facing certificate page and as
    a defensive fallback in case the proactive issuance hook was missed."""
    if course.certificate_trigger == "final_exam_passed":
        final_lessons = [
            lesson for lesson in course_lessons(course)
            if lesson.lesson_type == "quiz" and lesson.quiz_kind == "final"
        ]
        if not final_lessons:
            return False
        return any(is_lesson_completed(student, lesson) for lesson in final_lessons)
    return course_progress(student, course)["is_complete"]


def generate_qr_data_uri(url):
    """Renders a QR code for `url` as a base64 PNG data URI — embedded
    inline so the certificate prints/PDFs correctly with no external
    network request and nothing to store on disk."""
    img = qrcode.make(url, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_cert_context(course, lang, student=None, certificate=None):
    """Assembles the template context consumed by the certificate macros.
    Pass `student`/`certificate` for a real issued certificate; omit both
    for the admin's sample "preview the template" screen."""
    accent = course.accent_color or "#b8860b"
    logo_url = (
        url_for("public.certificate_asset", lang=lang, course_id=course.id, stored_path=course.certificate_logo_image)
        if course.certificate_logo_image else None
    )
    signature_url = (
        url_for("public.certificate_asset", lang=lang, course_id=course.id, stored_path=course.certificate_signature_image)
        if course.certificate_signature_image else None
    )

    student_name = student.name if student else "Jane A. Sample"
    cert_id = certificate.code if certificate else "OG-PREVIEW"
    issued_at = certificate.issued_at if certificate and certificate.issued_at else datetime.utcnow()
    revoked = bool(certificate and certificate.is_revoked)
    verify_code = certificate.code if certificate else "PREVIEW"
    verify_url = url_for("public.certificate_verify", lang=lang, code=verify_code, _external=True)

    return {
        "title": course.cert_title(),
        "student_name": student_name,
        "course_title": course.title(lang),
        "date": issued_at.strftime("%B %d, %Y"),
        "cert_id": cert_id,
        "issuer_name": course.cert_issuer_name(),
        "issuer_subtitle": course.cert_issuer_subtitle(),
        "signatory_name": course.cert_signatory_name(),
        "signatory_title": course.cert_signatory_title(),
        "logo_url": logo_url,
        "signature_url": signature_url,
        "accent_color": accent,
        "show_id": course.certificate_show_id,
        "show_qr": course.certificate_show_qr,
        "qr_data_uri": generate_qr_data_uri(verify_url) if course.certificate_show_qr else None,
        "verify_url": verify_url,
        "disclaimer": CERTIFICATE_DISCLAIMER,
        "revoked": revoked,
    }
