"""Extension registry and loader utilities."""

from __future__ import annotations

import importlib
import json
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .contracts import (
    ExtensionContributions,
    InstrumentationExtension,
    ScenarioExtension,
    SummaryExtension,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from src.infrastructure.observability.instrumentation import ObservabilityRegistry

LOGGER = logging.getLogger(__name__)
MANIFEST_PATH = Path("extensions/manifest.json")
ENV_VAR = "IDIOT_INDEX_EXTENSIONS"


@dataclass
class ExtensionManager:
    """Maintain registered extensions and apply their contributions."""

    summary_extensions: list[SummaryExtension] = field(default_factory=list)
    scenario_extensions: list[ScenarioExtension] = field(default_factory=list)
    instrumentation_extensions: list[InstrumentationExtension] = field(default_factory=list)
    logger: logging.Logger = field(default=LOGGER)
    _instrumentation_registry_cache: dict[str, set[int]] = field(
        default_factory=dict, init=False, repr=False
    )

    def register_summary_extension(self, extension: SummaryExtension) -> None:
        self.logger.debug("Registering summary extension", extra={"extension": extension.name})
        self.summary_extensions.append(extension)

    def register_scenario_extension(self, extension: ScenarioExtension) -> None:
        self.logger.debug("Registering scenario extension", extra={"extension": extension.name})
        self.scenario_extensions.append(extension)

    def register_instrumentation_extension(self, extension: InstrumentationExtension) -> None:
        self.logger.debug(
            "Registering instrumentation extension", extra={"extension": extension.name}
        )
        self.instrumentation_extensions.append(extension)

    def apply_summary_extensions(self, summary) -> ExtensionContributions:
        notes: list[str] = []
        metadata: dict[str, object] = {}
        for extension in self.summary_extensions:
            try:
                result = extension.contribute(summary)
            except Exception:  # pragma: no cover - defensive, logged
                self.logger.exception(
                    "Summary extension failed", extra={"extension": extension.name}
                )
                continue
            for note in result.notes:
                notes.append(f"[{extension.name}] {note}")
            if result.metadata:
                metadata[extension.name] = dict(result.metadata)
        return ExtensionContributions(notes=tuple(notes), metadata=metadata)

    def apply_scenario_extensions(self, result) -> ExtensionContributions:
        notes: list[str] = []
        metadata: dict[str, object] = {}
        for extension in self.scenario_extensions:
            try:
                contribution = extension.contribute(result)
            except Exception:  # pragma: no cover - defensive, logged
                self.logger.exception(
                    "Scenario extension failed", extra={"extension": extension.name}
                )
                continue
            for note in contribution.notes:
                notes.append(f"[{extension.name}] {note}")
            if contribution.metadata:
                metadata[extension.name] = dict(contribution.metadata)
        return ExtensionContributions(notes=tuple(notes), metadata=metadata)

    def apply_instrumentation_extensions(
        self, registry: ObservabilityRegistry
    ) -> None:  # pragma: no cover - thin orchestrator
        for extension in self.instrumentation_extensions:
            applied = self._instrumentation_registry_cache.setdefault(extension.name, set())
            registry_id = id(registry)
            if registry_id in applied:
                continue
            try:
                extension.register(registry)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception(
                    "Instrumentation extension failed",
                    extra={"extension": extension.name},
                )
                continue
            applied.add(registry_id)


def _parse_manifest(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        LOGGER.error("Invalid extension manifest", extra={"path": str(path), "error": str(exc)})
        return []
    modules = data.get("modules", [])
    return [module for module in modules if isinstance(module, str)]


def _modules_from_env() -> list[str]:
    raw = os.getenv(ENV_VAR, "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def discover_extension_modules() -> list[str]:
    modules = _parse_manifest(MANIFEST_PATH)
    modules.extend(_modules_from_env())
    return modules


def load_extensions(
    manager: ExtensionManager, modules: Sequence[str] | None = None
) -> ExtensionManager:
    resolved_modules = list(modules) if modules is not None else discover_extension_modules()
    for module_path in resolved_modules:
        try:
            module = importlib.import_module(module_path)
        except Exception:  # pragma: no cover - module import issues
            LOGGER.exception(
                "Failed to import extension module",
                extra={"extension_module": module_path},
            )
            continue
        register = getattr(module, "register", None)
        if not callable(register):
            LOGGER.warning(
                "Extension module missing register()",
                extra={"extension_module": module_path},
            )
            continue
        try:
            register(manager)
        except Exception:  # pragma: no cover - extension errors
            LOGGER.exception(
                "Extension registration failed",
                extra={"extension_module": module_path},
            )
            continue
    return manager


_MANAGER_SINGLETON: ExtensionManager | None = None


def get_extension_manager() -> ExtensionManager:
    global _MANAGER_SINGLETON
    if _MANAGER_SINGLETON is None:
        _MANAGER_SINGLETON = load_extensions(ExtensionManager())
    return _MANAGER_SINGLETON


__all__ = [
    "ExtensionManager",
    "discover_extension_modules",
    "get_extension_manager",
    "load_extensions",
]
