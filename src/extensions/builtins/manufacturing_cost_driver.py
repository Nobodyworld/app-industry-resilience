"""Reference extension surfacing material cost drivers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.extensions.contracts import ExtensionContributions, ScenarioExtension, SummaryExtension
from src.extensions.manager import ExtensionManager

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from src.application import IdiotIndexSummary
    from src.application.scenario_planner import ScenarioResult


@dataclass
class _MaterialsSummaryExtension(SummaryExtension):
    name: str = "manufacturing_cost_driver"

    def contribute(self, summary: IdiotIndexSummary) -> ExtensionContributions:
        dataframe = (
            summary.dataframe_filtered
            if not summary.dataframe_filtered.empty
            else summary.dataframe_full
        )
        if "materials_share_pct" not in dataframe.columns or dataframe.empty:
            return ExtensionContributions()
        leader = dataframe.sort_values("materials_share_pct", ascending=False).iloc[0]
        avg_share = float(dataframe["materials_share_pct"].mean())
        note = (
            "Materials share leader: "
            f"{leader['industry_name']} ({leader['industry_code']}) at {leader['materials_share_pct']:.1f}%"
        )
        metadata = {
            "top_industry": {
                "industry_code": leader["industry_code"],
                "industry_name": leader["industry_name"],
                "materials_share_pct": float(leader["materials_share_pct"]),
            },
            "average_materials_share_pct": avg_share,
        }
        return ExtensionContributions(notes=(note,), metadata=metadata)


@dataclass
class _ScenarioMaterialsExtension(ScenarioExtension):
    name: str = "manufacturing_cost_driver"

    def contribute(self, result: ScenarioResult) -> ExtensionContributions:
        baseline = result.baseline
        scenario = result.scenario
        if "materials_share_pct" not in baseline.columns or baseline.empty or scenario.empty:
            return ExtensionContributions()
        baseline_avg = float(baseline["materials_share_pct"].mean())
        scenario_avg = float(scenario["materials_share_pct"].mean())
        delta = scenario_avg - baseline_avg
        note = f"Scenario materials share change: {delta:+.2f} percentage points"
        metadata = {
            "baseline_average_materials_share_pct": baseline_avg,
            "scenario_average_materials_share_pct": scenario_avg,
            "delta_materials_share_pct": delta,
        }
        return ExtensionContributions(notes=(note,), metadata=metadata)


def register(manager: ExtensionManager) -> None:
    """Register both summary and scenario extensions."""

    manager.register_summary_extension(_MaterialsSummaryExtension())
    manager.register_scenario_extension(_ScenarioMaterialsExtension())


__all__ = ["register"]
