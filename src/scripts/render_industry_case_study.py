"""Render the documented Food Manufacturing results from committed data and formulas.

Run from the repository root: python -m src.scripts.render_industry_case_study
"""

from pathlib import Path

import pandas as pd

from src.application.scenario_planner import ScenarioAdjustment, ScenarioPlanner

ROOT = Path(__file__).resolve().parents[2]
START = "<!-- BEGIN GENERATED SCENARIO RESULTS -->"
END = "<!-- END GENERATED SCENARIO RESULTS -->"


def render_results() -> str:
    """Calculate tables, retaining enough precision to detect documentation drift."""
    frame = pd.read_csv(ROOT / "data/sample_industries.csv")
    result = ScenarioPlanner().plan(
        frame,
        [
            ScenarioAdjustment(
                industry_codes=["311"], gross_output_delta_pct=-10, materials_cost_delta_pct=8
            )
        ],
    )
    baseline = result.baseline.loc[result.baseline["industry_code"] == "311"].iloc[0]
    scenario = result.scenario.loc[result.scenario["industry_code"] == "311"].iloc[0]
    metrics = (
        "gross_output",
        "materials_cost",
        "value_added",
        "idiot_index",
        "resilience_score",
        "value_added_pct",
        "materials_share_pct",
        "materials_dependency_ratio",
        "shock_sensitivity_index",
        "health_score",
    )
    lines = [
        START,
        "",
        "## Calculated Target-Industry Results (NAICS 311)",
        "",
        f"Observation year: {int(baseline['year'])}. Values below are generated from the committed CSV.",
        "",
        "| Metric | Baseline | Scenario | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for metric in metrics:
        before, after = float(baseline[metric]), float(scenario[metric])
        lines.append(f"| `{metric}` | {before:,.4f} | {after:,.4f} | {after-before:+,.4f} |")
    lines.extend(
        [
            "",
            "## Calculated Portfolio-Level Results",
            "",
            "These totals and means describe all eight bundled sample industries.",
            "",
            "| Metric | Baseline | Scenario | Delta |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for metric in (
        "gross_output_total",
        "materials_cost_total",
        "value_added_total",
        "idiot_index_avg",
        "resilience_score_avg",
        "health_score_avg",
    ):
        before = getattr(result.baseline_summary, metric)
        after = getattr(result.scenario_summary, metric)
        lines.append(f"| `{metric}` | {before:,.4f} | {after:,.4f} | {after-before:+,.4f} |")
    return "\n".join([*lines, "", END])


def main() -> None:
    path = ROOT / "docs/INDUSTRY_SHOCK_CASE_STUDY.md"
    text = path.read_text(encoding="utf-8")
    start = text.index(START)
    end = text.index(END) + len(END)
    path.write_text(text[:start] + render_results() + text[end:], encoding="utf-8")


if __name__ == "__main__":
    main()
