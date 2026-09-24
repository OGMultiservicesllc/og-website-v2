"""OG Forms Builder engine: field-type metadata, the OG services list used by
Service Selector fields, conditional-rule evaluation, and submission-side
validation. Kept separate from the models so the (sizeable) FIELD_META table
and the rule evaluator are easy to find and unit-reason about on their own.
"""
import re
import secrets

# ---------------------------------------------------------------- field metadata

# input_kind drives which branch the field-macro templates render. Grouping
# many field_types onto a shared input_kind is what keeps the templates from
# needing 40+ near-duplicate branches.
FIELD_META = {
    # contact
    "first_name": {"label": "First Name", "input_kind": "text", "icon": "👤"},
    "last_name": {"label": "Last Name", "input_kind": "text", "icon": "👤"},
    "full_name": {"label": "Full Name", "input_kind": "text", "icon": "👤"},
    "email": {"label": "Email", "input_kind": "email", "icon": "✉"},
    "phone": {"label": "Phone", "input_kind": "tel", "icon": "☎"},
    "address": {"label": "Address", "input_kind": "text", "icon": "📍"},
    "address_multiline": {"label": "Multi-line Address", "input_kind": "textarea", "icon": "📍"},
    "company": {"label": "Company Name", "input_kind": "text", "icon": "🏢"},
    "job_title": {"label": "Job Title", "input_kind": "text", "icon": "🏢"},
    # general
    "short_answer": {"label": "Short Answer", "input_kind": "text", "icon": "✎"},
    "long_answer": {"label": "Long Answer", "input_kind": "textarea", "icon": "✎"},
    "number": {"label": "Number", "input_kind": "number", "icon": "#"},
    "url": {"label": "URL", "input_kind": "url", "icon": "🔗"},
    "file_upload": {"label": "File Upload", "input_kind": "file", "icon": "📎"},
    "record_list": {"label": "Records / timeline builder", "input_kind": "records", "icon": "🗂"},
    "signature": {"label": "Signature", "input_kind": "signature", "icon": "✒"},
    "rating": {"label": "Star Rating", "input_kind": "rating", "icon": "★"},
    "hidden": {"label": "Hidden Field", "input_kind": "hidden", "icon": "⋯"},
    # choices
    "single_choice": {"label": "Single Choice / Radio", "input_kind": "radio", "icon": "◉"},
    "multi_choice": {"label": "Multiple Choice / Checkboxes", "input_kind": "checkbox_group", "icon": "☑"},
    "dropdown": {"label": "Dropdown", "input_kind": "select", "icon": "▾"},
    "multi_dropdown": {"label": "Multi-select Dropdown", "input_kind": "multiselect", "icon": "▾"},
    "image_choice": {"label": "Image Choice", "input_kind": "image_choice", "icon": "🖼"},
    "yes_no": {"label": "Yes / No", "input_kind": "yes_no", "icon": "◐"},
    "consent": {"label": "Checkbox / Consent", "input_kind": "consent", "icon": "☑"},
    # dates
    "date": {"label": "Date", "input_kind": "date", "icon": "📅"},
    "datetime": {"label": "Date & Time", "input_kind": "datetime", "icon": "📅"},
    "time": {"label": "Time", "input_kind": "time", "icon": "🕐"},
    # services
    "service_single": {"label": "Service Selector", "input_kind": "service_single", "icon": "🗂"},
    "service_multi": {"label": "Multiple Service Selector", "input_kind": "service_multi", "icon": "🗂"},
    "appointment": {"label": "Appointment / Scheduling", "input_kind": "appointment", "icon": "🕐"},
    # pricing
    "price_fixed": {"label": "Fixed Price", "input_kind": "price_display", "icon": "$"},
    "price_custom": {"label": "Custom Price", "input_kind": "price_input", "icon": "$"},
    "donation": {"label": "Donation", "input_kind": "price_input", "icon": "$"},
    "product": {"label": "Product", "input_kind": "price_display", "icon": "$"},
    # layout
    "heading_h1": {"label": "Heading H1", "input_kind": "heading", "icon": "H1"},
    "heading_h2": {"label": "Heading H2", "input_kind": "heading", "icon": "H2"},
    "heading_h3": {"label": "Heading H3", "input_kind": "heading", "icon": "H3"},
    "paragraph": {"label": "Paragraph / Text", "input_kind": "paragraph", "icon": "¶"},
    "divider": {"label": "Divider", "input_kind": "divider", "icon": "—"},
    "spacer": {"label": "Spacer", "input_kind": "spacer", "icon": "␣"},
    "image": {"label": "Image", "input_kind": "image", "icon": "🖼"},
}

# Field types the visual builder auto-creates two fixed options for (mirrors
# the Quiz Builder's True/False pattern) instead of letting the admin edit
# an option list.
AUTO_OPTION_TYPES = ("yes_no",)


def field_label(field_type):
    return FIELD_META.get(field_type, {}).get("label", field_type)


def field_icon(field_type):
    return FIELD_META.get(field_type, {}).get("icon", "•")


def field_input_kind(field_type):
    return FIELD_META.get(field_type, {}).get("input_kind", "text")


# ---------------------------------------------------------------- OG services list

# A single, centrally-maintained list of OG's real top-level services (see
# CLAUDE.md's Services taxonomy) so admins building a Service Selector field
# never have to re-type service names by hand. Not a DB table — OG's public
# service pages are already hand-built content (app/service_pages.py), not
# database-driven, so this mirrors that same "plain Python data" precedent.
OG_SERVICES = [
    {"value": "certified_translation", "label_en": "Certified Translation", "label_es": "Traducción Certificada"},
    {"value": "taxes", "label_en": "Income Tax Preparation", "label_es": "Preparación de Impuestos"},
    {"value": "itin_caa", "label_en": "ITIN / CAA", "label_es": "ITIN / CAA"},
    {"value": "notary", "label_en": "Notary Public", "label_es": "Notario Público"},
    {"value": "immigration", "label_en": "Immigration Document Preparation", "label_es": "Preparación de Documentos de Inmigración"},
    {"value": "apostille", "label_en": "Apostille Assistance", "label_es": "Asistencia con Apostilla"},
    {"value": "nj_driver_license", "label_en": "NJ Driver License Assistance", "label_es": "Asistencia con Licencia de Conducir de NJ"},
    {"value": "wedding_officiant", "label_en": "Wedding Officiant", "label_es": "Oficiante de Bodas"},
    {"value": "document_services", "label_en": "Document & Office Services", "label_es": "Servicios de Documentos y Oficina"},
    {"value": "og_academy", "label_en": "OG Academy / Professional Courses", "label_es": "OG Academy / Cursos Profesionales"},
]


def og_service_label(value, lang):
    for service in OG_SERVICES:
        if service["value"] == value:
            return service["label_es"] if lang == "es" else service["label_en"]
    return value


# ---------------------------------------------------------------- naming / codes

def slugify(value):
    value = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return value or "form"


def internal_name_from_label(label, existing_names):
    base = re.sub(r"[^a-z0-9]+", "_", (label or "field").lower()).strip("_") or "field"
    name = base
    n = 2
    while name in existing_names:
        name = f"{base}_{n}"
        n += 1
    return name


def generate_submission_code():
    return "OGF-" + secrets.token_hex(3).upper()


# ---------------------------------------------------------------- validation

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[\d\s().+-]{7,20}$")


def is_valid_email(value):
    return bool(EMAIL_RE.match((value or "").strip()))


def is_valid_phone(value):
    return bool(PHONE_RE.match((value or "").strip()))


# ---------------------------------------------------------------- notifications

def queue_form_notifications(form, submission):
    """Hook point for admin-notification / client-confirmation emails.

    The CLIENT confirmation half is now wired to the real transactional email system (Transactional
    Email spec, item 9.4 "Application/service information submitted successfully") — only for a
    signed-in customer's own service intake (`submission.student_id` set), since an anonymous public
    Inquiry has no My Account to deep-link into and isn't in the spec's email catalog.

    The ADMIN-notification half (`notify_admin_enabled`/`notify_admin_email_list`) is deliberately left
    as a log-only stub: it is a staff operational notification, not one of the customer-facing
    transactional emails in the spec's catalog, and Admin already has first-class visibility into new
    submissions via Admin > Applications — wiring a real staff-email channel here would be new,
    unrequested scope. Wiring it later is still just swapping this one branch.
    """
    import logging

    logger = logging.getLogger("og_forms")
    if form.notify_admin_enabled and form.notify_admin_email_list:
        logger.info(
            "[forms] would notify admin(s) %s of submission %s for form %r",
            form.notify_admin_email_list, submission.code, form.name_admin,
        )
    if form.notify_client_enabled and submission.student_id:
        try:
            from app.email_service import send_transactional_email

            student = submission.student
            send_transactional_email(
                student, "service_submitted", (submission.language or student.preferred_language or "en"),
                ref={"kind": "form_submission", "id": submission.id}, related_type="form_submission", related_id=submission.id,
            )
        except Exception:  # noqa: BLE001
            logger.exception("[forms] service_submitted email failed to queue for submission %s", submission.code)


# ---------------------------------------------------------------- conditional logic

def _coerce_number(raw):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _condition_matches(operator, actual, expected):
    """`actual` is the raw submitted string (or list-of-strings for
    multi-value fields, already joined with a separator by the caller for
    the simple operators); `expected` is the rule's stored comparison value."""
    if operator == "is_empty":
        return not actual
    if operator == "is_not_empty":
        return bool(actual)
    if operator == "selected":
        return expected in (actual if isinstance(actual, list) else [actual])
    if operator == "not_selected":
        return expected not in (actual if isinstance(actual, list) else [actual])

    values = actual if isinstance(actual, list) else [actual or ""]
    if operator == "equals":
        return any(v == expected for v in values)
    if operator == "not_equals":
        return all(v != expected for v in values)
    if operator == "contains":
        return any(expected and expected in v for v in values)
    if operator == "not_contains":
        return all(not (expected and expected in v) for v in values)
    if operator in ("greater_than", "less_than"):
        expected_num = _coerce_number(expected)
        for v in values:
            actual_num = _coerce_number(v)
            if actual_num is None or expected_num is None:
                continue
            if operator == "greater_than" and actual_num > expected_num:
                return True
            if operator == "less_than" and actual_num < expected_num:
                return True
        return False
    return False


def evaluate_rule(rule, answers):
    """`answers` maps field_id -> submitted value (string, or list of
    strings for multi-value fields). Returns True if the rule's conditions
    are satisfied (respecting its all/any match_type)."""
    if not rule.conditions:
        return False
    results = []
    for condition in rule.conditions:
        actual = answers.get(condition.field_id)
        results.append(_condition_matches(condition.operator, actual, condition.value))
    return all(results) if rule.match_type == "all" else any(results)


def compute_field_effects(form, answers):
    """Applies every rule with a field target and returns
    {field_id: {"visible": bool, "required": bool-or-None}} overrides. A
    field absent from the dict uses its own default required/visible state.

    Several "show" rules aimed at one field combine with OR (any of them showing it
    is enough), which is how "show this when A and B, or when C" is expressed.
    A matching "hide" rule always hides."""
    effects = {}
    shows = {}
    for rule in form.rules:
        if rule.action not in ("show_field", "hide_field", "require_field", "optional_field"):
            continue
        if not rule.target_field_id:
            continue
        matched = evaluate_rule(rule, answers)
        entry = effects.setdefault(rule.target_field_id, {})
        if rule.action == "show_field":
            shows.setdefault(rule.target_field_id, []).append(matched)
        elif rule.action == "hide_field":
            if matched:
                entry["visible"] = False
        elif rule.action == "require_field":
            if matched:
                entry["required"] = True
        elif rule.action == "optional_field":
            if matched:
                entry["required"] = False
    for target, results in shows.items():
        entry = effects[target]
        entry["visible"] = any(results) and entry.get("visible", True)
    return effects


def compute_page_effects(form, answers):
    """Returns {page_id: {"visible": bool, "skip": bool}} from show_page /
    skip_page rules. Several show_page rules on one page combine with OR."""
    effects = {}
    shows = {}
    for rule in form.rules:
        if rule.action not in ("show_page", "skip_page"):
            continue
        if not rule.target_page_id:
            continue
        matched = evaluate_rule(rule, answers)
        entry = effects.setdefault(rule.target_page_id, {})
        if rule.action == "show_page":
            shows.setdefault(rule.target_page_id, []).append(matched)
        elif rule.action == "skip_page":
            entry["skip"] = bool(entry.get("skip")) or matched
    for target, results in shows.items():
        effects[target]["visible"] = any(results)
    return effects


def resolve_next_page(form, current_page, answers):
    """Applies goto_page / end_form rules scoped to the current page's
    fields, falling back to the natural next page in sort order."""
    ordered_pages = form.pages
    for rule in form.rules:
        if rule.action not in ("goto_page", "end_form"):
            continue
        if not evaluate_rule(rule, answers):
            continue
        rule_field_ids = {c.field_id for c in rule.conditions}
        current_field_ids = {f.id for f in current_page.fields}
        if not rule_field_ids & current_field_ids:
            continue
        if rule.action == "end_form":
            return None
        return rule.target_page

    index = ordered_pages.index(current_page)
    page_effects = compute_page_effects(form, answers)
    field_effects = compute_field_effects(form, answers)
    for page in ordered_pages[index + 1:]:
        if page_effects.get(page.id, {}).get("skip"):
            continue
        if page_effects.get(page.id, {}).get("visible") is False:
            continue
        # A step whose every field is currently hidden has nothing to ask.
        if page.fields and not any(field_effects.get(f.id, {}).get("visible", True) for f in page.fields):
            continue
        return page
    return None
