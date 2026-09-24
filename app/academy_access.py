"""Admin Grant Course Access (Wix migration support). Reuses the existing `Enrollment`/`Course`/progress/
certificate architecture unchanged — this module only decides WHEN/HOW an `Enrollment` row is created,
renewed, extended, revoked or restored, and logs it through the existing activity log (`app/activity.py`).

The `Enrollment` unique constraint on (student_id, course_id) already guarantees at most one row per
student+course, so "duplicate prevention" (item B5) falls out of the schema: granting access when a row
already exists always UPDATES that same row, never inserts a second one. Revoking (item B9) never deletes
the row either — `revoked_at` is set instead — so progress/quiz/certificate history (all keyed by
student_id+course_id, not by enrollment id) is never at risk of being orphaned."""

from datetime import datetime, timedelta

from app.activity import log_event
from app.extensions import db
from app.models import Enrollment, access_source_label

DURATION_PRESETS = [30, 60, 90]


def _notify_access(enrollment):
    try:
        from app.email_service import send_transactional_email

        student = enrollment.student
        send_transactional_email(
            student, "course_access", student.preferred_language or "en",
            ref={"enrollment_id": enrollment.id}, related_type="enrollment", related_id=enrollment.id,
        )
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("og_email").exception("[academy_access] course_access email failed to queue")


def _entity(enrollment):
    return ("enrollment", enrollment.id)


def existing_enrollment(student, course):
    return Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first()


def _resolve_expiry(course, *, duration_days=None, expires_at=None, no_expiration=False):
    if no_expiration:
        return None
    if expires_at is not None:
        return expires_at
    days = duration_days if duration_days is not None else course.access_duration_days
    return datetime.utcnow() + timedelta(days=days) if days else None


def grant_access(student, course, *, access_source, admin_id, actor="admin", duration_days=None, expires_at=None,
                  no_expiration=False, migration_reference=None, internal_note=None):
    """Returns (enrollment, status): status is "created" | "renewed_expired" | "restored_revoked" |
    "already_active" (item B5 — the caller shows the customer's current dates/progress and offers
    Extend / Change Expiration instead of silently doing nothing or creating a duplicate).

    `actor`/`admin_id`: "admin" (staff grant, `admin_id` set) or "system" (an OG Payments Square/manual
    payment activated this automatically — `admin_id` stays None; see app/payments.py `_fulfill_charge_context`,
    which passes `access_source="paid_new_site"`, never a fake $0 admin grant)."""
    existing = existing_enrollment(student, course)
    new_expires = _resolve_expiry(course, duration_days=duration_days, expires_at=expires_at, no_expiration=no_expiration)
    if existing is None:
        e = Enrollment(student_id=student.id, course_id=course.id, expires_at=new_expires, access_source=access_source,
                       granted_by_admin_id=admin_id, granted_at=datetime.utcnow(), migration_reference=(migration_reference or "").strip() or None,
                       internal_note=(internal_note or "").strip() or None)
        db.session.add(e)
        db.session.commit()
        log_event(student.id, "course_access_granted", actor=actor, actor_id=admin_id, entity=_entity(e),
                  meta={"course": course.title_en, "access_source": access_source_label(access_source, "en"), "expires": new_expires.isoformat() if new_expires else None})
        _notify_access(e)
        return e, "created"
    if existing.is_active:
        return existing, "already_active"
    status = "restored_revoked" if existing.is_revoked else "renewed_expired"
    existing.enrolled_at = datetime.utcnow()
    existing.expires_at = new_expires
    existing.access_source = access_source
    existing.granted_by_admin_id = admin_id
    existing.granted_at = datetime.utcnow()
    existing.migration_reference = (migration_reference or "").strip() or None
    if internal_note:
        existing.internal_note = internal_note.strip()
    existing.revoked_at = None
    existing.revoked_by_admin_id = None
    db.session.commit()
    log_event(student.id, "course_access_restored" if status == "restored_revoked" else "course_access_granted", actor=actor, actor_id=admin_id,
              entity=_entity(existing), meta={"course": course.title_en, "access_source": access_source_label(access_source, "en"), "expires": new_expires.isoformat() if new_expires else None})
    _notify_access(existing)
    return existing, status


def extend_access(enrollment, *, admin_id, duration_days=None, expires_at=None, no_expiration=False, reason=None):
    before = enrollment.expires_at
    enrollment.expires_at = _resolve_expiry(enrollment.course, duration_days=duration_days, expires_at=expires_at, no_expiration=no_expiration)
    db.session.commit()
    log_event(enrollment.student_id, "course_access_extended", actor="admin", actor_id=admin_id, entity=_entity(enrollment),
              meta={"course": enrollment.course.title_en, "from": before.isoformat() if before else None,
                    "to": enrollment.expires_at.isoformat() if enrollment.expires_at else None, "reason": (reason or "").strip() or None})
    return enrollment


def revoke_access(enrollment, *, admin_id, reason=None):
    enrollment.revoked_at = datetime.utcnow()
    enrollment.revoked_by_admin_id = admin_id
    db.session.commit()
    log_event(enrollment.student_id, "course_access_revoked", actor="admin", actor_id=admin_id, entity=_entity(enrollment),
              meta={"course": enrollment.course.title_en, "reason": (reason or "").strip() or None})
    return enrollment


def restore_access(enrollment, *, admin_id, note=None):
    enrollment.revoked_at = None
    enrollment.revoked_by_admin_id = None
    db.session.commit()
    log_event(enrollment.student_id, "course_access_restored", actor="admin", actor_id=admin_id, entity=_entity(enrollment),
              meta={"course": enrollment.course.title_en, "note": (note or "").strip() or None})
    return enrollment
