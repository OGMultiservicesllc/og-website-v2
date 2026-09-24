"""Import a package produced by ``export_content.py`` into the PostgreSQL
production database (``ogwebsite_prod`` on the VPS).

This script is meant to run ON THE VPS, against ``DATABASE_URL`` pointing at
the real production PostgreSQL, using the project's own venv/config. It
refuses to run against anything that is not PostgreSQL, specifically so it
can never be pointed at the local SQLite development database by mistake.

Safety model:
  - Every conflict check (existing rows, slug collisions, missing target
    Services) runs FIRST, before any write, and is fully reported; if
    anything is wrong the script aborts having written nothing.
  - All writes happen inside ONE database transaction. On any error at any
    point, the whole transaction is rolled back -- nothing partial is ever
    left behind.
  - `--dry-run` (the default) performs every check AND every write against
    the real database (so real constraint violations are caught, not just
    guessed at from the export data), then ALWAYS rolls back at the end and
    never commits. Pass `--apply` to actually commit.
  - Two different id strategies, deliberately:
      * MediaAsset, the two Academy courses and their whole structure, and
        the Case Simulation definitions are inserted preserving their exact
        original ids -- the target tables are expected to be completely
        empty (nothing seeds them), which is verified before any insert.
        MediaAsset ids in particular MUST match exactly, because
        `page_blocks` stores a MediaAsset id as plain text (not a real FK)
        for a few known keys, so a drifted id there would silently point at
        the wrong image with no database error to catch it.
      * The "request-a-quote" Form and its whole page/field/rule tree get
        FRESH ids on insert (never assumed free), because `forms` on the
        target is NOT empty -- the production Smart Intakes (I-90..W-7)
        already live there with their own independently-assigned ids. Every
        internal reference (form_pages.form_id, form_fields.page_id,
        form_field_options.field_id, form_conditional_rules.target_field_id,
        form_rule_conditions.rule_id/field_id) is rewritten through an
        id-remap table built as rows are inserted.
  - `services.hero_image_id` (and the other four image columns) are updated
    on the target Service found by SLUG, never by the Service's local numeric
    id (Service ids independently differ between the two databases).
  - After every explicit-id insert, the PostgreSQL sequence for that table is
    corrected (`setval`) so the next ordinary Admin-created row doesn't
    collide with an id we just inserted directly.
  - Physical files are only copied into COURSE_MEDIA_DIR AFTER a successful
    commit (never during --dry-run), verified by sha256 against
    files_manifest.json first.

Usage (on the VPS, later -- NOT run from here):
    python content_migration/import_content.py --package /path/to/export --dry-run
    python content_migration/import_content.py --package /path/to/export --apply
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import date, datetime

REQUIRE_EMPTY_TABLES = [
    # (table_name, model_import_path, attr_name)
    ("media_assets", "app.models.site_content", "MediaAsset"),
    ("courses", "app.models.course", "Course"),
    ("course_sections", "app.models.course", "CourseSection"),
    ("lessons", "app.models.course", "Lesson"),
    ("lesson_slides", "app.models.course", "LessonSlide"),
    ("lesson_resources", "app.models.course", "LessonResource"),
    ("quiz_questions", "app.models.progress", "QuizQuestion"),
    ("quiz_question_options", "app.models.progress", "QuizQuestionOption"),
    ("quiz_question_accepted_answers", "app.models.progress", "QuizQuestionAcceptedAnswer"),
    ("case_simulations", "app.models.case_simulation", "CaseSimulation"),
    ("case_simulation_documents", "app.models.case_simulation", "CaseSimulationDocument"),
    ("case_simulation_tasks", "app.models.case_simulation", "CaseSimulationTask"),
    ("case_simulation_task_options", "app.models.case_simulation", "CaseSimulationTaskOption"),
    ("case_simulation_task_accepted_answers", "app.models.case_simulation", "CaseSimulationTaskAcceptedAnswer"),
]

# Every table the package can contain -> its model, for the length-preflight
# check (check_string_lengths). Superset of REQUIRE_EMPTY_TABLES: also covers
# the natural-key/remapped tables (pages, page_blocks, blog_posts,
# site_settings, and the request-a-quote form tree), so a future
# VARCHAR(N) surprise anywhere in the package is caught before any INSERT is
# attempted, not during flush() -- see the 2026-09-23 quiz_question_options
# incident (migration b263d7c3e69e).
ALL_PACKAGE_TABLES = REQUIRE_EMPTY_TABLES + [
    ("pages", "app.models.page", "Page"),
    ("page_blocks", "app.models.content_block", "PageBlock"),
    ("blog_posts", "app.models.blog", "BlogPost"),
    ("site_settings", "app.models.settings", "SiteSettings"),
    ("forms", "app.models.form_builder", "Form"),
    ("form_pages", "app.models.form_builder", "FormPage"),
    ("form_fields", "app.models.form_builder", "FormField"),
    ("form_field_options", "app.models.form_builder", "FieldOption"),
    ("form_conditional_rules", "app.models.form_builder", "ConditionalRule"),
    ("form_rule_conditions", "app.models.form_builder", "RuleCondition"),
]

SERVICE_IMAGE_COLUMNS = ("hero_image_id", "hero_mobile_image_id", "card_image_id", "overview_image_id", "social_image_id")


class ImportAborted(Exception):
    pass


def _import_class(module_path, attr_name):
    import importlib

    return getattr(importlib.import_module(module_path), attr_name)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _coerce_row(model_cls, row, drop_id):
    """Turn an exported row dict back into kwargs for the model, converting
    ISO date/datetime strings back to real objects for typed columns."""
    col_types = {c.name: c.type for c in model_cls.__table__.columns}
    out = {}
    for key, value in row.items():
        if drop_id and key == "id":
            continue
        if value is not None and key in col_types:
            type_name = col_types[key].__class__.__name__
            if type_name == "DateTime" and isinstance(value, str):
                value = datetime.fromisoformat(value)
            elif type_name == "Date" and isinstance(value, str):
                value = date.fromisoformat(value)
        out[key] = value
    return out


def load_package(package_dir):
    for fname in ("manifest.json", "data.json", "files_manifest.json"):
        path = os.path.join(package_dir, fname)
        if not os.path.isfile(path):
            raise ImportAborted(f"Package is missing {fname} (expected at {path})")
    with open(os.path.join(package_dir, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    with open(os.path.join(package_dir, "data.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    with open(os.path.join(package_dir, "files_manifest.json"), encoding="utf-8") as fh:
        files_manifest = json.load(fh)
    return manifest, data, files_manifest


def verify_file_integrity(package_dir, files_manifest):
    """Confirm every file the manifest describes is present in the package
    and its sha256 matches -- catches a corrupted/incomplete scp transfer
    before we ever touch the database."""
    problems = []
    for entry in files_manifest:
        full_path = os.path.join(package_dir, "files", entry["relative_path"])
        if not os.path.isfile(full_path):
            problems.append(f"MISSING from package: {entry['relative_path']}")
            continue
        actual_size = os.path.getsize(full_path)
        if actual_size != entry["size_bytes"]:
            problems.append(f"SIZE MISMATCH: {entry['relative_path']} (expected {entry['size_bytes']}, got {actual_size})")
            continue
        actual_hash = _sha256(full_path)
        if actual_hash != entry["sha256"]:
            problems.append(f"HASH MISMATCH: {entry['relative_path']} (package may be corrupted)")
    return problems


def check_dialect_is_postgresql(db):
    if db.engine.dialect.name != "postgresql":
        raise ImportAborted(
            f"DATABASE_URL resolves to a '{db.engine.dialect.name}' database, not PostgreSQL. "
            "This importer refuses to run against anything but PostgreSQL, specifically so it "
            "can never be pointed at the local SQLite development database by mistake."
        )


def check_tables_empty(report):
    problems = []
    for table_name, module_path, attr_name in REQUIRE_EMPTY_TABLES:
        model_cls = _import_class(module_path, attr_name)
        count = model_cls.query.count()
        if count:
            problems.append(f"Target table '{table_name}' already has {count} row(s) -- refusing to insert "
                             "explicit-id rows on top of it (would risk id collisions or duplicate content).")
    report["empty_table_checks"] = "OK" if not problems else problems
    return problems


def check_slug_conflicts(data, report):
    from app.models.blog import BlogPost
    from app.models.form_builder import Form
    from app.models.page import Page

    problems = []
    existing_page_slugs = []
    for row in data.get("pages", []):
        slug = row["slug"]
        if Page.query.filter_by(slug=slug).first():
            problems.append(f"Page slug '{slug}' already exists on the target database.")
        existing_page_slugs.append(slug)

    for row in data.get("blog_posts", []):
        slug = row["slug"]
        if BlogPost.query.filter_by(slug=slug).first():
            problems.append(f"BlogPost slug '{slug}' already exists on the target database.")

    for row in data.get("forms", []):
        slug = row["slug"]
        if Form.query.filter_by(slug=slug).first():
            problems.append(f"Form slug '{slug}' already exists on the target database.")

    report["slug_conflict_checks"] = "OK" if not problems else problems
    return problems


def check_string_lengths(data, report):
    """Compare every String(N)-typed column's declared max length, for every
    table the package can contain, against the ACTUAL length of every value
    data.json would insert into it. Runs before any INSERT is attempted --
    the same check that would have caught the 2026-09-23
    quiz_question_options.text_es (306 chars into a VARCHAR(300)) incident in
    preflight instead of as a mid-flush PostgreSQL error."""
    import sqlalchemy as sa

    problems = []
    for table_name, module_path, attr_name in ALL_PACKAGE_TABLES:
        model_cls = _import_class(module_path, attr_name)
        string_cols = [c for c in model_cls.__table__.columns if isinstance(c.type, sa.String) and c.type.length]
        if not string_cols:
            continue
        for row in data.get(table_name, []):
            for col in string_cols:
                val = row.get(col.name)
                if isinstance(val, str) and len(val) > col.type.length:
                    problems.append(
                        f"{table_name}.{col.name} (row id={row.get('id')}): {len(val)} chars exceeds "
                        f"VARCHAR({col.type.length}) -- {val[:60]!r}..."
                    )
    report["string_length_checks"] = "OK" if not problems else problems
    return problems


def check_service_bridge(data, report):
    from app.models.site_content import Service

    warnings = []
    resolvable = []
    for entry in data.get("service_image_bridge", []):
        svc = Service.query.filter_by(slug=entry["service_slug"]).first()
        if not svc:
            warnings.append(f"Service slug '{entry['service_slug']}' not found on target -- "
                             f"its {entry['field']} will be left unset.")
        else:
            resolvable.append(entry)
    report["service_bridge_checks"] = "OK" if not warnings else warnings
    return warnings, resolvable


def insert_preserving_ids(db, model_cls, rows, report_key, report):
    count = 0
    for row in rows:
        kwargs = _coerce_row(model_cls, row, drop_id=False)
        db.session.add(model_cls(**kwargs))
        count += 1
    db.session.flush()
    report[report_key] = count
    return count


def insert_with_remap(db, model_cls, rows, id_field, fk_remaps, report_key, report):
    """Insert rows WITHOUT their original id (let PostgreSQL assign a fresh
    one), rewriting any FK column named in fk_remaps through the mapping
    built from an earlier table's insert. Returns {local_id: actual_id}."""
    local_to_actual = {}
    for row in rows:
        local_id = row.get(id_field)
        kwargs = _coerce_row(model_cls, row, drop_id=True)
        for fk_col, mapping in fk_remaps.items():
            if kwargs.get(fk_col) is not None:
                local_fk = kwargs[fk_col]
                if local_fk not in mapping:
                    raise ImportAborted(f"{model_cls.__tablename__}: no remapped id for {fk_col}={local_fk} "
                                         "(export package is internally inconsistent).")
                kwargs[fk_col] = mapping[local_fk]
        obj = model_cls(**kwargs)
        db.session.add(obj)
        db.session.flush()  # need obj.id immediately, for the NEXT table's remap
        if local_id is not None:
            local_to_actual[local_id] = obj.id
    report[report_key] = len(rows)
    return local_to_actual


def fix_sequence(db, model_cls, table_name):
    """Advance table_name's id sequence past the highest id now present.
    MAX(id) is computed through the ORM (a plain, already-proven query) rather
    than folded into the same raw SQL string as the setval() call, and both
    arguments to setval() are bind parameters -- no table name or count is
    ever concatenated into SQL text. This replaces an earlier version that
    string-concatenated the table name into a `FROM <name>` clause inside the
    same statement as the setval() call; that earlier version was never
    actually exercised against real PostgreSQL before the VPS import attempt
    that silently failed here (see the 2026-09-23 importer incident)."""
    from sqlalchemy import func, text

    max_id = db.session.query(func.max(model_cls.id)).scalar() or 1
    db.session.execute(
        text("SELECT setval(pg_get_serial_sequence(:t, 'id'), :max_id, true)"),
        {"t": table_name, "max_id": max_id},
    )


def run(package_dir, apply_changes, report):
    from app.extensions import db

    check_dialect_is_postgresql(db)

    manifest, data, files_manifest = load_package(package_dir)
    report["package"] = package_dir
    report["package_manifest"] = manifest

    file_problems = verify_file_integrity(package_dir, files_manifest)
    if file_problems:
        report["file_integrity"] = file_problems
        raise ImportAborted("File integrity check failed:\n  " + "\n  ".join(file_problems))
    report["file_integrity"] = "OK"

    empty_problems = check_tables_empty(report)
    slug_problems = check_slug_conflicts(data, report)
    length_problems = check_string_lengths(data, report)
    if empty_problems or slug_problems or length_problems:
        raise ImportAborted(
            "Conflict validation failed -- nothing was written:\n  "
            + "\n  ".join(empty_problems + slug_problems + length_problems)
        )

    bridge_warnings, bridge_resolvable = check_service_bridge(data, report)

    # ---- explicit-id groups (target tables verified empty above) ----
    MediaAsset = _import_class("app.models.site_content", "MediaAsset")
    insert_preserving_ids(db, MediaAsset, data.get("media_assets", []), "media_assets_inserted", report)

    Course = _import_class("app.models.course", "Course")
    CourseSection = _import_class("app.models.course", "CourseSection")
    Lesson = _import_class("app.models.course", "Lesson")
    LessonSlide = _import_class("app.models.course", "LessonSlide")
    LessonResource = _import_class("app.models.course", "LessonResource")
    insert_preserving_ids(db, Course, data.get("courses", []), "courses_inserted", report)
    insert_preserving_ids(db, CourseSection, data.get("course_sections", []), "course_sections_inserted", report)
    insert_preserving_ids(db, Lesson, data.get("lessons", []), "lessons_inserted", report)
    insert_preserving_ids(db, LessonSlide, data.get("lesson_slides", []), "lesson_slides_inserted", report)
    insert_preserving_ids(db, LessonResource, data.get("lesson_resources", []), "lesson_resources_inserted", report)

    QuizQuestion = _import_class("app.models.progress", "QuizQuestion")
    QuizQuestionOption = _import_class("app.models.progress", "QuizQuestionOption")
    QuizQuestionAcceptedAnswer = _import_class("app.models.progress", "QuizQuestionAcceptedAnswer")
    insert_preserving_ids(db, QuizQuestion, data.get("quiz_questions", []), "quiz_questions_inserted", report)
    insert_preserving_ids(db, QuizQuestionOption, data.get("quiz_question_options", []), "quiz_question_options_inserted", report)
    insert_preserving_ids(db, QuizQuestionAcceptedAnswer, data.get("quiz_question_accepted_answers", []), "quiz_question_accepted_answers_inserted", report)

    CaseSimulation = _import_class("app.models.case_simulation", "CaseSimulation")
    CaseSimulationDocument = _import_class("app.models.case_simulation", "CaseSimulationDocument")
    CaseSimulationTask = _import_class("app.models.case_simulation", "CaseSimulationTask")
    CaseSimulationTaskOption = _import_class("app.models.case_simulation", "CaseSimulationTaskOption")
    CaseSimulationTaskAcceptedAnswer = _import_class("app.models.case_simulation", "CaseSimulationTaskAcceptedAnswer")
    insert_preserving_ids(db, CaseSimulation, data.get("case_simulations", []), "case_simulations_inserted", report)
    insert_preserving_ids(db, CaseSimulationDocument, data.get("case_simulation_documents", []), "case_simulation_documents_inserted", report)
    insert_preserving_ids(db, CaseSimulationTask, data.get("case_simulation_tasks", []), "case_simulation_tasks_inserted", report)
    insert_preserving_ids(db, CaseSimulationTaskOption, data.get("case_simulation_task_options", []), "case_simulation_task_options_inserted", report)
    insert_preserving_ids(db, CaseSimulationTaskAcceptedAnswer, data.get("case_simulation_task_accepted_answers", []), "case_simulation_task_accepted_answers_inserted", report)

    for table_name, module_path, attr_name in REQUIRE_EMPTY_TABLES:
        fix_sequence(db, _import_class(module_path, attr_name), table_name)

    # ---- id-remapped group: request-a-quote form tree (forms table is NOT empty) ----
    Form = _import_class("app.models.form_builder", "Form")
    FormPage = _import_class("app.models.form_builder", "FormPage")
    FormField = _import_class("app.models.form_builder", "FormField")
    FieldOption = _import_class("app.models.form_builder", "FieldOption")
    ConditionalRule = _import_class("app.models.form_builder", "ConditionalRule")
    RuleCondition = _import_class("app.models.form_builder", "RuleCondition")

    form_map = insert_with_remap(db, Form, data.get("forms", []), "id", {}, "forms_inserted", report)
    page_map = insert_with_remap(db, FormPage, data.get("form_pages", []), "id", {"form_id": form_map}, "form_pages_inserted", report)
    field_map = insert_with_remap(db, FormField, data.get("form_fields", []), "id", {"page_id": page_map}, "form_fields_inserted", report)
    insert_with_remap(db, FieldOption, data.get("form_field_options", []), "id", {"field_id": field_map}, "form_field_options_inserted", report)
    rule_map = insert_with_remap(db, ConditionalRule, data.get("form_conditional_rules", []), "id",
                                  {"form_id": form_map, "target_field_id": field_map}, "form_conditional_rules_inserted", report)
    insert_with_remap(db, RuleCondition, data.get("form_rule_conditions", []), "id",
                       {"rule_id": rule_map, "field_id": field_map}, "form_rule_conditions_inserted", report)

    # ---- natural-key content: pages, page_blocks, blog_posts, site_settings ----
    Page = _import_class("app.models.page", "Page")
    inserted_pages = 0
    for row in data.get("pages", []):
        kwargs = _coerce_row(Page, row, drop_id=True)
        db.session.add(Page(**kwargs))
        inserted_pages += 1
    report["pages_inserted"] = inserted_pages

    PageBlock = _import_class("app.models.content_block", "PageBlock")
    pb_inserted, pb_updated = 0, 0
    for row in data.get("page_blocks", []):
        existing = PageBlock.query.filter_by(key=row["key"]).first()
        kwargs = _coerce_row(PageBlock, row, drop_id=True)
        if existing:
            for k, v in kwargs.items():
                if k != "key":
                    setattr(existing, k, v)
            pb_updated += 1
        else:
            db.session.add(PageBlock(**kwargs))
            pb_inserted += 1
    report["page_blocks_inserted"] = pb_inserted
    report["page_blocks_updated"] = pb_updated

    BlogPost = _import_class("app.models.blog", "BlogPost")
    inserted_posts = 0
    for row in data.get("blog_posts", []):
        kwargs = _coerce_row(BlogPost, row, drop_id=True)
        db.session.add(BlogPost(**kwargs))
        inserted_posts += 1
    report["blog_posts_inserted"] = inserted_posts

    SiteSettings = _import_class("app.models.settings", "SiteSettings")
    settings_rows = data.get("site_settings", [])
    settings_action = "none"
    if settings_rows:
        row = settings_rows[0]
        existing = SiteSettings.query.get(1)
        kwargs = _coerce_row(SiteSettings, row, drop_id=True)
        if existing:
            for k, v in kwargs.items():
                setattr(existing, k, v)
            settings_action = "updated existing singleton row"
        else:
            db.session.add(SiteSettings(id=1, **kwargs))
            settings_action = "inserted singleton row (id=1)"
    report["site_settings_action"] = settings_action

    db.session.flush()

    # ---- cross-reference: Service image columns, bridged by slug ----
    Service = _import_class("app.models.site_content", "Service")
    bridge_applied = []
    for entry in bridge_resolvable:
        svc = Service.query.filter_by(slug=entry["service_slug"]).first()
        setattr(svc, entry["field"], entry["media_asset_local_id"])  # media_asset ids preserved exactly, so no remap needed
        bridge_applied.append({"service_slug": entry["service_slug"], "field": entry["field"], "media_asset_id": entry["media_asset_local_id"]})
    report["service_bridge_applied"] = bridge_applied
    report["service_bridge_warnings"] = bridge_warnings

    # Recorded for verify_post_commit -- the request-a-quote form's ACTUAL id
    # on this database (never assumed to equal its local export id).
    report["request_a_quote_form_actual_id"] = form_map.get(data.get("forms", [{}])[0].get("id")) if data.get("forms") else None

    db.session.flush()

    return files_manifest


def verify_post_commit(db, data, report):
    """Re-read everything this import just committed, through a BRAND NEW
    connection (never the ORM session used to write it -- that session could
    still be showing its own cached/identity-mapped view), and compare
    against the counts `run()` recorded as it went. Returns a list of
    mismatch descriptions; empty means the commit is confirmed durable."""
    from sqlalchemy import text

    problems = []
    with db.engine.connect() as conn:
        def count(sql, **params):
            return conn.execute(text(sql), params).scalar()

        for table_name, _, _ in REQUIRE_EMPTY_TABLES:
            expected = report.get(f"{table_name}_inserted", 0)
            actual = count(f"SELECT COUNT(*) FROM {table_name}")
            if actual != expected:
                problems.append(f"{table_name}: expected {expected} rows post-commit, found {actual}")

        form_id = report.get("request_a_quote_form_actual_id")
        if data.get("forms"):
            if form_id is None or not count("SELECT COUNT(*) FROM forms WHERE id = :id", id=form_id):
                problems.append("request-a-quote Form: not found post-commit at its recorded actual id")
            else:
                checks = [
                    ("form_pages", "form_id", "form_pages_inserted"),
                    ("form_conditional_rules", "form_id", "form_conditional_rules_inserted"),
                ]
                for table_name, fk_col, report_key in checks:
                    expected = report.get(report_key, 0)
                    actual = count(f"SELECT COUNT(*) FROM {table_name} WHERE {fk_col} = :fid", fid=form_id)
                    if actual != expected:
                        problems.append(f"{table_name} (form_id={form_id}): expected {expected}, found {actual}")

        for row in data.get("pages", []):
            if not count("SELECT COUNT(*) FROM pages WHERE slug = :slug", slug=row["slug"]):
                problems.append(f"pages: slug '{row['slug']}' not found post-commit")

        for row in data.get("blog_posts", []):
            if not count("SELECT COUNT(*) FROM blog_posts WHERE slug = :slug", slug=row["slug"]):
                problems.append(f"blog_posts: slug '{row['slug']}' not found post-commit")

        for row in data.get("page_blocks", []):
            if not count("SELECT COUNT(*) FROM page_blocks WHERE key = :key", key=row["key"]):
                problems.append(f"page_blocks: key '{row['key']}' not found post-commit")

        if data.get("site_settings") and not count("SELECT COUNT(*) FROM site_settings WHERE id = 1"):
            problems.append("site_settings: singleton row (id=1) not found post-commit")

        for entry in report.get("service_bridge_applied", []):
            actual = count(
                f"SELECT COUNT(*) FROM services WHERE slug = :slug AND {entry['field']} = :mid",
                slug=entry["service_slug"], mid=entry["media_asset_id"],
            )
            if not actual:
                problems.append(f"services: '{entry['service_slug']}'.{entry['field']} does not hold "
                                 f"media_asset id {entry['media_asset_id']} post-commit")

    return problems


def verify_files_post_copy(package_dir, files_manifest, media_dir):
    """Re-read the sha256/size of every file the manifest describes, at its
    FINAL destination in media_dir, after copy_files() has run -- confirms
    what actually landed on disk, not just that copy_files() didn't raise."""
    problems = []
    for entry in files_manifest:
        dst = os.path.join(media_dir, entry["relative_path"])
        if not os.path.isfile(dst):
            problems.append(f"MISSING after copy: {entry['relative_path']}")
            continue
        if os.path.getsize(dst) != entry["size_bytes"]:
            problems.append(f"SIZE MISMATCH after copy: {entry['relative_path']}")
            continue
        if _sha256(dst) != entry["sha256"]:
            problems.append(f"HASH MISMATCH after copy: {entry['relative_path']}")
    return problems


def copy_files(package_dir, files_manifest, media_dir, report):
    copied, skipped, mismatched = [], [], []
    for entry in files_manifest:
        src = os.path.join(package_dir, "files", entry["relative_path"])
        dst = os.path.join(media_dir, entry["relative_path"])
        if os.path.exists(dst):
            if os.path.getsize(dst) == entry["size_bytes"] and _sha256(dst) == entry["sha256"]:
                skipped.append(entry["relative_path"])
                continue
            mismatched.append(entry["relative_path"])
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        import shutil

        shutil.copy2(src, dst)
        copied.append(entry["relative_path"])
    report["files_copied"] = copied
    report["files_already_present_unchanged"] = skipped
    report["files_name_collision_different_content"] = mismatched
    return mismatched


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--package", required=True, help="Path to an export package directory produced by export_content.py")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True, help="Validate and execute against a real transaction, then always roll back (default).")
    mode.add_argument("--apply", action="store_true", help="Actually commit the transaction and copy files. Overrides --dry-run.")
    parser.add_argument("--media-dir", default=None, help="Override COURSE_MEDIA_DIR for the file-copy step (default: read from app config).")
    args = parser.parse_args()
    apply_changes = bool(args.apply)

    package_dir = os.path.abspath(args.package)
    report = {"mode": "APPLY" if apply_changes else "DRY-RUN"}

    from app import create_app

    app = create_app()
    with app.app_context():
        from app.extensions import db

        try:
            files_manifest = run(package_dir, apply_changes, report)
        except ImportAborted as exc:
            db.session.rollback()
            print("=" * 70)
            print("IMPORT ABORTED -- no changes were written.")
            print("TRANSACTION ROLLED BACK")
            print("=" * 70)
            print(str(exc))
            print()
            print(json.dumps(report, indent=2, default=str, ensure_ascii=False))
            sys.exit(1)
        except Exception:
            db.session.rollback()
            print("=" * 70)
            print("IMPORT FAILED WITH AN UNEXPECTED ERROR")
            print("TRANSACTION ROLLED BACK -- no changes were written, despite any counts below")
            print("(those are statements EXECUTED during this run, not proof of anything committed).")
            print("=" * 70)
            import traceback

            traceback.print_exc()
            print(json.dumps(report, indent=2, default=str, ensure_ascii=False))
            sys.exit(1)

        if not apply_changes:
            db.session.rollback()
            print("=" * 70)
            print("DRY RUN COMPLETE -- every check and write above ran against the real")
            print("database inside a transaction that was then rolled back on purpose.")
            print("TRANSACTION ROLLED BACK")
            print("Nothing was committed and no files were copied. Re-run with --apply to commit.")
            print("=" * 70)
            print(json.dumps(report, indent=2, default=str, ensure_ascii=False))
            return

        # Only past this point does anything become real. Everything above --
        # including every "_inserted" count in `report` -- describes statements
        # already EXECUTED in the open transaction, not rows that are durable
        # yet. A failure in commit() itself still rolls back cleanly here.
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            print("=" * 70)
            print("COMMIT FAILED")
            print("TRANSACTION ROLLED BACK -- no changes were written, despite any counts above.")
            print("=" * 70)
            import traceback

            traceback.print_exc()
            sys.exit(1)

        print("=" * 70)
        print("TRANSACTION COMMITTED")
        print("=" * 70)

        # Don't just trust the commit call succeeded silently -- read the
        # counts back through a BRAND NEW connection (never the session that
        # wrote them) and require them to match what run() recorded. This is
        # exactly the check that would have caught the 2026-09-23 VPS
        # incident (a full-looking `report` with nothing actually persisted).
        with open(os.path.join(package_dir, "data.json"), encoding="utf-8") as fh:
            data_for_verify = json.load(fh)
        post_commit_problems = verify_post_commit(db, data_for_verify, report)
        report["post_commit_verification"] = "OK" if not post_commit_problems else post_commit_problems
        if post_commit_problems:
            print("=" * 70)
            print("POST-COMMIT VERIFICATION FAILED -- the commit call returned successfully, but")
            print("re-reading the data through a fresh connection does not show what was written.")
            print("Treat this import as FAILED, not successful, and investigate before retrying.")
            print("=" * 70)
            for p in post_commit_problems:
                print(f"  {p}")
            print(json.dumps(report, indent=2, default=str, ensure_ascii=False))
            sys.exit(1)
        print("Post-commit verification: every recorded insert is confirmed present via a fresh connection.")

        media_dir = args.media_dir or app.config["COURSE_MEDIA_DIR"]
        mismatched = copy_files(package_dir, files_manifest, media_dir, report)
        if mismatched:
            print("WARNING: the database import succeeded, but these files could not be copied "
                  "because a DIFFERENT file already exists at the destination path (resolve manually):")
            for m in mismatched:
                print(f"  {m}")

        post_copy_problems = verify_files_post_copy(package_dir, files_manifest, media_dir)
        report["post_copy_verification"] = "OK" if not post_copy_problems else post_copy_problems
        if post_copy_problems:
            print("=" * 70)
            print("POST-COPY FILE VERIFICATION FAILED -- the database commit is real and durable,")
            print("but the media files are not confirmed correct on disk. Investigate before")
            print("considering the customer-facing site fully restored.")
            print("=" * 70)
            for p in post_copy_problems:
                print(f"  {p}")
            print(json.dumps(report, indent=2, default=str, ensure_ascii=False))
            sys.exit(1)
        print(f"Post-copy verification: all {len(files_manifest)} files confirmed present with matching hash on disk.")

        print("=" * 70)
        print("IMPORT APPLIED.")
        print("=" * 70)
        print(json.dumps(report, indent=2, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
