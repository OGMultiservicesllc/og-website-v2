"""DS-260 source snapshots.

The DS-260 is an ONLINE Department of State form in the Consular Electronic Application Center (CEAC). It has no USCIS-style edition number, and no
edition is invented here. What OG keeps instead is a SOURCE SNAPSHOT: which official material the question schema was built from, when it was last
verified, and a hash of the question registry. Every DS-260 application records the snapshot it was created under (`Ds260Application.source_id`);
introducing a newer snapshot never rewrites an existing application, and the frozen registries of two snapshots can be diffed.

A snapshot row stores: agency, system, official name, source label, official references (one per line), sample date, verification date, schema hash,
the frozen registry {canonical question id: {section, label, type}} and honest notes about what could not be verified.
"""

import hashlib
import json
from datetime import date, datetime

from app.extensions import db
from app.models import Ds260Source

CURRENT_CODE = "ds260-og-2026-09-19"

SOURCE_LABEL = ("Department of State DS-260 IV Application SAMPLE, Bureau of Consular Affairs, Consular Systems and Technology, October 2019 (111 pp.), reconciled with "
                "Federal Register 30-day notice 2025-20231 (OMB 1405-0185)")
REFERENCES = "\n".join([
    "Supplied file: DS-260-Exemplar.pdf (Consular Systems and Technology, October 2019), read page by page",
    "Federal Register, 2025-11-19, 30-Day Notice of Proposed Information Collection: Immigrant Visa Application (DS-260), OMB 1405-0185, document 2025-20231",
    "reginfo.gov OMB 1405-0185: ICR 202605-1405-003 (approved with change 2026-05-19), ICR 202606-1405-004 (approved without change 2026-09-10)",
    "DOS/NVC public guidance mirrored on adoptions.state.gov (answers in English; CEAC session time-out; who may reopen a submitted DS-260; NVC civil-documents page)",
])
NOTES = "\n".join([
    "NOT verified: the June 2023 official DS-260 sample and the live CEAC screens (travel.state.gov blocks automated access from this environment). CEAC-facing wording is the 2019 sample's unless a newer official source says otherwise.",
    "Delta applied from the FR 2025 notice: travel question now covers the last fifteen years (2019 sample: five); family questions say applying for a U.S. immigrant visa instead of immigrating; frivolous-asylum question refers to an immigration judge or the Board of Immigration Appeals; new Medical Examination Disclosure and Consent (CEAC-only).",
    "Social-media rules (five years, provider list plus identifier, ‘other’ list, no passwords, private messaging excluded) come only from the 2019 sample; the provider list itself was not visible in the sample and is not reproduced.",
    "Which sections CEAC shows to which applicant (age, sex, nationality, occupation, visa class rules in the 2019 sample) is recorded as UNVERIFIED for the current system: OG asks the questions of everyone and flags the 2019 rule as a hint only.",
    "Sign and Submit / E-Signature / FGM/C certification / Selective Service notice / CEAC confirmation page are CEAC-only and are never collected or simulated.",
])


def hash_registry(registry):
    return hashlib.sha256(json.dumps(registry, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def registry_from_form(form):
    """{canonical question id: {sec, label, type}} for every customer-facing DS-260 question (from the form's own CEAC map)."""
    ceac = (form.features or {}).get("ceac") or {}
    fields = {f.internal_name: f for f in form.all_fields}
    out = {}
    for name, meta in ceac.items():
        f = fields.get(name)
        out[name] = {"sec": meta.get("sec"), "label": meta.get("label") or (f.label_en if f else ""), "type": f.field_type if f else "?"}
    return out


def ensure_snapshot(code, registry, *, label=SOURCE_LABEL, references=REFERENCES, notes=NOTES, sample_date="2019-10", make_current=True):
    """Create the snapshot `code` (idempotent). An existing snapshot is never modified (it is history); the registry hash is recorded."""
    row = Ds260Source.query.filter_by(code=code).first()
    if row is not None:
        return row
    if make_current:
        Ds260Source.query.filter(Ds260Source.is_current.is_(True)).update({"is_current": False})
    row = Ds260Source(code=code, source_label=label, reference=references, notes=notes, sample_date=sample_date, verified_at=date.today(),
                      schema_hash=hash_registry(registry), registry_json=json.dumps(registry, sort_keys=True, ensure_ascii=False), is_current=make_current,
                      created_at=datetime.utcnow())
    db.session.add(row)
    db.session.commit()
    return row


def current_source():
    row = Ds260Source.query.filter_by(is_current=True).order_by(Ds260Source.id.desc()).first()
    if row is None:  # a fresh database before the DS-260 form was seeded: register a placeholder from whatever form exists
        from app.models import Form

        form = Form.query.filter_by(slug="ds-260-client-intake").first()
        row = ensure_snapshot(CURRENT_CODE, registry_from_form(form) if form is not None else {})
    return row


def registry(source):
    try:
        return json.loads(source.registry_json or "{}")
    except ValueError:
        return {}


def diff(a, b):
    """What changed from snapshot `a` to snapshot `b`: {added, removed, changed} of canonical question ids (registries are frozen history)."""
    ra, rb = registry(a), registry(b)
    added = sorted(set(rb) - set(ra))
    removed = sorted(set(ra) - set(rb))
    changed = sorted(k for k in set(ra) & set(rb) if ra[k] != rb[k])
    return {"added": added, "removed": removed, "changed": changed, "same_hash": a.schema_hash == b.schema_hash}


def introduce_snapshot(code, registry_data, **kw):
    """A newer official source: record a NEW snapshot and make it current for NEW applications. Existing applications keep their own snapshot."""
    return ensure_snapshot(code, registry_data, make_current=True, **kw)
