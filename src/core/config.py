"""Application configuration loading and validation utilities.

This module centralises how the application interprets environment variables
and exposes a strongly typed configuration object that other modules can
depend on.  Configuration is intentionally loaded lazily so tests can supply
custom environments without mutating global state.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping, MutableMapping

from dotenv import load_dotenv

load_dotenv()


class ConfigError(ValueError):
    """Raised when configuration values cannot be parsed."""


class Environment(str, Enum):
    """Normalised environment indicator."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"

    @classmethod
    def from_raw(cls, raw: str | None) -> "Environment":
        if raw is None:
            return cls.DEVELOPMENT
        value = raw.strip().lower()
        if value in {"development", "dev"}:
            return cls.DEVELOPMENT
        if value in {"production", "prod"}:
            return cls.PRODUCTION
        if value in {"testing", "test", "ci"}:
            return cls.TESTING
        raise ConfigError(
            f"Unsupported ENVIRONMENT '{raw}'. Expected development, production, or testing."
        )

    @property
    def is_production(self) -> bool:
        return self is self.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self is self.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        return self is self.TESTING


@dataclass(frozen=True)
class RateLimitConfig:
    """Rate limit information for outbound API calls."""

    bea: int
    census: int
    default: int

    def as_dict(self) -> dict[str, int]:
        return {"bea": self.bea, "census": self.census, "default": self.default}


@dataclass(frozen=True)
class CacheConfig:
    """Configuration for cache directories and TTLs."""

    enabled: bool
    base_dir: Path
    api_ttl_seconds: int
    computation_ttl_seconds: int

    def api_cache_dir(self) -> Path:
        return self.base_dir / "api"

    def computation_cache_dir(self) -> Path:
        return self.base_dir / "computation"


@dataclass(frozen=True)
class AppConfig:
    """Primary configuration object consumed by the application."""

    environment: Environment
    log_level: str
    default_year: int
    bea_api_key: str | None
    census_api_key: str | None
    bea_api_version: str | None
    bea_api_base_urls: tuple[str, ...]
    rate_limits: RateLimitConfig
    cache: CacheConfig
    max_csv_size_mb: int
    supported_years_bea: range
    supported_years_census: range

    @property
    def is_production(self) -> bool:
        return self.environment.is_production

    @property
    def is_development(self) -> bool:
        return self.environment.is_development

    @property
    def is_testing(self) -> bool:
        return self.environment.is_testing


@dataclass(frozen=True)
class ConfigValidationResult:
    """Outcome of validating an :class:`AppConfig`."""

    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_ok(self) -> bool:
        return not self.errors

    def merge(self, other: "ConfigValidationResult") -> "ConfigValidationResult":
        return ConfigValidationResult(
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
        )


def load_config(env: Mapping[str, str] | None = None) -> AppConfig:
    """Load configuration from the provided environment mapping.

    Parameters
    ----------
    env:
        Optional mapping of environment variable names to values. When omitted
        the current process environment is used.
    """

    values: MutableMapping[str, str] = {
        key.upper(): value for key, value in (env or os.environ).items()
    }

    environment = Environment.from_raw(values.get("ENVIRONMENT"))

    default_year = _parse_int(values.get("DEFAULT_YEAR", "2021"), "DEFAULT_YEAR")
    log_level = values.get("LOG_LEVEL", "INFO").strip().upper()
    cache_enabled = _parse_bool(values.get("CACHE_ENABLED", "true"))
    max_csv_size = _parse_int(values.get("MAX_CSV_SIZE_MB", "50"), "MAX_CSV_SIZE_MB")

    bea_api_key = _clean_secret(values.get("BEA_API_KEY"))
    census_api_key = _clean_secret(values.get("CENSUS_API_KEY"))
    bea_api_version = _clean_secret(values.get("BEA_API_VERSION"))
    bea_api_base_urls = _parse_url_list(
        values.get("BEA_API_BASE_URLS", "https://apps.bea.gov/api/data"),
        "BEA_API_BASE_URLS",
    )

    cache_dir = Path(values.get("CACHE_DIR", ".cache")).resolve()
    api_ttl = _parse_int(values.get("CACHE_TTL_API", "3600"), "CACHE_TTL_API")
    computation_ttl = _parse_int(
        values.get("CACHE_TTL_COMPUTATION", "1800"), "CACHE_TTL_COMPUTATION"
    )

    rate_limits = RateLimitConfig(
        bea=_parse_int(
            values.get("BEA_RATE_LIMIT", "10" if environment.is_production else "30"),
            "BEA_RATE_LIMIT",
        ),
        census=_parse_int(
            values.get(
                "CENSUS_RATE_LIMIT", "20" if environment.is_production else "50"
            ),
            "CENSUS_RATE_LIMIT",
        ),
        default=_parse_int(
            values.get(
                "DEFAULT_RATE_LIMIT", "5" if environment.is_production else "20"
            ),
            "DEFAULT_RATE_LIMIT",
        ),
    )

    supported_years_bea = _parse_year_range(
        values.get("SUPPORTED_YEARS_BEA", "1997-2025"), "SUPPORTED_YEARS_BEA"
    )
    supported_years_census = _parse_year_range(
        values.get("SUPPORTED_YEARS_CENSUS", "1997-2024"), "SUPPORTED_YEARS_CENSUS"
    )

    return AppConfig(
        environment=environment,
        log_level=log_level,
        default_year=default_year,
        bea_api_key=bea_api_key,
        census_api_key=census_api_key,
        bea_api_version=bea_api_version,
        bea_api_base_urls=bea_api_base_urls,
        rate_limits=rate_limits,
        cache=CacheConfig(
            enabled=cache_enabled,
            base_dir=cache_dir,
            api_ttl_seconds=api_ttl,
            computation_ttl_seconds=computation_ttl,
        ),
        max_csv_size_mb=max_csv_size,
        supported_years_bea=supported_years_bea,
        supported_years_census=supported_years_census,
    )


def validate_config(config: AppConfig) -> ConfigValidationResult:
    """Validate configuration values returning any errors or warnings."""

    errors: list[str] = []
    warnings: list[str] = []

    if config.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        errors.append(
            "LOG_LEVEL must be one of DEBUG, INFO, WARNING, ERROR, or CRITICAL."
        )

    if config.default_year not in config.supported_years_bea:
        errors.append(
            f"DEFAULT_YEAR {config.default_year} is outside BEA supported range "
            f"{config.supported_years_bea.start}-{config.supported_years_bea.stop - 1}."
        )

    if config.default_year not in config.supported_years_census:
        warnings.append(
            f"DEFAULT_YEAR {config.default_year} is not within Census supported "
            f"range {config.supported_years_census.start}-"
            f"{config.supported_years_census.stop - 1}."
        )

    if config.cache.api_ttl_seconds <= 0:
        errors.append("CACHE_TTL_API must be a positive integer of seconds.")
    if config.cache.computation_ttl_seconds <= 0:
        errors.append(
            "CACHE_TTL_COMPUTATION must be a positive integer of seconds."
        )

    if config.max_csv_size_mb <= 0:
        errors.append("MAX_CSV_SIZE_MB must be a positive integer.")

    for name, value in config.rate_limits.as_dict().items():
        if value <= 0:
            errors.append(f"Rate limit for {name} must be a positive integer.")

    if config.environment.is_production:
        if not config.bea_api_key:
            errors.append("BEA_API_KEY is required when ENVIRONMENT is production.")
        if not config.census_api_key:
            errors.append(
                "CENSUS_API_KEY is required when ENVIRONMENT is production."
            )
    else:
        if not config.bea_api_key:
            warnings.append(
                "BEA_API_KEY is not set – production data will be unavailable."
            )
        if not config.census_api_key:
            warnings.append(
                "CENSUS_API_KEY is not set – Census data will be unavailable."
            )

    return ConfigValidationResult(errors=tuple(errors), warnings=tuple(warnings))


def get_config_summary(config: AppConfig | None = None) -> dict[str, object]:
    """Return a serialisable summary omitting sensitive values."""

    config = config or load_config()
    return {
        "environment": config.environment.value,
        "log_level": config.log_level,
        "default_year": config.default_year,
        "cache_enabled": config.cache.enabled,
        "cache_dir": str(config.cache.base_dir),
        "cache_ttl": {
            "api": config.cache.api_ttl_seconds,
            "computation": config.cache.computation_ttl_seconds,
        },
        "rate_limits": config.rate_limits.as_dict(),
        "max_csv_size_mb": config.max_csv_size_mb,
        "supported_years_bea": _range_to_tuple(config.supported_years_bea),
        "supported_years_census": _range_to_tuple(config.supported_years_census),
        "bea_key_set": bool(config.bea_api_key),
        "census_key_set": bool(config.census_api_key),
        "bea_api_version": config.bea_api_version or "default",
        "bea_api_base_urls": list(config.bea_api_base_urls),
    }


def _parse_int(value: str, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ConfigError(f"{name} must be an integer, received '{value}'.") from exc


def _parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_year_range(value: str, name: str) -> range:
    try:
        start_str, end_str = value.split("-", maxsplit=1)
        start = int(start_str)
        end = int(end_str)
    except (ValueError, TypeError) as exc:  # pragma: no cover - defensive
        raise ConfigError(
            f"{name} must use 'start-end' format, received '{value}'."
        ) from exc
    if start >= end:
        raise ConfigError(
            f"{name} start must be less than end, received '{value}'."
        )
    return range(start, end + 1)


def _clean_secret(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _range_to_tuple(value: range) -> tuple[int, int]:
    return value.start, value.stop - 1


def _parse_url_list(raw: str, name: str) -> tuple[str, ...]:
    urls = [part.strip() for part in raw.split(",") if part.strip()]
    if not urls:
        raise ConfigError(f"{name} must contain at least one URL.")
    return tuple(urls)


__all__ = [
    "AppConfig",
    "CacheConfig",
    "ConfigError",
    "ConfigValidationResult",
    "Environment",
    "RateLimitConfig",
    "get_config_summary",
    "load_config",
    "validate_config",
]

