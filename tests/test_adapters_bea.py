"""Tests for the BEA adapter including validation and caching helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from src.adapters.bea import (
    BEAClientError,
    _cache_key,
    _ensure_years,
    _merge_metadata_notes,
    fetch_go_ii_by_industry,
    select_bea_endpoint,
)
from src.core import (
    AppConfig,
    Cache,
    CacheConfig,
    Environment,
    RateLimitConfig,
    lineage_from_dataframe,
)
from src.core.config import DEFAULT_CENSUS_ASM_ENDPOINT_TEMPLATE


@patch("src.adapters.bea.get_api_cache", return_value=None)
@patch("src.adapters.bea.safe_get_json")
def test_fetch_bea(mock_get_json, _cache) -> None:
    """Gross output and intermediate inputs are merged with metadata."""

    health_response: dict = {"BEAAPI": {"Results": {"Data": []}}}
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
    lineage = lineage_from_dataframe(frame)
    assert lineage is not None
    assert lineage.source == "bea"
    assert lineage.source_kind.value == "live_provider"
    assert lineage.dataset_id == "gdpbyindustry"
    assert lineage.provider == "U.S. Bureau of Economic Analysis"
    assert lineage.observation_period == "2021"
    assert lineage.retrieval_mode.value == "live"
    assert lineage.is_official is True
    assert lineage.transformations[0].details == {"record_count": 1}


@patch("src.adapters.bea.safe_get_json")
def test_fetch_bea_multi_year_caches(mock_get_json, tmp_path) -> None:
    """Repeated BEA fetches for the same year set should use cache metadata."""

    cache = Cache(tmp_path, ttl_seconds=60)

    def fake_cache(_config):
        return cache

    health_response: dict = {"BEAAPI": {"Results": {"Data": []}}}

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

    values = {
        2021: {"1": "100", "2": "60"},
        2020: {"1": "90", "2": "55"},
    }

    def response_for_request(_url, *, params=None, **_kwargs):
        if params and params.get("method") == "GetParameterValues":
            return health_response
        assert params is not None
        request_year = int(params["Year"])
        table_id = params["TableID"]
        return build_response(request_year, values[request_year][table_id])

    mock_get_json.side_effect = response_for_request

    acquired_at = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
    with (
        patch("src.adapters.bea.get_api_cache", side_effect=fake_cache),
        patch("src.adapters.bea.datetime") as clock,
    ):
        clock.now.return_value = acquired_at
        frame = fetch_go_ii_by_industry("valid_api_key_12345", [2021, 2020])
        assert sorted(frame["year"].unique().tolist()) == [2020, 2021]
        metadata = frame.attrs["bea_metadata"]
        assert set(metadata["years"]) == {2020, 2021}
        assert cache.stats().files == 1
        assert metadata["notes"] == []
        miss_lineage = lineage_from_dataframe(frame)
        assert miss_lineage is not None
        assert miss_lineage.cache_status.value == "miss"
        assert miss_lineage.retrieval_mode.value == "live"
        assert miss_lineage.acquired_at == acquired_at

        cached_payload = cache.get(_cache_key((2021, 2020), None))
        assert isinstance(cached_payload, dict)
        serialized_lineage = json.dumps(cached_payload["lineage"])
        assert "valid_api_key_12345" not in serialized_lineage
        assert "cache_key" not in serialized_lineage
        assert "redis" not in serialized_lineage.casefold()
        assert "BEAAPI" not in serialized_lineage

        call_count = mock_get_json.call_count
        cached = fetch_go_ii_by_industry("valid_api_key_12345", [2020, 2021])
        assert len(cached) == len(frame)
        assert mock_get_json.call_count == call_count  # cache hit, no new calls
        hit_lineage = lineage_from_dataframe(cached)
        assert hit_lineage is not None
        assert hit_lineage.source == miss_lineage.source
        assert hit_lineage.acquired_at == miss_lineage.acquired_at
        assert hit_lineage.transformations == miss_lineage.transformations
        assert hit_lineage.cache_status.value == "hit"
        assert hit_lineage.retrieval_mode.value == "cache"


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
        _ensure_years(["2020", "twenty"])  # type: ignore
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
        census_asm_endpoint_template=DEFAULT_CENSUS_ASM_ENDPOINT_TEMPLATE,
        rate_limits=RateLimitConfig(bea=10, census=10, default=5),
        cache=CacheConfig(
            enabled=False,
            base_dir=tmp_path,
            api_ttl_seconds=0,
            computation_ttl_seconds=0,
        ),
        observability_snapshot_dir=tmp_path / "snapshots",
        observability_snapshot_retention_count=10,
        observability_snapshot_retention_days=14,
        observability_snapshot_min_interval_seconds=0.0,
        observability_snapshot_remote=None,
        max_csv_size_mb=50,
        supported_years_bea=range(1997, 2025),
        supported_years_census=range(1997, 2024),
    )

    endpoint = select_bea_endpoint(config)
    assert endpoint == "https://apps.bea.gov/api/data"
