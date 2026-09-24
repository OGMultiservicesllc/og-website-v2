"""NJ Driver License document requirements: generated from the guided-intake answers, stored in the existing Document Vault
(`source_key == "nj_dl"`), localized EN/ES for the customer. An identity document (passport, birth certificate, Permanent Resident
Card, EAD) already accepted for this same real Person in ANOTHER case (e.g. an immigration case) is reused instead of asked for again —
proof of NJ address is always fresh, never reused. Upload Now / Upload Later never blocks the intake."""

from datetime import datetime

from app import case_documents as vault
from app.driver_license import rules as dl_rules
from app.models import DocumentRequirement

SOURCE_KEY = "nj_dl"
REUSABLE = ("passport", "birth_certificate", "permanent_resident_card", "ead_card")
CATEGORY_FOR = {"passport": "passport", "foreign_license": "foreign_license", "national_id": "national_id", "birth_certificate": "birth_certificate",
                "permanent_resident_card": "proof_of_status", "ead_card": "proof_of_status", "other": "other"}

# Documents with two printed sides OG needs to see (item 9): each side is its own uploadable requirement, grouped
# in the UI under one heading, rather than a single slot that can only hold one image.
TWO_SIDED = ("foreign_license", "national_id")
SIDE_LABEL = {"front": ("Front", "Frente"), "back": ("Back", "Reverso")}
# Birth certificate: up to 3 pages (item 10) — page 1 is the primary slot, pages 2-3 are optional extras.
BC_MAX_PAGES = 3

CHOICE_LABEL = {"later": ("⏰ I'll upload it later", "⏰ Lo subiré después"), "dont_have": ("🚫 I don't have it yet", "🚫 Todavía no lo tengo")}


def _role_map(dl):
    """{doc_key: "needed"|"alternative"} from the customer's CURRENT document selection — recomputed fresh every
    time (never stored), so an earlier answer change is always reflected."""
    from app.driver_license import rules as dl_rules

    selected = (dl.answers or {}).get("documents") or []
    return dl_rules.document_plan(selected)


def doc_role(rule_key, roles):
    """roles = `_role_map(dl)`. -> "needed" | "alternative" | None (not an identity document, e.g. address proof)."""
    if not rule_key.startswith("dl.doc."):
        return None
    return roles.get(rule_key.split(".")[2])


def is_optional(rule_key, roles=None):
    if rule_key == "dl.doc.other":
        return True
    # birth certificate pages 2 and 3 are optional extras, never mandatory (item 10)
    if rule_key.startswith("dl.doc.birth_certificate.p") and not rule_key.endswith(".p1"):
        return True
    # a document `rules.document_plan()` classified "alternative" is not currently required (item 3/8): the
    # customer HAS it and OG can still ask for it, but it never counts toward "documents still needed".
    if roles is not None and doc_role(rule_key, roles) == "alternative":
        return True
    return False


def choice_kinds(rule_key):
    return ("later", "dont_have")


def req_text_for(key, dl, ctx, lang):
    en = lang != "es"
    if key == "dl.address_proof":
        return ("Proof of New Jersey Address" if en else "Comprobante de Dirección de Nueva Jersey",
                "A document that shows your current New Jersey address." if en else "Un documento que muestre tu dirección actual de Nueva Jersey.")
    if key == "dl.itin_evidence":
        return ("ITIN Document" if en else "Documento de ITIN", "The document that shows your ITIN." if en else "El documento que muestra tu ITIN.")
    parts = key.split(".")  # dl.doc.<key> or dl.doc.<key>.<side/page>
    doc_key = parts[2]
    title = dl_rules.document_label(doc_key, lang)
    if len(parts) > 3:
        suffix = parts[3]
        if suffix in SIDE_LABEL:
            side = SIDE_LABEL[suffix][0 if en else 1]
            return f"{title} — {side}", None
        if suffix.startswith("p") and suffix[1:].isdigit():
            n = suffix[1:]
            return (f"{title} — Page {n}" if en else f"{title} — Página {n}"), None
    return title, None


def req_text(req, lang):
    return req_text_for(req.rule_key, None, None, lang)


def desired(dl, ctx):
    """[{rule_key, title, person, category, customer_message, doc_basis, reuse}]. Every selected identity document still
    gets a requirement (so the customer and OG can see it and its status), but which ones split into Front/Back or
    multiple pages depends on `rules.document_plan()`'s role: only a "needed" document is asked for two-sided /
    multi-page — an "alternative" one the customer merely has gets a single plain requirement, never a mandatory-
    looking multi-part one (item 8/9/10)."""
    from app import cases as case_svc
    from app.driver_license import rules as dl_rules

    me = case_svc.ensure_customer_person(dl.case)
    out = []

    def add(key, category, *, reuse=False):
        title, message = req_text_for(key, dl, ctx, "en")
        out.append({"rule_key": key, "title": title, "person": me, "category": category, "customer_message": message, "doc_basis": "workflow", "reuse": reuse})

    selected = ctx.v("documents") or []
    plan = dl_rules.document_plan(selected)
    for d in selected:
        if d in ("other", "unsure"):
            continue
        category = CATEGORY_FOR.get(d, "other")
        needed = plan.get(d) == "needed"
        if needed and d in TWO_SIDED:
            add(f"dl.doc.{d}.front", category, reuse=d in REUSABLE)
            add(f"dl.doc.{d}.back", category, reuse=d in REUSABLE)
        elif needed and d == "birth_certificate":
            for n in range(1, BC_MAX_PAGES + 1):
                add(f"dl.doc.{d}.p{n}", category, reuse=(n == 1 and d in REUSABLE))
        else:
            add(f"dl.doc.{d}", category, reuse=d in REUSABLE)
    if ctx.v("ssn_itin_path") == "itin":
        add("dl.itin_evidence", "ssn_itin_document")
    if ctx.v("address_doc"):
        add("dl.address_proof", "nj_address_proof")
    return out


def sync(dl, ctx=None):
    """Create/withdraw exactly the requirements the answers ask for; attach a reusable identity document already accepted
    elsewhere for this same real person (within the case, or another case of the same customer)."""
    from app.extensions import db
    from app.driver_license import service

    ctx = ctx or service.ctx(dl, "en")
    specs = desired(dl, ctx)
    vault.sync_requirements(dl.case, SOURCE_KEY, specs)
    for req in DocumentRequirement.query.filter_by(case_id=dl.case_id, source_key=SOURCE_KEY).all():
        if req.withdrawn_at is not None or req.current_document is not None or req.person is None:
            continue
        # `req.category` (set from CATEGORY_FOR when the requirement was created) identifies the underlying document
        # even for a front/back or multi-page sub-requirement, where the rule_key's last segment is a side/page, not
        # the document key (e.g. "dl.doc.birth_certificate.p1" must not be parsed as document key "p1").
        if req.category not in ("passport", "birth_certificate", "proof_of_status"):
            continue
        doc, accepted = vault.find_reusable_document(dl.case, req.person, req.category)
        if doc is not None and accepted:
            vault._attach(req, doc, reason_for_previous="replaced")  # noqa: SLF001
            req.status, req.reused_at = "accepted", req.reused_at or datetime.utcnow()
            continue
        other = vault.find_reusable_elsewhere(dl.case, req.person, req.category)
        if other is not None:
            vault.reuse_across_cases(req, other)
    db.session.commit()


def requirements(dl):
    return [r for r in DocumentRequirement.query.filter_by(case_id=dl.case_id, source_key=SOURCE_KEY).all() if r.withdrawn_at is None]


def missing_required(dl):
    roles = _role_map(dl)
    return [r for r in requirements(dl) if not is_optional(r.rule_key, roles) and r.status in ("needed", "requested", "needs_replacement")]


def counts(dl):
    reqs = requirements(dl)
    roles = _role_map(dl)
    have = sum(1 for r in reqs if r.status in ("uploaded", "under_review", "accepted"))
    return have, len(reqs), len([r for r in reqs if not is_optional(r.rule_key, roles) and r.status in ("needed", "requested", "needs_replacement")])


ALT_LABEL = ("Alternative — not currently needed", "Alternativa — no se necesita por el momento")


def cards(dl, lang):
    from app.customer_status import requirement_status

    rows = []
    choices = dl.doc_choices
    roles = _role_map(dl)
    for r in sorted(requirements(dl), key=lambda x: x.id):
        title, message = req_text(r, lang)
        choice = choices.get(r.rule_key)
        role = doc_role(r.rule_key, roles)
        is_alt = role == "alternative" and r.status == "needed"
        status_text, _tone = (ALT_LABEL[0 if lang != "es" else 1], "neutral") if is_alt else requirement_status(r.status, lang)
        rows.append({"req": r, "title": title, "message": message, "status": r.status, "status_text": status_text, "role": role,
                     "optional": is_optional(r.rule_key, roles), "choice": choice, "reused": bool(r.reused_at),
                     "review_message": r.review_message if r.status == "needs_replacement" else None,
                     "can_upload": r.status in vault.CUSTOMER_CAN_UPLOAD, "can_remove": vault.customer_can_remove(r, r.current_document),
                     "doc": r.current_document, "choices": [(k, CHOICE_LABEL[k][0 if lang != "es" else 1]) for k in choice_kinds(r.rule_key)]})
    return rows
