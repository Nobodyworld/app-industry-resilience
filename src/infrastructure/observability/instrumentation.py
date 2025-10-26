"""Observability registry unifying metrics, tracing, and health probes."""

from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict, deque
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .health import HealthComponent, HealthProbe
from .metrics import Counter as MetricCounter
from .metrics import Gauge, Histogram, MetricRegistry
from .storage import ObservabilitySnapshot, SnapshotStorage, build_snapshot_id
from .tracing import Tracer

LOGGER = logging.getLogger(__name__)
_RECENT_EVENTS_LIMIT = 25


@dataclass(frozen=True)
class ObservationEvent:
    """Structured payload emitted whenever an instrumented operation completes."""

    name: str
    attributes: Mapping[str, Any]
    duration: float
    status: str
    trace_id: str | None
    error: str | None = None
    emitted_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "duration": self.duration,
            "status": self.status,
            "timestamp": self.emitted_at.isoformat(),
        }
        if self.attributes:
            payload["attributes"] = dict(self.attributes)
        if self.trace_id:
            payload["trace_id"] = self.trace_id
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass
class ObservabilityRegistry:
    """Central hub combining metrics, tracing, and health introspection."""

    metrics: MetricRegistry = field(default_factory=MetricRegistry)
    tracer: Tracer = field(default_factory=Tracer)
    _subscriptions: dict[str, list[Callable[[ObservationEvent], None]]] = field(
        default_factory=lambda: defaultdict(list), init=False, repr=False
    )
    _health_checks: dict[str, Callable[[], HealthComponent]] = field(
        default_factory=dict, init=False, repr=False
    )
    _probe: HealthProbe | None = field(default=None, init=False, repr=False)
    _recent_events: deque[ObservationEvent] = field(
        default_factory=lambda: deque(maxlen=_RECENT_EVENTS_LIMIT), init=False, repr=False
    )
    _event_counters: Counter[str] = field(default_factory=Counter, init=False, repr=False)
    _last_error_event: ObservationEvent | None = field(default=None, init=False, repr=False)

    def counter(
        self,
        name: str,
        description: str,
        *,
        label_names: Iterable[str] | None = None,
    ) -> MetricCounter:
        """Create or retrieve a counter metric managed by the registry."""

        return self.metrics.counter(name, description, label_names=label_names)

    def gauge(
        self,
        name: str,
        description: str,
        *,
        label_names: Iterable[str] | None = None,
    ) -> Gauge:
        """Create or retrieve a gauge metric managed by the registry."""

        return self.metrics.gauge(name, description, label_names=label_names)

    def histogram(
        self,
        name: str,
        description: str,
        *,
        buckets: Iterable[float] | None = None,
        label_names: Iterable[str] | None = None,
    ) -> Histogram:
        """Create or retrieve a histogram metric managed by the registry."""

        return self.metrics.histogram(
            name,
            description,
            buckets=buckets,
            label_names=label_names,
        )

    def subscribe(self, event_name: str, handler: Callable[[ObservationEvent], None]) -> None:
        """Subscribe to observation events.

        Use ``"*"`` to receive callbacks for every event published through
        :meth:`operation`.
        """

        self._subscriptions.setdefault(event_name, []).append(handler)

    def record_event(
        self,
        name: str,
        *,
        attributes: Mapping[str, Any] | None = None,
        status: str = "success",
        duration: float = 0.0,
        error: str | None = None,
    ) -> None:
        """Emit an observation event without wrapping a context manager."""

        attrs = dict(attributes or {})
        with self.tracer.start_span(name, attributes=attrs) as span:
            trace_id = span.trace_id
        self._emit(
            name,
            attrs,
            max(0.0, float(duration)),
            status=status,
            trace_id=trace_id,
            error=error,
        )

    def capture_snapshot(
        self, *, metadata: Mapping[str, Any] | None = None
    ) -> ObservabilitySnapshot:
        """Return a snapshot of the registry's current digest."""

        captured_at = datetime.now(UTC)
        snapshot_id = build_snapshot_id(captured_at)
        meta = dict(metadata or {})
        payload = self.digest()
        return ObservabilitySnapshot(
            snapshot_id=snapshot_id,
            captured_at=captured_at,
            payload=payload,
            metadata=meta,
        )

    def persist_snapshot(
        self,
        storage: SnapshotStorage,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> ObservabilitySnapshot:
        """Capture and store a snapshot using ``storage``."""

        snapshot = self.capture_snapshot(metadata=metadata)
        storage.save(snapshot)
        self.record_event(
            "observability.snapshot.persisted",
            attributes={
                "snapshot_id": snapshot.snapshot_id,
                "storage_dir": str(storage.base_dir),
                "metadata_keys": sorted(map(str, snapshot.metadata.keys())),
                "captured_at": snapshot.captured_at.isoformat(),
            },
        )
        return snapshot

    def register_health_check(self, name: str, supplier: Callable[[], HealthComponent]) -> None:
        """Register a lazy health check contribution.

        The supplier is invoked every time the bound :class:`HealthProbe` runs.
        """

        self._health_checks[name] = supplier
        if self._probe:
            self._probe.register(name, supplier)

    def bind_probe(self, probe: HealthProbe) -> None:
        """Attach an existing :class:`HealthProbe` to receive registered checks."""

        self._probe = probe
        for name, supplier in self._health_checks.items():
            probe.register(name, supplier)

    @contextmanager
    def operation(
        self, name: str, *, attributes: Mapping[str, Any] | None = None
    ) -> Iterator[None]:
        """Context manager publishing telemetry for a named operation."""

        attrs = dict(attributes or {})
        start = time.perf_counter()
        span_cm = self.tracer.start_span(name, attributes=attrs)
        span = span_cm.__enter__()
        exc_type: type[BaseException] | None = None
        exc: BaseException | None = None
        tb = None
        try:
            yield
        except Exception as error:  # pragma: no cover - defensive, re-raised
            exc_type = type(error)
            exc = error
            tb = error.__traceback__
            self._emit(
                name,
                attrs,
                time.perf_counter() - start,
                status="error",
                trace_id=span.trace_id,
                error=repr(error),
            )
            raise
        else:
            self._emit(
                name,
                attrs,
                time.perf_counter() - start,
                status="success",
                trace_id=span.trace_id,
                error=None,
            )
        finally:
            span_cm.__exit__(exc_type, exc, tb)

    def recent_events(self) -> list[dict[str, Any]]:
        """Return a serialisable list of recently emitted observation events."""

        return [event.as_dict() for event in self._recent_events]

    def metrics_summary(self) -> dict[str, Any]:
        """Summarise registered metric primitives and subscribers."""

        return {
            "counters": len(self.metrics.counters),
            "gauges": len(self.metrics.gauges),
            "histograms": len(self.metrics.histograms),
            "subscriptions": {
                name: len(handlers) for name, handlers in self._subscriptions.items()
            },
        }

    def health_overview(self) -> dict[str, Any]:
        """Return an aggregated view of observability state for diagnostics."""

        digest = self.digest()
        return {
            "metrics": digest["metrics"],
            "recent_events": digest["events"]["recent"],
            "registered_health_checks": digest["health_checks"],
            "traces": digest["traces"],
            "event_counters": digest["events"]["counts"],
            "last_error": digest["events"].get("last_error"),
            "subscriptions": digest["subscriptions"],
        }

    def digest(self) -> dict[str, Any]:
        """Return a comprehensive observability snapshot for automation."""

        recent = self.recent_events()
        counters = dict(self._event_counters)
        total = sum(counters.values())
        last_error = (
            self._last_error_event.as_dict() if self._last_error_event is not None else None
        )
        return {
            "metrics": self.metrics_summary(),
            "traces": {"exported_spans": self.tracer.span_count()},
            "health_checks": sorted(self._health_checks),
            "events": {
                "counts": counters,
                "total": total,
                "recent": recent,
                "last_error": last_error,
            },
            "subscriptions": {
                name: len(handlers) for name, handlers in self._subscriptions.items()
            },
        }

    def events(
        self,
        *,
        limit: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return recent observation events filtered by ``status`` and ``limit``.

        Events are returned in reverse chronological order so that the latest
        telemetry appears first in API responses and CLI diagnostics.
        """

        events: list[ObservationEvent] = list(self._recent_events)
        if status:
            status_normalised = status.lower()
            events = [event for event in events if event.status.lower() == status_normalised]
        if limit is not None and limit >= 0:
            events = events[-limit:]
        return [event.as_dict() for event in reversed(events)]

    def iter_recent_events(self) -> Iterator[ObservationEvent]:
        """Yield recently emitted observation events in chronological order."""

        yield from tuple(self._recent_events)

    def _emit(
        self,
        name: str,
        attributes: Mapping[str, Any],
        duration: float,
        *,
        status: str,
        trace_id: str | None,
        error: str | None,
    ) -> None:
        event = ObservationEvent(
            name=name,
            attributes=dict(attributes),
            duration=duration,
            status=status,
            trace_id=trace_id,
            error=error,
        )
        self._recent_events.append(event)
        self._event_counters[event.status] += 1
        if status.lower() == "error":
            self._last_error_event = event

        for handler in self._subscriptions.get(name, []):
            self._safe_invoke(handler, event)
        for handler in self._subscriptions.get("*", []):
            self._safe_invoke(handler, event)

    @staticmethod
    def _safe_invoke(handler: Callable[[ObservationEvent], None], event: ObservationEvent) -> None:
        try:
            handler(event)
        except Exception:  # pragma: no cover - defensive logging
            LOGGER.exception("Observability subscriber failed", extra={"event": event.as_dict()})


_REGISTRY_SINGLETON: ObservabilityRegistry | None = None


def bootstrap_observability() -> ObservabilityRegistry:
    """Return the process-wide observability registry singleton."""

    global _REGISTRY_SINGLETON
    if _REGISTRY_SINGLETON is None:
        _REGISTRY_SINGLETON = ObservabilityRegistry()
    return _REGISTRY_SINGLETON


__all__ = [
    "ObservationEvent",
    "ObservabilityRegistry",
    "bootstrap_observability",
]
