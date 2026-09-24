"""Backfill for the "Individual & Family Tax Preparation" Service row -- additive, idempotent.

Root cause (staging investigation, 2026-09-24): `app/seed_content.py::seed_service_content()` is a
ONE-TIME, all-or-nothing seeder guarded by `if ServiceCategory.query.count() > 0: return False` -- it
only ever runs against a completely empty database. It can never retroactively add a single service
to a database that has already been seeded once, regardless of what gets added to
`app/service_pages.py` afterward. This is the exact same class of gap `app/driver_license/seed.py`'s
`ensure_service()`/`ensure_category_wiring()` already exists to close for the NJ Driver License
service; this module is the same pattern for Tax.

The Tax Smart Intake itself (`app/tax/` — questions, pricing, case service layer) and its routes
(`app/blueprints/public/tax_routes.py`) were never missing anything; only the marketing/"Get Started"
Service row that `service_public.service_cta()` looks up by slug could be absent on a database whose
`taxes-itin` category was first seeded before "tax-preparation" existed in `SUBPAGES`, or whose first
`ensure_seeded()` run was interrupted before reaching it.

Reuses the SAME bilingual content already authored in `app/service_pages.py` (via
`seed_content._seed_services`) rather than a second, hand-retyped copy -- so there is exactly one
place this marketing copy is written, and no risk of the two drifting apart.
"""

from app.extensions import db
from app.models import Service, ServiceCategory
from app.tax.registry import SERVICE_SLUG

CATEGORY_SLUG = "taxes-itin"


def ensure_service():
    """Create the tax-preparation Service (+ its content items + related-service links) if it is
    missing. A no-op once it exists, whether from the original full seed or a prior run of this
    backfill -- never touches an existing row, so an Admin's own edits are always safe."""
    if Service.query.filter_by(slug=SERVICE_SLUG).first() is not None:
        return False
    cat = ServiceCategory.query.filter_by(slug=CATEGORY_SLUG).first()
    if cat is None:
        return False  # the category itself is missing -- a larger seeding gap, out of scope here

    from app.service_pages import SUBPAGES
    from app.seed_content import _seed_services

    pages = SUBPAGES.get(CATEGORY_SLUG, [])
    page = next((p for p in pages if p["slug"] == SERVICE_SLUG), None)
    if page is None:
        return False  # source content itself isn't in service_pages.py -- nothing to seed from

    _seed_services(cat, [page])
    db.session.flush()

    # _seed_services() only cross-links "related" services present in the SAME call's page list, so a
    # single-page call like this one links neither direction on its own. Fill in both directions using
    # each side's own authored `related` list, matching what a full fresh seed would have produced.
    svc = Service.query.filter_by(slug=SERVICE_SLUG).first()
    by_slug = {p["slug"]: p for p in pages}
    for rel_slug in page.get("related", []):
        rel = Service.query.filter_by(slug=rel_slug).first()
        if rel is not None and rel not in svc.related:
            svc.related.append(rel)
    for other_slug, other_page in by_slug.items():
        if other_slug == SERVICE_SLUG or SERVICE_SLUG not in other_page.get("related", []):
            continue
        other_svc = Service.query.filter_by(slug=other_slug).first()
        if other_svc is not None and svc not in other_svc.related:
            other_svc.related.append(svc)

    db.session.commit()
    return True
