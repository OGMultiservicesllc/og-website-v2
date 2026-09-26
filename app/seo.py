"""Explicit, per-request `<meta name="robots">` control for public_bp pages that must never be
indexed although they don't live under the `account` blueprint (which already gets an
unconditional `noindex, nofollow` from base.html) and aren't covered by the site-wide
`SiteSettings.block_search_indexing` staging toggle.

Three ways a page ends up noindexed, in the order base.html checks them:
  1. `SiteSettings.block_search_indexing` (staging-wide kill switch) -> noindex, nofollow.
  2. `request.blueprint == 'account'` -> noindex, nofollow.
  3. `g.robots_directive`, set by one of the helpers below -> whatever directive was set.
Otherwise no robots meta tag is emitted at all (the page is indexable).

`g` is per-request, so nothing here needs resetting between requests.
"""
from functools import wraps

from flask import g


def mark_noindex(follow=False):
    """Call directly from inside a view when the decorators below don't fit (e.g. the
    decision depends on something already computed in the view body)."""
    g.robots_directive = "noindex, follow" if follow else "noindex, nofollow"


def noindex_page(view_func=None, *, follow=False):
    """Unconditionally noindex this view's page — for pages that are always a workflow or
    utility page, never marketing content, regardless of auth state (e.g. the Tax/NJ Driver
    License/Consent to Travel "terms" pages, which render without requiring login but aren't
    meant to compete with the service landing pages for search traffic).

    `follow=True` emits "noindex, follow" instead of "noindex, nofollow" — for a page whose
    OUTGOING links should still be crawled (e.g. a functional form that links back to the
    service page it belongs to), as opposed to a workflow page with no links worth following.
    """

    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            mark_noindex(follow=follow)
            return func(*args, **kwargs)

        return wrapped

    return decorator(view_func) if view_func is not None else decorator


def noindex_if_service_intake(view_func):
    """For every `/f/<slug>*` route: the SAME url pattern serves both the authenticated Smart
    Intake (`Form.form_type == "service_intake"`, gated by `_intake_submission()`'s own login
    check) and public, no-account "inquiry" forms — only the former should ever be noindexed.
    Looks the form up by the view's own `slug` kwarg, so adding this one decorator is the whole
    job; no per-route business logic to duplicate or forget to update later."""

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        slug = kwargs.get("slug")
        if slug:
            from app.models import Form

            form = Form.query.filter_by(slug=slug, status="published").first()
            if form is not None and form.is_service_intake:
                mark_noindex()
        return view_func(*args, **kwargs)

    return wrapped


def current_robots_directive():
    """Read back what (if anything) this request has set. Used by base.html via inject_globals."""
    return getattr(g, "robots_directive", None)


#: robots.txt Disallow patterns (Google-style `*` wildcards) for authenticated workflow paths,
#: reused verbatim by `robots_txt()` in app/__init__.py so the meta-tag protection above and the
#: crawl-level protection here can never drift out of sync. Every entry was checked by hand
#: against the FULL live sitemap to confirm it cannot also match a real public service/location/
#: blog/course page (see docs/ SEO hygiene notes) — do not widen one of these to a bare
#: "/*/nj-driver-license/" or similar without re-checking that, since the marketing subpage
#: `/services/nj-driver-license/nj-driver-license-assistance` literally contains the substring
#: "nj-driver-license/" and a naive broad rule WOULD wrongly disallow it too.
#:
#: `/*/f/` is deliberately NOT included: that url pattern serves both the authenticated Smart
#: Intake AND public, no-login "inquiry" forms (Form.form_type) at the SAME url — a blanket
#: crawl block would also block a legitimate future public inquiry form. The per-page
#: `noindex_if_service_intake` meta tag above is the correct, precise protection for that one,
#: since only that can be conditional on the actual Form record.
WORKFLOW_DISALLOW_PATHS = (
    "/*/tax/",
    "/*/nj-driver-license/case",
    "/*/nj-driver-license/s/",
    "/*/nj-driver-license/edit",
    "/*/nj-driver-license/terms",
    "/*/nj-driver-license/start",
    "/*/nj-driver-license/doc/",
    "/*/nj-driver-license/send",
    "/*/nj-driver-license/done",
    "/*/nj-driver-license/price/",
    "/*/nj-driver-license/practice/",  # trailing slash: protects modes/start/q/results/review, NOT the bare public /practice explainer
    "/*/consent-to-travel/",
    "/*/services/*/*/start",  # the service "Get Started" resolver — never renders a page, only redirects
)
