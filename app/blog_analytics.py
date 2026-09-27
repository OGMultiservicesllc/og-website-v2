"""First-party blog view tracking (2026-09-27) — see app/models/blog.py's BlogPostView docstring
for the schema/dedup design, and docs/ for the approved audit+plan this implements verbatim.

`record_view()` is the only entry point the public blog route calls, and it can NEVER raise: a
tracking failure (a DB hiccup, an unexpected exception in this brand-new code) must never prevent
the article itself from rendering, so every exception is caught and logged, never re-raised —
same contract as `send_transactional_email()` elsewhere in this app.

Nothing here ever stores a raw IP address or raw User-Agent string. Both are used only as inputs
to one HMAC-SHA256 digest, computed and discarded in the same request; the digest is salted with
SECRET_KEY (never a hardcoded key) and additionally keyed by the UTC calendar date, so the exact
same visitor produces a DIFFERENT hash tomorrow — the 24-hour dedup window is structural, not a
time-range query, and the hash cannot be used to correlate one visitor's reads across days or
across different articles (post id is also part of the input).
"""
import hashlib
import hmac
import logging
from datetime import datetime, timedelta

from flask import current_app, request

logger = logging.getLogger("og_blog_analytics")

# Deliberately simple, case-insensitive substring match — not a UA-parsing library. "Exclude
# obvious bots where practical" (the approved brief) does not require perfect bot detection; this
# list covers the common search/social crawlers and generic HTTP-client tools that would otherwise
# inflate an admin-facing metric.
_BOT_UA_SUBSTRINGS = (
    "bot", "spider", "crawl", "slurp", "facebookexternalhit", "whatsapp", "bingpreview",
    "python-requests", "curl", "wget", "headlesschrome", "uptimerobot", "pingdom",
)


def _is_bot_ua(user_agent):
    ua = (user_agent or "").strip().lower()
    if not ua:
        return True  # no UA at all is not a real browser visit
    return any(marker in ua for marker in _BOT_UA_SUBSTRINGS)


def _visitor_hash(ip, user_agent, post_id, today):
    secret = current_app.config.get("SECRET_KEY", "")
    payload = f"{ip}|{user_agent}|{post_id}|{today.isoformat()}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return digest[:64]


def record_view(post):
    """Record one view of `post` for the current request, deduplicated to ~one per visitor per
    UTC day. Safe to call unconditionally from the public article route — every failure mode
    (staging, admin session, bot UA, DB error) is a silent no-op, never an exception."""
    try:
        from app.seo import is_staging_host

        if is_staging_host():
            return False
        from app.auth import is_admin_logged_in

        if is_admin_logged_in():
            return False
        if _is_bot_ua(request.headers.get("User-Agent", "")):
            return False

        ip = request.remote_addr or "unknown"
        ua = request.headers.get("User-Agent", "")
        today = datetime.utcnow().date()
        visitor_hash = _visitor_hash(ip, ua, post.id, today)

        from app.extensions import db

        db.session.execute(
            db.text(
                """
                INSERT INTO blog_post_views (blog_post_id, visitor_hash, viewed_at)
                VALUES (:post_id, :visitor_hash, :viewed_at)
                ON CONFLICT (blog_post_id, visitor_hash) DO NOTHING
                """
            ),
            {"post_id": post.id, "visitor_hash": visitor_hash, "viewed_at": datetime.utcnow()},
        )
        db.session.commit()
        return True
    except Exception:  # tracking must never break the article page
        logger.exception("[blog_analytics] record_view failed for post_id=%r", getattr(post, "id", None))
        try:
            from app.extensions import db

            db.session.rollback()
        except Exception:
            pass
        return False


def views_all_time(post_id):
    from app.extensions import db
    from app.models import BlogPostView

    return db.session.query(db.func.count(BlogPostView.id)).filter(BlogPostView.blog_post_id == post_id).scalar() or 0


def views_since(post_id, since_dt):
    from app.extensions import db
    from app.models import BlogPostView

    return (
        db.session.query(db.func.count(BlogPostView.id))
        .filter(BlogPostView.blog_post_id == post_id, BlogPostView.viewed_at >= since_dt)
        .scalar()
        or 0
    )


def post_stats(post_id):
    """{"all_time", "last_7", "last_30"} for one post — used by the admin edit page."""
    now = datetime.utcnow()
    return {
        "all_time": views_all_time(post_id),
        "last_7": views_since(post_id, now - timedelta(days=7)),
        "last_30": views_since(post_id, now - timedelta(days=30)),
    }


def bulk_view_counts(post_ids):
    """{post_id: all_time_count} for every id in post_ids, in ONE grouped query — used by the
    admin blog list so it never runs N+1 queries for N posts."""
    if not post_ids:
        return {}
    from app.extensions import db
    from app.models import BlogPostView

    rows = (
        db.session.query(BlogPostView.blog_post_id, db.func.count(BlogPostView.id))
        .filter(BlogPostView.blog_post_id.in_(post_ids))
        .group_by(BlogPostView.blog_post_id)
        .all()
    )
    counts = {post_id: count for post_id, count in rows}
    return {pid: counts.get(pid, 0) for pid in post_ids}
