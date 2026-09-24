"""Consistency prompts for the I-485 intake.

They compare the customer's OWN answers with each other and flag answers OG will look at together with the customer. They are
prompts to review, never eligibility findings: nothing here says a person is admissible, inadmissible, eligible or in need of a
waiver. Wording is always "OG should review this answer" / "please review".

Each check returns {"group", "fields", "message"}; `fields[0]` decides which step the "Review" link opens.
"""

import re
from datetime import date

from app.intake_records import parse_date, parse_records

_ITEM = re.compile(r"^e(\d+)([a-z]?)$")
UNSURE_FIELDS = [
    ("p2_eoir", "adjustment", "Part 2, Item 1", "Parte 2, Ítem 1"),
    ("b_underlying", "adjustment", "the petition behind this application", "la petición en que se basa esta solicitud"),
    ("b_role", "adjustment", "Part 2 (principal or derivative applicant)", "Parte 2 (solicitante principal o derivado)"),
    ("b_cat_group", "adjustment", "Part 2, Item 3 (category)", "Parte 2, Ítem 3 (categoría)"),
    ("b_245i", "adjustment", "Part 2, Item 4", "Parte 2, Ítem 4"),
    ("b_cspa", "adjustment", "Part 2, Item 5", "Parte 2, Ítem 5"),
    ("b_i864_exempt", "adjustment", "Part 3 (Affidavit of Support exemption)", "Parte 3 (exención de la Declaración Jurada de Patrocinio)"),
    ("h_visa_abroad", "history", "Part 4, Item 1", "Parte 4, Ítem 1"),
    ("h_prev_pr", "history", "Part 4, Item 5", "Parte 4, Ítem 5"),
    ("h_rescinded", "history", "Part 4, Item 6", "Parte 4, Ítem 6"),
    ("e56", "elig_public_charge", "Part 9, Item 56 (public charge exempt category)", "Parte 9, Ítem 56 (categoría exenta de carga pública)"),
]


def item_number(name):
    m = _ITEM.match(name or "")
    if not m:
        return None
    n, letter = int(m.group(1)), m.group(2)
    return f"{n}.{letter}" if letter else str(n)


def elig_group(n):
    n = int(str(n).split(".")[0])
    if n <= 9:
        return "elig_groups"
    if n <= 21:
        return "elig_immigration"
    if n <= 41:
        return "elig_criminal"
    if n <= 55:
        return "elig_security"
    if n <= 64:
        return "elig_public_charge"
    if n <= 76:
        return "elig_violations"
    return "elig_misc"


def run(a, lang="en", today=None):
    today = today or date.today()
    en = lang != "es"
    out = []

    def add(group, fields, msg_en, msg_es):
        out.append({"group": group, "fields": fields, "message": msg_en if en else msg_es})

    dob = parse_date(a.get("a_dob"))
    arrival = parse_date(a.get("a_arr_date"))
    if dob and dob > today:
        add("about_you", ["a_dob"], "The date of birth is in the future. Please review it.", "La fecha de nacimiento está en el futuro. Revísala.")
    if dob and (today - dob).days > 365 * 115:
        add("about_you", ["a_dob"], "The date of birth makes the applicant older than 115. Please review it.", "La fecha de nacimiento hace al solicitante mayor de 115 años. Revísala.")
    if dob and arrival and arrival < dob:
        add("arrival", ["a_arr_date"], "The date of last arrival is before the date of birth. Please review these dates.", "La fecha de la última llegada es anterior a la fecha de nacimiento. Revisa estas fechas.")
    if arrival and arrival > today:
        add("arrival", ["a_arr_date"], "The date of last arrival is in the future. Please review it.", "La fecha de la última llegada está en el futuro. Revísala.")
    stay = parse_date(a.get("a_i94_stay_date"))
    if arrival and stay and stay < arrival and a.get("a_i94_stay_type") == "date":
        add("arrival", ["a_i94_stay_date"], "The I-94 expiration date is before the arrival date. Please review these dates.", "La fecha de vencimiento del I-94 es anterior a la fecha de llegada. Revisa estas fechas.")

    for name, recs_name, label_en, label_es in (("a_address_history", "a_address_history", "address history", "historial de direcciones"),
                                                ("a_employment_history", "a_employment_history", "employment and education history", "historial de empleo y estudios")):
        starts = [parse_date(r.get("from")) for r in parse_records(a.get(recs_name)) if parse_date(r.get("from"))]
        if dob and starts and min(starts) < dob:
            add("addresses" if "address" in name else "employment", [name], f"The {label_en} has an entry that starts before the date of birth. Please review these dates.",
                f"El {label_es} tiene una entrada que empieza antes de la fecha de nacimiento. Revisa estas fechas.")

    # marital history
    status = a.get("m_status")
    try:
        times = int(float(a.get("m_times")))
    except (TypeError, ValueError):
        times = None
    prior = parse_records(a.get("m_prior"))
    if status in ("married", "separated", "divorced", "widowed", "annulled") and times is not None and times < 1:
        add("family", ["m_times"], "You chose a marital status that means you have been married, but entered 0 marriages. Please review these answers.",
            "Elegiste un estado civil que implica haber estado casado(a), pero anotaste 0 matrimonios. Revisa estas respuestas.")
    if times and times > 1 and status in ("married", "separated") and len(prior) < times - 1:
        add("family", ["m_prior"], f"You said {times} marriages in total but listed {len(prior)} prior marriage(s). Please review.",
            f"Dijiste {times} matrimonios en total pero enumeraste {len(prior)} matrimonio(s) anterior(es). Revisa.")
    mdate, sdob = parse_date(a.get("s_marr_date")), parse_date(a.get("s_dob"))
    if mdate and mdate > today:
        add("family", ["s_marr_date"], "The marriage date is in the future. Please review it.", "La fecha del matrimonio está en el futuro. Revísala.")
    if mdate and dob and mdate < dob:
        add("family", ["s_marr_date"], "The marriage date is before the applicant's date of birth. Please review these dates.", "La fecha del matrimonio es anterior a la fecha de nacimiento del solicitante. Revisa estas fechas.")
    if mdate and sdob and mdate < sdob:
        add("family", ["s_marr_date"], "The marriage date is before the spouse's date of birth. Please review these dates.", "La fecha del matrimonio es anterior a la fecha de nacimiento del cónyuge. Revisa estas fechas.")
    for rec in prior:
        d_m, d_e = parse_date(rec.get("date_married")), parse_date(rec.get("date_ended"))
        if d_m and d_e and d_e < d_m:
            add("family", ["m_prior"], "A prior marriage ended before it began. Please review these dates.", "Un matrimonio anterior terminó antes de empezar. Revisa estas fechas.")
            break
    children = parse_records(a.get("a_children"))
    try:
        count = int(float(a.get("ch_count")))
    except (TypeError, ValueError):
        count = None
    if count is not None and children and count != len(children):
        add("family", ["ch_count"], f"You said {count} living children but listed {len(children)}. Please review.", f"Dijiste {count} hijos vivos pero enumeraste {len(children)}. Revisa.")
    for c in children:
        cd = parse_date(c.get("dob"))
        if cd and dob and cd < dob:
            add("family", ["a_children"], "A child's date of birth is before the applicant's date of birth. Please review these dates.", "La fecha de nacimiento de un hijo(a) es anterior a la del solicitante. Revisa estas fechas.")
            break

    if a.get("a_ssn_want") == "yes" and a.get("a_ssn_consent") == "no":
        add("about_you", ["a_ssn_consent"], "The form says that wanting a Social Security card requires the consent for disclosure. Please review these answers.",
            "El formulario indica que querer una tarjeta del Seguro Social requiere el consentimiento de divulgación. Revisa estas respuestas.")
    if a.get("m_status") == "single" and a.get("s_family"):
        add("family", ["m_status"], "You chose Single, Never Married but there is spouse information. Please review these answers.", "Elegiste Soltero(a), nunca casado(a) pero hay información de un cónyuge. Revisa estas respuestas.")
    if a.get("b_role") == "derivative" and not (a.get("b_pa_family") and a.get("b_pa_given")):
        add("adjustment", ["b_pa_family"], "You are a derivative applicant: the principal applicant's name is needed. Please review.", "Eres solicitante derivado: se necesita el nombre del solicitante principal. Revisa.")

    # "Not sure — OG will review": a workflow flag, not a problem
    for name, group, label_en, label_es in UNSURE_FIELDS:
        if a.get(name) == "unsure":
            add(group, [name], f"You were not sure about {label_en}. OG will review this answer with you.", f"No estabas seguro(a) sobre {label_es}. OG revisará esta respuesta contigo.")

    # Part 9: every Yes is something OG looks at with the customer (never a conclusion)
    for name in sorted((k for k in a if _ITEM.match(k)), key=lambda k: (int(_ITEM.match(k).group(1)), _ITEM.match(k).group(2))):
        if a.get(name) != "yes":
            continue
        item = item_number(name)
        add(elig_group(item), [name], f"OG should review your answer to Part 9, Item {item}.", f"OG debe revisar tu respuesta al Ítem {item} de la Parte 9.")
    return out
