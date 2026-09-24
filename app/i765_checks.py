"""Consistency prompts for the I-765 intake. They compare the customer's own answers with each other and flag what OG will look at.
Never a legal conclusion: nothing says the applicant does or does not qualify for employment authorization or that a category is right."""

from datetime import date

from app import i765_calc as calc
from app.intake_records import parse_date


def run(a, lang="en", today=None):
    today = today or date.today()
    en = lang != "es"
    out = []

    def add(group, fields, msg_en, msg_es):
        out.append({"group": group, "fields": fields, "message": msg_en if en else msg_es})

    # ---- eligibility category: syntax only, never eligibility
    if a.get("e_known") == "known" and not calc.category_valid(a):
        add("category", ["e_cat_a"], "The eligibility category is not in the printed format (a letter, a number and, if there is one, a third part). OG will check it with you.",
            "La categoría de elegibilidad no está en el formato impreso (una letra, un número y, si hay, una tercera parte). OG la revisará contigo.")
    if a.get("e_known") == "unsure":
        add("category", ["e_known"], "You were not sure about your eligibility category. OG will review it with you before anything is prepared.",
            "No estabas seguro(a) de tu categoría de elegibilidad. OG la revisará contigo antes de preparar nada.")
    elif calc.branch(a):
        add("category", ["e_known"], "The category you entered has its own questions on the form. OG will review the category and any additional documentation with you.",
            "La categoría que ingresaste tiene preguntas propias en el formulario. OG revisará contigo la categoría y cualquier documentación adicional.")
    branch = calc.branch(a)
    for key, fld in (("x_c8_arrest", "x_c8_arrest"), ("x_c3536_arrest", "x_c3536_arrest")):
        if a.get(key) == "yes" and ((key == "x_c8_arrest" and branch == "c8") or (key == "x_c3536_arrest" and branch in ("c35", "c36"))):
            add("category", [fld], "You answered Yes to the arrest or conviction question. OG will review this answer with you; it is not a decision about your case.",
                "Respondiste Sí a la pregunta sobre arrestos o condenas. OG revisará esta respuesta contigo; no es una decisión sobre tu caso.")
    if a.get("a_abc") in ("yes", "unsure"):
        add("statement", ["a_abc"], "OG will review the ABC settlement question with you.", "OG revisará contigo la pregunta sobre el acuerdo ABC.")

    # ---- reason vs history
    if a.get("r_reason") in ("1b", "1c") and a.get("p_prior") == "no":
        add("reason", ["p_prior"], "You chose replacement or renewal but said you have never filed a Form I-765 before. Please review both answers.",
            "Elegiste reemplazo o renovación pero dijiste que nunca has presentado un Formulario I-765. Revisa ambas respuestas.")

    # ---- documents / dates
    if not (a.get("a_passport") or a.get("a_travel_doc")):
        add("arrival", ["a_passport"], "No passport or travel document number was given. OG will ask about it.", "No se indicó un número de pasaporte ni de documento de viaje. OG preguntará al respecto.")
    for name, group, label_en, label_es in (("a_dob", "applicant", "A date of birth", "Una fecha de nacimiento"), ("a_arr_date", "arrival", "The date of last arrival", "La fecha de la última llegada")):
        d = parse_date(a.get(name))
        if d and d > today:
            add(group, [name], f"{label_en} is in the future. Please review it.", f"{label_es} está en el futuro. Revísala.")
    exp = parse_date(a.get("a_doc_expiry"))
    if exp and exp < today:
        add("arrival", ["a_doc_expiry"], "The passport or travel document expiration date is in the past. OG will look at this with you.", "La fecha de vencimiento del pasaporte o documento de viaje ya pasó. OG lo revisará contigo.")
    return out
