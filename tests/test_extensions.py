from __future__ import annotations

import pandas as pd
import pytest

from src.application.idiot_index_service import IdiotIndexSummary, IndustryMetrics
from src.application.scenario_planner import ScenarioResult, ScenarioSummary
from src.extensions.manager import ExtensionManager, load_extensions


@pytest.fixture()
def sample_summary() -> IdiotIndexSummary:
    dataframe = pd.DataFrame(
        [
            {
                "industry_code": "1111",
                "industry_name": "Sample Industry",
                "materials_share_pct": 42.0,
                "idiot_index": 1.2,
                "value_added_pct": 55.0,
                "resilience_score": 1.5,
                "materials_dependency_ratio": 0.4,
                "shock_sensitivity_index": 0.5,
                "health_score": 72.0,
                "health_band": "healthy",
            },
            {
                "industry_code": "2222",
                "industry_name": "Runner Up",
                "materials_share_pct": 21.0,
                "idiot_index": 0.9,
                "value_added_pct": 48.0,
                "resilience_score": 1.3,
                "materials_dependency_ratio": 0.5,
                "shock_sensitivity_index": 0.6,
                "health_score": 61.0,
                "health_band": "watch",
            },
        ]
    )
    dataframe.attrs["source"] = "test"
    return IdiotIndexSummary(
        dataframe_full=dataframe.copy(),
        dataframe_filtered=dataframe,
        leaderboard=(
            IndustryMetrics(
                industry_code="1111",
                industry_name="Sample Industry",
                idiot_index=1.2,
                value_added_pct=None,
                materials_share_pct=42.0,
                gross_output=None,
                value_added=None,
            ),
        ),
        average_idiot_index=1.05,
        notes=tuple(),
        health_summary_full=None,
        health_summary_filtered=None,
    )


def test_builtin_extensions_register_and_contribute(sample_summary: IdiotIndexSummary) -> None:
    manager = load_extensions(
        ExtensionManager(), ["src.extensions.builtins.manufacturing_cost_driver"]
    )
    contributions = manager.apply_summary_extensions(sample_summary)

    assert any("manufacturing_cost_driver" in note for note in contributions.notes)
    assert "manufacturing_cost_driver" in contributions.metadata


def test_extension_failures_are_logged_and_ignored(sample_summary: IdiotIndexSummary) -> None:
    class BrokenExtension:
        name = "broken"

        def contribute(self, summary):  # type: ignore[override]
            raise RuntimeError("boom")

    manager = load_extensions(
        ExtensionManager(), ["src.extensions.builtins.manufacturing_cost_driver"]
    )
    manager.register_summary_extension(BrokenExtension())

    contributions = manager.apply_summary_extensions(sample_summary)

    assert "manufacturing_cost_driver" in contributions.metadata
    assert all("broken" not in note for note in contributions.notes)


def test_scenario_extension_enriches_metadata() -> None:
    manager = load_extensions(
        ExtensionManager(), ["src.extensions.builtins.manufacturing_cost_driver"]
    )
    baseline = pd.DataFrame(
        [
            {"materials_share_pct": 10.0},
            {"materials_share_pct": 20.0},
        ]
    )
    scenario = pd.DataFrame(
        [
            {"materials_share_pct": 12.0},
            {"materials_share_pct": 25.0},
        ]
    )
    deltas = pd.DataFrame([{"materials_share_pct": 2.0}])
    summary = ScenarioSummary(
        gross_output_total=1.0,
        materials_cost_total=1.0,
        value_added_total=1.0,
        idiot_index_avg=1.0,
        resilience_score_avg=1.0,
        materials_dependency_ratio_avg=1.0,
        shock_sensitivity_index_avg=1.0,
        health_score_avg=1.0,
    )
    result = ScenarioResult(
        baseline=baseline,
        scenario=scenario,
        deltas=deltas,
        baseline_summary=summary,
        scenario_summary=summary,
        delta_summary={"materials_dependency_ratio_avg": 0.0},
    )

    contributions = manager.apply_scenario_extensions(result)

    assert "manufacturing_cost_driver" in contributions.metadata
    assert any("manufacturing_cost_driver" in note for note in contributions.notes)
