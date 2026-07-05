"""Domain-specific analytics: hospitality (hotel) and digital-marketing KPIs
computed from a workspace dataset, using the standard industry formulas
directly rather than leaving the model to re-derive (and risk fumbling)
things like RevPAR or ROAS from raw columns each time.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from jarvis.skills.base import skill
from jarvis.skills.data_analysis import load_dataframe


def _safe_div(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _require_columns(df: pd.DataFrame, columns: list[str]) -> str | None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        return f"Column(s) {missing} not found. Available columns: {list(df.columns)}"
    return None


def _grouped(df: pd.DataFrame, group_by: str | None, kpi_fn) -> dict[str, Any]:
    result: dict[str, Any] = {"overall": kpi_fn(df)}
    if group_by:
        result["group_by"] = group_by
        result["by_group"] = {str(key): kpi_fn(group_df) for key, group_df in df.groupby(group_by)}
    return result


@skill(
    name="calculate_hospitality_kpis",
    description=(
        "Compute standard hotel/hospitality KPIs from a dataset in the workspace: Occupancy "
        "Rate (rooms sold / rooms available), ADR - Average Daily Rate (room revenue / rooms "
        "sold), RevPAR - Revenue per Available Room (room revenue / rooms available), and total "
        "revenue. Optionally broken down by a grouping column (e.g. property, room type, month). "
        "Use this for hotel/e-commerce-for-hospitality performance questions instead of "
        "hand-deriving the formulas."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the data file (csv/tsv/xlsx/json) in the workspace."},
            "rooms_available_col": {"type": "string", "description": "Column with total rooms available."},
            "rooms_sold_col": {"type": "string", "description": "Column with rooms sold/occupied."},
            "room_revenue_col": {"type": "string", "description": "Column with room revenue."},
            "group_by": {
                "type": "string",
                "description": "Optional column to break the KPIs down by, e.g. 'property' or 'month'.",
            },
        },
        "required": ["path", "rooms_available_col", "rooms_sold_col", "room_revenue_col"],
    },
)
def calculate_hospitality_kpis(
    path: str,
    rooms_available_col: str,
    rooms_sold_col: str,
    room_revenue_col: str,
    group_by: str | None = None,
) -> dict:
    df = load_dataframe(path)
    error = _require_columns(df, [rooms_available_col, rooms_sold_col, room_revenue_col])
    if error:
        return {"error": error}
    if group_by and group_by not in df.columns:
        return {"error": f"group_by column '{group_by}' not found. Available columns: {list(df.columns)}"}

    def _kpis(frame: pd.DataFrame) -> dict[str, float]:
        rooms_available = frame[rooms_available_col].sum()
        rooms_sold = frame[rooms_sold_col].sum()
        revenue = frame[room_revenue_col].sum()
        return {
            "rooms_available": round(float(rooms_available), 2),
            "rooms_sold": round(float(rooms_sold), 2),
            "total_revenue": round(float(revenue), 2),
            "occupancy_rate": round(_safe_div(rooms_sold, rooms_available), 4),
            "adr": round(_safe_div(revenue, rooms_sold), 2),
            "revpar": round(_safe_div(revenue, rooms_available), 2),
        }

    return {"path": path, **_grouped(df, group_by, _kpis)}


@skill(
    name="calculate_marketing_kpis",
    description=(
        "Compute standard digital-marketing KPIs from an ad performance dataset (e.g. a Google "
        "Ads or Meta Ads export) in the workspace: CTR (clicks / impressions), CPC (spend / "
        "clicks), CPA (spend / conversions), conversion rate (conversions / clicks), and — if a "
        "revenue column is given — ROAS (revenue / spend). Optionally broken down by a grouping "
        "column (e.g. campaign, channel, date). Use this instead of hand-deriving ad-metric "
        "formulas."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the data file (csv/tsv/xlsx/json) in the workspace."},
            "impressions_col": {"type": "string"},
            "clicks_col": {"type": "string"},
            "spend_col": {"type": "string"},
            "conversions_col": {"type": "string"},
            "revenue_col": {"type": "string", "description": "Optional revenue column, to also compute ROAS."},
            "group_by": {
                "type": "string",
                "description": "Optional column to break the KPIs down by, e.g. 'campaign' or 'channel'.",
            },
        },
        "required": ["path", "impressions_col", "clicks_col", "spend_col", "conversions_col"],
    },
)
def calculate_marketing_kpis(
    path: str,
    impressions_col: str,
    clicks_col: str,
    spend_col: str,
    conversions_col: str,
    revenue_col: str | None = None,
    group_by: str | None = None,
) -> dict:
    df = load_dataframe(path)
    required = [impressions_col, clicks_col, spend_col, conversions_col] + ([revenue_col] if revenue_col else [])
    error = _require_columns(df, required)
    if error:
        return {"error": error}
    if group_by and group_by not in df.columns:
        return {"error": f"group_by column '{group_by}' not found. Available columns: {list(df.columns)}"}

    def _kpis(frame: pd.DataFrame) -> dict[str, float]:
        impressions = frame[impressions_col].sum()
        clicks = frame[clicks_col].sum()
        spend = frame[spend_col].sum()
        conversions = frame[conversions_col].sum()
        out = {
            "impressions": round(float(impressions), 2),
            "clicks": round(float(clicks), 2),
            "spend": round(float(spend), 2),
            "conversions": round(float(conversions), 2),
            "ctr": round(_safe_div(clicks, impressions), 4),
            "cpc": round(_safe_div(spend, clicks), 2),
            "cpa": round(_safe_div(spend, conversions), 2),
            "conversion_rate": round(_safe_div(conversions, clicks), 4),
        }
        if revenue_col:
            revenue = frame[revenue_col].sum()
            out["revenue"] = round(float(revenue), 2)
            out["roas"] = round(_safe_div(revenue, spend), 3)
        return out

    return {"path": path, **_grouped(df, group_by, _kpis)}
