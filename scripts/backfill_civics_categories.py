"""Backfills CivicsQuestion.category from the official USCIS number ranges — matches
the section headers in the source PDF exactly. Does not touch question/answer text.

Run once: .venv/Scripts/python.exe scripts/backfill_civics_categories.py
"""

from app import create_app
from app.extensions import db
from app.models import CivicsQuestion

RANGES = [
    (1, 15, "gov_principles"),
    (16, 62, "gov_system"),
    (63, 72, "gov_rights"),
    (73, 89, "history_colonial"),
    (90, 99, "history_1800s"),
    (100, 118, "history_recent"),
    (119, 124, "symbols"),
    (125, 128, "holidays"),
]


def run():
    app = create_app()
    with app.app_context():
        updated = 0
        for lo, hi, category in RANGES:
            rows = CivicsQuestion.query.filter(CivicsQuestion.number >= lo, CivicsQuestion.number <= hi).all()
            for row in rows:
                row.category = category
                updated += 1
        db.session.commit()
        print(f"Updated category on {updated} questions.")


if __name__ == "__main__":
    run()
