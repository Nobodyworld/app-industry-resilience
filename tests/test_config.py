from __future__ import annotations

import pytest

from src.config import ConfigError, Environment, get_config_summary, load_config, validate_config


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
    assert config.default_year == 2020
    summary = get_config_summary(config)
    assert summary["bea_key_set"] is True


def test_load_config_invalid_environment() -> None:
    with pytest.raises(ConfigError):
        load_config({"ENVIRONMENT": "unknown"})


def test_validate_config_warnings_for_missing_keys(monkeypatch) -> None:
    env = {"ENVIRONMENT": "development", "BEA_API_KEY": "", "CENSUS_API_KEY": ""}
    config = load_config(env)
    result = validate_config(config)
    assert result.errors == ()
    assert any("BEA_API_KEY" in warning for warning in result.warnings)
