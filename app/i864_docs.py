"""I-864 document requirements on the case vault (no I-864-specific storage). Every requirement says WHY it exists (`doc_basis`):

  source    the supplied Form I-864 itself says to attach it: proof of the sponsor's status (page 1 NOTE), the federal tax return / transcript for
            the most recent year (Part 6 NOTE, Item 16.a), evidence when not required to file (Item 17), the Forms I-864A of household members
            whose income is used (Part 6 Item 13).
  workflow  what OG asks for to prepare and review the affidavit (income, employment and asset evidence, additional tax years). The Form I-864
            Instructions (which list USCIS's required evidence) are NOT in the supplied PDF, so nothing here claims USCIS requires it.
  answer    triggered by an answer.

Requirements belong to the right PERSON (the sponsor, the household member whose income is used...). A document already accepted for that person
in this case is attached instead of asking again ("Already received").
"""

from app import cases as case_svc
from app import i864_calc as calc
from app import i864_views as views
from app.i485_docs import application_requirements, documents_html as _documents_html, open_application_requirements  # noqa: F401
from app import case_documents as vault

SOURCE_KEY = "i864"

_STATUS = {"usc": "proof of your U.S. citizenship", "national": "proof of your U.S. national status", "lpr": "proof of your lawful permanent resident status"}
_STATUS_ES = {"usc": "prueba de tu ciudadanía de EE. UU.", "national": "prueba de tu estatus de nacional de EE. UU.", "lpr": "prueba de tu estatus de residente permanente legal"}


def _case_person(case, rec):
    """The CasePerson of THIS case a record (household member / person whose income is used) stands for: by the verified Person link, else by name."""
    pid = rec.get("person_id")
    if pid:
        for cp in case.people:
            if str(cp.person_id) == str(pid):
                return cp
    name = calc._norm(rec.get("given")) + calc._norm(rec.get("family"))
    if name:
        for cp in case.people:
            if calc._norm(cp.given_name) + calc._norm(cp.family_name) == name:
                return cp
    return None


def desired(submission):
    a = views.answers(submission)
    sponsor = case_svc.role_person(submission, "sponsor")
    principal = case_svc.role_person(submission, "principal_immigrant")
    out = []

    def add(rule_key, title, category, person=None, basis="workflow", message=None):
        out.append({"rule_key": rule_key, "title": title, "person": person, "category": category, "applications": [submission], "customer_message": message,
                    "reuse": True, "doc_basis": basis})

    status = a.get("s_status")
    add("i864.sponsor_status", "Sponsor's proof of U.S. citizenship, U.S. national status or lawful permanent resident status", "proof_of_status", sponsor, "source",
        "The first page of the form says a sponsor must include proof of " + ", ".join([_STATUS[status]] if status in _STATUS else ["citizenship, national status or lawful permanent resident status"]) + ".")
    tx = calc.tax(a)
    rows = tx["rows"]
    if a.get("t_norequire") == "yes":
        add("i864.tax_exempt", "Evidence that you were not required to file a Federal income tax return", "financial_document", sponsor, "source",
            "Item 17 of the form says you have attached evidence that your income was below the IRS required level.")
    elif rows:
        add("i864.tax_recent", f"Federal income tax return or IRS transcript — tax year {rows[0].get('year') or ''}".strip(" —"), "financial_document", sponsor, "source",
            "The form says to attach a photocopy or transcript of your Federal income tax return for the most recent tax year.")
    if len(rows) > 1 and a.get("t_norequire") != "yes":
        add("i864.tax_more", "Optional: Federal tax returns or transcripts for the other tax years you listed", "financial_document", sponsor, "workflow",
            "The form says additional years are optional and may help show your ability to maintain sufficient income.")
    inc = calc.income(a)
    if any(r.get("type") in ("employed", "self_employed") for r in inc["sources"]):
        add("i864.income_evidence", "Evidence of your current employment income (for example recent pay records or an employer letter)", "financial_document", sponsor, "workflow")
    if any(r.get("type") == "other" for r in inc["sources"]):
        add("i864.income_other", "Evidence of your other income", "financial_document", sponsor, "workflow")
    if a.get("hi_use") == "yes":
        for i, r in enumerate(calc._recs(a, "inc_people")):
            who = calc._display(r)
            key = (r.get("person_id") or calc._norm(who) or str(i))
            owner = _case_person(submission.case, r) if submission.case is not None else None
            scope = "" if owner is not None else f":{submission.id}"  # an unresolved person is never shared with another affidavit
            add(f"i864.income_person:{key}{scope}", f"Income evidence for {who}", "financial_document", owner, "workflow")
            if a.get("hi_i864a") == "yes":
                add(f"i864.i864a:{key}{scope}", f"Form I-864A completed by {who}", "other", owner, "source",
                    "Item 13 of the form says you are filing the Forms I-864A completed by the people whose income you use.")
    ast = calc.assets(a)
    for owner, label in (("sponsor", "your assets"), ("principal", "the principal immigrant's assets"), ("household", "your household members' assets")):
        if any(r.get("owner") == owner for r in ast["records"]):
            scope = f":{submission.id}" if owner == "household" else ""  # household members' assets belong to THIS affidavit only
            add(f"i864.assets:{owner}{scope}", f"Evidence of {label}", "financial_document", sponsor if owner == "sponsor" else (principal if owner == "principal" else None), "workflow")
    return out


def sync(submission):
    """Requirements of EVERY active I-864 of the case are computed together, so syncing one affidavit never withdraws what another one
    (a different sponsor, e.g. a joint sponsor) still needs. A requirement is per (rule, person); person-less ones are scoped to one affidavit;
    each requirement lists exactly the affidavits that want it."""
    case = submission.case
    if case is None:
        return None
    siblings = [x for x in case.applications if x.form_id == submission.form_id and x.status != "archived" and x.id != submission.id]
    merged = {}
    for sub in [submission] + siblings:
        for spec in desired(sub):
            key = (spec["rule_key"], spec["person"].id if spec.get("person") else None)
            if key in merged:
                merged[key]["applications"] = list({x.id: x for x in merged[key]["applications"] + spec["applications"]}.values())
            else:
                merged[key] = dict(spec, applications=list(spec["applications"]))
    result = vault.sync_requirements(case, SOURCE_KEY, list(merged.values()))
    # an affidavit that no longer wants a shared requirement stops being linked to it
    from app.extensions import db
    from app.models import DocumentRequirement, RequirementApplication

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
