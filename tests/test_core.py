from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from src.cache import Cache
from src.metrics import MetricConfig, compute_metrics, format_for_display
from src.normalize import normalize_columns
from src.sources.bea import fetch_go_ii_by_industry
from src.sources.census_asm import fetch_asm_manufacturing
from src.utils import HTTPRequestError, RetryPolicy, safe_get_json


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
    assert cache.stats().files == 1

    with patch.object(cache, "set", wraps=cache.set) as mocked_set:
        result_second = compute_metrics(data, cache=cache, config=MetricConfig(use_cache=True))
        mocked_set.assert_not_called()
    pd.testing.assert_frame_equal(result_first, result_second)


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


@patch("src.sources.census_asm.get_api_cache", return_value=None)
@patch("src.sources.census_asm.safe_get_json")
def test_fetch_census_manufacturing(mock_get_json, _cache):
    mock_get_json.return_value = [
        ["NAICS2017", "NAICS2017_LABEL", "RCPTOT", "CSTMTOT", "VALADD"],
        ["311", "Food", "100", "60", "40"],
    ]

    frame = fetch_asm_manufacturing("valid_api_key_12345", 2021)
    assert frame.loc[0, "industry_code"] == "311"
    assert frame.loc[0, "gross_output"] == 100.0


@patch("src.sources.bea.get_api_cache", return_value=None)
@patch("src.sources.bea.safe_get_json")
def test_fetch_bea(mock_get_json, _cache):
    go_response = {
        "BEAAPI": {
            "Results": {"Data": [{"Industry": "311", "IndustrYDescription": "Food", "Year": "2021", "DataValue": "100"}]}
        }
    }
    ii_response = {
        "BEAAPI": {
            "Results": {"Data": [{"Industry": "311", "IndustrYDescription": "Food", "Year": "2021", "DataValue": "60"}]}
        }
    }
    mock_get_json.side_effect = [go_response, ii_response]

    frame = fetch_go_ii_by_industry("valid_api_key_12345", 2021)
    assert "intermediate_inputs" in frame.columns
    assert frame.loc[0, "gross_output"] == 100_000_000.0
