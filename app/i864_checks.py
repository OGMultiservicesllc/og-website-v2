"""Consistency prompts for the I-864 intake: household double counting, arithmetic and internal consistency of the financial answers.

They compare the customer's OWN answers with each other and flag what OG will look at. Never a legal conclusion: nothing says a household,
income or assets are (in)sufficient, or that a joint sponsor is (or is not) needed.
"""

from datetime import date

from app import i864_calc as calc
from app.intake_records import parse_date


def run(a, lang="en", today=None):
    today = today or date.today()
    en = lang != "es"
    out = []

    def add(group, fields, msg_en, msg_es):
        out.append({"group": group, "fields": fields, "message": msg_en if en else msg_es})

    hh = calc.household(a)
    for i in hh["issues"]:
        if i["level"] in ("warn", "error"):
            add("household", ["h_people"], calc.issue_message(i, "en"), calc.issue_message(i, "es"))
    inc = calc.income(a)
    for i in inc["issues"]:
        add("income", ["e_sources"], calc.issue_message(i, "en"), calc.issue_message(i, "es"))
    tx = calc.tax(a)
    for i in tx["issues"]:
        if i["level"] != "info":
            add("tax", ["t_years"], calc.issue_message(i, "en"), calc.issue_message(i, "es"))
    ast = calc.assets(a)
    for i in ast["issues"]:
        add("assets", ["a_assets"], calc.issue_message(i, "en"), calc.issue_message(i, "es"))

    for d_name, group in (("s_dob", "sponsor"), ("p_dob", "principal")):
        d = parse_date(a.get(d_name))
        if d and d > today:
            add(group, [d_name], "A date of birth is in the future. Please review it.", "Una fecha de nacimiento está en el futuro. Revísala.")
    if a.get("i_principal") == "no" and a.get("i_family_q") != "yes" and not a.get("i_family"):
        add("other_immigrants", ["i_family"], "You said you are not sponsoring the principal immigrant, so family members need to be listed.",
            "Dijiste que no patrocinas al inmigrante principal, así que hay que listar a los familiares.")
    # workflow flags: "Not sure — OG will review" and answers OG will look at with the customer
    for name, group, label_en, label_es in (
        ("b_basis", "sponsor_basis", "why you are the sponsor (Part 1)", "por qué eres el patrocinador (Parte 1)"),
        ("hi_use", "hh_income", "using another person's income (Part 6)", "usar el ingreso de otra persona (Parte 6)"),
        ("a_use", "assets", "using assets (Part 7)", "usar activos (Parte 7)"),
    ):
        if a.get(name) == "unsure":
            add(group, [name], f"You were not sure about {label_en}. OG will review this answer with you.", f"No estabas seguro(a) sobre {label_es}. OG revisará esta respuesta contigo.")
    if a.get("h_ok") == "review":
        add("household", ["h_ok"], "You told us something about your household may be missing or wrong. OG will review it with you.", "Nos dijiste que algo de tu hogar puede faltar o estar mal. OG lo revisará contigo.")
    if a.get("b_basis") in ("1d", "1e", "1f"):
        add("sponsor_basis", ["b_basis"], "OG should review the basis for this affidavit with you.", "OG debe revisar contigo la base de este affidavit.")
    return out
