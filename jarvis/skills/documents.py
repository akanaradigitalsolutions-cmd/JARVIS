"""Document generation skills: PDF reports, PowerPoint presentations, and
Excel workbooks. This is what lets Jarvis "compile a summary in PDF" or
"create a presentation" from data or from its own analysis.

All outputs are written inside the sandboxed workspace (see filesystem.py).
"""

from __future__ import annotations

from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import BaseDocTemplate, Frame, HRFlowable, NextPageTemplate, PageTemplate
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, Spacer

from jarvis.skills.base import skill
from jarvis.skills.filesystem import resolve_in_workspace

# Shared "professional business" palette, used by both the PPTX and PDF
# generators so a report and a deck built from the same request look like
# they belong to the same brand.
_NAVY = "141B2E"
_ACCENT = "2EC4B6"
_MUTED = "6B7A8F"
_TEXT_DARK = "1F2A37"
_TEXT_LIGHT = "F5F7FA"


def _hc(hex_str: str) -> HexColor:
    """reportlab's HexColor wants a leading '#'; our shared palette
    constants don't have one since python-pptx's RGBColor.from_string
    requires the opposite (no '#')."""
    return HexColor(f"#{hex_str}")


_SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "heading": {"type": "string"},
        "body": {"type": "string", "description": "Paragraph text for this section."},
        "image_path": {
            "type": "string",
            "description": "Optional path (in the workspace) to a chart/image to embed after the text.",
        },
        "bullets": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional bullet points instead of/in addition to body text.",
        },
    },
    "required": ["heading"],
}


def _pdf_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "JarvisTitle", parent=base["Title"], textColor=_hc(_NAVY), fontSize=26, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "JarvisSubtitle", parent=base["Normal"], textColor=_hc(_MUTED), fontSize=12, spaceAfter=4,
        ),
        "heading": ParagraphStyle(
            "JarvisHeading2", parent=base["Heading2"], textColor=_hc(_NAVY), spaceBefore=16, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "JarvisBody", parent=base["BodyText"], textColor=_hc(_TEXT_DARK), leading=15,
        ),
        "bullet": ParagraphStyle(
            "JarvisBullet", parent=base["BodyText"], textColor=_hc(_TEXT_DARK), leftIndent=14, leading=15,
        ),
    }


_PDF_MARGIN_X = 0.75 * inch
_PDF_BOTTOM_MARGIN = 0.8 * inch
_PDF_COVER_BAND_HEIGHT = 2.2 * inch
_PDF_LATER_TOP_MARGIN = 0.9 * inch


def _pdf_page_number(canvas, doc) -> None:
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(_hc(_MUTED))
    canvas.drawRightString(letter[0] - 0.6 * inch, 0.5 * inch, f"Page {doc.page}")


def _make_pdf_cover_decoration(title: str, subtitle: str):
    """Draws the navy cover band with the title/subtitle straight onto the
    canvas (not as flowables), matching the PPTX title slide's look — this
    is what makes the report's first page feel like a designed cover
    instead of a plain page with a heading at the top."""

    def _decorate(canvas, doc) -> None:
        canvas.saveState()
        page_width, page_height = letter
        canvas.setFillColor(_hc(_NAVY))
        canvas.rect(0, page_height - _PDF_COVER_BAND_HEIGHT, page_width, _PDF_COVER_BAND_HEIGHT, fill=1, stroke=0)

        canvas.setFillColor(_hc(_TEXT_LIGHT))
        canvas.setFont("Helvetica-Bold", 25)
        canvas.drawString(_PDF_MARGIN_X, page_height - 1.15 * inch, title)

        canvas.setFillColor(_hc(_ACCENT))
        canvas.rect(_PDF_MARGIN_X, page_height - 1.4 * inch, 1.3 * inch, 3, fill=1, stroke=0)

        if subtitle:
            canvas.setFillColor(_hc(_MUTED))
            canvas.setFont("Helvetica", 12)
            canvas.drawString(_PDF_MARGIN_X, page_height - 1.75 * inch, subtitle)

        _pdf_page_number(canvas, doc)
        canvas.restoreState()

    return _decorate


def _pdf_later_page_decoration(canvas, doc) -> None:
    """Thin accent bar across the top of every page after the cover, plus
    the page number — a lighter-weight echo of the cover band."""
    canvas.saveState()
    page_width, page_height = letter
    canvas.setFillColor(_hc(_ACCENT))
    canvas.rect(0, page_height - 0.12 * inch, page_width, 0.12 * inch, fill=1, stroke=0)
    _pdf_page_number(canvas, doc)
    canvas.restoreState()


@skill(
    name="generate_pdf_report",
    description=(
        "Create a PDF report with a title and a series of sections (each with a heading, "
        "body text and/or bullet points, and an optional chart/image). Use this to compile "
        "analysis, summaries, or written reports into a shareable PDF file in the workspace."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Output filename, e.g. 'q2_report.pdf'."},
            "title": {"type": "string"},
            "subtitle": {"type": "string", "description": "Optional subtitle, e.g. a date range or author."},
            "sections": {"type": "array", "items": _SECTION_SCHEMA},
        },
        "required": ["filename", "title", "sections"],
    },
)
def generate_pdf_report(
    filename: str,
    title: str,
    sections: list[dict[str, Any]],
    subtitle: str = "",
) -> dict:
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    out_path = resolve_in_workspace(filename)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _pdf_styles()
    page_width, page_height = letter
    frame_width = page_width - 2 * _PDF_MARGIN_X

    cover_frame = Frame(
        _PDF_MARGIN_X, _PDF_BOTTOM_MARGIN, frame_width,
        page_height - _PDF_COVER_BAND_HEIGHT - 0.4 * inch - _PDF_BOTTOM_MARGIN, id="cover",
    )
    later_frame = Frame(
        _PDF_MARGIN_X, _PDF_BOTTOM_MARGIN, frame_width,
        page_height - _PDF_LATER_TOP_MARGIN - _PDF_BOTTOM_MARGIN, id="later",
    )

    doc = BaseDocTemplate(str(out_path), pagesize=letter)
    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=cover_frame, onPage=_make_pdf_cover_decoration(title, subtitle)),
        PageTemplate(id="Later", frames=later_frame, onPage=_pdf_later_page_decoration),
    ])

    story: list[Any] = [NextPageTemplate("Later")]

    for section in sections:
        story.append(Paragraph(section.get("heading", ""), styles["heading"]))
        story.append(HRFlowable(width="18%", thickness=2, color=_hc(_ACCENT), spaceAfter=8, hAlign="LEFT"))
        if section.get("body"):
            story.append(Paragraph(section["body"], styles["body"]))
        for bullet in section.get("bullets", []) or []:
            story.append(Paragraph(f'<font color="#{_ACCENT}">&#9679;</font>&nbsp;&nbsp;{bullet}', styles["bullet"]))
        image_path = section.get("image_path")
        if image_path:
            resolved_img = resolve_in_workspace(image_path)
            if resolved_img.exists():
                story.append(Spacer(1, 0.15 * inch))
                story.append(RLImage(str(resolved_img), width=6 * inch, height=3.375 * inch, kind="proportional"))
        story.append(Spacer(1, 0.25 * inch))

    doc.build(story)
    return {"path": filename, "sections": len(sections)}


def _blank_layout(prs: Presentation):
    """The default python-pptx template's blank layout (no placeholders at
    all), so every element on a slide is one we placed and styled
    ourselves rather than an unstyled inherited placeholder."""
    for layout in prs.slide_layouts:
        if len(layout.placeholders) == 0:
            return layout
    return prs.slide_layouts[6]


def _add_rect(slide, left, top, width, height, color_hex: str):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(color_hex)
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def _add_text(
    slide, left, top, width, height, text: str, size: int, color_hex: str,
    bold: bool = False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color_hex)
    return box


def _add_bullets(slide, left, top, width, height, bullets: list[str]):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, bullet in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(12)
        dot = p.add_run()
        dot.text = "▸  "
        dot.font.size = Pt(15)
        dot.font.bold = True
        dot.font.color.rgb = RGBColor.from_string(_ACCENT)
        text_run = p.add_run()
        text_run.text = bullet
        text_run.font.size = Pt(15)
        text_run.font.color.rgb = RGBColor.from_string(_TEXT_DARK)
    return box


@skill(
    name="generate_presentation",
    description=(
        "Create a PowerPoint (.pptx) presentation with a title slide and a series of content "
        "slides (each with a heading, bullet points, and an optional image/chart). Use this "
        "when asked to 'create a presentation' or 'make slides'."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Output filename, e.g. 'q2_marketing.pptx'."},
            "title": {"type": "string"},
            "subtitle": {"type": "string"},
            "slides": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {"type": "string"},
                        "bullets": {"type": "array", "items": {"type": "string"}},
                        "image_path": {"type": "string", "description": "Optional path (in workspace) to an image/chart."},
                    },
                    "required": ["heading"],
                },
            },
        },
        "required": ["filename", "title", "slides"],
    },
)
def generate_presentation(
    filename: str,
    title: str,
    slides: list[dict[str, Any]],
    subtitle: str = "",
) -> dict:
    if not filename.lower().endswith(".pptx"):
        filename += ".pptx"
    out_path = resolve_in_workspace(filename)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    prs = Presentation()
    prs.slide_width = Inches(13.333)  # 16:9 widescreen, not the dated 4:3 default
    prs.slide_height = Inches(7.5)
    layout = _blank_layout(prs)
    sw, sh = prs.slide_width, prs.slide_height

    # ---- title slide: full-bleed navy background, big title, gold rule ----
    title_slide = prs.slides.add_slide(layout)
    _add_rect(title_slide, 0, 0, sw, sh, _NAVY)
    _add_text(
        title_slide, Inches(0.9), Inches(2.9), sw - Inches(1.8), Inches(1.4),
        title, size=40, color_hex=_TEXT_LIGHT, bold=True,
    )
    _add_rect(title_slide, Inches(0.95), Inches(3.95), Inches(1.6), Pt(3), _ACCENT)
    if subtitle:
        _add_text(
            title_slide, Inches(0.9), Inches(4.2), sw - Inches(1.8), Inches(0.7),
            subtitle, size=18, color_hex=_MUTED,
        )

    # ---- content slides: white background, gold top bar, heading + body ----
    for i, slide_def in enumerate(slides):
        slide = prs.slides.add_slide(layout)
        _add_rect(slide, 0, 0, sw, Pt(6), _ACCENT)
        _add_text(
            slide, Inches(0.7), Inches(0.4), sw - Inches(1.4), Inches(0.9),
            slide_def.get("heading", ""), size=28, color_hex=_NAVY, bold=True,
        )
        _add_rect(slide, Inches(0.72), Inches(1.15), Inches(1.1), Pt(3), _ACCENT)

        bullets = slide_def.get("bullets") or []
        image_path = slide_def.get("image_path")
        resolved_img = resolve_in_workspace(image_path) if image_path else None
        has_image = bool(resolved_img and resolved_img.exists())

        body_width = Inches(6.0) if has_image else (sw - Inches(1.4))
        if bullets:
            _add_bullets(slide, Inches(0.7), Inches(1.6), body_width, sh - Inches(2.1), bullets)
        if has_image:
            slide.shapes.add_picture(
                str(resolved_img), Inches(7.1), Inches(1.7), width=sw - Inches(7.1) - Inches(0.6),
            )
        _add_text(
            slide, Inches(0.7), sh - Inches(0.55), Inches(4), Inches(0.4),
            "JARVIS", size=10, color_hex=_MUTED,
        )
        _add_text(
            slide, sw - Inches(2.7), sh - Inches(0.55), Inches(2), Inches(0.4),
            f"{i + 1:02d}", size=10, color_hex=_MUTED, align=PP_ALIGN.RIGHT,
        )

    # ---- closing slide: same navy treatment as the title slide, so the ----
    # ---- deck bookends itself instead of just stopping after the last topic
    closing_slide = prs.slides.add_slide(layout)
    _add_rect(closing_slide, 0, 0, sw, sh, _NAVY)
    _add_text(
        closing_slide, Inches(0.9), Inches(3.1), sw - Inches(1.8), Inches(1.1),
        "Thank You", size=36, color_hex=_TEXT_LIGHT, bold=True, align=PP_ALIGN.CENTER,
    )
    _add_rect(closing_slide, sw / 2 - Inches(0.8), Inches(4.05), Inches(1.6), Pt(3), _ACCENT)

    prs.save(str(out_path))
    return {"path": filename, "slides": len(slides) + 2}


@skill(
    name="generate_excel_report",
    description=(
        "Create an Excel (.xlsx) workbook from tabular data. Accepts one or more sheets, "
        "each a list of rows (first row is treated as the header)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Output filename, e.g. 'summary.xlsx'."},
            "sheets": {
                "type": "object",
                "description": "Map of sheet name -> rows (list of lists). First row is the header.",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "array"},
                },
            },
        },
        "required": ["filename", "sheets"],
    },
)
def generate_excel_report(filename: str, sheets: dict[str, list[list[Any]]]) -> dict:
    if not filename.lower().endswith(".xlsx"):
        filename += ".xlsx"
    out_path = resolve_in_workspace(filename)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    wb.remove(wb.active)

    for sheet_name, rows in sheets.items():
        ws = wb.create_sheet(title=sheet_name[:31])
        for row in rows:
            ws.append(row)
        if rows:
            for col_idx in range(1, len(rows[0]) + 1):
                ws.cell(row=1, column=col_idx).font = Font(bold=True)
                ws.column_dimensions[get_column_letter(col_idx)].width = 18

    wb.save(str(out_path))
    return {"path": filename, "sheets": list(sheets.keys())}
