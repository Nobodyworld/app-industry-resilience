"""Core domain modules for the Idiot Index application."""

from .analytics import (
    HealthAggregate,
    HealthBand,
    HealthBandBreakdown,
    HealthRisk,
    HealthScoreConfig,
    HealthSummary,
    compute_health_scores,
    summarise_health,
)
from .cache import Cache, CacheStats, get_api_cache, get_computation_cache
from .config import (
    AppConfig,
    CacheConfig,
    ConfigError,
    ConfigValidationResult,
    DistributedRateLimitConfig,
    Environment,
    RateLimitConfig,
    SnapshotRemoteStorageConfig,
    get_config_summary,
    load_config,
    validate_config,
)
from .metrics import MetricConfig, compute_metrics, format_for_display
from .normalize import (
    DEFAULT_COLUMN_ALIASES,
    NormalizationOptions,
    apply_dtype_overrides,
    normalize_columns,
)
from .security import FilePolicy, SecurityUtils
from .types import ValidationResult
from .utils import (
    HTTPRequestError,
    InvalidJSONError,
    RetryEvent,
    RetryPolicy,
    register_retry_observer,
    safe_get_json,
)

__all__ = [
    "AppConfig",
    "Cache",
    "HealthAggregate",
    "HealthBand",
    "HealthBandBreakdown",
    "HealthRisk",
    "HealthScoreConfig",
    "HealthSummary",
    "CacheConfig",
    "CacheStats",
    "ConfigError",
    "ConfigValidationResult",
    "DEFAULT_COLUMN_ALIASES",
    "NormalizationOptions",
    "apply_dtype_overrides",
    "DistributedRateLimitConfig",
    "Environment",
    "FilePolicy",
    "HTTPRequestError",
    "InvalidJSONError",
    "MetricConfig",
    "RetryEvent",
    "RateLimitConfig",
    "SnapshotRemoteStorageConfig",
    "RetryPolicy",
    "register_retry_observer",
    "SecurityUtils",
    "ValidationResult",
    "compute_health_scores",
    "compute_metrics",
    "format_for_display",
    "get_api_cache",
    "get_computation_cache",
    "get_config_summary",
    "load_config",
    "normalize_columns",
    "safe_get_json",
    "summarise_health",
    "validate_config",
]
