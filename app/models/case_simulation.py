from datetime import datetime

from app.extensions import db

# "Forensic" here means deep document/information review for tax prep and
# compliance-adjacent training — never criminal forensics. See CaseSimulation
# below; nothing in this module implies a certification, IRS approval, or any
# regulatory claim — that content is entirely admin-authored.
TASK_TYPES = ("multiple_choice", "multi_select", "short_answer", "free_response")
ATTEMPT_STATUSES = ("in_progress", "submitted", "needs_review")


class CaseSimulation(db.Model):
    """1:1 with a Lesson (lesson_type="case_simulation"). Holds the
    case's static definition; CaseSimulationAttempt holds what a student did
    with it."""

    __tablename__ = "case_simulations"

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), unique=True, nullable=False)

    title_en = db.Column(db.String(200), nullable=False)
    title_es = db.Column(db.String(200), nullable=False)
    description_en = db.Column(db.Text)
    description_es = db.Column(db.Text)
    client_profile_en = db.Column(db.Text)
    client_profile_es = db.Column(db.Text)
    instructions_en = db.Column(db.Text)
    instructions_es = db.Column(db.Text)

    passing_score = db.Column(db.Integer)  # percent 0-100; null = no pass/fail criteria
    max_attempts = db.Column(db.Integer)  # null = unlimited

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lesson = db.relationship("Lesson", backref=db.backref("case_simulation", uselist=False))
    documents = db.relationship(
        "CaseSimulationDocument", backref="case", order_by="CaseSimulationDocument.sort_order",
        cascade="all, delete-orphan",
    )
    tasks = db.relationship(
        "CaseSimulationTask", backref="case", order_by="CaseSimulationTask.sort_order",
        cascade="all, delete-orphan",
    )

    def title(self, lang):
        return self.title_es if lang == "es" and self.title_es else self.title_en

    def description(self, lang):
        return (self.description_es if lang == "es" else self.description_en) or ""

    def client_profile(self, lang):
        return (self.client_profile_es if lang == "es" else self.client_profile_en) or ""

    def instructions(self, lang):
        return (self.instructions_es if lang == "es" else self.instructions_en) or ""

    @property
    def active_documents(self):
        return [d for d in self.documents if d.is_active]

    @property
    def active_tasks(self):
        return [t for t in self.tasks if t.is_active]

    @property
    def max_score(self):
        return sum(t.points for t in self.active_tasks)


class CaseSimulationDocument(db.Model):
    __tablename__ = "case_simulation_documents"

    id = db.Column(db.Integer, primary_key=True)
    case_simulation_id = db.Column(db.Integer, db.ForeignKey("case_simulations.id"), nullable=False)

    label_en = db.Column(db.String(200), nullable=False)
    label_es = db.Column(db.String(200), nullable=False)
    doc_type = db.Column(db.String(60))  # free text: "W-2", "1099-NEC", "ID"...
    file_filename = db.Column(db.String(255), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def label(self, lang):
        return self.label_es if lang == "es" and self.label_es else self.label_en

    @property
    def is_pdf(self):
        return (self.file_filename or "").lower().endswith(".pdf")


class CaseSimulationTask(db.Model):
    __tablename__ = "case_simulation_tasks"

    id = db.Column(db.Integer, primary_key=True)
    case_simulation_id = db.Column(db.Integer, db.ForeignKey("case_simulations.id"), nullable=False)

    task_type = db.Column(db.String(20), nullable=False)
    prompt_en = db.Column(db.Text, nullable=False)
    prompt_es = db.Column(db.Text, nullable=False)
    explanation_en = db.Column(db.Text)  # shown after grading, deterministic types only
    explanation_es = db.Column(db.Text)
    points = db.Column(db.Integer, nullable=False, default=1)
    requires_justification = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # task_type == "free_response" only — the MVP rubric (see plan §6/§7):
    # a model answer + short grading notes, not a multi-table rubric system.
    expected_response_en = db.Column(db.Text)
    expected_response_es = db.Column(db.Text)
    rubric_notes_en = db.Column(db.Text)
    rubric_notes_es = db.Column(db.Text)

    options = db.relationship(
        "CaseSimulationTaskOption", backref="task", order_by="CaseSimulationTaskOption.sort_order",
        cascade="all, delete-orphan",
    )
    accepted_answers = db.relationship(
        "CaseSimulationTaskAcceptedAnswer", backref="task", cascade="all, delete-orphan",
    )

    def prompt(self, lang):
        return self.prompt_es if lang == "es" and self.prompt_es else self.prompt_en

    def explanation(self, lang):
        return (self.explanation_es if lang == "es" else self.explanation_en) or ""

    def expected_response(self, lang):
        return (self.expected_response_es if lang == "es" else self.expected_response_en) or ""

    def rubric_notes(self, lang):
        return (self.rubric_notes_es if lang == "es" else self.rubric_notes_en) or ""


class CaseSimulationTaskOption(db.Model):
    """One choice for a multiple_choice or multi_select task."""

    __tablename__ = "case_simulation_task_options"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("case_simulation_tasks.id"), nullable=False)

    # Text, not a bounded VARCHAR: plays the same role as
    # QuizQuestionOption.text_en/es (same "a choice can be a full sentence"
    # risk), widened alongside it during the PostgreSQL VARCHAR(300)
    # full-package audit, 2026-09-23 (see migration b263d7c3e69e), even though
    # this specific package's Case Simulation content stayed under 300 chars.
    text_en = db.Column(db.Text, nullable=False)
    text_es = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def text(self, lang):
        return self.text_es if lang == "es" and self.text_es else self.text_en


class CaseSimulationTaskAcceptedAnswer(db.Model):
    """One accepted answer for a short_answer task — same shape/role as
    QuizQuestionAcceptedAnswer, normalized rather than a comma-joined string."""

    __tablename__ = "case_simulation_task_accepted_answers"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("case_simulation_tasks.id"), nullable=False)

    answer_en = db.Column(db.String(300), nullable=False)
    answer_es = db.Column(db.String(300))


class CaseSimulationAttempt(db.Model):
    __tablename__ = "case_simulation_attempts"

    id = db.Column(db.Integer, primary_key=True)
    case_simulation_id = db.Column(db.Integer, db.ForeignKey("case_simulations.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)

    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)
    score = db.Column(db.Integer)  # points earned; null until submitted
    max_score = db.Column(db.Integer)  # points possible at submit time (case content may change later)
    passed = db.Column(db.Boolean)  # null if case has no passing_score, or not yet resolved
    status = db.Column(db.String(20), nullable=False, default="in_progress")

    case = db.relationship("CaseSimulation")
    student = db.relationship("Student")
    responses = db.relationship(
        "CaseSimulationResponse", backref="attempt", cascade="all, delete-orphan",
    )

    @property
    def score_percent(self):
        if not self.max_score:
            return 0
        return round((self.score or 0) / self.max_score * 100)


class CaseSimulationResponse(db.Model):
    __tablename__ = "case_simulation_responses"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("case_simulation_attempts.id"), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("case_simulation_tasks.id"), nullable=False)

    selected_option_id = db.Column(db.Integer, db.ForeignKey("case_simulation_task_options.id"))  # multiple_choice
    response_text = db.Column(db.Text)  # short_answer / free_response
    justification_text = db.Column(db.Text)  # when task.requires_justification

    is_correct = db.Column(db.Boolean)  # deterministic types only
    points_awarded = db.Column(db.Integer, nullable=False, default=0)

    ai_feedback_en = db.Column(db.Text)
    ai_feedback_es = db.Column(db.Text)
    reviewed_by_ai = db.Column(db.Boolean, nullable=False, default=False)
    reviewed_by_admin = db.Column(db.Boolean, nullable=False, default=False)

    task = db.relationship("CaseSimulationTask")
    selected_option = db.relationship("CaseSimulationTaskOption")
    selected_options = db.relationship(
        "CaseSimulationTaskOption", secondary="case_simulation_response_options", order_by="CaseSimulationTaskOption.sort_order",
    )

    def ai_feedback(self, lang):
        return (self.ai_feedback_es if lang == "es" else self.ai_feedback_en) or ""


class CaseSimulationResponseOption(db.Model):
    """Normalized join table for multi_select responses — replaces a
    selected_option_ids blob with a real relation."""

    __tablename__ = "case_simulation_response_options"

    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey("case_simulation_responses.id"), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey("case_simulation_task_options.id"), nullable=False)
