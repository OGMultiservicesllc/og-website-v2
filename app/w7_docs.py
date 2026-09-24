"""W-7 document requirements on the case vault, with the physical-original / CAA side kept separate from the digital upload.

Every requirement says WHY it exists (`doc_basis`): `irs_w7` (the IRS Form W-7 Instructions require or list it), `answer` (triggered by an answer), `workflow` (OG's own workflow),
`admin`, `customer`. Three DIFFERENT questions are answered per requirement and never mixed up:

  digital pre-review     the ordinary vault status (needed / uploaded / under review / accepted -> shown as "Accepted for pre-review")
  original required      `ItinDocTrack.original_required` + `original_state` (a photo upload NEVER moves it)
  who can certify        `ItinDocTrack.caa_route`: "caa" = OG (as a CAA) can verify the original; "irs_original" = OG cannot certify it (dependent's school/medical/national ID...),
                         so the original goes to the IRS with the package; "none" = no original needed

Nothing here decides admissibility of a document: the source-driven help says what the IRS lists, OG staff review the physical original.
"""

import html
from datetime import date

from flask import url_for

from app import case_documents as vault
from app import cases as case_svc
from app import w7_rules as R
from app import w7_text as T
from app.extensions import db
from app.intake_records import parse_date
from app.models import ItinDocTrack

SOURCE_KEY = "w7"
_CAT = {"passport": "passport", "us_visa": "visa_page", "school_record": "school_record", "medical_record": "medical_record", "birth_certificate": "birth_certificate"}


def _answers(submission):
    return case_svc.answers_by_name(submission)


def _list(v):
    if isinstance(v, list):
        return v
    return [v] if v else []


def _person(submission):
    return case_svc.role_person(submission, "itin_applicant")


def kind_of(a):
    return a.get("w_kind") or "primary"


def age_of(a):
    return R.age_on(parse_date(a.get("a_dob")))


def _foreign_birth(a):
    c = (a.get("a_birth_country") or "").strip().lower()
    return bool(c) and c not in ("united states", "usa", "u.s.", "us", "estados unidos", "united states of america")


def res_choice(a, age):
    band = R.age_band(age)
    return {"u6": a.get("res_u6"), "6_17": a.get("res_6_17"), "18plus": a.get("res_18")}.get(band)


def desired(submission):
    """[{rule_key, title, person, category, applications, customer_message, doc_basis, original_required, caa_route, doc_key}]"""
    a = _answers(submission)
    p = _person(submission)
    kind, age = kind_of(a), age_of(a)
    student = a.get("dep_student") == "yes"
    out = []

    def add(rule_key, title, category, basis, message=None, *, doc_key=None, original=False):
        route = "none"
        if original:
            route = "caa" if (doc_key and R.caa_can_verify(doc_key, kind)) else "irs_original"
        out.append({"rule_key": rule_key, "title": title, "person": p, "category": category, "applications": [submission], "customer_message": message, "reuse": True,
                    "doc_basis": basis, "original_required": original, "caa_route": route, "doc_key": doc_key})

    pp = a.get("pp_status") or "have"
    if pp in ("have", "later"):
        add("w7.passport", "Passport — biographical (photo) page", "passport", "irs_w7",
            "A valid passport is the only stand-alone document the IRS accepts for identity and foreign status. A clear photo now is used for OG's pre-review; OG also needs the passport itself.", doc_key="passport", original=True)
    if a.get("visa_entered") == "yes":
        add("w7.visa_page", "U.S. visa page", "visa_page", "answer", "Photo of the page with the U.S. visa (the IRS asks that the visa pages travel with the passport).", doc_key="us_visa", original=False)
    if pp == "none":
        chosen = [k for k in _list(a.get("alt_docs")) if k in R.EVIDENCE and k != "passport"]
        for k in chosen:
            add(f"w7.alt.{k}", R.EVIDENCE[k][0].split(" (")[0], _CAT.get(k, "id_document"), "irs_w7",
                "Without a passport the IRS needs at least two types of documents that prove identity and foreign status, and at least one must show a photograph.", doc_key=k, original=True)
        if len([k for k in chosen if k in R.EVIDENCE]) < 2:
            add("w7.alt.more", "Additional identification document (OG will tell you which fit)", "id_document", "irs_w7",
                "Without a passport the IRS needs at least two types of documents. OG will go through the IRS list with you.", doc_key=None, original=True)
    if kind == "dependent":
        age_known = age is not None
        has_entry = a.get("dep_entry_stamp") == "yes" and pp in ("have", "later")
        req_res, _note = R.needs_us_residency(kind, age, a.get("a_nationality"))
        if age_known and age < 18 and pp == "none":
            add("w7.birth_cert", "Birth certificate (original)", "birth_certificate", "irs_w7", T.BIRTH_CERT_HELP[0], doc_key="birth_certificate", original=True)
        elif kind == "dependent":
            add("w7.birth_cert", "Birth certificate", "birth_certificate", "workflow", T.BIRTH_CERT_HELP[0], doc_key="birth_certificate", original=False)
        if req_res and not has_entry:
            choice = res_choice(a, age)
            if choice in R.EVIDENCE or choice in R.RESIDENCY_ONLY:
                label = (R.ALL_DOC_LABELS[choice][0]).split(" (")[0]
                msg = T.MEDICAL_HELP[0] if choice == "medical_record" else (T.SCHOOL_HELP[0] if choice == "school_record" else T.RESIDENCY_HELP[0])
                add(f"w7.res.{choice}", f"{label} (U.S.) — proof of U.S. residency", _CAT.get(choice, "residency_proof"), "irs_w7", msg, doc_key=choice, original=True)
            else:
                names = ", ".join(R.ALL_DOC_LABELS[k][0].split(" (")[0] for k in R.residency_options(age))
                add("w7.res.choose", "Proof of U.S. residency — OG will tell you which document fits", "residency_proof", "irs_w7", T.RESIDENCY_HELP[0] + (" For this age: " + names + "." if names else ""), doc_key=None, original=True)
    if kind == "spouse":
        add("w7.marriage_cert", "Marriage certificate", "marriage_certificate", "workflow", "OG uses it to document the marriage for the tax return. A clear photo or scan is enough for now.", doc_key=None, original=False)
    if a.get("hist_itin") == "yes" and a.get("hist_name_changed") == "yes":
        add("w7.name_change", "Document showing the legal name change (marriage certificate or court order)", "name_change", "irs_w7",
            "If the legal name changed since the ITIN was issued, the IRS asks for supporting documentation such as a marriage certificate or a court order (W-7 Instructions, Line 1a). A clear copy is enough for now.", doc_key=None, original=False)
    if a.get("inc_type") in ("self", "both", "other"):
        add("w7.income_records", "Records of your self-employment or other income for the tax year", "income_records", "workflow",
            "Invoices, payment records, statements or a simple summary of what was earned. A clear copy is enough and OG can start without it; it helps prepare the tax return.", doc_key=None, original=False)
    if a.get("inc_type") in ("employee", "both"):
        add("w7.w2", "W-2 wage statement(s) for the tax year", "w2", "answer", "Upload each W-2 exactly as it was issued to you.", doc_key=None, original=False)
    return out


def _active_siblings(submission):
    case = submission.case
    return [x for x in case.applications if x.form_id == submission.form_id and x.status != "archived" and x.id != submission.id] if case is not None else []


def sync(submission):
    """Create / withdraw the requirements of EVERY active W-7 of the case together, then keep each requirement's original-tracking row."""
    case = submission.case
    if case is None:
        return None
    from app.models import DocumentRequirement

    merged = {}
    for sub in [submission] + _active_siblings(submission):
        for spec in desired(sub):
            key = (spec["rule_key"], spec["person"].id if spec["person"] else None)
            merged[key] = dict(spec, applications=list(spec["applications"]))
    payload = [{k: v for k, v in s.items() if k not in ("original_required", "caa_route", "doc_key")} for s in merged.values()]
    result = vault.sync_requirements(case, SOURCE_KEY, payload)
    for (rule_key, pid), spec in merged.items():
        req = DocumentRequirement.query.filter_by(case_id=case.id, rule_key=rule_key, person_id=pid).first()
        if req is None:
            continue
        track = ItinDocTrack.query.filter_by(requirement_id=req.id).first()
        if track is None:
            track = ItinDocTrack(requirement_id=req.id, original_state="required" if spec["original_required"] else "none")
            db.session.add(track)
        track.doc_key, track.original_required, track.caa_route = spec["doc_key"], spec["original_required"], spec["caa_route"]
        if not spec["original_required"] and track.original_state in ("required", "will_mail", "will_bring"):
            track.original_state = "none"
        if spec["original_required"] and track.original_state == "none":
            track.original_state = "required"
    db.session.commit()
    return result


def requirements_of(submission):
    from app.models import DocumentRequirement

    p = _person(submission)
    if submission.case is None or p is None:
        return []
    rows = DocumentRequirement.query.filter_by(case_id=submission.case_id, person_id=p.id, source="system", source_key=SOURCE_KEY).all()
    return [r for r in rows if r.withdrawn_at is None]


def passport_requirement(submission):
    return next((r for r in requirements_of(submission) if r.rule_key == "w7.passport"), None)


def passport_state(submission):
    """What My Account and the review show about the passport: needed / uploaded / confirmed."""
    from app import w7_passport as PP

    a = _answers(submission)
    pp = a.get("pp_status") or "have"
    req = passport_requirement(submission)
    uploaded = bool(req is not None and req.current_document is not None)
    ext = PP.latest(submission, statuses=("pending", "confirmed"))
    confirmed = bool(ext is not None and ext.status == "confirmed")
    return {"applies": pp != "none", "needed": pp != "none" and not uploaded, "uploaded": uploaded, "confirmed": confirmed, "pending_confirm": uploaded and not confirmed,
            "source": ext.source if ext is not None else None, "requirement": req}


def coverage_for(submission, planned=True):
    """IDENTITY / FOREIGN STATUS / PHOTO / RESIDENCY coverage from the documents the applicant is expected to provide (`planned`) or has actually uploaded."""
    a = _answers(submission)
    kind, age = kind_of(a), age_of(a)
    reqs = requirements_of(submission)
    keys = set()
    for r in reqs:
        t = r.itin_track
        k = t.doc_key if t is not None else None
        if k and (planned or r.current_document is not None):
            keys.add(k)
    exp = parse_date(a.get("a_pp_expiry"))
    res_req, _ = R.needs_us_residency(kind, age, a.get("a_nationality"))
    res_docs = [k for k in keys if k in R.residency_options(age)] if age is not None else []
    cov = R.coverage(kind, age, a.get("dep_student") == "yes", keys, birth_country_foreign=_foreign_birth(a), passport_has_entry_date=(a.get("dep_entry_stamp") == "yes"),
                     residency_docs=res_docs, residency_required=res_req, passport_current=(exp is None or exp >= date.today()))
    cov["docs"] = sorted(keys)
    cov["photo_exempt"] = R.photo_exempt(age, a.get("dep_student") == "yes")
    return cov


# ------------------------------------------------------------------ customer wording (EN / ES)
def _short(label):
    return label.split(" (")[0]


def req_text(req, lang="en"):
    """(title, message) a CUSTOMER sees for a requirement, in `lang`. The stored English title / message stay the admin record; the rules that create the requirement are untouched."""
    i = 0 if lang != "es" else 1
    key = req.rule_key or ""
    if key in T.REQ_TEXT:
        t = T.REQ_TEXT[key]
        title, msg = t[i], t[2 + i]
        if key == "w7.res.choose" and req.applications:
            age = age_of(_answers(req.applications[0]))
            names = ", ".join(_short(R.ALL_DOC_LABELS[k][i]) for k in R.residency_options(age))
            if names:
                msg += (" Examples: " if i == 0 else " Por ejemplo: ") + names + "."
        return title, msg
    if key == "w7.birth_cert":
        tr = getattr(req, "itin_track", None)
        return T.BIRTH_CERT_TEXT[0][i], T.BIRTH_CERT_TEXT[1 if (tr is not None and tr.original_required) else 2][i]
    if key.startswith("w7.alt.") and key[7:] in R.ALL_DOC_LABELS:
        return _short(R.ALL_DOC_LABELS[key[7:]][i]), T.ALT_TEXT[i]
    if key.startswith("w7.res.") and key[7:] in R.ALL_DOC_LABELS:
        doc = key[7:]
        return f"{_short(R.ALL_DOC_LABELS[doc][i])} — {T.RES_SUFFIX[i]}", T.RES_TEXT.get(doc, T.RES_TEXT["_default"])[i]
    return req.title, req.customer_message


# ------------------------------------------------------------------ customer / admin display
def status_words(req, lang):
    en = lang == "en"
    if req.status in ("accepted",):
        return "Accepted for pre-review" if en else "Aceptado para revisión previa"
    if req.status == "under_review":
        return "Under review" if en else "En revisión"
    if req.status == "uploaded":
        return "Uploaded — copy for pre-review" if en else "Subido — copia para revisión previa"
    if req.status == "needs_replacement":
        return "Needs a new copy" if en else "Necesita una copia nueva"
    return "Needed" if en else "Se necesita"


def documents_html(submission, lang="en"):
    """The applicant's checklist: digital copy (pre-review) and, separately, the physical original."""
    from app.models.itin import ORIGINAL_EN, ORIGINAL_ES

    en = lang == "en"
    case = submission.case
    try:
        sync(submission)
    except Exception:  # noqa: BLE001
        db.session.rollback()
    reqs = requirements_of(submission)
    if case is None or not reqs:
        return f'<p class="text-[13px] text-slate-500">{html.escape("No documents are needed yet." if en else "Aún no se necesitan documentos.")}</p>'
    tone = vault.STATUS_TONE
    rows, any_original = [], False
    for r in reqs:
        t = r.itin_track
        title, message = req_text(r, lang)
        try:
            link = url_for("account.my_case_detail", lang=lang, case_id=case.id, _anchor=f"req-{r.id}")
        except RuntimeError:
            link = "#"
        orig = ""
        if t is not None and t.original_required:
            any_original = True
            state = (ORIGINAL_EN if en else ORIGINAL_ES).get(t.original_state, t.original_state)
            orig = f'<p class="mt-1 text-[12px] font-semibold text-amber-800">Original: {html.escape(state)}</p>'
            if t.caa_route == "irs_original" and _kind_dep(submission):
                orig += f'<p class="text-[11px] text-slate-500">{html.escape(T.CAA_NOTE_DEPENDENT[0 if en else 1])}</p>'
        msg = f'<p class="mt-1 text-[13px] text-slate-600 break-words">{html.escape(message)}</p>' if message else ""
        action = "" if r.status in ("accepted", "under_review") else (
            f'<a href="{html.escape(link)}" class="mt-2 inline-flex items-center min-h-[40px] px-3.5 rounded-lg border border-slate-200 text-[13px] font-semibold text-accent-700 hover:border-accent-300">'
            + html.escape("Upload now (or later)" if en else "Subir ahora (o después)") + " &rarr;</a>")
        rows.append('<li class="rounded-xl border border-slate-100 bg-white px-3.5 py-3"><div class="flex flex-wrap items-start justify-between gap-2">'
                    f'<p class="min-w-0 flex-1 basis-40 text-sm font-semibold text-brand-800 break-words">📄 {html.escape(title)}</p>'
                    f'<span class="inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold {tone[r.status]}">{html.escape(status_words(r, lang))}</span></div>{msg}{orig}{action}</li>')
    delivery = f'<div class="mt-4 rounded-xl border border-mist-200 bg-mist-50 px-4 py-3">{T.delivery_html(lang, html.escape)}</div>' if any_original else ""
    return f'<ul class="space-y-2">{"".join(rows)}</ul>{delivery}'


def _kind_dep(submission):
    return kind_of(_answers(submission)) == "dependent"
