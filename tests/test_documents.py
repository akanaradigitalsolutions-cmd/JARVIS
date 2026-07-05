from jarvis.skills.data_analysis import generate_chart
from jarvis.skills.documents import generate_excel_report, generate_pdf_report, generate_presentation
from jarvis.skills.filesystem import resolve_in_workspace, write_text_file

CSV = "month,revenue\nJan,10000\nFeb,12500\nMar,9800\n"


def test_generate_pdf_report_creates_file():
    result = generate_pdf_report(
        filename="report.pdf",
        title="Q1 Summary",
        subtitle="Jan-Mar",
        sections=[
            {"heading": "Overview", "body": "Revenue grew steadily.", "bullets": ["Jan: $10,000", "Feb: $12,500"]},
        ],
    )
    assert result["sections"] == 1
    path = resolve_in_workspace("report.pdf")
    assert path.exists()
    assert path.stat().st_size > 0


def test_generate_pdf_report_embeds_chart():
    write_text_file("sales2.csv", CSV, overwrite=True)
    chart = generate_chart(path="sales2.csv", chart_type="line", output_filename="chart.png", x="month", y=["revenue"])
    result = generate_pdf_report(
        filename="report_with_chart.pdf",
        title="With chart",
        sections=[{"heading": "Revenue", "body": "See chart below.", "image_path": chart["path"]}],
    )
    assert resolve_in_workspace("report_with_chart.pdf").exists()
    assert result["sections"] == 1


def test_generate_presentation_creates_file():
    result = generate_presentation(
        filename="deck.pptx",
        title="Q1 Marketing Results",
        subtitle="Prepared by Jarvis",
        slides=[
            {"heading": "Highlights", "bullets": ["CTR up 12%", "CPC down 8%"]},
            {"heading": "Next steps", "bullets": ["Increase budget on top campaign"]},
        ],
    )
    assert result["slides"] == 4  # title slide + 2 content slides + closing slide
    assert resolve_in_workspace("deck.pptx").exists()


def test_generate_excel_report_creates_file():
    result = generate_excel_report(
        filename="summary.xlsx",
        sheets={"Revenue": [["Month", "Revenue"], ["Jan", 10000], ["Feb", 12500]]},
    )
    assert result["sheets"] == ["Revenue"]
    assert resolve_in_workspace("summary.xlsx").exists()
