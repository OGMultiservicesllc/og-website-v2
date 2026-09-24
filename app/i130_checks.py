"""Data-consistency checks for the I-130 intake.

They compare the customer's OWN answers with each other (petitioner vs beneficiary vs the
relationship they chose). They are prompts to review, never conclusions: nothing here says a
relationship is or is not valid, or that a petition can or cannot be filed.

Each check returns {"group", "fields", "message"}; the first entry of `fields` picks the step
the "Review" link opens. Groups are the section keys defined in seed_i130.SECTIONS.
"""

from datetime import date

from app.intake_records import CANDIDATES, is_us_country, parse_date, parse_records


def _int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _norm(text):
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


def _full(family, given):
    return _norm(given) + "|" + _norm(family)


def _digits(text):
    return "".join(ch for ch in (text or "") if ch.isdigit())


def run(a, lang="en", today=None):
    today = today or date.today()
    en = lang != "es"
    out = []

    def add(group, fields, msg_en, msg_es):
        out.append({"group": group, "fields": fields, "message": msg_en if en else msg_es})

    rel = a.get("relationship_type")
    pdob, bdob = parse_date(a.get("pet_dob")), parse_date(a.get("ben_dob"))

    for who, dob, name, group in (("Your", pdob, "pet_dob", "petitioner"), ("Your family member's", bdob, "ben_dob", "beneficiary")):
        if dob and dob > today:
            add(group, [name], f"{who} date of birth is in the future. Please review it.",
                f"{'Tu' if who == 'Your' else 'La'} fecha de nacimiento {'' if who == 'Your' else 'de tu familiar '}está en el futuro. Revísala.")

    if rel == "child" and pdob and bdob and bdob < pdob:
        add("beneficiary", ["ben_dob"], "You said the beneficiary is your child, but their date of birth is before yours. Please review these dates.",
            "Dijiste que el beneficiario es tu hijo(a), pero su fecha de nacimiento es anterior a la tuya. Revisa estas fechas.")
    if rel == "parent" and pdob and bdob and bdob > pdob:
        add("beneficiary", ["ben_dob"], "You said the beneficiary is your parent, but their date of birth is after yours. Please review these dates.",
            "Dijiste que el beneficiario es tu padre o madre, pero su fecha de nacimiento es posterior a la tuya. Revisa estas fechas.")

    # identity: one person cannot be both sides
    same_name = _full(a.get("pet_family"), a.get("pet_given")) == _full(a.get("ben_family"), a.get("ben_given")) and _norm(a.get("pet_given"))
    if same_name and pdob and bdob and pdob == bdob:
        add("beneficiary", ["ben_given"], "The beneficiary's name and date of birth are the same as yours. Please review these answers.",
            "El nombre y la fecha de nacimiento del beneficiario son iguales a los tuyos. Revisa estas respuestas.")
    pa, ba = _digits(a.get("pet_a_number")), _digits(a.get("ben_a_number"))
    if pa and ba and pa == ba:
        add("beneficiary", ["ben_a_number"], "The beneficiary's A-Number is the same as yours. Please review it.", "El Número A del beneficiario es igual al tuyo. Revísalo.")

    # marital history: petitioner and beneficiary
    for prefix, who_en, who_es, dob, family_group in (("pet", "You", "Tú", pdob, "pet_family"), ("ben", "The beneficiary", "El beneficiario", bdob, "ben_family")):
        status = a.get(f"{prefix}_marital_status")
        times = _int(a.get(f"{prefix}_times_married"))
        if status in ("married", "separated", "divorced", "widowed", "annulled") and times is not None and times < 1:
            add(family_group, [f"{prefix}_times_married"], f"{who_en} listed a marital status that means a marriage, but entered 0 marriages. Please review these answers.",
                f"{who_es} indicó un estado civil que implica un matrimonio, pero anotó 0 matrimonios. Revisa estas respuestas.")
        if status == "single" and times and times > 0:
            add(family_group, [f"{prefix}_times_married"], f"{who_en} listed “Single, Never Married” but also one or more marriages. Please review these answers.",
                f"{who_es} indicó “Soltero(a), nunca casado(a)” pero también uno o más matrimonios. Revisa estas respuestas.")
        mdate = parse_date(a.get(f"{prefix}_marriage_date"))
        if mdate and mdate > today:
            add(family_group, [f"{prefix}_marriage_date"], "A marriage date is in the future. Please review it.", "Una fecha de matrimonio está en el futuro. Revísala.")
        if mdate and dob and mdate < dob:
            add(family_group, [f"{prefix}_marriage_date"], "A marriage date is before the date of birth. Please review these dates.", "Una fecha de matrimonio es anterior a la fecha de nacimiento. Revisa estas fechas.")
        spouses = parse_records(a.get(f"{prefix}_spouses"))
        if sum(1 for s in spouses if s.get("current") == "yes") > 1:
            add(family_group, [f"{prefix}_spouses"], "More than one spouse is marked as the current spouse. Please review these answers.", "Más de un cónyuge está marcado como el cónyuge actual. Revisa estas respuestas.")
        if times is not None and spouses and len(spouses) > times:
            add(family_group, [f"{prefix}_spouses"], f"{len(spouses)} spouses are listed but the number of marriages is {times}. Please review these answers.",
                f"Hay {len(spouses)} cónyuges anotados pero el número de matrimonios es {times}. Revisa estas respuestas.")
        for s in spouses:
            ended = parse_date(s.get("date_ended"))
            if ended and ended > today:
                add(family_group, [f"{prefix}_spouses"], "A marriage end date is in the future. Please review it.", "Una fecha de fin de matrimonio está en el futuro. Revísala.")
                break

    # the relationship they chose vs the marriage answers
    if rel == "spouse":
        if a.get("pet_marital_status") not in (None, "", "married", "separated"):
            add("pet_family", ["pet_marital_status"], "You are petitioning for your spouse, but your marital status is not Married or Separated. Please review these answers.",
                "Estás presentando la petición para tu cónyuge, pero tu estado civil no es Casado(a) ni Separado(a). Revisa estas respuestas.")
        if a.get("ben_marital_status") not in (None, "", "married", "separated"):
            add("ben_family", ["ben_marital_status"], "You are petitioning for your spouse, but their marital status is not Married or Separated. Please review these answers.",
                "Estás presentando la petición para tu cónyuge, pero su estado civil no es Casado(a) ni Separado(a). Revisa estas respuestas.")
        pm, bm = parse_date(a.get("pet_marriage_date")), parse_date(a.get("ben_marriage_date"))
        if pm and bm and pm != bm:
            add("ben_family", ["ben_marriage_date"], "The marriage date you gave for yourself is different from the one you gave for the beneficiary. Please review both.",
                "La fecha de matrimonio que diste para ti es distinta de la que diste para el beneficiario. Revisa ambas.")
        bname = _full(a.get("ben_family"), a.get("ben_given"))
        pspouses = parse_records(a.get("pet_spouses"))
        if pspouses and _norm(a.get("ben_given")) and not any(_full(s.get("family"), s.get("given")) == bname for s in pspouses):
            add("pet_family", ["pet_spouses"], "The beneficiary is not listed among your spouses. Please review these answers.", "El beneficiario no aparece entre tus cónyuges. Revisa estas respuestas.")
        pname = _full(a.get("pet_family"), a.get("pet_given"))
        bspouses = parse_records(a.get("ben_spouses"))
        if bspouses and _norm(a.get("pet_given")) and not any(_full(s.get("family"), s.get("given")) == pname for s in bspouses):
            add("ben_family", ["ben_spouses"], "You are not listed among the beneficiary's spouses. Please review these answers.", "No apareces entre los cónyuges del beneficiario. Revisa estas respuestas.")
    if rel == "parent":
        bname = _full(a.get("ben_family"), a.get("ben_given"))
        parents = parse_records(a.get("pet_parents"))
        if parents and _norm(a.get("ben_given")) and not any(_full(p.get("family"), p.get("given")) == bname for p in parents):
            add("pet_family", ["pet_parents"], "You are petitioning for your parent, but they are not listed among your parents. Please review these answers.",
                "Estás presentando la petición para tu padre o madre, pero no aparece entre tus padres. Revisa estas respuestas.")
    if rel == "child" and a.get("relationship_basis") == "born_in_wedlock" and a.get("pet_marital_status") == "single" and _int(a.get("pet_times_married")) == 0:
        add("relationship", ["relationship_basis"], "You chose a relationship that involves the parents' marriage, but your marital history shows no marriage. Please review these answers.",
            "Elegiste una relación que involucra el matrimonio de los padres, pero tu historial matrimonial no muestra ningún matrimonio. Revisa estas respuestas.")

    # petitioner status
    lpr = parse_date(a.get("pet_lpr_date"))
    if lpr and lpr > today:
        add("petitioner", ["pet_lpr_date"], "Your date of admission is in the future. Please review it.", "Tu fecha de admisión está en el futuro. Revísala.")
    if lpr and pdob and lpr < pdob:
        add("petitioner", ["pet_lpr_date"], "Your date of admission is before your date of birth. Please review these dates.", "Tu fecha de admisión es anterior a tu fecha de nacimiento. Revisa estas fechas.")
    cdate = parse_date(a.get("pet_cert_date"))
    if cdate and pdob and cdate < pdob:
        add("petitioner", ["pet_cert_date"], "Your certificate date is before your date of birth. Please review these dates.", "La fecha de tu certificado es anterior a tu fecha de nacimiento. Revisa estas fechas.")

    # petitioner timelines vs birth
    for name, group, label_en, label_es in (("pet_address_history", "pet_address", "address history", "historial de direcciones"),
                                            ("pet_employment_history", "pet_employment", "employment history", "historial de empleo")):
        starts = [parse_date(r.get("from")) for r in parse_records(a.get(name)) if parse_date(r.get("from"))]
        if pdob and starts and min(starts) < pdob:
            add(group, [name], f"Your {label_en} has an entry that starts before your date of birth. Please review these dates.",
                f"Tu {label_es} tiene una entrada que empieza antes de tu fecha de nacimiento. Revisa estas fechas.")

    # mailing vs physical
    history = parse_records(a.get("pet_address_history"))
    if a.get("pet_mail_same") == "no" and history:
        current = next((r for r in history if r.get("present")), None)
        if current and _norm(current.get("street")) and _norm(current.get("street")) == _norm(a.get("pet_mail_street")) and _norm(current.get("zip")) == _norm(a.get("pet_mail_zip")):
            add("pet_address", ["pet_mail_same"], "You said your mailing address is different, but it looks the same as your current physical address. Please review it.",
                "Dijiste que tu dirección postal es diferente, pero parece igual a tu dirección física actual. Revísala.")

    # beneficiary immigration
    arrival = parse_date(a.get("ben_arrival_date"))
    stay = parse_date(a.get("ben_stay_date"))
    if arrival and arrival > today:
        add("ben_immigration", ["ben_arrival_date"], "The date of arrival is in the future. Please review it.", "La fecha de llegada está en el futuro. Revísala.")
    if arrival and bdob and arrival < bdob:
        add("ben_immigration", ["ben_arrival_date"], "The date of arrival is before the beneficiary's date of birth. Please review these dates.", "La fecha de llegada es anterior a la fecha de nacimiento del beneficiario. Revisa estas fechas.")
    if arrival and stay and stay < arrival:
        add("ben_immigration", ["ben_stay_date"], "The authorized stay expires before the date of arrival. Please review these dates.", "La estadía autorizada vence antes de la fecha de llegada. Revisa estas fechas.")
    if a.get("ben_ever_in_us") == "no" and a.get("processing_choice") == "adjustment_in_us":
        add("ben_immigration", ["processing_choice"], "You said the beneficiary was never in the United States but chose to apply at a USCIS office in the U.S. Please review these answers. OG will go over it with you.",
            "Dijiste que el beneficiario nunca ha estado en los Estados Unidos pero elegiste solicitar en una oficina de USCIS en EE. UU. Revisa estas respuestas. OG lo revisará contigo.")
    if a.get("ben_in_us_now") == "no" and a.get("processing_choice") == "adjustment_in_us":
        add("ben_immigration", ["processing_choice"], "You said the beneficiary is not in the United States now but chose to apply at a USCIS office in the U.S. Please review these answers. OG will go over it with you.",
            "Dijiste que el beneficiario no está en los Estados Unidos actualmente pero elegiste solicitar en una oficina de USCIS en EE. UU. Revisa estas respuestas. OG lo revisará contigo.")
    doc_exp = parse_date(a.get("ben_doc_expiry"))
    if a.get("ben_passport_number") and not a.get("ben_doc_country"):
        add("ben_immigration", ["ben_doc_country"], "A passport number is entered but the country that issued it is blank. Please review it.", "Hay un número de pasaporte pero el país que lo emitió está en blanco. Revísalo.")
    if doc_exp and doc_exp < today:
        add("ben_immigration", ["ben_doc_expiry"], "The passport or travel document appears to be expired. OG will review it with you.", "El pasaporte o documento de viaje parece estar vencido. OG lo revisará contigo.")

    # beneficiary family members
    for r in parse_records(a.get("ben_family_members")):
        d = parse_date(r.get("dob"))
        if d and bdob and str(r.get("relationship") or "").strip().lower() in ("child", "son", "daughter", "hijo", "hija", "hijo(a)") and d < bdob:
            add("ben_family", ["ben_family_members"], "A child listed for the beneficiary is older than the beneficiary. Please review these dates.",
                "Un hijo(a) anotado para el beneficiario es mayor que el beneficiario. Revisa estas fechas.")
            break

    if rel == "spouse":
        _spouse_supplement(a, lang, today, add, bdob)
    return out


def _spouse_supplement(a, lang, today, add, bdob):
    """Prompts for the Form I-130A information collected for a spouse beneficiary."""
    en = lang != "es"
    who = (a.get("ben_given") or "").strip() or ("your spouse" if en else "tu cónyuge")
    history = parse_records(a.get("ben_address_history"))
    jobs = parse_records(a.get("ben_employment_history"))

    for name, recs, group, label_en, label_es in (
        ("ben_address_history", history, "spouse_address", "address history", "historial de direcciones"),
        ("ben_employment_history", jobs, "spouse_employment", "employment history", "historial de empleo"),
    ):
        starts = [parse_date(r.get("from")) for r in recs if parse_date(r.get("from"))]
        if bdob and starts and min(starts) < bdob:
            add(group, [name], f"{who}'s {label_en} has an entry that starts before {who}'s date of birth. Please review these dates.",
                f"El {label_es} de {who} tiene una entrada que empieza antes de su fecha de nacimiento. Revisa estas fechas.")

    # the current address / job live in two shapes; they should describe the same thing
    present = next((r for r in history if r.get("present")), None)
    if present and a.get("ben_phys_street") and (present.get("street") or "").strip().lower() != (a.get("ben_phys_street") or "").strip().lower():
        add("spouse_address", ["ben_address_history"], f"The current address in {who}'s history is different from the address given in the earlier steps. Please review them.",
            f"La dirección actual en el historial de {who} es distinta de la que se dio en los pasos anteriores. Revísalas.")
    current_job = next((r for r in jobs if r.get("present")), None)
    if current_job and current_job.get("type") == "employed" and a.get("ben_employed") == "no":
        add("spouse_employment", ["ben_employment_history"], f"{who}'s history shows a current job, but an earlier step says {who} is not employed. Please review these answers.",
            f"El historial de {who} muestra un empleo actual, pero un paso anterior dice que no tiene empleo. Revisa estas respuestas.")
    if current_job and current_job.get("type") == "unemployed" and a.get("ben_employed") == "yes":
        add("spouse_employment", ["ben_employment_history"], f"{who}'s history says unemployed, but an earlier step gives a current employer. Please review these answers.",
            f"El historial de {who} dice desempleado(a), pero un paso anterior indica un empleador actual. Revisa estas respuestas.")

    # reuse choices must match what the history actually contains
    if a.get("ben_foreign_addr_status") == "yes_history" and not CANDIDATES["last_foreign_address"](history) and not parse_records(a.get("ben_foreign_addr")):
        add("spouse_foreign_address", ["ben_foreign_addr_status"], f"You said the last address outside the U.S. is shown in {who}'s history, but no address outside the U.S. of more than one year is listed. Please review it.",
            f"Dijiste que la última dirección fuera de EE. UU. aparece en el historial de {who}, pero no hay una dirección fuera de EE. UU. de más de un año. Revísalo.")
    if a.get("ben_foreign_job_status") == "yes_history" and not CANDIDATES["last_foreign_job"](jobs):
        add("spouse_foreign_employment", ["ben_foreign_job_status"], f"You said {who}'s last job outside the U.S. is shown in the history, but no job outside the U.S. is listed. Please review it.",
            f"Dijiste que el último empleo de {who} fuera de EE. UU. aparece en el historial, pero no hay ningún empleo fuera de EE. UU. Revísalo.")
    for rec in parse_records(a.get("ben_foreign_addr")):
        if is_us_country(rec.get("country")):
            add("spouse_foreign_address", ["ben_foreign_addr"], "This address is meant to be outside the United States, but the country looks like the United States. Please review it.",
                "Esta dirección debe estar fuera de los Estados Unidos, pero el país parece ser Estados Unidos. Revísala.")
    for rec in parse_records(a.get("ben_foreign_job")):
        if is_us_country(rec.get("country")):
            add("spouse_foreign_employment", ["ben_foreign_job"], "This job is meant to be outside the United States, but the country looks like the United States. Please review it.",
                "Este empleo debe estar fuera de los Estados Unidos, pero el país parece ser Estados Unidos. Revísalo.")

    # parents
    parents = parse_records(a.get("ben_parents"))
    if len(parents) < 2:
        n = len(parents)
        add("spouse_parents", ["ben_parents"], f"Form I-130A asks about both of {who}'s parents; {n} {'is' if n == 1 else 'are'} listed. OG will review this with you.",
            f"El Formulario I-130A pide información de ambos padres de {who}; hay {n} anotado(s). OG lo revisará contigo.")
    for p in parents:
        d = parse_date(p.get("dob"))
        if d and d > today:
            add("spouse_parents", ["ben_parents"], "A parent's date of birth is in the future. Please review it.", "La fecha de nacimiento de un padre o madre está en el futuro. Revísala.")
            break
        if d and bdob and d > bdob:
            add("spouse_parents", ["ben_parents"], f"A parent listed for {who} was born after {who}. Please review these dates.",
                f"Un padre o madre anotado para {who} nació después de {who}. Revisa estas fechas.")
            break

    # contact details the I-130A asks for (collected once, in the I-130 steps)
    if not a.get("ben_phone") and not a.get("ben_mobile"):
        add("spouse_statement", ["ben_phone"], f"Form I-130A asks for {who}'s daytime phone number. If {who} has none, OG will note it.",
            f"El Formulario I-130A pide el teléfono de día de {who}. Si no tiene, OG lo anotará.")
