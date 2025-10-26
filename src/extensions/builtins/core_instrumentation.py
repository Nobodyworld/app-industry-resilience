"""Built-in instrumentation extension ensuring baseline observability."""

from __future__ import annotations

from dataclasses import dataclass

from src.extensions.contracts import InstrumentationExtension
from src.extensions.manager import ExtensionManager
from src.infrastructure.observability.health import HealthComponent, HealthStatus
from src.infrastructure.observability.instrumentation import ObservabilityRegistry, ObservationEvent

_LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10)


@dataclass
class _CoreInstrumentationExtension(InstrumentationExtension):
    name: str = "core_instrumentation"

    def register(self, registry: ObservabilityRegistry) -> None:
        counter = registry.counter(
            "idiot_index_pipeline_runs_total",
            "Total Idiot Index operations executed",
            label_names=("operation", "status", "source"),
        )
        histogram = registry.histogram(
            "idiot_index_pipeline_duration_seconds",
            "Duration of Idiot Index operations",
            label_names=("operation", "source"),
            buckets=_LATENCY_BUCKETS,
        )

        def _record(event: ObservationEvent) -> None:
            source = str(event.attributes.get("source", "unknown"))
            counter.increment(
                labels={
                    "operation": event.name,
                    "status": event.status,
                    "source": source,
                }
            )
            histogram.observe(
                event.duration,
                labels={"operation": event.name, "source": source},
            )

        registry.subscribe("service.idiot_index.evaluate", _record)
        registry.subscribe("service.scenario.plan", _record)

        def _health() -> HealthComponent:
            metrics = registry.metrics_summary()
            events = registry.recent_events()[-5:]
            status: HealthStatus = "pass"
            summary = "Observability registry active"
            if metrics["counters"] == 0:
                status = "warn"
                summary = "Observability registry has no registered counters"
            details = {
                "metrics": metrics,
                "recent_events": events,
            }
            return HealthComponent(
                name="instrumentation_core",
                status=status,
                summary=summary,
                details=details,
            )

        registry.register_health_check("instrumentation_core", _health)


def register(manager: ExtensionManager) -> None:
    manager.register_instrumentation_extension(_CoreInstrumentationExtension())


__all__ = ["register"]
