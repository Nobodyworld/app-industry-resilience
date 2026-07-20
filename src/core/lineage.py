"""Typed, redacted data-lineage contracts for analytical datasets.

The lineage envelope is deliberately framework-independent.  It records a small,
allowlisted description of where a dataset came from and which bounded
transformations were applied without copying arbitrary dataframe metadata.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, TypeAlias

import pandas as pd

LINEAGE_ATTR_KEY = "lineage"
LINEAGE_SCHEMA_VERSION = "1"
CALCULATION_VERSION = "1"
TRANSFORMATION_VERSION = "1"

JSONScalar: TypeAlias = str | int | float | bool | None


class LineageSourceKind(StrEnum):
    """Stable categories describing the original dataset boundary."""

    BUNDLED_SAMPLE = "bundled_sample"
    OFFICIAL_SNAPSHOT = "official_snapshot"
    LIVE_PROVIDER = "live_provider"
    INLINE_RECORDS = "inline_records"
    UPLOADED_FILE = "uploaded_file"
    CACHE = "cache"


class LineageRetrievalMode(StrEnum):
    """How the current dataset instance entered the application."""

    BUNDLED = "bundled"
    SNAPSHOT = "snapshot"
    LIVE = "live"
    INLINE = "inline"
    UPLOAD = "upload"
    CACHE = "cache"


class LineageCacheStatus(StrEnum):
    """Whether a cache participated in producing the current dataset."""

    NOT_USED = "not_used"
    MISS = "miss"
    HIT = "hit"


_ALLOWED_STEP_DETAILS: dict[str, frozenset[str]] = {
    "source_load": frozenset({"record_count"}),
    "normalize_columns": frozenset({"column_count"}),
    "compute_metrics": frozenset({"metric_count"}),
    "compute_health_scores": frozenset({"group_by", "top_risk_limit"}),
    "filter_records": frozenset({"filter_applied", "result_count"}),
    "scenario_adjustment": frozenset(
        {
            "adjustment_count",
            "targeted_industry_count",
            "all_industries",
            "gross_output_delta_pct",
            "materials_cost_delta_pct",
            "value_added_delta_pct",
            "intermediate_inputs_delta_pct",
        }
    ),
    "export_serialization": frozenset({"format", "scope", "record_count"}),
}
_ALLOWED_STEP_NAMES = frozenset(_ALLOWED_STEP_DETAILS)
_FORBIDDEN_MARKERS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "bearer",
        "cache_dir",
        "cache_key",
        "cookie",
        "password",
        "redis_url",
        "secret",
        "token",
    }
)
_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[a-zA-Z]:[\\/]")


@dataclass(frozen=True)
class LineageStep:
    """One bounded transformation applied to a dataset."""

    name: str
    version: str = TRANSFORMATION_VERSION
    details: Mapping[str, JSONScalar] = field(default_factory=dict)

    def __post_init__(self) -> None:
        name = _clean_identifier(self.name, field_name="transformation name")
        if name not in _ALLOWED_STEP_NAMES:
            raise ValueError(f"Unsupported lineage transformation: {name}")
        version = _clean_version(self.version, field_name="transformation version")
        details = MappingProxyType(_sanitize_step_details(name, self.details))
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "details", details)

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-safe representation."""

        return {
            "name": self.name,
            "version": self.version,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class LineageEnvelope:
    """Typed provenance attached to one analytical dataset."""

    source: str
    source_kind: LineageSourceKind
    dataset_id: str
    observation_period: str
    retrieval_mode: LineageRetrievalMode
    is_sample: bool
    is_official: bool
    provider: str | None = None
    acquired_at: datetime | None = None
    snapshot_at: datetime | None = None
    calculation_version: str = CALCULATION_VERSION
    transformations: tuple[LineageStep, ...] = ()
    cache_status: LineageCacheStatus = LineageCacheStatus.NOT_USED
    schema_version: str = LINEAGE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        source = _clean_identifier(self.source, field_name="source")
        dataset_id = _clean_identifier(self.dataset_id, field_name="dataset_id")
        observation_period = _clean_public_text(
            self.observation_period,
            field_name="observation_period",
            maximum_length=128,
        )
        provider = (
            _clean_public_text(self.provider, field_name="provider", maximum_length=160)
            if self.provider is not None
            else None
        )
        calculation_version = _clean_version(
            self.calculation_version,
            field_name="calculation_version",
        )
        schema_version = _clean_version(self.schema_version, field_name="schema_version")
        if schema_version != LINEAGE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported lineage schema version: {schema_version}")
        if self.is_sample and self.is_official:
            raise ValueError("Sample lineage cannot also be marked as official.")

        source_kind = LineageSourceKind(self.source_kind)
        retrieval_mode = LineageRetrievalMode(self.retrieval_mode)
        cache_status = LineageCacheStatus(self.cache_status)
        acquired_at = _normalise_datetime(self.acquired_at, field_name="acquired_at")
        snapshot_at = _normalise_datetime(self.snapshot_at, field_name="snapshot_at")
        transformations = tuple(_coerce_step(step) for step in self.transformations)

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "source_kind", source_kind)
        object.__setattr__(self, "dataset_id", dataset_id)
        object.__setattr__(self, "observation_period", observation_period)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "acquired_at", acquired_at)
        object.__setattr__(self, "snapshot_at", snapshot_at)
        object.__setattr__(self, "retrieval_mode", retrieval_mode)
        object.__setattr__(self, "calculation_version", calculation_version)
        object.__setattr__(self, "transformations", transformations)
        object.__setattr__(self, "cache_status", cache_status)
        object.__setattr__(self, "schema_version", schema_version)

    def as_dict(self) -> dict[str, Any]:
        """Return the public, explicitly allowlisted lineage payload."""

        return {
            "schema_version": self.schema_version,
            "source": self.source,
            "source_kind": self.source_kind.value,
            "dataset_id": self.dataset_id,
            "provider": self.provider,
            "observation_period": self.observation_period,
            "acquired_at": _format_datetime(self.acquired_at),
            "snapshot_at": _format_datetime(self.snapshot_at),
            "retrieval_mode": self.retrieval_mode.value,
            "is_sample": self.is_sample,
            "is_official": self.is_official,
            "calculation_version": self.calculation_version,
            "transformations": [step.as_dict() for step in self.transformations],
            "cache_status": self.cache_status.value,
        }


def build_lineage(
    *,
    source: str,
    source_kind: LineageSourceKind | str,
    dataset_id: str,
    observation_period: str | int,
    retrieval_mode: LineageRetrievalMode | str,
    is_sample: bool,
    is_official: bool,
    provider: str | None = None,
    acquired_at: datetime | str | None = None,
    snapshot_at: datetime | str | None = None,
    calculation_version: str = CALCULATION_VERSION,
    transformations: Sequence[LineageStep | Mapping[str, Any]] = (),
    cache_status: LineageCacheStatus | str = LineageCacheStatus.NOT_USED,
) -> LineageEnvelope:
    """Build and validate a typed lineage envelope."""

    return LineageEnvelope(
        source=source,
        source_kind=LineageSourceKind(source_kind),
        dataset_id=dataset_id,
        provider=provider,
        observation_period=str(observation_period),
        acquired_at=_normalise_datetime(acquired_at, field_name="acquired_at"),
        snapshot_at=_normalise_datetime(snapshot_at, field_name="snapshot_at"),
        retrieval_mode=LineageRetrievalMode(retrieval_mode),
        is_sample=bool(is_sample),
        is_official=bool(is_official),
        calculation_version=calculation_version,
        transformations=tuple(_coerce_step(step) for step in transformations),
        cache_status=LineageCacheStatus(cache_status),
    )


def lineage_to_dict(lineage: LineageEnvelope) -> dict[str, Any]:
    """Serialize lineage without copying arbitrary metadata."""

    return lineage.as_dict()


def lineage_from_mapping(payload: Mapping[str, Any]) -> LineageEnvelope:
    """Parse only the typed, allowlisted fields from a mapping."""

    transformations_raw = payload.get("transformations", ())
    if not isinstance(transformations_raw, Sequence) or isinstance(
        transformations_raw, (str, bytes)
    ):
        raise ValueError("Lineage transformations must be a sequence.")

    return LineageEnvelope(
        schema_version=str(payload.get("schema_version", LINEAGE_SCHEMA_VERSION)),
        source=str(payload["source"]),
        source_kind=LineageSourceKind(str(payload["source_kind"])),
        dataset_id=str(payload["dataset_id"]),
        provider=(str(payload["provider"]) if payload.get("provider") is not None else None),
        observation_period=str(payload["observation_period"]),
        acquired_at=_normalise_datetime(payload.get("acquired_at"), field_name="acquired_at"),
        snapshot_at=_normalise_datetime(payload.get("snapshot_at"), field_name="snapshot_at"),
        retrieval_mode=LineageRetrievalMode(str(payload["retrieval_mode"])),
        is_sample=bool(payload["is_sample"]),
        is_official=bool(payload["is_official"]),
        calculation_version=str(payload.get("calculation_version", CALCULATION_VERSION)),
        transformations=tuple(_coerce_step(step) for step in transformations_raw),
        cache_status=LineageCacheStatus(
            str(payload.get("cache_status", LineageCacheStatus.NOT_USED.value))
        ),
    )


def attach_lineage(frame: pd.DataFrame, lineage: LineageEnvelope) -> pd.DataFrame:
    """Attach a safe serialized lineage envelope to a dataframe in place."""

    frame.attrs[LINEAGE_ATTR_KEY] = lineage_to_dict(lineage)
    return frame


def lineage_from_dataframe(frame: pd.DataFrame) -> LineageEnvelope | None:
    """Read typed lineage from a dataframe without exposing other attributes."""

    payload = frame.attrs.get(LINEAGE_ATTR_KEY)
    if payload is None:
        return None
    if isinstance(payload, LineageEnvelope):
        return payload
    if not isinstance(payload, Mapping):
        raise ValueError("Dataframe lineage metadata must be a mapping.")
    return lineage_from_mapping(payload)


def append_lineage_step(
    lineage: LineageEnvelope,
    step: LineageStep | str,
    *,
    version: str = TRANSFORMATION_VERSION,
    details: Mapping[str, JSONScalar] | None = None,
) -> LineageEnvelope:
    """Return a new envelope with one ordered transformation appended."""

    resolved = (
        step
        if isinstance(step, LineageStep)
        else LineageStep(name=step, version=version, details=details or {})
    )
    return replace(lineage, transformations=(*lineage.transformations, resolved))


def update_lineage_cache(
    lineage: LineageEnvelope,
    status: LineageCacheStatus | str,
    *,
    retrieval_mode: LineageRetrievalMode | str | None = None,
) -> LineageEnvelope:
    """Return lineage updated with bounded cache outcome metadata."""

    resolved_status = LineageCacheStatus(status)
    resolved_mode = (
        LineageRetrievalMode(retrieval_mode)
        if retrieval_mode is not None
        else (
            LineageRetrievalMode.CACHE
            if resolved_status is LineageCacheStatus.HIT
            else lineage.retrieval_mode
        )
    )
    return replace(lineage, cache_status=resolved_status, retrieval_mode=resolved_mode)


def _coerce_step(value: LineageStep | Mapping[str, Any]) -> LineageStep:
    if isinstance(value, LineageStep):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("Lineage transformation entries must be mappings.")
    details = value.get("details", {})
    if not isinstance(details, Mapping):
        raise ValueError("Lineage transformation details must be a mapping.")
    return LineageStep(
        name=str(value["name"]),
        version=str(value.get("version", TRANSFORMATION_VERSION)),
        details=details,
    )


def _sanitize_step_details(
    name: str,
    details: Mapping[str, Any],
) -> dict[str, JSONScalar]:
    allowed = _ALLOWED_STEP_DETAILS[name]
    sanitized: dict[str, JSONScalar] = {}
    for key in sorted(allowed):
        if key not in details:
            continue
        value = details[key]
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if len(value) > 128 or _contains_private_material(value):
                continue
        sanitized[key] = value
    return sanitized


def _clean_identifier(value: str, *, field_name: str) -> str:
    cleaned = str(value).strip().lower()
    if not _IDENTIFIER_PATTERN.fullmatch(cleaned) or _contains_private_material(cleaned):
        raise ValueError(f"Invalid public lineage {field_name}.")
    return cleaned


def _clean_version(value: str, *, field_name: str) -> str:
    cleaned = str(value).strip()
    if not cleaned or len(cleaned) > 32 or _contains_private_material(cleaned):
        raise ValueError(f"Invalid lineage {field_name}.")
    return cleaned


def _clean_public_text(value: str, *, field_name: str, maximum_length: int) -> str:
    cleaned = str(value).strip()
    if not cleaned or len(cleaned) > maximum_length or _contains_private_material(cleaned):
        raise ValueError(f"Invalid public lineage {field_name}.")
    return cleaned


def _contains_private_material(value: str) -> bool:
    lowered = value.casefold()
    if any(marker in lowered for marker in _FORBIDDEN_MARKERS):
        return True
    if _WINDOWS_ABSOLUTE_PATH.match(value) or value.startswith(("/home/", "/Users/")):
        return True
    if "://" in value or "\\Users\\" in value or "?" in value:
        return True
    return False


def _normalise_datetime(value: datetime | str | None, *, field_name: str) -> datetime | None:
    if value is None:
        return None
    parsed = value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Invalid lineage {field_name} timestamp.") from exc
    if not isinstance(parsed, datetime) or parsed.tzinfo is None:
        raise ValueError(f"Lineage {field_name} must include a timezone.")
    return parsed.astimezone(UTC)


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "CALCULATION_VERSION",
    "LINEAGE_ATTR_KEY",
    "LINEAGE_SCHEMA_VERSION",
    "TRANSFORMATION_VERSION",
    "LineageCacheStatus",
    "LineageEnvelope",
    "LineageRetrievalMode",
    "LineageSourceKind",
    "LineageStep",
    "append_lineage_step",
    "attach_lineage",
    "build_lineage",
    "lineage_from_dataframe",
    "lineage_from_mapping",
    "lineage_to_dict",
    "update_lineage_cache",
]
