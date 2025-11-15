from __future__ import annotations

from pathlib import Path

import pytest

from src.core.config import (
    DEFAULT_CENSUS_ASM_ENDPOINT_TEMPLATE,
    AppConfig,
    CacheConfig,
    ConfigValidationResult,
    Environment,
    RateLimitConfig,
)
from src.extensions.contracts import ExtensionContributions, SummaryExtension
from src.extensions.manager import ExtensionManager
from src.infrastructure.observability.health import build_default_probe


class _DummySummaryExtension(SummaryExtension):
    name = "dummy"

    def contribute(self, summary) -> ExtensionContributions:  # type: ignore[override]
        return ExtensionContributions(notes=("ok",), metadata={"note": "value"})


@pytest.fixture()
def configured_probe(tmp_path: Path):
    cache_dir = tmp_path / "cache"
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
            enabled=True,
            base_dir=cache_dir,
            api_ttl_seconds=60,
            computation_ttl_seconds=120,
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
    manager.register_summary_extension(_DummySummaryExtension())

    probe = build_default_probe(
        config_loader=lambda: config,
        config_validator=lambda cfg: ConfigValidationResult(),
        summary_builder=lambda cfg: {"environment": cfg.environment.value},
        telemetry_snapshot=lambda: {"metrics": {"counters": 1}},
        extension_manager_provider=lambda: manager,
    )
    return probe


def test_build_default_probe_reports_components(configured_probe) -> None:
    report = configured_probe.snapshot()

    assert report.status == "pass"
    component_names = {component.name for component in report.components}
    assert component_names == {"configuration", "cache", "extensions"}
    assert report.metadata["config"]["environment"] == "development"
    assert report.metadata["telemetry"]["metrics"]["counters"] == 1
    serialised = report.as_dict()
    assert serialised["status"] == "pass"
    assert any(component["name"] == "cache" for component in serialised["components"])


def test_health_cli_warn_exit(monkeypatch, capsys) -> None:
    class _DummyReport:
        status = "warn"

        def as_dict(self) -> dict[str, str]:
            return {"status": self.status}

    class _DummyProbe:
        def snapshot(self) -> _DummyReport:
            return _DummyReport()

    from scripts import check_health

    monkeypatch.setattr(check_health, "build_default_probe", lambda *_, **__: _DummyProbe())

    code = check_health.main(["--pretty"])
    output = capsys.readouterr().out

    assert code == 1
    assert '"status": "warn"' in output
