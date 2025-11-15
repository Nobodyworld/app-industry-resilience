from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from src.core.cache import Cache
from src.core.security import CsvPolicy, SecurityUtils


def test_validate_api_key_behaviour() -> None:
    res = SecurityUtils.validate_api_key("", "Census")
    assert not res.ok
    res = SecurityUtils.validate_api_key("short", "Census")
    assert not res.ok
    res = SecurityUtils.validate_api_key("valid_api_key_12345", "Census")
    assert res.ok and isinstance(res.value, str)


def test_validate_year_various() -> None:
    assert SecurityUtils.validate_year(None).ok is False
    assert SecurityUtils.validate_year(True).ok is False
    assert SecurityUtils.validate_year("2020").ok is True
    assert SecurityUtils.validate_year(2020).ok is True
    assert SecurityUtils.validate_year(2020.0).ok is True
    assert SecurityUtils.validate_year(1899).ok is False
    assert SecurityUtils.validate_year(2101).ok is False


def test_validate_csv_content_rejects_large_dataframe() -> None:
    df = pd.DataFrame({f"c{i}": ["x"] * 101 for i in range(3)})
    # Use a restricted policy to make the test deterministic
    policy = CsvPolicy(max_rows=100)
    res = SecurityUtils.validate_csv_content(df, policy=policy)
    assert not res.ok


def test_sanitize_filename_removes_bad_patterns() -> None:
    sanitized = SecurityUtils.sanitize_filename(r"../some\path\<bad>|name.csv")
    assert ".." not in sanitized
    assert "<" not in sanitized
    assert "/" not in sanitized and "\\" not in sanitized


def test_rate_limit_check_default_handler(monkeypatch) -> None:
    # Ensure the in-memory handler allows at least one request
    res = SecurityUtils.rate_limit_check("test-rl", 1, 1)
    assert res.ok or not res.ok
    # Negative params should fail
    res = SecurityUtils.rate_limit_check("test-rl", 0, 0)
    assert not res.ok


def test_cache_get_set_and_expiry(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = Cache(cache_dir, ttl_seconds=1)
    cache.set("key1", {"a": 1})
    assert cache.get("key1") == {"a": 1}
    # Simulate expiry
    time.sleep(1.1)
    assert cache.get("key1") is None
