"""Observability registry unifying metrics, tracing, and health probes."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from .health import HealthComponent, HealthProbe
from .metrics import Counter, Gauge, Histogram, MetricRegistry
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

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "duration": self.duration,
            "status": self.status,
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

    def counter(
        self,
        name: str,
        description: str,
        *,
        label_names: Iterable[str] | None = None,
    ) -> Counter:
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

        return {
            "metrics": self.metrics_summary(),
            "recent_events": self.recent_events(),
            "registered_health_checks": sorted(self._health_checks),
            "traces": {"exported_spans": self.tracer.span_count()},
        }

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
