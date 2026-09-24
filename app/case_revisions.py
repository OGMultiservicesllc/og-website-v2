"""Reopen / resubmit change tracking for CASE-LEVEL intakes (Tax, NJ Driver License) — the `CaseRevision` counterpart
to `app.reopen`'s `SubmissionRevision` mechanism for the generic Forms-engine intakes (I-90, N-400, I-130, ...).
Both dedicated modules (`app.tax`, `app.driver_license`) already share the SAME declarative interview framework
(`app.tax.questions.Step/Q/Opt`), so one generic answer-diff works for both instead of writing it twice.

    Submitted --(reopened: admin OR, for NJ Driver License only, the customer)--> Reopened --(resubmit)--> Submitted

`reopened_by` records WHO reopened it ("admin" or "customer") so the audit trail and Admin's change summary are
identical regardless of which self-service or staff action triggered the cycle."""

import json
from datetime import datetime

from app.extensions import db
from app.models import CaseRevision
from app.tax.questions import pick


def _value_label(config, key, value, lang):
    if value in (None, "", []):
        return ""
    q = config.index().get(key)
    if q is None:
        return str(value)
    if isinstance(value, list):
        return ", ".join(filter(None, (_value_label(config, key, v, lang) for v in value)))
    opts = q.options if not callable(q.options) else []
    o = next((x for x in opts if x.value == value), None)
    return pick(o.label, lang) if o else str(value)


def snapshot_answers(config, ctx):
    """{question_key: value} for EVERY question the config declares, read through `ctx.v()` — the SAME accessor
    the review screen and admin summary use, so a bound Person fact (name, address, date of birth — exactly the
    kind of thing a customer corrects) is captured identically to a plain case answer. Never trust `case.answers`
    alone for a diff: that dict only holds the UN-bound answers."""
    return {key: ctx.v(key) for key in config.index()}


def open_revision(case, message, *, actor, actor_id, before_answers):
    """actor: "admin" | "customer". `before_answers` is a plain {question_key: value} dict — the answers as they
    stood the moment this reopen happened, used later to compute the change summary."""
    now = datetime.utcnow()
    rev = CaseRevision(case_id=case.id, reopened_at=now, reopened_by=actor, reopened_by_id=actor_id,
                       reopen_message=(message or "").strip() or None, before_json=json.dumps(before_answers, ensure_ascii=False))
    db.session.add(rev)
    db.session.commit()
    return rev


def diff_answers(config, before, after, lang="en"):
    """[{key, label, before, after}] for every answer that changed, human-readable via the SAME question labels
    the customer's own review screen uses (`config.index()[key].label`)."""
    changes = []
    for key in list(dict.fromkeys(list(after) + list(before))):
        b, a = before.get(key), after.get(key)
        if b == a:
            continue
        b_text, a_text = _value_label(config, key, b, lang), _value_label(config, key, a, lang)
        if b_text == a_text:
            continue
        q = config.index().get(key)
        label = pick(q.label, lang) if q is not None else key
        changes.append({"key": key, "label": label, "before": b_text, "after": a_text})
    return changes


def close_revision(case, config, after_answers, lang="en"):
    """Closes the currently-open revision (the one from the most recent `open_revision`) with a computed diff.
    Returns (revision, changes) or (None, []) if nothing was open."""
    rev = next((r for r in reversed(case.revisions) if r.resubmitted_at is None), None)
    if rev is None:
        return None, []
    before = json.loads(rev.before_json or "{}")
    changes = diff_answers(config, before, after_answers, lang)
    rev.resubmitted_at = datetime.utcnow()
    rev.after_json = json.dumps(after_answers, ensure_ascii=False)
    rev.changes_json = json.dumps(changes, ensure_ascii=False)
    db.session.commit()
    return rev, changes


def revision_changes(revision):
    try:
        return json.loads(revision.changes_json or "[]")
    except ValueError:
        return []


def history(case):
    return list(case.revisions)
