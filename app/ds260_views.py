"""Customer-facing cards and the Admin summary for the DS-260 intake.

Everything here shows what OG knows or what the customer said; nothing decides admissibility, eligibility or a waiver. Security & Background answers are never
shown in a card or summary: only "n answers to review with OG" counts appear, and only to OG staff.
"""

import html

from app import business_info
from app import cases as case_svc
from app import ds260_calc as calc
from app import persons as pers
from app.case_types import role_label

_START_ITEMS = [
    (("Name", "Nombre"), ("family_name", "given_name")), (("Date of birth", "Fecha de nacimiento"), ("date_of_birth",)), (("Birthplace", "Lugar de nacimiento"), ("birth_country",)),
    (("Nationality", "Nacionalidad"), ("nationality",)), (("Passport", "Pasaporte"), ("passport_number",)), (("Present address", "Dirección actual"), ("current_address",)),
    (("Address history", "Historial de direcciones"), ("address_history",)), (("Marital status", "Estado civil"), ("marital_status",)), (("Other names", "Otros nombres"), ("other_names",)),
    (("Contact information", "Información de contacto"), ("phone_daytime", "email")),
]
_PT_ITEMS = [(("Name", "Nombre"), ("family_name", "given_name")), (("Address", "Dirección"), ("current_address",)), (("Contact information", "Información de contacto"), ("phone_daytime", "email"))]


def _card(inner, tone="accent"):
    return f'<div class="rounded-xl border border-{tone}-200 bg-mist-50 px-4 py-3">{inner}</div>'


def _owner(submission, role):
    cp = case_svc.role_person(submission, role)
    return (pers.owner_of(cp), cp) if cp is not None else (None, None)


def _found(owner, submission, items, lang):
    en = lang == "en"
    return [(le if en else ls) for (le, ls), keys in items if any(pers.offer(owner, k, submission) is not None for k in keys)]


def start_html(submission, lang="en"):
    en = lang == "en"
    blocks = []
    for role, items in (("visa_applicant", _START_ITEMS), ("petitioner", _PT_ITEMS)):
        owner, _cp = _owner(submission, role)
        if owner is None:
            continue
        found = _found(owner, submission, items, lang)
        if not found:
            continue
        rows = "".join(f'<li class="flex items-center gap-2 text-[15px] text-brand-800"><span class="text-emerald-600" aria-hidden="true">&#10003;</span><span class="min-w-0 break-words">{html.escape(x)}</span></li>' for x in found)
        who = ("About " if en else "Sobre ") + owner.full_name
        blocks.append(f'<div><p class="text-[13px] font-semibold text-slate-600 break-words">{html.escape(who)}</p><ul class="mt-1 space-y-1">{rows}</ul></div>')
    if not blocks:
        return ""
    head = "We already have some information" if en else "Ya tenemos algo de información"
    foot = ("This comes from other applications you have with OG, even in a different case. You will review each part before it is used. Only what is missing or has changed needs to be typed."
            if en else "Viene de otras solicitudes que tienes con OG, incluso en otro caso. Revisarás cada parte antes de usarla. Solo hay que escribir lo que falta o cambió.")
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape(head)}</p><div class="mt-2 space-y-3">{"".join(blocks)}</div><p class="mt-3 text-[12px] text-slate-500">{html.escape(foot)}</p>')


def context_html(submission, lang="en"):
    """Who this DS-260 is for, its role in the case, and the other applicants' DS-260s (names and progress only)."""
    from app import consular

    en = lang == "en"
    case = submission.case
    applicant, _cp = _owner(submission, "visa_applicant")
    if case is None or applicant is None:
        return ""
    row = submission.ds260
    role = row.applicant_role if row is not None else "principal"
    role_txt = ("Principal applicant" if role == "principal" else "Derivative applicant") if en else ("Solicitante principal" if role == "principal" else "Solicitante derivado")
    cd = case.consular_data
    nvc = f' · NVC {html.escape(consular.mask(cd.nvc_case_number))}' if cd is not None and cd.nvc_case_number else ""
    parts = [f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape("This DS-260 is for" if en else "Este DS-260 es para")}</p>'
             f'<p class="text-[17px] font-extrabold tracking-tight text-brand-800 break-words">{html.escape(applicant.full_name)}</p>'
             f'<p class="text-[13px] text-slate-600">{html.escape(role_txt)} &middot; {html.escape("Case" if en else "Caso")} <span class="font-mono font-semibold">{html.escape(case.case_number or "")}</span>{nvc}</p>']
    others = [a for a in consular.applicants(case) if a["submission"].id != submission.id]
    if others:
        rows = "".join(f'<li class="flex items-center justify-between gap-2 text-[13px] text-slate-700"><span class="min-w-0 break-words">{html.escape(o["person"].full_name if o["person"] else "?")}</span>'
                       f'<span class="text-slate-400 tabular-nums">{consular.form_progress(o["submission"])}%</span></li>' for o in others)
        parts.append(f'<p class="mt-3 text-xs font-bold uppercase tracking-wider text-slate-500">{html.escape("Other applicants in this case (each has their own DS-260)" if en else "Otros solicitantes de este caso (cada uno tiene su propio DS-260)")}</p><ul class="mt-1 space-y-1">{rows}</ul>')
    return _card("".join(parts))


def assist_html(submission, lang="en"):
    en = lang == "en"
    p = calc.preparer_defaults()
    head = "OG Multiservices as the preparer" if en else "OG Multiservices como preparador"
    body = (f"{p['given']} {p['surname']}, {p['org']}, {p['street']} {p['unit']}, {p['city']}, {p['state']} {p['zip']}" if en else f"{p['given']} {p['surname']}, {p['org']}, {p['street']} {p['unit']}, {p['city']}, {p['state']} {p['zip']}")
    note = ("This comes from OG's own configuration. OG Multiservices is not a law firm and is never listed as an attorney or accredited representative unless that is actually its status. "
            "If you choose “Yes” below, OG's details are what staff enter as the preparer in CEAC."
            if en else "Esto viene de la configuración propia de OG. OG Multiservices no es un bufete de abogados y nunca figura como abogado o representante acreditado a menos que ese sea realmente su estatus. "
            "Si eliges “Sí” abajo, los datos de OG son los que el personal ingresa como preparador en CEAC.")
    return _card(f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape(head)}</p><p class="mt-1 text-[14px] text-slate-700 break-words">{html.escape(body)}</p>'
                 f'<p class="mt-2 text-[12px] text-slate-500">{html.escape(note)}</p>')


# ------------------------------------------------------------------ Admin
def admin_summary(submission):
    """Data for the DS-260 panel on the application: applicant, role, case data (masked), source snapshot, OG vs CEAC status, review flags. No Security answers."""
    from app import consular, ds260_ceac
    from app.models import ApplicationRole

    a = case_svc.answers_by_name(submission)
    owner, _cp = _owner(submission, "visa_applicant")
    row = submission.ds260
    case = submission.case
    cd = case.consular_data if case is not None else None
    src = row.source if row is not None else None
    petitioner, _pcp = _owner(submission, "petitioner")
    counts = calc.security_counts(a)
    flags = calc.review_flags(a)
    children = []
    from app.intake_records import parse_records

    for rec in parse_records(a.get("k_children")):
        person = None
        if rec.get("person_id"):
            from app.models import Person

            person = Person.query.filter_by(id=int(rec["person_id"]), customer_id=submission.student_id).first() if str(rec["person_id"]).isdigit() else None
        own = None
        if person is not None:
            for x in consular.applicants(case) if case is not None else []:
                if x["person"] is not None and x["person"].id in [cp.id for cp in person.case_people]:
                    own = x["submission"]
        children.append({"name": " ".join(x for x in (rec.get("given"), rec.get("family")) if x) or (person.full_name if person else "?"), "immigrating": rec.get("immigrating") or "", "person": person, "own_ds260": own})
    siblings = [x for x in (consular.applicants(case) if case is not None else []) if x["submission"].id != submission.id]
    prep = ds260_ceac.readiness(submission) if submission.is_complete else {"blockers": ["Not sent to OG yet."], "warnings": [], "ready": False}
    return {
        "applicant": owner, "role": (row.applicant_role if row is not None else "principal"), "petitioner": petitioner, "pt_relation": a.get("pt_relation"),
        "case": case, "consular": {"nvc": consular.mask(cd.nvc_case_number) if cd and cd.nvc_case_number else "", "invoice": consular.mask(cd.invoice_id) if cd and cd.invoice_id else "",
                                   "post": cd.post if cd else "", "visa_class": cd.visa_class if cd else "", "priority": cd.priority_date if cd else None,
                                   "nvc_status": cd.nvc_status if cd else "", "interview": cd.interview_date if cd else None} if cd else None,
        "source": ({"code": src.code, "sample": src.sample_date, "verified": src.verified_at, "hash": (src.schema_hash or "")[:12], "is_current": src.is_current} if src is not None else None),
        "ceac_status": row.ceac_status if row is not None else "not_started", "ceac_status_at": row.ceac_status_at if row is not None else None, "ceac_status_by": row.ceac_status_by if row is not None else None,
        "ceac_note": row.ceac_note if row is not None else None, "ready_at": row.ready_for_ceac_at if row is not None else None, "ready_by": row.ready_for_ceac_by if row is not None else None,
        "hints": calc.hints(a, submission), "sec_counts": counts, "flags": flags, "children": children, "siblings": siblings, "prep": prep,
        "fgmc": a.get("c_fgmc") == "yes", "underlying": (cd.underlying_submission if cd is not None else None),
        "warning_after_submit": (row is not None and row.ceac_status == "submitted"),
    }
