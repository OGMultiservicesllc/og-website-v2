"""Global trailing-slash URL normalization (2026-09-27).

ROOT CAUSE: Flask/Werkzeug's default slash behavior only auto-redirects in ONE direction. Every
route in this app is defined WITHOUT a trailing slash (e.g. `/services/certified-translations`,
`/locations/paterson-nj`) — this is Werkzeug's "strict" rule shape. For a rule shaped like that,
requesting the URL WITH an extra trailing slash (`/locations/paterson-nj/`) does not match the
rule at all and is not auto-redirected by Werkzeug; it simply falls through to a 404. (The
opposite direction — a rule that DOES end in `/`, like this blueprint's own `/<lang>/` home route
— already auto-redirects the no-slash form to the slash form; that's pre-existing Werkzeug
behavior, untouched by this module, and is exactly why `/en` already redirects to `/en/`.)

This module adds the missing direction — trailing-slash to no-slash — as ONE small, generic,
framework-level `before_request` hook, not page-by-page routes, so it covers every current and
future public page automatically and can never drift out of sync with the route table.

Safety-by-construction (see `register_trailing_slash_normalization`):
  1. Only GET/HEAD requests are ever considered — every POST/PUT/PATCH/DELETE request (every form
     submission, Smart Intake autosave, webhook, payment callback, admin action) passes through
     completely untouched, by construction, before anything else in this function even runs.
  2. Only paths that CURRENTLY don't match any route are candidates (a path that already resolves
     is never touched, so nothing that works today can change behavior).
  3. The stripped (no-trailing-slash) candidate is only redirected to if it matches a real,
     already-registered route CLEANLY — i.e. Werkzeug's own matcher returns a normal match, not a
     `RequestRedirect` (which is what happens for `/en` -> `/en/`: matching the stripped candidate
     for `/en/` raises RequestRedirect back to `/en/` itself, which this code explicitly treats as
     "leave it alone" rather than following it — this is what makes the language root's OWN
     trailing slash the correct, un-touched exception, with no hardcoded path list required) and
     not `NotFound` (a genuinely nonexistent page stays exactly as 404 as it is today — requirement
     7). This also means a stripped path that only matches a redirect-only rule can never bounce
     back and forth — see `redirect_url_map_check_avoids_loops` in the test suite.
  4. Restricted to paths under `/<lang>/` (the only prefix `public_bp` and `account_bp` use) AND
     explicitly excluding the small set of session-sensitive / transactional workflow path
     fragments this project already treats as "not ordinary marketing content" for search-engine
     purposes (`app.seo.WORKFLOW_DISALLOW_PATHS` covers the same set for robots.txt) plus
     `/account` (authentication) and `/f/` (the Smart Intake engine, autosave/session-sensitive).
     `/admin`, `/static`, `/media`, `/webhooks`, `/robots.txt`, `/sitemap.xml` never start with
     `/<lang>/` at all, so they are excluded structurally, with no extra code needed.
"""
from flask import redirect, request
from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing import RequestRedirect

#: Path fragments that must never be trailing-slash-redirected even though they live under
#: `/<lang>/...`: authenticated/session-sensitive workflow subsystems, not ordinary public content.
#: Kept as plain substrings (same style as `app.seo.WORKFLOW_DISALLOW_PATHS`) — a page whose slug
#: happens to contain one of these fragments is not a realistic false positive in this codebase.
_EXCLUDED_PATH_FRAGMENTS = (
    "/account",             # My Account / authentication (account_bp) — out of scope per spec
    "/f/",                  # Smart Intake engine — dynamic slug, autosave/session-sensitive
    "/tax/",                # Tax Smart Intake workflow
    "/nj-driver-license/",  # NJ Driver License workflow (case/s/edit/terms/start/doc/send/done/price/practice)
    "/consent-to-travel/",  # Consent to Travel workflow
)


def register_trailing_slash_normalization(app):
    @app.before_request
    def normalize_trailing_slash():
        if request.method not in ("GET", "HEAD"):
            return None
        path = request.path
        if path == "/" or not path.endswith("/"):
            return None
        if not (path.startswith("/en/") or path.startswith("/es/")):
            return None
        if any(fragment in path for fragment in _EXCLUDED_PATH_FRAGMENTS):
            return None

        stripped = path.rstrip("/")
        if not stripped:
            return None

        adapter = app.url_map.bind_to_environ(request.environ)
        try:
            adapter.match(stripped, method=request.method)
        except (NotFound, MethodNotAllowed, RequestRedirect):
            # NotFound: genuinely no such page — stays 404, untouched (requirement 7).
            # RequestRedirect: the stripped path is itself only reachable via ANOTHER redirect
            # (e.g. "/en" -> "/en/", Werkzeug's own built-in slash-adding redirect) — following
            # that would send this request right back to where it started, so leave it alone.
            # MethodNotAllowed: the stripped path exists but not for this method — leave it alone.
            return None

        target = stripped
        if request.query_string:
            target = f"{stripped}?{request.query_string.decode('utf-8')}"
        # 301 (Moved Permanently), matching every other redirect already in this codebase
        # (app/__init__.py's root_redirect, the ITIN blog-slug fix, app/legacy_redirects.py) —
        # a consistent house convention. 308 was considered (it additionally guarantees strict
        # method preservation across all HTTP clients) but is unnecessary here: this hook never
        # fires for anything but GET/HEAD, so there is no method to accidentally rewrite, and
        # matching the codebase's existing single convention is safer than introducing a second one.
        return redirect(target, code=301)
