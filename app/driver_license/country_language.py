"""Country -> document language, for skipping an otherwise-redundant "what language is this document in?"
question when the answer is genuinely unambiguous (e.g. Dominican Republic -> Spanish) — never to guess.

A country is listed here ONLY when it has exactly one dominant, safely-assumed civil/identity-document language,
and that language is one OG's translation pricing actually supports (English/Spanish/Portuguese/French — see
`app/driver_license/pricing.py SEED`). Anything bilingual, multilingual, disputed, or simply not listed here
falls through to asking the customer directly — see `config.py`'s `_needs_lang_question()`. This table is the
ONE place to extend when OG confirms another country's document language; nothing else should grow a per-country
condition (see `config.py doc_lang_value`/`_needs_lang_question`, the only callers).

Deliberately excluded even though "official" language(s) exist: countries where more than one language is
genuinely in real use on civil documents (Canada, Belgium, Switzerland, India, Philippines, South Africa,
Cameroon, Haiti, most of Francophone Africa, etc.) — for these the customer is always asked.
"""

COUNTRY_DOCUMENT_LANGUAGE = {
    # Spanish — Latin America + Spain (OG's primary customer base)
    "Argentina": "es", "Bolivia": "es", "Chile": "es", "Colombia": "es", "Costa Rica": "es", "Cuba": "es",
    "Dominican Republic": "es", "Ecuador": "es", "El Salvador": "es", "Equatorial Guinea": "es", "Guatemala": "es",
    "Honduras": "es", "Mexico": "es", "Nicaragua": "es", "Panama": "es", "Paraguay": "es", "Peru": "es",
    "Spain": "es", "Uruguay": "es", "Venezuela": "es",
    # Portuguese
    "Brazil": "pt", "Portugal": "pt",
    # French — kept short and unambiguous on purpose; most French-official countries also use other languages
    # on real civil documents and are deliberately left out (customer is asked).
    "France": "fr", "Monaco": "fr",
    # English-official, single-language civil documents (safe to infer "no translation needed")
    "United States": "en", "United Kingdom": "en", "Ireland": "en", "Australia": "en", "New Zealand": "en",
    "Jamaica": "en", "Trinidad and Tobago": "en", "Guyana": "en", "Bahamas": "en", "Barbados": "en",
}


def infer_document_language(country_en):
    """The (en/es/pt/fr) code, or None when this country isn't safely inferable — caller must ask."""
    return COUNTRY_DOCUMENT_LANGUAGE.get((country_en or "").strip()) or None
