"""Human-friendly summaries of a Consent to Travel case: the customer's Review (masked/neutral wording, no
legal conclusion) and the structured Admin summary. No AI, generated from structured data only."""

from app.consent_travel import docs, people, pricing, service
from app.consent_travel.config import CONFIG, LOCATIONS
from app.tax.questions import pick


def _t(en, es, lang):
    return es if lang == "es" else en


def label(key, value, lang):
    q = CONFIG.index().get(key)
    if value in (None, "", []):
        return ""
    if q is None:
        return str(value)
    opts = q.options if not callable(q.options) else []
    o = next((x for x in opts if x.value == value), None)
    return (f"{o.emoji} " if o and o.emoji else "") + pick(o.label, lang) if o else str(value)


def _line(lab, val):
    return {"label": lab, "value": val} if val not in (None, "", []) else None


def _layover_lines(c, prefix, lang):
    en = lang != "es"
    n = c.v(f"{prefix}_layovers")
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        n = 0
    out = []
    for i in range(1, n + 1):
        out.append(_line(("Layover %d" % i) if en else ("Escala %d" % i), f"{c.v(f'{prefix}_lo{i}_city') or ''} ({c.v(f'{prefix}_lo{i}_airport') or ''})"))
    return out


def review_cards(ct, lang):
    en = lang != "es"
    c = service.ctx(ct, lang)
    cards = []

    mother = people.owner_for(ct, "mother")
    father = people.owner_for(ct, "father_traveler")
    third = people.owner_for(ct, "third_traveler")
    who_lines = [_line("With whom" if en else "Con quién viaja", label("traveling_with", c.v("traveling_with"), lang))]
    cards.append({"key": "who", "icon": "🧭", "title": _t("Who Travels", "Quién Viaja", lang), "lines": [x for x in who_lines if x], "edit": "who_travels"})

    child_lines = []
    for r in ct.children:
        info = people.info(ct, r)
        name = f"{info.get('given') or ''} {info.get('family') or ''}".strip() or f"#{r.id}"
        father_on = label("father_on_cert", r.data.get("father_on_cert"), lang) if c.v("traveling_with") in ("mother", "other") else ""
        child_lines.append(_line(name, father_on or ("—")))
    cards.append({"key": "children", "icon": "🧒", "title": _t("Children Traveling", "Menores que Viajan", lang), "lines": [x for x in child_lines if x] or [_line(None, _t("None added yet", "Ninguno agregado aún", lang))], "edit": "children"})

    groups = service.groups_for(ct)
    consent_lines = []
    for i, g in enumerate(groups, 1):
        names = ", ".join(ch["name"] for ch in g["children"])
        if not g["consenting"]:
            consent_lines.append(_line(names, _t("No additional consent required", "No se requiere consentimiento adicional", lang)))
            continue
        consenters = []
        for pid in g["consenting"]:
            p = people.person_by_id(ct, pid)
            if p is not None:
                consenters.append(f"{p.given_name or ''} {p.family_name or ''}".strip())
        consent_lines.append(_line(names, ", ".join(consenters)))
    cards.append({"key": "consent", "icon": "✍️", "title": _t("Who Consents", "Quién Consiente", lang), "lines": [x for x in consent_lines if x] or [_line(None, _t("Add a child to see this.", "Agrega un menor para ver esto.", lang))], "edit": "children"})

    contact_lines = [_line("Phone" if en else "Teléfono", c.v("phone")), _line("WhatsApp OK?" if en else "¿WhatsApp OK?", label("wa_consent", c.v("wa_consent"), lang))]
    cards.append({"key": "contact", "icon": "📞", "title": _t("Contact", "Contacto", lang), "lines": [x for x in contact_lines if x], "edit": "contact"})

    out_lines = [_line("Departure date" if en else "Fecha de salida", c.v("out_date")), _line("From" if en else "Desde", f"{c.v('out_dep_city') or ''} ({c.v('out_dep_airport') or ''})"),
                 _line("To" if en else "Hasta", f"{c.v('out_dest_city') or ''}, {c.v('out_dest_country') or ''} ({c.v('out_arr_airport') or ''})")] + _layover_lines(c, "out", lang)
    cards.append({"key": "itinerary_out", "icon": "🛫", "title": _t("Departure Flight", "Vuelo de Ida", lang), "lines": [x for x in out_lines if x], "edit": "itinerary_out"})

    if c.v("has_return") == "yes":
        ret_lines = [_line("Return date" if en else "Fecha de regreso", c.v("ret_date")), _line("From" if en else "Desde", f"{c.v('ret_dep_city') or ''} ({c.v('ret_dep_airport') or ''})"),
                     _line("Final destination" if en else "Destino final", f"{c.v('ret_dest_city') or ''} ({c.v('ret_dest_airport') or ''})")] + _layover_lines(c, "ret", lang)
    else:
        ret_lines = [_line(None, _t("No return flight", "Sin vuelo de regreso", lang))]
    cards.append({"key": "itinerary_return", "icon": "🛬", "title": _t("Return Flight", "Vuelo de Regreso", lang), "lines": [x for x in ret_lines if x], "edit": "has_return"})

    loc = LOCATIONS.get(c.v("location") or "", {})
    loc_lines = [_line(None, loc.get(lang if lang in ("en", "es") else "en")), _line(None, loc.get("address")), _line(None, _t("By confirmed appointment only.", "Únicamente con cita confirmada.", lang))]
    cards.append({"key": "location", "icon": "📍", "title": _t("Notarization Location", "Lugar de Notarización", lang), "lines": [x for x in loc_lines if x], "edit": "location"})

    price = pricing.customer_view(ct, groups, lang)
    price_lines = [_line(l["label"], l["amount"] or _t("—", "—", lang)) for l in price.get("lines", [])]
    price_lines.append(_line(_t("Estimated total", "Total estimado", lang), price.get("subtotal") if price["state"] != "confirmed" else price.get("final")))
    cards.append({"key": "price", "icon": "💲", "title": _t("Estimated Price", "Precio Estimado", lang), "lines": [x for x in price_lines if x], "edit": "price"})

    return cards


def admin_summary(ct):
    lang = "en"
    c = service.ctx(ct, lang)
    sections = []

    def sec(title, rows):
        rows = [r for r in rows if r and r[1] not in (None, "", [])]
        sections.append({"title": title, "rows": rows})

    mother = people.owner_for(ct, "mother")
    father = people.owner_for(ct, "father_traveler")
    third = people.owner_for(ct, "third_traveler")
    sec("Trip", [("Traveling with", label("traveling_with", c.v("traveling_with"), lang)), ("Customer's role", label("your_role", c.v("your_role"), lang))])
    sec("Mother", [("Name", f"{mother.given_name} {mother.family_name}" if mother else None)])
    sec("Father (traveling)", [("Name", f"{father.given_name} {father.family_name}" if father else None)]) if c.v("traveling_with") == "father" else None
    sec("Accompanying Person", [("Name", f"{third.given_name} {third.family_name}" if third else None), ("Relationship", c.v("th_relationship"))]) if c.v("traveling_with") == "other" else None

    child_rows = []
    for r in ct.children:
        info = people.info(ct, r)
        name = f"{info.get('given') or ''} {info.get('family') or ''}".strip()
        father_pid = r.data.get("father_pid")
        fp = people.person_by_id(ct, father_pid) if father_pid else None
        flag = " ⚠️ UNSURE — OG REVIEW" if r.data.get("father_on_cert") == "unsure" else ""
        child_rows.append((name, f"father_on_cert={r.data.get('father_on_cert')}, father={fp.given_name + ' ' + fp.family_name if fp else '—'}{flag}"))
    sec("Children", child_rows)

    groups = service.groups_for(ct)
    doc_rows = []
    for i, g in enumerate(groups, 1):
        names = ", ".join(ch["name"] for ch in g["children"])
        consenters = ", ".join(f"{p.given_name} {p.family_name}" for p in (people.person_by_id(ct, pid) for pid in g["consenting"]) if p is not None)
        doc_rows.append((f"Group {i}" if g["consenting"] else f"Group {i} (no document)", f"{names} — consenting: {consenters or 'none'}"))
    sec("Document Grouping", doc_rows)

    sec("Contact", [("Phone", c.v("phone")), ("WhatsApp OK", label("wa_consent", c.v("wa_consent"), lang))])
    sec("Notarization", [("Location", label("location", c.v("location"), lang))])
    sec("Itinerary — Departure", [("Date", c.v("out_date")), ("From", f"{c.v('out_dep_city')} ({c.v('out_dep_airport')})"), ("To", f"{c.v('out_dest_city')}, {c.v('out_dest_country')} ({c.v('out_arr_airport')})"), ("Layovers", c.v("out_layovers"))])
    if c.v("has_return") == "yes":
        sec("Itinerary — Return", [("Date", c.v("ret_date")), ("From", f"{c.v('ret_dep_city')} ({c.v('ret_dep_airport')})"), ("To", f"{c.v('ret_dest_city')} ({c.v('ret_dest_airport')})"), ("Layovers", c.v("ret_layovers"))])
    else:
        sec("Itinerary — Return", [("Return flight", "No")])
    sec("Note", [("Customer note", c.v("notes_text"))])
    q = ct.current_quote
    sec("Price", [("System estimate", pricing.fmt(q.system_estimate_cents) if q else None), ("Confirmed total", pricing.fmt(q.final_total_cents) if q and q.final_total_cents else None), ("Status", ct.price_status)])
    return {"sections": [s for s in sections if s]}
