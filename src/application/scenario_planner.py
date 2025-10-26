"""Scenario planning utilities for Idiot Index analytics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import cast

import pandas as pd

from src.core import (
    HealthSummary,
    MetricConfig,
    compute_health_scores,
    compute_metrics,
    format_for_display,
    summarise_health,
)
from src.extensions.manager import ExtensionManager, get_extension_manager
from src.infrastructure.observability import ObservabilityRegistry, bootstrap_observability

_INPUT_COLUMNS: tuple[str, ...] = (
    "industry_code",
    "industry_name",
    "year",
    "gross_output",
    "materials_cost",
    "intermediate_inputs",
    "value_added",
)


@dataclass(frozen=True)
class ScenarioAdjustment:
    """Describe a percentage-based adjustment applied to one or more industries."""

    industry_codes: Sequence[str] | None = None
    gross_output_delta_pct: float = 0.0
    materials_cost_delta_pct: float = 0.0
    value_added_delta_pct: float | None = None
    intermediate_inputs_delta_pct: float | None = None


@dataclass(frozen=True)
class ScenarioSummary:
    """Aggregate summary of baseline/scenario totals and averages."""

    gross_output_total: float | None
    materials_cost_total: float | None
    value_added_total: float | None
    idiot_index_avg: float | None
    resilience_score_avg: float | None
    materials_dependency_ratio_avg: float | None
    shock_sensitivity_index_avg: float | None
    health_score_avg: float | None


@dataclass(frozen=True)
class ScenarioResult:
    """Container describing baseline, scenario, and delta views."""

    baseline: pd.DataFrame
    scenario: pd.DataFrame
    deltas: pd.DataFrame
    baseline_summary: ScenarioSummary
    scenario_summary: ScenarioSummary
    delta_summary: Mapping[str, float | None]
    baseline_health_summary: HealthSummary | None = None
    scenario_health_summary: HealthSummary | None = None


@dataclass
class ScenarioPlanner:
    """Compute scenario deltas for Idiot Index datasets."""

    metric_config: MetricConfig = field(default_factory=lambda: MetricConfig(use_cache=False))
    extension_manager: ExtensionManager | None = None
    observability: ObservabilityRegistry | None = None

    def __post_init__(self) -> None:
        if self.extension_manager is None:
            self.extension_manager = get_extension_manager()
        if self.observability is None:
            self.observability = bootstrap_observability()
        if self.extension_manager is not None and self.observability is not None:
            self.extension_manager.apply_instrumentation_extensions(self.observability)

    def plan(
        self,
        base: pd.DataFrame,
        adjustments: Sequence[ScenarioAdjustment],
    ) -> ScenarioResult:
        if base.empty:
            raise ValueError("Base dataframe cannot be empty for scenario planning.")

        attributes = {
            "records": int(base.shape[0]),
            "adjustments": len(adjustments),
        }
        observability_cm = (
            self.observability.operation("service.scenario.plan", attributes=attributes)
            if self.observability is not None
            else nullcontext()
        )

        with observability_cm:
            raw_base = _extract_inputs(base)
            raw_base.attrs.update(base.attrs)

            baseline_metrics = _compute(raw_base, self.metric_config)
            adjusted_inputs = raw_base.copy()

            for adjustment in adjustments:
                _apply_adjustment(adjusted_inputs, adjustment)

            scenario_metrics = _compute(adjusted_inputs, self.metric_config)

            baseline_metrics = compute_health_scores(format_for_display(baseline_metrics))
            scenario_metrics = compute_health_scores(format_for_display(scenario_metrics))

            deltas = _calculate_deltas(baseline_metrics, scenario_metrics)

            baseline_summary = _summarise(baseline_metrics)
            scenario_summary = _summarise(scenario_metrics)
            delta_summary = {
                key: _difference(scenario_summary, baseline_summary, key)
                for key in baseline_summary.__dict__.keys()
            }

            baseline_health_summary = summarise_health(baseline_metrics)
            scenario_health_summary = summarise_health(scenario_metrics)

            result = ScenarioResult(
                baseline=baseline_metrics,
                scenario=scenario_metrics,
                deltas=deltas,
                baseline_summary=baseline_summary,
                scenario_summary=scenario_summary,
                delta_summary=delta_summary,
                baseline_health_summary=baseline_health_summary,
                scenario_health_summary=scenario_health_summary,
            )

            if self.extension_manager is not None:
                contributions = self.extension_manager.apply_scenario_extensions(result)
                if contributions.metadata:
                    for frame in (result.baseline, result.scenario, result.deltas):
                        extensions_meta = frame.attrs.setdefault("extensions", {})
                        extensions_meta.update(contributions.metadata)
                if contributions.notes:
                    notes = list(result.baseline.attrs.get("extension_notes", []))
                    notes.extend(contributions.notes)
                    result.baseline.attrs["extension_notes"] = notes

            return result


def plan_scenario(
    base: pd.DataFrame,
    adjustments: Sequence[ScenarioAdjustment],
    *,
    metric_config: MetricConfig | None = None,
) -> ScenarioResult:
    """Convenience wrapper around :class:`ScenarioPlanner`."""

    planner = ScenarioPlanner(metric_config=metric_config or MetricConfig(use_cache=False))
    return planner.plan(base, adjustments)


def _extract_inputs(df: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in _INPUT_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Dataframe missing required columns: {', '.join(missing)}")
    return df.loc[:, _INPUT_COLUMNS].copy()


def _apply_adjustment(df: pd.DataFrame, adjustment: ScenarioAdjustment) -> None:
    if not any(
        [
            adjustment.gross_output_delta_pct,
            adjustment.materials_cost_delta_pct,
            adjustment.value_added_delta_pct,
            adjustment.intermediate_inputs_delta_pct,
        ]
    ):
        return

    mask = (
        df["industry_code"].isin(adjustment.industry_codes)
        if adjustment.industry_codes
        else pd.Series(True, index=df.index)
    )

    def _scale(column: str, delta_pct: float | None) -> None:
        if delta_pct is None or delta_pct == 0.0:
            return
        if column not in df.columns:
            return
        multiplier = 1.0 + (delta_pct / 100.0)
        df.loc[mask, column] = df.loc[mask, column].astype("float64") * multiplier

    _scale("gross_output", adjustment.gross_output_delta_pct)
    _scale("materials_cost", adjustment.materials_cost_delta_pct)
    _scale("value_added", adjustment.value_added_delta_pct)
    _scale("intermediate_inputs", adjustment.intermediate_inputs_delta_pct)


def _compute(df: pd.DataFrame, metric_config: MetricConfig) -> pd.DataFrame:
    return compute_metrics(df, config=metric_config)


def _calculate_deltas(baseline: pd.DataFrame, scenario: pd.DataFrame) -> pd.DataFrame:
    numeric_columns = [
        "gross_output",
        "materials_cost",
        "intermediate_inputs",
        "value_added",
        "idiot_index",
        "value_added_pct",
        "materials_share_pct",
        "resilience_score",
        "materials_dependency_ratio",
        "shock_sensitivity_index",
        "health_score",
    ]

    baseline_indexed = baseline.set_index("industry_code")
    scenario_indexed = scenario.set_index("industry_code")

    delta_numeric = scenario_indexed[numeric_columns] - baseline_indexed[numeric_columns]
    delta_numeric.insert(0, "industry_name", scenario_indexed["industry_name"])

    return delta_numeric.reset_index()


def _summarise(df: pd.DataFrame) -> ScenarioSummary:
    return ScenarioSummary(
        gross_output_total=(
            float(df["gross_output"].sum(skipna=True)) if "gross_output" in df else None
        ),
        materials_cost_total=(
            float(df.get("materials_cost", pd.Series(dtype="float64")).sum(skipna=True))
            if "materials_cost" in df
            else None
        ),
        value_added_total=(
            float(df["value_added"].sum(skipna=True)) if "value_added" in df else None
        ),
        idiot_index_avg=float(df["idiot_index"].mean(skipna=True)) if "idiot_index" in df else None,
        resilience_score_avg=(
            float(df.get("resilience_score", pd.Series(dtype="float64")).mean(skipna=True))
            if "resilience_score" in df
            else None
        ),
        materials_dependency_ratio_avg=(
            float(
                df.get("materials_dependency_ratio", pd.Series(dtype="float64")).mean(skipna=True)
            )
            if "materials_dependency_ratio" in df
            else None
        ),
        shock_sensitivity_index_avg=(
            float(df.get("shock_sensitivity_index", pd.Series(dtype="float64")).mean(skipna=True))
            if "shock_sensitivity_index" in df
            else None
        ),
        health_score_avg=(
            float(df.get("health_score", pd.Series(dtype="float64")).mean(skipna=True))
            if "health_score" in df
            else None
        ),
    )


def _difference(
    scenario_summary: ScenarioSummary, baseline_summary: ScenarioSummary, field: str
) -> float | None:
    scenario_value = cast(float | None, getattr(scenario_summary, field))
    baseline_value = cast(float | None, getattr(baseline_summary, field))
    if scenario_value is None or baseline_value is None:
        return None
    return scenario_value - baseline_value


__all__ = [
    "ScenarioAdjustment",
    "ScenarioPlanner",
    "ScenarioResult",
    "ScenarioSummary",
    "plan_scenario",
]
