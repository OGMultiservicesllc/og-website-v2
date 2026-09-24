"""I-751 document requirements on the case vault (no I-751-specific storage). Every requirement says WHY it exists (`doc_basis`):

  source    the supplied Form I-751 itself says to attach it. The supplied PDF does not list required evidence (that is in the Form I-751
            Instructions, which were NOT supplied), so nothing here is labelled "source".
  workflow  what OG asks for to prepare and review the petition. OG confirms with the customer what applies to their situation.
  answer    triggered by an answer (a Yes to Items 18-21, a filing basis, children included in the petition).
  admin     added by OG in the case.

Titles for requirements tied to a private filing basis are deliberately neutral: they never name the basis. A document already in the case
vault for that person is attached instead of asked again (same case only). Requirements of every active I-751 of the case are computed
together, so syncing one application never withdraws another's.
"""

import html

from flask import url_for

from app import case_documents as vault
from app import cases as case_svc
from app import i751_calc as calc
from app.case_types import category_label
from app.i485_docs import application_requirements, open_application_requirements  # noqa: F401
from app.models import DocumentRequirement

SOURCE_KEY = "i751"

# friendly groups for the customer (never USCIS categories)
GROUPS = [
    ("status", ("Your status", "Tu estatus"), ("i751.green_card", "i751.proceedings")),
    ("marriage", ("Your marriage", "Tu matrimonio"), ("i751.marriage_cert", "i751.relationship_evidence", "i751.death_cert", "i751.divorce_decree", "i751.different_marriage")),
    ("basis", ("Your filing situation", "Tu situación de presentación"), ("i751.basis_docs",)),
    ("family", ("Your children", "Tus hijos"), ("i751.child_birth",)),
    ("other", ("Other documents", "Otros documentos"), ("i751.dispositions", "i751.fee_receipts")),
]


def desired(submission):
    a = case_svc.answers_by_name(submission)
    resident = case_svc.role_person(submission, "conditional_resident")
    out = []

    def add(rule_key, title, category, basis="workflow", message=None, person=True):
        out.append({"rule_key": rule_key, "title": title, "person": resident if person else None, "category": category, "applications": [submission],
                    "customer_message": message, "reuse": True, "doc_basis": basis})

    boxes = calc.basis(a)
    add("i751.green_card", "Copy of your Permanent Resident Card (front and back)", "proof_of_status", "workflow",
        "OG will confirm with you which of your documents are needed for this petition.")
    if calc.route(a) in ("joint", "waiver") or a.get("r_marital") in ("married", "divorced", "widowed"):
        if "1f" in boxes or a.get("p4_rel") == "parent_spouse":
            add("i751.marriage_cert", "Marriage certificate — your parent and their spouse", "marriage_certificate", "workflow", "OG will confirm which marriage record applies.", person=False)
        else:
            add("i751.marriage_cert", "Marriage certificate", "marriage_certificate", "workflow", "OG will confirm which marriage record applies.")
    if calc.route(a) == "joint":
        add("i751.relationship_evidence", "Evidence of your life together — OG will tell you what to send", "relationship_evidence", "workflow",
            "The Form I-751 Instructions (which we do not have in this intake) describe the evidence USCIS looks at. OG will go through what applies to you.")
    if "1c" in boxes:
        add("i751.death_cert", "Death certificate of your spouse", "divorce_death_certificate", "answer")
    if "1d" in boxes or (calc.marriage_ended(a) and "1c" not in boxes):
        add("i751.divorce_decree", "Divorce decree or annulment order", "divorce_death_certificate", "answer")
    if any(b in boxes for b in ("1e", "1f", "1g")):
        add("i751.basis_docs", "Supporting documents for your filing situation — OG will explain what is useful", "other", "answer",
            "Share only what you are comfortable sharing. OG will explain in private what may be useful. These documents are visible only to you and OG.")
    if a.get("q18") == "yes":
        add("i751.proceedings", "Notices or documents about your proceedings (if you have them)", "immigration_document", "answer")
    if a.get("q19") == "yes":
        add("i751.fee_receipts", "Any receipt or agreement for the fee you mentioned (if you have it)", "other", "answer")
    if a.get("q20") == "yes":
        add("i751.dispositions", "Criminal history documents — OG will tell you exactly what is needed", "other", "answer",
            "The form refers to the What Initial Evidence Is Required section of the Form I-751 Instructions for which criminal history documents to include. OG will review this with you and tell you what to send.")
    if a.get("q21") == "yes":
        add("i751.different_marriage", "Marriage certificate of your current marriage", "marriage_certificate", "answer")
    if calc.applying_children(a):
        add("i751.child_birth", "Birth certificates of the children included in this petition", "birth_certificate", "workflow", person=False)
    return out


def _active_siblings(submission):
    case = submission.case
    return [x for x in case.applications if x.form_id == submission.form_id and x.status != "archived" and x.id != submission.id] if case is not None else []


def sync(submission):
    case = submission.case
    if case is None:
        return None
    from app.extensions import db

    siblings = _active_siblings(submission)
    merged = {}
    for sub in [submission] + siblings:
        for spec in desired(sub):
            person = spec["person"]
            key = (spec["rule_key"], person.id if person else None)
            if key in merged:
                merged[key]["applications"] = list({x.id: x for x in merged[key]["applications"] + spec["applications"]}.values())
            else:
                merged[key] = dict(spec, applications=list(spec["applications"]))
    result = vault.sync_requirements(case, SOURCE_KEY, list(merged.values()))
    ids = {x.id for x in [submission] + siblings}
    for req in DocumentRequirement.query.filter_by(case_id=case.id, source="system", source_key=SOURCE_KEY).all():
        wanted_by = {x.id for x in merged.get((req.rule_key, req.person_id), {}).get("applications", [])}
        for link in list(req.application_links):
            if link.submission_id in ids and link.submission_id not in wanted_by:
                db.session.delete(link)
    db.session.commit()
    return result


def _group_of(rule_key):
    for key, label, rules in GROUPS:
        if rule_key in rules:
            return key
    return "other"


def documents_html(submission, lang="en"):
    en = lang == "en"
    case = submission.case
    try:
        sync(submission)
    except Exception:  # noqa: BLE001
        from app.extensions import db

        db.session.rollback()
    reqs = application_requirements(submission)
    if case is None or not reqs:
        return f'<p class="text-[13px] text-slate-500">{html.escape("No documents are needed yet." if en else "Aún no se necesitan documentos.")}</p>'
    tone = vault.STATUS_TONE
    by_group = {}
    for r in reqs:
        by_group.setdefault(_group_of(r.rule_key or ""), []).append(r)
    blocks = []
    for key, label, _rules in GROUPS:
        rows = []
        for r in by_group.get(key, []):
            who = f" · {html.escape(r.person.full_name)}" if r.person else ""
            received = ('<p class="mt-1 text-[12px] font-semibold text-emerald-700">&#10003; ' + html.escape("Already received" if en else "Ya recibido") + "</p>") if r.reused_at else ""
            basis = vault.BASIS_LABELS.get(r.doc_basis or "workflow", vault.BASIS_LABELS["workflow"])[0 if en else 1]
            message = f'<p class="mt-1 text-[12px] text-slate-500 break-words">{html.escape(r.customer_message)}</p>' if r.customer_message else ""
            try:
                link = url_for("account.my_case_detail", lang=lang, case_id=case.id, _anchor=f"req-{r.id}")
            except RuntimeError:
                link = "#"
            action = "" if r.status in ("accepted", "under_review") else (
                f'<a href="{html.escape(link)}" class="mt-2 inline-flex items-center min-h-[40px] px-3.5 rounded-lg border border-slate-200 text-[13px] font-semibold text-accent-700 hover:border-accent-300">'
                + html.escape("Upload in your case documents" if en else "Subir en los documentos de tu caso") + " &rarr;</a>")
            rows.append(
                '<li class="rounded-xl border border-slate-100 bg-white px-3.5 py-3">'
                '<div class="flex flex-wrap items-start justify-between gap-2">'
                f'<p class="min-w-0 flex-1 basis-40 text-sm font-semibold text-brand-800 break-words">{html.escape(r.title)}</p>'
                f'<span class="inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold {tone[r.status]}">{html.escape(vault.status_label(r.status, lang))}</span></div>'
                f'<p class="mt-0.5 text-[11px] text-slate-400">{html.escape(category_label(r.category, lang))}{who} &middot; {html.escape(basis)}</p>{message}{received}{action}</li>')
        if rows:
            blocks.append(f'<div><p class="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">{html.escape(label[0] if en else label[1])}</p><ul class="space-y-2">{"".join(rows)}</ul></div>')
    return f'<div class="space-y-5">{"".join(blocks)}</div>'
