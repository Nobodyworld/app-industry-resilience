"""Explicit public diagnostics projections; operator payloads stay private."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from src.core.config import AppConfig


def build_public_diagnostics(config: AppConfig) -> dict[str, object]:
    """Select anonymous-user-safe fields without serialising configuration mappings."""

    distributed = config.rate_limits.distributed
    version = config.bea_api_version
    return {
        "environment": config.environment.value,
        "log_level": (
            config.log_level
            if config.log_level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
            else "unknown"
        ),
        "default_year": config.default_year,
        "cache_enabled": config.cache.enabled,
        "cache_ttl": {
            "api": config.cache.api_ttl_seconds,
            "computation": config.cache.computation_ttl_seconds,
        },
        "rate_limits": {
            "bea": config.rate_limits.bea,
            "census": config.rate_limits.census,
            "default": config.rate_limits.default,
        },
        "rate_limit_mode": "redis" if distributed and distributed.enabled else "memory",
        "observability_snapshot": {
            "retention_count": config.observability_snapshot_retention_count,
            "retention_days": config.observability_snapshot_retention_days,
            "min_interval_seconds": config.observability_snapshot_min_interval_seconds,
        },
        "max_csv_size_mb": config.max_csv_size_mb,
        "supported_years_bea": (
            config.supported_years_bea.start,
            config.supported_years_bea.stop - 1,
        ),
        "supported_years_census": (
            config.supported_years_census.start,
            config.supported_years_census.stop - 1,
        ),
        "bea_key_set": bool(config.bea_api_key),
        "census_key_set": bool(config.census_api_key),
        # Version configuration is free text. Only a numeric version may be public.
        "bea_api_version": (
            version
            if version and re.fullmatch(r"v?[0-9]+(?:\.[0-9]+){0,2}", version)
            else "default"
        ),
    }


def _count(value: object) -> int | None:
    if (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    ):
        return int(value)
    return None


def _captured_at(value: object) -> datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return None


def build_public_snapshot_history(
    history: Sequence[Mapping[str, object]],
) -> list[dict[str, Any]]:
    """Allow only timestamps, counts and fixed status labels into charts and tables.

    Never forward identifiers, metadata, metric names, backends, destinations or
    error payloads, including strings substituted for otherwise numeric fields.
    """

    public = []
    for snapshot in history:
        events_raw = snapshot.get("events")
        events = events_raw if isinstance(events_raw, Mapping) else {}
        replication = snapshot.get("replication")
        status = replication.get("status") if isinstance(replication, Mapping) else None
        public.append(
            {
                "captured_at": _captured_at(snapshot.get("captured_at")),
                "event_total": _count(snapshot.get("event_total")),
                "errors": _count(events.get("error")),
                "success": _count(events.get("success")),
                "replication_status": (
                    (status if status in ("success", "error") else "unknown")
                    if isinstance(replication, Mapping)
                    else "unavailable"
                ),
                "has_error": bool(snapshot.get("last_error")),
            }
        )
    return public
