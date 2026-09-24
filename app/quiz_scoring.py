"""Pure deterministic grading for OG Academy's multi-type Quiz Builder —
mirrors app/case_scoring.py's role and shape exactly. single_choice,
multi_select, true_false, image_choice, short_answer, and number are graded
entirely here, no AI involved. long_answer and file_upload are never
auto-graded — an admin reviews them (see QUIZ_MANUAL_REVIEW_TYPES)."""

import re


def _normalize(text):
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def grade_single_choice(question, selected_option_id):
    """Also used for true_false and image_choice — same one-correct-option shape."""
    if selected_option_id is None:
        return False, 0
    correct_ids = {o.id for o in question.options if o.is_correct}
    is_correct = selected_option_id in correct_ids
    return is_correct, (question.points if is_correct else 0)


def grade_multi_select(question, selected_option_ids):
    """Exact-set match — every correct option selected, no incorrect ones,
    no partial credit (per spec)."""
    correct_ids = {o.id for o in question.options if o.is_correct}
    selected_ids = set(selected_option_ids or [])
    is_correct = bool(correct_ids) and selected_ids == correct_ids
    return is_correct, (question.points if is_correct else 0)


def grade_short_answer(question, response_text):
    normalized_response = _normalize(response_text)
    if not normalized_response:
        return False, 0
    accepted = set()
    for a in question.accepted_answers:
        accepted.add(_normalize(a.answer_en))
        if a.answer_es:
            accepted.add(_normalize(a.answer_es))
    is_correct = normalized_response in accepted
    return is_correct, (question.points if is_correct else 0)


def grade_number(question, response_value):
    if response_value is None or question.correct_number is None:
        return False, 0
    tolerance = question.number_tolerance or 0
    is_correct = abs(response_value - question.correct_number) <= tolerance
    return is_correct, (question.points if is_correct else 0)


def compute_attempt_totals(lesson, points_by_question_id):
    """`points_by_question_id` maps question.id -> points_awarded (int) for
    every question that was scored (0 for pending manual-review ones).
    Returns (score_percent, score_points, max_score_points)."""
    questions = lesson.quiz_questions
    max_score_points = sum(q.points for q in questions) or 0
    score_points = sum(points_by_question_id.values())
    score_percent = round(score_points / max_score_points * 100) if max_score_points else 0
    return score_percent, score_points, max_score_points
