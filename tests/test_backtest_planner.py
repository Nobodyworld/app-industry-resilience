from __future__ import annotations

import pandas as pd
import pytest

from src.application.backtest_planner import plan_backtest


def test_backtest_planner_uses_chronological_previous_period_baseline() -> None:
    frame = pd.DataFrame(
        [
            _row("2024-01-01", 100.0),
            _row("2024-02-01", 105.0),
            _row("2024-03-01", 110.0),
            _row("2024-04-01", 120.0),
            _row("2024-05-01", 125.0),
            _row("2024-06-01", 130.0),
        ]
    )

    result = plan_backtest(frame, target_field="signal_value", sections=3)

    assert result.training_period == ("2024-01-01", "2024-04-01")
    assert result.prediction_period == ("2024-05-01", "2024-06-01")
    assert [item["predicted_value"] for item in result.predictions] == [120.0, 120.0]
    assert [item["actual_value"] for item in result.actual_observations] == [125.0, 130.0]
    assert result.metrics.sample_count == 2
    assert result.metrics.mae == pytest.approx(7.5)
    assert result.metrics.rmse == pytest.approx(7.905694, rel=1e-6)
    assert "does not validate the experimental composite health_score" in result.limitations[1]


def test_backtest_planner_tracks_excluded_rows() -> None:
    frame = pd.DataFrame(
        [
            _row("2024-01-01", 100.0, series_id="A"),
            _row("2024-02-01", 101.0, series_id="A"),
            _row("2024-03-01", 102.0, series_id="A"),
            _row("2024-04-01", 103.0, series_id="A"),
            _row("2024-05-01", None, series_id="A"),
            _row("2024-06-01", 201.0, series_id="B"),
        ]
    )

    result = plan_backtest(frame, target_field="signal_value", sections=3)

    assert result.metrics.excluded_row_count == 2
    assert result.metrics.excluded_reasons == {
        "missing_actual": 1,
        "missing_training_history": 1,
    }


def test_backtest_planner_requires_observed_target() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        plan_backtest(pd.DataFrame([{"observation_date": "2024-01-01"}]), target_field="value")


def _row(
    date: str, value: float | None, *, series_id: str = "PCU311111311111"
) -> dict[str, object]:
    return {
        "observation_date": date,
        "release_period": date[:7],
        "series_id": series_id,
        "signal_value": value,
    }
