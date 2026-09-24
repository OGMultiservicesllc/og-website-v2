from datetime import datetime

from app.extensions import db


class LessonProgress(db.Model):
    __tablename__ = "lesson_progress"
    __table_args__ = (db.UniqueConstraint("student_id", "lesson_id", name="uq_student_lesson"),)

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)
    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    completed_at = db.Column(db.DateTime)


QUIZ_QUESTION_TYPES = (
    "single_choice",
    "multi_select",
    "true_false",
    "short_answer",
    "number",
    "long_answer",
    "image_choice",
    "file_upload",
)
# Graded instantly, no admin action needed.
QUIZ_AUTO_GRADED_TYPES = ("single_choice", "multi_select", "true_false", "short_answer", "number", "image_choice")
# Always start as "pending" — an admin marks them correct/incorrect and assigns points later.
QUIZ_MANUAL_REVIEW_TYPES = ("long_answer", "file_upload")


class QuizQuestion(db.Model):
    __tablename__ = "quiz_questions"

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    question_en = db.Column(db.Text, nullable=False)
    question_es = db.Column(db.Text, nullable=False)

    # --- legacy single_choice shape — kept forever, never migrated away from,
    # so every quiz built before the multi-type Quiz Builder keeps working
    # exactly as-is. New questions (any type) do NOT use these columns —
    # they use QuizQuestionOption instead (see below). Nullable because only
    # legacy rows populate them now.
    option_a_en = db.Column(db.String(300))
    option_a_es = db.Column(db.String(300))
    option_b_en = db.Column(db.String(300))
    option_b_es = db.Column(db.String(300))
    option_c_en = db.Column(db.String(300))
    option_c_es = db.Column(db.String(300))
    option_d_en = db.Column(db.String(300))
    option_d_es = db.Column(db.String(300))
    correct_option = db.Column(db.String(1))  # 'a' | 'b' | 'c' | 'd' — legacy only

    # --- multi-type Quiz Builder fields
    question_type = db.Column(db.String(20), nullable=False, default="single_choice", server_default="single_choice")
    points = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    required = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    feedback_correct_en = db.Column(db.Text)
    feedback_correct_es = db.Column(db.Text)
    feedback_incorrect_en = db.Column(db.Text)
    feedback_incorrect_es = db.Column(db.Text)
    # question_type == "number" only
    correct_number = db.Column(db.Float)
    number_tolerance = db.Column(db.Float, nullable=False, default=0, server_default="0")

    options = db.relationship(
        "QuizQuestionOption", backref="question", order_by="QuizQuestionOption.sort_order",
        cascade="all, delete-orphan",
    )
    accepted_answers = db.relationship(
        "QuizQuestionAcceptedAnswer", backref="question", cascade="all, delete-orphan",
    )

    def question(self, lang):
        return self.question_es if lang == "es" and self.question_es else self.question_en

    def option(self, letter, lang):
        """Legacy accessor — only meaningful for un-migrated rows that still
        carry option_a..d. New code should use `options` instead."""
        value = getattr(self, f"option_{letter}_{'es' if lang == 'es' else 'en'}")
        return value or getattr(self, f"option_{letter}_en")

    def feedback_correct(self, lang):
        return (self.feedback_correct_es if lang == "es" else self.feedback_correct_en) or ""

    def feedback_incorrect(self, lang):
        return (self.feedback_incorrect_es if lang == "es" else self.feedback_incorrect_en) or ""


class QuizQuestionOption(db.Model):
    """One choice for single_choice / multi_select / true_false / image_choice.
    Same role CaseSimulationTaskOption plays for Case Simulation tasks."""

    __tablename__ = "quiz_question_options"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("quiz_questions.id"), nullable=False)

    # Text, not a bounded VARCHAR: most options are short, but a quiz answer
    # choice can legitimately be a full sentence (e.g. a NJ Notary exam
    # option describing a specific notarial act) -- confirmed 306 chars found
    # in real content during the PostgreSQL VARCHAR(300) full-package audit,
    # 2026-09-23 (see migration b263d7c3e69e).
    text_en = db.Column(db.Text)
    text_es = db.Column(db.Text)
    image_filename = db.Column(db.String(255))  # question_type == "image_choice" only
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def text(self, lang):
        return (self.text_es if lang == "es" else self.text_en) or self.text_en or ""


class QuizQuestionAcceptedAnswer(db.Model):
    """One accepted answer for a short_answer question — same shape as
    CaseSimulationTaskAcceptedAnswer."""

    __tablename__ = "quiz_question_accepted_answers"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("quiz_questions.id"), nullable=False)

    answer_en = db.Column(db.String(300), nullable=False)
    answer_es = db.Column(db.String(300))


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)
    score_percent = db.Column(db.Integer, nullable=False)
    passed = db.Column(db.Boolean)  # nullable: null while status == "needs_review" — not yet determined
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    # New, additive — existing rows default to "graded" (they were always
    # fully auto-graded under the old single_choice-only system).
    status = db.Column(db.String(20), nullable=False, default="graded", server_default="graded")
    score_points = db.Column(db.Integer)
    max_score_points = db.Column(db.Integer)

    responses = db.relationship(
        "QuizResponse", backref="attempt", cascade="all, delete-orphan",
    )
    student = db.relationship("Student")
    lesson = db.relationship("Lesson")


class QuizResponse(db.Model):
    """One question's response within one attempt — did NOT exist before;
    previously only the aggregate score_percent/passed was stored. Purely
    additive: no historical data to migrate into this table."""

    __tablename__ = "quiz_responses"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("quiz_attempts.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("quiz_questions.id"), nullable=False)

    selected_option_id = db.Column(db.Integer, db.ForeignKey("quiz_question_options.id"))  # single_choice/true_false/image_choice
    response_text = db.Column(db.Text)  # short_answer / long_answer
    response_number = db.Column(db.Float)  # number
    file_filename = db.Column(db.String(255))  # file_upload

    is_correct = db.Column(db.Boolean)  # auto-graded types only
    points_awarded = db.Column(db.Integer, nullable=False, default=0)

    reviewed_by_admin = db.Column(db.Boolean, nullable=False, default=False)
    admin_feedback = db.Column(db.Text)
    reviewed_at = db.Column(db.DateTime)

    question = db.relationship("QuizQuestion")
    selected_option = db.relationship("QuizQuestionOption")
    selected_options = db.relationship(
        "QuizQuestionOption", secondary="quiz_response_options", order_by="QuizQuestionOption.sort_order",
    )


class QuizResponseOption(db.Model):
    """Normalized join table for multi_select responses."""

    __tablename__ = "quiz_response_options"

    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey("quiz_responses.id"), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey("quiz_question_options.id"), nullable=False)


class Submission(db.Model):
    __tablename__ = "submissions"
    __table_args__ = (db.UniqueConstraint("student_id", "lesson_id", name="uq_student_lesson_submission"),)

    STATUS_SUBMITTED = "submitted"
    STATUS_NEEDS_REVISION = "needs_revision"
    STATUS_APPROVED = "approved"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)

    text_response = db.Column(db.Text)
    file_filename = db.Column(db.String(255))
    status = db.Column(db.String(20), nullable=False, default=STATUS_SUBMITTED)
    feedback = db.Column(db.Text)

    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)

    student = db.relationship("Student")


class Certificate(db.Model):
    __tablename__ = "certificates"
    __table_args__ = (db.UniqueConstraint("student_id", "course_id", name="uq_student_course_cert"),)

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_filename = db.Column(db.String(255))
    status = db.Column(db.String(20), nullable=False, default="valid", server_default="valid")  # "valid" | "revoked"
    revoked_at = db.Column(db.DateTime)

    student = db.relationship("Student")
    course = db.relationship("Course")

    @property
    def is_revoked(self):
        return self.status == "revoked"
