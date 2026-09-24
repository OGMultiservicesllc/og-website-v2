"""Pure deterministic grading for OG Forensic Training's Case Simulation
tasks — kept separate from routes so the scoring rules are easy to verify on
their own, kept separate from the view layer so it can be reasoned about and tested on its own.

multiple_choice, multi_select, and short_answer are graded entirely here, with
no AI involved at all. free_response is graded elsewhere (app/forensic_ai.py)
since it genuinely needs judgment — this module only computes the attempt-level
totals once every task's points_awarded is known."""

import re


def _normalize(text):
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def grade_multiple_choice(task, selected_option_id):
    """Returns (is_correct, points_awarded)."""
    if selected_option_id is None:
        return False, 0
    correct_ids = {o.id for o in task.options if o.is_correct}
    is_correct = selected_option_id in correct_ids
    return is_correct, (task.points if is_correct else 0)


def grade_multi_select(task, selected_option_ids):
    """Exact-set match: every correct option selected, no incorrect ones —
    no partial credit, per the approved plan (simplicity over a partial-credit
    formula that would need its own tie-breaking rules)."""
    correct_ids = {o.id for o in task.options if o.is_correct}
    selected_ids = set(selected_option_ids or [])
    is_correct = bool(correct_ids) and selected_ids == correct_ids
    return is_correct, (task.points if is_correct else 0)


def grade_short_answer(task, response_text):
    """Compares a normalized (lowercased, punctuation/whitespace-stripped)
    response against every accepted answer (EN and ES), same tolerance
    approach as accepted-answer matching in the quiz module, but without any
    AI call — this stays 100% deterministic."""
    normalized_response = _normalize(response_text)
    if not normalized_response:
        return False, 0
    accepted = set()
    for a in task.accepted_answers:
        accepted.add(_normalize(a.answer_en))
        if a.answer_es:
            accepted.add(_normalize(a.answer_es))
    is_correct = normalized_response in accepted
    return is_correct, (task.points if is_correct else 0)


def points_from_free_response_fraction(task, score_fraction):
    return round(task.points * max(0.0, min(1.0, score_fraction)))


def compute_attempt_totals(case, points_by_task_id):
    """`points_by_task_id` maps task.id -> points_awarded (int) for every
    active task that was scored. Returns (score, max_score, passed)."""
    max_score = case.max_score
    score = sum(points_by_task_id.values())
    passed = None
    if case.passing_score is not None and max_score:
        passed = (score / max_score * 100) >= case.passing_score
    return score, max_score, passed
