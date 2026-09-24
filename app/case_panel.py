"""What Admin sees next to an application that lives in a case: the case, the people and roles of THIS application, the other
applications of the case (and how they relate), the documents this application needs, and which shared person facts it used
(confirmed / changed / needing review). Read-only; nothing here decides eligibility."""

from app import cases as case_svc
from app.case_types import FACTS, role_label
from app.models import ApplicationRole, PersonFactUse, RequirementApplication, DocumentRequirement
from app.intake_engine import status_label


def panel(submission):
    case = submission.case
    if case is None:
        return None
    roles = []
    for r in ApplicationRole.query.filter_by(submission_id=submission.id).order_by(ApplicationRole.id).all():
        roles.append({"person": r.person, "role": role_label(r.role_key, "en"), "key": r.role_key})
    related = [{"submission": s, "how": how, "status": status_label(s, "en")} for s, how in case_svc.related_applications(submission)]
    req_ids = [x.requirement_id for x in RequirementApplication.query.filter_by(submission_id=submission.id).all()]
    reqs = [r for r in DocumentRequirement.query.filter(DocumentRequirement.id.in_(req_ids)).order_by(DocumentRequirement.id).all() if r.withdrawn_at is None] if req_ids else []
    shared = []
    for use in PersonFactUse.query.filter_by(submission_id=submission.id).all():
        fact = use.fact
        if fact is None or fact.fact_key not in FACTS:
            continue
        if fact.needs_review:
            state = "needs review"
        elif fact.last_confirmed_at and fact.confirmed_by == submission.code:
            state = "confirmed here"
        elif fact.last_confirmed_at:
            state = "confirmed"
        else:
            state = "not yet confirmed"
        shared.append({"person": fact.owner.full_name if fact.owner is not None else "", "label": FACTS[fact.fact_key]["en"], "state": state,
                       "source": (fact.source_form or "") + (f" · {fact.source_submission.code}" if fact.source_submission else "")})
    seen, unique = set(), []
    for x in sorted(shared, key=lambda s: (s["person"], s["label"])):
        key = (x["person"], x["label"])
        if key not in seen:
            seen.add(key)
            unique.append(x)
    return {"case": case, "roles": roles, "related": related, "requirements": reqs, "shared": unique}
