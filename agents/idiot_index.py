"""Agent-facing wrappers around the Idiot Index application service.

The functions in this module delegate to :mod:`src.application` to perform data
retrieval, normalisation, metric computation, and leaderboard derivation. The
agent layer focuses on request validation, schema metadata, and logging so
automation clients receive stable, well-documented responses without depending
on Streamlit UI components.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence

from src.application import DataSource, evaluate_idiot_index
from src.application.idiot_index_service import IndustryMetrics, LoggerHooks
from src.core import HealthSummary, SecurityUtils
from src.infrastructure import log_data_processing, log_performance

from .toolkit import tool


@dataclass
class IdiotIndexRequest:
    """Input payload accepted by :func:`compute_idiot_index_summary`.

    The dataclass performs validation eagerly so automated callers receive
    immediate feedback on invalid parameters before any network traffic occurs.
    Search strings are sanitised using :class:`~src.core.SecurityUtils` to
    neutralise potentially unsafe patterns.
    """

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
    idiot_index: float = field(
        metadata={"description": "Computed Idiot Index value (may be NaN if unavailable)."}
    )
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
    health_score_average: float | None = field(
        default=None,
        metadata={"description": "Composite health score (0-100) for the filtered dataset."},
    )
    health_risk_band: str | None = field(
        default=None,
        metadata={"description": "Risk band label for the filtered dataset (excellent/healthy/watch/critical)."},
    )


def _to_snapshot(entry: IndustryMetrics) -> IndustrySnapshot:
    idiot_index = float(entry.idiot_index) if entry.idiot_index is not None else float("nan")
    return IndustrySnapshot(
        code=entry.industry_code,
        name=entry.industry_name,
        idiot_index=idiot_index,
        value_added_pct=entry.value_added_pct,
    )


def _health_overview(summary: HealthSummary | None) -> tuple[float | None, str | None]:
    if summary is None:
        return None, None
    return summary.overall.average_health_score, summary.overall.risk_band


@tool(
    name="compute_idiot_index_summary",
    description="Compute Idiot Index metrics and leaderboard for a given year and data source.",
)
def compute_idiot_index_summary(payload: IdiotIndexRequest) -> IdiotIndexResponse:
    """Return a lightweight summary ready for conversational agents."""

    summary = evaluate_idiot_index(
        year=payload.year,
        source=payload.source,
        search=payload.search,
        top_n=payload.top_n,
        logger_hooks=LoggerHooks(
            log_performance=log_performance,
            log_data_processing=lambda operation, count: log_data_processing(
                operation, count
            ),
        ),
    )

    top_industries = [_to_snapshot(entry) for entry in summary.leaderboard]
    health_score, health_band = _health_overview(summary.health_summary_filtered)

    return IdiotIndexResponse(
        rows_evaluated=len(summary.dataframe_filtered),
        idiot_index_average=summary.average_idiot_index,
        top_industries=top_industries,
        notes=list(summary.notes),
        health_score_average=health_score,
        health_risk_band=health_band,
    )


__all__ = [
    "DataSource",
    "IdiotIndexRequest",
    "IdiotIndexResponse",
    "IndustrySnapshot",
    "compute_idiot_index_summary",
]
