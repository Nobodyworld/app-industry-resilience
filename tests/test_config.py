from __future__ import annotations

import json
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
    assert config.census_asm_endpoint_template == "https://api.census.gov/data/{year}/asm"
    summary = get_config_summary(config)
    assert summary["bea_key_set"] is True
    snapshot_summary = summary["observability_snapshot"]
    expected_suffix = str(Path("build/observability_snapshots"))
    assert snapshot_summary["dir"].endswith(expected_suffix)
    assert snapshot_summary["retention_count"] == 20
    assert snapshot_summary["retention_days"] == 30
    assert snapshot_summary["min_interval_seconds"] == 600.0


def test_load_config_invalid_environment() -> None:
    with pytest.raises(ConfigError):
        load_config({"ENVIRONMENT": "unknown"})


def test_load_config_allows_custom_census_template() -> None:
    template = "https://example.com/asm/{year}?variant=beta"
    config = load_config({"CENSUS_ASM_ENDPOINT_TEMPLATE": template})

    assert config.census_asm_endpoint_template == template


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


def test_validate_config_rejects_census_template_without_year() -> None:
    config = load_config({"CENSUS_ASM_ENDPOINT_TEMPLATE": "https://example.com/static"})

    result = validate_config(config)

    assert any("CENSUS_ASM_ENDPOINT_TEMPLATE" in error for error in result.errors)


def test_validate_config_rejects_census_template_with_extra_placeholders() -> None:
    config = load_config({"CENSUS_ASM_ENDPOINT_TEMPLATE": "https://example.com/{region}/{year}"})

    result = validate_config(config)

    errors = "\n".join(result.errors)
    assert "only supports" in errors and "{year}" in errors


def test_validate_config_rejects_negative_snapshot_settings() -> None:
    config = load_config(
        {
            "OBSERVABILITY_SNAPSHOT_RETENTION_COUNT": "-1",
            "OBSERVABILITY_SNAPSHOT_RETENTION_DAYS": "-5",
            "OBSERVABILITY_SNAPSHOT_MIN_INTERVAL_SECONDS": "-1",
        }
    )

    result = validate_config(config)
    errors = "\n".join(result.errors)
    assert "RETENTION_COUNT" in errors
    assert "RETENTION_DAYS" in errors
    assert "MIN_INTERVAL_SECONDS" in errors


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


def test_load_config_applies_snapshot_retention_env(tmp_path: Path) -> None:
    env = {
        "OBSERVABILITY_SNAPSHOT_DIR": str(tmp_path),
        "OBSERVABILITY_SNAPSHOT_RETENTION_COUNT": "3",
        "OBSERVABILITY_SNAPSHOT_RETENTION_DAYS": "5",
        "OBSERVABILITY_SNAPSHOT_MIN_INTERVAL_SECONDS": "120",
    }

    config = load_config(env)

    assert config.observability_snapshot_retention_count == 3
    assert config.observability_snapshot_retention_days == 5
    assert config.observability_snapshot_min_interval_seconds == 120.0


def test_load_config_parses_remote_snapshot_settings() -> None:
    env = {
        "OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND": "s3",
        "OBSERVABILITY_SNAPSHOT_S3_BUCKET": "idiot-index-snapshots",
        "OBSERVABILITY_SNAPSHOT_S3_PREFIX": "nightly/",
        "OBSERVABILITY_SNAPSHOT_S3_REGION": "us-east-1",
        "OBSERVABILITY_SNAPSHOT_S3_ENDPOINT": "https://s3.example.com",
        "OBSERVABILITY_SNAPSHOT_S3_ACCESS_KEY": "abc",
        "OBSERVABILITY_SNAPSHOT_S3_SECRET_KEY": "xyz",
        "OBSERVABILITY_SNAPSHOT_S3_SESSION_TOKEN": "token",
        "OBSERVABILITY_SNAPSHOT_S3_USE_SSL": "true",
        "OBSERVABILITY_SNAPSHOT_S3_FORCE_PATH_STYLE": "yes",
        "OBSERVABILITY_SNAPSHOT_REMOTE_MAX_RETRIES": "4",
    }

    config = load_config(env)

    remote = config.observability_snapshot_remote
    assert remote is not None
    assert remote.enabled is True
    assert remote.backend == "s3"
    assert remote.bucket == "idiot-index-snapshots"
    assert remote.prefix == "nightly/"
    assert remote.region == "us-east-1"
    assert remote.endpoint_url == "https://s3.example.com"
    assert remote.access_key == "abc"
    assert remote.secret_key == "xyz"
    assert remote.session_token == "token"
    assert remote.use_ssl is True
    assert remote.force_path_style is True
    assert remote.max_retries == 4
    assert remote.options is None


def test_load_config_parses_gcs_remote_snapshot_settings() -> None:
    env = {
        "OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND": "gcs",
        "OBSERVABILITY_SNAPSHOT_GCS_BUCKET": "idiot-index-gcs",
        "OBSERVABILITY_SNAPSHOT_GCS_PREFIX": "cloud/",
        "OBSERVABILITY_SNAPSHOT_REMOTE_MAX_RETRIES": "2",
        "OBSERVABILITY_SNAPSHOT_GCS_PROJECT": "idiot-index",
        "OBSERVABILITY_SNAPSHOT_GCS_TIMEOUT_SECONDS": "15",
    }

    config = load_config(env)

    remote = config.observability_snapshot_remote
    assert remote is not None
    assert remote.backend == "gcs"
    assert remote.bucket == "idiot-index-gcs"
    assert remote.prefix == "cloud/"
    assert remote.max_retries == 2
    assert remote.options is not None
    assert remote.options.get("project") == "idiot-index"
    assert remote.options.get("timeout_seconds") == 15.0


def test_validate_config_rejects_remote_without_bucket() -> None:
    config = load_config({"OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND": "s3"})

    result = validate_config(config)

    assert any("S3_BUCKET" in error for error in result.errors)


def test_validate_config_rejects_gcs_without_bucket() -> None:
    config = load_config({"OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND": "gcs"})

    result = validate_config(config)

    assert any("GCS_BUCKET" in error for error in result.errors)


def test_config_summary_masks_remote_secrets() -> None:
    env = {
        "OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND": "s3",
        "OBSERVABILITY_SNAPSHOT_S3_BUCKET": "idiot-index-snapshots",
        "OBSERVABILITY_SNAPSHOT_S3_ACCESS_KEY": "abc",
        "OBSERVABILITY_SNAPSHOT_S3_SECRET_KEY": "xyz",
    }

    config = load_config(env)
    summary = get_config_summary(config)

    remote_summary = summary["observability_snapshot_remote"]
    assert remote_summary["enabled"] is True
    assert remote_summary["bucket"] == "idiot-index-snapshots"
    assert remote_summary["has_access_key"] is True
    assert remote_summary["has_secret_key"] is True
    assert remote_summary["options_keys"] == []
    assert "abc" not in str(remote_summary)


def test_load_config_parses_azure_remote_snapshot_settings() -> None:
    env = {
        "OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND": "azure-blob",
        "OBSERVABILITY_SNAPSHOT_AZURE_CONTAINER": "snapshots",
        "OBSERVABILITY_SNAPSHOT_AZURE_PREFIX": "nightly/",
        "OBSERVABILITY_SNAPSHOT_AZURE_CONNECTION_STRING": "UseDevelopmentStorage=true",
        "OBSERVABILITY_SNAPSHOT_REMOTE_MAX_RETRIES": "5",
    }

    config = load_config(env)

    remote = config.observability_snapshot_remote
    assert remote is not None
    assert remote.backend == "azure-blob"
    assert remote.bucket == "snapshots"
    assert remote.prefix == "nightly/"
    assert remote.max_retries == 5
    assert remote.options is not None
    assert remote.options.get("connection_string") == "UseDevelopmentStorage=true"


def test_validate_config_rejects_azure_without_container() -> None:
    config = load_config({"OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND": "azure-blob"})

    result = validate_config(config)

    assert any("AZURE_CONTAINER" in error for error in result.errors)


def test_load_config_parses_plugin_backend_options(tmp_path: Path) -> None:
    options = {"path": str(tmp_path / "replicas"), "mode": "mirror"}
    env = {
        "OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND": "plugin:debug",
        "OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS": json.dumps(options),
        "OBSERVABILITY_SNAPSHOT_REMOTE_MAX_RETRIES": "0",
    }

    config = load_config(env)

    remote = config.observability_snapshot_remote
    assert remote is not None
    assert remote.backend == "plugin:debug"
    assert remote.bucket is None
    assert remote.prefix == ""
    assert remote.options == options
    assert remote.max_retries == 0


def test_load_config_rejects_invalid_remote_options() -> None:
    env = {
        "OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND": "plugin:test",
        "OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS": "[]",
    }

    with pytest.raises(ConfigError):
        load_config(env)


def test_validate_config_accepts_plugin_backend(tmp_path: Path) -> None:
    env = {
        "OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND": "plugin:debug",
        "OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS": json.dumps({"path": str(tmp_path)}),
    }

    config = load_config(env)
    result = validate_config(config)

    assert result.errors == ()
