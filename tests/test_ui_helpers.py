from __future__ import annotations

import pandas as pd

from src.ui.helpers import (
    build_comparison_table,
    calculate_benchmark,
    decode_query_params,
    encode_query_params,
    prepare_download_artifacts,
    prepare_trend_data,
)


def _sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "industry_code": ["111", "112"],
            "industry_name": ["Alpha", "Beta"],
            "year": [2020, 2021],
            "gross_output": [100.0, 200.0],
            "materials_cost": [40.0, 90.0],
            "value_added": [60.0, 110.0],
            "idiot_index": [2.5, 2.22],
            "value_added_pct": [60.0, 55.0],
            "materials_share_pct": [40.0, 45.0],
        }
    )


def test_prepare_download_artifacts_creates_outputs() -> None:
    frame = _sample_frame()
    artifacts = prepare_download_artifacts(frame, frame.iloc[[0]], base_name="idiot")
    has_excel = any(
        item.mime
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        for item in artifacts
    )
    assert len(artifacts) == (6 if has_excel else 4)
    csv_artifact = next(item for item in artifacts if item.mime == "text/csv" and "full" in item.file_name)
    assert b"industry_code" in csv_artifact.data


def test_build_comparison_table_and_trend() -> None:
    frame = _sample_frame()
    comparison = build_comparison_table(frame, ["112"])
    assert comparison.iloc[0]["industry_name"] == "Beta"
    trend = prepare_trend_data(frame, ["111", "112"])
    assert set(trend["industry_code"]) == {"111", "112"}


def test_calculate_benchmark_returns_deltas() -> None:
    frame = _sample_frame()
    stats = calculate_benchmark(frame, "111")
    assert stats["idiot_index_avg"] > 0
    assert stats["idiot_index_delta"] is not None


def test_encode_decode_query_params_round_trip() -> None:
    encoded = encode_query_params(focus="true", compare=["111", "112"], search="test")
    decoded = decode_query_params(encoded)
    assert decoded["focus"] == ["true"]
    assert decoded["compare"] == ["111", "112"]
