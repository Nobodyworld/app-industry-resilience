from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from src.core.metrics import MetricConfig, compute_metrics
from src.infrastructure.observability.storage import ObservabilitySnapshot
from src.interfaces.streamlit.helpers import (
    build_comparison_table,
    build_health_band_distribution,
    build_health_risk_table,
    build_health_sector_table,
    build_scenario_comparison_table,
    calculate_benchmark,
    decode_query_params,
    encode_query_params,
    extract_health_badge,
    prepare_download_artifacts,
    prepare_trend_data,
    snapshot_history_table,
    snapshot_timeline_frame,
    summarise_observability_snapshot,
)


def _sample_df():
    return pd.DataFrame(
        [
            {
                "industry_code": "311",
                "industry_name": "Food",
                "year": 2020,
                "gross_output": 100.0,
                "materials_cost": 60.0,
                "value_added": 40.0,
            },
            {
                "industry_code": "312",
                "industry_name": "Beverage",
                "year": 2020,
                "gross_output": 200.0,
                "materials_cost": 120.0,
                "value_added": 80.0,
            },
        ]
    )


def test_prepare_download_artifacts_csv_json() -> None:
    df = _sample_df()
    artifacts = prepare_download_artifacts(df, df, base_name="report.csv")
    assert any(a.mime == "text/csv" for a in artifacts)
    assert any(a.mime == "application/json" for a in artifacts)


def test_build_comparison_table_empty_and_with_codes() -> None:
    df = _sample_df()
    df = compute_metrics(df, config=MetricConfig(use_cache=False))
    empty = build_comparison_table(df, [])
    assert empty.empty
    cmp = build_comparison_table(df, ["311"])
    assert not cmp.empty
    assert cmp.loc[0, "industry_code"] == "311"


def test_calculate_benchmark_and_deltas() -> None:
    df = _sample_df()
    df = compute_metrics(df, config=MetricConfig(use_cache=False))
    b = calculate_benchmark(df, "311")
    assert "idiot_index_avg" in b
    assert b["idiot_index_delta"] is not None


def test_build_health_tables_none() -> None:
    h = build_health_sector_table(None)
    assert h.empty
    d = build_health_band_distribution(None)
    assert d.empty
    r = build_health_risk_table(None)
    assert r.empty


def test_extract_health_badge_none() -> None:
    assert extract_health_badge(None)["score"] is None


def test_prepare_trend_data_and_snapshot_helpers() -> None:
    df = _sample_df()
    df = compute_metrics(df, config=MetricConfig(use_cache=False))
    trend = prepare_trend_data(df, ["311"])
    assert not trend.empty

    snapshot = ObservabilitySnapshot(
        snapshot_id="snap1",
        captured_at=datetime.now(UTC),
        payload={"events": {"counts": {"success": 1}, "recent": []}, "metrics": {"requests": 1}},
        metadata={"label": "test"},
    )
    summ = summarise_observability_snapshot(snapshot)
    assert summ["snapshot_id"] == "snap1"
    table = snapshot_history_table([summ])
    assert not table.empty
    timeline = snapshot_timeline_frame([summ])
    assert not timeline.empty


def test_query_param_encoding_decoding_roundtrip() -> None:
    enc = encode_query_params(foo="bar", codes=["311", "312"], noneval=None)
    assert enc["foo"][0] == "bar"
    dec = decode_query_params(enc)
    assert dec["foo"][0] == "bar"


def test_build_comparison_table_computes_metrics_if_missing() -> None:
    # Passing a raw dataframe to helpers should compute derived metrics implicitly.
    df = _sample_df()
    # don't call compute_metrics here; helper should compute it
    cmp = build_comparison_table(df, ["311"])
    assert not cmp.empty
    assert "idiot_index" in cmp.columns


def test_calculate_benchmark_computes_metrics_if_missing() -> None:
    df = _sample_df()
    b = calculate_benchmark(df, "312")
    assert "idiot_index_avg" in b


def test_prepare_trend_data_computes_metrics_if_missing() -> None:
    df = _sample_df()
    # verify prepare_trend_data works on a raw DF
    trend = prepare_trend_data(df, ["311"])
    assert not trend.empty
    assert "idiot_index" in trend.columns


def test_build_scenario_comparison_table_auto_compute() -> None:
    from src.application.scenario_planner import ScenarioResult

    # Prepare baseline and scenario raw dataframes (no computed columns)
    base = _sample_df()
    # scenario: same structure with a change in value added
    scenario = base.copy()
    scenario.loc[0, "value_added"] = 35.0

    result = ScenarioResult(
        baseline=base,
        scenario=scenario,
        baseline_summary=None,
        scenario_summary=None,
        delta_summary=None,
        deltas=base,
        baseline_health_summary=None,
        scenario_health_summary=None,
    )

    table = build_scenario_comparison_table(result)
    assert not table.empty
    assert "idiot_index_baseline" in table.columns
    assert "idiot_index_scenario" in table.columns
