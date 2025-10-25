"""Pydantic schemas and conversion helpers for the headless API."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any, Literal, cast

import numpy as np
import pandas as pd

from pydantic import BaseModel, ConfigDict, Field
from src.application import (
    DataSource,
    IdiotIndexSummary,
    IndustryMetrics,
    ScenarioAdjustment,
    ScenarioResult,
    ScenarioSummary,
)


class DatasetRecord(BaseModel):
    """Record representing a single industry observation."""

    industry_code: str = Field(..., description="NAICS industry code or similar identifier.")
    industry_name: str = Field(..., description="Human readable industry name.")
    year: int = Field(..., ge=0, description="Calendar year for the record.")
    gross_output: float = Field(..., description="Gross output value for the industry.")
    materials_cost: float | None = Field(
        default=None,
        description="Materials cost or intermediate input expenditure (optional).",
    )
    intermediate_inputs: float | None = Field(
        default=None,
        description="Intermediate inputs value when materials cost is unavailable.",
    )
    value_added: float | None = Field(
        default=None,
        description="Value added metric; optional when not supplied by the data source.",
    )

    model_config = ConfigDict(extra="allow")


class HealthComponentModel(BaseModel):
    name: str
    status: Literal["pass", "warn", "fail"]
    summary: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: Literal["pass", "warn", "fail"]
    service: str = Field(default="idiot-index-api")
    version: str
    checked_at: datetime
    trace_id: str | None = Field(
        default=None,
        description="Active trace identifier to correlate logs and metrics.",
    )
    components: list[HealthComponentModel] = Field(
        default_factory=list,
        description="Detailed component-level health signals.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured metadata describing configuration and observability state.",
    )
    telemetry: dict[str, Any] = Field(
        default_factory=dict,
        description="Shortcut field mirroring metadata['telemetry'] for backward compatibility.",
    )


class MetaSourcesResponse(BaseModel):
    sources: list[str]


class EvaluateFilters(BaseModel):
    search: str | None = Field(default=None, description="Search filter applied to the dataset.")
    top_n: int = Field(default=5, ge=1, description="Number of leaderboard entries requested.")


class LeaderboardEntry(BaseModel):
    industry_code: str
    industry_name: str
    idiot_index: float | None = None
    value_added_pct: float | None = None
    materials_share_pct: float | None = None
    gross_output: float | None = None
    value_added: float | None = None


class EvaluateDataset(BaseModel):
    full: list[dict[str, Any]]
    filtered: list[dict[str, Any]]


class EvaluateResponse(BaseModel):
    source: DataSource
    year: int
    filters: EvaluateFilters
    average_idiot_index: float | None = None
    notes: list[str] = Field(default_factory=list)
    leaderboard: list[LeaderboardEntry]
    dataset: EvaluateDataset
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class EvaluateRequest(BaseModel):
    """Request payload for the /evaluate endpoint."""

    source: DataSource = Field(default=DataSource.SAMPLE)
    year: int = Field(..., ge=1900, description="Year to evaluate (matching source availability).")
    search: str | None = Field(default=None, description="Optional search filter.")
    top_n: int = Field(default=5, ge=1, le=100, description="Leaderboard size to compute.")
    records: list[DatasetRecord] | None = Field(
        default=None,
        description=(
            "Optional inline dataset. When provided, the service skips remote fetching and "
            "uses the supplied records."
        ),
    )
    use_cache: bool | None = Field(
        default=None,
        description="Override cache usage when true/false; defaults to service configuration.",
    )

    model_config = ConfigDict(use_enum_values=True)


class ScenarioAdjustmentModel(BaseModel):
    industry_codes: list[str] | None = Field(
        default=None,
        description="Optional list of industry codes to target; applies to all when omitted.",
    )
    gross_output_delta_pct: float = Field(default=0.0)
    materials_cost_delta_pct: float = Field(default=0.0)
    value_added_delta_pct: float | None = Field(default=None)
    intermediate_inputs_delta_pct: float | None = Field(default=None)


class ScenarioRequest(BaseModel):
    base_records: list[DatasetRecord] = Field(
        ..., description="Baseline dataset records including required metric columns."
    )
    adjustments: list[ScenarioAdjustmentModel] = Field(
        default_factory=list, description="Scenario adjustments to apply."
    )
    use_cache: bool | None = Field(
        default=None,
        description="Optional override for metric caching during scenario computation.",
    )


class ScenarioSummaryModel(BaseModel):
    gross_output_total: float | None
    materials_cost_total: float | None
    value_added_total: float | None
    idiot_index_avg: float | None
    resilience_score_avg: float | None
    materials_dependency_ratio_avg: float | None
    shock_sensitivity_index_avg: float | None


class ScenarioResponse(BaseModel):
    baseline_summary: ScenarioSummaryModel
    scenario_summary: ScenarioSummaryModel
    delta_summary: dict[str, float | None]
    baseline: list[dict[str, Any]]
    scenario: list[dict[str, Any]]
    deltas: list[dict[str, Any]]
    metadata: dict[str, Any] = Field(default_factory=dict)


def records_to_dataframe(records: Sequence[DatasetRecord]) -> pd.DataFrame:
    """Convert validated dataset records into a pandas DataFrame."""

    if not records:
        raise ValueError("At least one record is required to build a dataframe.")

    payload = [record.model_dump(mode="python", exclude_none=False) for record in records]
    return pd.DataFrame(payload)


def adjustments_to_domain(
    adjustments: Iterable[ScenarioAdjustmentModel],
) -> list[ScenarioAdjustment]:
    """Convert API adjustment models into domain dataclasses."""

    converted: list[ScenarioAdjustment] = []
    for item in adjustments:
        converted.append(
            ScenarioAdjustment(
                industry_codes=item.industry_codes,
                gross_output_delta_pct=item.gross_output_delta_pct,
                materials_cost_delta_pct=item.materials_cost_delta_pct,
                value_added_delta_pct=item.value_added_delta_pct,
                intermediate_inputs_delta_pct=item.intermediate_inputs_delta_pct,
            )
        )
    return converted


def build_leaderboard(entries: Sequence[IndustryMetrics]) -> list[LeaderboardEntry]:
    return [
        LeaderboardEntry(
            industry_code=entry.industry_code,
            industry_name=entry.industry_name,
            idiot_index=entry.idiot_index,
            value_added_pct=entry.value_added_pct,
            materials_share_pct=entry.materials_share_pct,
            gross_output=entry.gross_output,
            value_added=entry.value_added,
        )
        for entry in entries
    ]


def scenario_summary_to_model(summary: ScenarioSummary) -> ScenarioSummaryModel:
    return ScenarioSummaryModel(**summary.__dict__)


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Return JSON-serialisable records for a dataframe."""

    sanitized = df.copy()
    sanitized = sanitized.where(pd.notna(sanitized), None)

    records: list[dict[str, Any]] = []
    for row in sanitized.to_dict(orient="records"):
        processed: dict[str, Any] = {}
        for key, value in row.items():
            processed[key] = _coerce_json_value(value)
        records.append(processed)
    return records


def summary_to_response(
    summary: IdiotIndexSummary,
    *,
    source: DataSource,
    year: int,
    filters: EvaluateFilters,
) -> EvaluateResponse:
    """Build an EvaluateResponse from the domain summary."""

    metadata = _sanitize_metadata(summary.dataframe_full.attrs)
    return EvaluateResponse(
        source=source,
        year=year,
        filters=filters,
        average_idiot_index=summary.average_idiot_index,
        notes=list(summary.notes),
        leaderboard=build_leaderboard(summary.leaderboard),
        dataset=EvaluateDataset(
            full=dataframe_to_records(summary.dataframe_full),
            filtered=dataframe_to_records(summary.dataframe_filtered),
        ),
        metadata=metadata,
    )


def scenario_to_response(result: ScenarioResult) -> ScenarioResponse:
    metadata = _sanitize_metadata(result.baseline.attrs)
    return ScenarioResponse(
        baseline_summary=scenario_summary_to_model(result.baseline_summary),
        scenario_summary=scenario_summary_to_model(result.scenario_summary),
        delta_summary=dict(result.delta_summary),
        baseline=dataframe_to_records(result.baseline),
        scenario=dataframe_to_records(result.scenario),
        deltas=dataframe_to_records(result.deltas),
        metadata=metadata,
    )


def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}

    try:
        encoded = json.dumps(metadata, default=_coerce_json_value)
        return cast(dict[str, Any], json.loads(encoded))
    except TypeError:
        fallback: dict[str, Any] = {}
        for key, value in metadata.items():
            fallback[key] = _coerce_json_value(value)
        return fallback


def _coerce_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
