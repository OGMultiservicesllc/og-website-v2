"""Case Summary PDF Engine — intermediate representation (2026-09-25).

A presenter (one per intake type — see app/case_summary/presenters.py) never touches ReportLab; it just
builds a `CaseSummaryDoc` out of these plain dataclasses. The engine (app/case_summary/engine.py) is the
ONLY code that knows how to lay a `CaseSummaryDoc` out on a page. This split is what lets 13 very
different intakes share one PDF engine without one generic content layout: every presenter controls
WHAT appears and in what order; the engine controls HOW it looks.

Deterministic by construction: nothing here calls an LLM, infers a value, or fills in a blank — a
presenter either has a real answer from structured case data, or it doesn't (in which case it uses
Field(..., missing=True) so the engine renders an explicit "Missing Information" warning, never a guess).
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Field:
    """One label/value line. `missing=True` renders as an explicit warning line, never a blank — the
    presenter decides that using the SAME validation/required rules the intake itself already applies
    (e.g. `item["missing"]` from `intake_engine.review_sections`), never an invented requirement."""

    label: str
    value: Optional[str] = None
    missing: bool = False


@dataclass
class KeyValueBlock:
    """A set of label/value lines, optionally under a small bold sub-heading (used when a Section holds
    more than one logical group, e.g. a PETITIONER section with "Identity" / "Address History" / "Employment"
    sub-groups from several intake pages)."""

    fields: List[Field] = field(default_factory=list)
    heading: Optional[str] = None


@dataclass
class TableRow:
    cells: List[str]


@dataclass
class TableBlock:
    headers: List[str]
    rows: List[List[str]]
    heading: Optional[str] = None


@dataclass
class DocumentLine:
    """One document requirement. `status` is one of "received" | "missing" | "not_required" — set by the
    presenter from the SAME DocumentRequirement.status this case's Admin/customer views already use,
    never re-derived. `note` is a short, optional clarification (e.g. "front" / "back" / "under review")."""

    label: str
    status: str
    note: Optional[str] = None


@dataclass
class DocumentGroup:
    """Documents for one person (or None for case-level documents with no single owner)."""

    person_label: Optional[str]
    documents: List[DocumentLine] = field(default_factory=list)


@dataclass
class DocumentsBlock:
    groups: List[DocumentGroup] = field(default_factory=list)


@dataclass
class WarningBlock:
    """A block of ⚠ Missing Information lines — used for a concise summary at the top of a section when
    several items are missing, in ADDITION to (not instead of) marking each Field individually."""

    items: List[str] = field(default_factory=list)
    heading: str = "Missing Information"


@dataclass
class PricingBlock:
    """Never claims "Paid" unless actual Payment records confirm it — the presenter builds `payment_status`
    from `app.payments.status_of()`/`paid_cents()`/`balance_cents()`, the same functions every other
    payment surface in this app already uses, never a re-derived notion of "paid"."""

    lines: List[Field] = field(default_factory=list)
    payment_status: Optional[str] = None


@dataclass
class NotesBlock:
    heading: str  # "Customer Notes" | "Internal OG Notes"
    notes: List[str] = field(default_factory=list)


Block = object  # KeyValueBlock | TableBlock | DocumentsBlock | WarningBlock | PricingBlock | NotesBlock


@dataclass
class Section:
    title: str
    blocks: List[Block] = field(default_factory=list)
    person_role: Optional[str] = None  # e.g. "PETITIONER" — rendered as a strong role banner above the title


@dataclass
class CaseSummaryDoc:
    """The whole document. `service_title` is the form/service name shown under the OG banner
    ("I-130 PETITION FOR ALIEN RELATIVE — CASE SUMMARY"); `unsupported_reason`, when set, means the
    engine renders a single plain notice page instead of a fabricated raw-data dump (per the task's
    explicit instruction: report an unsupported intake, never dump JSON)."""

    service_title: str
    case_number: str
    customer_name: str
    application_label: str
    status_label: str
    submitted_at: Optional[str] = None
    updated_at: Optional[str] = None
    sections: List[Section] = field(default_factory=list)
    unsupported_reason: Optional[str] = None
