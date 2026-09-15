"""Sentinel regressions for every public Streamlit diagnostics output channel."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.core.config import load_config
from src.interfaces.streamlit.diagnostics import build_public_diagnostics

SENTINELS = (
    r"C:\Users\private\repo\cache",
    "/home/private/repo/cache",
    "relative/private/cache",
    "private-redis.internal",
    "private-redis-key-prefix",
    "private-bucket",
    "private-container",
    "private-storage-prefix",
    "https://private-endpoint.internal",
    "private-replication-destination",
    "private-error-path",
    "192.0.2.123",
)


def private_config():
    return load_config(
        {
            "CACHE_DIR": SENTINELS[0],
            "OBSERVABILITY_SNAPSHOT_DIR": SENTINELS[1],
            "RATE_LIMIT_BACKEND": "redis",
            "RATE_LIMIT_REDIS_HOST": SENTINELS[3],
            "RATE_LIMIT_REDIS_KEY_PREFIX": SENTINELS[4],
            "OBSERVABILITY_SNAPSHOT_REMOTE_ENABLED": "true",
            "OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND": "s3",
            "OBSERVABILITY_SNAPSHOT_S3_BUCKET": SENTINELS[5],
            "OBSERVABILITY_SNAPSHOT_REMOTE_PREFIX": SENTINELS[7],
            "OBSERVABILITY_SNAPSHOT_S3_ENDPOINT": SENTINELS[8],
            "OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS": json.dumps(
                {"container": SENTINELS[6], "destination": SENTINELS[9], "host": SENTINELS[11]}
            ),
            "BEA_API_KEY": "private-bea-key",  # pragma: allowlist secret - synthetic sentinel
            "CENSUS_API_KEY": "private-census-key",  # pragma: allowlist secret - synthetic sentinel
            "BEA_API_BASE_URLS": SENTINELS[8],
            "CENSUS_ASM_ENDPOINT_TEMPLATE": SENTINELS[8] + "/{year}",
        }
    )


def private_history(status="error", *, malformed=False):
    return [
        {
            "snapshot_id": SENTINELS[0],
            "captured_at": SENTINELS[1] if malformed else "2026-09-15T01:00:00Z",
            "event_total": SENTINELS[2] if malformed else 3,
            "events": {"error": SENTINELS[3] if malformed else 1, "success": 2, SENTINELS[4]: 5},
            "metadata": {"label": SENTINELS[5], "container": SENTINELS[6]},
            "metrics": {SENTINELS[7]: 3},
            "replication": {
                "status": status,
                "backend": SENTINELS[8],
                "path": SENTINELS[9],
                "destination": SENTINELS[9],
                "error": SENTINELS[10],
            },
            "last_error": {"path": SENTINELS[0], "message": SENTINELS[10]},
            "future_sensitive_field": SENTINELS[11],
        }
    ]


def assert_public_render(app):
    assert not app.exception
    # Protobufs include text, JSON, Arrow tables, metrics and Plotly figure specs.
    rendered = "\n".join(str(getattr(element, "proto", "")) for element in app)
    rendered += "\n".join(table.value.to_json() for table in app.dataframe)
    for sentinel in (*SENTINELS, "private-bea-key", "private-census-key"):
        # Windows paths may be JSON/protobuf escaped; the distinctive pieces must also be absent.
        assert sentinel not in rendered
    for fragment in ("private/", "private\\", "private-", "private."):
        assert fragment not in rendered.lower()


def test_public_config_is_an_explicit_allowlist():
    config = private_config()
    config = replace(config, normalization_dtype_overrides={"future": SENTINELS[2]})
    public = build_public_diagnostics(config)
    assert set(public) == {
        "environment",
        "log_level",
        "default_year",
        "cache_enabled",
        "cache_ttl",
        "rate_limits",
        "rate_limit_mode",
        "observability_snapshot",
        "max_csv_size_mb",
        "supported_years_bea",
        "supported_years_census",
        "bea_key_set",
        "census_key_set",
        "bea_api_version",
    }
    assert set(public["rate_limits"]) == {"bea", "census", "default"}
    assert set(public["observability_snapshot"]) == {
        "retention_count",
        "retention_days",
        "min_interval_seconds",
    }
    assert set(public["cache_ttl"]) == {"api", "computation"}
    assert public["bea_key_set"] is True and public["census_key_set"] is True
    assert "private" not in json.dumps(public)
    # The internal configuration still retains the operator's infrastructure data.
    assert config.cache.base_dir == Path(SENTINELS[0]).resolve()
    assert config.rate_limits.distributed.host == SENTINELS[3]
    assert config.rate_limits.distributed.key_prefix == SENTINELS[4]


@pytest.mark.parametrize("value", SENTINELS)
def test_free_text_config_values_are_not_public(value):
    public = build_public_diagnostics(
        replace(private_config(), log_level=value, bea_api_version=value)
    )
    assert public["log_level"] == "unknown"
    assert public["bea_api_version"] == "default"


@pytest.mark.parametrize("version", [None, "1", "v2.1"])
def test_public_provider_version(version):
    assert build_public_diagnostics(replace(private_config(), bea_api_version=version))[
        "bea_api_version"
    ] == (version or "default")


@pytest.mark.parametrize("status", ["success", "error", "private-status", None])
@pytest.mark.parametrize("malformed", [False, True])
def test_observability_render_cannot_forward_private_payloads(status, malformed):
    def render(history):
        from src.interfaces.streamlit.components import render_observability_snapshots

        render_observability_snapshots(history)

    app = AppTest.from_function(render, args=(private_history(status, malformed=malformed),)).run()
    assert_public_render(app)
    assert (
        app.warning[0].value
        == "A recent error was recorded. Details are available to the application operator."
    )
    assert list(app.dataframe[0].value.columns) == [
        "Captured",
        "Events",
        "Errors",
        "Success",
        "Replication",
    ]
    if status == "success":
        assert app.success[0].value == "Latest snapshot replication succeeded."
    elif status == "error":
        assert (
            app.error[0].value
            == "Latest snapshot replication failed. Contact the application operator."
        )


@pytest.mark.parametrize(
    "history",
    [
        [],
        [{"events": None}],
        [{"events": {"error": float("nan"), "success": -1}, "event_total": float("inf")}],
    ],
)
def test_public_observability_missing_values(history):
    def render(history):
        from src.interfaces.streamlit.components import render_observability_snapshots

        render_observability_snapshots(history)

    app = AppTest.from_function(render, args=(history,)).run()
    assert_public_render(app)


@pytest.mark.parametrize("history", [[], private_history()])
def test_application_technical_diagnostics_are_public(monkeypatch, history):
    from src.core import SecurityUtils
    from src.core.config import ConfigValidationResult
    from src.interfaces.streamlit import bootstrap, helpers

    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    state = bootstrap.BootstrapState(private_config(), ConfigValidationResult())
    monkeypatch.setattr(bootstrap, "get_bootstrap_state", lambda: state)
    monkeypatch.setattr(helpers, "load_snapshot_history", lambda *args, **kwargs: history)
    monkeypatch.setattr(
        SecurityUtils,
        "rate_limit_handler_summary",
        lambda: {"backend": "redis", "host": SENTINELS[3], "last_error": {"path": SENTINELS[0]}},
    )
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
    assert_public_render(app)
    assert app.sidebar.json


def test_configuration_failures_hide_raw_operator_details(monkeypatch):
    from src.interfaces.streamlit import bootstrap

    def failed():
        raise bootstrap.BootstrapError(SENTINELS[0])

    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    monkeypatch.setattr(bootstrap, "get_bootstrap_state", failed)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
    assert_public_render(app)
    assert "Contact the application operator" in app.error[0].value
