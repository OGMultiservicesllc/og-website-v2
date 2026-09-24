"""NJ Knowledge Test practice engine: quick (10), by-topic, and full (50-question) simulation, drawn from the original
`DlQuestion` bank. An account is required to start (never anonymous — see the public routes), but starting practice never
creates a Driver License Case (`dl_case_id` is set only when the student already has one, purely informational).

This is a dedicated small model (`DlAttempt`/`DlAttemptResponse`), not the Academy's `QuizQuestion`/`QuizAttempt`: those are
one-quiz-per-lesson and have no topic/difficulty tagging or randomized draw across a shared bank, which this needs."""

import random

from app.extensions import db
from app.models import DL_TOPICS, DlAttempt, DlAttemptResponse, DlQuestion

MODE_COUNTS = {"quick": 10, "full": 50}
PASS_PERCENT = 80


def bank_size(topic=None):
    q = DlQuestion.query.filter_by(active=True)
    if topic:
        q = q.filter_by(topic=topic)
    return q.count()


def _draw(count, topic=None):
    """Random questions, spread across topics as evenly as practical for quick/full modes (never the same 50 every time
    once the bank is larger than the draw size)."""
    q = DlQuestion.query.filter_by(active=True)
    if topic:
        pool = q.filter_by(topic=topic).all()
        random.shuffle(pool)
        return pool[:count]
    by_topic = {}
    for row in q.all():
        by_topic.setdefault(row.topic, []).append(row)
    for rows in by_topic.values():
        random.shuffle(rows)
    topics = list(by_topic)
    random.shuffle(topics)
    out, i = [], 0
    while len(out) < count and any(by_topic.values()):
        t = topics[i % len(topics)]
        if by_topic[t]:
            out.append(by_topic[t].pop())
        i += 1
        if i > count * len(DL_TOPICS) + 50:
            break
    random.shuffle(out)
    return out[:count]


def start_attempt(student, mode, lang, *, topic=None, dl_case_id=None):
    count = MODE_COUNTS.get(mode, 10) if mode != "topic" else 10
    questions = _draw(count, topic if mode == "topic" else None)
    attempt = DlAttempt(student_id=student.id, dl_case_id=dl_case_id, mode=mode, topic_filter=topic if mode == "topic" else None, language=lang, total=len(questions))
    db.session.add(attempt)
    db.session.flush()
    for i, q in enumerate(questions):
        db.session.add(DlAttemptResponse(attempt_id=attempt.id, question_id=q.id, sort_order=i))
    db.session.commit()
    return attempt


def owned_attempt(student, attempt_id):
    a = DlAttempt.query.filter_by(id=attempt_id, student_id=student.id).first()
    return a


def current_response(attempt, n):
    """1-based question number -> its DlAttemptResponse, or None past the end."""
    rows = sorted(attempt.responses, key=lambda r: r.sort_order)
    return rows[n - 1] if 1 <= n <= len(rows) else None


def answer(attempt, n, option_id):
    resp = current_response(attempt, n)
    if resp is None:
        return None
    opt = next((o for o in resp.question.options if o.id == option_id), None)
    resp.selected_option_id = option_id if opt is not None else None
    resp.is_correct = bool(opt and opt.is_correct)
    db.session.commit()
    return resp


def complete(attempt):
    if attempt.completed_at is not None:
        return attempt
    from datetime import datetime

    correct = sum(1 for r in attempt.responses if r.is_correct)
    attempt.correct = correct
    attempt.percent = int(round(100 * correct / max(1, attempt.total)))
    attempt.passed = attempt.percent >= PASS_PERCENT
    attempt.completed_at = datetime.utcnow()
    db.session.commit()
    return attempt


def topic_performance(attempt):
    by_topic = {}
    for r in attempt.responses:
        t = r.question.topic
        row = by_topic.setdefault(t, {"correct": 0, "total": 0})
        row["total"] += 1
        if r.is_correct:
            row["correct"] += 1
    return by_topic


def history(student, limit=10):
    return DlAttempt.query.filter_by(student_id=student.id).filter(DlAttempt.completed_at.isnot(None)).order_by(DlAttempt.completed_at.desc()).limit(limit).all()


def best_score(student):
    rows = DlAttempt.query.filter_by(student_id=student.id).filter(DlAttempt.completed_at.isnot(None)).all()
    return max((r.percent for r in rows if r.percent is not None), default=None)
