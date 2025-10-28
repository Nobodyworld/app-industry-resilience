"""Application configuration loading and validation utilities.

This module centralises how the application interprets environment variables
and exposes a strongly typed configuration object that other modules can
depend on. Configuration is intentionally loaded lazily so tests can supply
custom environments without mutating global state."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
    def from_raw(cls, raw: str | None) -> Environment:
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
class DistributedRateLimitConfig:
    """Configuration for Redis-backed rate limiting."""

    enabled: bool
    host: str | None
    port: int
    db: int
    username: str | None
    password: str | None
    ssl: bool
    socket_timeout: float | None
    key_prefix: str
    window_seconds: float

    def as_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "ssl": self.ssl,
            "socket_timeout": self.socket_timeout,
            "key_prefix": self.key_prefix,
            "window_seconds": self.window_seconds,
            "username": bool(self.username),
            "password": bool(self.password),
        }


@dataclass(frozen=True)
class RateLimitConfig:
    """Rate limit information for outbound API calls."""

    bea: int
    census: int
    default: int
    distributed: DistributedRateLimitConfig | None = None

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
class SnapshotRemoteStorageConfig:
    """Configuration for replicating observability snapshots to remote storage."""

    enabled: bool
    backend: str
    bucket: str | None
    prefix: str
    region: str | None
    endpoint_url: str | None
    access_key: str | None
    secret_key: str | None
    session_token: str | None
    use_ssl: bool
    force_path_style: bool
    max_retries: int
    options: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "backend": self.backend,
            "bucket": self.bucket,
            "prefix": self.prefix,
            "region": self.region,
            "endpoint_url": self.endpoint_url,
            "use_ssl": self.use_ssl,
            "force_path_style": self.force_path_style,
            "max_retries": self.max_retries,
            "has_access_key": bool(self.access_key),
            "has_secret_key": bool(self.secret_key),
            "has_session_token": bool(self.session_token),
            "options_keys": sorted(self.options.keys()) if self.options else [],
        }


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
    observability_snapshot_dir: Path
    observability_snapshot_retention_count: int
    observability_snapshot_retention_days: int
    observability_snapshot_min_interval_seconds: float
    observability_snapshot_remote: SnapshotRemoteStorageConfig | None
    max_csv_size_mb: int
    supported_years_bea: range
    supported_years_census: range
    normalization_dtype_overrides: Mapping[str, str] = field(default_factory=dict)

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

    def merge(self, other: ConfigValidationResult) -> ConfigValidationResult:
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

    cache_dir = Path(values.get("CACHE_DIR", ".cache")).expanduser().resolve()
    snapshot_dir_raw = values.get("OBSERVABILITY_SNAPSHOT_DIR")
    if snapshot_dir_raw and snapshot_dir_raw.strip():
        snapshot_dir = Path(snapshot_dir_raw).expanduser().resolve()
    else:
        snapshot_dir = Path("build/observability_snapshots").resolve()
    api_ttl = _parse_int(values.get("CACHE_TTL_API", "3600"), "CACHE_TTL_API")
    computation_ttl = _parse_int(
        values.get("CACHE_TTL_COMPUTATION", "1800"), "CACHE_TTL_COMPUTATION"
    )

    backend_mode = values.get("RATE_LIMIT_BACKEND", "memory").strip().lower()
    distributed_cfg: DistributedRateLimitConfig | None = None

    if backend_mode in {"redis", "distributed"}:
        redis_host = values.get("RATE_LIMIT_REDIS_HOST", "localhost").strip() or "localhost"
        redis_port = _parse_int(
            values.get("RATE_LIMIT_REDIS_PORT", "6379"), "RATE_LIMIT_REDIS_PORT"
        )
        redis_db = _parse_int(values.get("RATE_LIMIT_REDIS_DB", "0"), "RATE_LIMIT_REDIS_DB")
        redis_username = _clean_secret(values.get("RATE_LIMIT_REDIS_USERNAME"))
        redis_password = _clean_secret(values.get("RATE_LIMIT_REDIS_PASSWORD"))
        redis_ssl = _parse_bool(values.get("RATE_LIMIT_REDIS_SSL"))
        timeout_raw = values.get("RATE_LIMIT_REDIS_TIMEOUT_SECONDS")
        socket_timeout = (
            _parse_float(timeout_raw, "RATE_LIMIT_REDIS_TIMEOUT_SECONDS") if timeout_raw else None
        )
        key_prefix = (
            values.get("RATE_LIMIT_REDIS_KEY_PREFIX", "idiot-index").strip() or "idiot-index"
        )
        ttl_seconds = _parse_float(
            values.get("RATE_LIMIT_REDIS_TTL_SECONDS", "300"), "RATE_LIMIT_REDIS_TTL_SECONDS"
        )

        redis_url = _clean_secret(values.get("RATE_LIMIT_REDIS_URL"))
        if redis_url:
            parsed = urlparse(redis_url)
            if parsed.hostname:
                redis_host = parsed.hostname
            if parsed.port:
                redis_port = parsed.port
            if parsed.username:
                redis_username = parsed.username
            if parsed.password:
                redis_password = parsed.password
            if parsed.path and parsed.path != "/":
                try:
                    redis_db = int(parsed.path.lstrip("/"))
                except ValueError as exc:  # pragma: no cover - defensive
                    raise ConfigError(
                        f"RATE_LIMIT_REDIS_URL contains invalid database segment: '{parsed.path}'."
                    ) from exc
            if parsed.scheme.lower() in {"rediss", "redis+tls"}:
                redis_ssl = True

        distributed_cfg = DistributedRateLimitConfig(
            enabled=True,
            host=redis_host,
            port=redis_port,
            db=redis_db,
            username=redis_username,
            password=redis_password,
            ssl=redis_ssl,
            socket_timeout=socket_timeout,
            key_prefix=key_prefix,
            window_seconds=ttl_seconds,
        )

    rate_limits = RateLimitConfig(
        bea=_parse_int(
            values.get("BEA_RATE_LIMIT", "10" if environment.is_production else "30"),
            "BEA_RATE_LIMIT",
        ),
        census=_parse_int(
            values.get("CENSUS_RATE_LIMIT", "20" if environment.is_production else "50"),
            "CENSUS_RATE_LIMIT",
        ),
        default=_parse_int(
            values.get("DEFAULT_RATE_LIMIT", "5" if environment.is_production else "20"),
            "DEFAULT_RATE_LIMIT",
        ),
        distributed=distributed_cfg,
    )

    supported_years_bea = _parse_year_range(
        values.get("SUPPORTED_YEARS_BEA", "1997-2025"), "SUPPORTED_YEARS_BEA"
    )
    supported_years_census = _parse_year_range(
        values.get("SUPPORTED_YEARS_CENSUS", "1997-2024"), "SUPPORTED_YEARS_CENSUS"
    )

    snapshot_retention_count = _parse_int(
        values.get("OBSERVABILITY_SNAPSHOT_RETENTION_COUNT", "20"),
        "OBSERVABILITY_SNAPSHOT_RETENTION_COUNT",
    )
    snapshot_retention_days = _parse_int(
        values.get("OBSERVABILITY_SNAPSHOT_RETENTION_DAYS", "30"),
        "OBSERVABILITY_SNAPSHOT_RETENTION_DAYS",
    )
    snapshot_min_interval_seconds = _parse_float(
        values.get("OBSERVABILITY_SNAPSHOT_MIN_INTERVAL_SECONDS", "600"),
        "OBSERVABILITY_SNAPSHOT_MIN_INTERVAL_SECONDS",
    )

    normalization_overrides: dict[str, str] = {}
    overrides_raw = values.get("NORMALIZE_DTYPE_OVERRIDES")
    if overrides_raw:
        try:
            parsed = json.loads(overrides_raw)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ConfigError(
                "NORMALIZE_DTYPE_OVERRIDES must be a JSON object mapping column names to pandas dtypes."
            ) from exc
        if not isinstance(parsed, Mapping):
            raise ConfigError(
                "NORMALIZE_DTYPE_OVERRIDES must be a JSON object mapping column names to pandas dtypes."
            )
        normalization_overrides = {
            str(key).strip().lower(): str(value).strip() for key, value in parsed.items()
        }

    remote_backend_raw = values.get("OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND", "").strip()
    remote_backend = remote_backend_raw.lower()
    remote_prefix = _resolve_snapshot_remote_prefix(values)
    remote_cfg: SnapshotRemoteStorageConfig | None = None
    if remote_backend:
        if remote_backend in {"off", "none", "disabled"}:
            remote_cfg = None
        else:
            remote_options = _parse_remote_options(
                values.get("OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS")
            )
            max_retries = _parse_int(
                values.get("OBSERVABILITY_SNAPSHOT_REMOTE_MAX_RETRIES", "3"),
                "OBSERVABILITY_SNAPSHOT_REMOTE_MAX_RETRIES",
            )
            if remote_backend == "s3":
                bucket = _clean_secret(values.get("OBSERVABILITY_SNAPSHOT_S3_BUCKET"))
                region = _clean_secret(values.get("OBSERVABILITY_SNAPSHOT_S3_REGION"))
                endpoint_url = _clean_secret(values.get("OBSERVABILITY_SNAPSHOT_S3_ENDPOINT"))
                access_key = _clean_secret(values.get("OBSERVABILITY_SNAPSHOT_S3_ACCESS_KEY"))
                secret_key = _clean_secret(values.get("OBSERVABILITY_SNAPSHOT_S3_SECRET_KEY"))
                session_token = _clean_secret(values.get("OBSERVABILITY_SNAPSHOT_S3_SESSION_TOKEN"))
                use_ssl = _parse_bool(values.get("OBSERVABILITY_SNAPSHOT_S3_USE_SSL", "true"))
                force_path_style = _parse_bool(
                    values.get("OBSERVABILITY_SNAPSHOT_S3_FORCE_PATH_STYLE")
                )
                remote_cfg = SnapshotRemoteStorageConfig(
                    enabled=True,
                    backend="s3",
                    bucket=bucket,
                    prefix=remote_prefix,
                    region=region,
                    endpoint_url=endpoint_url,
                    access_key=access_key,
                    secret_key=secret_key,
                    session_token=session_token,
                    use_ssl=use_ssl,
                    force_path_style=force_path_style,
                    max_retries=max_retries,
                    options=remote_options,
                )
            elif remote_backend == "gcs":
                bucket = _clean_secret(values.get("OBSERVABILITY_SNAPSHOT_GCS_BUCKET"))
                project = _clean_secret(values.get("OBSERVABILITY_SNAPSHOT_GCS_PROJECT"))
                credentials_file = _clean_secret(
                    values.get("OBSERVABILITY_SNAPSHOT_GCS_CREDENTIALS_FILE")
                )
                credentials_json = _clean_secret(
                    values.get("OBSERVABILITY_SNAPSHOT_GCS_CREDENTIALS_JSON")
                )
                location = _clean_secret(values.get("OBSERVABILITY_SNAPSHOT_GCS_LOCATION"))
                timeout_raw = values.get("OBSERVABILITY_SNAPSHOT_GCS_TIMEOUT_SECONDS")
                timeout_seconds = (
                    _parse_float(
                        timeout_raw,
                        "OBSERVABILITY_SNAPSHOT_GCS_TIMEOUT_SECONDS",
                    )
                    if timeout_raw
                    else None
                )
                options = _merge_options(
                    remote_options,
                    {
                        "project": project,
                        "credentials_file": credentials_file,
                        "credentials_json": credentials_json,
                        "location": location,
                        "timeout_seconds": timeout_seconds,
                    },
                )
                remote_cfg = SnapshotRemoteStorageConfig(
                    enabled=True,
                    backend="gcs",
                    bucket=bucket,
                    prefix=remote_prefix,
                    region=None,
                    endpoint_url=None,
                    access_key=None,
                    secret_key=None,
                    session_token=None,
                    use_ssl=True,
                    force_path_style=False,
                    max_retries=max_retries,
                    options=options,
                )
            elif remote_backend in {"azure", "azure-blob", "azure_blob"}:
                container = _clean_secret(values.get("OBSERVABILITY_SNAPSHOT_AZURE_CONTAINER"))
                connection_string = _clean_secret(
                    values.get("OBSERVABILITY_SNAPSHOT_AZURE_CONNECTION_STRING")
                )
                account_url = _clean_secret(values.get("OBSERVABILITY_SNAPSHOT_AZURE_ACCOUNT_URL"))
                credential = _clean_secret(values.get("OBSERVABILITY_SNAPSHOT_AZURE_CREDENTIAL"))
                sas_token = _clean_secret(values.get("OBSERVABILITY_SNAPSHOT_AZURE_SAS_TOKEN"))
                timeout_raw = values.get("OBSERVABILITY_SNAPSHOT_AZURE_TIMEOUT_SECONDS")
                timeout_seconds = (
                    _parse_float(
                        timeout_raw,
                        "OBSERVABILITY_SNAPSHOT_AZURE_TIMEOUT_SECONDS",
                    )
                    if timeout_raw
                    else None
                )
                options = _merge_options(
                    remote_options,
                    {
                        "connection_string": connection_string,
                        "account_url": account_url,
                        "credential": credential,
                        "sas_token": sas_token,
                        "timeout_seconds": timeout_seconds,
                    },
                )
                remote_cfg = SnapshotRemoteStorageConfig(
                    enabled=True,
                    backend="azure-blob",
                    bucket=container,
                    prefix=remote_prefix,
                    region=None,
                    endpoint_url=None,
                    access_key=None,
                    secret_key=None,
                    session_token=None,
                    use_ssl=True,
                    force_path_style=False,
                    max_retries=max_retries,
                    options=options,
                )
            else:
                remote_cfg = SnapshotRemoteStorageConfig(
                    enabled=True,
                    backend=remote_backend_raw or remote_backend,
                    bucket=None,
                    prefix=remote_prefix,
                    region=None,
                    endpoint_url=None,
                    access_key=None,
                    secret_key=None,
                    session_token=None,
                    use_ssl=True,
                    force_path_style=False,
                    max_retries=max_retries,
                    options=remote_options,
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
        observability_snapshot_dir=snapshot_dir,
        observability_snapshot_retention_count=snapshot_retention_count,
        observability_snapshot_retention_days=snapshot_retention_days,
        observability_snapshot_min_interval_seconds=snapshot_min_interval_seconds,
        observability_snapshot_remote=remote_cfg,
        max_csv_size_mb=max_csv_size,
        supported_years_bea=supported_years_bea,
        supported_years_census=supported_years_census,
        normalization_dtype_overrides=normalization_overrides,
    )


def validate_config(config: AppConfig) -> ConfigValidationResult:
    """Validate configuration values returning any errors or warnings."""

    errors: list[str] = []
    warnings: list[str] = []

    if config.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        errors.append("LOG_LEVEL must be one of DEBUG, INFO, WARNING, ERROR, or CRITICAL.")

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
        errors.append("CACHE_TTL_COMPUTATION must be a positive integer of seconds.")

    if config.max_csv_size_mb <= 0:
        errors.append("MAX_CSV_SIZE_MB must be a positive integer.")

    if (
        config.observability_snapshot_dir.exists()
        and not config.observability_snapshot_dir.is_dir()
    ):
        errors.append("OBSERVABILITY_SNAPSHOT_DIR must reference a directory path.")

    if config.observability_snapshot_retention_count < 0:
        errors.append("OBSERVABILITY_SNAPSHOT_RETENTION_COUNT must be zero or positive.")
    if config.observability_snapshot_retention_days < 0:
        errors.append("OBSERVABILITY_SNAPSHOT_RETENTION_DAYS must be zero or positive.")
    if config.observability_snapshot_min_interval_seconds < 0:
        errors.append("OBSERVABILITY_SNAPSHOT_MIN_INTERVAL_SECONDS must be zero or positive.")

    for name, value in config.rate_limits.as_dict().items():
        if value <= 0:
            errors.append(f"Rate limit for {name} must be a positive integer.")

    if config.rate_limits.distributed and config.rate_limits.distributed.enabled:
        dist = config.rate_limits.distributed
        if dist.port <= 0:
            errors.append("RATE_LIMIT_REDIS_PORT must be a positive integer.")
        if dist.window_seconds <= 0:
            errors.append("RATE_LIMIT_REDIS_TTL_SECONDS must be positive.")
        if not dist.key_prefix:
            errors.append("RATE_LIMIT_REDIS_KEY_PREFIX must not be empty.")
        if dist.socket_timeout is not None and dist.socket_timeout <= 0:
            errors.append("RATE_LIMIT_REDIS_TIMEOUT_SECONDS must be positive when provided.")
        if dist.host is None and not dist.ssl:
            warnings.append("Redis host not specified; defaulting to localhost.")

    if config.observability_snapshot_remote and config.observability_snapshot_remote.enabled:
        remote = config.observability_snapshot_remote
        if remote.max_retries < 0:
            errors.append("OBSERVABILITY_SNAPSHOT_REMOTE_MAX_RETRIES must be zero or positive.")
        if remote.backend == "s3":
            if not remote.bucket:
                errors.append(
                    "OBSERVABILITY_SNAPSHOT_S3_BUCKET is required when remote shipping is enabled."
                )
            if remote.prefix:
                segments = remote.prefix.split("/")
                if segments and segments[-1] == "":
                    segments = segments[:-1]
                if any(part.strip() == "" for part in segments):
                    errors.append(
                        "OBSERVABILITY_SNAPSHOT_S3_PREFIX must not contain empty path segments."
                    )
            if remote.endpoint_url and not remote.access_key and not remote.secret_key:
                warnings.append(
                    "OBSERVABILITY_SNAPSHOT_S3_ENDPOINT set without credentials; ensure IAM role or instance profile provides access."
                )
        elif remote.backend == "gcs":
            if not remote.bucket:
                errors.append(
                    "OBSERVABILITY_SNAPSHOT_GCS_BUCKET is required when remote shipping is enabled."
                )
            if remote.prefix:
                segments = remote.prefix.split("/")
                if segments and segments[-1] == "":
                    segments = segments[:-1]
                if any(part.strip() == "" for part in segments):
                    errors.append(
                        "OBSERVABILITY_SNAPSHOT_GCS_PREFIX must not contain empty path segments."
                    )
        elif remote.backend in {"azure-blob", "azure_blob", "azure"}:
            if not remote.bucket:
                errors.append(
                    "OBSERVABILITY_SNAPSHOT_AZURE_CONTAINER is required when remote shipping is enabled."
                )
            if remote.prefix:
                segments = remote.prefix.split("/")
                if segments and segments[-1] == "":
                    segments = segments[:-1]
                if any(part.strip() == "" for part in segments):
                    errors.append(
                        "OBSERVABILITY_SNAPSHOT_AZURE_PREFIX must not contain empty path segments."
                    )
            options = remote.options or {}
            if not options.get("connection_string") and not options.get("account_url"):
                warnings.append(
                    "Azure Blob backend configured without connection string or account URL; ensure default credentials are available."
                )
        else:
            backend_label = remote.backend or "unspecified"
            if backend_label.startswith("plugin:"):
                if not remote.options:
                    warnings.append(
                        "OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS not provided; verify plugin backends have the configuration they require."
                    )
            else:
                warnings.append(
                    "OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND "
                    f"'{backend_label}' requires a matching replication extension; without one, replication remains local-only."
                )

    if config.environment.is_production:
        if not config.bea_api_key:
            errors.append("BEA_API_KEY is required when ENVIRONMENT is production.")
        if not config.census_api_key:
            errors.append("CENSUS_API_KEY is required when ENVIRONMENT is production.")
    else:
        if not config.bea_api_key:
            warnings.append("BEA_API_KEY is not set – production data will be unavailable.")
        if not config.census_api_key:
            warnings.append("CENSUS_API_KEY is not set – Census data will be unavailable.")

    for column, dtype in config.normalization_dtype_overrides.items():
        if not column:
            errors.append("NORMALIZE_DTYPE_OVERRIDES keys must be non-empty strings.")
        if not dtype:
            errors.append("NORMALIZE_DTYPE_OVERRIDES values must be non-empty strings.")

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
        "observability_snapshot": {
            "dir": str(config.observability_snapshot_dir),
            "retention_count": config.observability_snapshot_retention_count,
            "retention_days": config.observability_snapshot_retention_days,
            "min_interval_seconds": config.observability_snapshot_min_interval_seconds,
        },
        "observability_snapshot_remote": (
            config.observability_snapshot_remote.as_dict()
            if config.observability_snapshot_remote
            else {"enabled": False, "backend": "none"}
        ),
        "cache_ttl": {
            "api": config.cache.api_ttl_seconds,
            "computation": config.cache.computation_ttl_seconds,
        },
        "rate_limits": config.rate_limits.as_dict(),
        "rate_limit_backend": {
            "mode": (
                "redis"
                if config.rate_limits.distributed and config.rate_limits.distributed.enabled
                else "memory"
            ),
            "config": (
                config.rate_limits.distributed.as_dict()
                if config.rate_limits.distributed and config.rate_limits.distributed.enabled
                else None
            ),
        },
        "normalization_dtype_overrides": dict(config.normalization_dtype_overrides),
        "max_csv_size_mb": config.max_csv_size_mb,
        "supported_years_bea": _range_to_tuple(config.supported_years_bea),
        "supported_years_census": _range_to_tuple(config.supported_years_census),
        "bea_key_set": bool(config.bea_api_key),
        "census_key_set": bool(config.census_api_key),
        "bea_api_version": config.bea_api_version or "default",
        "bea_api_base_urls": list(config.bea_api_base_urls),
    }


def _parse_remote_options(raw: str | None) -> Mapping[str, Any] | None:
    """Parse backend-specific options encoded as JSON."""

    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ConfigError("OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS must be a JSON object.") from exc
    if not isinstance(parsed, Mapping):
        raise ConfigError("OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS must be a JSON object.")
    options: dict[str, Any] = {}
    for key, value in parsed.items():
        key_str = str(key).strip()
        if not key_str:
            raise ConfigError(
                "OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS keys must be non-empty strings."
            )
        options[key_str] = value
    return options


def _merge_options(
    base: Mapping[str, Any] | None, extra: Mapping[str, Any]
) -> Mapping[str, Any] | None:
    """Merge backend option dictionaries while dropping ``None`` values."""

    merged: dict[str, Any] = {}
    if base:
        for key, value in base.items():
            if value is not None:
                merged[str(key)] = value
    for key, value in extra.items():
        if value is None:
            continue
        merged[str(key)] = value
    return merged or None


def _resolve_snapshot_remote_prefix(values: Mapping[str, str]) -> str:
    """Return a normalised remote prefix from supported environment variables."""

    for key in (
        "OBSERVABILITY_SNAPSHOT_REMOTE_PREFIX",
        "OBSERVABILITY_SNAPSHOT_S3_PREFIX",
        "OBSERVABILITY_SNAPSHOT_GCS_PREFIX",
        "OBSERVABILITY_SNAPSHOT_AZURE_PREFIX",
    ):
        raw = values.get(key)
        if raw and raw.strip():
            return _normalise_remote_prefix(raw)
    return ""


def _normalise_remote_prefix(raw: str | None) -> str:
    """Ensure prefixes end with a single slash when provided."""

    if raw is None:
        return ""
    value = raw.strip().strip("/")
    if not value:
        return ""
    return f"{value}/"


def _parse_int(value: str, name: str) -> int:
    """Return ``value`` as an integer or raise :class:`ConfigError`."""

    try:
        return int(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ConfigError(f"{name} must be an integer, received '{value}'.") from exc


def _parse_float(value: str, name: str) -> float:
    """Return ``value`` as a float or raise :class:`ConfigError`."""

    try:
        return float(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ConfigError(f"{name} must be numeric, received '{value}'.") from exc


def _parse_bool(value: str | None) -> bool:
    """Interpret a string flag into a boolean value."""

    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_year_range(value: str, name: str) -> range:
    """Parse a ``start-end`` formatted string into an inclusive range."""

    try:
        start_str, end_str = value.split("-", maxsplit=1)
        start = int(start_str)
        end = int(end_str)
    except (ValueError, TypeError) as exc:  # pragma: no cover - defensive
        raise ConfigError(f"{name} must use 'start-end' format, received '{value}'.") from exc
    if start >= end:
        raise ConfigError(f"{name} start must be less than end, received '{value}'.")
    return range(start, end + 1)


def _clean_secret(value: str | None) -> str | None:
    """Strip whitespace from a secret value and normalise empty strings to ``None``."""

    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _range_to_tuple(value: range) -> tuple[int, int]:
    """Convert a ``range`` to an inclusive ``(start, end)`` tuple."""

    return value.start, value.stop - 1


def _parse_url_list(raw: str, name: str) -> tuple[str, ...]:
    """Split and validate a comma-separated list of absolute URLs."""

    urls = [part.strip() for part in raw.split(",") if part.strip()]
    if not urls:
        raise ConfigError(f"{name} must contain at least one URL.")

    validated: dict[str, None] = {}
    for candidate in urls:
        parsed = urlparse(candidate)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            raise ConfigError(f"{name} entry '{candidate}' must be an absolute http(s) URL.")
        validated[candidate] = None

    # TODO-P3(6h): Cache parsed URLs on disk to avoid reparsing large lists
    # on every process start once configuration hot-reload lands.
    return tuple(validated.keys())


__all__ = [
    "AppConfig",
    "CacheConfig",
    "ConfigError",
    "ConfigValidationResult",
    "Environment",
    "DistributedRateLimitConfig",
    "SnapshotRemoteStorageConfig",
    "RateLimitConfig",
    "get_config_summary",
    "load_config",
    "validate_config",
]
