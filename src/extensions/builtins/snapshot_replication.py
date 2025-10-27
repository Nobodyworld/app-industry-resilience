"""Replication extensions and instrumentation for snapshot shipping."""

from __future__ import annotations

import logging
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.core import SnapshotRemoteStorageConfig, load_config
from src.extensions.contracts import InstrumentationExtension, ReplicationExtension
from src.extensions.manager import ExtensionManager
from src.infrastructure.observability.health import HealthComponent
from src.infrastructure.observability.instrumentation import (
    ObservabilityRegistry,
    ObservationEvent,
)
from src.infrastructure.observability.replication import (
    SnapshotReplicationError,
    SnapshotReplicator,
    create_s3_snapshot_replicator,
)
from src.infrastructure.observability.storage import ObservabilitySnapshot

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _DebugSnapshotReplicator:
    """Replicator that mirrors snapshots into a local debug directory."""

    target_dir: Path

    def replicate(self, snapshot: ObservabilitySnapshot, path: Path) -> None:
        destination = self.target_dir / f"{snapshot.snapshot_id}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            destination.write_bytes(path.read_bytes())
        except OSError as exc:  # pragma: no cover - defensive logging
            LOGGER.warning(
                "Failed to write snapshot to debug replication directory",
                extra={"target": str(destination)},
                exc_info=True,
            )
            raise SnapshotReplicationError(str(exc)) from exc

    def close(self) -> None:  # noqa: D401 - interface requirement
        return None


@dataclass(slots=True)
class _S3ReplicationExtension(ReplicationExtension):
    name: str = "snapshot_replication_s3"

    def supports(self, config: SnapshotRemoteStorageConfig) -> bool:
        return (config.backend or "").lower() == "s3"

    def build(self, config: SnapshotRemoteStorageConfig) -> SnapshotReplicator:
        return create_s3_snapshot_replicator(config)


@dataclass(slots=True)
class _DebugReplicationExtension(ReplicationExtension):
    name: str = "snapshot_replication_debug"

    def supports(self, config: SnapshotRemoteStorageConfig) -> bool:
        backend = (config.backend or "").lower()
        return backend in {"debug", "plugin:debug"}

    def build(self, config: SnapshotRemoteStorageConfig) -> SnapshotReplicator:
        options: Mapping[str, Any] = config.options or {}
        custom_path = options.get("path")
        if custom_path:
            target_dir = Path(str(custom_path)).expanduser()
        else:
            base_dir = load_config().observability_snapshot_dir
            target_dir = base_dir / "debug-replication"
        target_dir.mkdir(parents=True, exist_ok=True)
        return _DebugSnapshotReplicator(target_dir=target_dir)


@dataclass
class _SnapshotReplicationInstrumentation(InstrumentationExtension):
    name: str = "snapshot_replication_observer"
    _counter: Any = field(default=None, init=False, repr=False)
    _latency: Any = field(default=None, init=False, repr=False)
    _age: Any = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _last_status: str = field(default="skipped", init=False, repr=False)
    _last_backend: str = field(default="none", init=False, repr=False)
    _last_error: str | None = field(default=None, init=False, repr=False)
    _last_event_at: datetime | None = field(default=None, init=False, repr=False)
    _last_success_at: datetime | None = field(default=None, init=False, repr=False)

    def register(self, registry: ObservabilityRegistry) -> None:
        self._counter = registry.counter(
            "idiot_index_snapshot_replications_total",
            "Total snapshot replication attempts grouped by status",
            label_names=("status", "backend"),
        )
        self._latency = registry.histogram(
            "idiot_index_snapshot_replication_latency_seconds",
            "Latency of snapshot replication attempts",
            buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
            label_names=("backend",),
        )
        self._age = registry.gauge(
            "idiot_index_snapshot_replication_age_seconds",
            "Seconds since the most recent successful replication",
        )

        def _handle(event: ObservationEvent) -> None:
            backend = str(event.attributes.get("backend", "unknown"))
            status = event.status.lower()
            self._counter.increment(labels={"status": status, "backend": backend})
            self._latency.observe(event.duration, labels={"backend": backend})
            with self._lock:
                self._last_backend = backend
                self._last_status = status
                self._last_error = event.error
                self._last_event_at = event.emitted_at
                if status == "success":
                    self._last_success_at = event.emitted_at
                    self._age.set(0.0)
                elif self._last_success_at is not None:
                    delta = max(
                        0.0,
                        (event.emitted_at - self._last_success_at).total_seconds(),
                    )
                    self._age.set(delta)
                else:
                    self._age.set(0.0)

        registry.subscribe("observability.snapshot.replication", _handle)

        def _health_component() -> HealthComponent:
            with self._lock:
                backend = self._last_backend
                status = self._last_status
                error = self._last_error
                last_event = self._last_event_at
                last_success = self._last_success_at
            details: dict[str, Any] = {"backend": backend, "last_status": status}
            if last_event:
                details["last_event_at"] = last_event.isoformat()
            if last_success:
                details["last_success_at"] = last_success.isoformat()
                details["age_seconds"] = max(
                    0.0,
                    (datetime.now(UTC) - last_success).total_seconds(),
                )
            summary = "Replication disabled"
            health_status: str = "warn"
            if status == "success":
                summary = "Latest replication succeeded"
                health_status = "pass"
            elif status == "error":
                summary = "Latest replication failed"
                health_status = "warn"
                if error:
                    details["error"] = error
            elif status == "skipped":
                summary = "Replication backend skipped"
            else:
                summary = f"Latest replication reported status '{status}'"
            return HealthComponent(
                name="snapshot_replication",
                status=health_status,  # type: ignore[arg-type]
                summary=summary,
                details=details,
            )

        registry.register_health_check("snapshot_replication", _health_component)


def register(manager: ExtensionManager) -> None:
    manager.register_replication_extension(_S3ReplicationExtension())
    manager.register_replication_extension(_DebugReplicationExtension())
    manager.register_instrumentation_extension(_SnapshotReplicationInstrumentation())


__all__ = ["register"]
