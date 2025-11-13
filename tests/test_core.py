"""Tests for core domain logic including configuration, metrics, normalization, and utilities."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from src.adapters import fetch_asm_manufacturing
from src.core import (
    Cache,
    HTTPRequestError,
    MetricConfig,
    RetryPolicy,
    compute_metrics,
    format_for_display,
    normalize_columns,
    register_retry_observer,
    safe_get_json,
)


def test_normalize_columns_handles_aliases() -> None:
    frame = pd.DataFrame(
        {
            "NAICS2017": ["311"],
            "NAICS2017_LABEL": ["Food"],
            "Year": ["2021"],
            "RCPTOT": ["1,000"],
            "CSTMTOT": ["600"],
        }
    )

    normalized = normalize_columns(frame)
    assert list(normalized.columns)[:4] == [
        "industry_code",
        "industry_name",
        "year",
        "gross_output",
    ]
    assert normalized.loc[0, "gross_output"] == 1000.0
    assert normalized.loc[0, "materials_cost"] == 600.0


def test_normalize_columns_respects_dtype_overrides() -> None:
    frame = pd.DataFrame(
        {
            "industry_code": ["001"],
            "industry_name": ["Widgets"],
            "year": ["2021"],
            "gross_output": ["1_000"],
            "materials_cost": ["500"],
        }
    )

    normalized = normalize_columns(
        frame,
        dtype_overrides={"materials_cost": "Int64", "industry_code": "string"},
    )

    assert str(normalized.dtypes["materials_cost"]) == "Int64"
    assert str(normalized.dtypes["industry_code"]).startswith("string")


def test_normalize_columns_rejects_fractional_years() -> None:
    frame = pd.DataFrame(
        {
            "industry_code": ["311"],
            "industry_name": ["Food"],
            "year": ["2021.5"],
            "gross_output": ["1,000"],
        }
    )

    with pytest.raises(ValueError) as excinfo:
        normalize_columns(frame)

    assert "year" in str(excinfo.value).lower()


def test_compute_metrics_uses_cache(tmp_path) -> None:
    cache = Cache(tmp_path, ttl_seconds=60)
    data = pd.DataFrame(
        {
            "industry_code": ["311"],
            "industry_name": ["Food"],
            "year": [2021],
            "gross_output": [1000.0],
            "materials_cost": [500.0],
            "intermediate_inputs": [None],
            "source": ["Test"],
        }
    )

    result_first = compute_metrics(data, cache=cache, config=MetricConfig(use_cache=True))
    assert "idiot_index" in result_first.columns
    assert result_first.loc[0, "resilience_score"] == pytest.approx(1.0)
    assert result_first.loc[0, "materials_dependency_ratio"] == pytest.approx(0.5)
    assert result_first.loc[0, "shock_sensitivity_index"] == pytest.approx(0.5)
    assert cache.stats().files == 1

    with patch.object(cache, "set", wraps=cache.set) as mocked_set:
        result_second = compute_metrics(data, cache=cache, config=MetricConfig(use_cache=True))
        mocked_set.assert_not_called()
    pd.testing.assert_frame_equal(result_first, result_second)


def test_compute_metrics_handles_zero_denominators() -> None:
    data = pd.DataFrame(
        {
            "industry_code": ["000"],
            "industry_name": ["Zero"],
            "year": [2021],
            "gross_output": [100.0],
            "materials_cost": [0.0],
            "intermediate_inputs": [0.0],
            "value_added": [0.0],
        }
    )

    result = compute_metrics(data, config=MetricConfig(use_cache=False))
    assert pd.isna(result.loc[0, "resilience_score"])
    assert result.loc[0, "materials_dependency_ratio"] == pytest.approx(0.0)
    assert pd.isna(result.loc[0, "shock_sensitivity_index"])


def test_cache_removes_corrupted_entries(tmp_path) -> None:
    cache = Cache(tmp_path, ttl_seconds=60)
    key = "corrupted"
    path = cache._path_for_key(key)
    path.write_text("{not: json}", encoding="utf-8")

    assert cache.get(key) is None
    assert not path.exists()


def test_cache_respects_ttl(monkeypatch, tmp_path) -> None:
    cache = Cache(tmp_path, ttl_seconds=1)
    key = "expiring"
    base_time = 1_700_000_000.0

    monkeypatch.setattr("src.core.cache.time.time", lambda: base_time)
    cache.set(key, {"value": 1})
    path = cache._path_for_key(key)
    assert path.exists()

    monkeypatch.setattr("src.core.cache.time.time", lambda: base_time + 5)
    assert cache.get(key) is None
    assert not path.exists()


def test_cache_rejects_invalid_ttl(tmp_path) -> None:
    with pytest.raises(ValueError):
        Cache(tmp_path, ttl_seconds=0)


def test_format_for_display_coerces_numeric() -> None:
    frame = pd.DataFrame({"gross_output": ["100"], "materials_cost": ["50"]})
    formatted = format_for_display(frame)
    assert formatted.dtypes["gross_output"] == "float64"


def test_safe_get_json_retries_and_raises(monkeypatch) -> None:
    call_count = {"count": 0}

    def fake_get(*args, **kwargs):
        call_count["count"] += 1
        raise requests.exceptions.ConnectionError("boom")

    session = MagicMock()
    session.get.side_effect = fake_get
    monkeypatch.setattr("requests.Session", lambda: session)

    with pytest.raises(HTTPRequestError):
        safe_get_json("https://example.com", retry_policy=RetryPolicy(max_attempts=2, base_delay=0))

    assert call_count["count"] == 2


def test_safe_get_json_emits_retry_events(monkeypatch) -> None:
    events: list[str] = []

    def observer(event) -> None:
        events.append(event.status)

    register_retry_observer(observer)

    responses = {"count": 0}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"ok": "yes"}

    def fake_get(*args, **kwargs):
        responses["count"] += 1
        if responses["count"] == 1:
            raise requests.exceptions.Timeout("boom")
        return FakeResponse()

    session = MagicMock()
    session.get.side_effect = fake_get
    monkeypatch.setattr("requests.Session", lambda: session)

    payload = safe_get_json(
        "https://example.com",
        retry_policy=RetryPolicy(max_attempts=2, base_delay=0),
    )

    assert payload == {"ok": "yes"}
    assert events[0] == "retrying"
    assert events[-1] == "success"

    register_retry_observer(lambda event: None)

# TODO - fix duplication if exists
def test_fetch_asm_manufacturing_uses_year_specific_endpoint() -> None:
    """Ensure the Census ASM adapter calls the year-specific endpoint."""

    config = SimpleNamespace(supported_years_census=range(2010, 2030), cache=None)

    responses = [
        [
            ["NAICS2017", "NAICS2017_LABEL", "RCPTOT", "CSTMTOT", "VALADD"],
            ["311", "Food", "100", "60", "40"],
        ],
        [
            ["NAICS2017", "NAICS2017_LABEL", "RCPTOT", "CSTMTOT", "VALADD"],
            ["312", "Beverages", "200", "120", "80"],
        ],
    ]

    with (
        patch("src.adapters.census_asm.load_config", return_value=config),
        patch("src.adapters.census_asm.api_limiter.wait_for_api"),
        patch("src.adapters.census_asm.get_api_cache", return_value=None),
        patch("src.adapters.census_asm.safe_get_json", side_effect=responses) as mock_get,
    ):
        years = [2020, 2023]
        for year in years:
            frame = fetch_asm_manufacturing("valid_api_key_12345", year)
            assert frame["year"].iloc[0] == year

    called_urls = [call.args[0] for call in mock_get.call_args_list]
    expected_urls = [f"https://api.census.gov/data/{year}/asm" for year in years]
    assert called_urls == expected_urls

# TODO - fix duplication if exists
@pytest.mark.parametrize("year", [2019, 2021, 2023])
@patch("src.adapters.census_asm.get_api_cache", return_value=None)
@patch("src.adapters.census_asm.safe_get_json")
def test_fetch_census_manufacturing_uses_year_specific_endpoint(mock_get_json, _cache, year):
    mock_get_json.return_value = [
        ["NAICS2017", "NAICS2017_LABEL", "RCPTOT", "CSTMTOT", "VALADD"],
        ["311", "Food", "100", "60", "40"],
    ]

    frame = fetch_asm_manufacturing("valid_api_key_12345", year)

    expected_url = f"https://api.census.gov/data/{year}/asm"
    mock_get_json.assert_called_once()
    call_args, call_kwargs = mock_get_json.call_args
    assert call_args[0] == expected_url
    assert call_kwargs["params"]["key"] == "valid_api_key_12345"
    assert frame.loc[0, "industry_code"] == "311"
    assert frame.loc[0, "gross_output"] == 100.0


@patch("src.adapters.census_asm.get_api_cache", return_value=None)
@patch("src.adapters.census_asm.safe_get_json")
def test_fetch_census_manufacturing_honors_configured_endpoint_template(
    mock_get_json, _cache, monkeypatch
):
    monkeypatch.setenv(
        "CENSUS_ASM_ENDPOINT_TEMPLATE",
        "https://alt.example.com/v{year}/asm?dataset=asm",
    )
    mock_get_json.return_value = [
        ["NAICS2017", "NAICS2017_LABEL", "RCPTOT", "CSTMTOT", "VALADD"],
        ["311", "Food", "100", "60", "40"],
    ]

    frame = fetch_asm_manufacturing("valid_api_key_12345", 2022)

    expected_url = "https://alt.example.com/v2022/asm?dataset=asm"
    mock_get_json.assert_called_once()
    call_args, _ = mock_get_json.call_args
    assert call_args[0] == expected_url
    assert frame.loc[0, "industry_code"] == "311"
