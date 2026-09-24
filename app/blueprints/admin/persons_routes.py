"""Admin: the REAL person above CasePerson.

One Person (a real human inside one customer's data) may take part in many cases and applications; its stable facts follow it across
cases. This view shows the whole picture: cases, application roles, shared facts with every source (claims), conflicts (open and resolved)
and an explicit way to declare that two people are the same human. Sensitive values stay masked; a Person is never linked by name alone.
"""

from flask import abort, flash, redirect, render_template, request, url_for

from app import cases as case_svc
from app import persons as pers
from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.case_types import CASE_TYPES, ROLE_LABELS, conflict_capable, type_title
from app.extensions import db
from app.models import ApplicationRole, CasePerson, Person, PersonFact, PersonFactEvent, Student


@admin_bp.route("/persons")
@admin_required
def person_list():
    q = request.args.get("q", "").strip()
    only = request.args.get("only", "")
    query = Person.query.join(Student, Student.id == Person.customer_id)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Person.given_name.ilike(like), Person.family_name.ilike(like), Student.name.ilike(like), Student.email.ilike(like)))
    rows = []
    for p in query.order_by(Person.customer_id, Person.is_self.desc(), Person.id).all():
        conflicts = pers.open_conflicts(person=p)
        if only == "conflicts" and not conflicts:
            continue
        rows.append({"p": p, "cases": len(p.case_people), "facts": len(p.facts), "conflicts": len(conflicts)})
    return render_template("admin/persons_list.html", rows=rows, q=q, only=only)


@admin_bp.route("/persons/<int:person_id>")
@admin_required
def person_detail(person_id):
    person = Person.query.get_or_404(person_id)
    participation = []
    for cp in person.case_people:
        roles = ApplicationRole.query.filter_by(person_id=cp.id).order_by(ApplicationRole.id).all()
        participation.append({"cp": cp, "case": cp.case, "roles": [(r.submission, ROLE_LABELS.get(r.role_key, ROLE_LABELS["other"])["en"]) for r in roles]})
    facts = case_svc.facts_for_review(person, lang="en", reveal=False)
    conflicts = [r for r in facts if r["status"] == "needs_review" and conflict_capable(r["key"])]
    resolved = (PersonFactEvent.query.join(PersonFact, PersonFact.id == PersonFactEvent.fact_id)
                .filter(PersonFact.real_person_id == person.id, PersonFactEvent.kind == "resolved").order_by(PersonFactEvent.id.desc()).all())
    others = Person.query.filter(Person.customer_id == person.customer_id, Person.id != person.id).order_by(Person.id).all()
    # suggestions only: same A-Number (strong) or same name + date of birth; nothing is linked until OG clicks
    mine = {f.fact_key: pers.fact_value(f) for f in person.facts}
    suggestions = []
    for o in others:
        theirs = {f.fact_key: pers.fact_value(f) for f in o.facts}
        why = None
        if mine.get("a_number") and theirs.get("a_number") and case_svc._norm(mine["a_number"]) == case_svc._norm(theirs["a_number"]):
            why = "same A-Number"
        elif (case_svc._norm(person.given_name) == case_svc._norm(o.given_name) and case_svc._norm(person.family_name) == case_svc._norm(o.family_name)
              and mine.get("date_of_birth") and mine.get("date_of_birth") == theirs.get("date_of_birth")):
            why = "same name and date of birth"
        if why and not (person.is_self and o.is_self):
            suggestions.append((o, why))
    return render_template("admin/person_detail.html", person=person, participation=participation, facts=facts, conflicts=conflicts, resolved=resolved,
                           others=others, suggestions=suggestions, types=CASE_TYPES, type_title=type_title)


@admin_bp.route("/persons/<int:person_id>/merge", methods=["POST"])
@admin_required
def person_merge(person_id):
    """Explicitly declare that another Person of the SAME customer is this human. Facts merge; any difference becomes a conflict."""
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    person = Person.query.get_or_404(person_id)
    other = Person.query.filter_by(id=request.form.get("other_id", type=int) or 0, customer_id=person.customer_id).first_or_404()
    if other.id == person.id:
        abort(400)
    try:
        if other.is_self and not person.is_self:  # the customer's own person is always the survivor
            person, other = other, person
        for cp in list(other.case_people):
            pers.link_case_person(cp, person)
        flash("The two people were linked. Any different values are now conflicts for the customer to resolve.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    return redirect(url_for("admin.person_detail", person_id=person.id))
