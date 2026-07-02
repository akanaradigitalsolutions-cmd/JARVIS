from jarvis.skills.data_analysis import analyze_dataset, generate_chart
from jarvis.skills.filesystem import write_text_file, resolve_in_workspace

CSV = "month,revenue,bookings\nJan,10000,120\nFeb,12500,140\nMar,9800,110\n"


def _write_csv():
    write_text_file("sales.csv", CSV, overwrite=True)


def test_analyze_dataset_returns_summary():
    _write_csv()
    result = analyze_dataset("sales.csv")
    assert result["rows"] == 3
    assert set(result["columns"]) == {"month", "revenue", "bookings"}
    assert "revenue" in result["numeric_summary"]
    assert result["missing_values"] == {}


def test_generate_chart_writes_png():
    _write_csv()
    result = generate_chart(
        path="sales.csv",
        chart_type="bar",
        output_filename="revenue_chart.png",
        x="month",
        y=["revenue"],
        title="Monthly revenue",
    )
    assert result["path"] == "revenue_chart.png"
    assert resolve_in_workspace("revenue_chart.png").exists()


def test_generate_chart_rejects_bad_type():
    _write_csv()
    result = generate_chart(path="sales.csv", chart_type="not_a_type", output_filename="x.png")
    assert "error" in result
