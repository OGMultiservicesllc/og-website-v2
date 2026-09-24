"""Backing store for `app.ratelimit.allow()` — a fixed-window counter shared across every Gunicorn
worker (and any number of app processes), since it lives in the same database as everything else rather
than in a single process's memory. See `app/ratelimit.py` for the full explanation."""

from app.extensions import db


class RateLimitHit(db.Model):
    __tablename__ = "rate_limit_hits"

    key = db.Column(db.String(200), primary_key=True)
    window_start = db.Column(db.Float, nullable=False)  # epoch seconds — a plain float, never a native
    # DATETIME/TIMESTAMP column, so there is no dialect-specific date arithmetic anywhere in this table
    # (SQLite and PostgreSQL agree perfectly on float comparison/arithmetic).
    hit_count = db.Column(db.Integer, nullable=False, default=0)
