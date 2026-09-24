"""Reusable helpers for intakes where several official forms share ONE customer-facing intake
(for example Form I-130 with its Form I-130A supplement for a spouse beneficiary).

  * name tokens      "{ben}" in a step's text becomes the person's first name ("Maria"), so
                     the supplement can ask "Where has Maria lived?" instead of "the beneficiary".
  * canonical sync   a fact that lives in two places (the beneficiary's current address is both
                     an I-130 answer and the first entry of an address history) is kept in ONE
                     value: editing either side updates the other, so the two can never disagree.
  * dynamic blocks   a paragraph that shows something found in earlier answers ("We found this
                     address in Maria's history") so the customer confirms instead of re-typing.
  * supplements      which pages/sections belong to a supplemental official form, and whether a
                     submission still needs it (used by review, completeness and Admin).

Configuration lives in `Form.features` (`name_tokens`, `sync`, `supplements`); nothing here is
specific to one form.
"""

import html
import json

from flask import g, has_request_context

from app.extensions import db

_DEFAULT_FALLBACK = {"en": "your family member", "es": "tu familiar"}


# ------------------------------------------------------------------ name tokens
def name_tokens(form, submission):
    cfg = (form.features or {}).get("name_tokens") or {}
    if not cfg:
        return {}
    named = {}
    if submission is not None:
        from app.intake_completeness import named_answers

        named = named_answers(form, submission)
    out = {}
    for key, spec in cfg.items():
        if spec.get("role"):  # the person playing a role in this application (the case's canonical person)
            from app.cases import role_person

            person = role_person(submission, spec["role"]) if submission is not None else None
            name = (person.given_name or "").strip() if person is not None else ""
        else:
            name = str(named.get(spec["field"]) or "").strip()
        out[key] = {"name": name, "fallback": spec.get("fallback") or _DEFAULT_FALLBACK}
    return out


def set_name_tokens(form, submission):
    """Make `{token}` replacement available for the rest of this request."""
    if has_request_context():
        g.name_tokens = name_tokens(form, submission)


def apply_tokens(text, lang, escape=False):
    if not text or "{" not in text:
        return text
    tokens = g.get("name_tokens") if has_request_context() else None
    for key in dict.fromkeys(["ben", "app", *((tokens or {}).keys())]):
        token = "{" + key + "}"
        if token not in text:
            continue
        spec = (tokens or {}).get(key)
        if spec and spec["name"]:
            value = spec["name"]
        else:
            value = ((spec or {}).get("fallback") or _DEFAULT_FALLBACK)[lang if lang in ("en", "es") else "en"]
        text = text.replace(token, html.escape(value) if escape else value)
    return text


def first_name(form, submission, key="ben"):
    tokens = name_tokens(form, submission).get(key)
    return tokens["name"] if tokens else ""


# ------------------------------------------------------------------ helpers over saved values
def _values(submission):
    return {v.field_internal_name: v.value_text for v in submission.values}


def _set(form, submission, fields, name, value):
    """Write one answer by internal name (upsert)."""
    from app.models import SubmissionValue

    field = fields.get(name)
    if field is None:
        return
    row = next((v for v in submission.values if v.field_id == field.id), None)
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if row:
        row.value_text = text
    else:
        db.session.add(SubmissionValue(
            submission_id=submission.id, field_id=field.id, field_label_snapshot=field.label("en") or name,
            field_internal_name=name, field_type_snapshot=field.field_type, value_text=text,
        ))


def _delete(submission, name):
    for v in list(submission.values):
        if v.field_internal_name == name:
            db.session.delete(v)


_ADDR_KEYS = ("street", "unit_type", "unit_number", "city", "state", "zip", "province", "postal_code", "country")


def _active(rule, vals):
    when = rule.get("when")
    return not when or vals.get(when["field"]) == when["equals"]


def _sync_current_address(form, submission, fields, rule, page_names, vals):
    """The person's current address is one fact: the `present` entry of the history and the
    plain address answers (`prefix_*`) are kept identical, whichever side was just edited."""
    from app.intake_records import parse_records

    rec_name, prefix = rule["record_field"], rule["prefix"]
    start_field = rule.get("start_field")  # optional: the "started living here" answer, kept equal to the present entry's `from`
    records = parse_records(vals.get(rec_name))
    present = next((i for i, r in enumerate(records) if r.get("present")), None)
    if rec_name in page_names:
        if present is None:
            return
        cur = records[present]
        new = {"is_us": cur.get("is_us") or "yes", **{k: cur.get(k, "") for k in _ADDR_KEYS}}
        for key, value in new.items():
            if (vals.get(f"{prefix}_{key}") or "") != value:
                _set(form, submission, fields, f"{prefix}_{key}", value)
        if start_field and cur.get("from") and vals.get(start_field) != cur.get("from"):
            _set(form, submission, fields, start_field, cur["from"])
    elif rule.get("create_present") and present is None and any(n.startswith(prefix + "_") for n in page_names) and vals.get(f"{prefix}_street") and vals.get(f"{prefix}_city"):
        # first time the present address is known: start the history with it (the customer adds the earlier ones)
        rec = {"is_us": vals.get(f"{prefix}_is_us") or "yes", **{k: vals.get(f"{prefix}_{k}") or "" for k in _ADDR_KEYS}, "present": True}
        if start_field and vals.get(start_field):
            rec["from"] = vals[start_field]
        records.append({k: v for k, v in rec.items() if v not in ("", None)})
        _set(form, submission, fields, rec_name, records)
    elif any(n.startswith(prefix + "_") for n in page_names) and present is not None:
        cur = dict(records[present])
        new = {"is_us": vals.get(f"{prefix}_is_us") or "yes", **{k: vals.get(f"{prefix}_{k}") or "" for k in _ADDR_KEYS}}
        if any(cur.get(k, "") != v for k, v in new.items() if k != "is_us") or cur.get("is_us") != new["is_us"]:
            cur.update(new)
            if start_field and vals.get(start_field) and cur.get("from") != vals.get(start_field):
                cur["from"] = vals[start_field]
            records[present] = {k: v for k, v in cur.items() if v not in ("", None)}
            _set(form, submission, fields, rec_name, records)
        elif start_field and vals.get(start_field) and records[present].get("from") != vals.get(start_field):
            records[present] = dict(records[present], **{"from": vals[start_field]})
            _set(form, submission, fields, rec_name, records)


def _sync_current_employment(form, submission, fields, rule, page_names, vals):
    """Current job: the `present` employed entry of the employment history and the
    I-130 "current employer" answers describe the same job."""
    from app.intake_records import _default_employment, is_us_country, parse_records

    rec_name, prefix = rule["record_field"], rule["prefix"]
    flag, name_f, start_f = rule["employed"], rule["name"], rule["start"]
    records = parse_records(vals.get(rec_name))
    present = next((i for i, r in enumerate(records) if r.get("present")), None)
    if rec_name in page_names:
        if present is None:
            return
        cur = records[present]
        if cur.get("type") == "unemployed":
            _set(form, submission, fields, flag, "no")
        elif cur.get("type") == "employed":
            _set(form, submission, fields, flag, "yes")
            _set(form, submission, fields, name_f, cur.get("name", ""))
            _set(form, submission, fields, start_f, cur.get("from", ""))
            us = "yes" if is_us_country(cur.get("country")) or not cur.get("country") else "no"
            _set(form, submission, fields, f"{prefix}_is_us", us)
            _set(form, submission, fields, f"{prefix}_street", cur.get("street", ""))
            _set(form, submission, fields, f"{prefix}_unit_number", cur.get("unit_number", ""))
            _set(form, submission, fields, f"{prefix}_city", cur.get("city", ""))
            if us == "yes":
                state = cur.get("state", "")
                _set(form, submission, fields, f"{prefix}_state", state if len(state) == 2 else "")
                _set(form, submission, fields, f"{prefix}_zip", cur.get("zip", ""))
            else:
                _set(form, submission, fields, f"{prefix}_province", cur.get("state", ""))
                _set(form, submission, fields, f"{prefix}_postal_code", cur.get("zip", ""))
                _set(form, submission, fields, f"{prefix}_country", cur.get("country", ""))
    elif page_names & {flag, name_f, start_f} or any(n.startswith(prefix + "_") for n in page_names):
        if present is None or records[present].get("type") != "employed" or vals.get(flag) != "yes":
            return
        starting = _default_employment({"employed": flag, "name": name_f, "prefix": prefix, "start": start_f}, vals)
        if starting:
            cur = dict(records[present])
            cur.update({k: v for k, v in starting[0].items() if v})
            records[present] = cur
            _set(form, submission, fields, rec_name, records)


def _drop_stale_candidate(form, submission, fields, rule, page_names, vals):
    """Customer said the reused address is NOT the right one: drop the untouched copy so the
    builder opens empty instead of showing the address they just rejected."""
    from app.intake_records import CANDIDATES, parse_records

    if rule["status_field"] not in page_names or vals.get(rule["status_field"]) != rule["status_value"]:
        return
    saved = parse_records(vals.get(rule["record_field"]))
    found = CANDIDATES[rule["candidate"]](parse_records(vals.get(rule["source"])))
    if saved and found and all((saved[0].get(k) or "") == (found.get(k) or "") for k in ("street", "city", "country", "from", "to")):
        _delete(submission, rule["record_field"])


def _completed_event(form, submission, fields, rule, page_names, vals):
    from app.activity import log_event
    from app.models import ActivityEvent

    if rule["field"] not in page_names or not _active(rule, vals):
        return
    exists = ActivityEvent.query.filter_by(customer_id=submission.student_id, event_type=rule["event"], entity_id=submission.id).first()
    if not exists and submission.student_id:
        title = submission.service.title_en if submission.service else form.name_admin
        log_event(submission.student_id, rule["event"], entity=("submission", submission.id), meta={"service": title}, commit=False)


def _underlying_link(form, submission, fields, rule, page_names, vals):
    """Part 2 of an I-485: link (or unlink) the case's petition the applicant says this application is based on."""
    from app import cases as case_svc
    from app.i485_docs import underlying_candidates

    if rule["field"] not in page_names:
        return
    if vals.get(rule["field"]) == "yes":
        cands = underlying_candidates(submission)
        if cands and submission.case is not None:
            case_svc.link_applications(submission.case, submission, cands[0], "underlying_petition")
    else:
        case_svc.unlink_applications(submission, "underlying_petition")


def _requirements(form, submission, fields, rule, page_names, vals):
    from app.i485_docs import sync as sync_docs

    if submission.case_id:
        sync_docs(submission)


def _i864_calc(form, submission, fields, rule, page_names, vals):
    """Write the Part 5 / Part 6 / Part 7 arithmetic back as calculated answers (so Review, Admin and the snapshot show them)."""
    from app import i864_calc, i864_views

    for name, value in i864_calc.calculated(i864_views.answers(submission)).items():
        _set(form, submission, fields, name, value)


def _person_records(form, submission, fields, rule, page_names, vals):
    from app import i864_views

    i864_views.normalize_records(form, submission, tuple(rule.get("fields") or i864_views.PERSON_RECORD_FIELDS))


def _requirements_i864(form, submission, fields, rule, page_names, vals):
    from app.i864_docs import sync as sync_docs

    if submission.case_id:
        sync_docs(submission)


def _i765_calc(form, submission, fields, rule, page_names, vals):
    """Category branch / ABC relevance / Part 6 entries / preparer statement, written back as calculated answers (never a category decision)."""
    from app import cases as case_svc
    from app import i765_calc

    for name, value in i765_calc.calculated(case_svc.answers_by_name(submission)).items():
        _set(form, submission, fields, name, value)


def _requirements_i765(form, submission, fields, rule, page_names, vals):
    from app.i765_docs import sync as sync_docs

    if submission.case_id:
        sync_docs(submission)


def _i751_calc(form, submission, fields, rule, page_names, vals):
    """Filing-basis flags, residence-history window, Part 8 applicability, Part 11 entries and preparer statement, written back as calculated answers."""
    from app import cases as case_svc
    from app import i751_calc

    for name, value in i751_calc.calculated(case_svc.answers_by_name(submission), submission).items():
        _set(form, submission, fields, name, value)


def _requirements_i751(form, submission, fields, rule, page_names, vals):
    from app.i751_docs import sync as sync_docs

    if submission.case_id:
        sync_docs(submission)


def _ds260_calc(form, submission, fields, rule, page_names, vals):
    """Age, address-history start, 2019-sample visibility hints, Security & Background review counts and preparer defaults, written back as calculated answers."""
    from app import cases as case_svc
    from app import ds260_calc

    for name, value in ds260_calc.calculated(case_svc.answers_by_name(submission), submission).items():
        _set(form, submission, fields, name, value)


def _requirements_ds260(form, submission, fields, rule, page_names, vals):
    from app.ds260_docs import sync as sync_docs

    if submission.case_id:
        sync_docs(submission)


def _w7_calc(form, submission, fields, rule, page_names, vals):
    """Age band, passport flags, candidate W-7 reason and OG-review flags, written back as calculated answers; case-level tax info follows the primary taxpayer."""
    from app import w7_calc

    w7_calc.write(form, submission, fields)


def _requirements_w7(form, submission, fields, rule, page_names, vals):
    from app.w7_docs import sync as sync_docs

    if submission.case_id:
        sync_docs(submission)


_RULES = {
    "w7_calc": _w7_calc,
    "requirements_w7": _requirements_w7,
    "ds260_calc": _ds260_calc,
    "requirements_ds260": _requirements_ds260,
    "i751_calc": _i751_calc,
    "requirements_i751": _requirements_i751,
    "i765_calc": _i765_calc,
    "requirements_i765": _requirements_i765,
    "i864_calc": _i864_calc,
    "person_records": _person_records,
    "requirements_i864": _requirements_i864,
    "underlying_link": _underlying_link,
    "requirements": _requirements,
    "current_address": _sync_current_address,
    "current_employment": _sync_current_employment,
    "drop_stale_candidate": _drop_stale_candidate,
    "completed_event": _completed_event,
}


def sync_after_save(form, submission, page):
    """Run after a step is saved (never on autosave): keep shared facts identical."""
    if submission is not None:
        from app.shared_blocks import after_save

        after_save(form, submission, page)  # shared-data blocks: confirm / update the canonical facts (only when the form has blocks)
    rules = (form.features or {}).get("sync") or []
    if not rules or submission is None:
        return
    fields = {f.internal_name: f for f in form.all_fields}
    page_names = {f.internal_name for f in page.fields}
    for rule in rules:
        vals = _values(submission)
        if not _active(rule, vals):
            continue
        _RULES[rule["kind"]](form, submission, fields, rule, page_names, vals)
        db.session.flush()
    db.session.commit()


def documents_block_html(form, submission, lang):
    """The customer's document requirements for an application, as the same card list the Documents step shows (used by Review for DS-260)."""
    if form.source_form_name == "DS-260":
        from app.ds260_docs import documents_html
    elif form.source_form_name == "W-7":
        from app.w7_views import review_summary_html as documents_html
    else:
        return ""
    return documents_html(submission, lang) if submission is not None else ""


# ------------------------------------------------------------------ dynamic blocks
def dynamic_blocks(form, page, submission, lang):
    """{field_id: html} for paragraph fields whose text depends on earlier answers."""
    from app.intake_completeness import named_answers
    from app.intake_records import CANDIDATES, card_for, field_config, parse_records

    out = {}
    named = None
    for field in page.fields:
        if field.field_type != "paragraph" or not field.config_json or "dynamic" not in field.config_json:
            continue
        cfg = json.loads(field.config_json)
        dyn = cfg["dynamic"]
        if "shared_block" in dyn:
            from app.shared_blocks import summary_html

            out[field.id] = summary_html(submission, dyn["shared_block"], lang) if submission is not None else ""
            continue
        if dyn.get("kind") == "documents":
            if form.source_form_name == "I-864":
                from app.i864_docs import documents_html
            elif form.source_form_name == "I-765":
                from app.i765_docs import documents_html
            elif form.source_form_name == "I-751":
                from app.i751_docs import documents_html
            elif form.source_form_name == "DS-260":
                from app.ds260_docs import documents_html
            elif form.source_form_name == "W-7":
                from app.w7_docs import documents_html
            else:
                from app.i485_docs import documents_html

            out[field.id] = documents_html(submission, lang) if submission is not None else ""
            continue
        if str(dyn.get("kind", "")).startswith("w7_"):
            from app import w7_views

            out[field.id] = getattr(w7_views, dyn["kind"][3:] + "_html")(submission, lang) if submission is not None else ""
            continue
        if str(dyn.get("kind", "")).startswith("ds_"):
            from app import ds260_views

            out[field.id] = getattr(ds260_views, dyn["kind"][3:] + "_html")(submission, lang) if submission is not None else ""
            continue
        if str(dyn.get("kind", "")).startswith("i751_"):
            from app import i751_views

            out[field.id] = getattr(i751_views, dyn["kind"][5:] + "_html")(submission, lang) if submission is not None else ""
            continue
        if str(dyn.get("kind", "")).startswith("i765_"):
            from app import i765_views

            out[field.id] = getattr(i765_views, dyn["kind"][5:] + "_html")(submission, lang) if submission is not None else ""
            continue
        if str(dyn.get("kind", "")).startswith("i864_"):
            from app import i864_views

            out[field.id] = getattr(i864_views, dyn["kind"][5:] + "_html")(submission, lang) if submission is not None else ""
            continue
        if dyn.get("kind") == "context":
            from app.i485_docs import context_html

            out[field.id] = context_html(submission, lang) if submission is not None else ""
            continue
        if dyn.get("kind") == "underlying":
            from app.i485_docs import underlying_html

            out[field.id] = underlying_html(submission, lang) if submission is not None else ""
            continue
        named = named if named is not None else (named_answers(form, submission) if submission is not None else {})
        who_key = dyn.get("who", "ben")
        who = first_name(form, submission, who_key) or ((form.features.get("name_tokens") or {}).get(who_key, {}).get("fallback") or _DEFAULT_FALLBACK)[lang]
        records = parse_records(named.get(dyn["source"]))
        found = CANDIDATES[dyn["candidate"]](records)
        en = lang == "en"
        if found:
            title, sub = card_for(dyn["record"], found, lang)
            head = (f"We found this in {who}'s history" if en else f"Encontramos esto en el historial de {who}")
            out[field.id] = (
                '<div class="rounded-xl border border-accent-200 bg-mist-50 px-4 py-3">'
                f'<p class="text-xs font-bold uppercase tracking-wider text-accent-700">{html.escape(head)}</p>'
                f'<p class="mt-1 text-[15px] font-semibold text-brand-800 break-words">{html.escape(title)}</p>'
                f'<p class="text-[13px] text-slate-600 break-words">{html.escape(sub)}</p></div>'
            )
        else:
            none = (dyn["none"]["en"] if en else dyn["none"]["es"]).replace("{ben}", html.escape(who)).replace("{app}", html.escape(who))
            out[field.id] = f'<p class="text-[13px] text-slate-500">{none}</p>'
    return out


# ------------------------------------------------------------------ supplements
def supplement_map(form, lang):
    """{group_key: {"key", "title", "form", "edition"}} for the pages that belong to a
    supplemental official form (e.g. I-130A)."""
    out = {}
    for key, sup in ((form.features or {}).get("supplements") or {}).items():
        for group in sup["groups"]:
            out[group] = {"key": key, "title": sup["customer_title"][lang], "official": sup["title"][lang],
                          "form": sup["form"], "edition": sup["edition"]}
    return out


def supplement_status(form, submission):
    """For a submission of a form with a supplement: None (not applicable), "in_progress"
    (a draft), "needed" (submitted/reopened but the supplement's answers are missing) or "complete"."""
    for key, sup in ((form.features or {}).get("supplements") or {}).items():
        vals = _values(submission)
        when = sup["when"]
        if vals.get(when["field"]) != when["equals"]:
            continue
        has = vals.get(sup["required_field"]) not in (None, "", "[]")
        if has:
            return {"key": key, "form": sup["form"], "edition": sup["edition"], "state": "complete"}
        if submission.is_complete or submission.status == "reopened":
            return {"key": key, "form": sup["form"], "edition": sup["edition"], "state": "needed"}
        return {"key": key, "form": sup["form"], "edition": sup["edition"], "state": "in_progress"}
    return None
