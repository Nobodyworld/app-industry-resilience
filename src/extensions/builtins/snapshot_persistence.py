"""Automatic observability snapshot persistence extension."""

from __future__ import annotations

import atexit
import logging
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.core.config import load_config
from src.extensions.contracts import InstrumentationExtension
from src.extensions.manager import ExtensionManager
from src.infrastructure.observability.instrumentation import (
    ObservabilityRegistry,
    ObservationEvent,
)
from src.infrastructure.observability.replication import (
    NullSnapshotReplicator,
    SnapshotReplicationError,
    SnapshotReplicator,
    build_snapshot_replicator,
)
from src.infrastructure.observability.storage import (
    ObservabilitySnapshot,
    SnapshotStorage,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class _SnapshotPersistenceExtension(InstrumentationExtension):
    """Persist registry snapshots on startup, shutdown, and error events."""

    name: str = "snapshot_persistence"
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _last_persisted_at: datetime | None = field(default=None, init=False, repr=False)
    _storage: SnapshotStorage | None = field(default=None, init=False, repr=False)
    _retention_count: int = field(default=0, init=False, repr=False)
    _retention_days: int = field(default=0, init=False, repr=False)
    _min_interval_seconds: float = field(default=0.0, init=False, repr=False)
    _atexit_registered: bool = field(default=False, init=False, repr=False)
    _replicator: SnapshotReplicator | None = field(default=None, init=False, repr=False)
    _replicator_closed: bool = field(default=False, init=False, repr=False)
    _replication_backend: str = field(default="none", init=False, repr=False)

    def register(self, registry: ObservabilityRegistry) -> None:  # noqa: D401 - interface
        config = load_config()
        storage = SnapshotStorage(config.observability_snapshot_dir)
        self._storage = storage
        self._retention_count = max(0, config.observability_snapshot_retention_count)
        self._retention_days = max(0, config.observability_snapshot_retention_days)
        self._min_interval_seconds = max(
            0.0, float(config.observability_snapshot_min_interval_seconds)
        )
        remote_config = config.observability_snapshot_remote
        self._replicator = build_snapshot_replicator(remote_config)
        self._replication_backend = (remote_config.backend if remote_config else "none") or "none"

        self._persist(
            registry,
            storage,
            reason="startup",
            extra_metadata={"trigger": "startup"},
            force=True,
        )

        def _handle_event(event: ObservationEvent) -> None:
            if event.name == "observability.snapshot.persisted":
                return
            if event.status.lower() not in {"error", "warn"}:
                return
            metadata = {
                "trigger": "event",
                "event_name": event.name,
                "event_status": event.status,
            }
            if event.error:
                metadata["event_error"] = event.error
            self._persist(registry, storage, reason="event", extra_metadata=metadata)

        registry.subscribe("*", _handle_event)

        if not self._atexit_registered:
            atexit.register(self._handle_shutdown, registry, storage)
            self._atexit_registered = True

    def _persist(
        self,
        registry: ObservabilityRegistry,
        storage: SnapshotStorage,
        *,
        reason: str,
        extra_metadata: Mapping[str, Any] | None = None,
        force: bool = False,
    ) -> None:
        now = datetime.now(UTC)
        with self._lock:
            if not force and self._last_persisted_at is not None:
                delta = (now - self._last_persisted_at).total_seconds()
                if delta < self._min_interval_seconds:
                    LOGGER.debug(
                        "Skipping snapshot persistence due to throttle",
                        extra={
                            "reason": reason,
                            "min_interval_seconds": self._min_interval_seconds,
                            "elapsed": delta,
                        },
                    )
                    return
            metadata: dict[str, Any] = {"reason": reason}
            if extra_metadata:
                metadata.update(dict(extra_metadata))
            metadata.setdefault("snapshot_dir", str(storage.base_dir))
            try:
                snapshot = registry.persist_snapshot(storage, metadata=metadata)
            except Exception:  # pragma: no cover - defensive logging
                log_extra = {"reason": reason, "snapshot_dir": str(storage.base_dir)}
                if extra_metadata:
                    log_extra.update(dict(extra_metadata))
                LOGGER.exception("Failed to persist observability snapshot", extra=log_extra)
                return
            self._last_persisted_at = snapshot.captured_at
            self._replicate(
                registry,
                snapshot,
                storage.path_for(snapshot.snapshot_id),
                metadata,
            )
            self._prune(storage)

    def _prune(self, storage: SnapshotStorage) -> None:
        retention_count = max(0, self._retention_count)
        retention_days = max(0, self._retention_days)
        if retention_count == 0 and retention_days == 0:
            return
        snapshots = storage.list()
        cutoff_time: datetime | None = None
        if retention_days > 0:
            cutoff_time = datetime.now(UTC) - timedelta(days=retention_days)
        removable: set[str] = set()
        if retention_count > 0 and len(snapshots) > retention_count:
            for snapshot in snapshots[:-retention_count]:
                removable.add(snapshot.snapshot_id)
        if cutoff_time is not None:
            for snapshot in snapshots:
                if snapshot.captured_at < cutoff_time:
                    removable.add(snapshot.snapshot_id)
        for snapshot_id in removable:
            try:
                storage.delete(snapshot_id)
            except FileNotFoundError:  # pragma: no cover - concurrent cleanup
                LOGGER.debug(
                    "Snapshot already removed during pruning",
                    extra={"snapshot_id": snapshot_id},
                )

    def _replicate(
        self,
        registry: ObservabilityRegistry,
        snapshot: ObservabilitySnapshot,
        path: Path,
        metadata: Mapping[str, Any],
    ) -> None:
        replicator = self._replicator
        backend = self._replication_backend
        status = "skipped"
        error_message: str | None = None
        duration = 0.0
        if replicator is not None and not isinstance(replicator, NullSnapshotReplicator):
            start = time.perf_counter()
            try:
                replicator.replicate(snapshot, path)
            except SnapshotReplicationError as exc:
                status = "error"
                error_message = str(exc)
            except Exception as exc:  # pragma: no cover - defensive logging
                status = "error"
                error_message = str(exc)
                LOGGER.warning(
                    "Unexpected error while replicating snapshot",
                    extra={"path": str(path)},
                    exc_info=True,
                )
            else:
                status = "success"
            finally:
                duration = time.perf_counter() - start
        attributes: dict[str, Any] = {
            "snapshot_id": snapshot.snapshot_id,
            "backend": backend,
            "path": str(path),
            "replicator": replicator.__class__.__name__ if replicator else "null",
            "reason": str(metadata.get("reason", "unspecified")),
        }
        if "trigger" in metadata:
            attributes["trigger"] = str(metadata.get("trigger"))
        if "label" in metadata:
            attributes["label"] = str(metadata.get("label"))
        registry.record_event(
            "observability.snapshot.replication",
            attributes=attributes,
            status=status,
            duration=duration,
            error=error_message,
        )

    def _handle_shutdown(self, registry: ObservabilityRegistry, storage: SnapshotStorage) -> None:
        self._persist(
            registry,
            storage,
            reason="shutdown",
            extra_metadata={"trigger": "shutdown"},
            force=True,
        )
        self._close_replicator()

    def _close_replicator(self) -> None:
        if self._replicator_closed or self._replicator is None:
            return
        try:
            self._replicator.close()
        except Exception:  # pragma: no cover - defensive cleanup
            LOGGER.debug("Error closing snapshot replicator", exc_info=True)
        finally:
            self._replicator_closed = True


def register(manager: ExtensionManager) -> None:
    manager.register_instrumentation_extension(_SnapshotPersistenceExtension())


__all__ = ["register"]
