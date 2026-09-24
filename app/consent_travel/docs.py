"""Consent to Travel document requirements: generated from the guided-intake answers, stored in the existing
Document Vault (`source_key == "consent_travel"`), localized EN/ES. A child's passport/birth certificate, or
an adult's photo ID, already accepted for this same real Person in ANOTHER case is reused instead of asked
for again — OG never asks twice for the same document. Upload Now / Upload Later never blocks Send."""

from datetime import datetime

from app import case_documents as vault
from app.models import DocumentRequirement

SOURCE_KEY = "consent_travel"
CHOICE_LABEL = {"later": ("⏰ I'll upload it later", "⏰ Lo subiré después"), "dont_have": ("🚫 I don't have it yet", "🚫 Todavía no lo tengo")}


def req_text_for(key, lang):
    en = lang != "es"
    parts = key.split(".")  # ct.child.<record_id>.passport|birth_cert  |  ct.adult.<record_id>.id  |  ct.traveler.id
    kind = parts[-1]  # the last segment is always the document kind, regardless of how many segments precede it
    if kind == "passport":
        return ("Passport" if en else "Pasaporte"), None
    if kind == "birth_cert":
        return ("Birth Certificate" if en else "Acta de Nacimiento"), None
    if kind == "id":
        return ("Photo ID (Driver License, State ID or Passport)" if en else "Identificación con foto (Licencia, ID Estatal o Pasaporte)"), None
    return key, None


def req_text(req, lang):
    return req_text_for(req.rule_key, lang)


def choice_kinds(rule_key):
    return ("later", "dont_have")


def is_optional(rule_key, roles=None):
    return False


def desired(ct):
    """[{rule_key, title, person, category, customer_message, doc_basis, reuse}] — every child gets a
    passport + birth certificate requirement; every synced adult record gets a photo-ID requirement."""
    out = []

    def add(key, category, person, title):
        out.append({"rule_key": key, "title": title, "person": person, "category": category, "customer_message": None, "doc_basis": "workflow", "reuse": True})

    for r in ct.children:
        if r.person is None:
            continue
        person = r.person
        given = person.given_name or "Child"
        add(f"ct.child.{r.id}.passport", "child_passport", person, f"{given} — Passport")
        add(f"ct.child.{r.id}.birth_cert", "child_birth_certificate", person, f"{given} — Birth Certificate")
    for r in ct.adult_records:
        if r.person is None:
            continue
        person = r.person
        name = f"{person.given_name or ''} {person.family_name or ''}".strip() or "Adult"
        add(f"ct.adult.{r.id}.id", "adult_photo_id", person, f"{name} — Photo ID")
    # the traveling adult also needs a photo ID (no address) — a single, case-level requirement.
    traveler = _traveler_case_person(ct)
    if traveler is not None:
        add("ct.traveler.id", "adult_photo_id", traveler, f"{traveler.given_name or 'Traveler'} — Photo ID")
    return out


def _traveler_case_person(ct):
    """The traveling adult's CasePerson (document requirements are always scoped to a CasePerson, never a
    bare Person — `_traveler_person` below returns the underlying real Person)."""
    from app.consent_travel import people as ct_people

    person = _traveler_person(ct)
    return ct_people.case_person(ct, person, "other") if person is not None else None


def _traveler_person(ct):
    from app.consent_travel import people as ct_people

    tw = ct.answers.get("traveling_with")
    if tw == "mother":
        return ct_people.owner_for(ct, "mother")
    if tw == "father":
        return ct_people.owner_for(ct, "father_traveler")
    if tw == "other":
        return ct_people.owner_for(ct, "third_traveler")
    return None


def sync(ct):
    from app.extensions import db

    specs = desired(ct)
    vault.sync_requirements(ct.case, SOURCE_KEY, specs)
    for req in DocumentRequirement.query.filter_by(case_id=ct.case_id, source_key=SOURCE_KEY).all():
        if req.withdrawn_at is not None or req.current_document is not None or req.person is None:
            continue
        doc, accepted = vault.find_reusable_document(ct.case, req.person, req.category)
        if doc is not None and accepted:
            vault._attach(req, doc, reason_for_previous="replaced")  # noqa: SLF001
            req.status, req.reused_at = "accepted", req.reused_at or datetime.utcnow()
            continue
        other = vault.find_reusable_elsewhere(ct.case, req.person, req.category)
        if other is not None:
            vault.reuse_across_cases(req, other)
    db.session.commit()


def requirements(ct):
    return [r for r in DocumentRequirement.query.filter_by(case_id=ct.case_id, source_key=SOURCE_KEY).all() if r.withdrawn_at is None]


def missing_required(ct):
    return [r for r in requirements(ct) if r.status in ("needed", "requested", "needs_replacement")]


def counts(ct):
    reqs = requirements(ct)
    have = sum(1 for r in reqs if r.status in ("uploaded", "under_review", "accepted"))
    return have, len(reqs), len([r for r in reqs if r.status in ("needed", "requested", "needs_replacement")])


def cards(ct, lang, record=None, record_kind=None):
    """All vault cards, or (when `record`/`record_kind` given) only that ONE child's or adult's own two/one
    requirements — used to show a child's passport+birth-certificate uploads inline in their own sub-flow."""
    from app.customer_status import requirement_status

    rows = []
    choices = ct.doc_choices
    prefix = f"ct.{record_kind}.{record.id}." if record is not None and record_kind else None
    for r in sorted(requirements(ct), key=lambda x: x.id):
        if prefix is not None and not (r.rule_key or "").startswith(prefix):
            continue
        title, message = req_text(r, lang)
        choice = choices.get(r.rule_key)
        status_text, _tone = requirement_status(r.status, lang)
        rows.append({"req": r, "title": title, "message": message, "status": r.status, "status_text": status_text,
                     "optional": False, "choice": choice, "reused": bool(r.reused_at),
                     "review_message": r.review_message if r.status == "needs_replacement" else None,
                     "can_upload": r.status in vault.CUSTOMER_CAN_UPLOAD, "can_remove": vault.customer_can_remove(r, r.current_document),
                     "doc": r.current_document, "choices": [(k, CHOICE_LABEL[k][0 if lang != "es" else 1]) for k in choice_kinds(r.rule_key)]})
    return rows
