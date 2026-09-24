"""Form I-864 arithmetic and consistency checks — pure functions over an application's answers.

Everything here is CALCULATION and CONSISTENCY, never a legal conclusion: no function says a household is large/small enough, that
income or assets are sufficient, or that a joint sponsor is (or is not) needed. Poverty-guideline comparison (Form I-864P) is
deliberately NOT implemented: the platform has no reliable, versioned threshold source, and inventing values would be wrong.

Household size (Part 5) follows the official arithmetic: Item 1 sponsored immigrants, Item 2 yourself (1), Items 3-7 persons NOT
sponsored — each of which says "enter 0 if you already counted them in Item 1". A real person is counted ONCE: a person already
counted (as the sponsor, as a sponsored immigrant, or in an earlier category) is never counted again, and the reason is reported.

Financial values belong to THIS affidavit (application data), never to the global Person facts.
"""

import re
from datetime import date

from app.intake_records import parse_date, parse_money

# precedence when the same person is offered in two household categories
_CATEGORY_ORDER = ("spouse", "dependent_child", "other_dependent", "i864a_member", "previous_sponsored")
_ITEM_OF = {"spouse": 3, "dependent_child": 4, "other_dependent": 5, "previous_sponsored": 6, "i864a_member": 7}

CATEGORY_LABELS = {
    "sponsored": ("Sponsored immigrant", "Inmigrante patrocinado"), "sponsor": ("Sponsor (you)", "Patrocinador (tú)"),
    "spouse": ("Spouse", "Cónyuge"), "dependent_child": ("Dependent child", "Hijo(a) dependiente"), "other_dependent": ("Other dependent", "Otro dependiente"),
    "previous_sponsored": ("Previously sponsored", "Patrocinado(a) anteriormente"), "i864a_member": ("Combining income (Form I-864A)", "Combina ingresos (Formulario I-864A)"),
}


def _norm(text):
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def _recs(a, name):
    v = a.get(name)
    return [r for r in v if isinstance(r, dict)] if isinstance(v, list) else []


def person_key(rec=None, *, given=None, family=None, dob=None, person_id=None):
    """Identity used to avoid counting a person twice: (link, name+date-of-birth). A person is the same when the explicit Person link
    is the same, or the normalized name is the same and the dates of birth do not contradict each other."""
    if rec is not None:
        person_id, given, family, dob = rec.get("person_id"), rec.get("given"), rec.get("family"), rec.get("dob")
    name = _norm(given) + _norm(family)
    if not person_id and not name:
        return None
    return (str(person_id) if person_id else "", name, str(dob or ""))


def _display(rec):
    return " ".join(x for x in (rec.get("given"), rec.get("family")) if x) or ("(linked person)" if rec.get("person_id") else "(unnamed)")


def sponsor_key(a):
    return person_key(given=a.get("s_given"), family=a.get("s_family"), dob=a.get("s_dob"), person_id=a.get("_sponsor_pid"))


def principal_key(a):
    return person_key(given=a.get("p_given"), family=a.get("p_family"), dob=a.get("p_dob"), person_id=a.get("_principal_pid"))


def _same_person(k1, k2):
    if not k1 or not k2:
        return False
    if k1[0] and k1[0] == k2[0]:
        return True
    if k1[1] and k1[1] == k2[1]:
        return not (k1[2] and k2[2] and k1[2] != k2[2])
    return False


# ------------------------------------------------------------------ Part 4 / Part 5: who is sponsored, household size
def sponsored_people(a):
    """[{key, name, source}] the immigrants sponsored on this affidavit: the principal immigrant (Part 4 Item 1 = Yes) + Part 4 Items 4-7 (+ Part 11)."""
    out = []
    if a.get("i_principal") == "yes":
        name = " ".join(x for x in (a.get("p_given"), a.get("p_family")) if x) or "(principal immigrant)"
        out.append({"key": principal_key(a), "name": name, "source": "principal"})
    if a.get("i_family_q") == "yes" or a.get("i_principal") == "no":
        for r in _recs(a, "i_family"):
            out.append({"key": person_key(r), "name": _display(r), "source": "family"})
    return out


def household(a):
    """{items: {1..8}, size, rows: [...], issues: [...]} — the Part 5 arithmetic with double-counting prevention."""
    issues, rows = [], []
    seen = []  # [(key, label)]

    def counted_as(key):
        for k, label in seen:
            if _same_person(key, k):
                return label
        return None

    sponsor_k = sponsor_key(a)
    sponsor_name = " ".join(x for x in (a.get("s_given"), a.get("s_family")) if x) or "Sponsor"
    if sponsor_k:
        seen.append((sponsor_k, "sponsor"))
    sponsored = sponsored_people(a)
    n_sponsored = 0
    for p in sponsored:
        prior = counted_as(p["key"]) if p["key"] else None
        if prior:
            issues.append({"level": "error", "code": "sponsored_dup", "name": p["name"], "as": prior})
            rows.append({"name": p["name"], "category": "sponsored", "counted": False, "reason": prior})
            continue
        n_sponsored += 1
        if p["key"]:
            seen.append((p["key"], "sponsored"))
        rows.append({"name": p["name"], "category": "sponsored", "counted": True, "item": 1})
    items = {1: n_sponsored, 2: 1, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}
    rows.insert(0, {"name": sponsor_name, "category": "sponsor", "counted": True, "item": 2})

    married = a.get("h_married") == "yes"
    spouse_where = a.get("h_spouse")  # principal | sponsored | other
    people = _recs(a, "h_people")
    ordered = sorted(people, key=lambda r: _CATEGORY_ORDER.index(r.get("category")) if r.get("category") in _CATEGORY_ORDER else 99)
    spouse_records = [r for r in people if r.get("category") == "spouse"]
    if married and spouse_where in ("principal", "sponsored"):
        # already counted in Item 1: Item 3 is 0
        if spouse_where == "principal" and a.get("i_principal") != "yes":
            issues.append({"level": "warn", "code": "spouse_principal_not_sponsored"})
        if spouse_where == "sponsored" and not any(p["source"] == "family" for p in sponsored):
            issues.append({"level": "warn", "code": "spouse_sponsored_missing"})
    for r in ordered:
        cat = r.get("category")
        if cat not in _ITEM_OF:
            continue
        key = person_key(r)
        prior = counted_as(key) if key else None
        name = _display(r)
        if prior:
            rows.append({"name": name, "category": cat, "counted": False, "reason": prior})
            issues.append({"level": "info", "code": "already_counted", "name": name, "as": prior, "cat": cat})
            continue
        if cat == "spouse" and (not married or spouse_where in ("principal", "sponsored")):
            rows.append({"name": name, "category": cat, "counted": False, "reason": "spouse_item1" if married else "not_married"})
            issues.append({"level": "warn", "code": "spouse_conflict", "name": name})
            continue
        if cat == "spouse" and items[3] >= 1:
            rows.append({"name": name, "category": cat, "counted": False, "reason": "second_spouse"})
            issues.append({"level": "warn", "code": "two_spouses", "name": name})
            continue
        items[_ITEM_OF[cat]] += 1
        if key:
            seen.append((key, cat))
        rows.append({"name": name, "category": cat, "counted": True, "item": _ITEM_OF[cat]})
    if married and spouse_where == "other" and not spouse_records:
        issues.append({"level": "error", "code": "spouse_missing"})
    if married and spouse_where == "other" and items[3] == 0 and spouse_records:
        pass
    items[8] = sum(items[i] for i in range(1, 8))
    # income of people who are not counted in the household
    for r in _recs(a, "inc_people"):
        key = person_key(r)
        if key and not counted_as(key):
            issues.append({"level": "warn", "code": "income_not_counted", "name": _display(r)})
    return {"items": items, "size": items[8], "rows": rows, "issues": issues}


# ------------------------------------------------------------------ Part 6: current income
def income(a):
    """{sources, total_individual (Item 7), persons, total_household (Item 12), issues}. Item 7 is the sum of the sources entered."""
    issues, sources = [], _recs(a, "e_sources")
    total = 0.0
    bad = False
    for i, r in enumerate(sources):
        m = parse_money(r.get("income"))
        if m is None:
            bad = True
        else:
            total += m
    persons, persons_total, seen_income = [], 0.0, []
    for r in _recs(a, "inc_people"):
        key = person_key(r)
        if key and any(_same_person(key, k) for k in seen_income):  # one person's income is used once
            issues.append({"level": "warn", "code": "income_person_dup", "name": _display(r)})
            continue
        if key:
            seen_income.append(key)
        persons.append(r)
        m = parse_money(r.get("income"))
        if m is None:
            bad = True
        else:
            persons_total += m
    status = a.get("e_status") if isinstance(a.get("e_status"), list) else ([a.get("e_status")] if a.get("e_status") else [])
    emp = [r for r in sources if r.get("type") == "employed"]
    selfe = [r for r in sources if r.get("type") == "self_employed"]
    if "employed" in status and not emp:
        issues.append({"level": "warn", "code": "employed_no_source"})
    if "self_employed" in status and not selfe:
        issues.append({"level": "warn", "code": "selfemployed_no_source"})
    if emp and "employed" not in status:
        issues.append({"level": "warn", "code": "source_no_status", "what": "employed"})
    if selfe and "self_employed" not in status:
        issues.append({"level": "warn", "code": "source_no_status", "what": "self_employed"})
    if a.get("e_has_income") == "no" and sources:
        issues.append({"level": "warn", "code": "no_income_but_sources"})
    if "retired" in status and not parse_date(a.get("e_retired_since")):
        issues.append({"level": "error", "code": "retired_since_missing"})
    if "unemployed" in status and not parse_date(a.get("e_unemployed_since")):
        issues.append({"level": "error", "code": "unemployed_since_missing"})
    for name in ("e_retired_since", "e_unemployed_since"):
        d = parse_date(a.get(name))
        if d and d > date.today():
            issues.append({"level": "warn", "code": "date_future", "field": name})
    if bad:
        issues.append({"level": "error", "code": "bad_amount"})
    return {"sources": sources, "employers": [r.get("name") for r in emp], "employed_as": (emp[0].get("occupation") if emp else None),
            "self_employed_as": (selfe[0].get("occupation") if selfe else None), "total_individual": total, "persons_total": persons_total,
            "total_household": total + persons_total, "issues": issues, "status": status}


# ------------------------------------------------------------------ Part 6: tax history
def tax(a):
    """[{item: '16.a'|'16.b'|'16.c'|None, year, kind, income}] most recent first, plus issues. Years are never hard-coded."""
    recs = sorted(_recs(a, "t_years"), key=lambda r: str(r.get("year") or ""), reverse=True)
    rows = []
    for i, r in enumerate(recs):
        rows.append({"item": "16." + "abc"[i] if i < 3 else None, "year": r.get("year"), "kind": r.get("income_kind"), "income": r.get("income")})
    issues = []
    years = [int(r["year"]) for r in rows if str(r.get("year") or "").isdigit()]
    if a.get("t_three") == "yes" and len(rows) < 3:
        issues.append({"level": "warn", "code": "three_years_missing"})
    if a.get("t_norequire") == "yes" and rows and rows[0].get("kind") != "na":
        issues.append({"level": "warn", "code": "norequire_vs_income"})
    if a.get("t_norequire") != "yes" and not rows:
        issues.append({"level": "error", "code": "no_tax_year"})
    if len(years) > 1 and any(years[i] - years[i + 1] != 1 for i in range(len(years) - 1)):
        issues.append({"level": "info", "code": "years_not_consecutive"})
    if len(rows) > 3:
        issues.append({"level": "info", "code": "more_than_three"})
    return {"rows": rows, "issues": issues}


# ------------------------------------------------------------------ Part 7: assets
def assets(a):
    """Items 1-10 of Part 7 from the asset records (no sufficiency conclusion)."""
    recs = _recs(a, "a_assets")
    by = {("sponsor", "cash"): 0.0, ("sponsor", "real_estate"): 0.0, ("sponsor", "investments"): 0.0, ("household", "*"): 0.0,
          ("principal", "cash"): 0.0, ("principal", "real_estate"): 0.0, ("principal", "investments"): 0.0}
    issues = []
    for r in recs:
        m = parse_money(r.get("value"))
        if m is None:
            issues.append({"level": "error", "code": "bad_amount"})
            continue
        owner, kind = r.get("owner"), r.get("kind")
        if owner == "household":
            by[("household", "*")] += m
        elif (owner, kind) in by:
            by[(owner, kind)] += m
    it = {1: by[("sponsor", "cash")], 2: by[("sponsor", "real_estate")], 3: by[("sponsor", "investments")]}
    it[4] = it[1] + it[2] + it[3]
    it[5] = by[("household", "*")]
    it[6], it[7], it[8] = by[("principal", "cash")], by[("principal", "real_estate")], by[("principal", "investments")]
    it[9] = it[6] + it[7] + it[8]
    it[10] = it[4] + it[5] + it[9]
    if it[9] and a.get("i_principal") != "yes":
        issues.append({"level": "warn", "code": "principal_assets_not_sponsored"})
    if any(r.get("owner") == "household" for r in recs) and a.get("hi_use") != "yes":
        issues.append({"level": "warn", "code": "household_assets_without_income"})
    if recs and a.get("a_use") == "no":
        issues.append({"level": "warn", "code": "assets_but_not_used"})
    if not recs and a.get("a_use") == "yes":
        issues.append({"level": "warn", "code": "assets_used_none"})
    return {"items": it, "records": recs, "issues": issues}


def money_text(value):
    return f"{value:.2f}"


def usd(value):
    return f"${value:,.2f}".replace(".00", "")


# ------------------------------------------------------------------ what is written back as calculated answers
CALC_FIELDS = (
    [f"c_hh_{i}" for i in range(1, 9)] + ["c_inc_7", "c_inc_12"] + [f"c_ast_{i}" for i in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)]
)


def calculated(a):
    """{internal_name: text} for every calculated field (household items, Part 6 totals, Part 7 totals)."""
    out = {}
    hh = household(a)
    for i in range(1, 9):
        out[f"c_hh_{i}"] = str(hh["items"][i])
    inc = income(a)
    out["c_inc_7"] = money_text(inc["total_individual"])
    out["c_inc_12"] = money_text(inc["total_household"])
    ast = assets(a)
    for i in range(1, 11):
        out[f"c_ast_{i}"] = money_text(ast["items"][i])
    return out


ISSUE_TEXT = {
    "sponsored_dup": ("{name} is listed more than once as a sponsored immigrant (already counted as {as}). Please review.", "{name} aparece más de una vez como inmigrante patrocinado (ya contado como {as}). Revísalo."),
    "already_counted": ("{name} is already counted as {as}, so they were not counted again.", "{name} ya está contado como {as}, por eso no se contó de nuevo."),
    "spouse_missing": ("You said your spouse is not being sponsored, but no spouse was added to the household.", "Dijiste que tu cónyuge no está siendo patrocinado(a), pero no se agregó un cónyuge al hogar."),
    "spouse_conflict": ("{name} is listed as a spouse but your answers say your spouse is already counted (or you are not married). Please review.", "{name} aparece como cónyuge pero tus respuestas dicen que tu cónyuge ya está contado(a) (o que no estás casado(a)). Revísalo."),
    "two_spouses": ("{name} would be a second spouse in the household. Please review.", "{name} sería un segundo cónyuge en el hogar. Revísalo."),
    "spouse_principal_not_sponsored": ("You said your spouse is the principal immigrant but you are not sponsoring the principal immigrant. Please review.", "Dijiste que tu cónyuge es el inmigrante principal pero no estás patrocinando al inmigrante principal. Revísalo."),
    "spouse_sponsored_missing": ("You said your spouse is one of the family members you are sponsoring, but none was listed. Please review.", "Dijiste que tu cónyuge es uno de los familiares que patrocinas, pero no se listó ninguno. Revísalo."),
    "income_not_counted": ("{name}'s income is being used, but {name} is not counted in the household. Please review.", "Se está usando el ingreso de {name}, pero {name} no está contado(a) en el hogar. Revísalo."),
    "income_person_dup": ("{name}'s income is listed more than once, so it was counted only once. Please review.", "El ingreso de {name} aparece más de una vez, así que se contó una sola vez. Revísalo."),
    "employed_no_source": ("You said you are employed but no job income was added.", "Dijiste que tienes un empleo pero no se agregó ingreso de un empleo."),
    "selfemployed_no_source": ("You said you are self-employed but no self-employment income was added.", "Dijiste que trabajas por cuenta propia pero no se agregó ese ingreso."),
    "source_no_status": ("An income source was added for work you did not select as your current situation. Please review.", "Se agregó una fuente de ingreso de un trabajo que no elegiste como tu situación actual. Revísalo."),
    "no_income_but_sources": ("You said you have no income of your own but income sources were added. Please review.", "Dijiste que no tienes ingresos propios pero se agregaron fuentes de ingreso. Revísalo."),
    "retired_since_missing": ("Add the date you retired.", "Agrega la fecha en que te jubilaste."),
    "unemployed_since_missing": ("Add the date you became unemployed.", "Agrega la fecha en que quedaste desempleado(a)."),
    "date_future": ("A date is in the future. Please review it.", "Una fecha está en el futuro. Revísala."),
    "bad_amount": ("One of the amounts is not a valid dollar amount. Please review.", "Una de las cantidades no es un monto válido en dólares. Revísala."),
    "three_years_missing": ("You said you filed for the three most recent tax years, but fewer than three tax years were added. Please review.", "Dijiste que presentaste declaración por los tres años fiscales más recientes, pero se agregaron menos de tres. Revísalo."),
    "norequire_vs_income": ("You said you were not required to file, but the most recent tax year has an income amount. Please review.", "Dijiste que no estabas obligado(a) a presentar declaración, pero el año fiscal más reciente tiene un ingreso. Revísalo."),
    "no_tax_year": ("The most recent tax year (Item 16.a) is still missing.", "Aún falta el año fiscal más reciente (Ítem 16.a)."),
    "years_not_consecutive": ("The tax years are not consecutive. OG will look at this with you.", "Los años fiscales no son consecutivos. OG lo revisará contigo."),
    "more_than_three": ("Only the three most recent tax years fit on the form; OG will place the rest.", "En el formulario solo caben los tres años fiscales más recientes; OG colocará el resto."),
    "principal_assets_not_sponsored": ("Assets of the principal immigrant are included, but you are not sponsoring the principal immigrant. The form says to include them only if the principal immigrant is sponsored. Please review.",
                                       "Se incluyeron activos del inmigrante principal, pero no estás patrocinando al inmigrante principal. El formulario indica incluirlos solo si se patrocina al inmigrante principal. Revísalo."),
    "household_assets_without_income": ("Assets of a household member were added, but you did not say you are using another person's income. Please review.", "Se agregaron activos de un miembro del hogar, pero no dijiste que usas el ingreso de otra persona. Revísalo."),
    "assets_but_not_used": ("You said you are not using assets, but assets were added. Please review.", "Dijiste que no usas activos, pero se agregaron activos. Revísalo."),
    "assets_used_none": ("You said you are using assets, but none were added.", "Dijiste que usas activos, pero no se agregó ninguno."),
}


def issue_message(issue, lang="en"):
    en = ISSUE_TEXT[issue["code"]][0 if lang != "es" else 1]
    args = {k: (CATEGORY_LABELS.get(v, (v, v))[0 if lang != "es" else 1] if k in ("as", "cat") else v) for k, v in issue.items() if k not in ("level", "code")}
    try:
        return en.format(**args)
    except KeyError:
        return en
