from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from src.application.scenario_planner import (
    ScenarioAdjustment,
    ScenarioPlanner,
    plan_scenario,
)
from src.core import (
    LineageStep,
    attach_lineage,
    build_lineage,
    lineage_from_dataframe,
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


def _attach_official_lineage(frame: pd.DataFrame) -> pd.DataFrame:
    lineage = build_lineage(
        source="bea",
        source_kind="live_provider",
        dataset_id="bea-industry",
        provider="Bureau of Economic Analysis",
        observation_period="2021",
        acquired_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
        retrieval_mode="live",
        is_sample=False,
        is_official=True,
        transformations=(
            LineageStep(
                name="source_load",
                details={"record_count": len(frame)},
            ),
        ),
    )
    return attach_lineage(frame, lineage)


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
    assert "health_score" in result.baseline.columns
    assert result.baseline_health_summary is not None
    assert result.scenario_health_summary is not None
    assert "health_score_avg" in result.delta_summary


def test_scenario_lineage_preserves_source_and_bounds_adjustment_details() -> None:
    planner = ScenarioPlanner()
    base = _attach_official_lineage(_base_frame())
    adjustment = ScenarioAdjustment(
        industry_codes=["111"],
        gross_output_delta_pct=10.0,
        materials_cost_delta_pct=-5.0,
    )

    result = planner.plan(base, [adjustment])

    baseline_lineage = lineage_from_dataframe(result.baseline)
    scenario_lineage = lineage_from_dataframe(result.scenario)
    delta_lineage = lineage_from_dataframe(result.deltas)

    assert baseline_lineage is not None
    assert scenario_lineage is not None
    assert delta_lineage is not None
    assert baseline_lineage.source == "bea"
    assert scenario_lineage.source == "bea"
    assert delta_lineage.source == "bea"
    assert scenario_lineage.acquired_at == baseline_lineage.acquired_at
    assert delta_lineage.acquired_at == baseline_lineage.acquired_at
    assert [step.name for step in baseline_lineage.transformations] == [
        "source_load",
        "compute_metrics",
        "compute_health_scores",
    ]
    assert [step.name for step in scenario_lineage.transformations] == [
        "source_load",
        "scenario_adjustment",
        "compute_metrics",
        "compute_health_scores",
    ]
    assert delta_lineage.transformations == scenario_lineage.transformations

    adjustment_step = scenario_lineage.transformations[1]
    assert adjustment_step.details == {
        "adjustment_count": 1,
        "all_industries": False,
        "gross_output_delta_pct": 10.0,
        "intermediate_inputs_delta_pct": None,
        "materials_cost_delta_pct": -5.0,
        "targeted_industry_count": 1,
        "value_added_delta_pct": None,
    }


def test_scenario_planner_builds_redacted_fallback_lineage() -> None:
    base = _base_frame()
    base.attrs.update(
        {
            "source": "C:\\Users\\private\\records.csv",
            "api_key": "not-for-lineage",
        }
    )

    result = ScenarioPlanner().plan(base, [])
    lineage = lineage_from_dataframe(result.baseline)

    assert lineage is not None
    assert lineage.source == "scenario-input"
    assert lineage.dataset_id == "scenario-input"
    assert lineage.observation_period == "2021"
    serialized = lineage.as_dict()
    assert "api_key" not in serialized
    assert "records.csv" not in str(serialized)


def test_plan_scenario_defaults_to_no_cache() -> None:
    base = _base_frame()
    result = plan_scenario(base, [])
    pd.testing.assert_frame_equal(result.baseline, result.scenario)
    assert result.deltas["gross_output"].abs().sum() == 0.0
    assert "health_score" in result.baseline.columns
    assert result.baseline_health_summary is not None
