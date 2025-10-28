"""Extension contracts for Idiot Index modular augmentations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from src.application.idiot_index_service import IdiotIndexSummary
    from src.application.scenario_planner import ScenarioResult
    from src.core.config import SnapshotRemoteStorageConfig
    from src.extensions.connectors import ConnectorRegistry
    from src.infrastructure.observability.instrumentation import ObservabilityRegistry
    from src.infrastructure.observability.replication import SnapshotReplicator


@dataclass(frozen=True)
class ExtensionContributions:
    """Normalized contribution payload emitted by extensions."""

    notes: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


class SummaryExtension(Protocol):
    """Operate on IdiotIndexSummary objects and return additional notes/metadata."""

    name: str

    def contribute(self, summary: IdiotIndexSummary) -> ExtensionContributions: ...


class ScenarioExtension(Protocol):
    """Operate on ScenarioResult payloads to enrich metadata."""

    name: str

    def contribute(self, result: ScenarioResult) -> ExtensionContributions: ...


class InstrumentationExtension(Protocol):
    """Register observability hooks (metrics, tracing, health checks)."""

    name: str

    def register(self, registry: ObservabilityRegistry) -> None: ...


class ReplicationExtension(Protocol):
    """Provide custom snapshot replication implementations."""

    name: str

    def supports(self, config: SnapshotRemoteStorageConfig) -> bool: ...

    def build(self, config: SnapshotRemoteStorageConfig) -> SnapshotReplicator: ...


class ConnectorExtension(Protocol):
    """Register connector metadata and optional health hooks."""

    name: str

    def register(self, registry: ConnectorRegistry) -> None: ...


__all__ = [
    "ExtensionContributions",
    "InstrumentationExtension",
    "ReplicationExtension",
    "SummaryExtension",
    "ScenarioExtension",
    "ConnectorExtension",
]
