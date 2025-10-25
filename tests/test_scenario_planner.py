from __future__ import annotations

import pandas as pd
import pytest

from src.application.scenario_planner import (
    ScenarioAdjustment,
    ScenarioPlanner,
    plan_scenario,
)


def _base_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "industry_code": ["111", "112"],
            "industry_name": ["Alpha", "Beta"],
            "year": [2021, 2021],
            "gross_output": [100.0, 200.0],
            "materials_cost": [40.0, 90.0],
            "intermediate_inputs": [40.0, 90.0],
            "value_added": [60.0, 110.0],
        }
    )


def test_scenario_planner_applies_adjustments() -> None:
    planner = ScenarioPlanner()
    base = _base_frame()
    adjustment = ScenarioAdjustment(
        industry_codes=["111"],
        gross_output_delta_pct=10.0,
        materials_cost_delta_pct=-5.0,
    )

    result = planner.plan(base, [adjustment])

    baseline = result.baseline.set_index("industry_code")
    scenario = result.scenario.set_index("industry_code")

    assert scenario.loc["111", "gross_output"] == pytest.approx(110.0)
    assert scenario.loc["111", "materials_cost"] == pytest.approx(38.0)
    assert scenario.loc["112", "gross_output"] == pytest.approx(baseline.loc["112", "gross_output"])

    delta_row = result.deltas[result.deltas["industry_code"] == "111"].iloc[0]
    assert delta_row["gross_output"] == pytest.approx(10.0)
    assert delta_row["materials_cost"] == pytest.approx(-2.0)

    assert result.delta_summary["gross_output_total"] == pytest.approx(10.0)
    assert result.delta_summary["materials_cost_total"] == pytest.approx(-2.0)


def test_plan_scenario_defaults_to_no_cache() -> None:
    base = _base_frame()
    result = plan_scenario(base, [])
    pd.testing.assert_frame_equal(result.baseline, result.scenario)
    assert result.deltas["gross_output"].abs().sum() == 0.0
