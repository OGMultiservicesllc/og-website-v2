"""Smart-intake engine: everything that depends on a customer's answers.

Pure functions over (form, submission/answers) — no request handling — so the same
logic drives the step screens, the progress bar, the review page, the final
server-side validation and the frozen snapshot saved with a submission.

Rules of the road:
  * The active PATH is derived from the current answers (skip/show/go-to rules and
    pages whose every field is hidden), never stored, so it always reflects the
    latest answers.
  * Only fields that are visible on that path count. Answers to fields a rule now
    hides are never part of the submission.
  * Nothing here decides eligibility or gives advice; it only applies the rules an
    administrator configured.
"""

import json
import re
from datetime import date, datetime

from app.forms_engine import compute_field_effects, is_valid_email, is_valid_phone, og_service_label, resolve_next_page
from app.models import SUBMISSION_STATUS_LABELS, SUBMISSION_STATUS_LABELS_ES


# ------------------------------------------------------------------ answers
def answers_for(submission):
    """{field_id: str | list[str]} from the saved values."""
    answers = {}
    if not submission:
        return answers
    for v in submission.values:
        raw = v.value_text
        try:
            parsed = json.loads(raw)
            answers[v.field_id] = parsed if isinstance(parsed, list) else raw
        except (TypeError, ValueError):
            answers[v.field_id] = raw
    return answers


def _is_empty(value):
    return value is None or value == "" or value == []


# ------------------------------------------------------------------ path / progress
def _has_visible_field(page, effects):
    return any(effects.get(f.id, {}).get("visible", True) for f in page.fields)


def first_page(form, answers):
    from app.forms_engine import compute_page_effects

    page_effects = compute_page_effects(form, answers)
    field_effects = compute_field_effects(form, answers)
    for page in form.pages:
        pe = page_effects.get(page.id, {})
        if pe.get("skip") or pe.get("visible") is False:
            continue
        if _has_visible_field(page, field_effects):
            return page
    return form.pages[0] if form.pages else None


def path_pages(form, answers):
    """The ordered pages this customer will actually see with the current answers."""
    page = first_page(form, answers)
    path, seen = [], set()
    while page is not None and page.id not in seen and len(path) < 200:
        path.append(page)
        seen.add(page.id)
        page = resolve_next_page(form, page, answers)
    return path


def progress_for(form, submission, current_page=None):
    """{step, total, percent, path}. `step` is the 1-based position of the current
    page on the active path; the total moves as answers change the path."""
    answers = answers_for(submission)
    path = path_pages(form, answers)
    if submission is not None and submission.is_complete:
        return {"step": len(path), "total": len(path), "percent": 100, "path": path}
    page = current_page
    if page is None and submission is not None:
        index = max(1, min(submission.current_page or 1, len(form.pages)))
        page = form.pages[index - 1]
    total = max(len(path), 1)
    if page in path:
        step = path.index(page) + 1
    else:  # a page the answers currently skip: show it in order without breaking the bar
        earlier = [p for p in path if p.sort_order < page.sort_order] if page else []
        step = min(len(earlier) + 1, total)
        total = max(total, step)
    percent = round((step - 1) / total * 100)
    return {"step": step, "total": total, "percent": percent, "path": path}


# ------------------------------------------------------------------ display
def _option_label(field, value, lang):
    opt = next((o for o in field.options if o.value == value), None)
    return opt.label(lang) if opt else value


def mask(value):
    value = str(value or "")
    return ("•" * max(len(value) - 4, 0) + value[-4:]) if len(value) > 4 else "•" * len(value)


def display_value(field, raw, lang, files=(), reveal=True):
    """Human-readable answer in `lang`. Sensitive fields are masked unless `reveal`."""
    if field.field_type in ("file_upload", "signature"):
        return ", ".join(f.original_filename for f in files)
    if _is_empty(raw):
        return ""
    if field.field_type == "record_list":
        from app.intake_records import display_records, parse_records

        return display_records(field, parse_records(raw), lang)
    if field.is_multi_value:
        try:
            selected = raw if isinstance(raw, list) else json.loads(raw)
        except (TypeError, ValueError):
            selected = [raw]
        if field.field_type == "service_multi":
            return ", ".join(og_service_label(v, lang) for v in selected)
        return ", ".join(_option_label(field, v, lang) for v in selected)
    if field.field_type in ("single_choice", "dropdown", "image_choice", "yes_no"):
        return _option_label(field, raw, lang)
    if field.field_type == "service_single":
        return og_service_label(raw, lang)
    if field.field_type == "consent":
        return ("Yes" if lang == "en" else "Sí") if raw == "accepted" else "No"
    if field.field_type == "date":
        try:
            return datetime.strptime(raw, "%Y-%m-%d").strftime("%m/%d/%Y")
        except ValueError:
            return raw
    if field.is_sensitive and not reveal:
        return mask(raw)
    return raw


# ------------------------------------------------------------------ validation of stored values
def validate_value(field, value, lang):
    """Format checks shared by live page validation and final validation.
    `value` is a non-empty string. Returns an error message or None."""
    en = lang == "en"
    kind = field.field_type
    if kind == "email" and not is_valid_email(value):
        return field.validation_message(lang) or ("Enter a valid email address." if en else "Ingresa un correo electrónico válido.")
    if kind == "phone" and not is_valid_phone(value):
        return field.validation_message(lang) or ("Enter a valid phone number." if en else "Ingresa un número de teléfono válido.")
    if kind == "number":
        try:
            number = float(value)
        except ValueError:
            return "Enter a valid number." if en else "Ingresa un número válido."
        if field.min_value is not None and number < field.min_value:
            return f"Must be at least {field.min_value:g}." if en else f"Debe ser al menos {field.min_value:g}."
        if field.max_value is not None and number > field.max_value:
            return f"Must be at most {field.max_value:g}." if en else f"Debe ser como máximo {field.max_value:g}."
    if kind == "date":
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return "Enter a valid date." if en else "Ingresa una fecha válida."
        if field.date_rule == "past" and parsed > date.today():
            return field.validation_message(lang) or ("This date can't be in the future." if en else "Esta fecha no puede ser futura.")
        if field.date_rule == "future" and parsed < date.today():
            return field.validation_message(lang) or ("This date must be in the future." if en else "Esta fecha debe ser futura.")
        if parsed.year < 1900:
            return "Enter a valid date." if en else "Ingresa una fecha válida."
    if field.min_length and len(value) < field.min_length:
        return f"Must be at least {field.min_length} characters." if en else f"Debe tener al menos {field.min_length} caracteres."
    if field.max_length and len(value) > field.max_length:
        return f"Must be at most {field.max_length} characters." if en else f"Debe tener como máximo {field.max_length} caracteres."
    if field.pattern:
        try:
            ok = re.fullmatch(field.pattern, value, re.IGNORECASE) is not None
        except re.error:
            ok = True  # a broken admin pattern must not lock customers out
        if not ok:
            return field.validation_message(lang) or ("That doesn't look right. Please check the format." if en else "Esto no parece correcto. Revisa el formato.")
    return None


# ------------------------------------------------------------------ review
def _files_by_field(submission):
    by_field = {}
    for f in submission.files:
        by_field.setdefault(f.field_id, []).append(f)
    return by_field


def review_sections(form, submission, lang, reveal=False):
    """The active answers grouped by step, with what is still missing.
    [{page, number, title, items:[{field, label, value, files, missing, error}], missing_count}]"""
    answers = answers_for(submission)
    effects = compute_field_effects(form, answers)
    files = _files_by_field(submission)
    from app.shared_blocks import is_kept, is_system, review_target

    sections = []
    path = path_pages(form, answers)
    on_path = {p.id for p in path}
    # a shared block the applicant confirmed ("Everything is correct") skips its edit step, but its values still belong in Review
    extra = [p for p in form.pages if p.id not in on_path and any(is_kept(f) and not is_system(f) and not _is_empty(answers.get(f.id)) for f in p.fields)]
    shown = sorted(path + extra, key=lambda p: p.sort_order) if extra else path
    for number, page in enumerate(shown, 1):
        items, missing_count = [], 0
        for field in page.fields:
            if field.is_content_only or is_system(field):
                continue
            hidden = not effects.get(field.id, {}).get("visible", True)
            if hidden and not (is_kept(field) and not _is_empty(answers.get(field.id))):
                continue  # a confirmed shared copy stays visible in Review/Admin even while its edit step is skipped
            raw = answers.get(field.id)
            field_files = files.get(field.id, [])
            required = effects.get(field.id, {}).get("required")
            required = field.required if required is None else required
            has_value = bool(field_files) if field.field_type in ("file_upload", "signature") else not _is_empty(raw)
            missing = bool(required and not has_value)
            error = None
            if has_value and not missing and isinstance(raw, str) and field.field_type not in ("file_upload", "signature", "consent"):
                error = validate_value(field, raw, lang)
            elif has_value and field.field_type == "record_list":
                from app.intake_records import parse_records, records_error

                error = records_error(field, parse_records(raw), lang)
            if missing or error:
                missing_count += 1
            items.append({
                "field": field,
                "label": field.label(lang) or field.internal_name,
                "value": display_value(field, raw, lang, field_files, reveal=reveal),
                "files": field_files,
                "missing": missing,
                "error": error,
                "required": bool(required),
            })
        if items:
            target = (review_target(form, page) or page) if page.id not in on_path else page
            sections.append({"page": page, "target": target, "number": number, "title": page.title(lang) or f"Step {number}", "items": items, "missing_count": missing_count})
    return sections


def problems(sections):
    """[(section, item)] that block final submission."""
    return [(s, i) for s in sections for i in s["items"] if i["missing"] or i["error"]]


# ------------------------------------------------------------------ snapshot
def build_snapshot(form, submission):
    """Frozen, self-contained copy of what the customer answered (both languages),
    so later edits to the form never reinterpret this submission."""
    answers = answers_for(submission)
    sections = []
    for section in review_sections(form, submission, "en", reveal=True):
        items = []
        for it in section["items"]:
            field = it["field"]
            raw = answers.get(field.id)
            items.append({
                "field_id": field.id,
                "internal_name": field.internal_name,
                "source_ref": field.source_ref,
                "sources": field.sources(form),
                "type": field.field_type,
                "sensitive": bool(field.is_sensitive),
                "private": bool(field.config_json and '"private"' in field.config_json),
                "label_en": field.label("en"),
                "label_es": field.label("es"),
                "value": raw,
                "display_en": display_value(field, raw, "en", it["files"]),
                "display_es": display_value(field, raw, "es", it["files"]),
                "files": [{"id": f.id, "name": f.original_filename, "size": f.size_bytes} for f in it["files"]],
            })
        sections.append({"title_en": section["page"].title("en"), "title_es": section["page"].title("es"), "items": items,
                         "context": section["page"].context_key, "group": section["page"].group_key})
    return json.dumps({
        "form": {
            "id": form.id, "name": form.name_admin, "version": form.version,
            "source_form_name": form.source_form_name, "source_edition": form.source_edition,
        },
        "sections": sections,
    }, ensure_ascii=False)


def load_snapshot(submission):
    if not submission or not submission.snapshot_json:
        return None
    try:
        return json.loads(submission.snapshot_json)
    except ValueError:
        return None


# ------------------------------------------------------------------ status
def status_key(submission):
    if not submission.is_complete:
        return "reopened" if submission.status == "reopened" else "draft"
    return submission.status


def status_label(submission, lang="en"):
    labels = SUBMISSION_STATUS_LABELS_ES if lang == "es" else SUBMISSION_STATUS_LABELS
    return labels.get(status_key(submission), submission.status)


# ------------------------------------------------------------------ "who is this step about"
def context_map(form, submission, lang):
    """{context_key: {title, subtitle, name, tone, icon}} for intakes whose steps are about
    different people (e.g. I-130 petitioner vs beneficiary). Configured in
    Form.features["contexts"]; `context_names` lists the fields that hold each person's name."""
    feats = form.features
    contexts = feats.get("contexts") or {}
    if not contexts:
        return {}
    named = {}
    if submission is not None:
        from app.intake_completeness import named_answers

        named = named_answers(form, submission)
    out = {}
    for key, cfg in contexts.items():
        fields = (feats.get("context_names") or {}).get(key) or []
        name = " ".join(str(named.get(f) or "").strip() for f in fields).strip()
        if not name and (feats.get("context_roles") or {}).get(key) and submission is not None:
            from app.cases import role_person

            person = role_person(submission, feats["context_roles"][key])
            name = person.full_name if person is not None else ""
        out[key] = {"key": key, "title": cfg["title"][lang], "subtitle": cfg["subtitle"][lang], "name": name,
                    "tone": cfg.get("tone", "accent"), "icon": cfg.get("icon", "person")}
    return out
