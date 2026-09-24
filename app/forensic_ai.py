"""OpenAI-backed grading for OG Forensic Training's free_response case tasks.

Architecture: our own admin-authored content (a model
expected answer + short rubric notes on CaseSimulationTask, see
app/models/case_simulation.py) is the single source of truth. This module only
asks the model to judge how well the student's answer covers that content — it
is explicitly instructed not to invent grading criteria, not to accept an
answer as correct for reasons outside the provided rubric, and never to change
how many points a task is worth (that stays a plain Python calculation in
app/case_scoring.py, driven by CaseSimulationTask.points)."""

import json

from flask import current_app
from openai import OpenAI

_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = (
    "You are grading a free-response answer in a professional training exercise about "
    "reviewing tax-related documents and information (NOT criminal forensics). You are given "
    "the task prompt, a model expected answer/reasoning, short rubric notes describing what a "
    "strong answer should cover, and the student's actual response. Judge how much of the "
    "expected reasoning the student's answer actually covers — partial credit is expected and "
    "normal, not just all-or-nothing. Paraphrases, different wording, and reasonable structure "
    "are all fine. Do NOT invent grading criteria beyond the expected answer and rubric notes "
    "given to you, do NOT credit an answer for being correct about something the rubric doesn't "
    "ask about, and do NOT decide pass/fail — you only estimate what fraction of the expected "
    "reasoning was covered, from 0.0 (missed almost everything) to 1.0 (covered it thoroughly). "
    "If the student gave no answer or a clearly off-topic one, score 0.0."
)

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "score_fraction": {"type": "number", "description": "0.0 to 1.0, how much of the expected reasoning was covered"},
        "feedback_en": {"type": "string", "description": "One short paragraph of feedback for the student, in English"},
        "feedback_es": {"type": "string", "description": "The same feedback, in Spanish"},
    },
    "required": ["score_fraction", "feedback_en", "feedback_es"],
    "additionalProperties": False,
}

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = current_app.config.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        _client = OpenAI(api_key=api_key)
    return _client


def evaluate_free_response(prompt_text, expected_response, rubric_notes, student_response):
    """Returns {"score_fraction": float, "feedback_en": str, "feedback_es": str}.
    Raises on any API/parsing failure — callers must catch this and leave the
    response marked pending manual review rather than losing it or guessing."""
    client = _get_client()
    user_prompt = (
        f"Task prompt: {prompt_text}\n"
        f"Model expected answer/reasoning: {expected_response or '(none provided)'}\n"
        f"Rubric notes: {rubric_notes or '(none provided)'}\n"
        f"Student's response: {(student_response or '').strip() or '(no response given)'}"
    )
    response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "case_free_response_evaluation", "strict": True, "schema": _RESPONSE_SCHEMA},
        },
        temperature=0,
    )
    data = json.loads(response.choices[0].message.content)
    fraction = max(0.0, min(1.0, float(data.get("score_fraction", 0))))
    return {
        "score_fraction": fraction,
        "feedback_en": data.get("feedback_en", ""),
        "feedback_es": data.get("feedback_es", ""),
    }
