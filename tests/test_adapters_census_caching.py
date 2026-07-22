from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.adapters.census_asm import fetch_asm_manufacturing
from src.core.cache import Cache
from src.core.lineage import lineage_from_dataframe


def test_fetch_asm_manufacturing_caches(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache", ttl_seconds=60)

    def fake_cache(_cfg):
        return cache

    config = SimpleNamespace(
        supported_years_census=range(2010, 2030),
        cache=None,
        census_asm_endpoint_template="https://api.census.gov/data/{year}/asm",
    )

    responses = [
        [
            ["NAICS2017", "NAICS2017_LABEL", "RCPTOT", "CSTMTOT", "VALADD"],
            ["311", "Food", "100", "60", "40"],
        ]
    ]

    acquired_at = datetime(2026, 7, 21, 13, 0, tzinfo=UTC)
    with (
        patch("src.adapters.census_asm.load_config", return_value=config),
        patch("src.adapters.census_asm.get_api_cache", side_effect=fake_cache),
        patch("src.adapters.census_asm.safe_get_json", side_effect=responses) as mock_get,
        patch("src.adapters.census_asm.datetime") as clock,
    ):
        clock.now.return_value = acquired_at
        frame = fetch_asm_manufacturing("valid_api_key_12345", 2020)
        assert cache.stats().files >= 1
        assert frame.loc[0, "industry_code"] == "311"
        miss_lineage = lineage_from_dataframe(frame)
        assert miss_lineage is not None
        assert miss_lineage.source == "census"
        assert miss_lineage.source_kind.value == "live_provider"
        assert miss_lineage.dataset_id == "asm"
        assert miss_lineage.provider == "U.S. Census Bureau"
        assert miss_lineage.observation_period == "2020"
        assert miss_lineage.acquired_at == acquired_at
        assert miss_lineage.retrieval_mode.value == "live"
        assert miss_lineage.cache_status.value == "miss"
        assert miss_lineage.is_official is True

        cached_payload = cache.get("census_asm_2020")
        assert isinstance(cached_payload, dict)
        serialized_lineage = json.dumps(cached_payload["lineage"])
        assert "valid_api_key_12345" not in serialized_lineage
        assert "cache" not in serialized_lineage.casefold().replace('"cache_status": "miss"', "")
        assert "RCPTOT" not in serialized_lineage
        # second call should be served from the cache and not call safe_get_json again
        cached = fetch_asm_manufacturing("valid_api_key_12345", 2020)
        # safe_get_json call count should be 1 due to caching
        assert mock_get.call_count == 1
        hit_lineage = lineage_from_dataframe(cached)
        assert hit_lineage is not None
        assert hit_lineage.source == miss_lineage.source
        assert hit_lineage.acquired_at == miss_lineage.acquired_at
        assert hit_lineage.transformations == miss_lineage.transformations
        assert hit_lineage.retrieval_mode.value == "cache"
        assert hit_lineage.cache_status.value == "hit"


def test_fetch_asm_reads_legacy_cache_without_lineage(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache", ttl_seconds=60)
    cache.set(
        "census_asm_2020",
        {
            "records": [{"industry_code": "311", "gross_output": 100.0}],
            "metadata": {"year": 2020},
        },
    )
    config = SimpleNamespace(
        supported_years_census=range(2010, 2030),
        cache=None,
        census_asm_endpoint_template="https://api.census.gov/data/{year}/asm",
    )

    with (
        patch("src.adapters.census_asm.load_config", return_value=config),
        patch("src.adapters.census_asm.get_api_cache", return_value=cache),
        patch("src.adapters.census_asm.safe_get_json") as mock_get,
    ):
        frame = fetch_asm_manufacturing("valid_api_key_12345", 2020)

    assert frame.loc[0, "industry_code"] == "311"
    assert lineage_from_dataframe(frame) is None
    mock_get.assert_not_called()
