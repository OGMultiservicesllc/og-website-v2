"""Shared-data blocks: OFFER -> REVIEW -> CONFIRM / EDIT / RESOLVE a conflict.

A block (declared in app/case_types.py) is a group of application fields that describe facts about a REAL person the customer's data
may already know ("Maria's date of birth" from an N-400 in another case, an I-130 in this one, ...). What can be reused comes from
`persons.offer()`: the facts of the real Person, from any of the customer's cases, never the application's own claims.

  review step   "We already have this information for Maria" + values (with where/when they came from) + [Yes, this is correct] /
                [Review / Edit]. A stable fact that different sources state differently is a CONFLICT: the customer resolves it on a
                separate step first; nothing is ever pre-selected. Time-sensitive facts ask "Is this still current?".
  edit step     the ordinary questions, shown when nothing can be offered, when the customer chose to edit, or (after "correct")
                while a detail nobody could supply is still empty.

`<block>_avail` is recomputed on every visit while the block is UNANSWERED; the decision freezes only when the customer answers it
(the review choice or the edit step is saved). After that, newer/different information never overwrites the confirmed answer: it is
flagged for review (`changes_after_confirmation`). Reuse is never silent: choosing "correct" copies the offered values into the
application's own answers AND records the confirmation on the canonical facts with provenance.
"""

import html
import json

from app import cases as case_svc
from app import persons as pers
from app.case_types import FACTS, config_for, scope_of
from app.extensions import db

ADDR_KEYS = ("is_us", "street", "unit_type", "unit_number", "city", "state", "zip", "province", "postal_code", "country")
MODES = ("correct", "edit")


def blocks_for(form):
    cfg = config_for(form)
    return (cfg or {}).get("blocks") or {}


def _cfg(field):
    if not field.config_json:
        return {}
    try:
        return json.loads(field.config_json)
    except ValueError:
        return {}


def is_kept(field):
    """Answers of a shared block survive while their edit step is skipped (they are confirmed copies, not stale)."""
    return bool(field.config_json) and '"keep"' in field.config_json


def is_system(field):
    """Bookkeeping answers (availability flags, the confirm/edit choice): never shown in Review, Admin or the completeness check."""
    return bool(field.config_json) and '"system"' in field.config_json


def block_of(field):
    if not field.config_json or '"block"' not in field.config_json:
        return None
    return _cfg(field).get("block")


def block_scope(block):
    keys = list(block["fields"]) or []
    return "situational" if keys and all(scope_of(k) == "situational" for k in keys) else "stable"


def edit_followup(form, page, next_page, answers):
    """True when the applicant just chose "Review / Edit" on a block's review step and the next step is that block's edit step:
    coming from Review, they should continue into it instead of bouncing back."""
    if next_page is None:
        return False
    blocks = blocks_for(form)
    for f in page.fields:
        if f.internal_name in blocks and answers.get(f.id) == "edit" and any(block_of(g) == f.internal_name for g in next_page.fields):
            return True
    return False


def review_target(form, page):
    """The step to open when someone wants to change what an (otherwise skipped) block edit step holds: the block's review step."""
    key = next((block_of(f) for f in page.fields if block_of(f)), None)
    if not key:
        return None
    return next((p for p in form.pages if any(f.internal_name == key for f in p.fields)), None)


# ------------------------------------------------------------------ who / what the customer's data knows
def block_person(submission, block):
    if block.get("related"):
        return case_svc.person_related(submission, block["related"])
    return case_svc.role_person(submission, block["role"])


def block_offers(submission, block):
    """(person, {fact_key: offer}) — what can be reused for THIS application, from any of the customer's cases."""
    person = block_person(submission, block)
    if person is None:
        return None, {}
    out = {}
    for key in block["fields"]:
        off = pers.offer(person, key, submission)
        if off is None:
            continue
        only = block["only"].get(key)
        if only == "us" and isinstance(off["value"], dict) and off["value"].get("is_us") == "no":
            continue
        if isinstance(only, (tuple, list)) and off["value"] not in only:  # a stored value this form has no option for is never offered
            continue
        out[key] = off
    return person, out


def is_available(submission, block):
    person, offers = block_offers(submission, block)
    if person is None or not offers:
        return False
    return all(k in offers for k in block["require"])


def pending_conflicts(submission, key):
    block = blocks_for(submission.form).get(key)
    if not block:
        return []
    _person, offers = block_offers(submission, block)
    return [k for k, o in offers.items() if o["status"] == "conflict"]


# ------------------------------------------------------------------ recomputed availability (frozen only once answered)
def _fields(form):
    return {f.internal_name: f for f in form.all_fields}


def _stored(submission):
    return {v.field_internal_name: v.value_text for v in submission.values}


def answered(stored, key):
    return stored.get(key) in MODES


def prime_blocks(submission):
    """Recompute `<block>_avail` for every block the customer has NOT answered yet (an answered block keeps its decision)."""
    from app.intake_shared import _set

    form = submission.form
    blocks = blocks_for(form)
    if not blocks or submission.case_id is None:
        return False
    fields = _fields(form)
    stored = _stored(submission)
    changed = False
    for key, block in blocks.items():
        avail_name = f"{key}_avail"
        if avail_name not in fields or answered(stored, key):
            continue
        avail = "yes" if is_available(submission, block) else "no"
        if stored.get(avail_name) != avail:
            _set(form, submission, fields, avail_name, avail)
            changed = True
        miss_name = f"{key}_missing"
        if miss_name in fields:  # which of the block's details the customer's data cannot supply: only those are asked after "correct"
            _p, offers = block_offers(submission, block)
            missing = [k for k in (block.get("ask") or block["require"]) if k not in offers]
            text = json.dumps(missing)
            if stored.get(miss_name) != text:
                _set(form, submission, fields, miss_name, text)
                changed = True
    if changed:
        db.session.commit()
    return changed


def repair_unanswered(submission):
    """One-time repair of drafts made before availability was recomputed: a block whose choice was only DEFAULTED to "edit" (the
    customer entered nothing in it) is reset to unanswered so it can offer what is now known. Customer-entered answers are never
    touched. Idempotent."""
    form = submission.form
    blocks = blocks_for(form)
    if not blocks or submission.is_complete:
        return 0
    fields = _fields(form)
    stored = _stored(submission)
    n = 0
    for key in blocks:
        if stored.get(key) != "edit":
            continue
        names = [name for name, f in fields.items() if block_of(f) == key]
        if any(stored.get(name) not in (None, "") for name in names):
            continue
        for v in list(submission.values):
            if v.field_internal_name in (key, f"{key}_avail"):
                db.session.delete(v)
                n += 1
    if n:
        db.session.commit()
    return n


# ------------------------------------------------------------------ writing confirmed values into the application
def _as_text(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _map_record(rec, mapping):
    if not mapping:
        return {k: v for k, v in rec.items() if v not in ("", None)}
    return {dst: rec[src] for src, dst in mapping.items() if rec.get(src) not in ("", None, False)}


def materialize(submission, key, block):
    """Copy what was offered (and is not in conflict) into this application's own answers for the block."""
    from app.intake_shared import _set

    form = submission.form
    fields = _fields(form)
    person, offers = block_offers(submission, block)
    done = []
    for fact_key, target in block["fields"].items():
        off = offers.get(fact_key)
        if off is None or off["status"] != "single":
            continue
        value = off["value"]
        if isinstance(target, dict) and "address_prefix" in target:
            for k in ADDR_KEYS:
                _set(form, submission, fields, f"{target['address_prefix']}_{k}", (value or {}).get(k, ""))
        elif isinstance(target, dict) and "records" in target:
            recs = [_map_record(r, target.get("map")) for r in value if isinstance(r, dict)]
            _set(form, submission, fields, target["records"], [r for r in recs if r])
        else:
            _set(form, submission, fields, target, _as_text(value))
        done.append(fact_key)
    for name, (fact_key, const) in (block.get("also") or {}).items():
        if fact_key in done:  # e.g. a known A-Number answers "Do you have an A-Number?" with Yes
            _set(form, submission, fields, name, const)
    db.session.commit()
    return done, offers


def _answer_for(submission_values, target):
    """The application's current answer for one fact, in the fact's own representation."""
    if isinstance(target, dict) and "address_prefix" in target:
        rec = {k: (submission_values.get(f"{target['address_prefix']}_{k}") or "") for k in ADDR_KEYS}
        rec = {k: v for k, v in rec.items() if v}
        return rec or None
    if isinstance(target, dict) and "records" in target:
        raw = submission_values.get(target["records"])
        try:
            recs = json.loads(raw) if raw else []
        except ValueError:
            recs = []
        return [r for r in recs if isinstance(r, dict)] or None
    raw = submission_values.get(target)
    return (raw or "").strip() or None


def _fact_field_name(target):
    if isinstance(target, dict):
        return target.get("records") or target.get("address_prefix")
    return target


def after_save(form, submission, page):
    """Record confirmation / correction on the canonical facts for the block steps that were just saved, and freeze the block."""
    from app.intake_shared import _set

    blocks = blocks_for(form)
    if not blocks or submission.case_id is None:
        return
    prime_blocks(submission)
    names = {f.internal_name for f in page.fields}
    fields = _fields(form)
    stored = _stored(submission)
    for key, block in blocks.items():
        person = block_person(submission, block)
        if person is None:
            continue
        review_here = key in names
        edit_here = any(_fact_field_name(t) in names for t in block["fields"].values())
        if review_here and stored.get(key) == "correct":
            if pending_conflicts(submission, key):  # never confirm around an unresolved conflict
                for v in list(submission.values):
                    if v.field_internal_name == key:
                        db.session.delete(v)
                db.session.commit()
                stored = _stored(submission)
                continue
            done, offers = materialize(submission, key, block)
            for fact_key in done:
                pers.accept_offer(person, fact_key, offers[fact_key]["value"], submission, actor="customer")
            stored = _stored(submission)
        pf = block.get("prefill")
        if pf and edit_here:  # provenance: this application used the earlier application's document facts
            mapping = (pf["from"] or {}).get(stored.get(pf["choice_field"])) or {}
            for src_fact in dict.fromkeys(mapping.values()):
                fact = pers.get_fact(pers.owner_of(person), src_fact)
                if fact is not None:
                    pers.record_use(fact, submission, "prefill:" + key)
        if edit_here and stored.get(f"{key}_avail") in ("yes", "no"):
            if not answered(stored, key):
                _set(form, submission, fields, key, "edit")  # the customer supplied it themselves: the decision is now frozen
                db.session.commit()
            current = _stored(submission)
            for fact_key, target in block["fields"].items():
                cur = _answer_for(current, target)
                if cur in (None, "", [], {}):
                    continue
                fact = pers.get_fact(pers.owner_of(person), fact_key)
                if fact is None:
                    case_svc.record_fact(person, fact_key, cur, submission, _fact_field_name(target))
                elif case_svc._same(fact_key, case_svc.fact_value(fact), cur):
                    case_svc.confirm_facts(person, [fact_key], submission, actor="customer")
                else:
                    case_svc.update_fact(person, fact_key, cur, submission, actor="customer")
    db.session.commit()


# ------------------------------------------------------------------ prefill for the edit step
def prefill_values(submission, page):
    """{input_name: value} for the block fields of `page` that have no saved answer yet, from what can be offered (single offers only:
    a conflict is never pre-filled)."""
    form = submission.form
    blocks = blocks_for(form)
    if not blocks or submission.case_id is None:
        return {}
    stored = _stored(submission)
    out = {}
    fields = {f.internal_name: f for f in page.fields}
    for key, block in blocks.items():
        if not any(_fact_field_name(t) in fields for t in block["fields"].values()):
            continue
        person, offers = block_offers(submission, block)
        for fact_key, target in block["fields"].items():
            off = offers.get(fact_key)
            if off is None or off["status"] != "single":
                continue
            value = off["value"]
            if isinstance(target, dict) and "address_prefix" in target:
                for k in ADDR_KEYS:
                    f = fields.get(f"{target['address_prefix']}_{k}")
                    if f is not None and f.internal_name not in stored:
                        out[f.input_name()] = (value or {}).get(k, "")
            elif isinstance(target, dict) and "records" in target:
                f = fields.get(target["records"])
                if f is not None and f.internal_name not in stored:
                    out[f.input_name()] = json.dumps([_map_record(r, target.get("map")) for r in value if isinstance(r, dict)], ensure_ascii=False)
            else:
                f = fields.get(target)
                if f is not None and f.internal_name not in stored:
                    out[f.input_name()] = _as_text(value)
        for name, (fact_key, const) in (block.get("also") or {}).items():
            f = fields.get(name)
            if f is not None and fact_key in offers and offers[fact_key]["status"] == "single" and f.internal_name not in stored:
                out[f.input_name()] = const
        pf = block.get("prefill")
        if pf:  # details an earlier application stated under a DIFFERENT concept, reused only after the applicant said which one it is
            mapping = (pf["from"] or {}).get(stored.get(pf["choice_field"]))
            if mapping:
                _p, src = block_offers(submission, blocks[pf["source_block"]])
                for dst_fact, src_fact in mapping.items():
                    off = src.get(src_fact)
                    f = fields.get(block["fields"].get(dst_fact)) if isinstance(block["fields"].get(dst_fact), str) else None
                    if off is not None and off["status"] == "single" and f is not None and f.internal_name not in stored:
                        out[f.input_name()] = _as_text(off["value"])
    return out


# ------------------------------------------------------------------ after the customer answered: newer / different information
def changes_after_confirmation(submission, lang="en"):
    """[{block, message}] for blocks the customer already answered when the person's data now says something different (a conflict,
    a newer time-sensitive value, or a value that was not known then). The confirmed answer is never overwritten."""
    form = submission.form
    blocks = blocks_for(form)
    if not blocks or submission.case_id is None:
        return []
    stored = _stored(submission)
    en = lang != "es"
    out = []
    for key, block in blocks.items():
        if not answered(stored, key):
            continue
        person, offers = block_offers(submission, block)
        if person is None:
            continue
        for fact_key, target in block["fields"].items():
            off = offers.get(fact_key)
            if off is None:
                continue
            cur = _answer_for(stored, target)
            label = FACTS[fact_key]["en" if en else "es"]
            if off["status"] == "conflict":
                out.append({"block": key, "message": (f"Different information is now on file for “{label}”. OG should review it with you." if en
                                                       else f"Ahora hay información diferente registrada para “{label}”. OG debe revisarla contigo.")})
            elif cur is not None and not case_svc._same(fact_key, cur, off["value"]):
                out.append({"block": key, "message": (f"Newer or different information is available for “{label}”. Your confirmed answer was not changed; OG should review it." if en
                                                       else f"Hay información más reciente o diferente para “{label}”. Tu respuesta confirmada no se cambió; OG debe revisarla.")})
    return out


# ------------------------------------------------------------------ the review card
def _fmt_date(d, en):
    return d.strftime("%b %d, %Y") if en else d.strftime("%d/%m/%Y")


def _form_label(name, en):
    return (("Form " if en else "Formulario ") + name) if name else ("an application" if en else "una solicitud")


def _source_line(off, en):
    """Where the offered value came from and how strong it is."""
    src = off["options"][0]["sources"][0] if off["options"] and off["options"][0]["sources"] else None
    parts = []
    if off["confirmed"] and off["confirmed_at"]:
        parts.append((f"Confirmed {_fmt_date(off['confirmed_at'], en)}" if en else f"Confirmado {_fmt_date(off['confirmed_at'], en)}"))
        if src and src["form"]:
            parts.append(("from " if en else "de ") + _form_label(src["form"], en))
    elif src:
        what = ("Provided in " if en else "Indicado en ") + _form_label(src["form"], en)
        if src["state"] in ("draft", "reopened"):
            what += " (unfinished — please confirm)" if en else " (sin terminar — confírmalo)"
        if src["at"]:
            what += f" · {_fmt_date(src['at'], en)}"
        parts.append(what)
    if off["stale"]:
        parts.append("please check it is still current" if en else "verifica que siga vigente")
    return " · ".join(parts)


def summary_html(submission, key, lang="en"):
    from flask import url_for

    block = blocks_for(submission.form).get(key)
    if not block:
        return ""
    person, offers = block_offers(submission, block)
    if person is None or not offers:
        return ""
    en = lang == "en"
    rows, conflicts, missing = [], [], []
    for fact_key in block["fields"]:
        label = FACTS[fact_key]["en" if en else "es"]
        off = offers.get(fact_key)
        if off is None:
            missing.append(label)
            continue
        if off["status"] == "conflict":
            conflicts.append(label)
            opts = "".join(
                f'<li class="text-[13px] text-slate-700 break-words">{html.escape(case_svc.display_fact_value(fact_key, o["value"], lang, reveal=False))}'
                f' <span class="text-slate-400">— '
                + html.escape("; ".join(_form_label(s["form"], en) + (f" ({_fmt_date(s['at'], en)})" if s["at"] else "") for s in o["sources"][:2])) + "</span></li>"
                for o in off["options"])
            rows.append(
                '<div class="py-2.5 first:pt-0 last:pb-0">'
                f'<p class="text-xs font-semibold text-amber-800">{html.escape(label)}</p>'
                f'<p class="mt-0.5 text-[13px] font-semibold text-amber-800">{html.escape("We found different information" if en else "Encontramos información diferente")}</p>'
                f'<ul class="mt-1 space-y-0.5 list-disc pl-4">{opts}</ul></div>')
            continue
        value = case_svc.display_fact_value(fact_key, off["value"], lang, reveal=False)
        warn = off["stale"] or off["draft_only"]
        rows.append(
            '<div class="py-2.5 first:pt-0 last:pb-0">'
            f'<p class="text-xs font-semibold text-slate-500">{html.escape(label)}</p>'
            f'<p class="mt-0.5 text-[15px] font-semibold text-brand-800 whitespace-pre-line break-words">{html.escape(value)}</p>'
            f'<p class="mt-0.5 text-[11px] {"text-amber-700" if warn else "text-slate-400"}">{html.escape(_source_line(off, en))}</p></div>')
    if not rows:
        return ""
    situational = block_scope(block) == "situational"
    head = ("Is this still current?" if en else "¿Esto sigue vigente?") if situational else ("We already have this information" if en else "Ya tenemos esta información")
    extra = ""
    if conflicts:
        url = url_for("public.og_form_conflicts", lang=lang, slug=submission.form.slug, t=submission.resume_token, block=key)
        extra += ('<div class="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2.5">'
                  f'<p class="text-[13px] font-semibold text-amber-900">{html.escape("Please choose which information is correct first." if en else "Primero elige cuál información es la correcta.")}</p>'
                  f'<a href="{html.escape(url)}" class="mt-2 inline-flex items-center min-h-[44px] px-4 rounded-lg bg-accent-600 text-white text-sm font-semibold">'
                  f'{html.escape("Resolve" if en else "Resolver")} &rarr;</a></div>')
    if missing:
        extra += f'<p class="mt-3 text-[12px] text-slate-500">{html.escape("We still need: " if en else "Todavía necesitamos: ")}{html.escape(", ".join(missing))}.</p>'
    return (
        '<div class="rounded-xl border border-accent-200 bg-mist-50 px-4 py-3">'
        f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape(head)}</p>'
        f'<div class="mt-2 divide-y divide-mist-200">{"".join(rows)}</div>{extra}</div>'
    )
