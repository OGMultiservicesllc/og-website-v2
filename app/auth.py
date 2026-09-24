import hmac
from functools import wraps

from flask import flash, redirect, request, session, url_for
from werkzeug.security import check_password_hash


def check_admin_credentials(email, password):
    from app.models import AdminUser

    email = (email or "").strip().lower()
    if not email or not password:
        return None

    user = AdminUser.query.filter(AdminUser.email.ilike(email)).first()
    if not user or not user.is_active:
        return None
    if not check_password_hash(user.password_hash, password):
        return None
    return user


def is_admin_logged_in():
    return session.get("admin_logged_in") is True


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not is_admin_logged_in():
            flash("Please log in to access the admin area.", "error")
            return redirect(url_for("admin.login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped


def validate_csrf(token):
    expected = session.get("csrf_token", "")
    return bool(expected) and bool(token) and hmac.compare_digest(expected, token)


def safe_admin_next(next_url):
    """Where to send an admin after login. Only a same-site path is accepted — never a full URL,
    a protocol-relative //host, or a backslash trick — mirroring the exact same protections
    `app.blueprints.account.routes._safe_next` already applies on the customer side (Production
    Launch Readiness Audit, 2026-09-23: the admin login previously redirected to `next` with no
    validation at all, an open redirect). Returns None if `next_url` isn't safe."""
    if (
        next_url
        and next_url.startswith("/")
        and not next_url.startswith("//")
        and "\\" not in next_url
        and "://" not in next_url
        and ".." not in next_url
    ):
        return next_url
    return None
