"""DS-260 document requirements on the case vault (no DS-260-specific storage). Every requirement says WHY it exists (`doc_basis`):

  dos_nvc   the Department of State / National Visa Center civil-documents page lists it (birth, marriage and divorce, police certificates for the
            applicants; certified translation in one file after the original; originals to the interview). OG does NOT invent a universal checklist
            beyond what that page states: the NVC tells each case which documents apply, and OG confirms with the customer.
  answer    triggered by an answer (a previous spouse whose marriage ended, a refused visa, military service, a Security & Background answer).
  workflow  what OG asks for to prepare the answers (a copy of the passport's photo page).
  admin     added by OG in the case.
  customer  added by the customer (an additional document uploaded in the vault).

Requirements are per Person (each visa applicant has their own), so one applicant's documents never appear on another applicant's DS-260. Titles for
requirements tied to a private Security & Background answer are deliberately neutral. A document already in the case vault for that person is attached
instead of asked again. Requirements of every active DS-260 of the case are computed together, so syncing one never withdraws another's.
"""

import html

from flask import url_for

from app import case_documents as vault
from app import cases as case_svc
from app import ds260_calc as calc
from app.case_types import category_label
from app.i485_docs import application_requirements
from app.intake_records import parse_records
from app.models import DocumentRequirement

SOURCE_KEY = "ds260"

GROUPS = [
    ("civil", ("Civil documents", "Documentos civiles"), ("ds260.passport", "ds260.birth", "ds260.marriage", "ds260.prev_end", "ds260.police")),
    ("answers", ("Because of your answers", "Por tus respuestas"), ("ds260.refusal", "ds260.military", "ds260.private")),
]


def desired(submission):
    a = case_svc.answers_by_name(submission)
    applicant = case_svc.role_person(submission, "visa_applicant")
    out = []

    def add(rule_key, title, category, basis, message=None):
        out.append({"rule_key": rule_key, "title": title, "person": applicant, "category": category, "applications": [submission],
                    "customer_message": message, "reuse": True, "doc_basis": basis})

    add("ds260.passport", "Copy of the passport's photo page", "passport", "workflow", "OG uses it to prepare the passport and personal answers exactly as they appear.")
    add("ds260.birth", "Birth certificate", "birth_certificate", "dos_nvc", "The National Visa Center's civil-documents list includes it. If it is not in English, one certified translation (in the same file, after the original) is needed.")
    if a.get("a_marital") in ("married", "separated", "divorced", "widowed", "annulled") or a.get("ps_has") == "yes":
        add("ds260.marriage", "Marriage certificate", "marriage_certificate", "dos_nvc", "For each marriage. OG will confirm with you which ones apply.")
    ended = [r for r in parse_records(a.get("ps_records")) if r.get("how_ended") in ("death", "divorce", "annulment")]
    if ended:
        add("ds260.prev_end", "Divorce decree, annulment or death certificate for each previous marriage", "divorce_death_certificate", "answer")
    add("ds260.police", "Police certificate(s)", "police_certificate", "dos_nvc", "The National Visa Center's Document Finder shows which countries' police certificates apply. OG will go through it with you.")
    if a.get("t_refused") == "yes":
        add("ds260.refusal", "Any papers you have about the earlier U.S. visa or entry matter (if you have them)", "immigration_document", "answer")
    if a.get("aw_mil") == "yes":
        add("ds260.military", "Military service records (if you have them)", "other", "answer")
    if calc.review_flags(a) and any(k in ("medical", "criminal", "security1", "security2", "immig1", "immig2", "misc1", "misc2") for k in calc.review_flags(a)):
        add("ds260.private", "Additional supporting documents — OG will tell you privately what is useful", "other", "answer",
            "Share only what you are comfortable sharing. OG will explain in private what may be useful. These documents are visible only to you and OG.")
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
    for key, _label, rules in GROUPS:
        if rule_key in rules:
            return key
    return "answers"


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
