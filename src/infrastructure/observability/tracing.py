"""Trace utilities providing correlation IDs and span recording."""

from __future__ import annotations

import contextlib
import contextvars
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

_current_context: contextvars.ContextVar[TraceContext | None] = contextvars.ContextVar(
    "current_trace_context", default=None
)


@dataclass(slots=True)
class TraceContext:
    """Represents the active trace/span identifiers."""

    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    start_time: float
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }
        if self.attributes:
            payload["attributes"] = dict(self.attributes)
        return payload


class Tracer:
    """Simple tracer storing spans in-memory for inspection/logging."""

    def __init__(self) -> None:
        self._spans: list[TraceContext] = []

    @contextlib.contextmanager
    def start_span(
        self, name: str, *, attributes: dict[str, Any] | None = None
    ) -> Iterator[TraceContext]:
        parent = _current_context.get()
        trace_id = parent.trace_id if parent else uuid.uuid4().hex
        span_id = uuid.uuid4().hex
        context = TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent.span_id if parent else None,
            name=name,
            start_time=time.time(),
            attributes=dict(attributes or {}),
        )
        token = _current_context.set(context)
        try:
            yield context
        finally:
            context.end_time = time.time()
            self._spans.append(context)
            _current_context.reset(token)

    def last_span(self) -> TraceContext | None:
        if not self._spans:
            return None
        return self._spans[-1]

    def clear(self) -> None:
        self._spans.clear()

    def export(self) -> list[dict[str, Any]]:
        return [span.to_dict() for span in self._spans]

    def span_count(self) -> int:
        """Return the total number of completed spans captured so far."""

        return len(self._spans)


def current_trace_context() -> TraceContext | None:
    return _current_context.get()


def current_trace_id() -> str | None:
    context = _current_context.get()
    return context.trace_id if context else None


__all__ = [
    "TraceContext",
    "Tracer",
    "current_trace_context",
    "current_trace_id",
]
