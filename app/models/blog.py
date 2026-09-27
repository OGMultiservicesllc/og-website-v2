from datetime import datetime

from app.extensions import db

# The fixed set of categories a post can be filed under (Admin picks one, required). Free text was tried
# first and let "Taxes"/"taxes"/"Tax" fragment into different filters — a closed list keeps every post's
# category matching one of the public filter chips.
BLOG_CATEGORIES = ["Taxes", "ITIN", "Immigration", "Notary", "Apostille", "NJ Driver License", "OG Academy", "General"]


class BlogPost(db.Model):
    __tablename__ = "blog_posts"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)

    title_en = db.Column(db.String(200), nullable=False)
    title_es = db.Column(db.String(200), nullable=False)
    excerpt_en = db.Column(db.String(300))
    excerpt_es = db.Column(db.String(300))
    content_en = db.Column(db.Text)
    content_es = db.Column(db.Text)

    cover_image = db.Column(db.String(255))
    category = db.Column(db.String(100))
    author_name = db.Column(db.String(120))

    is_published = db.Column(db.Boolean, nullable=False, default=False)
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    media = db.relationship(
        "BlogMedia", backref="post", order_by="BlogMedia.sort_order", cascade="all, delete-orphan"
    )

    def title(self, lang):
        return self.title_es if lang == "es" and self.title_es else self.title_en

    def excerpt(self, lang):
        return (self.excerpt_es if lang == "es" else self.excerpt_en) or ""

    def content(self, lang):
        return (self.content_es if lang == "es" else self.content_en) or ""


class BlogMedia(db.Model):
    __tablename__ = "blog_media"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"), nullable=False)

    media_type = db.Column(db.String(10), nullable=False)  # 'image' | 'audio' | 'video'
    filename = db.Column(db.String(255))
    external_url = db.Column(db.String(500))
    caption_en = db.Column(db.String(300))
    caption_es = db.Column(db.String(300))
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def caption(self, lang):
        return (self.caption_es if lang == "es" else self.caption_en) or ""


class BlogPostView(db.Model):
    """First-party, admin-only view tracking (2026-09-27) — see app/blog_analytics.py for the
    write path. One row per (post, visitor) PER DAY, never a raw IP or user-agent: `visitor_hash`
    is an HMAC of the request's ip+UA+post+UTC-date, computed and discarded in-process, so the
    24-hour dedup window falls out of the hash itself (tomorrow's hash for the same visitor is a
    different value) rather than a time-range query or a cleanup job. The unique constraint below
    IS the dedup enforcement — a repeat view for the same (post, hash) is a no-op insert, not an
    application-level check-then-write, so it stays race-safe across Gunicorn workers exactly like
    `app/ratelimit.py`'s RateLimitHit."""

    __tablename__ = "blog_post_views"

    id = db.Column(db.Integer, primary_key=True)
    blog_post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"), nullable=False)
    visitor_hash = db.Column(db.String(64), nullable=False)
    viewed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("blog_post_id", "visitor_hash", name="uq_blog_post_view_post_visitor_day"),
        db.Index("ix_blog_post_views_post_viewed_at", "blog_post_id", "viewed_at"),
    )
