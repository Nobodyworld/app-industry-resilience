from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.adapters.census_asm import fetch_asm_manufacturing
from src.core.cache import Cache


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

    with (
        patch("src.adapters.census_asm.load_config", return_value=config),
        patch("src.adapters.census_asm.get_api_cache", side_effect=fake_cache),
        patch("src.adapters.census_asm.safe_get_json", side_effect=responses) as mock_get,
    ):
        frame = fetch_asm_manufacturing("valid_api_key_12345", 2020)
        assert cache.stats().files >= 1
        assert frame.loc[0, "industry_code"] == "311"
        # second call should be served from the cache and not call safe_get_json again
        fetch_asm_manufacturing("valid_api_key_12345", 2020)
        # safe_get_json call count should be 1 due to caching
        assert mock_get.call_count == 1
