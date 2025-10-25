"""Tests for the BEA adapter including validation and caching helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.adapters.bea import (
    BEAClientError,
    _ensure_years,
    _merge_metadata_notes,
    fetch_go_ii_by_industry,
    select_bea_endpoint,
)
from src.core import AppConfig, Cache, CacheConfig, Environment, RateLimitConfig


@patch("src.adapters.bea.get_api_cache", return_value=None)
@patch("src.adapters.bea.safe_get_json")
def test_fetch_bea(mock_get_json, _cache) -> None:
    """Gross output and intermediate inputs are merged with metadata."""

    health_response = {"BEAAPI": {"Results": {"Data": []}}}
    go_response = {
        "BEAAPI": {
            "Results": {
                "Data": [
                    {
                        "Industry": "311",
                        "IndustrYDescription": "Food",
                        "Year": "2021",
                        "DataValue": "100",
                    }
                ],
                "Notes": [" note "],
            }
        }
    }
    ii_response = {
        "BEAAPI": {
            "Results": {
                "Data": [
                    {
                        "Industry": "311",
                        "IndustrYDescription": "Food",
                        "Year": "2021",
                        "DataValue": "60",
                    }
                ],
                "Notes": ["note", "Different"],
            }
        }
    }
    mock_get_json.side_effect = [health_response, go_response, ii_response]

    frame = fetch_go_ii_by_industry("valid_api_key_12345", 2021)
    assert "intermediate_inputs" in frame.columns
    assert frame.loc[0, "gross_output"] == 100_000_000.0
    metadata = frame.attrs.get("bea_metadata", {})
    assert metadata.get("years") == (2021,)
    assert metadata.get("endpoint")
    assert metadata.get("notes") == ["note", "Different"]


@patch("src.adapters.bea.safe_get_json")
def test_fetch_bea_multi_year_caches(mock_get_json, tmp_path) -> None:
    """Repeated BEA fetches for the same year set should use cache metadata."""

    cache = Cache(tmp_path, ttl_seconds=60)

    def fake_cache(_config):
        return cache

    health_response = {"BEAAPI": {"Results": {"Data": []}}}

    def build_response(year: int, value: str) -> dict:
        return {
            "BEAAPI": {
                "Results": {
                    "Data": [
                        {
                            "Industry": "311",
                            "IndustrYDescription": "Food",
                            "Year": str(year),
                            "DataValue": value,
                        }
                    ]
                }
            }
        }

    mock_get_json.side_effect = [
        health_response,
        build_response(2021, "100"),
        build_response(2021, "60"),
        build_response(2020, "90"),
        build_response(2020, "55"),
    ]

    with patch("src.adapters.bea.get_api_cache", side_effect=fake_cache):
        frame = fetch_go_ii_by_industry("valid_api_key_12345", [2021, 2020])
        assert sorted(frame["year"].unique().tolist()) == [2020, 2021]
        metadata = frame.attrs["bea_metadata"]
        assert set(metadata["years"]) == {2020, 2021}
        assert cache.stats().files == 1
        assert metadata["notes"] == []

        call_count = mock_get_json.call_count
        cached = fetch_go_ii_by_industry("valid_api_key_12345", [2020, 2021])
        assert len(cached) == len(frame)
        assert mock_get_json.call_count == call_count  # cache hit, no new calls


@patch("src.adapters.bea.get_api_cache", return_value=None)
@patch("src.adapters.bea.safe_get_json", side_effect=Exception("down"))
def test_select_bea_endpoint_failure(mock_get_json, _cache) -> None:
    """Endpoint selection should bubble up errors with context."""

    with pytest.raises(BEAClientError):
        fetch_go_ii_by_industry("valid_api_key_12345", 2021)


def test_ensure_years_rejects_duplicates() -> None:
    """Duplicate year values should raise a descriptive BEAClientError."""

    with pytest.raises(BEAClientError) as excinfo:
        _ensure_years([2020, 2020])
    assert "Duplicate years" in str(excinfo.value)


def test_ensure_years_rejects_invalid_values() -> None:
    """Non-numeric year inputs are rejected early."""

    with pytest.raises(BEAClientError) as excinfo:
        _ensure_years(["2020", "twenty"])
    assert "Invalid BEA year value" in str(excinfo.value)


def test_merge_metadata_notes_deduplicates() -> None:
    """Metadata note helpers should strip whitespace and deduplicate."""

    notes = _merge_metadata_notes([" note "], ["note", "Other"], [])
    assert notes == ["note", "Other"]


@patch("src.adapters.bea.safe_get_json")
def test_select_bea_endpoint_success(mock_get_json, tmp_path: Path) -> None:
    """Endpoint selection returns the first working URL."""

    mock_get_json.return_value = {"BEAAPI": {"Results": {"Data": []}}}
    config = AppConfig(
        environment=Environment.DEVELOPMENT,
        log_level="INFO",
        default_year=2021,
        bea_api_key=None,
        census_api_key=None,
        bea_api_version=None,
        bea_api_base_urls=("https://apps.bea.gov/api/data", "https://fallback"),
        rate_limits=RateLimitConfig(bea=10, census=10, default=5),
        cache=CacheConfig(
            enabled=False,
            base_dir=tmp_path,
            api_ttl_seconds=0,
            computation_ttl_seconds=0,
        ),
        max_csv_size_mb=50,
        supported_years_bea=range(1997, 2025),
        supported_years_census=range(1997, 2024),
    )

    endpoint = select_bea_endpoint(config)
    assert endpoint == "https://apps.bea.gov/api/data"
