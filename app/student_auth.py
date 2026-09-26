from functools import wraps

from flask import flash, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.i18n import get_text
from app.models import Student


def hash_password(password):
    return generate_password_hash(password)


def register_student(email, password, name):
    email = email.strip().lower()
    student = Student(email=email, password_hash=hash_password(password), name=name.strip())
    return student


def authenticate_student(email, password):
    email = (email or "").strip().lower()
    student = Student.query.filter_by(email=email).first()
    if not student or not student.is_active:
        return None
    if not check_password_hash(student.password_hash, password or ""):
        return None
    return student


def current_student():
    if not hasattr(g, "_current_student"):
        student_id = session.get("student_id")
        g._current_student = Student.query.get(student_id) if student_id else None
    return g._current_student


def student_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        # Every @student_required page is an authenticated workflow page, never marketing
        # content — this is the single choke point for noindexing all of them (Tax/NJ Driver
        # License/Consent to Travel case screens, Knowledge Test practice attempts, Academy
        # self-study, My Account...), whether the request ends in the real page, a login
        # redirect, or a verify-email redirect (see app/seo.py: relying on the auth redirect
        # alone is not enough SEO protection on its own).
        from app.seo import mark_noindex

        mark_noindex()
        lang = kwargs.get("lang", "en")
        student = current_student()
        if not student:
            flash(get_text(lang, "flash_login_required"), "error")
            return redirect(url_for("account.login", lang=lang, next=request.path))
        # Mandatory email verification (item 4): no normal My Account access or service workflow until
        # verified. A single choke point here covers every @student_required route in the app (intake
        # start, Academy, Knowledge Test practice, My Account pages, ...) — see app/verification.py.
        if not student.is_email_verified:
            return redirect(url_for("account.verify_email", lang=lang, next=request.path))
        return view_func(*args, **kwargs)

    return wrapped
