"""Per-subpage service-area scope — replaces the old behavior where every one
of the 28 service subpages listed the same 19 cities regardless of what the
page actually was. This is a business/legal question, not marketing copy, so
it's kept in its own small file instead of buried inside service_pages.py's
~1700 lines of content.

Each subpage gets THREE independent yes/no facts:
    nj_in_person       — a client can be served in person at the Paterson,
                          NJ storefront for this service.
    tx_in_person       — a client can be served in person / by appointment
                          in the Spring, TX area for this service. This is
                          ONLY true where the client explicitly confirmed it
                          (2026-09-08) — never assumed from "well, it's the
                          same company."
    remote_nationwide  — this service can genuinely be completed without
                          either party being physically present (documents
                          exchanged by photo/mail/email), so it's offered to
                          anyone regardless of location.

A page can be any combination of the three (e.g. general tax prep is all
three; a passport photo is only nj_in_person + tx_in_person, since a photo
cannot be taken remotely).

CONFIRMED WITH THE CLIENT (2026-09-08, reconfirmed per-subpage 2026-09-08):
Taxes (Individual & Family, Small Business, Gig Economy, Amended Returns —
each confirmed individually, not just "Taxes" as a category), ITIN,
Certified Translations (all 8 document types, each confirmed — remote/
nationwide is legitimate for translations since a document photo/scan can
be reviewed from anywhere, but Paterson and Spring remain called out as
the two real local bases rather than diluting that with a raw city list),
Notary (in-person types only — see the Remote Online Notarization note
below), and Passport/ID Photos all have a real by-appointment option in
the Spring, TX area today. Nothing else does yet.

One item remains explicitly UNCONFIRMED — see NEEDS_CONFIRMATION at the
bottom:
  - Remote Online Notarization is left WITHOUT Texas in-person or remote-
    nationwide scope, because notarizing for a Texas-based signer may
    require a separate Texas RON commission/registration — a legal
    question this file does not attempt to answer. Do not add TX or
    nationwide scope here without the client naming the specific states
    this notary is commissioned/registered for RON.
"""

DEFAULT_SCOPE = {
    "nj_in_person": True,
    "tx_in_person": False,
    "remote_nationwide": False,
    "note": None,
}

_loc = lambda en, es: {"en": en, "es": es}  # noqa: E731 — tiny, matches service_pages.py's own helper

# (category, slug) -> overrides merged onto DEFAULT_SCOPE.
# A ("category", "*") entry applies to every slug in that category unless a
# more specific ("category", "slug") entry overrides it.
SCOPE_OVERRIDES = {
    # ---- Certified Translations: confirmed in-person/mobile in TX, and the
    # existing site already claims nationwide remote/mail-in service.
    ("certified-translations", "*"): {"remote_nationwide": True, "tx_in_person": True},

    # ---- Taxes & ITIN: "Taxes" and "ITIN" both explicitly confirmed for TX.
    ("taxes-itin", "*"): {"remote_nationwide": True, "tx_in_person": True},
    ("taxes-itin", "itin-application"): {
        "tx_in_person": True,
        # ITIN's whole value is in-person verification of original documents
        # by a Certified Acceptance Agent — that can't happen "remotely" the
        # way a mailed tax return can.
        "remote_nationwide": False,
        "note": _loc(
            "In-person original-document verification is the core of this service — available at our Paterson, NJ office or by appointment in the Spring, TX area. If you're elsewhere, the standard IRS mail-in process still applies; ask us for guidance.",
            "La verificación en persona de documentos originales es el núcleo de este servicio — disponible en nuestra oficina de Paterson, NJ o con cita en el área de Spring, TX. Si estás en otro lugar, aplica el proceso estándar de envío por correo al IRS; pregúntanos para orientarte.",
        ),
    },

    # ---- Immigration: document preparation doesn't require physical
    # presence, so it's already offered nationwide remotely — but no
    # in-person/mobile option in TX was confirmed.
    ("immigration", "*"): {"remote_nationwide": True},

    # ---- Notary: in-person notarization and travel-consent letters were
    # confirmed for TX. Remote Online Notarization is a distinct legal
    # question — see NEEDS_CONFIRMATION.
    ("notary", "notarization"): {"tx_in_person": True},
    ("notary", "minor-travel-consent"): {"tx_in_person": True},
    ("notary", "remote-online-notarization"): {
        "note": _loc(
            "Availability for out-of-state signers depends on which states this notary is currently commissioned/registered for online notarization — confirm your state when you reach out.",
            "La disponibilidad para firmantes fuera del estado depende de en qué estados este notario está actualmente comisionado/registrado para notarización en línea — confirma tu estado al contactarnos.",
        ),
    },

    # ---- Apostille: scoped to the document's issuing government, not the
    # client's home state — a client anywhere can mail in an eligible
    # document, so this is nationwide-remote rather than TX-in-person.
    ("apostille", "nj-state-document-apostille"): {
        "remote_nationwide": True,
        "note": _loc(
            "For documents issued by the State of New Jersey — available by mail from anywhere, not limited to New Jersey or Texas residents.",
            "Para documentos emitidos por el Estado de Nueva Jersey — disponible por correo desde cualquier lugar, no limitado a residentes de Nueva Jersey o Texas.",
        ),
    },
    ("apostille", "federal-document-apostille"): {"remote_nationwide": True},

    # ---- Document & Office Services: photos were confirmed for TX; copies/
    # fax/scan need equipment on site (Paterson only); the forms/benefits
    # service covers NJ-specific programs (Medicaid NJ, SNAP, NJ ANCHOR) by
    # definition, so Texas doesn't apply regardless of availability.
    ("document-office-services", "passport-photo-services"): {"tx_in_person": True},
    ("document-office-services", "forms-applications-assistance"): {
        "note": _loc(
            "Covers New Jersey–specific programs (Medicaid, SNAP, NJ ANCHOR) — not available to Texas residents by the nature of these programs, regardless of location.",
            "Cubre programas específicos de Nueva Jersey (Medicaid, SNAP, NJ ANCHOR) — no disponible para residentes de Texas por la naturaleza de estos programas, sin importar la ubicación.",
        ),
    },
}

# Scoping decisions that remain genuinely unconfirmed — everything else in
# SCOPE_OVERRIDES has been explicitly confirmed by the client per subpage.
NEEDS_CONFIRMATION = [
    "remote-online-notarization: left without Texas scope pending confirmation of which "
    "states this notary is currently commissioned/registered for RON.",
]


def get_scope(category, slug):
    scope = dict(DEFAULT_SCOPE)
    scope.update(SCOPE_OVERRIDES.get((category, "*"), {}))
    scope.update(SCOPE_OVERRIDES.get((category, slug), {}))
    return scope


def tx_available_pages():
    """(category, slug) pairs where the Spring, TX page can honestly link
    to a service — tx_in_person OR remote_nationwide (a TX client can use
    either), used by the Spring location page's service list."""
    from app.service_pages import SUBPAGES

    result = []
    for category, pages in SUBPAGES.items():
        for page in pages:
            scope = get_scope(category, page["slug"])
            if scope["tx_in_person"] or scope["remote_nationwide"]:
                result.append((category, page["slug"]))
    return result


def nj_available_pages():
    """(category, slug) pairs available at the Paterson, NJ office —
    effectively all of them, used by the Paterson location page's list."""
    from app.service_pages import SUBPAGES

    result = []
    for category, pages in SUBPAGES.items():
        for page in pages:
            scope = get_scope(category, page["slug"])
            if scope["nj_in_person"]:
                result.append((category, page["slug"]))
    return result
