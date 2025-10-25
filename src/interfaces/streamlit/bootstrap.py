"""Streamlit bootstrap utilities for lazy configuration handling.

These helpers centralise configuration loading and validation so the UI can
surface errors without costly import-time side effects. The module remains free
of Streamlit imports to keep layering clean and simplify unit testing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

from src.core import AppConfig, ConfigError, ConfigValidationResult, load_config, validate_config


class BootstrapError(RuntimeError):
    """Raised when configuration cannot be prepared for the UI."""


@dataclass(frozen=True)
class SidebarContext:
    """Details required to render sidebar controls safely."""

    default_year: int
    year_bounds: tuple[int, int]

    def clamp_year(self, year: int) -> int:
        """Clamp ``year`` to the configured inclusive bounds."""

        lower, upper = self.year_bounds
        if year < lower:
            return lower
        if year > upper:
            return upper
        return year

    def normalise_year(self, year: int | None) -> int:
        """Return a year that respects configured bounds and defaults."""

        if year is None:
            return self.default_year
        return self.clamp_year(year)


@dataclass(frozen=True)
class BootstrapState:
    """Container holding configuration and validation status."""

    config: AppConfig
    validation: ConfigValidationResult

    @property
    def errors(self) -> tuple[str, ...]:
        """Return validation errors discovered during bootstrap."""

        return self.validation.errors

    @property
    def warnings(self) -> tuple[str, ...]:
        """Return non-blocking validation warnings."""

        return self.validation.warnings

    @property
    def is_ready(self) -> bool:
        """Return True when validation found no blocking errors."""

        return self.validation.is_ok

    @property
    def has_warnings(self) -> bool:
        """Return True when validation surfaced non-blocking warnings."""

        return bool(self.validation.warnings)

    @property
    def supported_year_bounds(self) -> tuple[int, int]:
        """Return inclusive min/max year supported by either data source."""

        bea_range = self.config.supported_years_bea
        census_range = self.config.supported_years_census
        return (
            min(bea_range.start, census_range.start),
            max(bea_range.stop - 1, census_range.stop - 1),
        )

    @property
    def sidebar_context(self) -> SidebarContext:
        """Build the sidebar context for downstream UI helpers."""

        bounds = self.supported_year_bounds
        default_year = SidebarContext(
            default_year=self.config.default_year,
            year_bounds=bounds,
        ).clamp_year(self.config.default_year)

        return SidebarContext(default_year=default_year, year_bounds=bounds)

    def ensure_ready(self) -> AppConfig:
        """Return the config or raise if blocking errors exist."""

        if not self.is_ready:
            detail = "; ".join(self.errors) or "configuration errors detected"
            raise BootstrapError(f"Configuration contains blocking errors: {detail}")
        return self.config


def _normalise_env(env: Mapping[str, object] | None) -> tuple[tuple[str, str], ...] | None:
    if env is None:
        return None
    items = tuple(
        sorted((key.upper(), str(value)) for key, value in env.items() if value is not None)
    )
    return items or None


@lru_cache(maxsize=32)
def _load_state(env_items: tuple[tuple[str, str], ...] | None) -> BootstrapState:
    mapping = dict(env_items) if env_items is not None else None
    config = load_config(mapping)
    validation = validate_config(config)
    return BootstrapState(config=config, validation=validation)


def get_bootstrap_state(env: Mapping[str, object] | None = None) -> BootstrapState:
    """Return cached configuration + validation results for the UI."""

    try:
        return _load_state(_normalise_env(env))
    except ConfigError as exc:  # pragma: no cover - defensive passthrough
        raise BootstrapError(str(exc)) from exc


def reset_bootstrap_state() -> None:
    """Clear cached bootstrap state (primarily for tests)."""

    _load_state.cache_clear()


__all__ = [
    "BootstrapError",
    "BootstrapState",
    "SidebarContext",
    "get_bootstrap_state",
    "reset_bootstrap_state",
]
