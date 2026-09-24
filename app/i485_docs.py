"""I-485 document requirements, built on the case document vault (no I-485-specific storage).

Every requirement says WHY it exists (`doc_basis`), because OG must not present an OG workflow request as a USCIS
requirement:
  source    the supplied Form I-485 itself says to attach it (Part 3 Item 1.a SSA earnings statements; Part 9 Item 24 note
            for documentation of a pardon/clemency; Part 9 Item 65 note for the written statement about a missed
            removal proceeding).
  workflow  what OG asks for to prepare and review the case. The Form I-485 Instructions (which list USCIS's required
            evidence) are not part of the supplied PDF, so nothing in this group is claimed to be a USCIS requirement.
  answer    triggered by an answer (a prior marriage, a petition receipt number).
  admin     a manual request from OG Admin (created elsewhere).

A requirement is satisfied at once when the case vault already holds that document for that person (for example the
passport uploaded for the I-130): the customer is told it was already received.
"""

import html

from flask import url_for

from app import case_documents as vault
from app import cases as case_svc
from app.case_types import category_label
from app.models import ApplicationRole, RequirementApplication, DocumentRequirement

SOURCE_KEY = "i485"


def _yes(a, name):
    return a.get(name) == "yes"


def desired(submission):
    """[{rule_key, title, person?, category, applications, customer_message, doc_basis}] implied by the current answers."""
    a = case_svc.answers_by_name(submission)
    applicant = case_svc.role_person(submission, "applicant")
    spouse = case_svc.role_person(submission, "spouse")
    apps = [submission]
    out = []

    def add(rule_key, title, category, person=None, basis="workflow", message=None):
        out.append({"rule_key": rule_key, "title": title, "person": person, "category": category, "applications": apps,
                    "customer_message": message, "reuse": True, "doc_basis": basis})

    add("i485.passport", "Passport (biographic page and any pages with visas or stamps)", "passport", applicant, "workflow",
        "A clear, complete scan or photo of the biographic page. If you last arrived with a passport, include the pages showing your visa and entry stamp.")
    add("i485.birth", "Birth certificate", "birth_certificate", applicant, "workflow", "If it is not in English, OG will help arrange a certified translation.")
    add("i485.photo_id", "Government-issued photo ID", "photo_id", applicant, "workflow")
    if a.get("a_i94_number") or a.get("a_arr_how") in ("admitted", "paroled"):
        add("i485.i94", "Form I-94 arrival/departure record", "immigration_document", applicant, "workflow",
            "You can usually get your most recent electronic I-94 from the official U.S. Customs and Border Protection I-94 website.")
    if a.get("m_status") in ("married", "separated"):
        add("i485.marriage", "Marriage certificate (current marriage)", "marriage_certificate", None, "answer")
    if a.get("m_prior") or a.get("m_status") in ("divorced", "widowed", "annulled"):
        add("i485.prior_marriages", "Evidence that each prior marriage ended (divorce decree, annulment decree or death certificate)", "divorce_death_certificate",
            applicant, "answer")
    if a.get("b_receipt"):
        add("i485.underlying_notice", "Receipt or approval notice for the underlying petition", "immigration_document", applicant, "answer")
    if a.get("b_i864_exempt") == "q40":
        add("i485.ssa_earnings", "Social Security earnings statements", "financial_document", applicant, "source",
            "Part 3, Item 1.a of the form says to attach your SSA earnings statements. Do not count quarters in which you received a means-tested public benefit.")
    if _yes(a, "e24") and _yes(a, "e24_clemency"):
        add("i485.clemency", "Documentation of the pardon, amnesty, rehabilitation decree or other act of clemency", "other", applicant, "source",
            "Part 9, Item 24 of the form says to provide documentation of that post-conviction action.")
    if _yes(a, "e65"):
        add("i485.removal_statement", "Written statement about the removal proceeding you did not attend", "other", applicant, "source",
            "Part 9, Item 65 of the form says to attach a written statement explaining why you failed or refused to attend, including any reasonable cause.")
    return out


def sync(submission):
    case = submission.case
    if case is None:
        return None
    return vault.sync_requirements(case, SOURCE_KEY, desired(submission))


def application_requirements(submission):
    """The case's requirements that serve this application."""
    ids = [l.requirement_id for l in RequirementApplication.query.filter_by(submission_id=submission.id).all()]
    if not ids:
        return []
    return [r for r in DocumentRequirement.query.filter(DocumentRequirement.id.in_(ids)).order_by(DocumentRequirement.id).all() if r.withdrawn_at is None]


def open_application_requirements(submission):
    return [r for r in application_requirements(submission) if r.status in ("needed", "requested", "needs_replacement")]


# ------------------------------------------------------------------ underlying petition
def underlying_candidates(submission):
    """Petitions of THIS case in which the applicant is the beneficiary (never chosen for the customer)."""
    applicant = case_svc.role_person(submission, "applicant")
    case = submission.case
    if applicant is None or case is None:
        return []
    rows = ApplicationRole.query.filter(ApplicationRole.case_id == case.id, ApplicationRole.person_id == applicant.id,
                                        ApplicationRole.role_key.in_(("beneficiary", "spouse_beneficiary"))).all()
    seen, out = set(), []
    for r in rows:
        s = r.submission
        if s.id != submission.id and s.id not in seen and s.form.source_form_name == "I-130":
            seen.add(s.id)
            out.append(s)
    return out


def underlying_html(submission, lang="en"):
    en = lang == "en"
    cands = underlying_candidates(submission)
    if not cands:
        text = ("We did not find a related petition in your case. That is fine: you can still continue and OG will review this with you."
                if en else "No encontramos una petición relacionada en tu caso. No hay problema: puedes continuar y OG lo revisará contigo.")
        return f'<p class="text-[13px] text-slate-500">{html.escape(text)}</p>'
    from app.intake_engine import status_label

    rows = "".join(
        f'<p class="mt-1 text-[15px] font-semibold text-brand-800">{html.escape("Form " + (s.form.source_form_name or ""))} &middot; <span class="font-mono">{html.escape(s.code)}</span></p>'
        f'<p class="text-[13px] text-slate-600">{html.escape(status_label(s, lang))}</p>' for s in cands)
    head = "We found this petition in your case" if en else "Encontramos esta petición en tu caso"
    return ('<div class="rounded-xl border border-accent-200 bg-mist-50 px-4 py-3">'
            f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape(head)}</p>{rows}</div>')


# ------------------------------------------------------------------ the Documents step
def documents_html(submission, lang="en", sync_fn=None):
    en = lang == "en"
    case = submission.case
    try:
        (sync_fn or sync)(submission)  # the list always reflects the current answers, even if the last step saved before an answer changed
    except Exception:  # noqa: BLE001
        from app.extensions import db

        db.session.rollback()
    reqs = application_requirements(submission)
    if case is None or not reqs:
        return f'<p class="text-[13px] text-slate-500">{html.escape("No documents are needed yet." if en else "Aún no se necesitan documentos.")}</p>'
    tone = vault.STATUS_TONE
    rows = []
    for r in reqs:
        who = f" · {html.escape(r.person.full_name)}" if r.person else ""
        received = ('<p class="mt-1 text-[12px] font-semibold text-emerald-700">&#10003; ' + html.escape("Already received" if en else "Ya recibido") + "</p>") if r.reused_at else ""
        basis = vault.BASIS_LABELS.get(r.doc_basis or "workflow", vault.BASIS_LABELS["workflow"])[0 if en else 1]
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
            f'<p class="mt-0.5 text-[11px] text-slate-400">{html.escape(category_label(r.category, lang))}{who} &middot; {html.escape(basis)}</p>{received}{action}</li>')
    return f'<ul class="space-y-2">{"".join(rows)}</ul>'


# ------------------------------------------------------------------ the "Before you begin" card
def context_html(submission, lang="en"):
    """Who this application is for, which case it lives in, and what else the case holds (no eligibility statements)."""
    en = lang == "en"
    case = submission.case
    applicant = next((p for p in (case_svc.role_person(submission, r) for r in ("applicant", "conditional_resident", "sponsor")) if p is not None), None)
    if case is None or applicant is None:
        return ""
    others = [s for s in case.applications if s.id != submission.id]
    rows = [
        f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape("This application is for" if en else "Esta solicitud es para")}</p>'
        f'<p class="mt-1 text-[17px] font-extrabold tracking-tight text-brand-800 break-words">{html.escape(applicant.full_name)}</p>'
        f'<p class="text-[13px] text-slate-600">{html.escape("Case" if en else "Caso")} <span class="font-mono font-semibold">{html.escape(case.case_number or "")}</span></p>']
    if others:
        from app.intake_engine import status_label

        head = "Also in this case" if en else "También en este caso"
        items = "".join(
            f'<li class="text-[13px] text-slate-600 break-words">{html.escape("Form " + (s.form.source_form_name or s.form.name_admin))} &middot; '
            f'<span class="font-mono">{html.escape(s.code)}</span> &middot; {html.escape(status_label(s, lang))}</li>' for s in others)
        rows.append(f'<p class="mt-3 text-xs font-bold uppercase tracking-wider text-slate-500">{html.escape(head)}</p><ul class="mt-1 space-y-0.5">{items}</ul>')
    return '<div class="rounded-xl border border-accent-200 bg-mist-50 px-4 py-3">' + "".join(rows) + "</div>"
