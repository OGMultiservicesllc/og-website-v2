"""remove abandoned citizenship practice system

Removes the "Citizenship Exam Practice & Interview Simulation" course and the
citizenship/N-400-only tables (civics question bank, civics test sessions,
N-400 practice, virtual officers, interview scenarios) plus the Virtual
Interview usage-limit columns on site_settings.

A full JSON archive of this data and a copy of the database were taken to
backups/2026-09-18_pre_redesign before this ran. downgrade() recreates the
empty tables only; it does NOT restore data (use the archive for that).

Revision ID: a1c0de5e0001
Revises: 7dc5e57be2ff
Create Date: 2026-09-18 12:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1c0de5e0001'
down_revision = '7dc5e57be2ff'
branch_labels = None
depends_on = None

CITIZENSHIP_COURSE_SLUG = 'practica-examen-simulacion-entrevista-ciudadania'

DROP_ORDER = [
    'civics_test_answers', 'civics_test_sessions', 'civics_question_flags', 'civics_answers', 'civics_questions',
    'n400_interview_answers', 'n400_interview_sessions', 'n400_questions',
    'interview_scenarios', 'officer_profiles',
]

CREATE_SQL = [
    """CREATE TABLE officer_profiles ( id INTEGER NOT NULL, name VARCHAR(120) NOT NULL, avatar_filename VARCHAR(255), voice VARCHAR(20) NOT NULL, languages VARCHAR(20) NOT NULL, tone_en TEXT, tone_es TEXT, is_active BOOLEAN NOT NULL, sort_order INTEGER NOT NULL, created_at DATETIME, updated_at DATETIME, PRIMARY KEY (id) )""",
    """CREATE TABLE civics_questions ( id INTEGER NOT NULL, number INTEGER, question_en TEXT NOT NULL, question_es TEXT NOT NULL, is_active BOOLEAN NOT NULL, created_at DATETIME, updated_at DATETIME, required_count INTEGER NOT NULL, category VARCHAR(40), PRIMARY KEY (id) )""",
    """CREATE TABLE civics_answers ( id INTEGER NOT NULL, question_id INTEGER NOT NULL, answer_en VARCHAR(300) NOT NULL, answer_es VARCHAR(300), PRIMARY KEY (id), FOREIGN KEY(question_id) REFERENCES civics_questions (id) )""",
    """CREATE TABLE civics_question_flags ( id INTEGER NOT NULL, student_id INTEGER NOT NULL, question_id INTEGER NOT NULL, flagged_at DATETIME, PRIMARY KEY (id), FOREIGN KEY(question_id) REFERENCES civics_questions (id), FOREIGN KEY(student_id) REFERENCES students (id), CONSTRAINT uq_student_question_flag UNIQUE (student_id, question_id) )""",
    """CREATE TABLE civics_test_sessions ( id INTEGER NOT NULL, student_id INTEGER NOT NULL, lesson_id INTEGER, mode VARCHAR(20) NOT NULL, started_at DATETIME, completed_at DATETIME, questions_asked INTEGER NOT NULL, correct_count INTEGER NOT NULL, incorrect_count INTEGER NOT NULL, passed BOOLEAN, ai_interactions_count INTEGER DEFAULT '0' NOT NULL, end_reason VARCHAR(30), PRIMARY KEY (id), FOREIGN KEY(lesson_id) REFERENCES lessons (id), FOREIGN KEY(student_id) REFERENCES students (id) )""",
    """CREATE TABLE civics_test_answers ( id INTEGER NOT NULL, session_id INTEGER NOT NULL, question_id INTEGER NOT NULL, order_asked INTEGER NOT NULL, student_answer_text TEXT, is_correct BOOLEAN, ai_confidence FLOAT, ai_matched_answer VARCHAR(300), ai_reason TEXT, answered_at DATETIME, PRIMARY KEY (id), FOREIGN KEY(question_id) REFERENCES civics_questions (id), FOREIGN KEY(session_id) REFERENCES civics_test_sessions (id) )""",
    """CREATE TABLE n400_questions ( id INTEGER NOT NULL, number INTEGER, category VARCHAR(40), question_en TEXT NOT NULL, question_es TEXT NOT NULL, sample_answer_en TEXT, sample_answer_es TEXT, rubric_notes_en TEXT, rubric_notes_es TEXT, is_active BOOLEAN NOT NULL, sort_order INTEGER NOT NULL, created_at DATETIME, updated_at DATETIME, PRIMARY KEY (id) )""",
    """CREATE TABLE n400_interview_sessions ( id INTEGER NOT NULL, student_id INTEGER NOT NULL, lesson_id INTEGER, started_at DATETIME, completed_at DATETIME, questions_asked INTEGER NOT NULL, ai_interactions_count INTEGER NOT NULL, end_reason VARCHAR(30), PRIMARY KEY (id), FOREIGN KEY(lesson_id) REFERENCES lessons (id), FOREIGN KEY(student_id) REFERENCES students (id) )""",
    """CREATE TABLE n400_interview_answers ( id INTEGER NOT NULL, session_id INTEGER NOT NULL, question_id INTEGER NOT NULL, order_asked INTEGER NOT NULL, student_answer_text TEXT, ai_feedback_en TEXT, ai_feedback_es TEXT, reviewed_by_ai BOOLEAN NOT NULL, answered_at DATETIME, PRIMARY KEY (id), FOREIGN KEY(question_id) REFERENCES n400_questions (id), FOREIGN KEY(session_id) REFERENCES n400_interview_sessions (id) )""",
    """CREATE TABLE interview_scenarios ( id INTEGER NOT NULL, lesson_id INTEGER NOT NULL, officer_profile_id INTEGER NOT NULL, scenario_type VARCHAR(30) NOT NULL, max_questions INTEGER NOT NULL, passing_score INTEGER NOT NULL, created_at DATETIME, updated_at DATETIME, PRIMARY KEY (id), FOREIGN KEY(lesson_id) REFERENCES lessons (id), FOREIGN KEY(officer_profile_id) REFERENCES officer_profiles (id), UNIQUE (lesson_id) )""",
]


def _ids(conn, sql, params):
    return [r[0] for r in conn.execute(sa.text(sql), params)]


def upgrade():
    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names())

    row = conn.execute(sa.text("SELECT id FROM courses WHERE slug = :s"), {"s": CITIZENSHIP_COURSE_SLUG}).fetchone()
    if row:
        course_id = row[0]
        certs = conn.execute(sa.text("SELECT COUNT(*) FROM certificates WHERE course_id = :c"), {"c": course_id}).scalar()
        if certs:
            raise RuntimeError("Citizenship course has issued certificates; refusing to delete automatically.")

        section_ids = _ids(conn, "SELECT id FROM course_sections WHERE course_id = :c", {"c": course_id})
        lesson_ids = []
        for sid in section_ids:
            lesson_ids += _ids(conn, "SELECT id FROM lessons WHERE section_id = :s", {"s": sid})

        for lid in lesson_ids:
            p = {"l": lid}
            for t in ('civics_test_answers',):
                if t in existing:
                    conn.execute(sa.text("DELETE FROM civics_test_answers WHERE session_id IN (SELECT id FROM civics_test_sessions WHERE lesson_id = :l)"), p)
            if 'civics_test_sessions' in existing:
                conn.execute(sa.text("DELETE FROM civics_test_sessions WHERE lesson_id = :l"), p)
            if 'n400_interview_answers' in existing:
                conn.execute(sa.text("DELETE FROM n400_interview_answers WHERE session_id IN (SELECT id FROM n400_interview_sessions WHERE lesson_id = :l)"), p)
            if 'n400_interview_sessions' in existing:
                conn.execute(sa.text("DELETE FROM n400_interview_sessions WHERE lesson_id = :l"), p)
            if 'interview_scenarios' in existing:
                conn.execute(sa.text("DELETE FROM interview_scenarios WHERE lesson_id = :l"), p)
            for t in ('lesson_progress', 'lesson_resources', 'lesson_slides', 'submissions'):
                if t in existing:
                    conn.execute(sa.text(f"DELETE FROM {t} WHERE lesson_id = :l"), p)
            conn.execute(sa.text("DELETE FROM lessons WHERE id = :l"), p)

        conn.execute(sa.text("DELETE FROM course_sections WHERE course_id = :c"), {"c": course_id})
        conn.execute(sa.text("DELETE FROM enrollments WHERE course_id = :c"), {"c": course_id})
        conn.execute(sa.text("DELETE FROM courses WHERE id = :c"), {"c": course_id})

    for t in DROP_ORDER:
        if t in existing:
            op.drop_table(t)

    cols = {c['name'] for c in sa.inspect(conn).get_columns('site_settings')}
    with op.batch_alter_table('site_settings', schema=None) as batch_op:
        for name in ('interview_max_duration_minutes', 'interview_max_ai_interactions', 'interview_max_daily_attempts'):
            if name in cols:
                batch_op.drop_column(name)


def downgrade():
    with op.batch_alter_table('site_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('interview_max_duration_minutes', sa.Integer(), server_default='15', nullable=False))
        batch_op.add_column(sa.Column('interview_max_ai_interactions', sa.Integer(), server_default='25', nullable=False))
        batch_op.add_column(sa.Column('interview_max_daily_attempts', sa.Integer(), server_default='3', nullable=False))
    for stmt in CREATE_SQL:
        op.execute(stmt)
