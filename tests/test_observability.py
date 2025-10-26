from src.extensions.builtins import core_instrumentation
from src.extensions.manager import ExtensionManager
from src.infrastructure.observability.instrumentation import ObservabilityRegistry


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
