from __future__ import annotations

from types import SimpleNamespace

from src.core.config import (
    DEFAULT_CENSUS_ASM_ENDPOINT_TEMPLATE,
    AppConfig,
    CacheConfig,
    Environment,
    RateLimitConfig,
)
from src.extensions.builtins.rate_limiting import _RateLimitingInstrumentation
from src.extensions.manager import ExtensionManager
from src.infrastructure.observability.health import build_default_probe
from src.infrastructure.observability.instrumentation import ObservabilityRegistry


def test_rate_limiting_health_probe_warns_on_redis_fallback(monkeypatch, tmp_path) -> None:
    # Build a config with redis settings (not actually used by the limiter status in test)
    config = AppConfig(
        environment=Environment.DEVELOPMENT,
        log_level="INFO",
        default_year=2024,
        bea_api_key="test",
        census_api_key="test",
        bea_api_version="v1",
        bea_api_base_urls=("https://example.test/api",),
        census_asm_endpoint_template=DEFAULT_CENSUS_ASM_ENDPOINT_TEMPLATE,
        rate_limits=RateLimitConfig(bea=10, census=10, default=10),
        cache=CacheConfig(
            enabled=True, base_dir=tmp_path, api_ttl_seconds=60, computation_ttl_seconds=120
        ),
        observability_snapshot_dir=tmp_path / "snapshots",
        observability_snapshot_retention_count=5,
        observability_snapshot_retention_days=7,
        observability_snapshot_min_interval_seconds=0.0,
        observability_snapshot_remote=None,
        max_csv_size_mb=25,
        supported_years_bea=range(2020, 2026),
        supported_years_census=range(2020, 2026),
    )

    manager = ExtensionManager()
    manager.register_instrumentation_extension(_RateLimitingInstrumentation())
    registry = ObservabilityRegistry()
    manager.apply_instrumentation_extensions(registry)

    class _FakeLimiter:
        def status(self):
            return {"mode": "redis-fallback", "last_error": "connection refused"}

    # Replace get_api_limiter used by health probe with an object that reports fallback
    monkeypatch.setattr(
        "src.extensions.builtins.rate_limiting.get_api_limiter", lambda: _FakeLimiter()
    )
    monkeypatch.setattr(
        "src.extensions.builtins.rate_limiting.SecurityUtils",
        SimpleNamespace(rate_limit_handler_summary=lambda: {"backend": "redis-fallback"}),
    )

    probe = build_default_probe(
        config_loader=lambda: config,
        config_validator=lambda cfg: SimpleNamespace(errors=(), warnings=()),
        summary_builder=lambda cfg: {"environment": cfg.environment.value},
        telemetry_snapshot=lambda: {"metrics": {"counters": 1}},
        extension_manager_provider=lambda: manager,
    )

    # Bind the probe to the registry so instrumentation health checks are added
    registry.bind_probe(probe)
    report = probe.snapshot()
    components = {c.name: c for c in report.components}
    assert "rate_limiting" in components
    assert components["rate_limiting"].status == "warn"
