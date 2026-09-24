"""Language-neutral business facts. Real data — do not use placeholders here.

OG Multiservices LLC operates from two locations, which are NOT the same
kind of thing and must never be presented as if they were:

- Paterson, NJ — a real physical storefront office. Its street address is
  public and safe to render anywhere (HTML, JSON-LD, sitemap, maps).
- Spring, TX — a real, active base of operations, but run from a private
  residence. Confirmed by the client (2026-09-08): the SAME phone/WhatsApp
  number and the SAME business hours as Paterson apply here too — those are
  not invented, they're the one shared company-wide contact channel. What
  must NEVER be derived, guessed, or added later for Spring: a street
  address, a ZIP code, or GPS coordinates. `LOCATIONS["spring-tx"]` has no
  address fields at all (not blank strings — the keys don't exist), so
  there's nothing for a template to accidentally render. If a real TX
  business address is ever obtained, it must be added explicitly and
  reviewed before anything renders it publicly — never inferred from this
  file's shape.
"""

BUSINESS_NAME = "OG Multiservices LLC"
FOUNDER_NAME = "Marcos Ogando"
FOUNDING_YEAR = 2019

# Shared company-wide contact channels — the same for both locations
# (confirmed by the client, not assumed).
PHONE_DISPLAY = "201-685-5444"
PHONE_TEL = "+12016855444"
WHATSAPP_DISPLAY = "862-332-2321"
WHATSAPP_LINK = "https://wa.me/18623322321"
EMAIL = "info@ogmultiservicesllc.com"
# Defaults OG uses when it acts as the interpreter on a customer's Form I-90 (Part 6).
# The intake pre-fills these as EDITABLE defaults (via "@biz:NAME" field defaults), so
# changing OG's details here updates every new intake without touching code.
INTERPRETER_LAST_NAME = "Ogando"
INTERPRETER_FIRST_NAME = "Marcos"
INTERPRETER_ORG = BUSINESS_NAME
INTERPRETER_PHONE = PHONE_DISPLAY
INTERPRETER_EMAIL = EMAIL
# Defaults OG uses when it is the PREPARER of a customer's form (e.g. Form I-864 Part 10, Items 1-5). Today they are the same
# person/office as the interpreter defaults; separate names so they can be changed independently ("@biz:PREPARER_*" defaults).
PREPARER_LAST_NAME = INTERPRETER_LAST_NAME
PREPARER_FIRST_NAME = INTERPRETER_FIRST_NAME
PREPARER_ORG = BUSINESS_NAME
PREPARER_PHONE = PHONE_DISPLAY
PREPARER_MOBILE = ""
PREPARER_FAX = ""  # Form I-751 Part 10 Item 5 (Preparer's Fax Number); empty unless OG configures one
PREPARER_EMAIL = EMAIL
# What the configured preparer IS, for forms whose preparer statement distinguishes it (Form I-765 Part 5 Item 7): "not_attorney" (a preparer who
# is neither an attorney nor an accredited representative), "attorney" or "accredited". OG Multiservices is not a law firm: this is never
# defaulted to attorney/accredited status. If it were changed, PREPARER_REPRESENTATION_EXTENDS says whether the representation goes beyond
# preparation ("extends" / "does_not_extend").
PREPARER_STATUS = "not_attorney"
PREPARER_REPRESENTATION_EXTENDS = ""
# Public Paterson office, structured for address forms (never a residential address).
OFFICE_STREET = "145 Presidential Blvd"
OFFICE_UNIT_TYPE = "ste"
OFFICE_UNIT_NUMBER = "2"
OFFICE_CITY = "Paterson"
OFFICE_STATE = "NJ"
OFFICE_ZIP = "07522"
# Certifying Acceptance Agent details used on the W-7 preparation view (Acceptance Agent's Use ONLY). The IRS-issued identifiers are NOT invented here: empty means
# "staff enters it from OG's own IRS records".
CAA_COMPANY = BUSINESS_NAME
CAA_PHONE = PHONE_DISPLAY
CAA_FAX = ""
CAA_EIN = ""
CAA_PTIN = ""
CAA_OFFICE_CODE = ""

# Alternate checkout payment methods (2026-09-23). Public information shown to customers choosing how to
# pay — never a secret. The Cash App tag additionally has a SiteSettings override (`SiteSettings.cash_app_tag`)
# so it can be changed later without a code deploy; this constant is only the fallback default.
ZELLE_PHONE = WHATSAPP_DISPLAY  # 862-332-2321 — the same shared number, confirmed by the client for Zelle too
ZELLE_RECIPIENT = BUSINESS_NAME
CASH_APP_TAG_DEFAULT = "$ogmultiservicesllc"
CASH_APP_RECIPIENT = BUSINESS_NAME

HOURS_DISPLAY = "Mon–Fri 9:00 AM – 5:00 PM"
HOURS_CLOSED_DISPLAY = "Sat–Sun Closed"

# Back-compat: several templates (footer, contact page, the old sitewide
# JSON-LD) already reference these directly as "the" business address.
# They keep working unchanged — they just mean "Paterson" now that a second
# location exists.
ADDRESS_LINE1 = "145 Presidential Blvd, STE 2"
ADDRESS_LINE2 = "Paterson, NJ 07522, United States"

# Nearby cities used for local-SEO copy. Kept as their own constants (rather
# than only inside LOCATIONS) since several places already reference these
# names directly.
NJ_SERVICE_CITIES = [
    "Paterson", "Clifton", "Passaic", "Elizabeth", "Newark", "Paramus",
    "Wayne", "Hackensack", "Garfield", "Totowa", "Lodi", "Fair Lawn",
]
TX_SERVICE_CITIES = [
    "Spring", "Houston", "The Woodlands", "Conroe", "Tomball", "Cypress", "Klein",
]

LOCATIONS = {
    "paterson-nj": {
        "type": "storefront",  # a real public office — clients can walk in
        "public_address": True,
        "city": "Paterson",
        "state": "NJ",
        "address_line1": ADDRESS_LINE1,
        "address_line2": ADDRESS_LINE2,
        "postal_code": "07522",
        "phone_display": PHONE_DISPLAY,
        "phone_tel": PHONE_TEL,
        "whatsapp_link": WHATSAPP_LINK,
        "hours_display": HOURS_DISPLAY,
        "hours_closed_display": HOURS_CLOSED_DISPLAY,
        "service_cities": NJ_SERVICE_CITIES,
    },
    "spring-tx": {
        "type": "service_area",  # a real base of operations run from a
        "public_address": False,  # private residence — no address is ever
        "city": "Spring",          # stored here for a template to render.
        "state": "TX",
        # No address_line1 / address_line2 / postal_code keys on purpose —
        # see the module docstring. Do not add them without explicit,
        # separate confirmation from the client.
        "phone_display": PHONE_DISPLAY,
        "phone_tel": PHONE_TEL,
        "whatsapp_link": WHATSAPP_LINK,
        "hours_display": HOURS_DISPLAY,
        "hours_closed_display": HOURS_CLOSED_DISPLAY,
        "service_cities": TX_SERVICE_CITIES,
    },
}
