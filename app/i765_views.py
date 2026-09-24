"""Customer-facing cards and the Admin summary for the I-765 intake. Everything here shows what OG knows or what the customer said;
nothing decides eligibility, suggests a category or says a Yes answer makes anyone (in)eligible."""

import html
import json

from flask import url_for

from app import cases as case_svc
from app import i765_calc as calc
from app import persons as pers
from app.case_types import FACTS, role_label
from app.models import ApplicationRole, FormSubmission, Person

# Category suggestions are CONFIGURATION, empty by default: the supplied PDF does not say which category fits which case, so none is invented.
# If OG ever configures one ({case_type: "(c)(9)"}), it is shown as a suggestion the customer must confirm or change — never applied.
CATEGORY_SUGGESTIONS = {}

_SENSITIVE = ("a_anumber", "a_ssn", "a_passport", "a_travel_doc", "a_uscis_account")


def answers(submission):
    return case_svc.answers_by_name(submission)


def mask(value):
    value = str(value or "")
    return ("•••• " + value[-4:]) if len(value) > 4 else ("••••" if value else "")


def _card(inner):
    return f'<div class="rounded-xl border border-accent-200 bg-mist-50 px-4 py-3">{inner}</div>'


def _applicant_person(submission):
    cp = case_svc.role_person(submission, "applicant")
    return (pers.owner_of(cp), cp) if cp is not None else (None, None)


# ------------------------------------------------------------------ Smart Start
_START_ITEMS = [
    (("Name", "Nombre"), ("family_name", "given_name")), (("Date of birth", "Fecha de nacimiento"), ("date_of_birth",)),
    (("Birthplace", "Lugar de nacimiento"), ("birth_country", "birth_city")), (("Citizenship", "Ciudadanía"), ("nationality",)),
    (("A-Number", "Número A"), ("a_number",)), (("Address", "Dirección"), ("current_address",)), (("Last U.S. arrival", "Última llegada a EE. UU."), ("last_arrival_date",)),
    (("Form I-94", "Formulario I-94"), ("i94_number",)), (("Immigration status", "Estatus migratorio"), ("class_of_admission", "current_status")),
    (("Marital status", "Estado civil"), ("marital_status",)), (("Other names", "Otros nombres"), ("other_names",)),
    (("Contact information", "Información de contacto"), ("phone_daytime", "email")),
    (("Passport or travel document", "Pasaporte o documento de viaje"), ("arrival_document_number", "passport_number")),
]


def start_html(submission, lang="en"):
    en = lang == "en"
    owner, _cp = _applicant_person(submission)
    if owner is None:
        return ""
    found = []
    for (label_en, label_es), keys in _START_ITEMS:
        if any(pers.offer(owner, k, submission) is not None for k in keys):
            found.append(label_en if en else label_es)
    if not found:
        return ""
    name = owner.given_name or owner.full_name
    rows = "".join(f'<li class="flex items-center gap-2 text-[15px] text-brand-800"><span class="text-emerald-600" aria-hidden="true">&#10003;</span><span class="min-w-0 break-words">{html.escape(x)}</span></li>' for x in found)
    head = (f"We found information previously provided to OG for {name}" if en else f"Encontramos información que se le dio antes a OG sobre {name}")
    foot = ("You will review this information before it is used. Only what is missing or has changed needs to be typed." if en
            else "Revisarás esta información antes de usarla. Solo hay que escribir lo que falta o cambió.")
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape("We already have most of your information" if en else "Ya tenemos la mayor parte de tu información")}</p>'
                 f'<p class="mt-1 text-[13px] text-slate-600">{html.escape(head)}</p><ul class="mt-2 space-y-1">{rows}</ul><p class="mt-3 text-[12px] text-slate-500">{html.escape(foot)}</p>')


# ------------------------------------------------------------------ previous I-765 (context only — never answers Item 12)
def prior_others(submission):
    owner, _cp = _applicant_person(submission)
    if owner is None:
        return []
    ids = [cp.id for cp in owner.case_people]
    if not ids:
        return []
    out, seen = [], set()
    for r in ApplicationRole.query.filter(ApplicationRole.person_id.in_(ids), ApplicationRole.role_key == "applicant").all():
        s = r.submission
        if s is not None and s.id != submission.id and s.form_id == submission.form_id and s.student_id == submission.student_id and s.status != "archived" and s.id not in seen:
            seen.add(s.id)
            out.append(s)
    return out


def prior_html(submission, lang="en"):
    others = prior_others(submission)
    if not others:
        return ""
    en = lang == "en"
    from app.intake_engine import status_label

    rows = "".join(f'<li class="text-[13px] text-slate-600 break-words">{html.escape("Form I-765")} &middot; <span class="font-mono">{html.escape(s.code)}</span> &middot; {html.escape(status_label(s, lang))}</li>' for s in others)
    note = ("This is only what OG handled. It does not replace your answer: you may have filed before with someone else or long ago." if en
            else "Esto es solo lo que OG manejó. No reemplaza tu respuesta: puede que hayas presentado antes con otra persona o hace mucho tiempo.")
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-slate-500">{html.escape("Forms I-765 OG has for you" if en else "Formularios I-765 que OG tiene de ti")}</p><ul class="mt-1 space-y-0.5">{rows}</ul>'
                 f'<p class="mt-2 text-[12px] text-slate-500">{html.escape(note)}</p>')


# ------------------------------------------------------------------ the passport-or-travel-document known from another application
def arrdoc_html(submission, lang="en"):
    from app.shared_blocks import block_offers, blocks_for

    en = lang == "en"
    block = blocks_for(submission.form).get("sb_arrdoc")
    if not block:
        return ""
    _p, offers = block_offers(submission, block)
    if not offers:
        return ""
    rows = []
    for k in ("arrival_document_number", "arrival_document_country", "arrival_document_expiry"):
        off = offers.get(k)
        if off is None:
            continue
        rows.append(f'<div class="py-1.5"><p class="text-xs font-semibold text-slate-500">{html.escape(FACTS[k]["en" if en else "es"])}</p>'
                    f'<p class="text-[15px] font-semibold text-brand-800 break-words">{html.escape(case_svc.display_fact_value(k, off["value"], lang, reveal=False))}</p></div>')
    src = next(iter(offers.values()))["options"][0]["sources"][0]
    where = ("Given for " if en else "Indicado en ") + (("Form " if en else "Formulario ") + src["form"] if src.get("form") else ("an application" if en else "una solicitud"))
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape("What OG has" if en else "Lo que tiene OG")}</p>'
                 f'<div class="mt-1 divide-y divide-mist-200">{"".join(rows)}</div><p class="mt-1 text-[11px] text-slate-400">{html.escape(where)}</p>')


# ------------------------------------------------------------------ category hint (configuration only)
def category_hint_html(submission, lang="en"):
    en = lang == "en"
    case = submission.case
    hint = CATEGORY_SUGGESTIONS.get(case.case_type) if case is not None else None
    if not hint:
        return ""
    text = (f"For this kind of case, the category OG usually sees is {hint}. This is only a suggestion — enter your own category or choose “Not sure”." if en
            else f"Para este tipo de caso, la categoría que OG suele ver es {hint}. Es solo una sugerencia: ingresa tu propia categoría o elige “No estoy seguro(a)”.")
    return _card(f'<p class="text-[13px] text-slate-700">{html.escape(text)}</p>')


# ------------------------------------------------------------------ Part 6 and Part 5 cards
def additional_html(submission, lang="en"):
    en = lang == "en"
    entries = calc.additional_entries(answers(submission))
    if not entries:
        return f'<p class="text-[13px] text-slate-500">{html.escape("Nothing extra needs to go on the additional-information page so far." if en else "Hasta ahora no hace falta agregar nada a la página de información adicional.")}</p>'
    rows = "".join(f'<li class="py-2"><p class="text-[11px] font-bold uppercase tracking-wide text-slate-400">{html.escape(calc.entry_label(e, lang))}</p>'
                   f'<p class="text-[14px] text-brand-800 break-words whitespace-pre-line">{html.escape(e["text"])}</p></li>' for e in entries)
    head = "OG will add these to the Additional Information page of the form for you" if en else "OG agregará esto a la página de Información adicional del formulario por ti"
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape(head)}</p><ul class="mt-1 divide-y divide-mist-200">{rows}</ul>')


def preparer_statement_text(lang="en"):
    from app import business_info

    item, extends = calc.preparer_statement()
    table = __import__("app.seed_i765", fromlist=["PREP_STATEMENT_EN"])
    words_en = {"extends": "extends", "does_not_extend": "does not extend"}
    words_es = {"extends": "se extiende", "does_not_extend": "no se extiende"}
    if lang == "es":
        return item, table.PREP_STATEMENT_ES[item].format(extends=words_es.get(extends, "…"))
    return item, table.PREP_STATEMENT_EN[item].format(extends=words_en.get(extends, "…"))


def preparer_html(submission, lang="en"):
    en = lang == "en"
    item, text = preparer_statement_text(lang)
    head = "Preparer's statement (Part 5, Item %s)" % item if en else "Declaración del preparador (Parte 5, Ítem %s)" % item
    note = ("This comes from OG's own configuration. OG Multiservices is not a law firm and is never listed as an attorney or accredited representative unless that is actually its status."
            if en else "Esto viene de la configuración propia de OG. OG Multiservices no es un bufete de abogados y nunca figura como abogado o representante acreditado a menos que ese sea realmente su estatus.")
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape(head)}</p><p class="mt-1 text-[14px] text-slate-700">{html.escape(text)}</p>'
                 f'<p class="mt-2 text-[12px] text-slate-500">{html.escape(note)}</p>')


# ------------------------------------------------------------------ Admin
REASONS = {"1a": "Initial permission to accept employment (1.a)", "1b": "Replacement / correction NOT due to USCIS error (1.b)", "1c": "Renewal of permission to accept employment (1.c)"}


def admin_summary(submission):
    a = answers(submission)
    owner, cp = _applicant_person(submission)
    branch = calc.branch(a)
    yn = lambda v: {"yes": "Yes", "no": "No", "unsure": "Not sure — OG to review"}.get(v, v or "—")
    specific = []
    if branch == "c3c":
        specific += [("28.a Degree", a.get("x_degree")), ("28.b Employer's name as listed in E-Verify", a.get("x_everify_name")), ("28.c E-Verify Company ID / Client Company ID", a.get("x_everify_id"))]
    if branch == "c26":
        specific += [("29 Receipt number of H-1B spouse's most recent I-797 (I-129)", a.get("x_c26_receipt"))]
    if branch == "c8":
        specific += [("30 Ever arrested and/or convicted?", yn(a.get("x_c8_arrest")))]
    if branch == "c35":
        specific += [("31.a Receipt number of your I-797 notice for Form I-140", a.get("x_c35_receipt")), ("31.b Ever arrested and/or convicted?", yn(a.get("x_c3536_arrest")))]
    if branch == "c36":
        specific += [("31.a Receipt number of spouse's or parent's I-797 for Form I-140", a.get("x_c36_receipt")), ("31.b Ever arrested and/or convicted?", yn(a.get("x_c3536_arrest")))]
    from app.i765_checks import run as checks

    item, text = preparer_statement_text("en")
    return {
        "person": owner, "case_person": cp,
        "reason": REASONS.get(a.get("r_reason"), "—"),
        "category_known": a.get("e_known") == "known", "category_unsure": a.get("e_known") == "unsure", "category": calc.category_text(a) if a.get("e_known") == "known" else "",
        "category_malformed": a.get("e_known") == "known" and not calc.category_valid(a), "specific": specific, "branch": branch,
        "ids": [("A-Number", mask(a.get("a_anumber"))), ("USCIS Online Account", a.get("a_uscis_account") or "—"), ("SSN", mask(a.get("a_ssn")))],
        "arrival": [("I-94", a.get("a_i94_number") or "—"), ("Date of last arrival", a.get("a_arr_date") or "—"), ("Place", a.get("a_arr_place") or "—"), ("Status at last arrival", a.get("a_arr_status") or "—"),
                    ("Current status", a.get("a_current_status") or "—"), ("Passport (most recent)", mask(a.get("a_passport")) or "—"), ("Travel document", mask(a.get("a_travel_doc")) or "—"),
                    ("Issuing country", a.get("a_doc_country") or "—"), ("Expires", a.get("a_doc_expiry") or "—"), ("SEVIS", a.get("a_sevis") or "—")],
        "prior": yn(a.get("p_prior")), "prior_others": prior_others(submission), "countries": calc.countries(a),
        "interpreter_used": a.get("s_statement") == "interpreter", "interpreter": [(k, a.get(k)) for k in ("int_family", "int_given", "int_org", "int_phone", "int_language") if a.get(k)],
        "preparer": [(k, a.get(k)) for k in ("prep_family", "prep_given", "prep_org", "prep_phone", "prep_email") if a.get(k)], "prep_item": item, "prep_text": text,
        "abc": yn(a.get("a_abc")) if a.get("c_abc_rel") == "yes" else "Not asked", "additional": [(calc.entry_label(e), e["text"]) for e in calc.additional_entries(a)],
        "flags": [c["message"] for c in checks(a, "en")],
    }
