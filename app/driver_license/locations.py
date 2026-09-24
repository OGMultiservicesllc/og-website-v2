"""MVC agency location list offered to the customer as 1st/2nd/3rd appointment-assistance choice. Admin-managed
(Admin -> NJ Driver License -> Locations); never scraped or hard-coded into a template. Seed list only for first run."""

from app.extensions import db
from app.models import MvcLocation

SEED = ["Paterson", "Wayne", "Lodi", "Newark", "North Bergen", "Oakland", "Rahway", "Randolph", "Bayonne", "Elizabeth", "Edison", "Flemington"]


def _slug(name):
    return name.lower().replace(" ", "-")


def ensure_seed():
    have = {r.slug for r in MvcLocation.query.all()}
    added = 0
    for i, name in enumerate(SEED):
        slug = _slug(name)
        if slug not in have:
            db.session.add(MvcLocation(name=name, slug=slug, sort_order=i))
            added += 1
    if added:
        db.session.commit()
    return added
