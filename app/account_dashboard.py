"""My Account redesign: the presentation/aggregation layer behind Home, Services, Documents and Messages.

This module invents NO new state. It reads the existing Case / FormSubmission / Document Vault / Tax /
ITIN architecture and normalizes it into the small set of shapes the customer-facing templates need
(a status word, a tone, a "what do I do next" link). Every aggregation step is defensive: one broken
case must never break the whole page (see `_safe`), matching the rest of this codebase's "logging must
never break a customer's page" convention (compare `app/activity.py log_event`).
"""

import logging

from app import case_documents as vault
from app import customer_status
from app.case_types import domain_of, type_title
from app.intake_engine import status_key
from app.models import Case, FormSubmission, ServiceCategory, SubmissionNote

logger = logging.getLogger(__name__)


def _portal_helpers():
    """Lazy import: `app.blueprints.account.portal_routes` imports this module back (to call `home_data` etc.),
    so the reverse import must happen at call time, not at module load, to avoid a circular import."""
    from app.blueprints.account.portal_routes import application_cards_single, card_title, document_rows

    return application_cards_single, card_title, document_rows

DOMAIN_TAX = "tax_itin"
DOMAIN_IMMIGRATION = "immigration"


def _safe(fn, *args, default=None, **kw):
    """Run one aggregation step; on any unexpected error, log it and degrade to `default` instead of a 500."""
    try:
        return fn(*args, **kw)
    except Exception:
        logger.exception("account_dashboard: %s failed", getattr(fn, "__name__", fn))
        return default


# ------------------------------------------------------------------ header / avatar
def avatar(student, lang):
    from flask import url_for

    return {"photo_url": url_for("account.photo", lang=lang, v=student.photo_filename[-8:]) if student.photo_filename else None, "initials": student.initials}


# ------------------------------------------------------------------ one application (FormSubmission), normalized
def _app_entry(sub, lang):
    application_cards_single, card_title, _ = _portal_helpers()
    label, tone = customer_status.application_status(status_key(sub), lang)
    card = application_cards_single(sub, lang)
    view_url = _url("account.application_detail", lang=lang, submission_id=sub.id)
    return {"kind": "application", "sub": sub, "title": card_title(sub, lang), "label": label, "tone": tone,
            "percent": card["percent"], "continue_url": card["continue_url"], "view_url": view_url,
            "docs_total": 0, "docs_missing": 0, "extra_count": 0,
            "is_action": status_key(sub) in ("draft", "reopened", "waiting_client"), "updated_at": sub.updated_at or sub.submitted_at}


def _url(endpoint, **kw):
    from flask import url_for

    return url_for(endpoint, **kw)


# ------------------------------------------------------------------ one case, normalized (generic — works for any case type)
def _primary_application(case):
    """The application within a case most worth showing on a compact card: an unfinished one first (it needs
    action or progress to show), otherwise the most recently touched one."""
    apps = case.applications
    if not apps:
        return None
    incomplete = [s for s in apps if not s.is_complete]
    if incomplete:
        return sorted(incomplete, key=lambda s: s.updated_at or s.id, reverse=True)[0]
    return sorted(apps, key=lambda s: s.updated_at or s.submitted_at or s.id, reverse=True)[0]


def case_entry(case, lang):
    """Generic normalized card for ANY case type (used by both the Immigration section and Services).
    Tax and ITIN cases get their own richer normalizer (`_tax_entry`/`_itin_entry`) and are never passed here."""
    application_cards_single, card_title, _ = _portal_helpers()
    primary = _primary_application(case)
    open_actions = vault.open_customer_actions(case)
    docs_have, docs_total, docs_missing = 0, 0, 0
    for r in vault.visible_requirements(case):
        docs_total += 1
        if r.status in ("uploaded", "under_review", "accepted"):
            docs_have += 1
        if r in open_actions:
            docs_missing += 1
    if primary is not None:
        label, tone = customer_status.application_status(status_key(primary), lang)
        card = application_cards_single(primary, lang)
        percent = card["percent"] if not primary.is_complete else None
        continue_url = card["continue_url"]
        title = card_title(primary, lang)
        is_action = status_key(primary) in ("draft", "reopened", "waiting_client")
    else:
        label, tone = customer_status.case_status(case.status, lang)
        percent, continue_url, is_action = None, None, False
        title = type_title(case.case_type, lang)
    if docs_missing and not is_action:
        is_action, tone = True, "action"
    extra_count = max(0, len(case.applications) - 1)
    return {"kind": "case", "case": case, "domain": domain_of(case.case_type, lang), "type_title": type_title(case.case_type, lang), "title": title,
            "label": label, "tone": tone, "percent": percent, "docs_have": docs_have, "docs_total": docs_total, "docs_missing": docs_missing,
            "extra_count": extra_count, "continue_url": continue_url, "view_url": _url("account.my_case_detail", lang=lang, case_id=case.id),
            "is_action": is_action, "updated_at": case.updated_at}


def _tax_entry(case, lang):
    from app.tax import portal as tax_portal

    d = tax_portal.dashboard(case, lang)
    if d is None:
        return None
    is_action = d["editable"] or bool(d["actions"]) or d["docs_missing"] > 0
    label, tone = customer_status.tax_status(d["tax"].status, lang)
    if is_action and tone not in ("action", "problem"):
        tone = "action"
    subtitle = ("Individual Tax Return" if lang != "es" else "Declaración de Impuestos Individual") + f" — {d['year']}"
    return {"kind": "tax", "case": case, "domain": domain_of(case.case_type, lang), "type_title": subtitle, "title": subtitle,
            "label": label, "tone": tone, "percent": d["percent"] if d["editable"] else None, "docs_have": d["docs_have"], "docs_total": d["docs_total"],
            "docs_missing": d["docs_missing"], "price": d["price"], "extra_count": 0,
            "continue_url": _url(d["continue_url"][0], **d["continue_url"][1]) if d["editable"] else None,
            "view_url": _url("account.my_case_detail", lang=lang, case_id=case.id), "is_action": is_action, "updated_at": case.updated_at}


def _itin_entry(case, lang):
    from app import itin

    d = itin.dashboard(case, lang)
    apps = d.get("applicants") or []
    unfinished = [a for a in apps if not a["started"] or (not a["submission"].is_complete)]
    label, tone = customer_status.itin_status(d["stage"], lang)
    docs_missing = max(0, d["docs_total"] - d["docs_got"])
    is_action = docs_missing > 0 or bool(unfinished) or bool(d.get("originals"))
    if is_action and tone == "processing":
        tone = "action"
    subtitle = ("ITIN Application" if lang != "es" else "Solicitud de ITIN") + (f" — {len(apps)} {'people' if lang != 'es' else 'personas'}" if len(apps) > 1 else "")
    continue_url = None
    if unfinished:
        s = unfinished[0]["submission"]
        continue_url = _url("public.og_form_view", lang=lang, slug=s.form.slug, page=s.current_page, t=s.resume_token) if not s.is_complete else None
    return {"kind": "itin", "case": case, "domain": domain_of(case.case_type, lang), "type_title": subtitle, "title": subtitle,
            "label": label, "tone": tone, "percent": None, "docs_have": d["docs_got"], "docs_total": d["docs_total"], "docs_missing": docs_missing,
            "extra_count": 0, "continue_url": continue_url, "view_url": _url("account.my_case_detail", lang=lang, case_id=case.id),
            "is_action": is_action, "updated_at": case.updated_at}


def _ct_entry(case, lang):
    from app.consent_travel import docs as ct_docs
    from app.consent_travel import service as ct_service

    ct = case.consent_travel_data
    if ct is None:
        return None
    editable = ct.status in ct_service.EDITABLE
    have, total, missing = _safe(ct_docs.counts, ct, default=(0, 0, 0))
    label, tone = customer_status.case_status(case.status, lang)
    is_action = editable or missing > 0 or ct.status == "waiting_client"
    if is_action and tone not in ("action",):
        tone = "action"
    title = "Consent to Travel Authorization" if lang != "es" else "Autorización de Viaje para Menores"
    continue_url = None
    if editable:
        key = ct.current_step if ct_service.step_by_key(ct_service.ctx(ct, lang), ct.current_step or "") else "intro"
        continue_url = _url("public.ct_step", lang=lang, case_id=case.id, step_key=key)
    return {"kind": "ct", "case": case, "domain": domain_of(case.case_type, lang), "type_title": title, "title": title,
            "label": label, "tone": tone, "percent": None, "docs_have": have, "docs_total": total, "docs_missing": missing, "extra_count": 0,
            "continue_url": continue_url, "view_url": _url("account.my_case_detail", lang=lang, case_id=case.id), "is_action": is_action, "updated_at": case.updated_at}


def _dl_entry(case, lang):
    from app.driver_license import portal as dl_portal

    d = dl_portal.dashboard(case, lang)
    if d is None:
        return None
    is_action = d["editable"] or bool(d["actions"]) or d["docs_missing"] > 0
    tone = "action" if is_action else d["status_tone"]
    return {"kind": "dl", "case": case, "domain": domain_of(case.case_type, lang), "type_title": "NJ Driver License" if lang != "es" else "Licencia de Conducir de NJ",
            "title": "NJ Driver License" if lang != "es" else "Licencia de Conducir de NJ", "label": d["milestone_label"], "tone": tone,
            "percent": None, "docs_have": d["docs_have"], "docs_total": d["docs_total"], "docs_missing": d["docs_missing"], "extra_count": 0,
            "continue_url": _url(d["continue_url"][0], **d["continue_url"][1]) if d["editable"] else None,
            "view_url": _url("account.my_case_detail", lang=lang, case_id=case.id), "is_action": is_action, "updated_at": case.updated_at,
            "next_step_text": d["next_step_text"]}


def _sort_priority(e):
    """Item 36: customer action required, then active/in-progress, then completed/recent, then archived —
    never plain database id order. `e["tone"]` is the SAME customer-status tone every entry already carries."""
    if e.get("is_action"):
        return 0
    tone = e.get("tone")
    if tone in ("processing",):
        return 1
    if tone == "done":
        return 2
    return 3


def _sort_entries(entries):
    return sorted(entries, key=lambda e: (_sort_priority(e), -(e["updated_at"].timestamp() if e.get("updated_at") else 0)))


def _normalize_case(case, lang):
    if case.case_type == "tax_return":
        return _safe(_tax_entry, case, lang)
    if case.case_type == "itin_application":
        return _safe(_itin_entry, case, lang)
    if case.case_type == "nj_driver_license":
        return _safe(_dl_entry, case, lang)
    if case.case_type == "consent_travel":
        return _safe(_ct_entry, case, lang)
    return _safe(case_entry, case, lang)


# ------------------------------------------------------------------ action items (the single "what do I need to do" list)
def _action_text(entry, lang):
    en = lang != "es"
    if entry["kind"] == "application":
        return f"{entry['title']}: {entry['label']}"
    docs_word = ("document" if entry["docs_missing"] == 1 else "documents") if en else ("documento" if entry["docs_missing"] == 1 else "documentos")
    if entry["docs_missing"]:
        return (f"{entry['title']}: {entry['docs_missing']} {docs_word} needed" if en else f"{entry['title']}: {entry['docs_missing']} {docs_word} necesarios")
    return f"{entry['title']}: {entry['label']}"


def _action_verb(entry, lang):
    """Item 30: a task row must carry a specific verb (Upload/Continue/Review/Confirm), never a generic "View"."""
    en = lang != "es"
    status = _entry_state(entry)
    if entry.get("docs_missing"):
        return "Upload" if en else "Subir"
    if status == "reopened":
        return "Review" if en else "Revisar"
    if entry.get("price") and entry["price"].get("state") == "confirmed" and entry["price"].get("needs_ack"):
        return "Confirm" if en else "Confirmar"
    if status == "draft":
        return "Continue" if en else "Continuar"
    return "Review" if en else "Revisar"


def action_items(entries, orphan_entries, lang):
    items = []
    for e in orphan_entries:
        if e and e["is_action"]:
            items.append({"text": _action_text(e, lang), "href": e["continue_url"] or e["view_url"], "verb": "Continue" if lang != "es" else "Continuar"})
    for e in entries:
        if e and e["is_action"]:
            href = e["continue_url"] or e["view_url"]
            items.append({"text": _action_text(e, lang), "href": href, "verb": _action_verb(e, lang)})
    return items


# ------------------------------------------------------------------ documents preview (across every case, requirement/vault based)
def all_requirements(cases, lang):
    rows = []
    for case in cases:
        for r in _safe(vault.visible_requirements, case, default=[]):
            title, message = vault.customer_text(r, lang)
            if r.status == "needs_replacement" and r.review_message:
                message = r.review_message
            override = vault.status_override(r, lang)
            label, tone = override if override else customer_status.requirement_status(r.status, lang)
            rows.append({"req": r, "case": case, "title": title, "message": message, "label": label, "tone": tone,
                         "can_upload": r.status in vault.CUSTOMER_CAN_UPLOAD, "can_remove": vault.customer_can_remove(r, r.current_document),
                         "upload_url": _url("account.my_case_upload", lang=lang, case_id=case.id, requirement_id=r.id),
                         "remove_url": _url("account.my_case_remove", lang=lang, case_id=case.id, requirement_id=r.id)})
    rows.sort(key=lambda x: (x["req"].status not in ("needed", "requested", "needs_replacement"), x["req"].updated_at or x["req"].created_at), reverse=False)
    return rows


def action_count(student, lang="en"):
    """Cheap count for the header's notification indicator (shown on every account page, not just Home)."""
    return len(_safe(lambda: home_data(student, lang)["actions"], default=[]))


# ------------------------------------------------------------------ Home
def home_data(student, lang):
    cases = Case.query.filter_by(customer_id=student.id).order_by(Case.updated_at.desc(), Case.id.desc()).all()
    cases = [c for c in cases if not (c.status == "closed" and not c.applications)]
    orphan_subs = (FormSubmission.query.filter_by(student_id=student.id, case_id=None)
                   .order_by(FormSubmission.is_complete.asc(), FormSubmission.updated_at.desc()).all())

    entries = [x for x in (_normalize_case(c, lang) for c in cases) if x is not None]
    orphan_entries = [x for x in (_safe(_app_entry, s, lang) for s in orphan_subs) if x is not None]
    entries = _sort_entries(entries)  # action-required first, then active, then completed/archived (item 36)

    tax_entries = [e for e in entries if e["kind"] in ("tax", "itin")]
    immigration_entries = [e for e in entries if e["kind"] == "case" and e["case"].case_type in _immigration_types()]
    dl_entries = [e for e in entries if e["kind"] == "dl"]
    other_entries = [e for e in entries if e["kind"] == "ct" or (e["kind"] == "case" and e["case"].case_type not in _immigration_types())]

    from app import payments_dashboard

    payment_actions = _safe(payments_dashboard.action_items, student, lang, default=[])
    actions = payment_actions + _safe(action_items, entries, orphan_entries, lang, default=[])
    docs_preview = _safe(all_requirements, cases, lang, default=[])
    docs_action_first = sorted(docs_preview, key=lambda r: r["req"].status not in ("needed", "requested", "needs_replacement"))

    return {
        "avatar": avatar(student, lang),
        "actions": actions,
        "tax_entries": tax_entries[:2],
        "immigration_entries": (immigration_entries + orphan_entries_for_immigration(orphan_entries))[:3],
        "dl_entries": dl_entries[:1],
        "other_entries": other_entries[:2],
        "docs_preview": docs_action_first[:5],
        "docs_total": len(docs_preview),
        "files_from_og": _safe(files_from_og_summary, student, lang, default={"count": 0, "new_count": 0, "latest": None}),
        "has_services": bool(cases or orphan_subs),
        "more_services": len(cases) + len(orphan_subs) > (len(tax_entries) + len(immigration_entries) + len(dl_entries) + len(other_entries) + len(orphan_entries)),
    }


# ------------------------------------------------------------------ Files from OG (item 19: a small Home summary; item A3-A14: the dedicated page)
def files_from_og_summary(student, lang):
    """Item A19: Home shows a compact card, never the full page duplicated — count, how many are unseen
    (never downloaded — reusing the existing `downloaded_at` column rather than inventing a "read" flag),
    and the single most recent file."""
    from app import customer_files as cf_service

    rows = cf_service.for_customer(student)
    latest = rows[0] if rows else None
    return {"count": len(rows), "new_count": sum(1 for f in rows if f.downloaded_at is None),
            "latest": _og_file_row(latest, lang) if latest else None}


def _og_file_row(f, lang):
    from app.models import category_label

    return {"f": f, "title": f.title, "category": f.category, "category_label": category_label(f.category, lang),
            "related_service": f.related_service, "tax_year": f.tax_year, "person": f.person, "description": f.description,
            "released_at": f.published_at, "is_new": f.downloaded_at is None,
            "can_preview": (f.mime_type or "") in ("application/pdf", "image/jpeg", "image/png", "image/webp"),
            "view_url": _url("account.og_file_download", lang=lang, file_id=f.id, inline=1), "download_url": _url("account.og_file_download", lang=lang, file_id=f.id)}


def files_from_og_data(student, lang, category=None, q=None):
    from app import customer_files as cf_service
    from app.models import FILE_CATEGORIES

    all_rows = cf_service.for_customer(student)
    counts = cf_service.counts_by_category(student)
    rows = cf_service.search(student, category=category, q=q)
    rows = [_og_file_row(f, lang) for f in rows]
    tax_rows, other_rows = [], []
    for r in rows:
        (tax_rows if r["category"] == "taxes" else other_rows).append(r)
    tax_by_year = {}
    for r in tax_rows:
        tax_by_year.setdefault(r["tax_year"], []).append(r)
    tax_years = sorted((y for y in tax_by_year if y), reverse=True)
    if None in tax_by_year:
        tax_years.append(None)  # undated tax files last, still shown, never dropped
    people = sorted({f.person for f in all_rows if f.person}, key=lambda p: p.full_name)
    return {"rows": rows, "tax_by_year": tax_by_year, "tax_years": tax_years, "other_rows": other_rows,
            "categories": FILE_CATEGORIES, "counts": counts, "total": len(all_rows), "category": category or "all", "q": q or "", "people": people}


def orphan_entries_for_immigration(orphan_entries):
    # an orphan (case-less) application is virtually always an unfinished immigration/tax intake that hasn't
    # reached its own case-setup step yet — it belongs in the Immigration section so the customer sees it,
    # not silently dropped because it has no Case row yet.
    return orphan_entries


def _immigration_types():
    from app.case_types import CASE_DOMAINS

    return [k for k, v in CASE_DOMAINS.items() if v.get("key") == DOMAIN_IMMIGRATION]


# ------------------------------------------------------------------ Services (the full list)
# The four CUSTOMER-FACING groupings (item 13): a presentation layer only — Case/Application/CasePerson etc.
# underneath are completely unchanged; this only decides which section of the Services page an entry appears in.
FAMILIES = [
    ("immigration", ("Immigration", "Inmigración"), "immigration"),
    ("tax_itin", ("Taxes & ITIN", "Impuestos e ITIN"), "taxes"),
    ("driver_license", ("NJ Driver License", "Licencia de Conducir de NJ"), "license"),
    ("other", ("Other Services", "Otros Servicios"), "documents"),
]


def _family_of(e):
    if e["kind"] in ("tax", "itin"):
        return "tax_itin"
    if e["kind"] == "dl":
        return "driver_license"
    if e["kind"] == "application" or (e["kind"] == "case" and e["case"].case_type in _immigration_types()):
        return "immigration"
    return "other"


def services_data(student, lang):
    cases = Case.query.filter_by(customer_id=student.id).order_by(Case.updated_at.desc(), Case.id.desc()).all()
    cases = [c for c in cases if not (c.status == "closed" and not c.applications)]
    orphan_subs = (FormSubmission.query.filter_by(student_id=student.id, case_id=None)
                   .order_by(FormSubmission.is_complete.asc(), FormSubmission.updated_at.desc()).all())
    entries = [x for x in (_normalize_case(c, lang) for c in cases) if x is not None]
    orphan_entries = [x for x in (_safe(_app_entry, s, lang) for s in orphan_subs) if x is not None]
    all_entries = _sort_entries(orphan_entries + entries)

    needs_attention = [e for e in all_entries if e["is_action"]]
    done_states = {"completed", "closed", "archived", "accepted"}
    rest = [e for e in all_entries if not e["is_action"]]

    families = []
    for key, (title_en, title_es), icon in FAMILIES:
        fam_entries = [e for e in rest if _family_of(e) == key]
        if not fam_entries:
            continue
        families.append({"key": key, "title": title_es if lang == "es" else title_en, "icon": icon,
                         "active": [e for e in fam_entries if _entry_state(e) not in done_states],
                         "completed": [e for e in fam_entries if _entry_state(e) in done_states]})

    categories = ServiceCategory.query.filter_by(is_published=True).order_by(ServiceCategory.sort_order, ServiceCategory.id).all()
    return {"needs_attention": needs_attention, "families": families, "categories": categories}


def _entry_state(e):
    if e["kind"] == "application":
        return status_key(e["sub"])
    return e["case"].status


# ------------------------------------------------------------------ My Documents (customer -> OG only; item A2). "Files
# from OG" (OG -> customer) is now its own dedicated page (`files_from_og_data`) — never mixed in this list.
def documents_data(student, lang):
    _, _, document_rows = _portal_helpers()
    cases = Case.query.filter_by(customer_id=student.id).order_by(Case.updated_at.desc()).all()
    rows = _safe(all_requirements, cases, lang, default=[])
    grouped = {}
    order = []
    for r in rows:
        key = r["case"].id
        if key not in grouped:
            grouped[key] = {"case": r["case"], "title": type_title(r["case"].case_type, lang), "rows": []}
            order.append(key)
        grouped[key]["rows"].append(r)
    files = _safe(document_rows, student, default=[])
    files = [f for f in files if f.original_filename != "signature.png"]
    return {"groups": [grouped[k] for k in order], "files": files,
            "have": sum(1 for r in rows if r["req"].status in ("uploaded", "under_review", "accepted")), "total": len(rows)}


# ------------------------------------------------------------------ Messages (read-only aggregation, no new persistence)
def messages_data(student, lang):
    from datetime import datetime

    _, card_title, _ = _portal_helpers()
    msgs = []
    subs = FormSubmission.query.filter_by(student_id=student.id).all()
    sub_ids = [s.id for s in subs]
    if sub_ids:
        notes = SubmissionNote.query.filter(SubmissionNote.submission_id.in_(sub_ids), SubmissionNote.is_customer_visible.is_(True)).order_by(SubmissionNote.created_at.desc()).all()
        by_sub = {s.id: s for s in subs}
        for n in notes:
            sub = by_sub.get(n.submission_id)
            if sub is None:
                continue
            msgs.append({"text": n.body, "at": n.created_at, "href": _url("account.application_detail", lang=lang, submission_id=sub.id), "title": card_title(sub, lang)})
        for sub in subs:
            if sub.status == "reopened" and sub.reopen_message:
                msgs.append({"text": sub.reopen_message, "at": sub.updated_at, "href": _url("account.application_detail", lang=lang, submission_id=sub.id), "title": card_title(sub, lang)})
    cases = Case.query.filter_by(customer_id=student.id).all()
    for case in cases:
        if case.case_type == "tax_return" and case.tax_data is not None:
            tx = case.tax_data
            if tx.status == "waiting_client" and tx.customer_message:
                msgs.append({"text": tx.customer_message, "at": tx.updated_at, "href": _url("account.my_case_detail", lang=lang, case_id=case.id), "title": type_title(case.case_type, lang)})
            if tx.status == "reopened" and tx.reopen_message:
                msgs.append({"text": tx.reopen_message, "at": tx.reopened_at or tx.updated_at, "href": _url("account.my_case_detail", lang=lang, case_id=case.id), "title": type_title(case.case_type, lang)})
        for r in _safe(vault.visible_requirements, case, default=[]):
            if r.status == "needs_replacement" and r.review_message:
                title, _msg = vault.customer_text(r, lang)
                msgs.append({"text": f"{title}: {r.review_message}", "at": r.reviewed_at or r.updated_at, "href": _url("account.my_case_detail", lang=lang, case_id=case.id) + "#documents", "title": type_title(case.case_type, lang)})
    msgs.sort(key=lambda m: m["at"] or datetime.min, reverse=True)
    return msgs
