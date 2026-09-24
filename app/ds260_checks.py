"""Consistency prompts for the DS-260 intake. They compare the customer's own answers with each other and with what OG already holds for the same real
Person in other applications (I-130 / I-130A, I-485, I-864, I-751, I-765). Never a legal conclusion and never a silent pick: a difference is shown as
"Review difference" and both values stay in the Person's history. Security & Background answers are only ever mentioned as a generic count-free notice."""

from datetime import date

from app import ds260_calc as calc
from app.intake_records import parse_date, parse_records

_APPLICANT_ROLES = ("applicant", "beneficiary", "conditional_resident", "principal_immigrant", "visa_applicant")
_OTHER_FORMS = ("I-130", "I-485", "I-864", "I-751", "I-765", "I-90", "N-400")


def _n(*parts):
    return " ".join(calc.norm(p) for p in parts if p)


def _names(records):
    return {(_n(r.get("given"), r.get("family")), r.get("dob") or "") for r in records if _n(r.get("given"), r.get("family"))}


def _other_applications(submission):
    """The customer's OTHER applications in which the same real Person is the applicant (any case)."""
    from app import cases as case_svc
    from app import persons as pers
    from app.models import ApplicationRole, FormSubmission

    cp = case_svc.role_person(submission, "visa_applicant")
    if cp is None:
        return []
    owner = pers.owner_of(cp)
    ids = [c.id for c in owner.case_people]
    if not ids:
        return []
    rows = (ApplicationRole.query.join(FormSubmission, FormSubmission.id == ApplicationRole.submission_id)
            .filter(ApplicationRole.person_id.in_(ids), ApplicationRole.role_key.in_(_APPLICANT_ROLES), FormSubmission.id != submission.id, FormSubmission.status != "archived").all())
    seen, out = set(), []
    for r in rows:
        s = r.submission
        if s.id not in seen and s.form.source_form_name in _OTHER_FORMS and s.student_id == submission.student_id:
            seen.add(s.id)
            out.append(s)
    return out


def _roles_in(sub, role_key):
    from app.models import ApplicationRole

    return [(r.person.given_name or "", r.person.family_name or "") for r in ApplicationRole.query.filter_by(submission_id=sub.id, role_key=role_key).all() if r.person is not None]


def run(a, lang="en", today=None, submission=None):
    today = today or date.today()
    en = lang != "es"
    out = []

    def add(group, fields, msg_en, msg_es):
        out.append({"group": group, "fields": fields, "message": msg_en if en else msg_es})

    dob = parse_date(a.get("a_dob"))
    if dob and dob > today:
        add("about", ["a_dob"], "The date of birth is in the future. Please review it.", "La fecha de nacimiento está en el futuro. Revísala.")
    issued, expires = parse_date(a.get("a_doc_issued")), parse_date(a.get("a_doc_expiry"))
    if issued and expires and expires < issued:
        add("passport", ["a_doc_expiry"], "The expiration date is before the issue date. Please review these dates.", "La fecha de vencimiento es anterior a la de emisión. Revisa estas fechas.")
    if expires and expires < today:
        add("passport", ["a_doc_expiry"], "This document has expired. OG will look at what that means for the application with you; this is not a decision about your case.",
            "Este documento ya venció. OG revisará contigo qué significa para la solicitud; esto no es una decisión sobre tu caso.")
    if dob and issued and issued < dob:
        add("passport", ["a_doc_issued"], "The document's issue date is before the date of birth. Please review these dates.", "La fecha de emisión del documento es anterior a la fecha de nacimiento. Revisa estas fechas.")

    # ---- marital status vs the family records
    spouse, prev, kids = parse_records(a.get("s_records")), parse_records(a.get("ps_records")), parse_records(a.get("k_children"))
    marital = a.get("a_marital")
    if marital in ("married", "separated") and not spouse:
        add("family", ["s_records"], "The marital status says married or separated but no current spouse is listed. Please review.", "El estado civil indica casado(a) o separado(a) pero no hay un cónyuge actual en la lista. Revísalo.")
    if marital in ("single",) and (spouse or prev):
        add("family", ["a_marital"], "The marital status says single (never married) but a spouse or previous spouse is listed. Please review both answers.", "El estado civil indica soltero(a) (nunca casado(a)) pero hay un cónyuge o cónyuge anterior en la lista. Revisa ambas respuestas.")
    if marital in ("divorced", "widowed", "annulled") and a.get("ps_has") == "no":
        add("family", ["ps_has"], "The marital status suggests a previous marriage, but you said there were none. Please review.", "El estado civil sugiere un matrimonio anterior, pero dijiste que no hubo ninguno. Revísalo.")
    if a.get("ps_has") == "yes" and not prev:
        add("family", ["ps_has"], "You said there were previous spouses but none are listed. Please review.", "Dijiste que hubo cónyuges anteriores pero no hay ninguno en la lista. Revísalo.")
    if a.get("k_has") == "yes" and not kids:
        add("family", ["k_has"], "You said there are children but none are listed. Please review.", "Dijiste que hay hijos pero no hay ninguno en la lista. Revísalo.")
    if a.get("k_has") == "no" and kids:
        add("family", ["k_has"], "You said there are no children but some are listed. Please review.", "Dijiste que no hay hijos pero hay algunos en la lista. Revísalo.")

    # ---- family dates
    for field, label_en, label_es in (("pf_records", "father", "padre"), ("pm_records", "mother", "madre")):
        for r in parse_records(a.get(field)):
            d = parse_date(r.get("dob"))
            if d and dob and (dob.year - d.year) < 12:
                add("family", [field], f"The {label_en}'s date of birth is less than 12 years before the applicant's. Please review the dates.", f"La fecha de nacimiento del {label_es} es menos de 12 años anterior a la del solicitante. Revisa las fechas.")
            blanks = [n for n in ("family", "given", "dob", "birth_country") if not r.get(n)]
            if blanks:
                add("family", [field], f"Some of the {label_en}'s details are blank. OG enters “Do Not Know” in CEAC only for those CEAC allows; please answer what you can.", f"Faltan algunos datos del {label_es}. OG registra “Do Not Know” en CEAC solo donde CEAC lo permite; responde lo que puedas.")
    for r in spouse:
        m = parse_date(r.get("marriage_date"))
        if m and dob and m < dob:
            add("family", ["s_records"], "The marriage date is before the applicant's date of birth. Please review these dates.", "La fecha del matrimonio es anterior a la fecha de nacimiento del solicitante. Revisa estas fechas.")
        if m and m > today:
            add("family", ["s_records"], "The marriage date is in the future. Please review it.", "La fecha del matrimonio es futura. Revísala.")
    for r in prev:
        m, e = parse_date(r.get("marriage_date")), parse_date(r.get("ended_date"))
        if m and e and e < m:
            add("family", ["ps_records"], "A previous marriage ended before it began. Please review these dates.", "Un matrimonio anterior terminó antes de comenzar. Revisa estas fechas.")
    for r in kids:
        d = parse_date(r.get("dob"))
        if d and dob and d <= dob:
            add("family", ["k_children"], "A child's date of birth is not after the applicant's. Please review the dates.", "La fecha de nacimiento de un hijo(a) no es posterior a la del solicitante. Revisa las fechas.")
        if r.get("immigrating") == "unsure":
            add("family", ["k_children"], "You were not sure whether a child is applying. OG will confirm; each child who applies gets their own DS-260.", "No estabas seguro(a) de si un hijo(a) solicita. OG lo confirmará; cada hijo(a) que solicita tiene su propio DS-260.")
    for r in spouse:
        if r.get("immigrating") == "unsure":
            add("family", ["s_records"], "You were not sure whether your spouse is applying. OG will confirm; a spouse who applies gets their own DS-260.", "No estabas seguro(a) de si tu cónyuge solicita. OG lo confirmará; un cónyuge que solicita tiene su propio DS-260.")

    # ---- present address / permanent U.S. address / green-card mailing
    if a.get("gc_same") == "unsure":
        add("contact", ["gc_same"], "You were not sure where the Green Card should be mailed. OG will confirm with you.", "No estabas seguro(a) de adónde enviar la Green Card. OG lo confirmará contigo.")
    if a.get("t_been") == "no" and a.get("t_visits"):
        add("travel", ["t_been"], "You said the applicant has never been to the U.S. but visits are listed. Please review.", "Dijiste que el solicitante nunca ha estado en EE. UU. pero hay visitas en la lista. Revísalo.")

    # ---- Security & Background: a generic, content-free notice only
    if any(calc.security_counts(a).values()):
        add("security", ["sec_med_1"], "OG will go through some of your answers in Security & Background with you privately before anything is entered anywhere. This is not a decision about your case.",
            "OG revisará contigo en privado algunas de tus respuestas de Seguridad y antecedentes antes de ingresar algo en cualquier lugar. Esto no es una decisión sobre tu caso.")

    if submission is not None:
        out.extend(_cross_form(submission, a, en, spouse, kids))
    return out


def _cross_form(submission, a, en, spouse, kids):
    """What other OG applications for the same Person say, compared with this DS-260 (never picks a side)."""
    from app import cases as case_svc
    from app import persons as pers
    from app.case_types import FACTS
    from app.models import Person

    out = []

    def add(group, fields, msg_en, msg_es):
        out.append({"group": group, "fields": fields, "message": msg_en if en else msg_es})

    cp = case_svc.role_person(submission, "visa_applicant")
    if cp is not None:
        owner = pers.owner_of(cp)
        field_of = {"date_of_birth": "a_dob", "birth_country": "a_birth_country", "birth_city": "a_birth_city", "sex": "a_sex", "nationality": "a_nationality", "family_name": "a_family", "given_name": "a_given"}
        for fact in pers.open_conflicts(person=owner):
            if fact.fact_key in field_of:
                label = FACTS[fact.fact_key]["en" if en else "es"]
                add("about", [field_of[fact.fact_key]], f"We found different information for “{label}” in a previous OG application. Review the difference: OG does not choose one for you.",
                    f"Encontramos información diferente en “{label}” en una solicitud anterior de OG. Revisa la diferencia: OG no elige una por ti.")
    others = _other_applications(submission)
    for label_en, label_es, role, records, field in (("children", "hijos", "child", kids, "k_children"), ("parents", "padres", "parent", parse_records(a.get("pf_records")) + parse_records(a.get("pm_records")), "pf_records"),
                                                      ("spouse", "cónyuge", "spouse", spouse, "s_records")):
        here = {n for n, _d in _names(records)}
        for sub in others:
            for given, family in _roles_in(sub, role):
                name = _n(given, family)
                if name and name not in here:
                    shown = f"{given} {family}".strip()
                    add("family", [field], f"Another OG application ({sub.form.source_form_name}) lists {shown} as a {label_en[:-1] if label_en.endswith('s') else label_en} that is not in this DS-260. Please review.",
                        f"Otra solicitud de OG ({sub.form.source_form_name}) lista a {shown} como {label_es} que no aparece en este DS-260. Revísalo.")
    # a typed family member who looks like a Person the customer already has
    known = {}
    for p in Person.query.filter_by(customer_id=submission.student_id).all():
        known.setdefault(_n(p.given_name, p.family_name), []).append(p)
    for field in ("pf_records", "pm_records", "s_records", "ps_records", "k_children"):
        for r in parse_records(a.get(field)):
            if not r.get("person_id") and known.get(_n(r.get("given"), r.get("family"))):
                add("family", [field], f"{r.get('given', '')} {r.get('family', '')} looks like someone already in your OG cases. Choose them from the list so their information is reused instead of typed again.".strip(),
                    f"{r.get('given', '')} {r.get('family', '')} parece alguien que ya está en tus casos de OG. Elígelo(a) de la lista para reutilizar su información en lugar de escribirla otra vez.".strip())
    return out


run.wants_submission = True
