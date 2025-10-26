from __future__ import annotations

from pathlib import Path

import pytest

from src.core import (
    ConfigError,
    Environment,
    get_config_summary,
    load_config,
    validate_config,
)


def test_load_config_from_mapping(tmp_path) -> None:
    env = {
        "ENVIRONMENT": "production",
        "DEFAULT_YEAR": "2020",
        "BEA_API_KEY": "abc123456789",
        "CENSUS_API_KEY": "def123456789",
        "CACHE_DIR": str(tmp_path),
        "CACHE_ENABLED": "true",
    }
    config = load_config(env)

    assert config.environment is Environment.PRODUCTION
    assert config.cache.base_dir == tmp_path.resolve()
    assert config.observability_snapshot_dir == Path("build/observability_snapshots").resolve()
    assert config.default_year == 2020
    summary = get_config_summary(config)
    assert summary["bea_key_set"] is True
    assert summary["observability_snapshot_dir"].endswith("build/observability_snapshots")


def test_load_config_invalid_environment() -> None:
    with pytest.raises(ConfigError):
        load_config({"ENVIRONMENT": "unknown"})


def test_validate_config_warnings_for_missing_keys(monkeypatch) -> None:
    env = {"ENVIRONMENT": "development", "BEA_API_KEY": "", "CENSUS_API_KEY": ""}
    config = load_config(env)
    result = validate_config(config)
    assert result.errors == ()
    assert any("BEA_API_KEY" in warning for warning in result.warnings)


def test_validate_config_rejects_snapshot_file(tmp_path: Path) -> None:
    snapshot_file = tmp_path / "snapshot.json"
    snapshot_file.write_text("{}", encoding="utf-8")
    env = {"OBSERVABILITY_SNAPSHOT_DIR": str(snapshot_file)}

    config = load_config(env)
    result = validate_config(config)

    assert any("OBSERVABILITY_SNAPSHOT_DIR" in error for error in result.errors)


def test_load_config_rejects_non_http_urls() -> None:
    with pytest.raises(ConfigError) as excinfo:
        load_config({"BEA_API_BASE_URLS": "ftp://example.com"})

    message = str(excinfo.value).lower()
    assert "http" in message and "url" in message


def test_load_config_deduplicates_url_entries() -> None:
    config = load_config(
        {"BEA_API_BASE_URLS": "https://apps.bea.gov/api/data, https://apps.bea.gov/api/data"}
    )

    assert config.bea_api_base_urls == ("https://apps.bea.gov/api/data",)
