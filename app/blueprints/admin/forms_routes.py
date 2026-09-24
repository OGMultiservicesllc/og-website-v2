import csv
import io
import json
import re
from datetime import datetime

from flask import abort, flash, redirect, render_template, request, session, url_for, Response

from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.forms_engine import (
    AUTO_OPTION_TYPES,
    FIELD_META,
    OG_SERVICES,
    field_label,
    generate_submission_code,
    internal_name_from_label,
    og_service_label,
    slugify,
)
from app.models import (
    ConditionalRule,
    FieldOption,
    Form,
    FormField,
    FormPage,
    FormSubmission,
    RuleCondition,
    SubmissionFile,
    SubmissionNote,
)
from app.models import (
    CONDITION_OPERATORS,
    CONTENT_ONLY_TYPES,
    FIELD_CATEGORIES,
    FORM_FIELD_TYPES,
    FORM_TYPES,
    RULE_ACTIONS,
    SUBMISSION_STATUSES,
)
from app.uploads import course_media_full_path, delete_course_media, save_course_media

FORM_TEMPLATES = {
    "blank": {"name": "Blank Form", "pages": [{"title_en": "Page 1", "title_es": "Página 1", "fields": []}]},
    "request_quote": {
        "name": "Request a Quote",
        "pages": [
            {"title_en": "Contact", "title_es": "Contacto", "fields": ["full_name", "email", "phone"]},
            {"title_en": "Service", "title_es": "Servicio", "fields": ["service_single", "long_answer"]},
        ],
    },
    "contact": {
        "name": "Contact Form",
        "pages": [{"title_en": "Contact", "title_es": "Contacto", "fields": ["full_name", "email", "phone", "long_answer"]}],
    },
    "document_upload": {
        "name": "Document Upload",
        "pages": [{"title_en": "Upload", "title_es": "Subir", "fields": ["full_name", "email", "file_upload"]}],
    },
    "service_request": {
        "name": "Service Request",
        "pages": [{"title_en": "Request", "title_es": "Solicitud", "fields": ["full_name", "email", "phone", "service_single", "long_answer"]}],
    },
    "appointment_request": {
        "name": "Appointment Request",
        "pages": [{"title_en": "Appointment", "title_es": "Cita", "fields": ["full_name", "email", "phone", "service_single", "appointment"]}],
    },
}


# ---------------------------------------------------------------- helpers

def _unique_slug(base_slug, form_id=None):
    slug = base_slug
    n = 2
    while True:
        query = Form.query.filter_by(slug=slug)
        if form_id:
            query = query.filter(Form.id != form_id)
        if not query.first():
            return slug
        slug = f"{base_slug}-{n}"
        n += 1


def _next_sort_order(items):
    return (max((i.sort_order for i in items), default=0)) + 1


def _swap_sort_order(siblings, item, direction):
    index = siblings.index(item)
    if direction == "up" and index > 0:
        other = siblings[index - 1]
    elif direction == "down" and index < len(siblings) - 1:
        other = siblings[index + 1]
    else:
        return
    item.sort_order, other.sort_order = other.sort_order, item.sort_order
    db.session.commit()


def _default_field_kwargs(field_type):
    kwargs = {"field_type": field_type}
    if field_type == "email":
        kwargs["required"] = True
    if field_type in ("price_fixed", "product"):
        kwargs["price_amount"] = 0
    if field_type == "file_upload":
        kwargs["max_files"] = 1
        kwargs["max_file_size_mb"] = 10
    return kwargs


def _add_field(page, field_type, label_en=None):
    label_en = label_en or field_label(field_type)
    existing_names = {f.internal_name for f in page.form.all_fields}
    field = FormField(
        page_id=page.id,
        sort_order=_next_sort_order(page.fields),
        internal_name=internal_name_from_label(label_en, existing_names),
        label_en=label_en,
        label_es=label_en,
        **_default_field_kwargs(field_type),
    )
    db.session.add(field)
    db.session.flush()

    if field_type == "yes_no":
        db.session.add(FieldOption(field_id=field.id, sort_order=0, value="yes", label_en="Yes", label_es="Sí"))
        db.session.add(FieldOption(field_id=field.id, sort_order=1, value="no", label_en="No", label_es="No"))
    elif field_type in ("single_choice", "multi_choice", "dropdown", "multi_dropdown"):
        db.session.add(FieldOption(field_id=field.id, sort_order=0, value="option_1", label_en="Option 1", label_es="Opción 1"))
        db.session.add(FieldOption(field_id=field.id, sort_order=1, value="option_2", label_en="Option 2", label_es="Opción 2"))
    return field


def _build_form_from_template(template_key, name_admin, form_type="inquiry"):
    template = FORM_TEMPLATES.get(template_key, FORM_TEMPLATES["blank"])
    slug = _unique_slug(slugify(name_admin))
    form = Form(
        slug=slug,
        name_admin=name_admin,
        form_type=form_type if form_type in FORM_TYPES else "inquiry",
        title_en=name_admin,
        title_es=name_admin,
    )
    db.session.add(form)
    db.session.flush()

    for page_index, page_def in enumerate(template["pages"]):
        page = FormPage(
            form_id=form.id, sort_order=page_index,
            title_en=page_def.get("title_en"), title_es=page_def.get("title_es"),
        )
        db.session.add(page)
        db.session.flush()
        for field_type in page_def.get("fields", []):
            _add_field(page, field_type)

    if not form.pages:
        db.session.add(FormPage(form_id=form.id, sort_order=0, title_en="Page 1", title_es="Página 1"))

    db.session.commit()
    return form


# ---------------------------------------------------------------- forms list / lifecycle

@admin_bp.route("/forms")
@admin_required
def forms_list():
    forms = Form.query.order_by(Form.updated_at.desc()).all()
    submission_counts = dict(
        db.session.query(FormSubmission.form_id, db.func.count(FormSubmission.id))
        .filter(FormSubmission.is_complete.is_(True))
        .group_by(FormSubmission.form_id)
        .all()
    )
    new_counts = dict(
        db.session.query(FormSubmission.form_id, db.func.count(FormSubmission.id))
        .filter(FormSubmission.status == "new", FormSubmission.is_complete.is_(True))
        .group_by(FormSubmission.form_id)
        .all()
    )
    draft_counts = dict(
        db.session.query(FormSubmission.form_id, db.func.count(FormSubmission.id))
        .filter(FormSubmission.is_complete.is_(False), FormSubmission.student_id.isnot(None))
        .group_by(FormSubmission.form_id)
        .all()
    )
    return render_template(
        "admin/forms_list.html", forms=forms, submission_counts=submission_counts, new_counts=new_counts,
        draft_counts=draft_counts, templates=FORM_TEMPLATES,
    )


@admin_bp.route("/forms/new", methods=["POST"])
@admin_required
def form_new():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    name_admin = request.form.get("name_admin", "").strip() or "Untitled Form"
    template_key = request.form.get("template", "blank")
    form = _build_form_from_template(template_key, name_admin, request.form.get("form_type", "inquiry"))
    flash("Form created.", "success")
    return redirect(url_for("admin.form_builder", form_id=form.id))


def _clone_form(source, *, name_admin, slug, version=1, previous_version_id=None):
    """Deep copy of a form (pages, fields, options, rules) as a new Draft."""
    clone = Form(
        slug=slug,
        name_admin=name_admin,
        status="draft",
        form_type=source.form_type,
        source_form_name=source.source_form_name, source_edition=source.source_edition,
        version=version, previous_version_id=previous_version_id,
        features_json=source.features_json,
        title_en=source.title_en, title_es=source.title_es,
        description_en=source.description_en, description_es=source.description_es,
        submit_label_en=source.submit_label_en, submit_label_es=source.submit_label_es,
        success_action=source.success_action,
        success_message_en=source.success_message_en, success_message_es=source.success_message_es,
        redirect_url=source.redirect_url,
        notify_admin_enabled=source.notify_admin_enabled, notify_admin_emails=source.notify_admin_emails,
        notify_client_enabled=source.notify_client_enabled,
        confirmation_subject_en=source.confirmation_subject_en, confirmation_subject_es=source.confirmation_subject_es,
        confirmation_body_en=source.confirmation_body_en, confirmation_body_es=source.confirmation_body_es,
        accent_color=source.accent_color, button_style=source.button_style, border_radius=source.border_radius,
        spacing=source.spacing, background_style=source.background_style, show_progress=source.show_progress,
    )
    db.session.add(clone)
    db.session.flush()

    page_map = {}
    field_map = {}
    for page in source.pages:
        new_page = FormPage(
            form_id=clone.id, sort_order=page.sort_order,
            title_en=page.title_en, title_es=page.title_es,
            description_en=page.description_en, description_es=page.description_es,
            group_key=page.group_key, context_key=page.context_key,
        )
        db.session.add(new_page)
        db.session.flush()
        page_map[page.id] = new_page

        for field in page.fields:
            new_field = FormField(
                page_id=new_page.id, sort_order=field.sort_order,
                field_type=field.field_type, internal_name=field.internal_name,
                label_en=field.label_en, label_es=field.label_es,
                placeholder_en=field.placeholder_en, placeholder_es=field.placeholder_es,
                help_text_en=field.help_text_en, help_text_es=field.help_text_es,
                validation_message_en=field.validation_message_en, validation_message_es=field.validation_message_es,
                required=field.required, default_value=field.default_value, width=field.width,
                min_value=field.min_value, max_value=field.max_value,
                min_length=field.min_length, max_length=field.max_length,
                allowed_file_types=field.allowed_file_types, max_file_size_mb=field.max_file_size_mb,
                max_files=field.max_files,
                content_en=field.content_en, content_es=field.content_es,
                image_filename=field.image_filename,
                price_amount=field.price_amount, price_currency=field.price_currency,
                service_source=field.service_source, admin_notes=field.admin_notes,
                source_ref=field.source_ref, source_note=field.source_note, source_form=field.source_form, source_edition=field.source_edition,
                source_extra_json=field.source_extra_json, is_sensitive=field.is_sensitive,
                pattern=field.pattern, date_rule=field.date_rule,
                help_detail_en=field.help_detail_en, help_detail_es=field.help_detail_es,
                help_where_en=field.help_where_en, help_where_es=field.help_where_es, config_json=field.config_json,
            )
            db.session.add(new_field)
            db.session.flush()
            field_map[field.id] = new_field
            for option in field.options:
                db.session.add(FieldOption(
                    field_id=new_field.id, sort_order=option.sort_order,
                    value=option.value, label_en=option.label_en, label_es=option.label_es,
                    image_filename=option.image_filename,
                ))

    for rule in source.rules:
        new_rule = ConditionalRule(
            form_id=clone.id, sort_order=rule.sort_order, match_type=rule.match_type, action=rule.action,
            target_field_id=field_map[rule.target_field_id].id if rule.target_field_id in field_map else None,
            target_page_id=page_map[rule.target_page_id].id if rule.target_page_id in page_map else None,
        )
        db.session.add(new_rule)
        db.session.flush()
        for condition in rule.conditions:
            if condition.field_id not in field_map:
                continue
            db.session.add(RuleCondition(
                rule_id=new_rule.id, field_id=field_map[condition.field_id].id,
                operator=condition.operator, value=condition.value,
            ))

    return clone


@admin_bp.route("/forms/<int:form_id>/duplicate", methods=["POST"])
@admin_required
def form_duplicate(form_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    source = Form.query.get_or_404(form_id)
    clone = _clone_form(source, name_admin=source.name_admin + " (Copy)", slug=_unique_slug(slugify(source.name_admin + "-copy")))
    db.session.commit()
    flash(f"Duplicated as “{clone.name_admin}”.", "success")
    return redirect(url_for("admin.form_builder", form_id=clone.id))


@admin_bp.route("/forms/<int:form_id>/new-version", methods=["POST"])
@admin_required
def form_new_version(form_id):
    """Start the next version of a form as a Draft. Submissions already completed stay
    tied to the version they were completed under; publishing the new version points
    the service at it (see form_status)."""
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    source = Form.query.get_or_404(form_id)
    latest = Form.query.filter_by(previous_version_id=source.id).first()
    if latest:
        flash(f"Version {latest.version} already exists for this form.", "error")
        return redirect(url_for("admin.form_builder", form_id=latest.id))
    next_version = (source.version or 1) + 1
    base = re.sub(r"-v\d+$", "", source.slug)
    clone = _clone_form(
        source, name_admin=re.sub(r" \(v\d+\)$", "", source.name_admin) + f" (v{next_version})",
        slug=_unique_slug(f"{base}-v{next_version}"), version=next_version, previous_version_id=source.id,
    )
    db.session.commit()
    flash(f"Version {next_version} created as a draft. Publishing it will make new applications use it; completed ones keep version {source.version}.", "success")
    return redirect(url_for("admin.form_builder", form_id=clone.id))


@admin_bp.route("/forms/<int:form_id>/status", methods=["POST"])
@admin_required
def form_status(form_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    form = Form.query.get_or_404(form_id)
    status = request.form.get("status")
    if status in ("draft", "published", "archived"):
        if status == "published" and form.status != "published":
            form.published_at = datetime.utcnow()
            if form.previous_version_id:
                from app.models import Service

                moved = Service.query.filter_by(form_id=form.previous_version_id).all()
                for svc in moved:
                    svc.form_id = form.id
                if moved:
                    flash(f"{len(moved)} service(s) now start applications on version {form.version}. Drafts already in progress finish on the version they began with.", "success")
        form.status = status
        db.session.commit()
        flash(f"Form marked {status}.", "success")
    return redirect(request.form.get("next") or url_for("admin.forms_list"))


@admin_bp.route("/forms/<int:form_id>/delete", methods=["POST"])
@admin_required
def form_delete(form_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    form = Form.query.get_or_404(form_id)
    for field in form.all_fields:
        if field.image_filename:
            delete_course_media(field.image_filename)
        for option in field.options:
            if option.image_filename:
                delete_course_media(option.image_filename)
    for submission in form.submissions:
        for f in submission.files:
            delete_course_media(f.stored_filename)
    db.session.delete(form)
    db.session.commit()
    flash("Form deleted.", "success")
    return redirect(url_for("admin.forms_list"))


# ---------------------------------------------------------------- builder

@admin_bp.route("/forms/<int:form_id>", methods=["GET"])
@admin_required
def form_builder(form_id):
    form = Form.query.get_or_404(form_id)
    if not form.pages:
        db.session.add(FormPage(form_id=form.id, sort_order=0, title_en="Page 1", title_es="Página 1"))
        db.session.commit()

    page_id = request.args.get("page", type=int)
    page = FormPage.query.get(page_id) if page_id else None
    if not page or page.form_id != form.id:
        page = form.pages[0]

    field_id = request.args.get("field", type=int)
    selected_field = FormField.query.get(field_id) if field_id else None
    if selected_field and selected_field.page_id != page.id:
        selected_field = None

    lang = request.args.get("lang", "en")
    if lang not in ("en", "es"):
        lang = "en"
    device = request.args.get("device", "desktop")

    return render_template(
        "admin/forms/builder.html",
        form=form, page=page, selected_field=selected_field, lang=lang, device=device,
        field_categories=FIELD_CATEGORIES, field_meta=FIELD_META,
        content_only_types=CONTENT_ONLY_TYPES, auto_option_types=AUTO_OPTION_TYPES,
        condition_operators=CONDITION_OPERATORS, rule_actions=RULE_ACTIONS,
        og_services=OG_SERVICES,
    )


@admin_bp.route("/forms/<int:form_id>/settings", methods=["POST"])
@admin_required
def form_settings_update(form_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    form = Form.query.get_or_404(form_id)
    f = request.form

    form.name_admin = f.get("name_admin", form.name_admin).strip() or form.name_admin
    if f.get("form_type") in FORM_TYPES:
        form.form_type = f.get("form_type")
    form.source_form_name = f.get("source_form_name", "").strip()[:40] or None
    form.source_edition = f.get("source_edition", "").strip()[:40] or None
    form.title_en = f.get("title_en", "").strip() or form.title_en
    form.title_es = f.get("title_es", "").strip() or form.title_es
    form.description_en = f.get("description_en", "").strip()
    form.description_es = f.get("description_es", "").strip()
    form.submit_label_en = f.get("submit_label_en", "").strip() or "Submit"
    form.submit_label_es = f.get("submit_label_es", "").strip() or "Enviar"

    form.success_action = "redirect" if f.get("success_action") == "redirect" else "message"
    form.success_message_en = f.get("success_message_en", "").strip()
    form.success_message_es = f.get("success_message_es", "").strip()
    form.redirect_url = f.get("redirect_url", "").strip() or None

    form.notify_admin_enabled = f.get("notify_admin_enabled") == "on"
    form.notify_admin_emails = f.get("notify_admin_emails", "").strip()
    form.notify_client_enabled = f.get("notify_client_enabled") == "on"
    form.confirmation_subject_en = f.get("confirmation_subject_en", "").strip()
    form.confirmation_subject_es = f.get("confirmation_subject_es", "").strip()
    form.confirmation_body_en = f.get("confirmation_body_en", "").strip()
    form.confirmation_body_es = f.get("confirmation_body_es", "").strip()

    accent = f.get("accent_color", "").strip()
    import re
    form.accent_color = accent if re.fullmatch(r"#[0-9a-fA-F]{6}", accent) else None
    form.button_style = f.get("button_style") if f.get("button_style") in ("solid", "outline") else "solid"
    form.border_radius = f.get("border_radius") if f.get("border_radius") in ("sharp", "rounded", "pill") else "rounded"
    form.spacing = f.get("spacing") if f.get("spacing") in ("compact", "comfortable") else "comfortable"
    form.background_style = f.get("background_style") if f.get("background_style") in ("card", "transparent") else "card"
    form.show_progress = f.get("show_progress") == "on"

    db.session.commit()
    flash("Form settings saved.", "success")
    return redirect(url_for("admin.form_builder", form_id=form.id))


# ---------------------------------------------------------------- pages

@admin_bp.route("/forms/<int:form_id>/pages/new", methods=["POST"])
@admin_required
def form_page_new(form_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    form = Form.query.get_or_404(form_id)
    n = len(form.pages) + 1
    page = FormPage(form_id=form.id, sort_order=_next_sort_order(form.pages), title_en=f"Page {n}", title_es=f"Página {n}")
    db.session.add(page)
    db.session.commit()
    return redirect(url_for("admin.form_builder", form_id=form.id, page=page.id))


@admin_bp.route("/forms/pages/<int:page_id>/update", methods=["POST"])
@admin_required
def form_page_update(page_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    page = FormPage.query.get_or_404(page_id)
    page.title_en = request.form.get("title_en", "").strip()
    page.title_es = request.form.get("title_es", "").strip()
    page.description_en = request.form.get("description_en", "").strip()
    page.description_es = request.form.get("description_es", "").strip()
    db.session.commit()
    flash("Page updated.", "success")
    return redirect(url_for("admin.form_builder", form_id=page.form_id, page=page.id))


@admin_bp.route("/forms/pages/<int:page_id>/duplicate", methods=["POST"])
@admin_required
def form_page_duplicate(page_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    page = FormPage.query.get_or_404(page_id)
    new_page = FormPage(
        form_id=page.form_id, sort_order=_next_sort_order(page.form.pages),
        title_en=(page.title_en or "") + " (Copy)", title_es=(page.title_es or "") + " (Copia)",
        description_en=page.description_en, description_es=page.description_es,
    )
    db.session.add(new_page)
    db.session.flush()
    for field in page.fields:
        new_field = FormField(
            page_id=new_page.id, sort_order=field.sort_order,
            field_type=field.field_type, internal_name=field.internal_name + "_copy",
            label_en=field.label_en, label_es=field.label_es,
            placeholder_en=field.placeholder_en, placeholder_es=field.placeholder_es,
            help_text_en=field.help_text_en, help_text_es=field.help_text_es,
            required=field.required, default_value=field.default_value, width=field.width,
            min_value=field.min_value, max_value=field.max_value,
            min_length=field.min_length, max_length=field.max_length,
            allowed_file_types=field.allowed_file_types, max_file_size_mb=field.max_file_size_mb,
            max_files=field.max_files, content_en=field.content_en, content_es=field.content_es,
            price_amount=field.price_amount, price_currency=field.price_currency,
            service_source=field.service_source,
        )
        db.session.add(new_field)
        db.session.flush()
        for option in field.options:
            db.session.add(FieldOption(
                field_id=new_field.id, sort_order=option.sort_order,
                value=option.value, label_en=option.label_en, label_es=option.label_es,
            ))
    db.session.commit()
    flash("Page duplicated.", "success")
    return redirect(url_for("admin.form_builder", form_id=page.form_id, page=new_page.id))


@admin_bp.route("/forms/pages/<int:page_id>/delete", methods=["POST"])
@admin_required
def form_page_delete(page_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    page = FormPage.query.get_or_404(page_id)
    form_id = page.form_id
    if len(page.form.pages) <= 1:
        flash("A form needs at least one page.", "error")
        return redirect(url_for("admin.form_builder", form_id=form_id))
    for field in page.fields:
        if field.image_filename:
            delete_course_media(field.image_filename)
    db.session.delete(page)
    db.session.commit()
    flash("Page deleted.", "success")
    return redirect(url_for("admin.form_builder", form_id=form_id))


@admin_bp.route("/forms/pages/<int:page_id>/move", methods=["POST"])
@admin_required
def form_page_move(page_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    page = FormPage.query.get_or_404(page_id)
    direction = request.form.get("direction")
    siblings = list(FormPage.query.filter_by(form_id=page.form_id).order_by(FormPage.sort_order).all())
    _swap_sort_order(siblings, page, direction)
    return redirect(url_for("admin.form_builder", form_id=page.form_id, page=page.id))


@admin_bp.route("/forms/<int:form_id>/pages/reorder", methods=["POST"])
@admin_required
def form_pages_reorder(form_id):
    if not validate_csrf(request.headers.get("X-CSRFToken")):
        abort(400)
    payload = request.get_json(silent=True) or {}
    order = payload.get("order", [])
    pages_by_id = {p.id: p for p in FormPage.query.filter_by(form_id=form_id).all()}
    for index, pid in enumerate(order):
        if pid in pages_by_id:
            pages_by_id[pid].sort_order = index
    db.session.commit()
    return {"ok": True}


# ---------------------------------------------------------------- fields

@admin_bp.route("/forms/pages/<int:page_id>/fields/new", methods=["POST"])
@admin_required
def form_field_new(page_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    page = FormPage.query.get_or_404(page_id)
    field_type = request.form.get("field_type")
    if field_type not in FORM_FIELD_TYPES:
        abort(400)
    field = _add_field(page, field_type)
    db.session.commit()
    flash("Field added.", "success")
    return redirect(url_for("admin.form_builder", form_id=page.form_id, page=page.id, field=field.id))


def _apply_field_settings(field, form):
    f = form
    field.label_en = f.get("label_en", "").strip()
    field.label_es = f.get("label_es", "").strip()
    field.placeholder_en = f.get("placeholder_en", "").strip()
    field.placeholder_es = f.get("placeholder_es", "").strip()
    field.help_text_en = f.get("help_text_en", "").strip()
    field.help_text_es = f.get("help_text_es", "").strip()
    field.validation_message_en = f.get("validation_message_en", "").strip()
    field.validation_message_es = f.get("validation_message_es", "").strip()
    field.required = f.get("required") == "on"
    field.default_value = f.get("default_value", "").strip() or None
    field.width = f.get("width") if f.get("width") in ("full", "half", "third") else "full"
    field.admin_notes = f.get("admin_notes", "").strip()
    if "_intake_options" in f:
        field.source_ref = f.get("source_ref", "").strip()[:120] or None
        field.source_note = f.get("source_note", "").strip() or None
        field.is_sensitive = f.get("is_sensitive") == "on"
        field.pattern = f.get("pattern", "").strip()[:200] or None
        field.date_rule = f.get("date_rule") if f.get("date_rule") in ("past", "future") else None
        field.help_detail_en = f.get("help_detail_en", "").strip() or None
        field.help_detail_es = f.get("help_detail_es", "").strip() or None
        field.help_where_en = f.get("help_where_en", "").strip() or None
        field.help_where_es = f.get("help_where_es", "").strip() or None
        cfg = f.get("config_json", "").strip()
        if cfg:
            try:
                json.loads(cfg)
                field.config_json = cfg
            except ValueError:
                flash("Component settings must be valid JSON; they were not saved.", "error")
        elif "config_json" in f:
            field.config_json = None

    def _float_or_none(key):
        raw = f.get(key, "").strip()
        try:
            return float(raw) if raw else None
        except ValueError:
            return None

    def _int_or_none(key):
        raw = f.get(key, "").strip()
        try:
            return int(raw) if raw else None
        except ValueError:
            return None

    field.min_value = _float_or_none("min_value")
    field.max_value = _float_or_none("max_value")
    field.min_length = _int_or_none("min_length")
    field.max_length = _int_or_none("max_length")

    field.allowed_file_types = f.get("allowed_file_types", "").strip()
    field.max_file_size_mb = _int_or_none("max_file_size_mb") or 10
    field.max_files = _int_or_none("max_files") or 1

    field.content_en = f.get("content_en", "").strip()
    field.content_es = f.get("content_es", "").strip()

    field.price_amount = _float_or_none("price_amount")
    field.price_currency = f.get("price_currency", "USD").strip() or "USD"
    field.service_source = f.get("service_source") if f.get("service_source") in ("og_services", "custom") else "og_services"

    internal_name = f.get("internal_name", "").strip()
    if internal_name:
        clash = FormField.query.filter(
            FormField.page.has(form_id=field.page.form_id),
            FormField.internal_name == internal_name,
            FormField.id != field.id,
        ).first()
        if not clash:
            field.internal_name = internal_name


@admin_bp.route("/forms/fields/<int:field_id>/update", methods=["POST"])
@admin_required
def form_field_update(field_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    field = FormField.query.get_or_404(field_id)

    image = request.files.get("image_file")
    if image and image.filename:
        try:
            new_filename = save_course_media(image, "image")
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.form_builder", form_id=field.page.form_id, page=field.page_id, field=field.id))
        if field.image_filename:
            delete_course_media(field.image_filename)
        field.image_filename = new_filename

    _apply_field_settings(field, request.form)
    db.session.commit()
    flash("Field updated.", "success")
    return redirect(url_for("admin.form_builder", form_id=field.page.form_id, page=field.page_id, field=field.id))


@admin_bp.route("/forms/fields/<int:field_id>/duplicate", methods=["POST"])
@admin_required
def form_field_duplicate(field_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    field = FormField.query.get_or_404(field_id)
    existing_names = {f.internal_name for f in field.page.form.all_fields}
    new_field = FormField(
        page_id=field.page_id, sort_order=_next_sort_order(field.page.fields),
        field_type=field.field_type, internal_name=internal_name_from_label(field.internal_name, existing_names),
        label_en=field.label_en, label_es=field.label_es,
        placeholder_en=field.placeholder_en, placeholder_es=field.placeholder_es,
        help_text_en=field.help_text_en, help_text_es=field.help_text_es,
        validation_message_en=field.validation_message_en, validation_message_es=field.validation_message_es,
        required=field.required, default_value=field.default_value, width=field.width,
        min_value=field.min_value, max_value=field.max_value,
        min_length=field.min_length, max_length=field.max_length,
        allowed_file_types=field.allowed_file_types, max_file_size_mb=field.max_file_size_mb,
        max_files=field.max_files, content_en=field.content_en, content_es=field.content_es,
        price_amount=field.price_amount, price_currency=field.price_currency,
        service_source=field.service_source, admin_notes=field.admin_notes,
    )
    db.session.add(new_field)
    db.session.flush()
    for option in field.options:
        db.session.add(FieldOption(
            field_id=new_field.id, sort_order=option.sort_order,
            value=option.value, label_en=option.label_en, label_es=option.label_es,
            image_filename=option.image_filename,
        ))
    db.session.commit()
    flash("Field duplicated.", "success")
    return redirect(url_for("admin.form_builder", form_id=field.page.form_id, page=field.page_id, field=new_field.id))


@admin_bp.route("/forms/fields/<int:field_id>/delete", methods=["POST"])
@admin_required
def form_field_delete(field_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    field = FormField.query.get_or_404(field_id)
    form_id = field.page.form_id
    page_id = field.page_id
    if field.image_filename:
        delete_course_media(field.image_filename)
    for option in field.options:
        if option.image_filename:
            delete_course_media(option.image_filename)
    db.session.delete(field)
    db.session.commit()
    flash("Field removed.", "success")
    return redirect(url_for("admin.form_builder", form_id=form_id, page=page_id))


@admin_bp.route("/forms/fields/<int:field_id>/move", methods=["POST"])
@admin_required
def form_field_move(field_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    field = FormField.query.get_or_404(field_id)
    direction = request.form.get("direction")
    siblings = list(FormField.query.filter_by(page_id=field.page_id).order_by(FormField.sort_order).all())
    _swap_sort_order(siblings, field, direction)
    return redirect(url_for("admin.form_builder", form_id=field.page.form_id, page=field.page_id, field=field.id))


@admin_bp.route("/forms/pages/<int:page_id>/fields/reorder", methods=["POST"])
@admin_required
def form_fields_reorder(page_id):
    if not validate_csrf(request.headers.get("X-CSRFToken")):
        abort(400)
    payload = request.get_json(silent=True) or {}
    order = payload.get("order", [])
    fields_by_id = {f.id: f for f in FormField.query.filter_by(page_id=page_id).all()}
    for index, fid in enumerate(order):
        if fid in fields_by_id:
            fields_by_id[fid].sort_order = index
    db.session.commit()
    return {"ok": True}


# ---------------------------------------------------------------- options

@admin_bp.route("/forms/fields/<int:field_id>/options/new", methods=["POST"])
@admin_required
def form_option_new(field_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    field = FormField.query.get_or_404(field_id)
    n = len(field.options) + 1
    option = FieldOption(
        field_id=field.id, sort_order=_next_sort_order(field.options),
        value=f"option_{n}", label_en=f"Option {n}", label_es=f"Opción {n}",
    )
    db.session.add(option)
    db.session.commit()
    return redirect(url_for("admin.form_builder", form_id=field.page.form_id, page=field.page_id, field=field.id))


@admin_bp.route("/forms/options/<int:option_id>/update", methods=["POST"])
@admin_required
def form_option_update(option_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    option = FieldOption.query.get_or_404(option_id)

    image = request.files.get("image_file")
    if image and image.filename:
        try:
            new_filename = save_course_media(image, "image")
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.form_builder", form_id=option.field.page.form_id, page=option.field.page_id, field=option.field_id))
        if option.image_filename:
            delete_course_media(option.image_filename)
        option.image_filename = new_filename

    value = request.form.get("value", "").strip()
    option.value = value or option.value
    option.label_en = request.form.get("label_en", "").strip() or option.label_en
    option.label_es = request.form.get("label_es", "").strip() or option.label_en
    db.session.commit()
    return redirect(url_for("admin.form_builder", form_id=option.field.page.form_id, page=option.field.page_id, field=option.field_id))


@admin_bp.route("/forms/options/<int:option_id>/duplicate", methods=["POST"])
@admin_required
def form_option_duplicate(option_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    option = FieldOption.query.get_or_404(option_id)
    db.session.add(FieldOption(
        field_id=option.field_id, sort_order=_next_sort_order(option.field.options),
        value=option.value + "_copy", label_en=option.label_en + " (Copy)", label_es=option.label_es + " (Copia)",
    ))
    db.session.commit()
    return redirect(url_for("admin.form_builder", form_id=option.field.page.form_id, page=option.field.page_id, field=option.field_id))


@admin_bp.route("/forms/options/<int:option_id>/delete", methods=["POST"])
@admin_required
def form_option_delete(option_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    option = FieldOption.query.get_or_404(option_id)
    field = option.field
    if option.image_filename:
        delete_course_media(option.image_filename)
    db.session.delete(option)
    db.session.commit()
    return redirect(url_for("admin.form_builder", form_id=field.page.form_id, page=field.page_id, field=field.id))


@admin_bp.route("/forms/options/<int:option_id>/move", methods=["POST"])
@admin_required
def form_option_move(option_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    option = FieldOption.query.get_or_404(option_id)
    direction = request.form.get("direction")
    siblings = list(FieldOption.query.filter_by(field_id=option.field_id).order_by(FieldOption.sort_order).all())
    _swap_sort_order(siblings, option, direction)
    return redirect(url_for("admin.form_builder", form_id=option.field.page.form_id, page=option.field.page_id, field=option.field_id))


# ---------------------------------------------------------------- conditional rules

@admin_bp.route("/forms/<int:form_id>/rules/new", methods=["POST"])
@admin_required
def form_rule_new(form_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    form = Form.query.get_or_404(form_id)
    rule = ConditionalRule(form_id=form.id, sort_order=_next_sort_order(form.rules), action="show_field", match_type="all")
    db.session.add(rule)
    db.session.flush()

    preset_target_id = request.form.get("preset_target_field_id", type=int)
    non_content_fields = [f for f in form.all_fields if not f.is_content_only]
    condition_field = next((f for f in non_content_fields if f.id != preset_target_id), None) or next(iter(non_content_fields), None)
    if condition_field:
        db.session.add(RuleCondition(rule_id=rule.id, field_id=condition_field.id, operator="equals", value=""))
    target_field = next((f for f in non_content_fields if f.id == preset_target_id), None) or condition_field
    if target_field:
        rule.target_field_id = target_field.id

    db.session.commit()

    return_page_id = request.form.get("return_page_id", type=int)
    return_field_id = request.form.get("return_field_id", type=int)
    return redirect(
        url_for("admin.form_builder", form_id=form.id, page=return_page_id, field=return_field_id)
        + f"#rule-{rule.id}"
    )


@admin_bp.route("/forms/rules/<int:rule_id>/update", methods=["POST"])
@admin_required
def form_rule_update(rule_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    rule = ConditionalRule.query.get_or_404(rule_id)
    f = request.form

    rule.match_type = "any" if f.get("match_type") == "any" else "all"
    action = f.get("action")
    rule.action = action if action in RULE_ACTIONS else "show_field"
    rule.target_field_id = f.get("target_field_id", type=int) if rule.action in (
        "show_field", "hide_field", "require_field", "optional_field") else None
    rule.target_page_id = f.get("target_page_id", type=int) if rule.action in ("show_page", "skip_page", "goto_page") else None

    RuleCondition.query.filter_by(rule_id=rule.id).delete()
    cond_field_ids = f.getlist("cond_field_id")
    cond_operators = f.getlist("cond_operator")
    cond_values = f.getlist("cond_value")
    for field_id, operator, value in zip(cond_field_ids, cond_operators, cond_values):
        if not field_id:
            continue
        if operator not in CONDITION_OPERATORS:
            continue
        db.session.add(RuleCondition(rule_id=rule.id, field_id=int(field_id), operator=operator, value=value.strip()))

    db.session.commit()
    flash("Conditional rule saved.", "success")
    return_page_id = f.get("return_page_id", type=int)
    return_field_id = f.get("return_field_id", type=int)
    return redirect(
        url_for("admin.form_builder", form_id=rule.form_id, page=return_page_id, field=return_field_id)
        + f"#rule-{rule.id}"
    )


@admin_bp.route("/forms/rules/<int:rule_id>/delete", methods=["POST"])
@admin_required
def form_rule_delete(rule_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    rule = ConditionalRule.query.get_or_404(rule_id)
    form_id = rule.form_id
    return_page_id = request.form.get("return_page_id", type=int)
    return_field_id = request.form.get("return_field_id", type=int)
    db.session.delete(rule)
    db.session.commit()
    flash("Rule removed.", "success")
    return redirect(url_for("admin.form_builder", form_id=form_id, page=return_page_id, field=return_field_id))


# ---------------------------------------------------------------- submissions

@admin_bp.route("/forms/<int:form_id>/submissions")
@admin_required
def form_submissions(form_id):
    form = Form.query.get_or_404(form_id)
    query = FormSubmission.query.filter_by(form_id=form.id)

    show_drafts = request.args.get("drafts") == "1"
    reopened = FormSubmission.status == "reopened"
    query = (query.filter(FormSubmission.is_complete.is_(False), ~reopened) if show_drafts
             else query.filter(db.or_(FormSubmission.is_complete.is_(True), reopened)))
    draft_total = (FormSubmission.query.filter_by(form_id=form.id, is_complete=False)
                   .filter(FormSubmission.student_id.isnot(None), ~reopened).count())

    status = request.args.get("status", "")
    if status in SUBMISSION_STATUSES or status == "reopened":
        query = query.filter_by(status=status)

    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                FormSubmission.display_name.ilike(like),
                FormSubmission.display_email.ilike(like),
                FormSubmission.display_phone.ilike(like),
                FormSubmission.code.ilike(like),
            )
        )

    sort = request.args.get("sort", "newest")
    if sort == "oldest":
        query = query.order_by(FormSubmission.submitted_at.asc())
    else:
        query = query.order_by(FormSubmission.submitted_at.desc())

    submissions = query.all()
    return render_template(
        "admin/forms/submissions.html", form=form, submissions=submissions, status=status, q=q, sort=sort,
        statuses=SUBMISSION_STATUSES + ("reopened",), show_drafts=show_drafts, draft_total=draft_total,
    )


@admin_bp.route("/forms/<int:form_id>/submissions/export.csv")
@admin_required
def form_submissions_export(form_id):
    form = Form.query.get_or_404(form_id)
    fields = form.all_fields
    header = ["Submission ID", "Date", "Language", "Status", "Name", "Email", "Phone"] + [f.label("en") or f.internal_name for f in fields]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for submission in FormSubmission.query.filter_by(form_id=form.id, is_complete=True).order_by(FormSubmission.submitted_at.desc()).all():
        values_by_field = {v.field_id: v.value_text for v in submission.values}
        row = [
            submission.code,
            submission.submitted_at.strftime("%Y-%m-%d %H:%M") if submission.submitted_at else "",
            submission.language, submission.status,
            submission.display_name or "", submission.display_email or "", submission.display_phone or "",
        ]
        for field in fields:
            raw = values_by_field.get(field.id, "")
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    raw = ", ".join(parsed)
            except (ValueError, TypeError):
                pass
            row.append(raw or "")
        writer.writerow(row)

    return Response(
        buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={form.slug}-submissions.csv"},
    )


def _legacy_sources(form, ref):
    """Snapshots frozen before multi-form mapping only have `source_ref` (the intake's own form)."""
    return [{"form": form.source_form_name, "edition": form.source_edition, "ref": ref}] if ref else []


def _admin_answer_sections(submission):
    """Grouped answers for the admin review. A completed service intake is read from
    its frozen snapshot (so it always shows what the customer actually answered, under
    the form version they used); a draft is read live from the current answers."""
    from app.intake_engine import load_snapshot, review_sections

    form = submission.form
    if form.is_service_intake:
        snap = load_snapshot(submission)
        if snap:
            return [
                {"title": sec["title_en"], "context": sec.get("context"), "group": sec.get("group"), "items": [
                    {"label": it["label_en"], "value": it["display_en"] if it["value"] not in (None, "", []) else "",
                     "source_ref": it.get("source_ref"), "sources": it.get("sources") or _legacy_sources(form, it.get("source_ref")),
                     "sensitive": it.get("sensitive"), "files": it.get("files", [])}
                    for it in sec["items"]]}
                for sec in snap["sections"]
            ]
        return [
            {"title": sec["page"].title("en") or "Page", "context": sec["page"].context_key, "group": sec["page"].group_key, "items": [
                {"label": it["field"].label("en") or it["field"].internal_name, "value": it["value"],
                 "source_ref": it["field"].source_ref, "sources": it["field"].sources(form), "sensitive": it["field"].is_sensitive,
                 "files": [{"id": f.id, "name": f.original_filename, "size": f.size_bytes} for f in it["files"]]}
                for it in sec["items"]]}
            for sec in review_sections(form, submission, "en", reveal=True)
        ]
    return None


@admin_bp.route("/forms/submissions/<int:submission_id>")
@admin_required
def form_submission_detail(submission_id):
    from app.intake_engine import context_map, progress_for, status_key, status_label

    from app.intake_shared import set_name_tokens, supplement_status

    submission = FormSubmission.query.get_or_404(submission_id)
    set_name_tokens(submission.form, submission)
    sections = _admin_answer_sections(submission)
    sup_cfg = submission.form.features.get("supplements") or {}
    present_groups = {sec.get("group") for sec in (sections or []) if sec["items"]}
    forms_sources = []
    if submission.form.is_service_intake and sup_cfg:
        forms_sources.append({"form": submission.form.source_form_name, "edition": submission.source_edition_snapshot or submission.form.source_edition,
                              "title": "Petition for Alien Relative", "supplement": False})
        for key, sup in sup_cfg.items():
            if present_groups & set(sup["groups"]):
                forms_sources.append({"form": sup["form"], "edition": sup["edition"], "title": sup["title"]["en"], "supplement": True})
    sup_groups = {g: k for k, v in sup_cfg.items() for g in v["groups"]}
    values_by_field_id = {v.field_id: v for v in submission.values}
    files_by_field_id = {}
    for file in submission.files:
        files_by_field_id.setdefault(file.field_id, []).append(file)

    display_by_field_id = {}
    for field in submission.form.all_fields:
        v = values_by_field_id.get(field.id)
        if not v or not v.value_text:
            continue
        raw = v.value_text
        if field.is_multi_value:
            try:
                selected = json.loads(raw)
            except (TypeError, ValueError):
                selected = []
            labels = [o.label("en") for o in field.options if o.value in selected]
            if field.field_type == "service_multi":
                labels = [og_service_label(val, "en") for val in selected]
            display_by_field_id[field.id] = ", ".join(labels) or raw
        elif field.field_type in ("single_choice", "dropdown", "image_choice", "yes_no"):
            opt = next((o for o in field.options if o.value == raw), None)
            display_by_field_id[field.id] = opt.label("en") if opt else raw
        elif field.field_type == "service_single":
            display_by_field_id[field.id] = og_service_label(raw, "en")
        else:
            display_by_field_id[field.id] = raw

    completeness = None
    if submission.form.features.get("completeness_check"):
        from app.intake_completeness import completeness_report

        completeness = completeness_report(submission.form, submission, "en")
    progress = progress_for(submission.form, submission) if submission.form.is_service_intake and not submission.is_complete else None
    activity = []
    if submission.student_id:
        from app.activity import timeline

        activity = [
            (e, text) for e, text in timeline(submission.student_id, "all", 400)
            if e.entity_type == "submission" and e.entity_id == submission.id
        ][:30]
    from app.case_panel import panel as case_panel

    i864 = i765 = i751 = ds260 = w7 = None
    if submission.form.source_form_name == "W-7":
        from app.w7_views import admin_summary as w7_summary

        w7 = w7_summary(submission)
    elif submission.form.source_form_name == "DS-260":
        from app.ds260_views import admin_summary as ds260_summary

        ds260 = ds260_summary(submission)
    elif submission.form.source_form_name == "I-751":
        from app.i751_views import admin_summary as i751_summary

        i751 = i751_summary(submission)
    elif submission.form.source_form_name == "I-864":
        from app.i864_views import admin_summary

        i864 = admin_summary(submission)
    elif submission.form.source_form_name == "I-765":
        from app.i765_views import admin_summary as i765_summary

        i765 = i765_summary(submission)
    return render_template(
        "admin/forms/submission_detail.html", submission=submission, form=submission.form, case_panel=case_panel(submission), i864=i864, i765=i765, i751=i751, w7=w7,
        files_by_field_id=files_by_field_id, display_by_field_id=display_by_field_id,
        statuses=[s for s in SUBMISSION_STATUSES if s != "ready_for_ceac"], sections=sections, progress=progress, activity=activity, completeness=completeness, ds260=ds260,
        status_key=status_key(submission), status_label=status_label(submission),
        contexts=context_map(submission.form, submission, "en"),
        forms_sources=forms_sources, sup_groups=sup_groups, sup_cfg=sup_cfg,
        supplement_state=supplement_status(submission.form, submission) if sup_cfg else None,
        revisions=_revisions_for(submission), is_reopened=(not submission.is_complete and submission.status == "reopened"),
        internal_notes=[n for n in submission.notes if not n.is_customer_visible],
        customer_messages=[n for n in submission.notes if n.is_customer_visible],
    )


def _revisions_for(submission):
    from app.reopen import revision_changes

    return [{"r": r, "changes": revision_changes(r)} for r in reversed(submission.revisions)]


@admin_bp.route("/forms/submissions/<int:submission_id>/reopen", methods=["POST"])
@admin_required
def form_submission_reopen(submission_id):
    """Give the customer permission to edit a submitted intake again (same application)."""
    from app.reopen import reopen_submission

    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    submission = FormSubmission.query.get_or_404(submission_id)
    if reopen_submission(submission, request.form.get("message", ""), actor_id=session.get("admin_user_id")):
        flash("Application reopened. The customer can now continue editing it.", "success")
    else:
        flash("Only a submitted service application can be reopened.", "error")
    return redirect(url_for("admin.form_submission_detail", submission_id=submission.id))


@admin_bp.route("/forms/submissions/<int:submission_id>/lock", methods=["POST"])
@admin_required
def form_submission_lock(submission_id):
    from app.reopen import lock_again

    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    submission = FormSubmission.query.get_or_404(submission_id)
    if lock_again(submission, actor_id=session.get("admin_user_id")):
        flash("Editing closed. The application is back to Submitted.", "success")
    return redirect(url_for("admin.form_submission_detail", submission_id=submission.id))


@admin_bp.route("/files/<int:file_id>")
@admin_required
def submission_file(file_id):
    """Admin download of a customer's uploaded document, by record id — the storage
    path is never exposed."""
    import os

    from flask import send_file

    file = SubmissionFile.query.get_or_404(file_id)
    path = course_media_full_path(file.stored_filename)
    if not os.path.isfile(path):
        abort(404)
    inline = request.args.get("inline") == "1" and (file.mime_type or "") in ("application/pdf", "image/jpeg", "image/png", "image/webp")
    response = send_file(path, mimetype=file.mime_type or "application/octet-stream", as_attachment=not inline, download_name=file.original_filename, conditional=True)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@admin_bp.route("/forms/submissions/<int:submission_id>/status", methods=["POST"])
@admin_required
def form_submission_status(submission_id):
    from app.activity import log_event
    from app.intake_engine import status_label
    from app.models.form_builder import SUBMISSION_STATUS_LABELS

    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    submission = FormSubmission.query.get_or_404(submission_id)
    status = request.form.get("status")
    if status == "ready_for_ceac":
        flash("Use “Mark ready for CEAC” on the DS-260 panel: it checks the answers first.", "error")
        return redirect(url_for("admin.form_submission_detail", submission_id=submission.id))
    if status in SUBMISSION_STATUSES and submission.is_complete and status != submission.status:
        before = status_label(submission)
        submission.status = status
        db.session.commit()
        if submission.student_id:
            log_event(submission.student_id, "application_status_changed", actor="admin", entity=("submission", submission.id),
                      meta={"from_label": before, "to_label": SUBMISSION_STATUS_LABELS.get(status, status),
                            "service": submission.service.title_en if submission.service else submission.form.name_admin})
        flash("Status updated.", "success")
    elif not submission.is_complete:
        flash("A draft cannot change status until the customer submits it.", "error")
    return redirect(url_for("admin.form_submission_detail", submission_id=submission.id))


@admin_bp.route("/forms/submissions/<int:submission_id>/notes", methods=["POST"])
@admin_required
def form_submission_note_add(submission_id):
    from app.activity import log_event

    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    submission = FormSubmission.query.get_or_404(submission_id)
    body = request.form.get("body", "").strip()
    if body:
        db.session.add(SubmissionNote(submission_id=submission.id, body=body, author_name="OG team", is_customer_visible=False))
        db.session.commit()
        if submission.student_id:
            log_event(submission.student_id, "admin_note_added", actor="admin", entity=("submission", submission.id), meta={"where": "application"})
        flash("Internal note added (never shown to the customer).", "success")
    return redirect(url_for("admin.form_submission_detail", submission_id=submission.id))


@admin_bp.route("/forms/submissions/<int:submission_id>/request-info", methods=["POST"])
@admin_required
def form_submission_request_info(submission_id):
    """A message the customer WILL see on their application; moves it to Waiting for Client."""
    from app.activity import log_event
    from app.models.form_builder import SUBMISSION_STATUS_LABELS

    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    submission = FormSubmission.query.get_or_404(submission_id)
    body = request.form.get("body", "").strip()
    if not body or not submission.is_complete:
        flash("Write the message to send. (Drafts cannot be sent requests.)", "error")
        return redirect(url_for("admin.form_submission_detail", submission_id=submission.id))
    before = submission.status
    db.session.add(SubmissionNote(submission_id=submission.id, body=body, author_name="OG team", is_customer_visible=True))
    submission.status = "waiting_client"
    db.session.commit()
    if submission.student_id:
        title = submission.service.title_en if submission.service else submission.form.name_admin
        log_event(submission.student_id, "admin_info_requested", actor="admin", entity=("submission", submission.id), meta={"service": title})
        if before != "waiting_client":
            log_event(submission.student_id, "application_status_changed", actor="admin", entity=("submission", submission.id),
                      meta={"from_label": SUBMISSION_STATUS_LABELS.get(before, before), "to_label": SUBMISSION_STATUS_LABELS["waiting_client"], "service": title})
        try:
            from app.email_service import send_transactional_email

            student = submission.student
            send_transactional_email(student, "info_needed", (submission.language or student.preferred_language or "en"),
                                     ref={"kind": "form_submission", "id": submission.id}, related_type="form_submission", related_id=submission.id)
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger("og_email").exception("[forms] info_needed email failed to queue for submission %s", submission.id)
    flash("Request sent — the customer will see it on their application.", "success")
    return redirect(url_for("admin.form_submission_detail", submission_id=submission.id))
