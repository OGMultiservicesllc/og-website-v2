"""Backfills QuizQuestionOption rows for every pre-existing QuizQuestion built
under the old fixed 4-option (A/B/C/D) system, so they render/grade through
the same normalized path as questions created in the new multi-type Quiz
Builder. Purely additive: the legacy option_a..d/correct_option columns are
left completely untouched (never dropped, never modified) — this script only
ADDS QuizQuestionOption rows derived from them.

Idempotent: skips any question that already has options (safe to re-run).

Run once: .venv/Scripts/python.exe scripts/migrate_quiz_questions.py
"""

from app import create_app
from app.extensions import db
from app.models import QuizQuestion, QuizQuestionOption


def run():
    app = create_app()
    with app.app_context():
        migrated = 0
        skipped = 0
        for question in QuizQuestion.query.all():
            if question.options:
                skipped += 1
                continue
            if not question.option_a_en:
                # Not a legacy 4-option question (e.g. already created as some
                # other type with no options yet) — nothing to backfill.
                skipped += 1
                continue

            for i, letter in enumerate(["a", "b", "c", "d"]):
                en = getattr(question, f"option_{letter}_en")
                es = getattr(question, f"option_{letter}_es")
                if not en:
                    continue
                db.session.add(QuizQuestionOption(
                    question_id=question.id, text_en=en, text_es=es or en,
                    is_correct=(question.correct_option == letter), sort_order=i,
                ))
            question.question_type = "single_choice"
            migrated += 1

        db.session.commit()
        print(f"Migrated {migrated} legacy question(s) to normalized options. Skipped {skipped} (already migrated or no legacy options).")


if __name__ == "__main__":
    run()
