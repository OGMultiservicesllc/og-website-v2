"""I-765 document requirements on the case vault (no I-765-specific storage). Every requirement says WHY it exists (`doc_basis`):

  source    the supplied Form I-765 itself says to attach it (Part 1 Item 1.c: a copy of the previous employment authorization document).
  workflow  what OG asks for to prepare and review the application. The Form I-765 Instructions (which list USCIS's required evidence) are NOT
            part of the supplied PDF, so nothing here claims USCIS requires it.
  answer    triggered by an answer (a previous I-765, an arrest/conviction Yes).

A document already in the case vault for that person is attached instead of asked again. A requirement that another application of the same
case already made for the same person and document (for example the I-485's passport) is SHARED, not duplicated. Requirements of every active
I-765 of the case are computed together, so syncing one application never withdraws another's.
"""

from app import case_documents as vault
from app import cases as case_svc
from app.i485_docs import application_requirements, documents_html as _documents_html, open_application_requirements  # noqa: F401
from app.models import DocumentRequirement

SOURCE_KEY = "i765"
# rule keys other forms already use for the same person + document
ADOPT = {"i765.passport": ("i485.passport",), "i765.i94": ("i485.i94",)}


def desired(submission):
    a = case_svc.answers_by_name(submission)
    applicant = case_svc.role_person(submission, "applicant")
    out = []

    def add(rule_key, title, category, basis="workflow", message=None):
        out.append({"rule_key": rule_key, "title": title, "person": applicant, "category": category, "applications": [submission],
                    "customer_message": message, "reuse": True, "doc_basis": basis})

    reason = a.get("r_reason")
    if reason == "1c":
        add("i765.prior_ead", "Copy of your previous employment authorization document", "immigration_document", "source",
            "Part 1, Item 1.c of the form says to attach a copy of your previous employment authorization document.")
    if reason == "1b":
        add("i765.replaced_ead", "Copy of the employment authorization document being replaced or corrected (if you have it)", "immigration_document", "workflow",
            "If it was lost or stolen you may not have a copy: OG will tell you what to provide instead.")
    if a.get("a_passport"):
        add("i765.passport", "Passport (biographic page)", "passport", "workflow", "A clear, complete scan or photo of the biographic page.")
    if a.get("a_travel_doc"):
        add("i765.travel_doc", "Travel document (biographic page)", "immigration_document", "workflow")
    if a.get("a_i94_number"):
        add("i765.i94", "Form I-94 arrival/departure record", "immigration_document", "workflow", "You can usually get your most recent electronic I-94 from the official U.S. Customs and Border Protection I-94 website.")
    if a.get("p_prior") == "yes":
        add("i765.prior_notices", "Notices or receipts from your previous Form I-765 (if you have them)", "immigration_document", "answer")
    branch = __import__("app.i765_calc", fromlist=["branch"]).branch(a)
    if branch == "c26":
        add("i765.c26_notice", "Copy of your H-1B spouse's most recent Form I-797 notice for Form I-129", "immigration_document", "workflow")
    if branch == "c35":
        add("i765.c35_notice", "Copy of your Form I-797 notice for Form I-140", "immigration_document", "workflow")
    if branch == "c36":
        add("i765.c36_notice", "Copy of your spouse's or parent's Form I-797 notice for Form I-140", "immigration_document", "workflow")
    if (branch == "c8" and a.get("x_c8_arrest") == "yes") or (branch in ("c35", "c36") and a.get("x_c3536_arrest") == "yes"):
        add("i765.dispositions", "Court dispositions — OG will tell you exactly what is needed", "other", "answer",
            "The form refers to the Form I-765 Instructions for how to provide court dispositions. OG will review this with you and tell you what to send.")
    return out


def _active_siblings(submission):
    case = submission.case
    return [x for x in case.applications if x.form_id == submission.form_id and x.status != "archived" and x.id != submission.id] if case is not None else []


def sync(submission):
    case = submission.case
    if case is None:
        return None
    from app.extensions import db
    from app.models import RequirementApplication

    siblings = _active_siblings(submission)
    merged, adopted = {}, []
    for sub in [submission] + siblings:
        for spec in desired(sub):
            person = spec["person"]
            shared = None
            for other_key in ADOPT.get(spec["rule_key"], ()):
                shared = DocumentRequirement.query.filter_by(case_id=case.id, rule_key=other_key, person_id=person.id if person else None).first()
                if shared is not None and shared.withdrawn_at is None:
                    break
                shared = None
            if shared is not None:  # the same document, already requested by another application of the case: share it
                adopted.append((shared, sub))
                continue
            key = (spec["rule_key"], person.id if person else None)
            if key in merged:
                merged[key]["applications"] = list({x.id: x for x in merged[key]["applications"] + spec["applications"]}.values())
            else:
                merged[key] = dict(spec, applications=list(spec["applications"]))
    result = vault.sync_requirements(case, SOURCE_KEY, list(merged.values()))
    for shared, sub in adopted:
        if not RequirementApplication.query.filter_by(requirement_id=shared.id, submission_id=sub.id).first():
            db.session.add(RequirementApplication(requirement_id=shared.id, submission_id=sub.id))
    ids = {x.id for x in [submission] + siblings}
    for req in DocumentRequirement.query.filter_by(case_id=case.id, source="system", source_key=SOURCE_KEY).all():
        wanted_by = {x.id for x in merged.get((req.rule_key, req.person_id), {}).get("applications", [])}
        for link in list(req.application_links):
            if link.submission_id in ids and link.submission_id not in wanted_by:
                db.session.delete(link)
    db.session.commit()
    return result


def documents_html(submission, lang="en"):
    return _documents_html(submission, lang, sync_fn=sync)
