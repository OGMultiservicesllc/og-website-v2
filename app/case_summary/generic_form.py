"""Case Summary sections for any generic Smart-Intake (FormSubmission-based) application — I-90, N-400,
I-130 (+ its I-130A supplement pages, already part of the SAME submission), I-485, I-864, I-765, I-751,
DS-260, and each individual W-7/ITIN application.

Reuses `intake_engine.review_sections()` (the SAME grouped, human-labeled Q&A the customer's own Review
page and Admin's application page already render — never re-derives field labels/values) and, where the
form defines them, `Form.features["sections"]` (human section titles keyed by `FormPage.group_key`,
already authored for the completeness-check feature) and `Form.features["contexts"]` (person-role titles
keyed by `FormPage.context_key`, e.g. Petitioner/Beneficiary) to turn raw page order into a properly
organized, person-labeled summary — deterministically, with no per-form hand-written field list.

A form with neither `features["sections"]` nor `features["contexts"]` configured (currently only I-90,
a single-applicant form with no ambiguity about whose information is whose) falls back to one Section per
form page, titled by the page's own title — still fully human-readable and grouped, never raw JSON.
"""
from app.case_summary.blocks import Field, KeyValueBlock, Section


def build_sections(form, submission, lang="en"):
    from app.intake_engine import context_map, review_sections

    sections_data = review_sections(form, submission, lang, reveal=True)
    ctx_map = context_map(form, submission, lang)
    feats = form.features or {}
    section_cfg = feats.get("sections") or []
    section_title = {}
    for s in section_cfg:
        title = s.get("title") or {}
        section_title[s["key"]] = title.get(lang) or title.get("en") or s["key"]

    # Two-level grouping, first-seen order preserved: CONTEXT (person role, e.g. Petitioner/Beneficiary)
    # is the top-level Section — matching the task's "one PETITIONER block" example — and each context's
    # own topical groups (Identity, Address History, Employment...) become sub-headed blocks inside it,
    # rather than fragmenting one person into many small navy-banner sections. A page with no context
    # (relationship info, documents-adjacent pages, etc.) becomes its own top-level Section by group_key.
    ctx_order, ctx_groups = [], {}
    for sec in sections_data:
        page = sec["page"]
        gkey = getattr(page, "group_key", None) or "other"
        ckey = getattr(page, "context_key", None)
        if ckey not in ctx_groups:
            ctx_groups[ckey] = {"order": [], "groups": {}}
            ctx_order.append(ckey)
        cg = ctx_groups[ckey]
        if gkey not in cg["groups"]:
            title = section_title.get(gkey) or (gkey.replace("_", " ").title() if section_cfg or ckey else sec["title"])
            cg["groups"][gkey] = {"title": title, "items": []}
            cg["order"].append(gkey)
        cg["groups"][gkey]["items"].extend(sec["items"])

    def _fields(items):
        out = []
        for item in items:
            value = item["value"]
            if item["missing"]:
                out.append(Field(item["label"], None, missing=True))
            elif value not in (None, "", []):
                out.append(Field(item["label"], str(value)))
        return out

    sections = []
    for ckey in ctx_order:
        cg = ctx_groups[ckey]
        ctx = ctx_map.get(ckey) if ckey else None
        if ctx:
            blocks = []
            multi = len(cg["order"]) > 1
            for gkey in cg["order"]:
                fields = _fields(cg["groups"][gkey]["items"])
                if fields:
                    blocks.append(KeyValueBlock(fields=fields, heading=cg["groups"][gkey]["title"] if multi else None))
            if blocks:
                sections.append(Section(title=ctx["title"], person_role=ctx["title"], blocks=blocks))
        else:
            for gkey in cg["order"]:
                fields = _fields(cg["groups"][gkey]["items"])
                if fields:
                    sections.append(Section(title=cg["groups"][gkey]["title"], blocks=[KeyValueBlock(fields=fields)]))
    return sections


def application_label(form):
    parts = [form.source_form_name or form.name_admin]
    if form.source_edition:
        parts.append(f"(edition {form.source_edition})")
    return " ".join(p for p in parts if p)
