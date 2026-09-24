import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    APP_ENV = os.environ.get("APP_ENV", "development")
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///og_website_v2.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # True only in production (behind real HTTPS via Nginx) — the session cookie (which also carries the
    # CSRF token, see app/__init__.py's ensure_csrf_token) must never be sendable over plain HTTP once a
    # real deployment exists. Left False in development so the local dev server (plain HTTP) keeps
    # working exactly as before — a cookie marked Secure is simply never SENT over an insecure connection,
    # which would silently break every login locally if this were hardcoded True. See Production Launch
    # Readiness Audit, 2026-09-23, finding E4.
    SESSION_COOKIE_SECURE = os.environ.get("APP_ENV") == "production"

    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
    ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")

    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

    # Square (OG Payments) — sandbox only until docs/SQUARE_PRODUCTION_ACTIVATION.md is followed.
    # SQUARE_APPLICATION_ID and SQUARE_LOCATION_ID are safe to reach the browser (they identify the
    # merchant/app to Square's own Web Payments SDK, not a secret); SQUARE_ACCESS_TOKEN and
    # SQUARE_WEBHOOK_SIGNATURE_KEY are server-only and must never be sent to the frontend.
    SQUARE_ENVIRONMENT = os.environ.get("SQUARE_ENVIRONMENT", "sandbox")
    SQUARE_APPLICATION_ID = os.environ.get("SQUARE_APPLICATION_ID", "")
    SQUARE_ACCESS_TOKEN = os.environ.get("SQUARE_ACCESS_TOKEN", "")
    SQUARE_LOCATION_ID = os.environ.get("SQUARE_LOCATION_ID", "")
    SQUARE_WEBHOOK_SIGNATURE_KEY = os.environ.get("SQUARE_WEBHOOK_SIGNATURE_KEY", "")
    SQUARE_WEBHOOK_URL = os.environ.get("SQUARE_WEBHOOK_URL", "")  # the exact URL registered in the Square dashboard; used to verify the signature
    SQUARE_ALLOW_PRODUCTION = os.environ.get("SQUARE_ALLOW_PRODUCTION", "") == "1"  # a second explicit opt-in beyond SQUARE_ENVIRONMENT=production — see docs/SQUARE_PRODUCTION_ACTIVATION.md

    # Every customer document upload, Files-from-OG release, course media file, and certificate lives
    # here as a plain file on disk — there is no secondary copy anywhere. The default is INSIDE the
    # code checkout, which is fine for local development but unsafe in production: a redeploy strategy
    # that replaces the code directory (fresh clone, `rsync --delete`, a container rebuild without a
    # mounted volume) would destroy every customer's documents. Production MUST set this explicitly to
    # a path OUTSIDE the deployed code, on storage covered by the backup plan — see
    # docs/PRODUCTION_MEDIA_STORAGE.md. `validate_for_production()` below refuses to start if this is
    # still the in-repo default. See Production Launch Readiness Audit, 2026-09-23, finding E5.
    _DEFAULT_COURSE_MEDIA_DIR = os.path.join(BASE_DIR, "instance", "course_media")
    COURSE_MEDIA_DIR = os.environ.get("COURSE_MEDIA_DIR", _DEFAULT_COURSE_MEDIA_DIR)
    MAX_CONTENT_LENGTH = 600 * 1024 * 1024  # 600MB cap on any single upload

    # Transactional email (Titan/Bluehost SMTP) — see docs/TRANSACTIONAL_EMAIL_SETUP.md.
    # MAIL_ENABLED is the explicit switch required before ANY SMTP delivery is attempted (a second,
    # deliberate opt-in — same belt-and-suspenders pattern as SQUARE_ALLOW_PRODUCTION above). Default is
    # OFF, so a fresh clone or a test run never sends real mail by accident. SMTP_PASSWORD is a secret and
    # must never be logged, returned to the browser, or written anywhere but this environment variable.
    MAIL_ENABLED = os.environ.get("MAIL_ENABLED", "") == "1"
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.titan.email")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "465") or "465")
    SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "true").lower() != "false"
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    MAIL_FROM_EMAIL = os.environ.get("MAIL_FROM_EMAIL", "info@ogmultiservicesllc.com")
    MAIL_FROM_NAME = os.environ.get("MAIL_FROM_NAME", "OG Multiservices LLC")
    MAIL_REPLY_TO = os.environ.get("MAIL_REPLY_TO", "info@ogmultiservicesllc.com")
    # The public HTTPS origin used to build every link inside an email (e.g. "https://ogmultiservicesllc.com").
    # Deliberately has NO safe default of "http://localhost:5001" for production — see validate_for_production.
    APP_PUBLIC_URL = os.environ.get("APP_PUBLIC_URL", "http://localhost:5001")
    # Development safety net (item 15): outside production, if this is set, every outgoing email's actual
    # envelope recipient is redirected here instead of the real customer address — the EmailLog still
    # records the true intended recipient for audit. Optional; MAIL_ENABLED defaulting to off is already
    # the primary safeguard, this is a second layer for when a developer deliberately turns mail on locally.
    MAIL_DEV_REDIRECT_TO = os.environ.get("MAIL_DEV_REDIRECT_TO", "")

    @staticmethod
    def validate_for_production():
        if os.environ.get("APP_ENV") == "production":
            if os.environ.get("SECRET_KEY", "dev-only-insecure-key") == "dev-only-insecure-key":
                raise RuntimeError(
                    "SECRET_KEY must be set to a real value when APP_ENV=production."
                )
            if not os.environ.get("ADMIN_EMAIL") or not os.environ.get("ADMIN_PASSWORD_HASH"):
                raise RuntimeError(
                    "ADMIN_EMAIL and ADMIN_PASSWORD_HASH must be set when APP_ENV=production."
                )
            course_media_dir = os.environ.get("COURSE_MEDIA_DIR", "")
            if not course_media_dir or os.path.normcase(os.path.normpath(course_media_dir)) == os.path.normcase(
                os.path.normpath(Config._DEFAULT_COURSE_MEDIA_DIR)
            ):
                raise RuntimeError(
                    "COURSE_MEDIA_DIR must be set to a real path OUTSIDE the deployed code directory when "
                    "APP_ENV=production — this is where every customer document lives; the in-repo default "
                    "is not safe for production (see docs/PRODUCTION_MEDIA_STORAGE.md)."
                )
            if os.environ.get("MAIL_ENABLED", "") == "1":
                if not os.environ.get("SMTP_USERNAME") or not os.environ.get("SMTP_PASSWORD"):
                    raise RuntimeError(
                        "SMTP_USERNAME and SMTP_PASSWORD must be set when MAIL_ENABLED=1 in production."
                    )
                public_url = os.environ.get("APP_PUBLIC_URL", "")
                if not public_url or "localhost" in public_url or "127.0.0.1" in public_url:
                    raise RuntimeError(
                        "APP_PUBLIC_URL must be set to the real production HTTPS origin when MAIL_ENABLED=1 in production."
                    )
