from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from io import BytesIO

import pandas as pd
import pytest

from src.core import attach_lineage, build_lineage, lineage_from_dataframe
from src.core.metrics import MetricConfig, compute_metrics
from src.infrastructure.observability.instrumentation import ObservabilityRegistry
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
    pytest.importorskip("xlsxwriter")
    df = _sample_df()
    attach_lineage(
        df,
        build_lineage(
            source="census",
            source_kind="official_snapshot",
            dataset_id="aies",
            provider="U.S. Census Bureau",
            observation_period=2023,
            snapshot_at=datetime(2026, 2, 26, tzinfo=UTC),
            retrieval_mode="snapshot",
            is_sample=False,
            is_official=True,
        ),
    )
    before = lineage_from_dataframe(df)
    artifacts = prepare_download_artifacts(df, df, base_name="industry_cost_structure_results")

    labels = {artifact.label for artifact in artifacts}
    file_names = {artifact.file_name for artifact in artifacts}

    assert len(artifacts) == 8
    assert labels == {
        "All rows – CSV",
        "All rows – CSV lineage",
        "All rows – JSON",
        "All rows – Excel",
        "Current view – CSV",
        "Current view – CSV lineage",
        "Current view – JSON",
        "Current view – Excel",
    }
    assert file_names == {
        "industry_cost_structure_results_full.csv",
        "industry_cost_structure_results_full.lineage.json",
        "industry_cost_structure_results_full.json",
        "industry_cost_structure_results_full.xlsx",
        "industry_cost_structure_results_filtered.csv",
        "industry_cost_structure_results_filtered.lineage.json",
        "industry_cost_structure_results_filtered.json",
        "industry_cost_structure_results_filtered.xlsx",
    }
    legacy_stem = "idiot" + "_index_results"
    assert all(legacy_stem not in artifact.file_name for artifact in artifacts)

    csv_artifact = next(
        artifact
        for artifact in artifacts
        if artifact.file_name == "industry_cost_structure_results_full.csv"
    )
    csv_rows = pd.read_csv(BytesIO(csv_artifact.data))
    assert csv_rows.loc[0, "industry_code"] == 311
    assert csv_rows.loc[0, "industry_name"] == "Food"

    json_artifact = next(
        artifact
        for artifact in artifacts
        if artifact.file_name == "industry_cost_structure_results_full.json"
    )
    json_document = json.loads(json_artifact.data.decode())
    assert set(json_document) == {"lineage", "records"}
    assert json_document["records"][0]["industry_code"] == "311"
    assert json_document["records"][0]["industry_name"] == "Food"
    assert json_document["lineage"]["source"] == "census"
    assert json_document["lineage"]["transformations"][-1]["name"] == "export_serialization"

    companion = next(
        artifact
        for artifact in artifacts
        if artifact.file_name == "industry_cost_structure_results_full.lineage.json"
    )
    companion_document = json.loads(companion.data.decode())
    assert companion_document["lineage"]["transformations"][-1]["details"] == {
        "format": "csv",
        "record_count": 2,
        "scope": "full",
    }

    xlsx_artifact = next(
        artifact
        for artifact in artifacts
        if artifact.file_name == "industry_cost_structure_results_full.xlsx"
    )
    assert xlsx_artifact.data
    with zipfile.ZipFile(BytesIO(xlsx_artifact.data)) as workbook:
        workbook_xml = workbook.read("xl/workbook.xml").decode()
    assert 'name="Cost Structure"' in workbook_xml
    assert 'name="Lineage"' in workbook_xml
    assert lineage_from_dataframe(df) == before


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


def test_auto_compute_counter_and_logging_are_bounded(monkeypatch, caplog) -> None:
    import src.interfaces.streamlit.helpers as helpers

    registry = ObservabilityRegistry()
    monkeypatch.setattr(helpers, "bootstrap_observability", lambda: registry)
    with caplog.at_level("INFO", logger="idiot_index.helpers"):
        build_comparison_table(_sample_df(), ["311"])

    counter = registry.metrics.counters["industry_resilience_streamlit_auto_compute_total"]
    assert counter.label_names == ("helper",)
    assert dict(counter.samples()) == {("build_comparison_table",): 1.0}
    assert "Auto-computing derived metrics" in caplog.text
    assert "Food" not in caplog.text


def test_auto_compute_counter_does_not_increment_when_metrics_present(monkeypatch) -> None:
    import src.interfaces.streamlit.helpers as helpers

    registry = ObservabilityRegistry()
    monkeypatch.setattr(helpers, "bootstrap_observability", lambda: registry)
    build_comparison_table(
        compute_metrics(_sample_df(), config=MetricConfig(use_cache=False)), ["311"]
    )
    assert "industry_resilience_streamlit_auto_compute_total" not in registry.metrics.counters


def test_scenario_auto_compute_counter_tracks_baseline_and_scenario(monkeypatch) -> None:
    import src.interfaces.streamlit.helpers as helpers
    from src.application.scenario_planner import ScenarioResult

    registry = ObservabilityRegistry()
    monkeypatch.setattr(helpers, "bootstrap_observability", lambda: registry)
    base = _sample_df()
    result = ScenarioResult(base, base.copy(), None, None, None, base, None, None)
    build_scenario_comparison_table(result)

    samples = dict(
        registry.metrics.counters["industry_resilience_streamlit_auto_compute_total"].samples()
    )
    assert samples == {
        ("build_scenario_comparison_table_baseline",): 1.0,
        ("build_scenario_comparison_table_scenario",): 1.0,
    }
