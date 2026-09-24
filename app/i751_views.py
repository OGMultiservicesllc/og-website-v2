"""Customer-facing cards and the Admin summary for the I-751 intake. Everything here shows what OG knows or what the customer said;
nothing decides eligibility, timeliness, good faith or a waiver, and nothing says a Yes answer makes anyone (in)eligible."""

import html
import json

from app import cases as case_svc
from app import i751_calc as calc
from app import persons as pers
from app.case_types import role_label

_SENSITIVE = ("r_anumber", "r_ssn", "r_uscis", "s_ssn", "s_anumber")


def answers(submission):
    return case_svc.answers_by_name(submission)


def mask(value):
    value = str(value or "")
    return ("•••• " + value[-4:]) if len(value) > 4 else ("••••" if value else "")


def _card(inner):
    return f'<div class="rounded-xl border border-accent-200 bg-mist-50 px-4 py-3">{inner}</div>'


def _owner(submission, role):
    cp = case_svc.role_person(submission, role)
    return (pers.owner_of(cp), cp) if cp is not None else (None, None)


_START_ITEMS = [
    (("Name", "Nombre"), ("family_name", "given_name")), (("Date of birth", "Fecha de nacimiento"), ("date_of_birth",)),
    (("Birthplace", "Lugar de nacimiento"), ("birth_country",)), (("Citizenship", "Ciudadanía"), ("nationality",)),
    (("A-Number", "Número A"), ("a_number",)), (("Address", "Dirección"), ("current_address",)), (("Address history", "Historial de direcciones"), ("address_history",)),
    (("Marital status", "Estado civil"), ("marital_status",)), (("Other names", "Otros nombres"), ("other_names",)),
    (("Contact information", "Información de contacto"), ("phone_daytime", "email")),
    (("Physical description", "Descripción física"), ("height_feet", "eye_color", "ethnicity")),
]


def _found(owner, submission, keys_items, lang):
    en = lang == "en"
    return [(le if en else ls) for (le, ls), keys in keys_items if any(pers.offer(owner, k, submission) is not None for k in keys)]


def start_html(submission, lang="en"):
    en = lang == "en"
    resident, _cp = _owner(submission, "conditional_resident")
    relevant, _cp2 = _owner(submission, "relevant_individual")
    blocks = []
    for owner, label_en, label_es, items in ((resident, "About", "Sobre", _START_ITEMS), (relevant, "About", "Sobre", _START_ITEMS[:6])):
        if owner is None:
            continue
        found = _found(owner, submission, items, lang)
        if not found:
            continue
        name = owner.full_name
        rows = "".join(f'<li class="flex items-center gap-2 text-[15px] text-brand-800"><span class="text-emerald-600" aria-hidden="true">&#10003;</span><span class="min-w-0 break-words">{html.escape(x)}</span></li>' for x in found)
        blocks.append(f'<div><p class="text-[13px] font-semibold text-slate-600 break-words">{html.escape((label_en if en else label_es) + " " + name)}</p><ul class="mt-1 space-y-1">{rows}</ul></div>')
    if not blocks:
        return ""
    head = "We already have some information" if en else "Ya tenemos algo de información"
    foot = ("This comes from other applications you have with OG, even in a different case. You will review each part before it is used. Only what is missing or has changed needs to be typed."
            if en else "Viene de otras solicitudes que tienes con OG, incluso en otro caso. Revisarás cada parte antes de usarla. Solo hay que escribir lo que falta o cambió.")
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape(head)}</p><div class="mt-2 space-y-3">{"".join(blocks)}</div><p class="mt-3 text-[12px] text-slate-500">{html.escape(foot)}</p>')


def additional_html(submission, lang="en"):
    en = lang == "en"
    entries = [e for e in calc.additional_entries(answers(submission))]
    if not entries:
        return f'<p class="text-[13px] text-slate-500">{html.escape("Nothing extra needs to go on the additional-information page so far." if en else "Hasta ahora no hace falta agregar nada a la página de información adicional.")}</p>'
    rows = "".join(f'<li class="py-2"><p class="text-[11px] font-bold uppercase tracking-wide text-slate-400">{html.escape(calc.entry_label(e, lang))}</p>'
                   f'<p class="text-[14px] text-brand-800 break-words whitespace-pre-line">{html.escape(e["text"] if not e.get("private") else ("Details you gave (kept private)" if en else "Detalles que diste (se mantienen privados)"))}</p></li>' for e in entries)
    head = "OG will add these to the Additional Information page of the form for you" if en else "OG agregará esto a la página de Información adicional del formulario por ti"
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape(head)}</p><ul class="mt-1 divide-y divide-mist-200">{rows}</ul>')


def preparer_statement_text(lang="en"):
    from app import i751_text as T

    item, extends = calc.preparer_statement()
    words = ({"extends": "se extiende", "does_not_extend": "no se extiende"} if lang == "es" else {"extends": "extends", "does_not_extend": "does not extend"})
    table = T.PREP_STATEMENT_ES if lang == "es" else T.PREP_STATEMENT_EN
    return item, table[item].format(extends=words.get(extends, "…"))


def preparer_html(submission, lang="en"):
    en = lang == "en"
    item, text = preparer_statement_text(lang)
    head = "Preparer's statement (Part 10, Item %s)" % item if en else "Declaración del preparador (Parte 10, Ítem %s)" % item
    note = ("This comes from OG's own configuration. OG Multiservices is not a law firm and is never listed as an attorney or accredited representative unless that is actually its status."
            if en else "Esto viene de la configuración propia de OG. OG Multiservices no es un bufete de abogados y nunca figura como abogado o representante acreditado a menos que ese sea realmente su estatus.")
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape(head)}</p><p class="mt-1 text-[14px] text-slate-700">{html.escape(text)}</p>'
                 f'<p class="mt-2 text-[12px] text-slate-500">{html.escape(note)}</p>')


def route_html(submission, lang="en"):
    """A short, neutral reminder on the Part 4 / Part 8 pages of what the customer chose (never displays a private basis wording)."""
    en = lang == "en"
    a = answers(submission)
    r = calc.route(a)
    label = {"joint": ("Filing together with your spouse (joint petition)", "Presentando junto con tu cónyuge (petición conjunta)"),
             "waiver": ("Filing without your spouse", "Presentando sin tu cónyuge"), "unsure": ("Not sure yet — OG will review with you", "Aún no estás seguro(a): OG lo revisará contigo")}.get(r)
    if not label:
        return ""
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape("How you are filing" if en else "Cómo presentas")}</p>'
                 f'<p class="mt-1 text-[15px] font-semibold text-brand-800">{html.escape(label[0] if en else label[1])}</p>')


def kids_html(submission, lang="en"):
    en = lang == "en"
    first, extra = calc.children_split(answers(submission))
    if not extra:
        return ""
    msg = (f"The printed form has room for {calc.FORM_ROOM_CHILDREN} children. OG will add the other {len(extra)} to the Additional Information page for you." if en
           else f"El formulario impreso tiene espacio para {calc.FORM_ROOM_CHILDREN} hijos. OG agregará a los otros {len(extra)} a la página de Información adicional por ti.")
    return _card(f'<p class="text-[13px] text-slate-700">{html.escape(msg)}</p>')


def history_html(submission, lang="en"):
    """The residence-history period this petition asks about, in plain words (from the date the customer became a resident)."""
    en = lang == "en"
    a = answers(submission)
    since = calc.since(a)
    if since:
        text = (f"This history should cover the time since you became a resident ({since.strftime('%m/%d/%Y')}) until today." if en
                else f"Este historial debe cubrir el tiempo desde que te hiciste residente ({since.strftime('%m/%d/%Y')}) hasta hoy.")
    else:
        text = ("Add the date you became a resident on the previous step so we can check the whole period." if en
                else "Agrega en el paso anterior la fecha en que te hiciste residente para verificar todo el período.")
    return _card(f'<p class="text-[13px] text-slate-700">{html.escape(text)}</p>')


# ------------------------------------------------------------------ Admin
BASIS_TEXT = {"1a": "Joint petition with my spouse (1.a)", "1b": "Joint petition with my parent's spouse (1.b)", "1c": "Spouse is deceased (1.c)",
              "1d": "Marriage terminated through divorce or annulment (1.d)", "1e": "Battered / extreme cruelty by spouse (1.e)",
              "1f": "Parent's marriage — battered / extreme cruelty (1.f)", "1g": "Extreme hardship if status terminated (1.g)"}
P4_TEXT = {"spouse": "Spouse or former spouse (1.a)", "parent_spouse": "Parent's spouse or former spouse (1.b)"}


def admin_summary(submission):
    a = answers(submission)
    resident, rcp = _owner(submission, "conditional_resident")
    relevant, xcp = _owner(submission, "relevant_individual")
    from app.i751_checks import run as checks

    yn = lambda v: {"yes": "Yes", "no": "No", "unsure": "Not sure — OG to review"}.get(v, v or "—")
    item, text = preparer_statement_text("en")
    first, extra = calc.children_split(a)
    kid_rows = []
    for i, k in enumerate(first + extra, 1):
        kid_rows.append({"n": i, "name": calc.child_name(k), "dob": k.get("dob") or "—", "a_number": mask(k.get("a_number")) if k.get("a_number") else "—",
                         "living": "Yes" if k.get("where") == "with_me" else "No", "applying": yn(k.get("applying")), "part11": i > calc.FORM_ROOM_CHILDREN, "linked": bool(k.get("person_id"))})
    status, _res = calc.history_status(a, next((f for f in submission.form.all_fields if f.internal_name == "r_history"), None))
    return {
        "resident": resident, "resident_cp": rcp, "relevant": relevant, "relevant_cp": xcp,
        "relevant_role": role_label(calc.p4_role(a), "en") if calc.p4_role(a) else "—",
        "route": {"joint": "Joint petition", "waiver": "Waiver / individual filing request", "unsure": "Not sure — OG to review"}.get(calc.route(a), "—"),
        "basis": [BASIS_TEXT[b] for b in calc.basis(a)], "basis_unsure": calc.waiver_unsure(a), "sensitive": calc.sensitive_basis(a),
        "p4": P4_TEXT.get(a.get("p4_rel"), "—"), "part8": calc.part8_applies(a) == "yes",
        "marriage": [("Marital status (10)", a.get("r_marital") or "—"), ("Date of marriage (11)", a.get("r_marriage_date") or "—"), ("Place of marriage (12)", a.get("r_marriage_place") or "—"),
                     ("Marriage ended (13)", (a.get("r_marriage_end_date") or "Yes") if a.get("r_marriage_ended") == "yes" else ("No" if a.get("r_marriage_ended") == "no" else "—")),
                     ("Conditional residence expires (14)", a.get("r_expires") or "—"), ("Resident since (OG helper)", a.get("r_resident_since") or "—")],
        "ids": [("A-Number", mask(a.get("r_anumber"))), ("USCIS Online Account", a.get("r_uscis") or "—"), ("SSN", mask(a.get("r_ssn")))],
        "questions": [("18 Removal / deportation / rescission proceedings", yn(a.get("q18"))), ("19 Fee paid to anyone other than an attorney", yn(a.get("q19"))),
                      ("20 Arrested, detained, charged, ...", yn(a.get("q20"))), ("21 Different marriage than the one that gave conditional residence", yn(a.get("q21")) if a.get("r_marital") == "married" else "Not asked"),
                      ("22 Resided at any other address", yn(a.get("r_other_addr"))), ("23 Spouse / parent's spouse serving with the U.S. Government outside the U.S.", yn(a.get("q23")))],
        "history_status": {"ok": "Covers the period", "gaps": "Has gaps / issues to review", "none": "Not entered", "na": "Not needed (Item 22 = No)"}[status],
        "children": kid_rows, "children_over": len(extra),
        "accommodations": [("Own", yn(a.get("acc_own"))), ("Spouse's", yn(a.get("acc_spouse"))), ("Included children's", yn(a.get("acc_children")))],
        "interpreter_used": a.get("s_statement") == "interpreter" or a.get("s8_statement") == "interpreter",
        "interpreter": [(k, a.get(k)) for k in ("int_family", "int_given", "int_org", "int_phone", "int_language") if a.get(k)],
        "preparer": [(k, a.get(k)) for k in ("prep_family", "prep_given", "prep_org", "prep_phone", "prep_email") if a.get(k)], "prep_item": item, "prep_text": text,
        "additional": [(calc.entry_label(e), e["text"]) for e in calc.additional_entries(a)], "flags": [c["message"] for c in checks(a, "en")],
        "unsigned_note": "Signatures and dates of signature (Part 7 Item 6, Part 8 Item 6, Part 9 Item 6, Part 10 Item 8) are not collected by this intake.",
    }


# ------------------------------------------------------------------ verbatim texts with the person's name filled in (reading only; nothing is signed here)
def _preparer_name_and_status():
    from app import business_info as bi

    name = " ".join(x for x in (getattr(bi, "PREPARER_FIRST_NAME", ""), getattr(bi, "PREPARER_LAST_NAME", "")) if x) or getattr(bi, "PREPARER_ORG", "") or "OG Multiservices"
    attorney = getattr(bi, "PREPARER_STATUS", "not_attorney") in ("attorney", "accredited")
    return name, attorney


def _p7_prep(lang, who_en="the petitioner"):
    from app import i751_text as T

    name, attorney = _preparer_name_and_status()
    is_not = ("is" if attorney else "is not") if lang != "es" else ("es" if attorney else "no es")
    return (T.P7_PREPARER_ES if lang == "es" else T.P7_PREPARER_EN).format(name=name, is_not=is_not)


def p7prep_html(submission, lang="en"):
    en = lang == "en"
    head = "Part 7, Item 2 — the person who prepares your petition (from OG's own settings)" if en else "Parte 7, Ítem 2 — la persona que prepara tu petición (de la configuración propia de OG)"
    note = "" if en else f'<p class="mt-1 text-[12px] text-slate-500">{html.escape(_courtesy())}</p>'
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape(head)}</p><p class="mt-1 text-[14px] text-slate-700 break-words">{html.escape(_p7_prep(lang))}</p>{note}')


def p8prep_html(submission, lang="en"):
    en = lang == "en"
    head = "Part 8, Item 2 — the person who prepares the petition (from OG's own settings)" if en else "Parte 8, Ítem 2 — la persona que prepara la petición (de la configuración propia de OG)"
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape(head)}</p><p class="mt-1 text-[14px] text-slate-700 break-words">{html.escape(_p7_prep(lang))}</p>')


def _courtesy():
    from app import i751_text as T

    return T.COURTESY_SHORT_ES


def _paras(texts, name, lang):
    out = []
    for t in texts:
        t = t.replace("{name}", html.escape(name or "________"))
        out.append(f'<p class="text-[15px] leading-relaxed text-slate-700">{t}</p>')
    if lang == "es":
        out.append(f'<p class="text-[12px] text-slate-500">{html.escape(_courtesy())}</p>')
    return '<div class="space-y-3">' + "".join(out) + "</div>"


def asc_html(submission, lang="en"):
    from app import i751_text as T

    owner, _cp = _owner(submission, "conditional_resident")
    return _paras(T.ASC_ES if lang == "es" else T.ASC_EN, owner.full_name if owner else "", lang)


def asc8_html(submission, lang="en"):
    from app import i751_text as T

    owner, _cp = _owner(submission, "relevant_individual")
    cert = (T.CERT_ES if lang == "es" else T.CERT_EN)[:2]
    return _paras(list(T.ASC_ES if lang == "es" else T.ASC_EN) + list(cert), owner.full_name if owner else "", lang)
