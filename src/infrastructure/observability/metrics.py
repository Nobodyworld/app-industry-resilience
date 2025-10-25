"""Lightweight metrics primitives with Prometheus exposition support."""

from __future__ import annotations

import threading
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field

LabelValues = tuple[str, ...]
DEFAULT_BUCKETS: tuple[float, ...] = (0.1, 0.5, 1.0, 2.5, 5.0, 10.0)


@dataclass(slots=True)
class _MetricBase:
    name: str
    description: str
    label_names: tuple[str, ...] = field(default_factory=tuple)

    def _normalise_labels(self, labels: Mapping[str, str] | None) -> LabelValues:
        if not self.label_names:
            return ()
        if labels is None:
            return tuple("" for _ in self.label_names)
        return tuple(labels.get(label, "") for label in self.label_names)


@dataclass(slots=True)
class Counter(_MetricBase):
    """Monotonic counter supporting labelled increments."""

    _values: dict[LabelValues, float] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def increment(self, amount: float = 1.0, *, labels: Mapping[str, str] | None = None) -> None:
        if amount < 0:
            raise ValueError("Counters cannot be decremented")
        key = self._normalise_labels(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def samples(self) -> Iterator[tuple[LabelValues, float]]:
        with self._lock:
            yield from self._values.items()


@dataclass(slots=True)
class Gauge(_MetricBase):
    """Gauge tracking the latest value per label set."""

    _values: dict[LabelValues, float] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def set(self, value: float, *, labels: Mapping[str, str] | None = None) -> None:
        key = self._normalise_labels(labels)
        with self._lock:
            self._values[key] = value

    def add(self, delta: float, *, labels: Mapping[str, str] | None = None) -> None:
        key = self._normalise_labels(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + delta

    def samples(self) -> Iterator[tuple[LabelValues, float]]:
        with self._lock:
            yield from self._values.items()


@dataclass(slots=True)
class Histogram(_MetricBase):
    """Histogram with configurable buckets and sum tracking."""

    buckets: tuple[float, ...] = field(default_factory=lambda: DEFAULT_BUCKETS)
    _counts: dict[LabelValues, list[int]] = field(default_factory=dict, init=False)
    _sum: dict[LabelValues, float] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        if sorted(self.buckets) != list(self.buckets):
            raise ValueError("Histogram buckets must be sorted")

    def observe(self, value: float, *, labels: Mapping[str, str] | None = None) -> None:
        key = self._normalise_labels(labels)
        with self._lock:
            bucket_counts = self._counts.setdefault(key, [0] * (len(self.buckets) + 1))
            index = next(
                (i for i, boundary in enumerate(self.buckets) if value <= boundary),
                len(self.buckets),
            )
            bucket_counts[index] += 1
            self._sum[key] = self._sum.get(key, 0.0) + value

    def samples(self) -> Iterator[tuple[LabelValues, list[int], float]]:
        with self._lock:
            for key, counts in self._counts.items():
                yield key, list(counts), self._sum.get(key, 0.0)


@dataclass(slots=True)
class MetricRegistry:
    """Container for registered metrics."""

    counters: dict[str, Counter] = field(default_factory=dict, init=False)
    gauges: dict[str, Gauge] = field(default_factory=dict, init=False)
    histograms: dict[str, Histogram] = field(default_factory=dict, init=False)

    def counter(
        self, name: str, description: str, *, label_names: Iterable[str] | None = None
    ) -> Counter:
        metric = self.counters.get(name)
        if metric is None:
            metric = Counter(
                name=name, description=description, label_names=tuple(label_names or ())
            )
            self.counters[name] = metric
        return metric

    def gauge(
        self, name: str, description: str, *, label_names: Iterable[str] | None = None
    ) -> Gauge:
        metric = self.gauges.get(name)
        if metric is None:
            metric = Gauge(name=name, description=description, label_names=tuple(label_names or ()))
            self.gauges[name] = metric
        return metric

    def histogram(
        self,
        name: str,
        description: str,
        *,
        buckets: Iterable[float] | None = None,
        label_names: Iterable[str] | None = None,
    ) -> Histogram:
        metric = self.histograms.get(name)
        if metric is None:
            metric = Histogram(
                name=name,
                description=description,
                label_names=tuple(label_names or ()),
                buckets=tuple(sorted(buckets)) if buckets is not None else DEFAULT_BUCKETS,
            )
            self.histograms[name] = metric
        return metric


def _format_labels(label_names: tuple[str, ...], label_values: LabelValues) -> str:
    if not label_names:
        return ""
    parts = [f'{name}="{value}"' for name, value in zip(label_names, label_values, strict=False)]
    return "{" + ",".join(parts) + "}"


def render_prometheus_text(registry: MetricRegistry) -> str:
    """Render the registry contents using the Prometheus text exposition format."""

    lines: list[str] = []
    for counter in registry.counters.values():
        lines.append(f"# HELP {counter.name} {counter.description}")
        lines.append(f"# TYPE {counter.name} counter")
        for labels, value in counter.samples():
            label_text = _format_labels(counter.label_names, labels)
            lines.append(f"{counter.name}{label_text} {value:.6f}")

    for gauge in registry.gauges.values():
        lines.append(f"# HELP {gauge.name} {gauge.description}")
        lines.append(f"# TYPE {gauge.name} gauge")
        for labels, value in gauge.samples():
            label_text = _format_labels(gauge.label_names, labels)
            lines.append(f"{gauge.name}{label_text} {value:.6f}")

    for histogram in registry.histograms.values():
        lines.append(f"# HELP {histogram.name} {histogram.description}")
        lines.append(f"# TYPE {histogram.name} histogram")
        for labels, counts, total in histogram.samples():
            cumulative = 0
            for index, boundary in enumerate(histogram.buckets):
                cumulative += counts[index]
                label_text = _format_labels(
                    histogram.label_names + ("le",), labels + (str(boundary),)
                )
                lines.append(f"{histogram.name}_bucket{label_text} {cumulative}")
            cumulative += counts[-1]
            label_text = _format_labels(histogram.label_names + ("le",), labels + ("+Inf",))
            lines.append(f"{histogram.name}_bucket{label_text} {cumulative}")
            sum_label_text = _format_labels(histogram.label_names, labels)
            lines.append(f"{histogram.name}_sum{sum_label_text} {total:.6f}")
            lines.append(f"{histogram.name}_count{sum_label_text} {cumulative}")

    return "\n".join(lines) + "\n"


__all__ = [
    "Counter",
    "Gauge",
    "Histogram",
    "MetricRegistry",
    "render_prometheus_text",
]
