from __future__ import annotations

import pandas as pd
import pytest

from src.core import (
    LINEAGE_ATTR_KEY,
    HealthBand,
    HealthScoreConfig,
    LineageStep,
    MetricConfig,
    attach_lineage,
    build_lineage,
    compute_health_scores,
    compute_metrics,
    lineage_from_dataframe,
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


def test_compute_health_scores_preserves_approved_metadata_and_ordered_lineage() -> None:
    frame = _analytics_frame()
    source_lineage = build_lineage(
        source="sample",
        source_kind="bundled_sample",
        dataset_id="sample_industries",
        observation_period=2023,
        retrieval_mode="bundled",
        is_sample=True,
        is_official=False,
        transformations=(LineageStep(name="source_load", details={"record_count": len(frame)}),),
    )
    frame.attrs.update(
        {
            "source": "api-inline",
            "bea_metadata": {
                "years": [2023],
                "notes": ["Public provider note"],
                "contract_validated": True,
                "raw_payload": ["should-not-propagate"],
            },
            "private_debug": "should-not-propagate",
        }
    )
    attach_lineage(frame, source_lineage)

    scored = compute_health_scores(frame)
    lineage = lineage_from_dataframe(scored)

    assert lineage is not None
    assert lineage.transformations[:-1] == source_lineage.transformations
    assert [step.name for step in lineage.transformations] == [
        "source_load",
        "compute_health_scores",
    ]
    assert sum(step.name == "compute_health_scores" for step in lineage.transformations) == 1
    assert lineage.transformations[-1].details == {}
    assert set(scored.attrs) == {"source", "bea_metadata", LINEAGE_ATTR_KEY}
    assert scored.attrs["source"] == "api-inline"
    assert scored.attrs["bea_metadata"] == {
        "years": [2023],
        "notes": ["Public provider note"],
        "contract_validated": True,
    }
    assert "private_debug" not in scored.attrs
    scored.attrs["bea_metadata"]["notes"].append("output-only note")
    assert frame.attrs["bea_metadata"]["notes"] == ["Public provider note"]
    assert scored["health_score"].tolist() == [68.0, 82.45, 34.75]
    assert scored["health_band"].tolist() == [
        "moderate_input_intensity",
        "lower_input_intensity",
        "review_required",
    ]


def test_compute_health_scores_without_lineage_drops_arbitrary_attrs() -> None:
    frame = _analytics_frame()
    frame.attrs["private_debug"] = "should-not-propagate"

    scored = compute_health_scores(frame)

    assert lineage_from_dataframe(scored) is None
    assert scored.attrs == {}
    assert scored["health_score"].tolist() == [68.0, 82.45, 34.75]


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
