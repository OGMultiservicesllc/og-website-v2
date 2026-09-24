"""Consistency prompts for the I-751 intake. They compare the customer's own answers with each other and flag what OG will look at.
Never a legal conclusion: nothing says the petition is timely, that a waiver applies, that a marriage was in good faith, or that anyone is (in)eligible.
Wording that could reveal a sensitive filing basis to someone looking over the customer's shoulder is kept neutral ("your filing basis")."""

from datetime import date

from app import i751_calc as calc
from app.intake_records import parse_date


def run(a, lang="en", today=None):
    today = today or date.today()
    en = lang != "es"
    out = []

    def add(group, fields, msg_en, msg_es):
        out.append({"group": group, "fields": fields, "message": msg_en if en else msg_es})

    route, basis = calc.route(a), calc.basis(a)

    # ---- filing basis (never a decision)
    if route == "unsure" or calc.waiver_unsure(a):
        add("basis", ["b_route"], "You were not sure how you are filing. OG will review your filing basis with you before anything is prepared.",
            "No estabas seguro(a) de cómo presentas. OG revisará contigo tu base de presentación antes de preparar nada.")
    if route == "joint" and a.get("b_joint") == "1b":
        add("basis", ["b_joint"], "OG will confirm with you how the rest of the petition applies to a filing together with your parent's spouse.",
            "OG confirmará contigo cómo se aplica el resto de la petición a una presentación junto con el cónyuge de tu padre o madre.")
    if any(b in basis for b in calc.SENSITIVE_BOXES):
        add("basis", ["b_waiver"], "OG will go through your filing basis with you in private.", "OG revisará contigo tu base de presentación en privado.")
    if route == "joint" and calc.marriage_ended(a):
        add("basis", ["r_marriage_ended"], "You said you are filing together, but also that the marriage has ended. Please review both answers.",
            "Dijiste que presentas en conjunto, pero también que el matrimonio terminó. Revisa ambas respuestas.")
    if "1c" in basis and a.get("r_marital") not in (None, "", "widowed"):
        add("basis", ["r_marital"], "Your filing basis and your marital status do not seem to match. Please review both answers.",
            "Tu base de presentación y tu estado civil no parecen coincidir. Revisa ambas respuestas.")
    if "1d" in basis and a.get("r_marital") == "widowed":
        add("basis", ["r_marital"], "Your filing basis and your marital status do not seem to match. Please review both answers.",
            "Tu base de presentación y tu estado civil no parecen coincidir. Revisa ambas respuestas.")
    if route == "joint" and a.get("r_marital") not in (None, "", "married"):
        add("basis", ["r_marital"], "You are filing together with a spouse but your marital status is not “Married”. Please review.",
            "Presentas en conjunto con un cónyuge, pero tu estado civil no es “Casado(a)”. Revísalo.")
    # Part 4 relationship vs basis
    if a.get("p4_rel") == "spouse" and (a.get("b_joint") == "1b" or "1f" in basis):
        add("spouse", ["p4_rel"], "The relationship you chose for the person in Part 4 does not seem to match your filing basis. Please review.",
            "La relación que elegiste para la persona de la Parte 4 no parece coincidir con tu base de presentación. Revísala.")
    if a.get("p4_rel") == "parent_spouse" and (a.get("b_joint") == "1a" or any(b in basis for b in ("1c", "1d", "1e"))):
        add("spouse", ["p4_rel"], "The relationship you chose for the person in Part 4 does not seem to match your filing basis. Please review.",
            "La relación que elegiste para la persona de la Parte 4 no parece coincidir con tu base de presentación. Revísala.")

    # ---- marriage / conditional residence dates (OG looks at timing; nothing is concluded here)
    m, ended, expires, since = (parse_date(a.get(k)) for k in ("r_marriage_date", "r_marriage_end_date", "r_expires", "r_resident_since"))
    for name, d, group, label_en, label_es in (("r_marriage_date", m, "marriage", "The date of marriage", "La fecha del matrimonio"), ("r_resident_since", since, "conditional", "The date you became a resident", "La fecha en que te hiciste residente")):
        if d and d > today:
            add(group, [name], f"{label_en} is in the future. Please review it.", f"{label_es} está en el futuro. Revísala.")
    if m and ended and ended < m:
        add("marriage", ["r_marriage_end_date"], "The date the marriage ended is before the date of marriage. Please review these dates.", "La fecha en que terminó el matrimonio es anterior a la fecha del matrimonio. Revisa estas fechas.")
    if since and expires and expires < since:
        add("conditional", ["r_expires"], "The expiration date is before the date you became a resident. Please review these dates.", "La fecha de vencimiento es anterior a la fecha en que te hiciste residente. Revisa estas fechas.")
    if expires and expires < today:
        add("conditional", ["r_expires"], "The date your conditional residence expires has passed. OG will look at the timing with you; this is not a decision about your case.",
            "La fecha en que vence tu residencia condicional ya pasó. OG revisará contigo los plazos; esto no es una decisión sobre tu caso.")
    if m and since and since < m:
        add("marriage", ["r_marriage_date"], "The date of marriage is after the date you became a resident. Please review these dates.", "La fecha del matrimonio es posterior a la fecha en que te hiciste residente. Revisa estas fechas.")

    # ---- Yes answers: OG looks at them with the customer (never a decision)
    for key, item in (("q18", "18"), ("q19", "19"), ("q20", "20"), ("q21", "21"), ("q23", "23")):
        if a.get(key) == "yes":
            add("additional", [key], f"You answered Yes to Item {item}. OG will review this answer with you; it is not a decision about your case.",
                f"Respondiste Sí al Ítem {item}. OG revisará esta respuesta contigo; no es una decisión sobre tu caso.")
    # ---- residence history since becoming a resident
    if a.get("r_other_addr") == "yes" and not calc.since(a):
        add("residence", ["r_resident_since"], "Add the date you became a resident so we can check that your address history covers the whole period.",
            "Agrega la fecha en que te hiciste residente para verificar que tu historial de direcciones cubra todo el período.")
    # ---- children
    kids = calc.children(a)
    if a.get("k_has") == "yes" and not kids:
        add("children", ["k_has"], "You said you have children but none are listed. Please review.", "Dijiste que tienes hijos pero no hay ninguno en la lista. Revísalo.")
    if len(kids) > calc.FORM_ROOM_CHILDREN:
        add("children", ["k_children"], "The printed form has room for five children. OG will add the others to the Additional Information page for you.",
            "El formulario impreso tiene espacio para cinco hijos. OG agregará a los demás a la página de Información adicional por ti.")
    for name, d, group, label_en, label_es in (("r_dob", parse_date(a.get("r_dob")), "conditional", "A date of birth", "Una fecha de nacimiento"), ("s_dob", parse_date(a.get("s_dob")), "spouse", "The date of birth of the person in Part 4", "La fecha de nacimiento de la persona de la Parte 4")):
        if d and d > today:
            add(group, [name], f"{label_en} is in the future. Please review it.", f"{label_es} está en el futuro. Revísala.")
    return out
