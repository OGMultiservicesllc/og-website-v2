from datetime import datetime

from app.extensions import db

LESSON_TYPES = (
    "text",
    "video",
    "presentation",
    "quiz",
    "assignment",
    "case_simulation",
)

CERTIFICATE_TRIGGERS = ("course_completion", "final_exam_passed")
CERTIFICATE_TEMPLATES = ("classic", "modern", "premium")
CERTIFICATE_DEFAULTS = {
    "title": "Certificate of Completion",
    "issuer_name": "OG Academy",
    "issuer_subtitle": "A Division of OG Multiservices LLC",
    "signatory_name": "Marcos Ogando",
    "signatory_title": "Founder / Instructor",
}


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    category = db.Column(db.String(100))

    title_en = db.Column(db.String(200), nullable=False)
    title_es = db.Column(db.String(200), nullable=False)
    subtitle_en = db.Column(db.String(300))
    subtitle_es = db.Column(db.String(300))
    description_en = db.Column(db.Text)
    description_es = db.Column(db.Text)

    cover_image = db.Column(db.String(255))
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    access_duration_days = db.Column(db.Integer)  # null = unlimited access
    price_cents = db.Column(db.Integer)  # null or 0 = free enrollment; otherwise Model A "Enroll & Pay" (see app/payments.py)
    accent_color = db.Column(db.String(7))  # e.g. "#1e6bd6"; null = default academy color

    # certificate settings — all optional, fall back to CERTIFICATE_DEFAULTS below
    certificate_enabled = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    certificate_trigger = db.Column(db.String(30), nullable=False, default="course_completion", server_default="course_completion")  # "course_completion" | "final_exam_passed"
    certificate_template = db.Column(db.String(20), nullable=False, default="classic", server_default="classic")  # "classic" | "modern" | "premium"
    certificate_title = db.Column(db.String(200))
    certificate_issuer_name = db.Column(db.String(200))
    certificate_issuer_subtitle = db.Column(db.String(200))
    certificate_signatory_name = db.Column(db.String(200))
    certificate_signatory_title = db.Column(db.String(200))
    certificate_signature_image = db.Column(db.String(255))
    certificate_logo_image = db.Column(db.String(255))
    certificate_show_qr = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    certificate_show_id = db.Column(db.Boolean, nullable=False, default=True, server_default="1")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sections = db.relationship(
        "CourseSection",
        backref="course",
        order_by="CourseSection.sort_order",
        cascade="all, delete-orphan",
    )

    def title(self, lang):
        return self.title_es if lang == "es" and self.title_es else self.title_en

    def subtitle(self, lang):
        return (self.subtitle_es if lang == "es" else self.subtitle_en) or ""

    def description(self, lang):
        return (self.description_es if lang == "es" else self.description_en) or ""

    @property
    def lesson_count(self):
        return sum(len(section.lessons) for section in self.sections)

    def cert_title(self):
        return self.certificate_title or CERTIFICATE_DEFAULTS["title"]

    def cert_issuer_name(self):
        return self.certificate_issuer_name or CERTIFICATE_DEFAULTS["issuer_name"]

    def cert_issuer_subtitle(self):
        return self.certificate_issuer_subtitle or CERTIFICATE_DEFAULTS["issuer_subtitle"]

    def cert_signatory_name(self):
        return self.certificate_signatory_name or CERTIFICATE_DEFAULTS["signatory_name"]

    def cert_signatory_title(self):
        return self.certificate_signatory_title or CERTIFICATE_DEFAULTS["signatory_title"]


class CourseSection(db.Model):
    __tablename__ = "course_sections"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)

    title_en = db.Column(db.String(200), nullable=False)
    title_es = db.Column(db.String(200), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lessons = db.relationship(
        "Lesson",
        backref="section",
        order_by="Lesson.sort_order",
        cascade="all, delete-orphan",
    )

    def title(self, lang):
        return self.title_es if lang == "es" and self.title_es else self.title_en


class Lesson(db.Model):
    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey("course_sections.id"), nullable=False)

    lesson_type = db.Column(db.String(20), nullable=False, default="text")
    title_en = db.Column(db.String(200), nullable=False)
    title_es = db.Column(db.String(200), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_preview = db.Column(db.Boolean, nullable=False, default=False)

    # type = "text"
    content_en = db.Column(db.Text)
    content_es = db.Column(db.Text)

    # type = "video"
    video_source = db.Column(db.String(20))  # "upload" | "external"
    video_filename = db.Column(db.String(255))
    video_external_url = db.Column(db.String(500))

    # type = "quiz"
    quiz_kind = db.Column(db.String(20), nullable=False, default="final", server_default="final")  # "final" | "formative"
    quiz_passing_percentage = db.Column(db.Integer, nullable=False, default=70)
    quiz_max_attempts = db.Column(db.Integer)  # null = unlimited
    quiz_allow_retry = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    quiz_show_results = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    quiz_show_correct_answers = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    quiz_questions_per_page = db.Column(db.Integer, nullable=False, default=8, server_default="8")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    slides = db.relationship(
        "LessonSlide",
        backref="lesson",
        order_by="LessonSlide.sort_order",
        cascade="all, delete-orphan",
    )
    quiz_questions = db.relationship(
        "QuizQuestion",
        backref="lesson",
        order_by="QuizQuestion.sort_order",
        cascade="all, delete-orphan",
    )
    resources = db.relationship(
        "LessonResource",
        backref="lesson",
        order_by="LessonResource.sort_order",
        cascade="all, delete-orphan",
    )
    submissions = db.relationship(
        "Submission",
        backref="lesson",
        cascade="all, delete-orphan",
    )

    def title(self, lang):
        return self.title_es if lang == "es" and self.title_es else self.title_en

    def content(self, lang):
        return (self.content_es if lang == "es" else self.content_en) or ""


class LessonSlide(db.Model):
    __tablename__ = "lesson_slides"

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)

    image_en = db.Column(db.String(255))
    audio_en = db.Column(db.String(255))
    image_es = db.Column(db.String(255))
    audio_es = db.Column(db.String(255))
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def image(self, lang):
        return (self.image_es if lang == "es" else self.image_en)

    def audio(self, lang):
        return (self.audio_es if lang == "es" else self.audio_en)


class LessonResource(db.Model):
    __tablename__ = "lesson_resources"

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)

    title_en = db.Column(db.String(200), nullable=False)
    title_es = db.Column(db.String(200), nullable=False)
    file_filename = db.Column(db.String(255))
    external_url = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def title(self, lang):
        return self.title_es if lang == "es" and self.title_es else self.title_en
