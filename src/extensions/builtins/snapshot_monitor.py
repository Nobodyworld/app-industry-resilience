"""Observability snapshot instrumentation extension."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.core.config import load_config
from src.extensions.contracts import InstrumentationExtension
from src.extensions.manager import ExtensionManager
from src.infrastructure.observability.health import HealthComponent, HealthStatus
from src.infrastructure.observability.instrumentation import (
    ObservabilityRegistry,
    ObservationEvent,
)
from src.infrastructure.observability.storage import ObservabilitySnapshot, SnapshotStorage

_STALE_SECONDS_WARN = 24 * 60 * 60  # one day


@dataclass
class _SnapshotInstrumentation(InstrumentationExtension):
    """Expose snapshot persistence metrics and health diagnostics."""

    name: str = "snapshot_monitor"
    _storage: SnapshotStorage | None = field(default=None, init=False, repr=False)
    _latest_snapshot: ObservabilitySnapshot | None = field(default=None, init=False, repr=False)

    def register(self, registry: ObservabilityRegistry) -> None:  # noqa: D401 - interface
        config = load_config()
        storage = SnapshotStorage(config.observability_snapshot_dir)
        self._storage = storage

        count_gauge = registry.gauge(
            "idiot_index_observability_snapshots_total",
            "Number of observability snapshots stored on disk",
        )
        age_gauge = registry.gauge(
            "idiot_index_observability_snapshot_age_seconds",
            "Age of the most recent observability snapshot in seconds",
        )

        def _refresh_metrics() -> dict[str, Any]:
            snapshots = storage.list()
            count = len(snapshots)
            count_gauge.set(float(count))
            latest: ObservabilitySnapshot | None = snapshots[-1] if snapshots else None
            if latest is None:
                age_gauge.set(0.0)
            else:
                age = max(0.0, (datetime.now(UTC) - latest.captured_at).total_seconds())
                age_gauge.set(age)
            self._latest_snapshot = latest
            return {
                "count": count,
                "latest": latest,
            }

        def _on_snapshot(event: ObservationEvent) -> None:
            if event.name != "observability.snapshot.persisted":
                return
            _refresh_metrics()

        registry.subscribe("observability.snapshot.persisted", _on_snapshot)
        _refresh_metrics()

        def _health() -> HealthComponent:
            data = _refresh_metrics()
            latest_snapshot = data["latest"]
            status: HealthStatus = "pass"
            summary = "Observability snapshots healthy"
            details: dict[str, Any] = {
                "snapshot_dir": str(storage.base_dir),
                "total_snapshots": data["count"],
            }
            if latest_snapshot is None:
                status = "warn"
                summary = "No observability snapshots captured"
            else:
                age_seconds = max(
                    0.0,
                    (datetime.now(UTC) - latest_snapshot.captured_at).total_seconds(),
                )
                details["latest_snapshot_id"] = latest_snapshot.snapshot_id
                details["latest_snapshot_captured_at"] = latest_snapshot.captured_at.isoformat()
                details["latest_snapshot_age_seconds"] = age_seconds
                if age_seconds > _STALE_SECONDS_WARN:
                    status = "warn"
                    summary = "Latest snapshot is stale"

            return HealthComponent(
                name="observability_snapshots",
                status=status,
                summary=summary,
                details=details,
            )

        registry.register_health_check("observability_snapshots", _health)


def register(manager: ExtensionManager) -> None:
    manager.register_instrumentation_extension(_SnapshotInstrumentation())


__all__ = ["register"]
