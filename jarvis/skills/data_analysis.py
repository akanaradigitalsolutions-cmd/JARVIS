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

# Same navy/teal palette as the PDF/PPTX generators (jarvis/skills/documents.py)
# so a chart embedded in a report looks like it belongs to the same brand
# instead of matplotlib's default blue/orange color cycle.
_NAVY = "#141B2E"
_ACCENT = "#2EC4B6"
_MUTED = "#6B7A8F"
_PALETTE = ["#2EC4B6", "#141B2E", "#E4A94F", "#8895A7", "#7C6FDC"]


def _apply_brand_style(ax, fig) -> None:
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(_MUTED)
    ax.spines["bottom"].set_color(_MUTED)
    ax.tick_params(colors=_MUTED, labelsize=9)
    ax.yaxis.grid(True, color="#E4E9F0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.xaxis.label.set_color(_MUTED)
    ax.yaxis.label.set_color(_MUTED)


def load_dataframe(path: str, sheet_name: str | None = None) -> pd.DataFrame:
    """Shared by every skill that reads tabular data (this module and
    business_metrics.py) so file-type support only needs to live in one
    place."""
    resolved = resolve_in_workspace(path)
    if not resolved.exists():
        raise FileNotFoundError(f"'{path}' not found in the workspace.")
    suffix = resolved.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(resolved)
    if suffix == ".tsv":
        return pd.read_csv(resolved, sep="\t")
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(resolved, sheet_name=sheet_name or 0)
    if suffix == ".json":
        return pd.read_json(resolved)
    raise ValueError(f"Unsupported data file type: {suffix}. Use .csv, .tsv, .xlsx, .xls, or .json.")


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
    df = load_dataframe(path, sheet_name)
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

    df = load_dataframe(path)
    y_cols = y or [c for c in df.select_dtypes(include="number").columns][:1]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    if chart_type == "line":
        df.plot(x=x, y=y_cols, kind="line", ax=ax, color=_PALETTE, linewidth=2.4)
    elif chart_type == "bar":
        df.plot(x=x, y=y_cols, kind="bar", ax=ax, color=_PALETTE, width=0.7, edgecolor="none")
    elif chart_type == "scatter":
        ax.scatter(df[x], df[y_cols[0]], color=_ACCENT, edgecolor=_NAVY, linewidth=0.5, s=50)
        ax.set_xlabel(x)
        ax.set_ylabel(y_cols[0])
    elif chart_type == "pie":
        df.set_index(x)[y_cols[0]].plot(
            kind="pie", ax=ax, autopct="%1.1f%%", colors=_PALETTE,
            wedgeprops={"edgecolor": "white", "linewidth": 1.5},
            textprops={"color": _NAVY, "fontsize": 9},
        )
        ax.set_ylabel("")
    elif chart_type == "hist":
        df[y_cols[0]].plot(kind="hist", ax=ax, color=_ACCENT, edgecolor="white")

    if chart_type != "pie":
        _apply_brand_style(ax, fig)
        if ax.get_legend() is not None:
            ax.legend(frameon=False, labelcolor=_NAVY)
    if title:
        ax.set_title(title, color=_NAVY, fontsize=13, fontweight="bold", pad=12)
    fig.tight_layout()

    if not output_filename.lower().endswith(".png"):
        output_filename += ".png"
    out_path = resolve_in_workspace(output_filename)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)

    return {"path": output_filename}
