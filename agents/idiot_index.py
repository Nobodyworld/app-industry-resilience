"""Agent-facing helpers for computing Idiot Index summaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Sequence

import pandas as pd

from src.adapters import fetch_asm_manufacturing, fetch_go_ii_by_industry
from src.core import (
    SecurityUtils,
    compute_metrics,
    format_for_display,
    load_config,
    normalize_columns,
)
from src.infrastructure import log_data_processing, log_performance

from .toolkit import tool

_SAMPLE_DATA = Path("data/sample_industries.csv")


class DataSource(str, Enum):
    """Available data sources for agent requests."""

    SAMPLE = "sample"
    BEA = "bea"
    CENSUS = "census"


@dataclass
class IdiotIndexRequest:
    """Input payload accepted by :func:`compute_idiot_index_summary`."""

    year: int = field(metadata={"description": "Calendar year to evaluate."})
    source: DataSource = field(
        default=DataSource.SAMPLE,
        metadata={"description": "Which data source to query: sample, bea, or census."},
    )
    search: str | None = field(
        default=None,
        metadata={
            "description": "Optional case-insensitive filter applied to industry name or code.",
        },
    )
    top_n: int = field(
        default=5,
        metadata={
            "description": "How many industries to include in the leaderboard.",
            "minimum": 1,
            "maximum": 25,
        },
    )

    def __post_init__(self) -> None:
        if not isinstance(self.year, int) or not (1997 <= self.year <= 2100):
            raise ValueError("year must be between 1997 and 2100.")
        if not isinstance(self.top_n, int) or not (1 <= self.top_n <= 25):
            raise ValueError("top_n must be an integer between 1 and 25.")
        if not isinstance(self.source, DataSource):
            raise ValueError("source must be a DataSource enum member.")
        if self.search:
            sanitized = SecurityUtils.sanitize_string_input(self.search)
            self.search = sanitized or None


@dataclass
class IndustrySnapshot:
    """Slim representation of an industry's Idiot Index position."""

    code: str = field(metadata={"description": "NAICS code for the industry."})
    name: str = field(metadata={"description": "Display label for the industry."})
    idiot_index: float = field(metadata={"description": "Computed Idiot Index value."})
    value_added_pct: float | None = field(
        default=None,
        metadata={"description": "Share of value added as a percentage if available."},
    )


@dataclass
class IdiotIndexResponse:
    """Response payload returned by :func:`compute_idiot_index_summary`."""

    rows_evaluated: int = field(
        metadata={"description": "Number of rows considered after filtering."}
    )
    idiot_index_average: float | None = field(
        default=None,
        metadata={"description": "Average Idiot Index across the filtered dataset."},
    )
    top_industries: List[IndustrySnapshot] = field(
        default_factory=list,
        metadata={"description": "Leaderboard of industries sorted by Idiot Index."},
    )
    notes: Sequence[str] = field(
        default_factory=list,
        metadata={"description": "Metadata notes returned from upstream services when available."},
    )


def _load_dataset(payload: IdiotIndexRequest) -> pd.DataFrame:
    config = load_config()
    if payload.source is DataSource.SAMPLE:
        frame = pd.read_csv(_SAMPLE_DATA)
    elif payload.source is DataSource.BEA:
        if not config.bea_api_key:
            raise ValueError("BEA API key is required but missing from configuration.")
        frame = fetch_go_ii_by_industry(api_key=config.bea_api_key, year=payload.year)
    elif payload.source is DataSource.CENSUS:
        if not config.census_api_key:
            raise ValueError("Census API key is required but missing from configuration.")
        frame = fetch_asm_manufacturing(api_key=config.census_api_key, year=payload.year)
    else:  # pragma: no cover - Enum prevents reaching this branch
        raise ValueError(f"Unsupported data source {payload.source}.")

    log_data_processing("agent_dataset_loaded", len(frame))
    return frame


def _filter_dataset(frame: pd.DataFrame, payload: IdiotIndexRequest) -> pd.DataFrame:
    sanitized = payload.search
    if not sanitized:
        return frame
    lowered = sanitized.lower()
    mask = frame["industry_name"].str.lower().str.contains(lowered) | frame[
        "industry_code"
    ].str.lower().str.contains(lowered)
    return frame.loc[mask].copy()


@tool(
    name="compute_idiot_index_summary",
    description="Compute Idiot Index metrics and leaderboard for a given year and data source.",
)
def compute_idiot_index_summary(payload: IdiotIndexRequest) -> IdiotIndexResponse:
    """Return a lightweight summary ready for conversational agents."""

    start = pd.Timestamp.utcnow()
    raw_frame = _load_dataset(payload)
    normalized = normalize_columns(raw_frame)
    metrics = compute_metrics(normalized)
    display = format_for_display(metrics)
    filtered = _filter_dataset(display, payload)

    ranked = (
        filtered.sort_values("idiot_index", ascending=False)
        .head(payload.top_n)
        .itertuples()
    )
    top_industries = [
        IndustrySnapshot(
            code=row.industry_code,
            name=row.industry_name,
            idiot_index=float(row.idiot_index),
            value_added_pct=float(row.value_added_pct)
            if pd.notna(row.value_added_pct)
            else None,
        )
        for row in ranked
    ]

    response = IdiotIndexResponse(
        rows_evaluated=len(filtered),
        idiot_index_average=float(filtered["idiot_index"].mean())
        if not filtered.empty
        else None,
        top_industries=top_industries,
        notes=list(filtered.attrs.get("bea_metadata", {}).get("notes", [])),
    )
    log_performance("agent_compute_idiot_index", (pd.Timestamp.utcnow() - start).total_seconds())
    return response


__all__ = [
    "DataSource",
    "IdiotIndexRequest",
    "IdiotIndexResponse",
    "IndustrySnapshot",
    "compute_idiot_index_summary",
]
