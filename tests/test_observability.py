import json
from pathlib import Path

import pytest

from src.extensions.builtins import core_instrumentation
from src.extensions.manager import ExtensionManager, load_extensions
from src.infrastructure.observability import instrumentation as instrumentation_mod
from src.infrastructure.observability.instrumentation import (
    ObservabilityRegistry,
    bootstrap_observability,
)
from src.infrastructure.observability.storage import SnapshotStorage


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


def test_events_method_filters_and_limits() -> None:
    registry = ObservabilityRegistry()
    registry.record_event("service.dataset.profile", attributes={"source": "sample"})

    with pytest.raises(RuntimeError):
        with registry.operation("service.failure", attributes={"source": "sample"}):
            raise RuntimeError("boom")

    all_events = registry.events()
    assert all_events
    assert all_events[0]["status"] == "error"
    assert all_events[0]["name"] == "service.failure"

    success_events = registry.events(status="success")
    assert all(event["status"] == "success" for event in success_events)

    error_events = registry.events(status="ERROR")
    assert len(error_events) == 1
    assert error_events[0]["error"] == "RuntimeError('boom')"

    limited_events = registry.events(limit=1)
    assert len(limited_events) == 1
    assert limited_events[0]["status"] == "error"


def test_registry_persist_snapshot_roundtrip(tmp_path: Path) -> None:
    registry = ObservabilityRegistry()
    storage = SnapshotStorage(tmp_path)

    registry.record_event("service.dataset.profile", attributes={"source": "sample"})
    snapshot = registry.persist_snapshot(storage, metadata={"source": "unit"})

    assert snapshot.metadata["source"] == "unit"

    stored_path = storage.base_dir / f"{snapshot.snapshot_id}.json"
    assert stored_path.exists()

    loaded = storage.get(snapshot.snapshot_id)
    assert loaded.snapshot_id == snapshot.snapshot_id
    assert loaded.metadata == snapshot.metadata
    assert loaded.payload["events"]["total"] >= 1


def test_persist_snapshot_emits_observability_event(tmp_path: Path) -> None:
    registry = ObservabilityRegistry()
    storage = SnapshotStorage(tmp_path)
    captured: list[dict[str, object]] = []

    def _capture(event) -> None:
        captured.append(event.as_dict())

    registry.subscribe("observability.snapshot.persisted", _capture)
    snapshot = registry.persist_snapshot(storage, metadata={"source": "unit"})

    assert captured
    payload = captured[-1]
    assert payload["name"] == "observability.snapshot.persisted"
    assert payload["attributes"]["snapshot_id"] == snapshot.snapshot_id
    assert payload["attributes"]["storage_dir"] == str(storage.base_dir)


def test_snapshot_storage_rejects_invalid_identifier(tmp_path: Path) -> None:
    storage = SnapshotStorage(tmp_path)

    with pytest.raises(ValueError):
        storage.get("../invalid")

    with pytest.raises(ValueError):
        storage.path_for("bad/id")


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


def test_snapshot_monitor_extension_tracks_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OBSERVABILITY_SNAPSHOT_DIR", str(tmp_path))
    registry = ObservabilityRegistry()
    manager = ExtensionManager()
    load_extensions(manager, ["src.extensions.builtins.snapshot_monitor"])
    manager.apply_instrumentation_extensions(registry)

    component = registry._health_checks["observability_snapshots"]()
    assert component.status == "warn"
    assert component.details["total_snapshots"] == 0

    storage = SnapshotStorage(tmp_path)
    registry.persist_snapshot(storage, metadata={"label": "unit"})

    updated = registry._health_checks["observability_snapshots"]()
    assert updated.details["total_snapshots"] >= 1
    assert updated.status in {"pass", "warn"}


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
