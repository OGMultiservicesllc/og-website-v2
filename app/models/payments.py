"""OG Payments: the operational payment ledger — the source of truth for what a customer owes and has
paid, regardless of HOW they paid (Square online, or Zelle/cash/check/other recorded by Admin). Square is
the processor for online payments; it is never the only record of OG's payment history.

Three tables, deliberately not full double-entry accounting (see CLAUDE.md "OG Payments"):

`Charge` — "what is owed" for one service/course relationship. One row per case/enrollment/ad-hoc service;
its `total_cents` can be revised (each revision keeps the previous value for audit) as OG moves from an
Smart-Intake ESTIMATE to a CONFIRMED final price. `total_cents is None` means "No Payment Required" —
never assume $0 for a service nobody has priced.

`PaymentRequest` — a specific "please pay $X now" ask from Admin (Phase 23) — may be less than the full
balance (partial payments, Model D). What the customer is actually allowed to pay through Square is always
bounded by an OPEN PaymentRequest's `requested_cents`, never a client-supplied amount (Phase 30).

`Payment` — one payment attempt/record, Square or manual, always linked to a `Charge` (and optionally the
`PaymentRequest` it fulfills). `Refund` is a child of `Payment` — the original payment row is never deleted
or mutated to look unpaid; a refund is its own row so history is preserved (Phase 13).

Audit events reuse the EXISTING `app.activity.log_event`/`ActivityEvent` mechanism (entity=("charge", id) /
("payment", id)) — no separate payment-audit table, consistent with how `CaseRevision`/Academy enrollment
events already work in this project."""

from datetime import datetime

from app.extensions import db

CHARGE_CONTEXTS = ("case", "enrollment")  # exactly one of Charge.case_id / Charge.enrollment_id is set

PRICE_MODES = ("none", "estimate", "final")  # Charge.price_mode — an estimate is never an authoritative amount due (Phase 24)

PAYMENT_METHODS = [
    ("square", ("Card (Square)", "Tarjeta (Square)")),
    ("zelle", ("Zelle", "Zelle")),
    ("cash_app", ("Cash App", "Cash App")),
    ("cash", ("Cash", "Efectivo")),
    ("check", ("Check", "Cheque")),
    ("square_offline", ("Square (received outside the website)", "Square (recibido fuera del sitio web)")),
    ("other", ("Other", "Otro")),
]
MANUAL_METHODS = ("zelle", "cash_app", "cash", "check", "square_offline", "other")  # every method except "square" itself is Admin-recorded
# The subset a customer can pick at Academy checkout (Phase: alternate payment methods, 2026-09-23) — never
# "square" (that's the online Square Web Payments flow, unaffected) and never "check"/"square_offline"/"other"
# (Admin-only entries used when recording a payment after the fact, not offered as a checkout choice).
CHECKOUT_MANUAL_METHODS = ("zelle", "cash_app", "cash")

PAYMENT_STATUSES = ("pending", "completed", "failed", "canceled")
REFUND_STATUSES = ("pending", "completed", "failed")


def method_label(method, lang="en"):
    for key, (en, es) in PAYMENT_METHODS:
        if key == method:
            return es if lang == "es" else en
    return method or ""


class Charge(db.Model):
    __tablename__ = "charges"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"))  # most services
    enrollment_id = db.Column(db.Integer, db.ForeignKey("enrollments.id"))  # an Academy course the customer is ALREADY enrolled in (e.g. a renewal)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", name="fk_charges_course"))  # Model A "Enroll & Pay" — no Enrollment exists yet; one is created on successful payment
    description = db.Column(db.String(200), nullable=False)  # customer-facing, e.g. "I-130 Petition Preparation"
    currency = db.Column(db.String(3), nullable=False, default="USD", server_default="USD")
    total_cents = db.Column(db.Integer)  # null = not yet priced ("No Payment Required")
    price_mode = db.Column(db.String(10), nullable=False, default="none", server_default="none")  # none | estimate | final
    previous_total_cents = db.Column(db.Integer)  # the total before the most recent price change, for the audit trail
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"))
    priced_at = db.Column(db.DateTime)
    priced_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"))
    canceled_at = db.Column(db.DateTime)  # Admin can cancel a charge that's no longer needed; payments already made are untouched

    customer = db.relationship("Student")
    case = db.relationship("Case", backref=db.backref("charges", order_by="Charge.created_at"))
    enrollment = db.relationship("Enrollment", backref=db.backref("charges", order_by="Charge.created_at"))
    course = db.relationship("Course")
    requests = db.relationship("PaymentRequest", backref="charge", order_by="PaymentRequest.created_at", cascade="all, delete-orphan")
    payments = db.relationship("Payment", backref="charge", order_by="Payment.created_at", cascade="all, delete-orphan")

    @property
    def is_canceled(self):
        return self.canceled_at is not None

    def display_title(self, lang="en"):
        """Customer-facing title. `description` is an admin-authored, English-only label (same convention
        as every other admin-typed customer-facing string in this project) — EXCEPT a course purchase,
        where a real bilingual `Course.title(lang)` already exists and takes over so Spanish customers never
        see the English course name."""
        return self.course.title(lang) if self.course_id else self.description


class PaymentRequest(db.Model):
    __tablename__ = "payment_requests"

    id = db.Column(db.Integer, primary_key=True)
    charge_id = db.Column(db.Integer, db.ForeignKey("charges.id"), nullable=False, index=True)
    requested_cents = db.Column(db.Integer, nullable=False)
    message = db.Column(db.String(500))  # optional customer-facing note ("Please pay the deposit to begin.")
    due_date = db.Column(db.Date)  # optional, never required (spec: "Do NOT require due date")
    status = db.Column(db.String(10), nullable=False, default="open", server_default="open")  # open | fulfilled | canceled
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"))
    fulfilled_at = db.Column(db.DateTime)
    canceled_at = db.Column(db.DateTime)
    canceled_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"))

    payments = db.relationship("Payment", backref="payment_request", order_by="Payment.created_at")

    @property
    def is_open(self):
        return self.status == "open"


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    charge_id = db.Column(db.Integer, db.ForeignKey("charges.id"), nullable=False, index=True)
    payment_request_id = db.Column(db.Integer, db.ForeignKey("payment_requests.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)  # denormalized for fast, safe ownership checks
    receipt_number = db.Column(db.String(20), unique=True)  # "OGP-000123", assigned once the row exists (matches Case's OGC-/Application's OGF- convention)
    amount_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="USD", server_default="USD")
    method = db.Column(db.String(20), nullable=False)  # square | zelle | cash | check | square_offline | other
    status = db.Column(db.String(10), nullable=False, default="pending", server_default="pending")  # pending | completed | failed | canceled
    failure_reason = db.Column(db.String(300))

    # Square-specific (all optional — null for manual payments). Never card number/CVV.
    square_payment_id = db.Column(db.String(80), unique=True)
    square_order_id = db.Column(db.String(80))
    idempotency_key = db.Column(db.String(80), unique=True)  # generated once per attempt, reused verbatim on retry (Phase 8)
    card_brand = db.Column(db.String(30))
    card_last4 = db.Column(db.String(4))

    # Manual-payment fields (Phase 6). Never settable by the customer.
    reference = db.Column(db.String(120))  # e.g. a check number or Zelle confirmation
    internal_note = db.Column(db.Text)  # admin-only, never shown to the customer
    recorded_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"))  # null for a Square/customer-initiated payment
    payment_date = db.Column(db.Date)  # when the money actually arrived (manual payments only; may predate created_at)

    # Alternate checkout methods (Zelle/Cash App/Pay at Office, 2026-09-23): the customer's own selection at
    # checkout creates a PENDING Payment (method set, recorded_by_admin_id still null — no admin has acted
    # yet); Admin's "Confirm Payment" / "Cancel / Reject" then resolves it. canceled_at/canceled_by_admin_id
    # mirror the exact same audit-trail shape Charge/PaymentRequest already use for their own cancellation.
    canceled_at = db.Column(db.DateTime)
    canceled_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime)

    customer = db.relationship("Student")
    refunds = db.relationship("Refund", backref="payment", order_by="Refund.created_at", cascade="all, delete-orphan")

    @property
    def is_manual(self):
        return self.method != "square"

    @property
    def refunded_cents(self):
        return sum(r.amount_cents for r in self.refunds if r.status == "completed")

    @property
    def net_cents(self):
        return self.amount_cents - self.refunded_cents


class Refund(db.Model):
    __tablename__ = "refunds"

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=False, index=True)
    amount_cents = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(10), nullable=False, default="pending", server_default="pending")  # pending | completed | failed
    reason = db.Column(db.String(300))
    square_refund_id = db.Column(db.String(80), unique=True)  # null for a manual-payment refund (bookkeeping only, no processor call)
    idempotency_key = db.Column(db.String(80), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"))
    completed_at = db.Column(db.DateTime)
