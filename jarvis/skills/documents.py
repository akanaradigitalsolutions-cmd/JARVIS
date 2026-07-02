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
from pptx.util import Inches
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from jarvis.skills.base import skill
from jarvis.skills.filesystem import resolve_in_workspace

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

    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"])]
    if subtitle:
        story.append(Paragraph(subtitle, styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))

    for section in sections:
        story.append(Paragraph(section.get("heading", ""), styles["Heading2"]))
        if section.get("body"):
            story.append(Paragraph(section["body"], styles["BodyText"]))
        for bullet in section.get("bullets", []) or []:
            story.append(Paragraph(f"&bull;&nbsp;&nbsp;{bullet}", styles["BodyText"]))
        image_path = section.get("image_path")
        if image_path:
            resolved_img = resolve_in_workspace(image_path)
            if resolved_img.exists():
                story.append(Spacer(1, 0.15 * inch))
                story.append(RLImage(str(resolved_img), width=6 * inch, height=3.375 * inch, kind="proportional"))
        story.append(Spacer(1, 0.25 * inch))

    doc = SimpleDocTemplate(str(out_path), pagesize=letter)
    doc.build(story)
    return {"path": filename, "sections": len(sections)}


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

    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_slide.shapes.title.text = title
    if subtitle and len(title_slide.placeholders) > 1:
        title_slide.placeholders[1].text = subtitle

    for slide_def in slides:
        layout = prs.slide_layouts[1]  # title + content
        slide = prs.slides.add_slide(layout)
        slide.shapes.title.text = slide_def.get("heading", "")

        bullets = slide_def.get("bullets") or []
        if bullets:
            body = slide.placeholders[1].text_frame
            body.text = bullets[0]
            for bullet in bullets[1:]:
                p = body.add_paragraph()
                p.text = bullet

        image_path = slide_def.get("image_path")
        if image_path:
            resolved_img = resolve_in_workspace(image_path)
            if resolved_img.exists():
                slide.shapes.add_picture(str(resolved_img), Inches(5.5), Inches(1.5), width=Inches(4))

    prs.save(str(out_path))
    return {"path": filename, "slides": len(slides) + 1}


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
