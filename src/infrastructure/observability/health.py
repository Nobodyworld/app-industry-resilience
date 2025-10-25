from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from src.core.config import (
    AppConfig,
    ConfigValidationResult,
    get_config_summary,
    load_config,
    validate_config,
)

if TYPE_CHECKING:
    from src.extensions.manager import ExtensionManager

HealthStatus = Literal["pass", "warn", "fail"]


@dataclass(slots=True, frozen=True)
class HealthComponent:
    """Represents the outcome of a single health check."""

    name: str
    status: HealthStatus
    summary: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": self.name, "status": self.status}
        if self.summary:
            payload["summary"] = self.summary
        if self.details:
            payload["details"] = dict(self.details)
        return payload


@dataclass(slots=True, frozen=True)
class HealthReport:
    """Aggregated health snapshot across all registered checks."""

    status: HealthStatus
    checked_at: datetime
    components: tuple[HealthComponent, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checked_at": self.checked_at.isoformat(),
            "components": [component.as_dict() for component in self.components],
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class HealthProbe:
    """Execute registered health checks and compute a holistic status."""

    metadata_factory: Callable[[], Mapping[str, Any]] | None = None
    _checks: list[tuple[str, Callable[[], HealthComponent]]] = field(default_factory=list)

    def register(self, name: str, func: Callable[[], HealthComponent]) -> None:
        """Register a named health check."""

        self._checks.append((name, func))

    def snapshot(self) -> HealthReport:
        """Run all registered checks and return a report."""

        components: list[HealthComponent] = []
        for name, func in self._checks:
            try:
                component = func()
            except Exception as exc:  # pragma: no cover - defensive
                component = HealthComponent(
                    name=name,
                    status="fail",
                    summary="Health check raised an exception",
                    details={"exception": repr(exc)},
                )
            else:
                if component.name != name:
                    component = replace(component, name=name)
            components.append(component)

        overall: HealthStatus = "pass"
        if any(component.status == "fail" for component in components):
            overall = "fail"
        elif any(component.status == "warn" for component in components):
            overall = "warn"

        metadata = dict(self.metadata_factory()) if self.metadata_factory else {}

        return HealthReport(
            status=overall,
            checked_at=datetime.now(UTC),
            components=tuple(components),
            metadata=metadata,
        )


def _configuration_component(
    loader: Callable[[], AppConfig],
    validator: Callable[[AppConfig], ConfigValidationResult],
) -> HealthComponent:
    config = loader()
    validation = validator(config)
    status: HealthStatus = "pass"
    summary = "Configuration validated"
    if validation.errors:
        status = "fail"
        summary = "Configuration validation failed"
    elif validation.warnings:
        status = "warn"
        summary = "Configuration validated with warnings"

    details: dict[str, Any] = {
        "environment": config.environment.value,
        "log_level": config.log_level,
    }
    if validation.errors:
        details["errors"] = list(validation.errors)
    if validation.warnings:
        details["warnings"] = list(validation.warnings)

    return HealthComponent(
        name="configuration",
        status=status,
        summary=summary,
        details=details,
    )


def _cache_component(loader: Callable[[], AppConfig]) -> HealthComponent:
    config = loader()
    cache = config.cache
    details: dict[str, Any] = {
        "enabled": cache.enabled,
        "base_dir": str(cache.base_dir),
    }

    if not cache.enabled:
        return HealthComponent(
            name="cache",
            status="warn",
            summary="Cache disabled",
            details=details,
        )

    api_dir = cache.api_cache_dir()
    computation_dir = cache.computation_cache_dir()
    details.update({"api_dir": str(api_dir), "computation_dir": str(computation_dir)})

    try:
        cache.base_dir.mkdir(parents=True, exist_ok=True)
        api_dir.mkdir(parents=True, exist_ok=True)
        computation_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        details["error"] = str(exc)
        return HealthComponent(
            name="cache",
            status="fail",
            summary="Cache directories are not accessible",
            details=details,
        )

    writable = os.access(cache.base_dir, os.W_OK)
    details["writable"] = writable
    if not writable:
        return HealthComponent(
            name="cache",
            status="fail",
            summary="Cache directory is not writable",
            details=details,
        )

    return HealthComponent(
        name="cache",
        status="pass",
        summary="Cache directories ready",
        details=details,
    )


def _extensions_component(manager: ExtensionManager) -> HealthComponent:
    summary_extensions = [extension.name for extension in manager.summary_extensions]
    scenario_extensions = [extension.name for extension in manager.scenario_extensions]

    details = {
        "summary_extensions": summary_extensions,
        "scenario_extensions": scenario_extensions,
    }

    if not summary_extensions and not scenario_extensions:
        return HealthComponent(
            name="extensions",
            status="warn",
            summary="No extensions registered",
            details=details,
        )

    return HealthComponent(
        name="extensions",
        status="pass",
        summary=(
            f"{len(summary_extensions)} summary extensions, "
            f"{len(scenario_extensions)} scenario extensions active"
        ),
        details=details,
    )


def build_default_probe(
    *,
    config_loader: Callable[[], AppConfig] = load_config,
    config_validator: Callable[[AppConfig], ConfigValidationResult] = validate_config,
    summary_builder: Callable[[AppConfig | None], Mapping[str, Any]] = get_config_summary,
    telemetry_snapshot: Callable[[], Mapping[str, Any]] | None = None,
    extension_manager_provider: Callable[[], ExtensionManager] | None = None,
) -> HealthProbe:
    """Construct a HealthProbe with sensible defaults for the Idiot Index stack."""

    def metadata() -> Mapping[str, Any]:
        config = config_loader()
        data: dict[str, Any] = {"config": dict(summary_builder(config))}
        if telemetry_snapshot:
            data["telemetry"] = telemetry_snapshot()
        return data

    probe = HealthProbe(metadata_factory=metadata)
    probe.register(
        "configuration",
        lambda: _configuration_component(config_loader, config_validator),
    )
    probe.register("cache", lambda: _cache_component(config_loader))
    if extension_manager_provider is not None:
        probe.register(
            "extensions",
            lambda: _extensions_component(extension_manager_provider()),
        )
    return probe


__all__ = [
    "HealthComponent",
    "HealthProbe",
    "HealthReport",
    "HealthStatus",
    "build_default_probe",
]
