"""Telemetry helpers for the headless API."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from src.infrastructure.observability import (
    Counter,
    Gauge,
    Histogram,
    MetricRegistry,
    ObservabilityRegistry,
    Tracer,
    current_trace_id,
    render_prometheus_text,
)


@dataclass(slots=True)
class RequestTelemetryContext:
    start_time: float
    trace_id: str | None
    _span_cm: Any

    def finish(
        self,
        exc_type: type[BaseException] | None = None,
        exc: BaseException | None = None,
    ) -> None:
        self._span_cm.__exit__(exc_type, exc, None)


@dataclass(slots=True)
class ApiTelemetry:
    """Container storing API metrics and tracing utilities."""

    registry_override: MetricRegistry | None = None
    tracer_override: Tracer | None = None
    observability: ObservabilityRegistry | None = None
    registry: MetricRegistry = field(init=False, repr=False)
    tracer: Tracer = field(init=False, repr=False)
    _request_counter: Counter = field(init=False, repr=False)
    _latency: Histogram = field(init=False, repr=False)
    _inflight: Gauge = field(init=False, repr=False)
    _errors: Counter = field(init=False, repr=False)

    def __post_init__(self) -> None:
        registry = self.registry_override
        tracer = self.tracer_override
        if self.observability is not None:
            registry = registry or self.observability.metrics
            tracer = tracer or self.observability.tracer
        self.registry = registry or MetricRegistry()
        self.tracer = tracer or Tracer()
        self._request_counter = self.registry.counter(
            "idiot_index_api_requests_total",
            "Total number of API requests",
            label_names=("method", "path", "status"),
        )
        self._latency = self.registry.histogram(
            "idiot_index_api_request_duration_seconds",
            "Latency for API requests",
            buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
            label_names=("method", "path"),
        )
        self._inflight = self.registry.gauge(
            "idiot_index_api_requests_in_flight",
            "Number of in-flight API requests",
            label_names=("path",),
        )
        self._errors = self.registry.counter(
            "idiot_index_api_errors_total",
            "Total number of API errors",
            label_names=("path", "kind"),
        )

    def start_request(self, method: str, path: str) -> RequestTelemetryContext:
        self._inflight.add(1, labels={"path": path})
        span_cm = self.tracer.start_span(
            f"api:{method} {path}", attributes={"method": method, "path": path}
        )
        span = span_cm.__enter__()
        return RequestTelemetryContext(
            start_time=time.perf_counter(), trace_id=span.trace_id, _span_cm=span_cm
        )

    def finish_request(
        self,
        method: str,
        path: str,
        status_code: int,
        context: RequestTelemetryContext,
        *,
        error: BaseException | None = None,
    ) -> None:
        context.finish(type(error) if error else None, error)
        duration = time.perf_counter() - context.start_time
        self._request_counter.increment(
            labels={"method": method, "path": path, "status": str(status_code)}
        )
        self._latency.observe(duration, labels={"method": method, "path": path})
        self._inflight.add(-1, labels={"path": path})
        if status_code >= 500:
            self._errors.increment(labels={"path": path, "kind": "server"})
        elif status_code >= 400:
            self._errors.increment(labels={"path": path, "kind": "client"})

    def record_exception(self, path: str, kind: str = "server") -> None:
        self._errors.increment(labels={"path": path, "kind": kind})

    def metrics_response(self) -> str:
        return render_prometheus_text(self.registry)

    def correlation_id(self) -> str | None:
        return current_trace_id()

    def health_snapshot(self) -> dict[str, Any]:
        """Return lightweight readiness metadata for health probes."""

        payload = {
            "metrics": {
                "counters": len(self.registry.counters),
                "gauges": len(self.registry.gauges),
                "histograms": len(self.registry.histograms),
            },
            "tracing": {
                "exported_spans": self.tracer.span_count(),
            },
        }
        if self.observability is not None:
            payload["observability"] = self.observability.health_overview()
        return payload


DEFAULT_TELEMETRY = ApiTelemetry()


__all__ = ["ApiTelemetry", "DEFAULT_TELEMETRY", "RequestTelemetryContext"]
