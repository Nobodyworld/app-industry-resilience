"""Connector registry supporting modular data and automation integrations."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from typing import TYPE_CHECKING, Any

from src.infrastructure.observability.health import HealthComponent, HealthStatus
from src.infrastructure.observability.metrics import Gauge

if TYPE_CHECKING:  # pragma: no cover - typing only
    from src.infrastructure.observability.instrumentation import ObservabilityRegistry


ConnectorHealthSupplier = Callable[[], HealthComponent]


@dataclass(slots=True, frozen=True)
class ConnectorRegistration:
    """Static metadata describing an integration connector."""

    identifier: str
    name: str
    kind: str
    version: str
    description: str | None = None
    owner: str | None = None
    tags: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    health_check: ConnectorHealthSupplier | None = None


@dataclass(slots=True, frozen=True)
class ConnectorSnapshot:
    """Serializable snapshot of a registered connector."""

    identifier: str
    name: str
    kind: str
    version: str
    description: str | None
    owner: str | None
    tags: tuple[str, ...]
    capabilities: tuple[str, ...]
    metadata: Mapping[str, Any]
    health: Mapping[str, Any] | None = None


class ConnectorRegistry:
    """Maintain connector registrations and expose observability hooks."""

    def __init__(self) -> None:
        self._connectors: dict[str, ConnectorRegistration] = {}
        self._observability: ObservabilityRegistry | None = None
        self._gauge: Gauge | None = None
        self._tracked_kinds: set[str] = set()

    @property
    def connectors(self) -> Mapping[str, ConnectorRegistration]:
        """Get a read-only view of all registered connectors."""
        return dict(self._connectors)

    def register(self, registration: ConnectorRegistration) -> None:
        """Register a new connector with validation and metrics refresh."""
        identifier = registration.identifier.strip()
        if not identifier:
            raise ValueError("Connector identifier must not be empty.")
        if identifier in self._connectors:
            raise ValueError(f"Connector '{identifier}' already registered.")
        self._connectors[identifier] = registration
        self._refresh_metrics()

    def attach_observability(self, registry: ObservabilityRegistry) -> None:
        """Attach observability hooks for connector metrics and health checks."""
        if self._observability is registry:
            return
        self._observability = registry
        self._gauge = registry.gauge(
            "idiot_index_connectors_registered_total",
            "Number of registered connectors by kind.",
            label_names=("kind",),
        )

        def _catalog_health() -> HealthComponent:
            """Generate health component for the entire connector catalog."""
            components = tuple(self._connector_health_components())
            status: HealthStatus = "pass"
            if any(component.status == "fail" for component in components):
                status = "fail"
            elif any(component.status == "warn" for component in components):
                status = "warn"
            return HealthComponent(
                name="connectors_catalog",
                status=status,
                summary="Connector registry active",
                details={
                    "count": len(self._connectors),
                    "by_kind": Counter(reg.kind for reg in self._connectors.values()),
                    "components": [component.as_dict() for component in components],
                },
            )

        registry.register_health_check("connectors_catalog", _catalog_health)
        self._refresh_metrics()

    def summary(self, *, include_health: bool = False) -> dict[str, Any]:
        """Generate a summary of all registered connectors with optional health status."""
        connectors = []
        health_map: dict[str, Mapping[str, Any] | None] = {}
        if include_health:
            for component in self._connector_health_components():
                health_map[component.name] = component.as_dict()

        for registration in sorted(self._connectors.values(), key=lambda reg: reg.identifier):
            payload = ConnectorSnapshot(
                identifier=registration.identifier,
                name=registration.name,
                kind=registration.kind,
                version=registration.version,
                description=registration.description,
                owner=registration.owner,
                tags=registration.tags,
                capabilities=registration.capabilities,
                metadata=dict(registration.metadata),
                health=(
                    health_map.get(self._health_component_name(registration))
                    if include_health
                    else None
                ),
            )
            connectors.append(payload)

        counts = Counter(snapshot.kind for snapshot in connectors)
        return {
            "count": len(connectors),
            "by_kind": dict(sorted(counts.items())),
            "items": [asdict(snapshot) for snapshot in connectors],
        }

    def _refresh_metrics(self) -> None:
        """Update observability metrics to reflect current connector registrations."""
        if self._gauge is None:
            return
        counts = Counter(reg.kind for reg in self._connectors.values())
        for kind, count in counts.items():
            self._tracked_kinds.add(kind)
            self._gauge.set(float(count), labels={"kind": kind})
        for kind in list(self._tracked_kinds):
            if kind not in counts:
                self._gauge.set(0.0, labels={"kind": kind})

    def _connector_health_components(self) -> Sequence[HealthComponent]:
        """Generate health components for all registered connectors."""
        components: list[HealthComponent] = []
        for registration in self._connectors.values():
            name = self._health_component_name(registration)
            supplier = registration.health_check
            if supplier is None:
                components.append(
                    HealthComponent(
                        name=name,
                        status="warn",
                        summary="Connector health check not provided",
                        details={"connector": registration.identifier},
                    )
                )
                continue
            try:
                component = supplier()
            except Exception as exc:  # pragma: no cover - defensive instrumentation
                component = HealthComponent(
                    name=name,
                    status="fail",
                    summary="Connector health check raised an exception",
                    details={"connector": registration.identifier, "error": repr(exc)},
                )
            else:
                component = replace(component, name=name)
            components.append(component)
        return components

    @staticmethod
    def _health_component_name(registration: ConnectorRegistration) -> str:
        """Generate a standardized health component name for a connector."""
        return f"connector:{registration.identifier}"


__all__ = [
    "ConnectorRegistration",
    "ConnectorRegistry",
    "ConnectorSnapshot",
]
