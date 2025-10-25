"""Extension contracts for Idiot Index modular augmentations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from src.application.idiot_index_service import IdiotIndexSummary
    from src.application.scenario_planner import ScenarioResult


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


__all__ = [
    "ExtensionContributions",
    "SummaryExtension",
    "ScenarioExtension",
]
