"""Centralized legacy Wix -> new site redirect map (2026-09-26).

ONE dict is the whole source of truth: an exact old Wix path (no `/<lang>/` prefix — the old
site's urls were flat) maps to the exact FINAL destination on the new site (already language-
prefixed). `register_legacy_redirects(app)` (called once from `create_app()`) turns every entry
into its own literal Flask url rule — never a wildcard/prefix rule — so a stale or mistyped entry
can only ever affect its own exact old path and can never accidentally intercept a real route;
Flask's own startup rule registration is the safety net against ever colliding with one (a
genuine collision would raise at import time, not silently misroute at runtime).

Every value here is a FINAL destination, never another key of this same map — every redirect is
OLD URL -> FINAL NEW URL in one hop, never a chain through an intermediate alias. Query strings
(UTM/tracking params) are preserved verbatim onto the destination, never interpreted or stripped.

Deliberately NOT implemented (see the task's own HOLD / RETIRED lists, kept alongside this map so
they're never silently forgotten, not scattered across chat history):
  - HOLD_LEGACY_PATHS: real old urls with no equivalent new content yet. Add them here once that
    content exists — never redirect them to Home just to avoid a 404.
  - RETIRED: obsolete Colony Store / product / property pages. No entry, no route — left 404. Not
    listed as data here because per-path enumeration isn't safe (some are prefixes like
    /product-page/*), and this module intentionally never registers a wildcard/catch-all rule.
"""
import re

LEGACY_REDIRECTS = {
    # ---- OG Academy / NJ Notary Public course ----
    "/courses-2/cursonotarionj": "/es/courses/new-jersey-notary-public-certification",
    "/cursonotarionj": "/es/courses/new-jersey-notary-public-certification",
    "/challenge-page/njnotarypublictest": "/es/courses/new-jersey-notary-public-certification",
    "/challenge-page/notarionewjersey": "/es/courses/new-jersey-notary-public-certification",

    "/onlinecourses": "/es/courses",
    "/courses-paterson-nj": "/es/courses",
    "/courses": "/es/courses",
    "/courses-2": "/es/courses",
    "/newjerseynotary2": "/es/courses",
    "/es/newjerseynotary2": "/es/courses",

    # ---- Notary ----
    "/notario-publico": "/es/services/notary",
    "/notary": "/en/services/notary",
    "/notarypublic": "/en/services/notary",
    "/ronnj": "/en/services/notary/remote-online-notarization",

    # ---- Certified Translations ----
    "/certified-translations-paterson-nj": "/es/services/certified-translations",
    "/certifiedtranslations": "/en/services/certified-translations",
    "/birth-certificate-translation-paterson-nj": "/en/services/certified-translations/certified-birth-certificate-translation",
    "/marriage-certificate-translation-paterson-nj": "/en/services/certified-translations/marriage-certificate-translation",
    "/divorce-decree-translation-paterson-nj": "/en/services/certified-translations/divorce-certificate-translation",
    "/academic-transcript-translation-paterson-nj": "/en/services/certified-translations/academic-transcript-translation",

    # ---- Taxes & ITIN ----
    "/itin": "/es/services/taxes-itin/itin-application",
    "/itin-paterson-nj": "/es/services/taxes-itin/itin-application",
    "/itinrequest": "/es/services/taxes-itin/itin-application",
    "/self-employed-tax-preparer-paterson": "/en/services/taxes-itin/gig-economy-tax-preparation",
    "/taxes": "/es/services/taxes-itin/tax-preparation",
    "/taxes1": "/es/services/taxes-itin/tax-preparation",
    "/taxes-paterson-nj": "/es/services/taxes-itin/tax-preparation",
    "/taxes-parterson-nj": "/es/services/taxes-itin/tax-preparation",  # legacy typo, kept verbatim (that's the actual old url)
    "/online-taxes-paterson-nj": "/es/services/taxes-itin/tax-preparation",
    "/copy-3-of-taxes-home": "/es/services/taxes-itin/tax-preparation",
    "/taxform2024": "/es/services/taxes-itin/tax-preparation",
    "/enmiendas-paterson-nj": "/es/services/taxes-itin/tax-amendments",

    # ---- NJ Driver License ----
    "/licencianewjersey": "/es/services/nj-driver-license/nj-driver-license-assistance",
    "/licencianj": "/es/services/nj-driver-license/nj-driver-license-assistance",

    # ---- Immigration ----
    "/immigrationusa": "/es/services/immigration",

    # ---- Apostille ----
    "/apostille": "/en/services/apostille",

    # ---- Document & Office Services ----
    "/printing": "/en/services/document-office-services/document-services",
    "/photo": "/en/services/document-office-services/passport-photo-services",

    # ---- Locations / legacy service hubs ----
    "/services-paterson-nj": "/es/locations/paterson-nj",
    "/tools-and-tips": "/en/resources",

    # ---- Blog ----
    # Individual legacy posts are deliberately NOT mapped here — only migrate one once a real
    # equivalent new article exists (see the task brief); the index is a safe, always-correct target.
    "/blog": "/en/blog",
    "/blog-paterson-nj": "/es/blog",

    # ---- Home aliases ----
    "/home": "/en/",
    "/copy-of-home": "/en/",

    # ---- Privacy ----
    "/privacy-policy": "/en/page/privacy-policy",
    "/og-ai-privacy-policy": "/en/page/privacy-policy",
    "/notaryprivacy": "/en/page/privacy-policy",

    # ---- Terms ----
    "/og-ai-terms": "/en/page/terms-of-service",
    "/notaryterms": "/en/page/terms-of-service",
}

#: Real old urls with NO equivalent new content yet — explicitly left unimplemented per the task
#: brief. Never silently redirected to Home. Kept here (not just in chat history) so a future pass
#: has one place to check before adding real entries above.
HOLD_LEGACY_PATHS = (
    "/oficiantedebodas",
    "/challenge-page/clasenotarioron",
    "/challenge-page/testnotarypa",
    "/translationplan",
    "/network-solutions",
)


def _endpoint_for(old_path):
    slug = re.sub(r"[^a-z0-9]+", "_", old_path.strip("/").lower()).strip("_")
    return f"legacy_redirect__{slug or 'root'}"


def register_legacy_redirects(app):
    """Call once from create_app(). Registers one literal (non-wildcard) url rule per
    LEGACY_REDIRECTS entry, each a plain 301 to its fixed destination with the incoming query
    string (if any) preserved verbatim — never interpreted, never dropped, never chained through
    another entry of this map."""
    from flask import redirect, request

    def _make_view(destination):
        def _view():
            qs = request.query_string.decode()
            target = f"{request.url_root.rstrip('/')}{destination}"
            return redirect(f"{target}?{qs}" if qs else target, code=301)

        return _view

    for old_path, new_path in LEGACY_REDIRECTS.items():
        app.add_url_rule(old_path, endpoint=_endpoint_for(old_path), view_func=_make_view(new_path), strict_slashes=False)
