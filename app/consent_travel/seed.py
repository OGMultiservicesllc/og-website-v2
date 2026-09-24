"""First-run seed for the Consent to Travel Authorization for Minors service: the public Service row (under
the existing `notary` category) + price rules. Guarded to only add what is missing — never re-seeds over
Admin's own edits."""

from app.consent_travel import pricing
from app.extensions import db
from app.models import Service, ServiceCategory, ServiceContentItem

SERVICE_SLUG = "consent-to-travel-authorization"
CATEGORY_SLUG = "notary"
# The old, pre-Smart-Intake service page this one replaces — kept in the DB (never deleted) but
# unpublished so /notary shows only one Consent to Travel entry, the one wired to the real intake.
OLD_DUPLICATE_SLUG = "minor-travel-consent"

WHEN_NEEDED = [
    ("A minor is traveling without both parents", "Un menor viaja sin ambos padres"),
    ("A minor is traveling with only one parent", "Un menor viaja con solo uno de sus padres"),
    ("A minor is traveling with a grandparent, relative or family friend", "Un menor viaja con un abuelo, familiar o amigo de la familia"),
    ("An airline or border official is requiring a notarized consent letter", "Una aerolínea o funcionario fronterizo requiere una carta de consentimiento notariada"),
]
INCLUDED = [
    ("Review of your children's passports and birth certificates", "Revisión de los pasaportes y actas de nacimiento de tus hijos"),
    ("Determination of which parent(s) need to sign, per child", "Determinación de qué padre(s) deben firmar, por menor"),
    ("In-person notarization at our Paterson, NJ or Spring, TX office", "Notarización en persona en nuestra oficina de Paterson, NJ o Spring, TX"),
    ("Guidance in English and Spanish", "Orientación en inglés y español"),
]
FAQ = [
    (("Does selecting a location confirm my appointment?", "¿Seleccionar una ubicación confirma mi cita?"),
     ("No. All notarizations are by confirmed appointment only — OG will contact you to confirm the date and time.",
      "No. Todas las notarizaciones son únicamente con cita confirmada — OG te contactará para confirmar la fecha y hora."), "faq1"),
    (("Do I pay before OG reviews my case?", "¿Pago antes de que OG revise mi caso?"),
     ("No. OG reviews your case and confirms the price before any payment is requested.", "No. OG revisa tu caso y confirma el precio antes de solicitar cualquier pago."), "faq2"),
    (("Can I include more than one child?", "¿Puedo incluir a más de un menor?"),
     ("Yes — add each child one by one. Children who need the same parent(s) to consent can often go on the same document for a lower additional-child price.",
      "Sí — agrega a cada menor uno por uno. Los menores que necesitan el consentimiento de el/los mismo(s) padre(s) a menudo pueden ir en el mismo documento por un precio menor por menor adicional."), "faq3"),
]


def ensure_service():
    cat = ServiceCategory.query.filter_by(slug=CATEGORY_SLUG).first()
    if cat is None or Service.query.filter_by(slug=SERVICE_SLUG).first() is not None:
        return False
    svc = Service(
        category_id=cat.id, slug=SERVICE_SLUG, icon="document", is_published=True, is_featured=False, sort_order=50,
        title_en="Consent to Travel Authorization for Minors", title_es="Autorización de Viaje para Menores",
        short_en="A notarized letter authorizing a minor to travel without one or both parents present.",
        short_es="Una carta notariada que autoriza a un menor a viajar sin uno o ambos padres presentes.",
        hero_text_en="OG helps you prepare a notarized Consent to Travel document for your child. Add one or more children, tell us who they're traveling with, and OG reviews and confirms your price.",
        hero_text_es="OG te ayuda a preparar un documento notariado de Autorización de Viaje para tu hijo. Agrega uno o más menores, dinos con quién viajan, y OG revisa y confirma tu precio.",
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


def ensure_no_duplicate():
    """Unpublish the old 'Minor Travel Consent Notarization' service page now that the real Smart Intake
    ('Consent to Travel Authorization for Minors') replaces it — non-destructive (row/content kept, Admin
    can republish it), idempotent (no-op once already unpublished)."""
    old = Service.query.filter_by(slug=OLD_DUPLICATE_SLUG).first()
    if old is not None and old.is_published:
        old.is_published = False
        db.session.commit()
        return True
    return False


def ensure_all():
    seeded = ensure_service()
    seeded = bool(pricing.ensure_seed()) or seeded
    seeded = ensure_no_duplicate() or seeded
    return seeded
