"""Case document vault + document requirement engine.

Two different things, never merged:
  DocumentRequirement  what OG needs ("Maria's passport"), its status and who it is for.
  CaseDocument         the uploaded file, stored once in the case vault.
A document fills a requirement through a DocumentAttachment, so one file can satisfy several
requirements, and one requirement can serve several applications (RequirementApplication).
Replacements supersede, they never delete: the earlier file and its review history stay for Admin
while the currently valid version is obvious.

`ensure_requirement` / `sync_requirements` are the API future Smart Intakes call to add or withdraw
requirements from their answers (each rule owns a stable `rule_key`); nothing here knows about any
specific form or rule.
"""

import os
import re
from datetime import datetime

from app.cases import case_event
from app.extensions import db
from app.models import (
    CaseDocument,
    DocumentAttachment,
    DocumentRequirement,
    FormSubmission,
    RequirementApplication,
    SubmissionFile,
)
from app.uploads import course_media_full_path, delete_course_media, save_course_media

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp"}
MAX_UPLOAD_MB = 10
CUSTOMER_CAN_UPLOAD = ("needed", "requested", "uploaded", "needs_replacement")


def _notify(student, template_key, **kw):
    """Best-effort transactional email — never allowed to affect the document workflow itself."""
    if student is None:
        return
    try:
        from app.email_service import send_transactional_email

        send_transactional_email(student, template_key, student.preferred_language or "en", **kw)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("og_email").exception("[case_documents] transactional email %r failed to queue", template_key)
NAME_RE = re.compile(r"[\x00-\x1f\\/]+")

STATUS_ES = {
    "needed": "Necesario", "requested": "Solicitado", "uploaded": "Subido", "under_review": "En revisión",
    "accepted": "Aceptado", "needs_replacement": "Requiere reemplazo",
}
STATUS_TONE = {
    "needed": "bg-slate-100 text-slate-600", "requested": "bg-accent-50 text-accent-700", "uploaded": "bg-amber-50 text-amber-800",
    "under_review": "bg-amber-50 text-amber-800", "accepted": "bg-emerald-50 text-emerald-700", "needs_replacement": "bg-red-50 text-red-700",
}


def status_label(status, lang="en"):
    from app.models import REQUIREMENT_STATUS_LABELS

    return STATUS_ES.get(status, status) if lang == "es" else REQUIREMENT_STATUS_LABELS.get(status, status)


def _person_meta(req):
    return f" — {req.person.full_name}" if req.person else ""


def _event(req, event_type, actor, actor_id, extra=None, commit=False):
    case_event(req.case, event_type, actor=actor, actor_id=actor_id,
               meta=dict({"title": req.title, "for_person": _person_meta(req), "requirement": req.id}, **(extra or {})), commit=commit)


# ------------------------------------------------------------------ requirements
def _link_applications(req, applications):
    have = {l.submission_id for l in req.application_links}
    for sub in applications or []:
        if sub.case_id != req.case_id:
            raise ValueError("A requirement can only serve applications of its own case.")
        if sub.id not in have:
            db.session.add(RequirementApplication(requirement_id=req.id, submission_id=sub.id))
            have.add(sub.id)


BASIS_LABELS = {
    "source": ("Stated on the official form", "Indicado en el formulario oficial"),
    "workflow": ("OG workflow request", "Solicitud del proceso de OG"),
    "answer": ("Triggered by an answer", "Generado por una respuesta"),
    "admin": ("Requested by OG", "Solicitado por OG"),
    "dos_nvc": ("Department of State / NVC document list", "Lista de documentos del Departamento de Estado / NVC"),
    "customer": ("Added by you", "Agregado por ti"),
    "irs_w7": ("IRS Form W-7 instructions", "Instrucciones del Formulario W-7 del IRS"),
}


def find_reusable_document(case, person, category):
    """(document, already_accepted): a current vault document of this person/category that already sits in the case, so
    a new requirement for the same thing does not ask the customer to upload it again."""
    best, accepted_best = None, False
    for doc in case.documents:
        if doc.superseded_at is not None or doc.category != category or doc.category == "other":
            continue
        if person is not None and doc.person_id != person.id:
            continue
        if person is None and doc.person_id is not None:  # never hand one person's document to a requirement that belongs to nobody in particular
            continue
        accepted = any(a.superseded_at is None and a.requirement.status == "accepted" for a in doc.attachments)
        if best is None or (accepted and not accepted_best):
            best, accepted_best = doc, accepted
    return best, accepted_best


def create_requirement(case, title, *, category="other", person=None, applications=(), customer_message=None, internal_note=None,
                       source="admin", rule_key=None, source_key=None, status=None, actor="admin", actor_id=None, created_by=None, commit=True,
                       reuse=False, doc_basis=None):
    if person is not None and person.case_id != case.id:
        raise ValueError("That person is not part of this case.")
    req = DocumentRequirement(
        case_id=case.id, person_id=person.id if person else None, category=category or "other", title=(title or "Document").strip()[:200],
        customer_message=(customer_message or "").strip() or None, internal_note=(internal_note or "").strip() or None, source=source,
        rule_key=rule_key, source_key=source_key, status=status or ("requested" if source == "admin" else "needed"), created_by=created_by,
        doc_basis=doc_basis or ("admin" if source == "admin" else "workflow"),
    )
    db.session.add(req)
    db.session.flush()
    _link_applications(req, applications)
    reused = False
    if reuse:
        doc, was_accepted = find_reusable_document(case, person, req.category)
        if doc is not None:
            _attach(req, doc, reason_for_previous="replaced")
            req.reused_at = datetime.utcnow()
            if was_accepted:  # OG already accepted this very file for another application of the case
                req.status, req.accepted_at, req.reviewed_at, req.reviewed_by = "accepted", req.reused_at, req.reused_at, "OG (accepted earlier in this case)"
            _event(req, "case_document_reused", "system", None, {"filename": doc.original_filename})
            reused = True
    if req.status == "requested" and not reused:
        _event(req, "case_document_requested", actor, actor_id)
        _notify(case.customer, "document_needed", ref={"requirement_id": req.id}, related_type="requirement", related_id=req.id,
                dedupe_key=f"document_needed:{req.id}")
    if commit:
        db.session.commit()
    return req


def ensure_requirement(case, rule_key, title, *, person=None, source_key=None, **kw):
    """Idempotent: create the requirement for `rule_key` (per person) or return/reactivate the existing one."""
    existing = (DocumentRequirement.query.filter_by(case_id=case.id, rule_key=rule_key, person_id=person.id if person else None).first())
    if existing is None:
        return create_requirement(case, title, person=person, rule_key=rule_key, source_key=source_key, source="system", **kw)
    if existing.withdrawn_at is not None:
        existing.withdrawn_at = None
        if existing.current_document is None and existing.status in ("accepted", "uploaded", "under_review"):
            existing.status = "needed"
    _link_applications(existing, kw.get("applications"))
    db.session.commit()
    return existing


def withdraw_requirement(req, *, actor="system", actor_id=None, commit=True):
    if req.withdrawn_at is None:
        req.withdrawn_at = datetime.utcnow()
        _event(req, "case_document_withdrawn", actor, actor_id)
    if commit:
        db.session.commit()
    return req


def sync_requirements(case, source_key, desired):
    """Declarative API for a rule set / application: `desired` is a list of dicts
    {rule_key, title, person?, category?, applications?, customer_message?}. Missing requirements are created,
    withdrawn ones come back, and system requirements this source no longer wants are withdrawn (uploaded
    files are kept). Requirements an admin created by hand are never touched."""
    created = reactivated = withdrawn = 0
    wanted = set()
    for spec in desired:
        spec = dict(spec)
        key = spec.pop("rule_key")
        person = spec.pop("person", None)
        wanted.add((key, person.id if person else None))
        before = DocumentRequirement.query.filter_by(case_id=case.id, rule_key=key, person_id=person.id if person else None).first()
        was_withdrawn = before is not None and before.withdrawn_at is not None
        ensure_requirement(case, key, spec.pop("title"), person=person, source_key=source_key, **spec)
        created += before is None
        reactivated += was_withdrawn
    for req in DocumentRequirement.query.filter_by(case_id=case.id, source="system", source_key=source_key).all():
        if req.withdrawn_at is None and (req.rule_key, req.person_id) not in wanted:
            withdraw_requirement(req, commit=False)
            withdrawn += 1
    db.session.commit()
    return {"created": created, "reactivated": reactivated, "withdrawn": withdrawn}


def customer_text(req, lang="en"):
    """(title, message) a customer sees for a requirement. Requirements with localized wording (ITIN / W-7) answer in `lang`; every other requirement keeps its stored text."""
    if req.source_key == "w7":
        from app import w7_docs

        return w7_docs.req_text(req, lang)
    if req.source_key == "tax":
        from app.tax import docs as tax_docs

        return tax_docs.req_text(req, lang)
    if req.source_key == "nj_dl":
        from app.driver_license import docs as dl_docs

        return dl_docs.req_text(req, lang)
    return req.title, req.customer_message


def status_override(req, lang="en"):
    """(status_text, tone) a requirement's status should show as INSTEAD of the generic `status_label`/`STATUS_TONE`
    mapping, or None to use those as normal. Currently only the NJ Driver License "Alternative — not currently
    needed" documents (see `app.driver_license.rules.document_plan`): the generic Vault status vocabulary has no
    concept of "the customer has this but it isn't needed right now", and that must read the same everywhere the
    customer can see the requirement (the intake's own upload step AND the account case page), not just one."""
    if req.source_key == "nj_dl" and req.status == "needed":
        from app.driver_license import docs as dl_docs

        dl = req.case.dl_data
        if dl is not None and dl_docs.doc_role(req.rule_key, dl_docs._role_map(dl)) == "alternative":  # noqa: SLF001
            return dl_docs.ALT_LABEL[0 if lang != "es" else 1], "neutral"
    return None


# ------------------------------------------------------------------ uploads
def validate_upload(file_storage, lang="en"):
    """Error text, or None when the upload is acceptable (type, real content, size)."""
    from app.blueprints.public.routes import _matches_extension, _probe_upload

    name = (file_storage.filename or "").strip()
    if not name:
        return "Choose a file to upload." if lang == "en" else "Elige un archivo para subir."
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXTENSIONS:
        return f"Unsupported file type: .{ext}" if lang == "en" else f"Tipo de archivo no admitido: .{ext}"
    size, head = _probe_upload(file_storage)
    if size <= 0:
        return "The file is empty." if lang == "en" else "El archivo está vacío."
    if size > MAX_UPLOAD_MB * 1024 * 1024:
        return f"Each file must be {MAX_UPLOAD_MB} MB or smaller." if lang == "en" else f"Cada archivo debe pesar {MAX_UPLOAD_MB} MB o menos."
    if not _matches_extension(ext, head):
        return f"“{name}” doesn't look like a real .{ext} file." if lang == "en" else f"“{name}” no parece un archivo .{ext} válido."
    return None


def _store(case, file_storage, *, person, category, title, uploaded_by, uploaded_by_id):
    from app.blueprints.public.routes import _guess_mime, _probe_upload

    _size, head = _probe_upload(file_storage)
    stored = save_course_media(file_storage, "document")
    path = course_media_full_path(stored)
    safe_name = NAME_RE.sub("_", os.path.basename(file_storage.filename or "document"))[:200]
    doc = CaseDocument(case_id=case.id, person_id=person.id if person else None, category=category or "other", title=(title or "")[:200] or None,
                       original_filename=safe_name, stored_filename=stored, size_bytes=os.path.getsize(path) if os.path.isfile(path) else 0,
                       mime_type=_guess_mime(safe_name, head), uploaded_by=uploaded_by, uploaded_by_id=uploaded_by_id)
    db.session.add(doc)
    db.session.flush()
    return doc


def _attach(req, doc, *, reason_for_previous):
    now = datetime.utcnow()
    for att in req.attachments:
        if att.superseded_at is None:
            att.superseded_at, att.superseded_reason = now, reason_for_previous
    db.session.add(DocumentAttachment(requirement_id=req.id, document_id=doc.id))
    req.status, req.uploaded_at, req.updated_at = "uploaded", now, now
    req.review_message = None


def upload_for_requirement(req, file_storage, *, uploaded_by="customer", uploaded_by_id=None, actor=None):
    """Store a new file for a requirement. A later upload for the same requirement is a REPLACEMENT: the earlier
    document is kept (superseded) and the new one becomes the current version."""
    previous = req.current_document or next((a.document for a in reversed(req.attachments)), None)
    doc = _store(req.case, file_storage, person=req.person, category=req.category, title=req.title, uploaded_by=uploaded_by, uploaded_by_id=uploaded_by_id)
    if previous is not None and previous.superseded_at is None:
        previous.superseded_at = datetime.utcnow()
        doc.replaces_id = previous.id
    _attach(req, doc, reason_for_previous="replaced")
    _event(req, "case_document_uploaded", actor or uploaded_by, uploaded_by_id, {"filename": doc.original_filename})
    db.session.commit()
    return doc


def find_reusable_elsewhere(case, person, category):
    """(document, accepted) — a current, ACCEPTED vault document of the SAME real person and category in another case of the same customer."""
    if person is None or person.person_id is None or category in ("other", None):
        return None
    from app.models import Case, CasePerson

    rows = (CaseDocument.query.join(Case, Case.id == CaseDocument.case_id).join(CasePerson, CasePerson.id == CaseDocument.person_id)
            .filter(Case.customer_id == case.customer_id, CaseDocument.case_id != case.id, CaseDocument.category == category, CaseDocument.superseded_at.is_(None),
                    CasePerson.person_id == person.person_id).order_by(CaseDocument.id.desc()).all())
    for doc in rows:
        if any(a.superseded_at is None and a.requirement.status == "accepted" for a in doc.attachments):
            return doc
    return None


def reuse_across_cases(req, source, *, actor="system"):
    """Use an accepted document of ANOTHER case of the same customer for this requirement: a new vault row shares the stored file (never copied twice) and remembers where it came from."""
    if source.case.customer_id != req.case.customer_id:
        raise ValueError("That document belongs to a different customer.")
    doc = CaseDocument(case_id=req.case_id, person_id=req.person_id, category=source.category, title=source.title, original_filename=source.original_filename,
                       stored_filename=source.stored_filename, size_bytes=source.size_bytes, mime_type=source.mime_type, uploaded_by=source.uploaded_by,
                       uploaded_by_id=source.uploaded_by_id, reused_from_id=source.id)
    db.session.add(doc)
    db.session.flush()
    _attach(req, doc, reason_for_previous="replaced")
    now = datetime.utcnow()
    req.reused_at = now
    req.status, req.accepted_at, req.reviewed_at, req.reviewed_by = "accepted", now, now, "OG (accepted earlier in another case)"
    _event(req, "case_document_reused", actor, None, {"filename": doc.original_filename})
    return doc


def attach_existing_document(req, doc, *, actor="customer", actor_id=None):
    """Reuse a document already in the vault for another requirement (no second copy of the file)."""
    if doc.case_id != req.case_id:
        raise ValueError("That document belongs to a different case.")
    if req.person_id and doc.person_id and doc.person_id != req.person_id:
        raise ValueError("That document belongs to a different person.")
    _attach(req, doc, reason_for_previous="replaced")
    _event(req, "case_document_uploaded", actor, actor_id, {"filename": doc.original_filename})
    db.session.commit()
    return doc


# ------------------------------------------------------------------ review
def _review(req, status, actor_name, message=None):
    now = datetime.utcnow()
    req.status, req.reviewed_at, req.reviewed_by, req.updated_at = status, now, actor_name, now
    req.review_message = (message or "").strip() or None


def mark_under_review(req, actor_name, actor_id=None):
    if req.current_document is None:
        raise ValueError("There is no uploaded document to review.")
    _review(req, "under_review", actor_name)
    _event(req, "case_document_under_review", "admin", actor_id)
    db.session.commit()


def accept(req, actor_name, actor_id=None):
    if req.current_document is None:
        raise ValueError("There is no uploaded document to accept.")
    _review(req, "accepted", actor_name)
    req.accepted_at = req.reviewed_at
    _event(req, "case_document_accepted", "admin", actor_id)
    db.session.commit()


def request_replacement(req, message, actor_name, actor_id=None):
    """Needs Replacement + a customer-facing reason. The rejected file is kept in the history."""
    if not (message or "").strip():
        raise ValueError("Tell the customer what to fix.")
    if req.current_document is None:
        raise ValueError("There is no uploaded document to replace.")
    now = datetime.utcnow()
    for att in req.attachments:
        if att.superseded_at is None:
            att.superseded_at, att.superseded_reason = now, "needs_replacement"
    _review(req, "needs_replacement", actor_name, message)
    req.accepted_at = None
    _event(req, "case_document_replacement_requested", "admin", actor_id)
    db.session.commit()
    _notify(req.case.customer, "document_replacement", ref={"requirement_id": req.id}, related_type="requirement", related_id=req.id)


# ------------------------------------------------------------------ removal
def _delete_file_if_unused(doc):
    """Delete the stored file, unless another vault row (a document brought over from another case) still points at it."""
    if CaseDocument.query.filter(CaseDocument.stored_filename == doc.stored_filename, CaseDocument.id != doc.id).count() == 0:
        delete_course_media(doc.stored_filename)


def remove_document(doc, *, actor="admin", actor_id=None):
    """Delete a vault document (file and rows). Requirements that were using it go back to Requested."""
    case = doc.case
    for att in list(doc.attachments):
        req = att.requirement
        was_current = att.superseded_at is None
        doc.attachments.remove(att)  # delete-orphan removes the row; the document delete below cascades the rest
        if was_current:
            req.status, req.uploaded_at, req.accepted_at, req.reviewed_at = "requested", None, None, None
    for other in CaseDocument.query.filter_by(replaces_id=doc.id).all():
        other.replaces_id = None
    name = doc.original_filename
    _delete_file_if_unused(doc)
    db.session.delete(doc)
    case_event(case, "case_document_removed", actor=actor, actor_id=actor_id, meta={"filename": name}, commit=False)
    db.session.commit()


def customer_can_remove(req, doc):
    """A customer may take back their OWN upload only before OG has started reviewing it."""
    return doc is not None and doc.uploaded_by == "customer" and req.status == "uploaded" and len(doc.attachments) == 1


# ------------------------------------------------------------------ queries
def visible_requirements(case):
    return [r for r in case.requirements if r.withdrawn_at is None]


def requirement_counts(case):
    counts = {}
    for r in visible_requirements(case):
        counts[r.status] = counts.get(r.status, 0) + 1
    return counts


def open_customer_actions(case):
    """Requirements waiting on the customer."""
    return [r for r in visible_requirements(case) if r.status in ("needed", "requested", "needs_replacement")]


def requirement_groups(case):
    """Requirements grouped by person (None = relationship/case-level), customer first."""
    groups, order = {}, []
    for r in visible_requirements(case):
        key = r.person_id
        if key not in groups:
            groups[key] = {"person": r.person, "requirements": []}
            order.append(key)
        groups[key]["requirements"].append(r)
    order.sort(key=lambda k: (k is None, 0 if (groups[k]["person"] and groups[k]["person"].is_customer) else 1, k or 0))
    return [groups[k] for k in order]


def vault_documents(case):
    """Current documents by person; superseded ones stay available as history."""
    return [d for d in case.documents if d.superseded_at is None]


def application_files(case):
    """Files uploaded INSIDE the case's applications (unchanged, still served by the existing secure routes)."""
    ids = [s.id for s in case.applications]
    if not ids:
        return []
    rows = SubmissionFile.query.filter(SubmissionFile.submission_id.in_(ids)).order_by(SubmissionFile.uploaded_at.desc()).all()
    return [f for f in rows if f.original_filename != "signature.png"]


def owned_document(student, case_id, document_id):
    """A vault document only if its case belongs to this customer AND the document belongs to that case."""
    from app.cases import owned_case

    case = owned_case(student, case_id)
    if case is None:
        return None, None
    doc = CaseDocument.query.filter_by(id=document_id, case_id=case.id).first()
    return case, doc


def owned_requirement(student, case_id, requirement_id):
    from app.cases import owned_case

    case = owned_case(student, case_id)
    if case is None:
        return None, None
    req = DocumentRequirement.query.filter_by(id=requirement_id, case_id=case.id).first()
    if req is not None and req.withdrawn_at is not None:
        req = None
    return case, req
