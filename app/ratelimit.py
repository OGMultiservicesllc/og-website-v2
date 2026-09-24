"""Shared, multi-worker-safe rate limiter for sensitive endpoints (sign-in, registration, password
reset, email verification, autosave). Backed by a single small table (`RateLimitHit`,
`app/models/ratelimit.py`) in the SAME database the rest of the app already uses — SQLite in
development, PostgreSQL in production — instead of an in-process dict. This deliberately avoids adding
Redis or any other new piece of infrastructure: a low-traffic transactional-service site like this one
doesn't need it, and a plain DB table gives every Gunicorn worker (and any number of app processes) a
single, consistent view of how many hits a key has recorded, which an in-process store fundamentally
cannot (each worker previously had its own independent counter — see the Production Launch Readiness
Audit, 2026-09-23, finding D1).

Algorithm: a fixed (not sliding) window counter. One row per key, holding the window's start time and a
hit count; a window "rolls over" (resets to count=1) the first time `allow()` is called after
`window_start + window_seconds` has passed. This is a well-known, standard trade-off for a DB-backed
limiter — a client sitting exactly on a window boundary could in the worst case get up to ~2x `limit`
hits across the two adjacent windows, versus a byte-perfect sliding window. For abuse protection on
login/registration/password-reset/verification endpoints (never a precision rate contract), this is the
right trade for staying a single, cheap, portable SQL statement rather than a per-hit log table.

The read-modify-write is done as ONE atomic `INSERT ... ON CONFLICT ... DO UPDATE ... RETURNING`
statement — supported identically by modern SQLite (3.24+, bundled with this project's Python) and by
PostgreSQL — so two Gunicorn workers hitting the same key at the same instant still can't race each
other into both being allowed past the limit; the database's own row-level conflict resolution decides
which write "wins" the increment.

Fail-safe behavior: if the rate-limit table itself can't be written (a transient DB error), `allow()`
FAILS CLOSED — return False — for security-sensitive callers. A broken limiter must never silently turn
into "no limit at all"; a spurious temporary block on a rare DB hiccup is the safer failure mode here.
"""

import logging
import time

from flask import current_app, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("og_ratelimit")


def client_ip():
    return request.remote_addr or "unknown"


_UPSERT_SQL = text(
    """
    INSERT INTO rate_limit_hits (key, window_start, hit_count)
    VALUES (:key, :now, 1)
    ON CONFLICT (key) DO UPDATE SET
        hit_count = CASE WHEN rate_limit_hits.window_start < :threshold THEN 1 ELSE rate_limit_hits.hit_count + 1 END,
        window_start = CASE WHEN rate_limit_hits.window_start < :threshold THEN :now ELSE rate_limit_hits.window_start END
    RETURNING hit_count
    """
)


def allow(key, limit, window_seconds):
    """Record a hit for `key` and return False once more than `limit` hits have occurred inside the
    trailing `window_seconds`-second window. Same signature/semantics as the original in-process
    version: up to exactly `limit` calls within a window return True; the (limit+1)-th onward returns
    False until the window rolls over."""
    from app.extensions import db

    now = time.time()
    threshold = now - window_seconds
    try:
        result = db.session.execute(_UPSERT_SQL, {"key": key, "now": now, "threshold": threshold})
        count = result.scalar()
        db.session.commit()
        return count <= limit
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("[ratelimit] storage failure for key %r — failing closed (denying)", key)
        return False
