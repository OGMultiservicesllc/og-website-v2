"""Completeness check for Smart Intakes.

Turns a submission into "what is finished, what needs attention" grouped into the
sections an intake defines (`Form.features_json` -> `sections`, each page carries a
`group_key`). Three kinds of things need attention:

  * missing  - a required answer or upload is still empty
  * error    - an answer that cannot be accepted as it stands (bad format, reversed dates)
  * review   - something to double-check: a gap or overlap in a timeline, a trip that may
               need OG's review, or two answers that seem inconsistent with each other

Nothing here decides eligibility. The same report feeds the customer's Completeness
Check page and the Admin application view.
"""

from app.intake_engine import answers_for, path_pages, review_sections
from app.intake_records import analyze, field_config, parse_records, since_from_answers
from app.i130_checks import run as i130_checks
from app.i485_checks import run as i485_checks
from app.i864_checks import run as i864_checks
from app.i765_checks import run as i765_checks
from app.i751_checks import run as i751_checks
from app.ds260_checks import run as ds260_checks
from app.n400_checks import run as n400_checks
from app.w7_checks import run as w7_checks

CONSISTENCY = {"w7": w7_checks,"n400": n400_checks, "i130": i130_checks, "i485": i485_checks, "i864": i864_checks, "i765": i765_checks, "i751": i751_checks, "ds260": ds260_checks}

_TEXT = {
    "missing": ("Answer needed: {label}", "Falta responder: {label}"),
}


def named_answers(form, submission):
    by_id = answers_for(submission)
    return {f.internal_name: by_id.get(f.id) for f in form.all_fields if f.id in by_id}


def _short(text, n=110):
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def completeness_report(form, submission, lang="en"):
    feats = form.features
    pages = form.pages
    page_number = {p.id: i for i, p in enumerate(pages, 1)}
    section_cfg = feats.get("sections") or []
    groups = {}
    order = []

    def group(key):
        if key not in groups:
            title = next((s["title"][lang] for s in section_cfg if s["key"] == key), key.replace("_", " ").title() if key else ("Other" if lang == "en" else "Otros"))
            groups[key] = {"key": key, "title": title, "issues": [], "pages": [],
                           "supplement": next((s.get("supplement") for s in section_cfg if s["key"] == key), None)}
            order.append(key)
        return groups[key]

    for s in section_cfg:
        group(s["key"])

    answers = answers_for(submission)
    path = path_pages(form, answers)
    on_path = {p.id for p in path}
    for section in review_sections(form, submission, lang, reveal=False):
        page = section["page"]
        idx = page_number[section.get("target", page).id]
        g = group(page.group_key or "other")
        g["pages"].append(idx)
        for item in section["items"]:
            field = item["field"]
            if item["missing"]:
                g["issues"].append({"kind": "missing", "page": idx, "field": field.internal_name,
                                    "message": _TEXT["missing"][1 if lang == "es" else 0].format(label=_short(item["label"]))})
            elif item["error"]:
                g["issues"].append({"kind": "error", "page": idx, "field": field.internal_name, "message": item["error"]})
            elif field.field_type == "record_list":
                cfg = field_config(field)
                for x in analyze(cfg, parse_records(answers.get(field.id)), lang, since=since_from_answers(cfg, named_answers(form, submission)))["issues"]:
                    if x["level"] in ("warn", "review"):
                        g["issues"].append({"kind": "review", "page": idx, "field": field.internal_name, "message": x["message"]})

    fn = CONSISTENCY.get(feats.get("consistency"))
    if fn:
        field_page = {f.internal_name: page_number[p.id] for p in pages for f in p.fields}
        named = named_answers(form, submission)
        for c in (fn(named, lang, submission=submission) if getattr(fn, "wants_submission", False) else fn(named, lang)):
            page = next((field_page[n] for n in c["fields"] if n in field_page and pages[field_page[n] - 1].id in on_path), None)
            if page is None:
                continue
            group(c["group"])["issues"].append({"kind": "review", "page": page, "field": c["fields"][0], "message": c["message"]})

    if feats.get("sections") and submission.case_id:
        from app.shared_blocks import blocks_for, changes_after_confirmation

        if blocks_for(form):
            for ch in changes_after_confirmation(submission, lang):
                page = next((p for p in pages if any(f.internal_name == ch["block"] for f in p.fields)), None)
                if page is not None and page.id in on_path:
                    group(page.group_key or "other")["issues"].append({"kind": "review", "page": page_number[page.id], "field": ch["block"], "message": ch["message"]})

    if feats.get("documents_check"):
        from app.i485_docs import open_application_requirements

        docs_page = next((page_number[p.id] for p in pages if p.group_key == "documents"), None)
        if docs_page is not None:
            from app.case_documents import customer_text

            for req in open_application_requirements(submission):
                title = customer_text(req, lang)[0]
                group("documents")["issues"].append({"kind": "review", "page": docs_page, "field": "docs_list",
                                                     "message": (f"Document still needed: {title}" if lang != "es" else f"Aún falta un documento: {title}")})
            if "documents" in groups and not groups["documents"]["pages"]:
                groups["documents"]["pages"].append(docs_page)

    result = []
    for key in order:
        g = groups[key]
        if not g["pages"] and not g["issues"]:
            continue  # a section this customer's path never reaches
        g["ok"] = not g["issues"]
        g["first_page"] = g["issues"][0]["page"] if g["issues"] else (g["pages"][0] if g["pages"] else None)
        result.append(g)
    total = sum(len(g["issues"]) for g in result)
    attention = sum(1 for g in result if not g["ok"])
    sups = {k: {"title": v["customer_title"][lang], "official": v["title"][lang], "form": v["form"], "edition": v["edition"]}
            for k, v in (feats.get("supplements") or {}).items()}
    return {"groups": result, "issue_count": total, "attention_count": attention, "ok": total == 0, "supplements": sups}
