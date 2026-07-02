"""Data analysis skills: load CSV/Excel data, summarize it, and generate
charts. Chart images are saved into the workspace so they can be embedded
into PDF reports or presentations via documents.py.
"""

from __future__ import annotations

from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless: no display available on server/CLI

import matplotlib.pyplot as plt
import pandas as pd

from jarvis.skills.base import skill
from jarvis.skills.filesystem import resolve_in_workspace

_SUPPORTED_CHARTS = {"line", "bar", "scatter", "pie", "hist"}


def _load_dataframe(path: str, sheet_name: str | None = None) -> pd.DataFrame:
    resolved = resolve_in_workspace(path)
    if not resolved.exists():
        raise FileNotFoundError(f"'{path}' not found in the workspace.")
    suffix = resolved.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(resolved)
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(resolved, sheet_name=sheet_name or 0)
    if suffix == ".json":
        return pd.read_json(resolved)
    raise ValueError(f"Unsupported data file type: {suffix}. Use .csv, .xlsx, .xls, or .json.")


@skill(
    name="analyze_dataset",
    description=(
        "Load a CSV/Excel/JSON file from the workspace and return a statistical summary: "
        "shape, columns, data types, missing values, and descriptive statistics (mean, min, "
        "max, std, etc. for numeric columns). Use this before making charts or reports so you "
        "understand the data first."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the data file, relative to the workspace."},
            "sheet_name": {"type": "string", "description": "Sheet name, for Excel files with multiple sheets."},
        },
        "required": ["path"],
    },
)
def analyze_dataset(path: str, sheet_name: str | None = None) -> dict:
    df = _load_dataframe(path, sheet_name)
    numeric_summary = df.describe(include="number").round(3).to_dict()
    return {
        "path": path,
        "rows": int(df.shape[0]),
        "columns": list(df.columns.astype(str)),
        "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
        "missing_values": {str(c): int(v) for c, v in df.isna().sum().items() if v > 0},
        "numeric_summary": numeric_summary,
        "preview": df.head(10).to_dict(orient="records"),
    }


@skill(
    name="generate_chart",
    description=(
        "Generate a chart image (PNG) from a data file in the workspace and save it there. "
        "Returns the saved image path, which can then be embedded into a PDF report or "
        "presentation slide."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the source data file, relative to the workspace."},
            "chart_type": {"type": "string", "enum": sorted(_SUPPORTED_CHARTS)},
            "x": {"type": "string", "description": "Column to use for the x-axis (or labels, for pie charts)."},
            "y": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Column(s) to plot on the y-axis. For pie/hist, a single column.",
            },
            "title": {"type": "string"},
            "output_filename": {"type": "string", "description": "Filename for the saved PNG, e.g. 'revenue_chart.png'."},
        },
        "required": ["path", "chart_type", "output_filename"],
    },
)
def generate_chart(
    path: str,
    chart_type: str,
    output_filename: str,
    x: str | None = None,
    y: list[str] | None = None,
    title: str = "",
) -> dict:
    if chart_type not in _SUPPORTED_CHARTS:
        return {"error": f"Unsupported chart_type '{chart_type}'. Use one of {sorted(_SUPPORTED_CHARTS)}."}

    df = _load_dataframe(path)
    y_cols = y or [c for c in df.select_dtypes(include="number").columns][:1]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    if chart_type == "line":
        df.plot(x=x, y=y_cols, kind="line", ax=ax)
    elif chart_type == "bar":
        df.plot(x=x, y=y_cols, kind="bar", ax=ax)
    elif chart_type == "scatter":
        ax.scatter(df[x], df[y_cols[0]])
        ax.set_xlabel(x)
        ax.set_ylabel(y_cols[0])
    elif chart_type == "pie":
        df.set_index(x)[y_cols[0]].plot(kind="pie", ax=ax, autopct="%1.1f%%")
        ax.set_ylabel("")
    elif chart_type == "hist":
        df[y_cols[0]].plot(kind="hist", ax=ax)

    if title:
        ax.set_title(title)
    fig.tight_layout()

    if not output_filename.lower().endswith(".png"):
        output_filename += ".png"
    out_path = resolve_in_workspace(output_filename)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

    return {"path": output_filename}
