"""Human-friendly summaries of a Driver License case: the customer's personalized plan (Final Review, sensitive values masked) and the
structured Admin summary. Generated from structured data only. No AI. The customer NEVER sees a point count or a technical worksheet —
see app/driver_license/rules.py's SOURCE NOTE — only "Good" / "Still needed" / "OG will review"."""

from app.driver_license import docs, people, pricing, rules, service
from app.driver_license.config import CONFIG, doc_lang_value
from app.tax.questions import pick


def _t(en, es, lang):
    return es if lang == "es" else en


def label(key, value, lang):
    q = CONFIG.index().get(key)
    if value in (None, "", []):
        return ""
    if q is None:
        return str(value)
    if isinstance(value, list):
        return ", ".join(filter(None, (label(key, v, lang) for v in value)))
    opts = q.options if not callable(q.options) else []
    o = next((x for x in opts if x.value == value), None)
    return (f"{o.emoji} " if o and o.emoji else "") + pick(o.label, lang) if o else str(value)


def _line(lab, val):
    return {"label": lab, "value": val} if val not in (None, "", []) else None


def _lang_line(c, doc_key, question_key):
    """Admin-facing language display for a translatable document: the customer's direct answer if they were
    asked, otherwise the inferred value clearly marked as inferred (item C) — never silently blank just because
    the question itself was skipped."""
    direct = c.v(question_key)
    if direct:
        return label(question_key, direct, "en")
    inferred = doc_lang_value(c, doc_key)
    if not inferred:
        return ""
    return f"{label(question_key, inferred, 'en')} (inferred from country, not asked)"


def review_cards(dl, lang):
    en = lang != "es"
    c = service.ctx(dl, lang)
    owner = people.self_person(dl)
    g = lambda bind: people.get_fact(owner, bind)  # noqa: E731
    cards = []

    name = " ".join(x for x in (g("given_name"), g("family_name")) if x)
    addr = ", ".join(x for x in (g("address.street"), g("address.city"), g("address.zip")) if x)
    cards.append({"key": "about", "icon": "👤", "title": _t("About You", "Sobre Ti", lang),
                 "lines": [x for x in (_line(_t("Name", "Nombre", lang), name), _line(_t("Phone", "Teléfono", lang), g("phone_daytime")),
                                       _line("Email", g("email")), _line(_t("NJ Address", "Dirección de NJ", lang), addr)) if x], "edit": "about"})

    doc_lines = []
    for d in c.v("documents") or []:
        if d in ("other", "unsure"):
            continue
        doc_lines.append({"label": None, "value": f"✓ {rules.document_label(d, lang)}"})
    cards.append({"key": "documents", "icon": "📋", "title": _t("Documents", "Documentos", lang), "lines": doc_lines or [_line(None, _t("Nothing selected yet", "Nada seleccionado todavía", lang))], "edit": "documents"})

    price = pricing.customer_view(dl, c, lang)
    trans_lines = [{"label": l["label"], "value": l["amount"]} for l in price.get("lines", [])] if price.get("state") in ("estimate", "review") else []
    cards.append({"key": "translations", "icon": "🌐", "title": _t("Translations", "Traducciones", lang), "lines": trans_lines or [_line(None, _t("None needed", "Ninguna necesaria", lang))], "edit": "doc_languages"})

    ssn_path = c.v("ssn_itin_path")
    ssn_line = _t("OG review required for affidavit option", "Se requiere revisión de OG para la opción de declaración jurada", lang) if ssn_path == "neither" else label("ssn_itin_path", ssn_path, lang)
    cards.append({"key": "ssn", "icon": "🧾", "title": "SSN / ITIN", "lines": [_line(None, ssn_line)] if ssn_line else [], "edit": "ssn_itin"})

    addr_doc = c.v("address_doc")
    addr_line = f"✓ {label('address_doc', addr_doc, lang)}" if addr_doc not in (None, "none", "unsure") else _t("⚠ Still needed", "⚠ Todavía se necesita", lang)
    cards.append({"key": "nj_address", "icon": "🏠", "title": _t("NJ Address", "Dirección de NJ", lang), "lines": [_line(None, addr_line)], "edit": "address_proof"})

    next_lines = []
    where = c.v("where")
    if where in ("not_started", "need_permit_appt", "unsure") and c.v("wants_appointment_help") == "yes":
        next_lines.append(_line(_t("Next Step", "Próximo Paso", lang), _t("Initial Permit Appointment", "Cita del Initial Permit", lang)))
        for i, key in enumerate(("loc1", "loc2", "loc3"), 1):
            locid = c.v(key)
            if locid:
                from app.models import MvcLocation

                loc = MvcLocation.query.get(int(locid)) if str(locid).isdigit() else None
                ord_label = {1: (_t("Preferred MVC", "MVC Preferido", lang)), 2: _t("Second Choice", "Segunda Opción", lang), 3: _t("Third Choice", "Tercera Opción", lang)}[i]
                if loc:
                    next_lines.append(_line(ord_label, loc.name))
    cards.append({"key": "next", "icon": "➡️", "title": _t("Next Step", "Próximo Paso", lang), "lines": [x for x in next_lines if x] or [_line(None, _t("OG will follow up with your next step.", "OG te dará seguimiento con tu próximo paso.", lang))], "edit": "appointment"})
    return cards


def admin_summary(dl):
    lang = "en"
    c = service.ctx(dl, lang)
    owner = people.self_person(dl)
    g = lambda bind: people.get_fact(owner, bind)  # noqa: E731
    a = service.assess(dl, c)
    sections = []

    def sec(title, rows):
        rows = [r for r in rows if r and r[1] not in (None, "", [])]
        sections.append({"title": title, "rows": rows})

    sec("Applicant", [("Name", " ".join(x for x in (g("given_name"), g("family_name")) if x)), ("Date of birth", g("date_of_birth")), ("Phone", g("phone_daytime")),
                      ("Email", g("email")), ("NJ Address", ", ".join(x for x in (g("address.street"), g("address.unit_number"), g("address.city"), g("address.zip")) if x)),
                      ("Where they said they are", label("where", c.v("where"), lang))])
    sec("Documents (identity/points assessment)", [("Selected", label("documents", c.v("documents"), lang)), ("Points (UNVERIFIED — see rules.py)", a["points"]),
                                                    ("Has a primary document", "Yes" if a["has_primary"] else "No"), ("Meets minimum (unverified)", "Yes" if a["meets_minimum"] else "No"),
                                                    ("Rules version", a["rules_version"])])
    sec("SSN / ITIN / Affidavit", [("Path", label("ssn_itin_path", c.v("ssn_itin_path"), lang)), ("ITIN evidence", label("itin_evidence", c.v("itin_evidence"), lang))])
    sec("Foreign Driver License", [("Issuing country", label("fl_country", c.v("fl_country"), lang)), ("Currently valid", label("fl_valid", c.v("fl_valid"), lang)),
                                    ("Language", _lang_line(c, "foreign_license", "fl_lang"))])
    sec("NJ Address Proof", [("Document", label("address_doc", c.v("address_doc"), lang))])
    sec("Document Languages", [("National ID", _lang_line(c, "national_id", "lang_national_id")), ("Birth Certificate", _lang_line(c, "birth_certificate", "lang_birth_certificate")),
                               ("Standard single-page birth certificate", label("bc_standard", c.v("bc_standard"), lang))])
    loc_names = []
    from app.models import MvcLocation

    for key in ("loc1", "loc2", "loc3"):
        locid = c.v(key)
        if locid and str(locid).isdigit():
            loc = MvcLocation.query.get(int(locid))
            if loc:
                loc_names.append(loc.name)
    sec("Appointment Assistance", [("Wants help", label("wants_appointment_help", c.v("wants_appointment_help"), lang)), ("Preferred locations", ", ".join(loc_names)),
                                   ("Initial Permit status", dl.initial_permit_state), ("Knowledge Test status", dl.knowledge_test_state), ("Road Test status", dl.road_test_state)])
    sec("Customer note", [("Note", c.v("notes_text"))])
    return {"sections": sections, "assessment": a, "flags": _flags(dl, c, a), "missing": service.missing_info(dl, lang)}


def _flags(dl, c, a):
    out = []

    def add(code, en, es, level="review"):
        out.append({"code": code, "en": en, "es": es, "level": level})

    if "no_primary_identity_document" in a["flags"]:
        add("no_primary_id", "No primary identity document selected", "No se seleccionó un documento de identidad primario")
    if "identity_documents_incomplete" in a["flags"]:
        add("id_incomplete", "Document set may be incomplete for the 6-Point ID requirement (verify against current MVC rules)", "El conjunto de documentos puede estar incompleto para el requisito de 6 puntos (verificar con las reglas actuales del MVC)")
    if "affidavit_review_required" in a["flags"]:
        add("affidavit_review", "AFFIDAVIT REVIEW REQUIRED — customer has neither SSN nor ITIN", "SE REQUIERE REVISIÓN DE DECLARACIÓN JURADA — el cliente no tiene SSN ni ITIN", "pro")
    if "ssn_itin_status_unclear" in a["flags"]:
        add("ssn_itin_unclear", "Customer is not sure about SSN/ITIN status", "El cliente no está seguro sobre su estado de SSN/ITIN")
    if "foreign_license_review" in a["flags"]:
        add("foreign_license", "Foreign driver license on file — review for Road Test determination (never auto-waived)", "Licencia extranjera en el expediente — revisar para la determinación del examen práctico (nunca se exime automáticamente)")
    if "foreign_license_expired" in a["flags"]:
        add("foreign_license_expired", "Customer says their foreign license is NOT currently valid", "El cliente dice que su licencia extranjera NO está vigente actualmente")
    if "nj_address_proof_needed" in a["flags"]:
        add("address_needed", "No NJ address proof document yet", "Todavía no hay documento de comprobante de dirección de NJ")
    if c.v("notes_text"):
        add("customer_note", "Customer left a note for OG", "El cliente dejó una nota para OG")
    if dl.initial_permit_state in ("scheduled", "obtained") and _loc_pref_changed_recently(dl):
        add("appointment_pref_changed_after_scheduled",
            "Customer changed their preferred MVC location AFTER an Initial Permit appointment was already recorded — the recorded appointment was NOT automatically changed",
            "El cliente cambió su ubicación preferida del MVC DESPUÉS de que ya se registró una cita del Initial Permit — la cita registrada NO se cambió automáticamente", "pro")
    return out


def _loc_pref_changed_recently(dl):
    """True if the most recently CLOSED revision (an Admin reopen or a Driver License self-edit) changed a
    preferred-location answer — item 36: a changed preference must never silently rewrite an appointment OG
    already recorded; it only ever surfaces as a flag for OG to review."""
    rev = next((r for r in reversed(dl.case.revisions) if r.resubmitted_at is not None), None)
    if rev is None:
        return False
    from app import case_revisions

    return any(c["key"] in ("loc1", "loc2", "loc3") for c in case_revisions.revision_changes(rev))
