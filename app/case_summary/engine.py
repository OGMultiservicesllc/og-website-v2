"""Case Summary PDF Engine — the ONLY code in this package that knows how to lay a `CaseSummaryDoc` out
on a page (see blocks.py for the presenter-facing intermediate representation this consumes).

Internal OG working document, not the final government/service form — every page carries
"For OG Multiservices Internal Case Preparation" so it can never be mistaken for one.
"""
import re
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app import business_info
from app.case_summary.blocks import (
    DocumentsBlock,
    KeyValueBlock,
    NotesBlock,
    PricingBlock,
    TableBlock,
    WarningBlock,
)

NAVY = colors.HexColor("#0f2a4a")
ACCENT = colors.HexColor("#0aa3cf")
SLATE = colors.HexColor("#475569")
LIGHT = colors.HexColor("#eef2f7")
WARN = colors.HexColor("#b45309")
WARN_BG = colors.HexColor("#fff7ed")
OK_GREEN = colors.HexColor("#047857")

MARGIN = 0.6 * inch

# Some option labels elsewhere in this app are prefixed with an emoji for the customer-facing UI (e.g.
# tax/y2025.py's income options). The PDF's base Helvetica font has no emoji glyphs — an unstripped emoji
# renders as a solid box, which reads like a rendering bug. Stripped here, once, for every piece of text
# that reaches the PDF, rather than asking every presenter to know about this.
_EMOJI_RE = re.compile(
    "[\U0001F1E6-\U0001FAFF\U00002600-\U000027BF\U00002190-\U000021FF\U00002B00-\U00002BFF\U0001F000-\U0001F0FF]+",
    flags=re.UNICODE,
)


def _strip_emoji(s):
    return _EMOJI_RE.sub("", s).strip()


def safe_filename(case_number, suffix="Case_Summary"):
    """"OG_CT-000009_Case_Summary.pdf" — a case number is already a short, server-generated code
    (never customer-controlled free text), but it's still sanitized before it ever reaches a filename."""
    stub = re.sub(r"[^A-Za-z0-9_-]+", "-", (case_number or "case").strip())
    return f"OG_{stub}_{suffix}.pdf"


def _styles():
    ss = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("og_title", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=15, textColor=NAVY, spaceAfter=2, alignment=0),
        "subtitle": ParagraphStyle("og_subtitle", parent=ss["Normal"], fontName="Helvetica", fontSize=9, textColor=SLATE, spaceAfter=10),
        "internal_note": ParagraphStyle("og_internal", parent=ss["Normal"], fontName="Helvetica-Oblique", fontSize=8, textColor=SLATE, spaceAfter=12),
        "section": ParagraphStyle("og_section", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, textColor=colors.white, backColor=NAVY,
                                  spaceBefore=10, spaceAfter=6, leftIndent=6, borderPadding=(4, 4, 4, 4)),
        "person_role": ParagraphStyle("og_role", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT, spaceBefore=8, spaceAfter=0),
        "subheading": ParagraphStyle("og_subhead", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=9.5, textColor=NAVY, spaceBefore=6, spaceAfter=3),
        "label": ParagraphStyle("og_label", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=8.7, textColor=SLATE),
        "value": ParagraphStyle("og_value", parent=ss["Normal"], fontName="Helvetica", fontSize=8.7, textColor=colors.black),
        "missing": ParagraphStyle("og_missing", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=8.7, textColor=WARN),
        "warning_item": ParagraphStyle("og_warn_item", parent=ss["Normal"], fontName="Helvetica", fontSize=8.7, textColor=WARN),
        "note": ParagraphStyle("og_note", parent=ss["Normal"], fontName="Helvetica", fontSize=8.7, textColor=colors.black, leftIndent=6),
        "table_header": ParagraphStyle("og_th", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=8.3, textColor=colors.white),
        "table_cell": ParagraphStyle("og_td", parent=ss["Normal"], fontName="Helvetica", fontSize=8.3, textColor=colors.black),
        "case_info_label": ParagraphStyle("og_ci_label", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=8.7, textColor=colors.white),
        "case_info_value": ParagraphStyle("og_ci_value", parent=ss["Normal"], fontName="Helvetica", fontSize=8.7, textColor=colors.white),
    }
    return styles


def _kv_table(styles, kv: KeyValueBlock):
    flow = []
    if kv.heading:
        flow.append(Paragraph(_esc(kv.heading), styles["subheading"]))
    rows = []
    for f in kv.fields:
        if f.missing:
            rows.append([Paragraph(_esc(f.label), styles["label"]), Paragraph("MISSING INFORMATION", styles["missing"])])
        elif f.value not in (None, ""):
            rows.append([Paragraph(_esc(f.label), styles["label"]), Paragraph(_esc(f.value), styles["value"])])
    if not rows:
        return flow
    t = Table(rows, colWidths=[1.9 * inch, 4.8 * inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LIGHT),
    ]))
    flow.append(t)
    return flow


def _table_block(styles, tb: TableBlock):
    flow = []
    if tb.heading:
        flow.append(Paragraph(_esc(tb.heading), styles["subheading"]))
    header = [Paragraph(_esc(h), styles["table_header"]) for h in tb.headers]
    data = [header] + [[Paragraph(_esc(c), styles["table_cell"]) for c in row] for row in tb.rows]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.4, LIGHT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    flow.append(t)
    return flow


_DOC_STATUS = {
    "received": ("✓ Received", OK_GREEN),
    "missing": ("MISSING", WARN),
    "not_required": ("Not required", SLATE),
}


def _documents_block(styles, db: DocumentsBlock):
    flow = []
    for group in db.groups:
        if group.person_label:
            flow.append(Paragraph(_esc(group.person_label), styles["subheading"]))
        rows = []
        for d in group.documents:
            text, color = _DOC_STATUS.get(d.status, (d.status, SLATE))
            note = f" ({_esc(d.note)})" if d.note else ""
            rows.append([Paragraph(_esc(d.label), styles["value"]), Paragraph(f'<font color="{color.hexval()}">{text}</font>{note}', styles["value"])])
        if rows:
            t = Table(rows, colWidths=[3.6 * inch, 3.1 * inch])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                                   ("LINEBELOW", (0, 0), (-1, -2), 0.4, LIGHT)]))
            flow.append(t)
    return flow


def _warning_block(styles, wb: WarningBlock):
    if not wb.items:
        return []
    rows = [[Paragraph(f"! {_esc(i)}", styles["warning_item"])] for i in wb.items]
    t = Table(rows, colWidths=[6.7 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), WARN_BG), ("BOX", (0, 0), (-1, -1), 0.6, WARN),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 6)]))
    return [Paragraph(_esc(wb.heading), styles["subheading"]), t]


def _pricing_block(styles, pb: PricingBlock):
    flow = _kv_table(styles, KeyValueBlock(fields=pb.lines))
    if pb.payment_status:
        flow.append(Spacer(1, 3))
        flow.append(Paragraph(f'<b>Payment status:</b> {_esc(pb.payment_status)}', styles["value"]))
    return flow


def _notes_block(styles, nb: NotesBlock):
    flow = [Paragraph(_esc(nb.heading), styles["subheading"])]
    if not nb.notes:
        flow.append(Paragraph("None on file.", styles["value"]))
        return flow
    for n in nb.notes:
        flow.append(Paragraph(f"• {_esc(n)}", styles["note"]))
    return flow


def _esc(v):
    s = _strip_emoji(str(v))
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _block_flow(styles, block):
    if isinstance(block, KeyValueBlock):
        return _kv_table(styles, block)
    if isinstance(block, TableBlock):
        return _table_block(styles, block)
    if isinstance(block, DocumentsBlock):
        return _documents_block(styles, block)
    if isinstance(block, WarningBlock):
        return _warning_block(styles, block)
    if isinstance(block, PricingBlock):
        return _pricing_block(styles, block)
    if isinstance(block, NotesBlock):
        return _notes_block(styles, block)
    return []


def _case_info_table(styles, doc):
    rows = [
        [Paragraph("Case #", styles["case_info_label"]), Paragraph(_esc(doc.case_number), styles["case_info_value"]),
         Paragraph("Customer", styles["case_info_label"]), Paragraph(_esc(doc.customer_name), styles["case_info_value"])],
        [Paragraph("Application", styles["case_info_label"]), Paragraph(_esc(doc.application_label), styles["case_info_value"]),
         Paragraph("Status", styles["case_info_label"]), Paragraph(_esc(doc.status_label), styles["case_info_value"])],
    ]
    if doc.submitted_at:
        rows.append([Paragraph("Submitted", styles["case_info_label"]), Paragraph(_esc(doc.submitted_at), styles["case_info_value"]),
                    Paragraph("Last updated", styles["case_info_label"]), Paragraph(_esc(doc.updated_at or "—"), styles["case_info_value"])])
    t = Table(rows, colWidths=[0.9 * inch, 2.55 * inch, 0.9 * inch, 2.55 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def render(doc, *, generated_by=None):
    """CaseSummaryDoc -> PDF bytes."""
    styles = _styles()
    buf = BytesIO()
    generated_at = datetime.utcnow()

    def _header_footer(canvas, pdf):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(SLATE)
        canvas.drawString(MARGIN, LETTER[1] - 0.35 * inch, business_info.BUSINESS_NAME.upper())
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(LETTER[0] - MARGIN, LETTER[1] - 0.35 * inch, f"Case {doc.case_number}")
        canvas.setStrokeColor(LIGHT)
        canvas.line(MARGIN, LETTER[1] - 0.42 * inch, LETTER[0] - MARGIN, LETTER[1] - 0.42 * inch)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(SLATE)
        footer = f"OG Multiservices LLC — Internal Case Summary — Case {doc.case_number} — Generated {generated_at.strftime('%b %d, %Y %I:%M %p UTC')}"
        canvas.drawString(MARGIN, 0.4 * inch, footer)
        canvas.drawRightString(LETTER[0] - MARGIN, 0.4 * inch, f"Page {pdf.page}")
        canvas.restoreState()

    frame = Frame(MARGIN, 0.65 * inch, LETTER[0] - 2 * MARGIN, LETTER[1] - 1.35 * inch, id="main")
    template = PageTemplate(id="main", frames=[frame], onPage=_header_footer)
    pdf = BaseDocTemplate(buf, pagesize=LETTER, pageTemplates=[template],
                          leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=0.65 * inch,
                          title=f"{doc.case_number} Case Summary", author=business_info.BUSINESS_NAME)

    story = []
    story.append(Paragraph(f"{_esc(doc.service_title)} — CASE SUMMARY", styles["title"]))
    story.append(Paragraph("For OG Multiservices Internal Case Preparation — not the final government/service form", styles["subtitle"]))
    story.append(_case_info_table(styles, doc))
    story.append(Spacer(1, 8))

    if doc.unsupported_reason:
        story.append(Paragraph("This case type is not yet supported by the Case Summary PDF engine.", styles["section"]))
        story.append(Spacer(1, 4))
        story.append(Paragraph(_esc(doc.unsupported_reason), styles["value"]))
    else:
        for section in doc.sections:
            sec_flow = []
            if section.person_role:
                sec_flow.append(Paragraph(_esc(section.person_role), styles["person_role"]))
            sec_flow.append(Paragraph(_esc(section.title.upper()), styles["section"]))
            for block in section.blocks:
                sec_flow.extend(_block_flow(styles, block))
                sec_flow.append(Spacer(1, 4))
            # Keep a section's heading with at least its first block on one page where reasonably small;
            # a large section (many blocks) still flows normally rather than forcing everything together.
            if sum(1 for b in section.blocks) <= 3:
                story.append(KeepTogether(sec_flow))
            else:
                story.extend(sec_flow)

    pdf.build(story)
    return buf.getvalue()
