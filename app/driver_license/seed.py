"""First-run seed for the NJ Driver License Assistance service: the public Service row (under the existing `nj-driver-license`
category), MVC locations and price rules. Guarded to only add what is missing — never re-seeds over Admin's own edits."""

from app.extensions import db
from app.models import Service, ServiceCategory, ServiceContentItem
from app.driver_license import locations, pricing, seed_questions

SERVICE_SLUG = "nj-driver-license-assistance"

WHEN_NEEDED = [
    ("You haven't started your NJ Driver License process yet", "Todavía no has comenzado tu proceso de Licencia de Conducir de NJ"),
    ("You need help preparing your documents for the 6-Point ID check", "Necesitas ayuda para preparar tus documentos para la verificación de 6 puntos"),
    ("A document needs a certified translation", "Un documento necesita una traducción certificada"),
    ("You need help scheduling your Initial Permit appointment", "Necesitas ayuda para programar tu cita del Initial Permit"),
    ("You want to practice for the Knowledge Test", "Quieres practicar para el examen teórico"),
]
INCLUDED = [
    ("Review of the documents you already have", "Revisión de los documentos que ya tienes"),
    ("Certified translations when a document needs one", "Traducciones certificadas cuando un documento las necesita"),
    ("Appointment assistance for your Initial Permit", "Asistencia con la cita para tu Initial Permit"),
    ("Free Knowledge Test practice with your OG account", "Práctica gratuita del examen teórico con tu cuenta de OG"),
    ("Guidance in English and Spanish", "Orientación en inglés y español"),
]
FAQ = [
    (("Does OG file anything with the NJ MVC for me?", "¿OG presenta algo ante el MVC de NJ en mi nombre?"),
     ("No. OG helps you prepare and understand the process. The MVC makes the final decisions about your documents, your appointment and your license.",
      "OG no presenta nada ante el MVC por ti; te ayuda a prepararte y entender el proceso. El MVC toma las decisiones finales sobre tus documentos, tu cita y tu licencia."),
     "faq1"),
    (("Do I need to know how many MVC points my documents are worth?", "¿Necesito saber cuántos puntos del MVC valen mis documentos?"),
     ("No. Just tell OG which documents you have — OG reviews everything for you.", "No. Solo dinos qué documentos tienes — OG revisa todo por ti."), "faq2"),
    (("Does having a foreign driver license waive my Road Test?", "¿Tener una licencia de conducir extranjera exime mi examen práctico?"),
     ("Not automatically. OG reviews your foreign license and helps determine your next step; the Road Test decision is confirmed by OG.",
      "No automáticamente. OG revisa tu licencia extranjera y te ayuda a determinar tu próximo paso; la decisión sobre el examen práctico la confirma OG."), "faq3"),
]


def ensure_service():
    cat = ServiceCategory.query.filter_by(slug="nj-driver-license").first()
    if cat is None or Service.query.filter_by(slug=SERVICE_SLUG).first() is not None:
        return False
    if not cat.subpage_endpoint:
        cat.subpage_endpoint = "public.nj_driver_license_subpage"
    svc = Service(
        category_id=cat.id, slug=SERVICE_SLUG, icon="license", is_published=True, is_featured=True, sort_order=0,
        title_en="NJ Driver License Assistance", title_es="Asistencia con la Licencia de Conducir de NJ",
        short_en="OG helps you prepare your documents, translations, appointments, and next steps for your NJ Driver License.",
        short_es="OG te ayuda a preparar tus documentos, traducciones, citas y próximos pasos para tu Licencia de Conducir de NJ.",
        hero_text_en="OG helps you prepare your documents, translations, appointments, and next steps. Not sure what you need? We'll guide you.",
        hero_text_es="OG te ayuda a preparar tus documentos, traducciones, citas y próximos pasos. ¿No sabes qué necesitas? Nosotros te guiamos.",
        cta_mode="default", requires_intake=False, requires_account=True,
    )
    db.session.add(svc)
    db.session.flush()
    for i, (en, es) in enumerate(WHEN_NEEDED, 1):
        db.session.add(ServiceContentItem(service_id=svc.id, kind="when_needed", sort_order=i, title_en=en, title_es=es))
    for i, (en, es) in enumerate(INCLUDED, 1):
        db.session.add(ServiceContentItem(service_id=svc.id, kind="included", sort_order=i, title_en=en, title_es=es))
    for i, (q, a, _key) in enumerate(FAQ, 1):
        db.session.add(ServiceContentItem(service_id=svc.id, kind="faq", sort_order=i, title_en=q[0], title_es=q[1] or q[0], body_en=a[0], body_es=a[1]))
    db.session.commit()
    return True


def ensure_service_content():
    """Backfill When Needed / Included / FAQ onto an existing Service row that was created (by an earlier partial
    run of this seeder) before this content was added — never touches a service that already has content items,
    so an admin's own edits are safe."""
    svc = Service.query.filter_by(slug=SERVICE_SLUG).first()
    if svc is None or ServiceContentItem.query.filter_by(service_id=svc.id).first() is not None:
        return False
    for i, (en, es) in enumerate(WHEN_NEEDED, 1):
        db.session.add(ServiceContentItem(service_id=svc.id, kind="when_needed", sort_order=i, title_en=en, title_es=es))
    for i, (en, es) in enumerate(INCLUDED, 1):
        db.session.add(ServiceContentItem(service_id=svc.id, kind="included", sort_order=i, title_en=en, title_es=es))
    for i, (q, a, _key) in enumerate(FAQ, 1):
        db.session.add(ServiceContentItem(service_id=svc.id, kind="faq", sort_order=i, title_en=q[0], title_es=q[1] or q[0], body_en=a[0], body_es=a[1]))
    db.session.commit()
    return True


def ensure_faq_translation_fix():
    """Repair the FAQ ServiceContentItem rows created by an earlier, buggy version of this seeder: two of the
    three Spanish FAQ questions were left blank (falling back to the English text) and the third held a stray
    English sentence instead of a translation. Only touches a row whose Spanish text still matches the OLD
    (wrong) value on file, so an Admin's own edit to the FAQ text is never overwritten."""
    svc = Service.query.filter_by(slug=SERVICE_SLUG).first()
    if svc is None:
        return False
    OLD_WRONG = {1: "OG makes the final decision about my documents?", 2: "Do I need to know how many MVC points my documents are worth?",
                 3: "Does having a foreign driver license waive my Road Test?"}
    changed = False
    for row in ServiceContentItem.query.filter_by(service_id=svc.id, kind="faq").all():
        old_wrong = OLD_WRONG.get(row.sort_order)
        correct = next((q[1] for q, _a, _k in FAQ if q[0] == (row.title_en or "")), None)
        if old_wrong and correct and row.title_es == old_wrong:
            row.title_es = correct
            changed = True
    if changed:
        db.session.commit()
    return changed


def ensure_category_wiring():
    """Backfill `subpage_endpoint` on the `nj-driver-license` category when it is still unset — the same
    early-return in `ensure_service()` that skipped content on an already-existing Service row also skipped
    this line, which left every 'NJ Driver License Assistance' service card linking back to the category's
    own URL instead of the service detail page. Never touches a category that already points somewhere."""
    cat = ServiceCategory.query.filter_by(slug="nj-driver-license").first()
    if cat is None or cat.subpage_endpoint:
        return False
    cat.subpage_endpoint = "public.nj_driver_license_subpage"
    db.session.commit()
    return True


def ensure_documents_resync():
    """One-time repair, safe to re-run: re-applies the current (narrower) upload-requirement rules to every
    existing DL case, so a case that already went through `docs.sync()` under the old logic (which requested
    every selected identity document, not just the ones OG actually needs) drops its now-unwanted requirements.
    Uses the same non-destructive `sync_requirements` every save already goes through — withdraws, never
    deletes, and never touches a document the customer already uploaded."""
    from app.driver_license import docs, service
    from app.models import DlCaseData

    touched = False
    for dl in DlCaseData.query.all():
        before = {r.rule_key for r in docs.requirements(dl)}
        docs.sync(dl, service.ctx(dl, "en"))
        after = {r.rule_key for r in docs.requirements(dl)}
        touched = touched or before != after
    return touched


def ensure_all():
    seeded = ensure_service()
    seeded = ensure_service_content() or seeded
    seeded = ensure_faq_translation_fix() or seeded
    seeded = ensure_category_wiring() or seeded
    seeded = bool(locations.ensure_seed()) or seeded
    seeded = bool(pricing.ensure_seed()) or seeded
    seeded = bool(seed_questions.ensure_seed()) or seeded
    seeded = ensure_documents_resync() or seeded
    return seeded
