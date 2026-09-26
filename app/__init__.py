import os
import secrets

from flask import Flask, abort, redirect, request, session, url_for

from config import Config
from app.extensions import db, migrate
from app.i18n import DEFAULT_LANGUAGE, get_text, valid_language
from app import business_info
from app.auth import is_admin_logged_in
from app.media_library import media_url
from app.site_content import site_asset, site_focus, site_text
from app.forms_engine import field_icon, field_input_kind
from app.intake_records import client_spec as _records_spec
from app.nav import main_nav, nav_categories, pages_for_section, standalone_top_pages
from app.student_auth import current_student
from app.video_embed import to_embed_url

# Imported so Alembic's autogenerate (flask db migrate) can see every model.
from app import models  # noqa: F401


def create_app(config_class=Config):
    config_class.validate_for_production()

    app = Flask(__name__)
    app.config.from_object(config_class)
    os.makedirs(app.config["COURSE_MEDIA_DIR"], exist_ok=True)

    if app.config.get("APP_ENV") == "production":
        # Trust exactly ONE reverse-proxy hop: Internet -> Nginx -> Gunicorn -> Flask. Nginx is the
        # only thing between the client and this app in production, so we trust its X-Forwarded-For
        # (real client IP -> request.remote_addr, used by app/ratelimit.py and by the IP recorded on
        # Tax/DL terms acceptance) and X-Forwarded-Proto (real scheme -> request.scheme / request.is_secure,
        # needed for correct https:// URLs and for SESSION_COOKIE_SECURE to behave correctly) exactly
        # once each. x_host/x_port/x_prefix are left untrusted (0) — Nginx is expected to proxy_pass the
        # real Host header through unchanged, so there is nothing there we need to trust. Gated to
        # APP_ENV=production only: outside production there is no proxy in front of the dev server, so
        # trusting a forwarded header here would let a request simply claim any IP/scheme it likes.
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0, x_port=0, x_prefix=0)

    db.init_app(app)
    migrate.init_app(app, db)
    app.jinja_env.filters["embed_url"] = to_embed_url
    app.jinja_env.globals["media_url"] = media_url

    from app.blueprints.public.routes import public_bp
    from app.blueprints.admin.routes import admin_bp
    from app.blueprints.account.routes import account_bp
    from app.blueprints.admin import pages_routes  # noqa: F401  (registers routes onto admin_bp)
    from app.blueprints.admin import blog_routes  # noqa: F401  (registers routes onto admin_bp)
    from app.blueprints.admin import inquiries_routes  # noqa: F401  (registers routes onto admin_bp)
    from app.blueprints.admin import media_routes  # noqa: F401  (registers routes onto admin_bp)
    from app.blueprints.admin import services_routes  # noqa: F401  (registers routes onto admin_bp)
    from app.blueprints.admin import site_pages_routes  # noqa: F401  (registers routes onto admin_bp)
    from app.blueprints.admin import nav_routes  # noqa: F401  (registers routes onto admin_bp)
    from app.blueprints.admin import customers_routes  # noqa: F401  (registers routes onto admin_bp)
    from app.blueprints.admin import settings_routes  # noqa: F401  (registers routes onto admin_bp)
    from app.blueprints.admin import forms_routes  # noqa: F401  (registers routes onto admin_bp)
    from app.blueprints.admin import ds260_routes  # noqa: F401  (registers routes onto admin_bp)
    from app.blueprints.admin import itin_routes  # noqa: F401  (ITIN / W-7 admin routes)
    from app.blueprints.admin import tax_routes as admin_tax_routes  # noqa: F401  (Tax Smart Intake admin + pricing)
    from app.blueprints.admin import dl_routes as admin_dl_routes  # noqa: F401  (NJ Driver License admin + pricing + locations + question bank)
    from app.blueprints.admin import consent_travel_routes as admin_ct_routes  # noqa: F401  (Consent to Travel admin + approval + pricing)
    from app.blueprints.admin import case_routes as admin_case_routes  # noqa: F401  (registers routes onto admin_bp)
    from app.blueprints.admin import client_cases_routes  # noqa: F401  (registers routes onto admin_bp)
    from app.blueprints.admin import payments_routes as admin_payments_routes  # noqa: F401  (OG Payments admin actions)
    from app.blueprints.admin import persons_routes  # noqa: F401  (real-person view)
    from app.blueprints.admin import email_routes as admin_email_routes  # noqa: F401  (transactional email visibility + SMTP test tool)
    from app.blueprints.admin import notifications_routes as admin_notifications_routes  # noqa: F401  (Notification Center)
    from app.blueprints.admin import customer_import_routes  # noqa: F401  (Wix customer CSV import + invitations)
    from app.blueprints.admin import case_summary_routes  # noqa: F401  (Case Summary PDF downloads)
    from app.blueprints.public import intake_routes  # noqa: F401  (registers routes onto public_bp)
    from app.blueprints.public import tax_routes  # noqa: F401  (Tax Smart Intake)
    from app.blueprints.public import dl_routes  # noqa: F401  (NJ Driver License Assistance)
    from app.blueprints.public import dl_practice_routes  # noqa: F401  (NJ Knowledge Test practice center)
    from app.blueprints.public import consent_travel_routes  # noqa: F401  (Consent to Travel Authorization for Minors)
    from app.blueprints.account import portal_routes  # noqa: F401  (registers routes onto account_bp)
    from app.blueprints.account import verify_routes  # noqa: F401  (mandatory email verification screens)
    from app.blueprints.account import password_routes  # noqa: F401  (forgot/reset password)
    from app.blueprints.account import activate_routes  # noqa: F401  (Wix migration: Activate My Account)
    from app.blueprints.account import case_routes as account_case_routes  # noqa: F401  (registers routes onto account_bp)
    from app.blueprints.account import cases_portal_routes  # noqa: F401  (registers routes onto account_bp)
    from app.blueprints.account import payments_routes  # noqa: F401  (OG Payments — My Account Payments + Square pay flow)

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(account_bp)

    @app.route("/")
    def root_redirect():
        return redirect(f"/{DEFAULT_LANGUAGE}/", code=301)

    @app.route("/robots.txt")
    def robots_txt():
        from flask import Response
        from app.models import SiteSettings
        from app.seo import WORKFLOW_DISALLOW_PATHS

        settings = SiteSettings.get()
        if settings.block_search_indexing:
            lines = ["User-agent: *", "Disallow: /"]
        else:
            lines = ["User-agent: *", "Allow: /", "Disallow: /admin/", "Disallow: /*/account/"]
            lines += [f"Disallow: {p}" for p in WORKFLOW_DISALLOW_PATHS]
            lines.append(f"Sitemap: {request.url_root.rstrip('/')}/sitemap.xml")
        return Response("\n".join(lines), mimetype="text/plain")

    @app.route("/webhooks/square", methods=["POST"])
    def square_webhook():
        """Phase 9: never trusts a browser redirect as proof of payment — this is the authoritative,
        server-to-server confirmation path. No language prefix (Square doesn't know about /en//es/) and no
        student session (Square, not a customer, calls this). Signature verification is mandatory; an
        unverifiable request is rejected before any data is touched."""
        import json

        from app import square_client
        from app.payments import handle_square_webhook_event

        signature = request.headers.get("x-square-hmacsha256-signature", "")
        notification_url = app.config.get("SQUARE_WEBHOOK_URL") or request.url_root.rstrip("/") + "/webhooks/square"
        if not square_client.verify_webhook_signature(request.get_data(), signature, notification_url):
            app.logger.warning("[payments] rejected a Square webhook with an invalid signature")
            abort(401)
        try:
            payload = json.loads(request.get_data())
        except ValueError:
            abort(400)
        handle_square_webhook_event(payload.get("type", ""), payload.get("data") or {})
        return "", 200

    @app.route("/sitemap.xml")
    def sitemap_xml():
        from flask import Response
        from app.models import BlogPost, Course, Page, ServiceCategory

        static_endpoints = [
            "public.home", "public.services", "public.courses",
            "public.blog", "public.about", "public.contact", "public.resources",
            "public.locations_hub", "public.location_paterson", "public.location_spring",
            # NJ Knowledge Test practice: the explainer page is genuinely public (no account
            # required, meaningful standalone content) and worth its own sitemap entry.
            # `/practice/modes` and everything past it (@student_required) is deliberately NOT
            # sitemapped — it has no content for an anonymous visitor/crawler, it only ever
            # redirects them to sign in.
            "public.dl_practice_home",
        ]
        urls = []
        for lang in ("en", "es"):
            for endpoint in static_endpoints:
                urls.append(url_for(endpoint, lang=lang, _external=True))
            for cat in ServiceCategory.query.filter_by(is_published=True).order_by(ServiceCategory.sort_order).all():
                urls.append(url_for(cat.endpoint, lang=lang, _external=True))
                if cat.subpage_endpoint:
                    for svc in cat.published_services:
                        urls.append(url_for(cat.subpage_endpoint, lang=lang, slug=svc.slug, _external=True))
            for page in Page.query.filter_by(is_published=True).all():
                urls.append(url_for("public.page_view", lang=lang, slug=page.slug, _external=True))
            for post in BlogPost.query.filter_by(is_published=True).all():
                urls.append(url_for("public.blog_post", lang=lang, slug=post.slug, _external=True))
            for course in Course.query.filter_by(is_published=True).all():
                urls.append(url_for("public.course_detail", lang=lang, slug=course.slug, _external=True))

        xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        xml += [f"<url><loc>{u}</loc></url>" for u in urls]
        xml.append("</urlset>")
        return Response("\n".join(xml), mimetype="application/xml")

    @app.route("/site-logo")
    def site_logo():
        from flask import send_file
        from app.models import SiteSettings
        from app.uploads import course_media_full_path

        settings = SiteSettings.get()
        if not settings.logo_filename:
            abort(404)
        full_path = course_media_full_path(settings.logo_filename)
        if not os.path.isfile(full_path):
            abort(404)
        return send_file(full_path, conditional=True)

    @app.route("/media/<int:asset_id>/<path:name>")
    def media_asset(asset_id, name):
        """Public site imagery from the Media Library (not client documents)."""
        from flask import send_file
        from app.media_library import thumbnail_path
        from app.models import MediaAsset
        from app.uploads import course_media_full_path

        asset = db.session.get(MediaAsset, asset_id)
        if not asset:
            abort(404)
        width = request.args.get("w", type=int)
        path = thumbnail_path(asset, width) if width else course_media_full_path(asset.stored_path)
        if not path or not os.path.isfile(path):
            abort(404)
        response = send_file(path, conditional=True, max_age=60 * 60 * 24 * 30)
        return response

    @app.before_request
    def ensure_csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)

    @app.context_processor
    def inject_globals():
        lang = request.view_args.get("lang", DEFAULT_LANGUAGE) if request.view_args else DEFAULT_LANGUAGE
        if not valid_language(lang):
            lang = DEFAULT_LANGUAGE

        def t(key):
            return get_text(lang, key)

        def st(key):
            return site_text(key, lang)

        admin_active = is_admin_logged_in()
        new_inquiry_count = 0
        admin_alert_count = 0
        admin_recent_notifications = []
        if admin_active:
            from app.models import Inquiry

            new_inquiry_count = Inquiry.query.filter_by(status="new").count()
            # Admin bell count / dropdown reuse the SAME Notification Center query the full page uses
            # (app/notifications.py) — never a second, independently-derived notion of "what's unread".
            from app import notifications as notif

            admin_alert_count = notif.unread_count()
            admin_recent_notifications = notif.recent(limit=6)

        from app.models import SiteSettings

        site_settings = SiteSettings.get()
        sameas_urls = [
            url
            for url in (
                site_settings.facebook_url,
                site_settings.instagram_url,
                site_settings.tiktok_url,
                site_settings.youtube_url,
                site_settings.linkedin_url,
            )
            if url and url.strip()
        ]

        def logo_url(external=False):
            if site_settings.logo_filename:
                return url_for("site_logo", _external=external)
            return url_for("static", filename="img/logo.png", _external=external)

        def switch_url():
            other_lang = "es" if lang == "en" else "en"
            if not request.view_args:
                return f"/{other_lang}/"
            try:
                other_args = dict(request.view_args)
                other_args["lang"] = other_lang
                return url_for(request.endpoint, **other_args)
            except Exception:
                return f"/{other_lang}/"

        def account_action_count():
            student = current_student()
            if student is None:
                return 0
            from app.account_dashboard import action_count

            return action_count(student, lang)

        from app.admin_case_nav import admin_case_url
        from app.seo import current_robots_directive

        return {
            "lang": lang,
            "t": t,
            "st": st,
            "account_action_count": account_action_count,
            "admin_case_url": admin_case_url,
            "seo_robots": current_robots_directive(),
            "admin_alert_count": admin_alert_count,
            "admin_recent_notifications": admin_recent_notifications,
            "site_asset": site_asset,
            "site_focus": site_focus,
            "media_url": media_url,
            "switch_url": switch_url,
            "biz": business_info,
            "site_settings": site_settings,
            "sameas_urls": sameas_urls,
            "logo_url": logo_url,
            "csrf_token": session.get("csrf_token", ""),
            "admin_logged_in": admin_active,
            "new_inquiry_count": new_inquiry_count,
            "student": current_student(),
            "pages_for_section": pages_for_section,
            "main_nav": main_nav(lang),
            "nav_categories": nav_categories(lang),
            "standalone_nav_pages": standalone_top_pages(),
            "field_input_kind": field_input_kind,
            "records_spec": _records_spec,
            "field_icon": field_icon,
        }

    with app.app_context():
        from app.seed_content import ensure_seeded

        ensure_seeded()

    return app
