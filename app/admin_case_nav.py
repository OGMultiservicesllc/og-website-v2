"""Centralized Case -> Admin destination resolver (2026-09-25).

Every place in Admin that needs to link TO a case (Customer -> Cases, the generic Cases list, global
search, Dashboard, the Notification Center) should go through `admin_case_url(case)` instead of
hardcoding a URL per case_type — one place decides which service's specialized case-detail screen a
case belongs to, so they can never drift out of sync with each other.

Falls back to the generic Case Overview (`admin.ocase_detail`) for any case type without a dedicated
screen (every immigration case type, `general_service`, and anything added later) — never a 404 just
because a specialized handler doesn't exist yet.
"""
from flask import url_for

#: case_type -> (endpoint, url_for kwarg name for the Case's own id). Every one of these existing routes
#: takes the CASE's id directly (confirmed against app/blueprints/admin/{dl,consent_travel,tax,itin}_routes.py
#: — each resolves it via `db.session.get(Case, case_id)`, not a service-specific row id).
_SPECIALIZED_ROUTES = {
    "nj_driver_license": "admin.dl_case",
    "consent_travel": "admin.ct_case",
    "tax_return": "admin.tax_case",
    "itin_application": "admin.itin_case",
}

#: For these case types, the specialized route ITSELF 404s unless the one-to-one data row exists
#: (`case.dl_data`/`.consent_travel_data`/`.tax_data` are `uselist=False` backrefs — see
#: app/blueprints/admin/{dl,consent_travel,tax}_routes.py's own `_case_or_404`/`_tax_or_404`/`_ct_or_404`).
#: A case of one of these types can exist WITHOUT that row — e.g. an admin picked the type from the
#: generic "+ Create a case" form instead of the customer completing that service's real intake — so the
#: resolver has to check the same condition the route checks, or it would hand out a link that 404s.
#: `itin_application` is deliberately absent: admin.itin_case has no such guard.
_REQUIRES_DATA_ATTR = {
    "nj_driver_license": "dl_data",
    "consent_travel": "consent_travel_data",
    "tax_return": "tax_data",
}


def admin_case_url(case):
    """The correct Admin URL for this case: its service's own specialized case-detail screen when one
    exists AND is actually reachable for this case, otherwise the generic Case Overview. Never raises,
    and never hands back a link that 404s, for any case_type."""
    if case is None:
        return None
    endpoint = _SPECIALIZED_ROUTES.get(case.case_type)
    data_attr = _REQUIRES_DATA_ATTR.get(case.case_type)
    if endpoint and (data_attr is None or getattr(case, data_attr, None) is not None):
        try:
            return url_for(endpoint, case_id=case.id)
        except Exception:  # noqa: BLE001 — a route resolution failure must never break a page that just wants a link
            pass
    try:
        return url_for("admin.ocase_detail", case_id=case.id)
    except Exception:  # noqa: BLE001
        return None
