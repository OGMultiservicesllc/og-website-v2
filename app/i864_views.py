"""Customer-facing summaries for the I-864 intake (household, income, assets, who/where) and the person-record normalization.

All output is calculation and consistency information — never a statement that the household, income or assets are (in)sufficient.
"""

import html
import json

from flask import url_for

from app import cases as case_svc
from app import persons as pers
from app import i864_calc as calc
from app.case_types import role_label
from app.models import ApplicationRole, Person

PERSON_RECORD_FIELDS = ("i_family", "h_people", "inc_people")


# ------------------------------------------------------------------ answers with the real-Person ids added (for identity)
def answers(submission):
    a = case_svc.answers_by_name(submission)
    for key, role in (("_sponsor_pid", "sponsor"), ("_principal_pid", "principal_immigrant")):
        cp = case_svc.role_person(submission, role)
        if cp is not None:
            a[key] = pers.owner_of(cp).id
    return a


# ------------------------------------------------------------------ link records to real Persons (never trusted from the form on its own)
def fill_from_people(records, customer_id, extra=None):
    """A record may carry `person_id` (picked from the customer's OWN people). Verify it, drop it otherwise, and copy what the Person already has
    into BLANK name / date-of-birth / ID fields so the record reads as that person. Returns True when anything changed. Nothing is saved here."""
    changed = False
    for rec in records:
        pid = rec.get("person_id")
        if not pid:
            continue
        try:
            person = Person.query.filter_by(id=int(pid), customer_id=customer_id).first()
        except (TypeError, ValueError):
            person = None
        if person is None:
            rec.pop("person_id", None)
            changed = True
            continue
        facts = {f.fact_key: pers.fact_value(f) for f in person.facts}
        fill = {"given": facts.get("given_name") or person.given_name, "family": facts.get("family_name") or person.family_name,
                "middle": facts.get("middle_name"), "dob": facts.get("date_of_birth"), "a_number": facts.get("a_number"), "uscis": facts.get("uscis_account_number")}
        for rec_key, fact_key in (extra or {}).items():  # a record type may take more facts from the Person (DS-260: place of birth)
            fill[rec_key] = facts.get(fact_key)
        for k, v in fill.items():
            if v and not rec.get(k) and isinstance(v, str):
                rec[k] = v
                changed = True
    return changed


def normalize_records(form, submission, names=PERSON_RECORD_FIELDS):
    """A record may carry `person_id` (chosen in the record builder from the customer's OWN people). Verify it belongs to this customer,
    drop it otherwise, and copy the stable facts the Person already has into blank fields so the customer can confirm or edit them."""
    from app.intake_records import parse_records
    from app.intake_shared import _set

    fields = {f.internal_name: f for f in form.all_fields}
    stored = {v.field_internal_name: v.value_text for v in submission.values}
    for name in names:
        if name not in fields or not stored.get(name):
            continue
        recs = parse_records(stored[name])
        from app.intake_records import field_config

        changed = fill_from_people(recs, submission.student_id, (field_config(fields[name]) or {}).get("fill_extra"))
        if changed:
            _set(form, submission, fields, name, recs)


def person_options(student):
    """[(value, en, es)] the customer's own people, for the "someone I already have" selector in the record builder."""
    out = []
    for p in Person.query.filter_by(customer_id=student.id).order_by(Person.is_self.desc(), Person.id).all():
        roles = sorted({r.role_key for cp in p.case_people for r in ApplicationRole.query.filter_by(person_id=cp.id).all()})
        hint = ", ".join(role_label(r, "en") for r in roles)
        hint_es = ", ".join(role_label(r, "es") for r in roles)
        out.append((str(p.id), f"{p.full_name}{' (you)' if p.is_self else ''}{' — ' + hint if hint else ''}", f"{p.full_name}{' (tú)' if p.is_self else ''}{' — ' + hint_es if hint_es else ''}"))
    return out


# ------------------------------------------------------------------ html
def _card(inner, tone="accent"):
    return f'<div class="rounded-xl border border-{tone}-200 bg-mist-50 px-4 py-3">{inner}</div>'


def _issues_html(issues, lang):
    shown = [i for i in issues if i["level"] in ("warn", "error", "info")]
    if not shown:
        return ""
    lis = "".join(f'<li class="text-[13px] {"text-amber-800" if i["level"] != "info" else "text-slate-600"} break-words">{html.escape(calc.issue_message(i, lang))}</li>' for i in shown)
    return f'<ul class="mt-3 space-y-1 list-disc pl-4">{lis}</ul>'


def context_html(submission, lang="en"):
    en = lang == "en"
    case = submission.case
    sponsor, principal = case_svc.role_person(submission, "sponsor"), case_svc.role_person(submission, "principal_immigrant")
    if case is None or sponsor is None or principal is None:
        return ""
    rows = [
        f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape("Sponsor" if en else "Patrocinador")}</p>'
        f'<p class="text-[17px] font-extrabold tracking-tight text-brand-800 break-words">{html.escape(sponsor.full_name)}</p>',
        f'<p class="mt-2 text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape("Principal immigrant" if en else "Inmigrante principal")}</p>'
        f'<p class="text-[17px] font-extrabold tracking-tight text-brand-800 break-words">{html.escape(principal.full_name)}</p>',
        f'<p class="mt-2 text-[13px] text-slate-600">{html.escape("Case" if en else "Caso")} <span class="font-mono font-semibold">{html.escape(case.case_number or "")}</span></p>']
    others = [s for s in case.applications if s.id != submission.id]
    if others:
        from app.intake_engine import status_label

        items = "".join(f'<li class="text-[13px] text-slate-600 break-words">{html.escape("Form " + (s.form.source_form_name or s.form.name_admin))} &middot; <span class="font-mono">{html.escape(s.code)}</span> &middot; {html.escape(status_label(s, lang))}</li>' for s in others)
        rows.append(f'<p class="mt-3 text-xs font-bold uppercase tracking-wider text-slate-500">{html.escape("Also in this case" if en else "También en este caso")}</p><ul class="mt-1 space-y-0.5">{items}</ul>')
    return _card("".join(rows))


def household_html(submission, lang="en"):
    en = lang == "en"
    a = answers(submission)
    hh = calc.household(a)
    rows = []
    for r in hh["rows"]:
        label = calc.CATEGORY_LABELS.get(r["category"], (r["category"], r["category"]))[0 if en else 1]
        if r["counted"]:
            state = ('<span class="text-emerald-700 font-semibold">' + html.escape("Included" if en else "Incluido") + "</span>")
        else:
            why = calc.CATEGORY_LABELS.get(r.get("reason"), (str(r.get("reason") or ""), str(r.get("reason") or "")))[0 if en else 1]
            state = ('<span class="text-slate-500">' + html.escape(("Not counted again — already counted as " if en else "No se cuenta de nuevo — ya contado como ") + why) + "</span>")
        rows.append(f'<li class="py-2 first:pt-0 last:pb-0"><p class="text-[11px] font-bold uppercase tracking-wide text-slate-400">{html.escape(label)}</p>'
                    f'<p class="text-[15px] font-semibold text-brand-800 break-words">{html.escape(r["name"])}</p><p class="text-[12px]">{state}</p></li>')
    size = (f'<p class="mt-3 text-xs font-bold uppercase tracking-wider text-slate-500">{html.escape("Calculated household size" if en else "Tamaño del hogar calculado")}</p>'
            f'<p class="text-3xl font-extrabold text-brand-800">{hh["size"]}</p>'
            f'<p class="text-[12px] text-slate-500">{html.escape("This is arithmetic from the people you listed. OG reviews what it means for your case." if en else "Es aritmética con las personas que listaste. OG revisa lo que significa para tu caso.")}</p>')
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape("Your household" if en else "Tu hogar")}</p>'
                 f'<ul class="mt-2 divide-y divide-mist-200">{"".join(rows)}</ul>{size}{_issues_html(hh["issues"], lang)}')


def income_html(submission, lang="en"):
    en = lang == "en"
    a = answers(submission)
    inc = calc.income(a)
    lines = []
    for r in inc["sources"]:
        title = r.get("name") or r.get("description") or (("Self-employment" if en else "Trabajo por cuenta propia") if r.get("type") == "self_employed" else "—")
        lines.append(f'<li class="flex items-baseline justify-between gap-3 py-1.5"><span class="min-w-0 break-words text-[14px] text-slate-700">{html.escape(title)}</span>'
                     f'<span class="shrink-0 text-[14px] font-semibold text-brand-800">{html.escape(calc.usd(calc.parse_money(r.get("income")) or 0))}</span></li>')
    for r in calc._recs(a, "inc_people"):
        lines.append(f'<li class="flex items-baseline justify-between gap-3 py-1.5"><span class="min-w-0 break-words text-[14px] text-slate-700">{html.escape(calc._display(r))} <span class="text-slate-400">({html.escape(r.get("relationship") or "")})</span></span>'
                     f'<span class="shrink-0 text-[14px] font-semibold text-brand-800">{html.escape(calc.usd(calc.parse_money(r.get("income")) or 0))}</span></li>')
    body = (f'<ul class="divide-y divide-mist-200">{"".join(lines)}</ul>' if lines else f'<p class="text-[13px] text-slate-500">{html.escape("No income added yet." if en else "Aún no hay ingresos agregados.")}</p>')
    tot = (f'<div class="mt-3 grid grid-cols-2 gap-3"><div><p class="text-[11px] font-bold uppercase tracking-wide text-slate-400">{html.escape("Your individual annual income" if en else "Tu ingreso anual individual")}</p>'
           f'<p class="text-xl font-extrabold text-brand-800">{html.escape(calc.usd(inc["total_individual"]))}</p></div>'
           f'<div><p class="text-[11px] font-bold uppercase tracking-wide text-slate-400">{html.escape("Current annual household income" if en else "Ingreso anual actual del hogar")}</p>'
           f'<p class="text-xl font-extrabold text-brand-800">{html.escape(calc.usd(inc["total_household"]))}</p></div></div>')
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape("Income totals" if en else "Totales de ingreso")}</p>{body}{tot}{_issues_html(inc["issues"], lang)}')


def assets_html(submission, lang="en"):
    en = lang == "en"
    a = answers(submission)
    ast = calc.assets(a)
    it = ast["items"]
    labels = [(4, "Your assets" if en else "Tus activos"), (5, "Household members' assets" if en else "Activos de los miembros del hogar"),
              (9, "Principal immigrant's assets" if en else "Activos del inmigrante principal"), (10, "Total value of assets" if en else "Valor total de los activos")]
    rows = "".join(f'<div class="flex items-baseline justify-between gap-3 py-1.5"><span class="text-[14px] text-slate-700">{html.escape(l)}</span><span class="text-[14px] font-semibold text-brand-800">{html.escape(calc.usd(it[i]))}</span></div>' for i, l in labels)
    note = html.escape("This is a total of what you entered. OG reviews whether assets are used and how." if en else "Es un total de lo que ingresaste. OG revisa si se usan los activos y cómo.")
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape("Asset totals" if en else "Totales de activos")}</p><div class="mt-1 divide-y divide-mist-200">{rows}</div>'
                 f'<p class="mt-2 text-[12px] text-slate-500">{note}</p>{_issues_html(ast["issues"], lang)}')


# ------------------------------------------------------------------ Admin
BASIS_LABELS = {
    "1a": "Petitioner", "1b": "Alien worker petitioner", "1c": "Business owner (5% or more) of the petitioning business", "1d": "Only joint sponsor",
    "1e": "First or second of two joint sponsors", "1f": "Substitute sponsor (original petitioner deceased)", "unsure": "Customer was not sure — OG to review",
}
STATUS_LABELS = {"usc": "U.S. citizen", "national": "U.S. national", "lpr": "Lawful permanent resident"}


def admin_summary(submission):
    """Everything OG reviews on one I-864, computed from the application's own answers. Read-only; no sufficiency or legal conclusions."""
    from app import i864_checks

    a = answers(submission)
    sponsor_cp, principal_cp = case_svc.role_person(submission, "sponsor"), case_svc.role_person(submission, "principal_immigrant")
    sponsor = pers.owner_of(sponsor_cp) if sponsor_cp is not None else None
    principal = pers.owner_of(principal_cp) if principal_cp is not None else None
    hh, inc, tx, ast = calc.household(a), calc.income(a), calc.tax(a), calc.assets(a)
    linked = []
    for name, label in (("i_family", "Sponsored family member"), ("h_people", "Household member"), ("inc_people", "Income provided by")):
        for rec in calc._recs(a, name):
            pid = rec.get("person_id")
            person = Person.query.filter_by(id=int(pid), customer_id=submission.student_id).first() if str(pid or "").isdigit() else None
            linked.append({"label": label, "name": calc._display(rec), "person": person, "relationship": rec.get("relationship") or calc.CATEGORY_LABELS.get(rec.get("category"), ("", ""))[0]})
    role_keys = sorted({r.role_key for r in ApplicationRole.query.filter_by(submission_id=submission.id).all()})
    return {
        "sponsor": sponsor, "principal": principal, "sponsor_name": (sponsor.full_name if sponsor else None), "principal_name": (principal.full_name if principal else None),
        "basis": BASIS_LABELS.get(a.get("b_basis"), a.get("b_basis") or "—"), "status": STATUS_LABELS.get(a.get("s_status"), a.get("s_status") or "—"),
        "role_keys": [role_label(r, "en") for r in role_keys], "joint": any(rk in ("joint_sponsor", "substitute_sponsor") for rk in role_keys),
        "sponsoring_principal": a.get("i_principal") == "yes", "linked": linked,
        "household": hh, "income": inc, "tax": tx, "assets": ast, "flags": [i["message"] for i in i864_checks.run(a, "en")],
        "usd": calc.usd, "money": lambda v: calc.usd(calc.parse_money(v) or 0),
    }
