"""Data-consistency checks for the N-400 intake.

These compare a customer's OWN answers with each other ("your marriage date is before
your spouse's date of birth"). They are prompts to review, never eligibility findings:
nothing here says a person does or does not qualify for naturalization.

Each check returns {"group", "fields", "message"}; `fields` are internal field names the
customer should look at (the first one decides which step the "Review" link opens).
"""

from datetime import date

from app.intake_records import parse_date, parse_records


def _int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _norm(text):
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


def run(a, lang="en", today=None):
    today = today or date.today()
    en = lang != "es"
    out = []

    def add(group, fields, msg_en, msg_es):
        out.append({"group": group, "fields": fields, "message": msg_en if en else msg_es})

    dob = parse_date(a.get("dob"))
    lpr = parse_date(a.get("date_lpr"))
    residence = parse_records(a.get("residence_history"))
    work = parse_records(a.get("employment_history"))
    trips = parse_records(a.get("trips"))

    if dob and dob > today:
        add("personal", ["dob"], "Your date of birth is in the future. Please review it.", "Tu fecha de nacimiento está en el futuro. Revísala.")
    if dob and lpr and lpr < dob:
        add("personal", ["date_lpr"], "The date you became a permanent resident is before your date of birth. Please review these dates.",
            "La fecha en que te hiciste residente permanente es anterior a tu fecha de nacimiento. Revisa estas fechas.")
    if lpr and lpr > today:
        add("personal", ["date_lpr"], "The date you became a permanent resident is in the future. Please review it.", "La fecha en que te hiciste residente permanente está en el futuro. Revísala.")
    for name, recs, group, label_en, label_es in (
        ("residence_history", residence, "residence", "residence history", "historial de residencia"),
        ("employment_history", work, "employment", "employment and education history", "historial de empleo y estudios"),
    ):
        starts = [parse_date(r.get("from")) for r in recs if parse_date(r.get("from"))]
        if dob and starts and min(starts) < dob:
            add(group, [name], f"Your {label_en} has an entry that starts before your date of birth. Please review these dates.",
                f"Tu {label_es} tiene una entrada que empieza antes de tu fecha de nacimiento. Revisa estas fechas.")

    if lpr:
        early = [t for t in trips if parse_date(t.get("from")) and parse_date(t.get("from")) < lpr]
        if early:
            add("travel", ["trips"], "A trip is dated before the day you became a permanent resident. Please review these dates.",
                "Un viaje tiene fecha anterior al día en que te hiciste residente permanente. Revisa estas fechas.")

    # marital history
    status = a.get("marital_status")
    times = _int(a.get("times_married"))
    if status in ("married", "separated", "divorced", "widowed", "annulled") and times is not None and times < 1:
        add("family", ["times_married"], "You listed a marital status that means you have been married, but entered 0 marriages. Please review these answers.",
            "Indicaste un estado civil que implica haber estado casado(a), pero anotaste 0 matrimonios. Revisa estas respuestas.")
    if status == "single" and a.get("basis") in ("spouse_citizen", "spouse_abroad"):
        add("family", ["marital_status", "basis"], "You chose a filing reason based on marriage, but your marital status is Single, Never Married. Please review these answers.",
            "Elegiste un motivo de presentación basado en el matrimonio, pero tu estado civil es Soltero(a), nunca casado(a). Revisa estas respuestas.")
    mdate = parse_date(a.get("marriage_date"))
    sdob = parse_date(a.get("spouse_dob"))
    if mdate and mdate > today:
        add("family", ["marriage_date"], "The marriage date is in the future. Please review it.", "La fecha de matrimonio está en el futuro. Revísala.")
    if mdate and sdob and mdate < sdob:
        add("family", ["marriage_date"], "The marriage date is before your spouse's date of birth. Please review these dates.", "La fecha de matrimonio es anterior a la fecha de nacimiento de tu cónyuge. Revisa estas fechas.")
    if mdate and dob and mdate < dob:
        add("family", ["marriage_date"], "The marriage date is before your date of birth. Please review these dates.", "La fecha de matrimonio es anterior a tu fecha de nacimiento. Revisa estas fechas.")

    # children
    total = _int(a.get("children_total"))
    kids = parse_records(a.get("children"))
    if total and total > 0 and len(kids) < total:
        add("family", ["children"], f"You said you have {total} children under 18, but added {len(kids)}. Please add the rest.",
            f"Dijiste que tienes {total} hijos menores de 18 años, pero agregaste {len(kids)}. Agrega los demás.")
    elif total is not None and kids and len(kids) > total:
        add("family", ["children_total"], f"You added {len(kids)} children but said you have {total} under 18. Please review these answers.",
            f"Agregaste {len(kids)} hijos pero dijiste que tienes {total} menores de 18. Revisa estas respuestas.")

    # mailing vs physical
    if a.get("mail_same") == "no" and residence:
        current = next((r for r in residence if r.get("present")), None)
        if current and _norm(current.get("street")) and _norm(current.get("street")) == _norm(a.get("mail_street")) and _norm(current.get("zip")) == _norm(a.get("mail_zip")):
            add("address", ["mail_same"], "You said your mailing address is different, but it looks the same as your current physical address. Please review it.",
                "Dijiste que tu dirección postal es diferente, pero parece igual a tu dirección física actual. Revísala.")

    # SSA
    if a.get("ssa_request") == "yes" and a.get("ssa_consent") == "no":
        add("personal", ["ssa_consent"], "You asked for a Social Security card but did not consent to the disclosure. The form says you must answer “Yes” to both to receive a card.",
            "Pediste una tarjeta de Seguro Social pero no diste tu consentimiento para la divulgación. El formulario indica que debes responder “Sí” a ambas para recibirla.")

    # selective service vs sex
    if a.get("sex") == "female" and a.get("selective_male") == "yes":
        add("additional", ["selective_male"], "You selected Female, but answered “Yes” to the question that begins “Are you a male…”. Please review these answers.",
            "Seleccionaste Femenino, pero respondiste “Sí” a la pregunta que empieza “¿Eres varón…”. Revisa estas respuestas.")
    if a.get("served_us") == "no" and a.get("mil_current") == "yes":
        add("additional", ["served_us"], "You said you have never served in the U.S. armed forces, but also that you are currently a member. Please review these answers.",
            "Dijiste que nunca has servido en las fuerzas armadas de EE. UU., pero también que eres miembro actual. Revisa estas respuestas.")

    # timelines: the current entries should describe the same present
    if residence and work and not any(r.get("present") for r in residence):
        pass  # coverage gaps are reported by the timeline analysis itself
    return out
