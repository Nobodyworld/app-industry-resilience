"""Release-aware rolling backtests for observed public-data signals."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.core.public_data import EraWindow, split_periods_into_eras


@dataclass(frozen=True)
class BacktestMetricSummary:
    """Error metrics for a chronological baseline comparison."""

    mae: float | None
    rmse: float | None
    mape: float | None
    directional_accuracy: float | None
    sample_count: int
    excluded_row_count: int
    excluded_reasons: dict[str, int]


@dataclass(frozen=True)
class BacktestResult:
    """Persistable rolling backtest output for one target field."""

    training_period: tuple[str, str]
    prediction_period: tuple[str, str]
    source_release_dates: tuple[str, ...]
    target_field: str
    baseline_config: dict[str, Any]
    predictions: tuple[dict[str, Any], ...]
    actual_observations: tuple[dict[str, Any], ...]
    metrics: BacktestMetricSummary
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "training_period": list(self.training_period),
            "prediction_period": list(self.prediction_period),
            "source_release_dates": list(self.source_release_dates),
            "target_field": self.target_field,
            "baseline_config": self.baseline_config,
            "predictions": list(self.predictions),
            "actual_observations": list(self.actual_observations),
            "metrics": self.metrics.__dict__,
            "limitations": list(self.limitations),
        }


class BacktestPlanner:
    """Run a chronological previous-period baseline over observed values."""

    def plan(
        self,
        frame: pd.DataFrame,
        *,
        target_field: str,
        date_field: str = "observation_date",
        entity_field: str = "series_id",
        release_field: str = "release_period",
        sections: int = 3,
    ) -> BacktestResult:
        if frame.empty:
            raise ValueError("Backtest dataframe cannot be empty.")
        required = {target_field, date_field, entity_field, release_field}
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise ValueError(f"Backtest dataframe missing required columns: {', '.join(missing)}")

        work = frame.copy()
        work["_period"] = work[date_field].astype(str)
        work["_target"] = pd.to_numeric(work[target_field], errors="coerce")
        work.sort_values([entity_field, "_period"], inplace=True)

        eras = split_periods_into_eras(work["_period"], sections=sections)
        if len(eras) < 2:
            raise ValueError("At least two eras are required for a rolling backtest.")

        training_era = _combine_eras(eras[:-1], label="training")
        prediction_era = eras[-1]
        prediction_periods = set(prediction_era.periods)
        training_periods = set(training_era.periods)

        predictions: list[dict[str, Any]] = []
        actuals: list[dict[str, Any]] = []
        excluded_reasons: dict[str, int] = {}

        for _, row in work[work["_period"].isin(prediction_periods)].iterrows():
            entity = str(row[entity_field])
            actual = row["_target"]
            if pd.isna(actual):
                _count_exclusion(excluded_reasons, "missing_actual")
                continue
            history = work[
                (work[entity_field].astype(str) == entity)
                & (work["_period"].isin(training_periods))
                & work["_target"].notna()
            ].sort_values("_period")
            if history.empty:
                _count_exclusion(excluded_reasons, "missing_training_history")
                continue
            baseline = float(history.iloc[-1]["_target"])
            actual_value = float(actual)
            period = str(row["_period"])
            release_period = str(row[release_field])
            predictions.append(
                {
                    entity_field: entity,
                    "prediction_period": period,
                    "release_period": release_period,
                    "predicted_value": baseline,
                    "baseline_source_period": str(history.iloc[-1]["_period"]),
                    "baseline_method": "previous_period_observed_value",
                }
            )
            actuals.append(
                {
                    entity_field: entity,
                    "prediction_period": period,
                    "release_period": release_period,
                    "actual_value": actual_value,
                }
            )

        metrics = _compute_metrics(predictions, actuals, excluded_reasons)
        release_dates = tuple(sorted(str(value) for value in work[release_field].dropna().unique()))
        return BacktestResult(
            training_period=(training_era.start_period, training_era.end_period),
            prediction_period=(prediction_era.start_period, prediction_era.end_period),
            source_release_dates=release_dates,
            target_field=target_field,
            baseline_config={
                "method": "previous_period_observed_value",
                "date_field": date_field,
                "entity_field": entity_field,
                "release_field": release_field,
                "sections": sections,
            },
            predictions=tuple(predictions),
            actual_observations=tuple(actuals),
            metrics=metrics,
            limitations=(
                "This is a naive chronological baseline over directly observed values.",
                "It does not validate the experimental composite health_score.",
                "Rows are excluded when actual values or prior training observations are missing.",
            ),
        )


def plan_backtest(
    frame: pd.DataFrame,
    *,
    target_field: str,
    date_field: str = "observation_date",
    entity_field: str = "series_id",
    release_field: str = "release_period",
    sections: int = 3,
) -> BacktestResult:
    """Convenience wrapper around :class:`BacktestPlanner`."""

    return BacktestPlanner().plan(
        frame,
        target_field=target_field,
        date_field=date_field,
        entity_field=entity_field,
        release_field=release_field,
        sections=sections,
    )


def _combine_eras(eras: tuple[EraWindow, ...], *, label: str) -> EraWindow:
    periods: list[str] = []
    observations = 0
    for era in eras:
        periods.extend(era.periods)
        observations += era.observations
    return EraWindow(
        label=label,
        start_period=periods[0],
        end_period=periods[-1],
        periods=tuple(periods),
        observations=observations,
    )


def _compute_metrics(
    predictions: list[dict[str, Any]],
    actuals: list[dict[str, Any]],
    excluded_reasons: dict[str, int],
) -> BacktestMetricSummary:
    if not predictions:
        return BacktestMetricSummary(
            mae=None,
            rmse=None,
            mape=None,
            directional_accuracy=None,
            sample_count=0,
            excluded_row_count=sum(excluded_reasons.values()),
            excluded_reasons=dict(excluded_reasons),
        )

    errors: list[float] = []
    pct_errors: list[float] = []
    direction_hits = 0
    for prediction, actual in zip(predictions, actuals, strict=True):
        predicted_value = float(prediction["predicted_value"])
        actual_value = float(actual["actual_value"])
        error = predicted_value - actual_value
        errors.append(error)
        if actual_value != 0:
            pct_errors.append(abs(error / actual_value))
        if _direction(predicted_value) == _direction(actual_value):
            direction_hits += 1

    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error**2 for error in errors) / len(errors))
    mape = (sum(pct_errors) / len(pct_errors)) * 100 if pct_errors else None
    directional_accuracy = direction_hits / len(errors)
    return BacktestMetricSummary(
        mae=mae,
        rmse=rmse,
        mape=mape,
        directional_accuracy=directional_accuracy,
        sample_count=len(errors),
        excluded_row_count=sum(excluded_reasons.values()),
        excluded_reasons=dict(excluded_reasons),
    )


def _direction(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _count_exclusion(excluded_reasons: dict[str, int], reason: str) -> None:
    excluded_reasons[reason] = excluded_reasons.get(reason, 0) + 1


__all__ = [
    "BacktestMetricSummary",
    "BacktestPlanner",
    "BacktestResult",
    "plan_backtest",
]
