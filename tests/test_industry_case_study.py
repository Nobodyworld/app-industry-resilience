"""Keep the published worked example tied to actual CSV inputs and calculations."""

import pandas as pd

from src.scripts.render_industry_case_study import END, ROOT, START, render_results


def test_food_manufacturing_documentation_matches_execution() -> None:
    frame = pd.read_csv(ROOT / "data/sample_industries.csv", dtype={"industry_code": str})
    target = frame.set_index("industry_code").loc["311"]
    assert target["gross_output"] == 904100
    assert target["materials_cost"] == 552700
    text = (ROOT / "docs/INDUSTRY_SHOCK_CASE_STUDY.md").read_text(encoding="utf-8")
    documented = text[text.index(START) : text.index(END) + len(END)]
    assert documented == render_results()
