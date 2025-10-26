import json

import pytest

from src.extensions.builtins import core_instrumentation
from src.extensions.manager import ExtensionManager, load_extensions
from src.infrastructure.observability import instrumentation as instrumentation_mod
from src.infrastructure.observability.instrumentation import (
    ObservabilityRegistry,
    bootstrap_observability,
)


def test_operation_emits_events_and_records_recent_history() -> None:
    registry = ObservabilityRegistry()
    captured: list[str] = []

    def _capture(event) -> None:
        captured.append(event.status)

    registry.subscribe("service.idiot_index.evaluate", _capture)
    with registry.operation("service.idiot_index.evaluate", attributes={"source": "sample"}):
        pass

    assert captured == ["success"]
    events = registry.recent_events()
    assert events and events[0]["name"] == "service.idiot_index.evaluate"
    assert "timestamp" in events[0]
    overview = registry.health_overview()
    assert overview["event_counters"]["success"] == 1


def test_record_event_emits_without_context() -> None:
    registry = ObservabilityRegistry()

    registry.record_event("service.dataset.profile", attributes={"source": "sample"})

    events = registry.recent_events()
    assert events and events[0]["status"] == "success"
    assert registry.tracer.last_span() is not None
    assert registry.tracer.last_span().name == "service.dataset.profile"


def test_core_instrumentation_registers_metrics_and_health() -> None:
    registry = ObservabilityRegistry()
    manager = ExtensionManager()
    core_instrumentation.register(manager)
    manager.apply_instrumentation_extensions(registry)

    with registry.operation("service.idiot_index.evaluate", attributes={"source": "sample"}):
        pass

    overview = registry.health_overview()
    assert overview["metrics"]["counters"] >= 1
    assert "instrumentation_core" in overview["registered_health_checks"]
    assert overview["event_counters"]["success"] >= 1


def test_digest_tracks_errors_and_last_error() -> None:
    registry = ObservabilityRegistry()
    with pytest.raises(RuntimeError):
        with registry.operation("service.test", attributes={"source": "sample"}):
            raise RuntimeError("boom")

    digest = registry.digest()
    assert digest["events"]["counts"]["error"] == 1
    assert digest["events"]["total"] == 1
    assert digest["events"]["last_error"]["error"] == "RuntimeError('boom')"


def test_observability_tail_cli_once(monkeypatch, capsys) -> None:
    instrumentation_mod._REGISTRY_SINGLETON = None  # reset singleton
    registry = bootstrap_observability()
    manager = ExtensionManager()
    core_instrumentation.register(manager)
    manager.apply_instrumentation_extensions(registry)

    with registry.operation("service.cli", attributes={"source": "unit"}):
        pass

    from scripts import observability_tail

    exit_code = observability_tail.main(["--once", "--json"])
    output = capsys.readouterr().out.strip()

    assert exit_code == 0
    payload = json.loads(output)
    assert payload["name"] == "service.cli"
    assert payload["status"] == "success"


def test_data_quality_extension_health() -> None:
    registry = ObservabilityRegistry()
    manager = ExtensionManager()
    load_extensions(manager, ["src.extensions.builtins.data_quality"])
    manager.apply_instrumentation_extensions(registry)

    # No dataset events yet -> warn
    component = registry._health_checks["data_quality"]()
    assert component.status == "warn"

    dataset_attributes = {
        "source": "sample",
        "year": 2024,
        "full_rows": 10,
        "filtered_rows": 8,
        "full_missing_ratio": 0.0,
        "filtered_missing_ratio": 0.1,
        "filtered_missing_columns": [],
    }
    registry.record_event("service.dataset.profile", attributes=dataset_attributes)

    component = registry._health_checks["data_quality"]()
    assert component.status == "pass"

    scenario_attributes = {
        "source": "sample",
        "adjustments": 1,
        "baseline_rows": 8,
        "scenario_rows": 8,
        "delta_rows": 8,
        "baseline_missing_ratio": 0.1,
        "scenario_missing_ratio": 0.3,
        "delta_missing_ratio": 0.2,
    }
    registry.record_event("service.scenario.profile", attributes=scenario_attributes)

    component = registry._health_checks["data_quality"]()
    assert component.status == "warn"
