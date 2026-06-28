from __future__ import annotations

import pandas as pd
import pytest

from src.core import (
    HealthBand,
    HealthScoreConfig,
    compute_health_scores,
    compute_metrics,
    MetricConfig,
    summarise_health,
)


def _analytics_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "industry_code": "311",
                "industry_name": "Food Manufacturing",
                "idiot_index": 1.5,
                "value_added_pct": 60.0,
                "resilience_score": 2.5,
                "materials_dependency_ratio": 0.35,
                "shock_sensitivity_index": 0.4,
            },
            {
                "industry_code": "541",
                "industry_name": "Professional Services",
                "idiot_index": 1.1,
                "value_added_pct": 72.0,
                "resilience_score": 3.2,
                "materials_dependency_ratio": 0.2,
                "shock_sensitivity_index": 0.25,
            },
            {
                "industry_code": "44-45",
                "industry_name": "Retail Trade",
                "idiot_index": 0.9,
                "value_added_pct": 35.0,
                "resilience_score": 1.1,
                "materials_dependency_ratio": 0.65,
                "shock_sensitivity_index": 0.7,
            },
        ]
    )


def test_compute_health_scores_adds_columns() -> None:
    frame = _analytics_frame()
    scored = compute_health_scores(frame)

    assert "health_score" in scored.columns
    assert "health_band" in scored.columns
    assert scored.loc[0, "health_score"] > 0
    assert scored.loc[1, "health_band"] in {band.name for band in HealthScoreConfig().bands}


def test_compute_health_scores_handles_missing_values() -> None:
    frame = _analytics_frame()
    frame.loc[0, "resilience_score"] = None

    scored = compute_health_scores(frame)

    assert pd.isna(scored.loc[0, "health_score"])
    assert scored.loc[0, "health_band"] is None


def test_summarise_health_returns_expected_structure() -> None:
    frame = _analytics_frame()
    config = HealthScoreConfig(
        bands=(
            HealthBand(name="excellent", min_score=75.0),
            HealthBand(name="healthy", min_score=55.0),
            HealthBand(name="watch", min_score=35.0),
            HealthBand(name="critical", min_score=0.0),
        )
    )
    summary = summarise_health(frame, config=config)

    assert summary.overall.industries == 3
    assert summary.band_breakdown[0].band == "excellent"
    assert summary.top_risks[0].industry_code == "44-45"
    assert any(aggregate.label.startswith("3") for aggregate in summary.sectors)


def test_summarise_health_overall_group_excludes_sectors() -> None:
    frame = _analytics_frame()

    summary = summarise_health(frame, group_by="overall")

    assert summary.sectors == ()


def test_summarise_health_limits_top_risks() -> None:
    frame = _analytics_frame()

    summary = summarise_health(frame, top_risk_limit=0)

    assert summary.top_risks == ()


def test_compute_health_scores_validates_columns() -> None:
    with pytest.raises(ValueError):
        compute_health_scores(pd.DataFrame({"industry_code": []}))


def test_official_snapshot_bottom_risk_scores_are_reproducible() -> None:
    frame = pd.read_csv("data/official_industry_snapshot.csv")
    metrics = compute_metrics(frame, config=MetricConfig(use_cache=False))
    scored = compute_health_scores(metrics)

    code_key = scored["industry_code"].astype(str).str.replace(r"\.0$", "", regex=True)
    target = scored[code_key.isin(["493", "521", "622", "623", "484"])]
    observed = {
        str(row["industry_code"]).replace(".0", ""): float(row["health_score"])
        for _, row in target[["industry_code", "health_score"]].iterrows()
    }

    assert observed["493"] == pytest.approx(0.00, abs=1e-2)
    assert observed["521"] == pytest.approx(0.00, abs=1e-2)
    assert observed["622"] == pytest.approx(3.07, abs=1e-2)
    assert observed["623"] == pytest.approx(6.14, abs=1e-2)
    assert observed["484"] == pytest.approx(6.38, abs=1e-2)
