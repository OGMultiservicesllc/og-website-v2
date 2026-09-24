"""Selective, read-only export of REAL/reusable content from the local SQLite
development database into a portable JSON + file package, for manual review
and later import into the VPS's PostgreSQL production database
(``ogwebsite_prod``).

Included (plan approved 2026-09-23):
  - Media Library (``media_assets``)
  - Both real OG Academy courses and their full structure (sections, lessons,
    slides, resources, quiz questions/options/accepted answers)
  - Case Simulation DEFINITIONS only (case, documents, tasks, task options,
    task accepted answers) -- never attempts/responses/response_options,
    which are student test data
  - Privacy Policy / Terms of Service pages
  - page_blocks, blog_posts, site_settings
  - The "request-a-quote" inquiry Form and its full structure (the only Form
    not already reproduced by the production seed scripts on the VPS)
  - A Service -> MediaAsset "bridge" (keyed by service slug, never by local
    numeric id) so hero/card/etc. image assignments can be re-applied to
    whichever Service row already exists on the target database

Deliberately EXCLUDED (operational/test data -- see the 2026-09-23
inventory): students, admin test accounts, persons, cases and everything
under them, form_submissions, enrollments/progress, certificates, payments/
charges/payment_requests/refunds, terms_acceptances, tax/W-7/ITIN/DL case
data, email logs, inquiries, activity/rate-limit tables, and every other
Smart Intake's structure (I-90 through W-7 -- production already generates
those from its own seed scripts; re-importing them would create confusing
duplicate rows with different ids than the ones already live).

This script only READS the local SQLite database (plain ``.query()`` calls;
it never calls ``db.session.add``/``commit``/``flush``) and never connects to
any other database. It does not touch the VPS.

Usage:
    python content_migration/export_content.py
    python content_migration/export_content.py --out content_migration/exports/manual_run
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime

TOOL_VERSION = "1.0"

# PageBlock keys whose content_en value is a MediaAsset id (as a string), not
# free text -- these need id remapping on import if the MediaAsset ends up
# with a different id on the target database. Kept as an explicit, known list
# (matches this project's convention of small explicit registries) rather
# than a speculative generic "looks like a number" heuristic.
MEDIA_ID_PAGE_BLOCK_KEYS = {"home_hero_image", "founder_photo", "about_hero_image"}

SERVICE_IMAGE_COLUMNS = ("hero_image_id", "hero_mobile_image_id", "card_image_id", "overview_image_id", "social_image_id")


def _row(obj, exclude=()):
    """Serialize one ORM instance to a plain JSON-safe dict using its own
    mapped columns (correct types via SQLAlchemy, not raw sqlite3 rows)."""
    out = {}
    for col in obj.__table__.columns:
        if col.name in exclude:
            continue
        value = getattr(obj, col.name)
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        out[col.name] = value
    return out


def _add_file(files, stored_path, tag):
    if stored_path:
        files.append((stored_path, tag))


def collect_media_assets():
    from app.models.site_content import MediaAsset

    rows = MediaAsset.query.order_by(MediaAsset.id).all()
    files = []
    for r in rows:
        _add_file(files, r.stored_path, f"media_assets.stored_path#{r.id}")
    return {"media_assets": [_row(r) for r in rows]}, files, {r.id for r in rows}


def collect_academy():
    from app.models.course import Course, CourseSection, Lesson, LessonResource, LessonSlide
    from app.models.progress import QuizQuestion, QuizQuestionAcceptedAnswer, QuizQuestionOption

    courses = Course.query.order_by(Course.id).all()
    course_ids = [c.id for c in courses]
    sections = CourseSection.query.filter(CourseSection.course_id.in_(course_ids)).order_by(CourseSection.id).all()
    section_ids = [s.id for s in sections]
    lessons = Lesson.query.filter(Lesson.section_id.in_(section_ids)).order_by(Lesson.id).all()
    lesson_ids = [l.id for l in lessons]
    slides = LessonSlide.query.filter(LessonSlide.lesson_id.in_(lesson_ids)).order_by(LessonSlide.id).all()
    resources = LessonResource.query.filter(LessonResource.lesson_id.in_(lesson_ids)).order_by(LessonResource.id).all()
    questions = QuizQuestion.query.filter(QuizQuestion.lesson_id.in_(lesson_ids)).order_by(QuizQuestion.id).all()
    question_ids = [q.id for q in questions]
    options = QuizQuestionOption.query.filter(QuizQuestionOption.question_id.in_(question_ids)).order_by(QuizQuestionOption.id).all()
    accepted = QuizQuestionAcceptedAnswer.query.filter(QuizQuestionAcceptedAnswer.question_id.in_(question_ids)).order_by(QuizQuestionAcceptedAnswer.id).all()

    files = []
    for c in courses:
        _add_file(files, c.cover_image, f"courses.cover_image#{c.id}")
        _add_file(files, c.certificate_signature_image, f"courses.certificate_signature_image#{c.id}")
        _add_file(files, c.certificate_logo_image, f"courses.certificate_logo_image#{c.id}")
    for l in lessons:
        _add_file(files, l.video_filename, f"lessons.video_filename#{l.id}")
    for s in slides:
        _add_file(files, s.image_en, f"lesson_slides.image_en#{s.id}")
        _add_file(files, s.audio_en, f"lesson_slides.audio_en#{s.id}")
        _add_file(files, s.image_es, f"lesson_slides.image_es#{s.id}")
        _add_file(files, s.audio_es, f"lesson_slides.audio_es#{s.id}")
    for r in resources:
        _add_file(files, r.file_filename, f"lesson_resources.file_filename#{r.id}")
    for o in options:
        _add_file(files, o.image_filename, f"quiz_question_options.image_filename#{o.id}")

    data = {
        "courses": [_row(x) for x in courses],
        "course_sections": [_row(x) for x in sections],
        "lessons": [_row(x) for x in lessons],
        "lesson_slides": [_row(x) for x in slides],
        "lesson_resources": [_row(x) for x in resources],
        "quiz_questions": [_row(x) for x in questions],
        "quiz_question_options": [_row(x) for x in options],
        "quiz_question_accepted_answers": [_row(x) for x in accepted],
    }
    return data, files


def collect_case_simulation_definitions():
    """Only the static case/document/task/option/accepted-answer definitions.
    Never case_simulation_attempts, case_simulation_responses or
    case_simulation_response_options -- all three are student attempt data
    (response_options in particular joins to case_simulation_responses, a
    test-data table, not to anything a static case defines)."""
    from app.models.case_simulation import (
        CaseSimulation,
        CaseSimulationDocument,
        CaseSimulationTask,
        CaseSimulationTaskAcceptedAnswer,
        CaseSimulationTaskOption,
    )

    sims = CaseSimulation.query.order_by(CaseSimulation.id).all()
    sim_ids = [s.id for s in sims]
    docs = CaseSimulationDocument.query.filter(CaseSimulationDocument.case_simulation_id.in_(sim_ids)).order_by(CaseSimulationDocument.id).all()
    tasks = CaseSimulationTask.query.filter(CaseSimulationTask.case_simulation_id.in_(sim_ids)).order_by(CaseSimulationTask.id).all()
    task_ids = [t.id for t in tasks]
    options = CaseSimulationTaskOption.query.filter(CaseSimulationTaskOption.task_id.in_(task_ids)).order_by(CaseSimulationTaskOption.id).all()
    accepted = CaseSimulationTaskAcceptedAnswer.query.filter(CaseSimulationTaskAcceptedAnswer.task_id.in_(task_ids)).order_by(CaseSimulationTaskAcceptedAnswer.id).all()

    files = []
    for d in docs:
        _add_file(files, d.file_filename, f"case_simulation_documents.file_filename#{d.id}")

    data = {
        "case_simulations": [_row(x) for x in sims],
        "case_simulation_documents": [_row(x) for x in docs],
        "case_simulation_tasks": [_row(x) for x in tasks],
        "case_simulation_task_options": [_row(x) for x in options],
        "case_simulation_task_accepted_answers": [_row(x) for x in accepted],
    }
    return data, files


def collect_legal_pages():
    from app.models.page import Page

    rows = Page.query.filter(Page.slug.in_(["privacy-policy", "terms-of-service"])).order_by(Page.id).all()
    return {"pages": [_row(r) for r in rows]}


def collect_page_blocks():
    from app.models.content_block import PageBlock

    rows = PageBlock.query.order_by(PageBlock.id).all()
    return {"page_blocks": [_row(r) for r in rows]}


def collect_blog_posts():
    from app.models.blog import BlogPost

    rows = BlogPost.query.order_by(BlogPost.id).all()
    files = []
    for r in rows:
        _add_file(files, r.cover_image, f"blog_posts.cover_image#{r.id}")
    return {"blog_posts": [_row(x) for x in rows]}, files


def collect_site_settings():
    from app.models.settings import SiteSettings

    rows = SiteSettings.query.order_by(SiteSettings.id).all()
    files = []
    for r in rows:
        _add_file(files, r.logo_filename, f"site_settings.logo_filename#{r.id}")
    return {"site_settings": [_row(x) for x in rows]}, files


def collect_request_a_quote():
    from app.models.form_builder import ConditionalRule, FieldOption, Form, FormField, FormPage, RuleCondition

    form = Form.query.filter_by(slug="request-a-quote").first()
    if not form:
        return {}, [], None

    pages = FormPage.query.filter_by(form_id=form.id).order_by(FormPage.id).all()
    page_ids = [p.id for p in pages]
    fields = FormField.query.filter(FormField.page_id.in_(page_ids)).order_by(FormField.id).all()
    field_ids = [f.id for f in fields]
    options = FieldOption.query.filter(FieldOption.field_id.in_(field_ids)).order_by(FieldOption.id).all()
    rules = ConditionalRule.query.filter_by(form_id=form.id).order_by(ConditionalRule.id).all()
    rule_ids = [r.id for r in rules]
    conditions = RuleCondition.query.filter(RuleCondition.rule_id.in_(rule_ids)).order_by(RuleCondition.id).all()

    files = []
    for f in fields:
        _add_file(files, f.image_filename, f"form_fields.image_filename#{f.id}")

    data = {
        "forms": [_row(form)],
        "form_pages": [_row(p) for p in pages],
        "form_fields": [_row(f) for f in fields],
        "form_field_options": [_row(o) for o in options],
        "form_conditional_rules": [_row(r) for r in rules],
        "form_rule_conditions": [_row(c) for c in conditions],
    }
    return data, files, form.id


def collect_service_image_bridge(media_asset_ids):
    from app.models.site_content import Service

    services = Service.query.order_by(Service.id).all()
    bridge = []
    for s in services:
        for col in SERVICE_IMAGE_COLUMNS:
            value = getattr(s, col)
            if value and value in media_asset_ids:
                bridge.append({"service_slug": s.slug, "field": col, "media_asset_local_id": value})
    return bridge


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_files_manifest(file_refs, media_dir):
    """Dedupe (relative_path -> [source tags]), verify every file exists on
    disk, and compute a sha256 + size for each. Aborts loudly (never writes a
    partial package) if any referenced file is missing."""
    by_path = {}
    for rel_path, tag in file_refs:
        by_path.setdefault(rel_path, []).append(tag)

    missing = []
    manifest = []
    for rel_path, tags in sorted(by_path.items()):
        full_path = os.path.join(media_dir, rel_path)
        if not os.path.isfile(full_path):
            missing.append((rel_path, tags))
            continue
        manifest.append({
            "relative_path": rel_path.replace("\\", "/"),
            "sha256": _sha256(full_path),
            "size_bytes": os.path.getsize(full_path),
            "referenced_by": tags,
        })

    if missing:
        print("ERROR: the following files are referenced by content being exported but do not exist on disk:", file=sys.stderr)
        for rel_path, tags in missing:
            print(f"  MISSING: {rel_path}  (referenced by: {', '.join(tags)})", file=sys.stderr)
        print(f"\nExpected under: {media_dir}", file=sys.stderr)
        print("Aborting -- no export package was written.", file=sys.stderr)
        sys.exit(1)

    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser.add_argument("--db", default=os.path.join(project_root, "instance", "og_website_v2.db"),
                         help="Path to the local SQLite database (read-only; default: instance/og_website_v2.db)")
    parser.add_argument("--media-dir", default=os.path.join(project_root, "instance", "course_media"),
                         help="Path to the local COURSE_MEDIA_DIR (default: instance/course_media)")
    parser.add_argument("--out", default=None,
                         help="Output directory for the export package (default: content_migration/exports/<timestamp>)")
    args = parser.parse_args()

    if not os.path.isfile(args.db):
        print(f"ERROR: SQLite database not found at {args.db}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(args.media_dir):
        print(f"ERROR: media directory not found at {args.media_dir}", file=sys.stderr)
        sys.exit(1)

    # Force DATABASE_URL to the exact local SQLite file we intend to read,
    # regardless of whatever .env says -- this script never writes to it.
    os.environ["DATABASE_URL"] = "sqlite:///" + os.path.abspath(args.db)
    os.environ.setdefault("APP_ENV", "development")

    from app import create_app

    app = create_app()
    with app.app_context():
        data = {}
        file_refs = []

        media_data, media_files, media_asset_ids = collect_media_assets()
        data.update(media_data)
        file_refs += media_files

        academy_data, academy_files = collect_academy()
        data.update(academy_data)
        file_refs += academy_files

        sim_data, sim_files = collect_case_simulation_definitions()
        data.update(sim_data)
        file_refs += sim_files

        data.update(collect_legal_pages())
        data.update(collect_page_blocks())

        blog_data, blog_files = collect_blog_posts()
        data.update(blog_data)
        file_refs += blog_files

        settings_data, settings_files = collect_site_settings()
        data.update(settings_data)
        file_refs += settings_files

        quote_data, quote_files, quote_form_id = collect_request_a_quote()
        data.update(quote_data)
        file_refs += quote_files

        data["service_image_bridge"] = collect_service_image_bridge(media_asset_ids)

        files_manifest = build_files_manifest(file_refs, args.media_dir)

        # Build the package in a temp dir first; only rename into place if
        # everything (data + every referenced file) succeeds, so a failed run
        # never leaves a half-written package behind.
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        final_out = args.out or os.path.join(project_root, "content_migration", "exports", timestamp)
        final_out = os.path.abspath(final_out)
        os.makedirs(os.path.dirname(final_out), exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="og_export_") as tmp:
            files_dir = os.path.join(tmp, "files")
            for entry in files_manifest:
                src = os.path.join(args.media_dir, entry["relative_path"])
                dst = os.path.join(files_dir, entry["relative_path"])
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)

            with open(os.path.join(tmp, "data.json"), "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False, sort_keys=True)

            with open(os.path.join(tmp, "files_manifest.json"), "w", encoding="utf-8") as fh:
                json.dump(files_manifest, fh, indent=2, ensure_ascii=False, sort_keys=True)

            manifest = {
                "tool_version": TOOL_VERSION,
                "generated_at_utc": datetime.utcnow().isoformat() + "Z",
                "source": {"engine": "sqlite", "db_file": os.path.basename(args.db)},
                "media_id_page_block_keys": sorted(MEDIA_ID_PAGE_BLOCK_KEYS),
                "request_a_quote_form_local_id": quote_form_id,
                "row_counts": {k: len(v) for k, v in data.items() if isinstance(v, list)},
                "file_count": len(files_manifest),
                "file_total_bytes": sum(e["size_bytes"] for e in files_manifest),
                "excluded_note": (
                    "Operational/test data (students, cases, submissions, payments, other Smart "
                    "Intakes, etc.) is deliberately excluded -- see the 2026-09-23 migration plan."
                ),
            }
            with open(os.path.join(tmp, "manifest.json"), "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=2, ensure_ascii=False, sort_keys=True)

            if os.path.exists(final_out):
                print(f"ERROR: output directory already exists: {final_out}", file=sys.stderr)
                sys.exit(1)
            # copytree (not move) so the TemporaryDirectory context manager can still
            # clean up `tmp` normally on exit below, instead of erroring on an already-
            # vacated path.
            shutil.copytree(tmp, final_out)

        print("Export complete.")
        print(f"Package: {final_out}")
        print(f"Rows: {manifest['row_counts']}")
        print(f"Files: {manifest['file_count']} ({manifest['file_total_bytes'] / (1024*1024):.1f} MB)")


if __name__ == "__main__":
    main()
