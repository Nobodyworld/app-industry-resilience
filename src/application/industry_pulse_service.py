"""Snapshot-backed Industry Pulse application service."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from src.core.industry_pulse import (
    INDUSTRY_PULSE_ENDPOINT,
    INDUSTRY_PULSE_INTERPRETATION,
    INDUSTRY_PULSE_LEVEL_LIMITATION,
    INDUSTRY_PULSE_REGISTRY,
    INDUSTRY_PULSE_REGISTRY_VERSION,
    INDUSTRY_PULSE_SCHEMA_VERSION,
    INDUSTRY_PULSE_SOURCE,
    FreshnessState,
    IndustryPulseChangeSummary,
    IndustryPulseFreshness,
    IndustryPulseObservation,
    IndustryPulseProvenance,
    IndustryPulseRegistry,
    IndustryPulseRegistryEntry,
    IndustryPulseSeriesHistory,
    IndustryPulseSnapshotError,
)

DEFAULT_SNAPSHOT_PATH = Path(__file__).parents[2] / "data" / "industry_pulse_bls_snapshot.csv"
DEFAULT_METADATA_PATH = (
    Path(__file__).parents[2] / "data" / "industry_pulse_bls_snapshot.metadata.json"
)
DEFAULT_FRESHNESS_THRESHOLD_DAYS = 90
MAX_OBSERVATION_LIMIT = 120
_SNAPSHOT_COLUMNS = (
    "series_id",
    "industry_code",
    "industry_name",
    "observation_date",
    "value",
    "units",
    "seasonal_adjustment",
    "base_date",
    "release_period",
    "source",
)


class IndustryPulseService:
    """Serve verified mappings and deterministic observations without network access."""

    def __init__(
        self,
        *,
        snapshot_path: Path | str = DEFAULT_SNAPSHOT_PATH,
        metadata_path: Path | str = DEFAULT_METADATA_PATH,
        registry: IndustryPulseRegistry = INDUSTRY_PULSE_REGISTRY,
        as_of: date | None = None,
        freshness_threshold_days: int = DEFAULT_FRESHNESS_THRESHOLD_DAYS,
    ) -> None:
        if freshness_threshold_days <= 0:
            raise ValueError("Freshness threshold must be positive.")
        self.registry = registry
        self.as_of = as_of or date.today()
        self.freshness_threshold_days = freshness_threshold_days
        self._metadata = _load_metadata(Path(metadata_path))
        observations, snapshot_hash = _load_snapshot(Path(snapshot_path), registry)
        _validate_manifest(self._metadata, observations, snapshot_hash, registry)
        self._observations = observations
        self._by_series: dict[str, tuple[IndustryPulseObservation, ...]] = {}
        grouped: dict[str, list[IndustryPulseObservation]] = defaultdict(list)
        for observation in observations:
            grouped[observation.series_id].append(observation)
        for series_id, items in grouped.items():
            self._by_series[series_id] = tuple(
                sorted(items, key=lambda item: item.observation_date)
            )
        retrieved_at = _parse_retrieved_at(str(self._metadata["retrieved_at"]))
        self.provenance = IndustryPulseProvenance(
            dataset_id="bls_ppi_industry_pulse",
            provider=INDUSTRY_PULSE_SOURCE,
            source_url=INDUSTRY_PULSE_ENDPOINT,
            retrieval_mode="offline_reviewed_snapshot",
            retrieved_at=retrieved_at,
            snapshot_sha256=snapshot_hash,
            manifest_identity=str(self._metadata["manifest_identity"]),
            registry_version=str(self._metadata["registry_version"]),
            schema_version=str(self._metadata["schema_version"]),
            transformations=tuple(str(item) for item in self._metadata["transformations"]),
        )

    @property
    def metadata(self) -> Mapping[str, Any]:
        """Return a defensive, path-free copy of public snapshot metadata."""

        return cast(dict[str, Any], json.loads(json.dumps(self._metadata)))

    def list_mappings(
        self, *, series_id: str | None = None
    ) -> tuple[IndustryPulseRegistryEntry, ...]:
        entries = self.registry.entries
        if series_id is not None:
            match = self.registry.by_series_id(series_id)
            return (match,) if match is not None else ()
        return entries

    def for_series_id(
        self,
        series_id: str,
        *,
        start: date | None = None,
        end: date | None = None,
        limit: int = MAX_OBSERVATION_LIMIT,
    ) -> IndustryPulseSeriesHistory:
        mapping = self.registry.by_series_id(series_id)
        if mapping is None:
            return self._history(None, (), availability="unmapped")
        return self.for_industry_code(
            mapping.industry_code,
            start=start,
            end=end,
            limit=limit,
        )

    def for_industry_code(
        self,
        industry_code: str,
        *,
        start: date | None = None,
        end: date | None = None,
        limit: int = MAX_OBSERVATION_LIMIT,
    ) -> IndustryPulseSeriesHistory:
        if start is not None and end is not None and start > end:
            raise ValueError("start date cannot be after end date")
        if limit < 1 or limit > MAX_OBSERVATION_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_OBSERVATION_LIMIT}")
        mapping = self.registry.by_industry_code(industry_code)
        if mapping is None:
            return self._history(None, (), availability="unmapped")
        full = self._by_series.get(mapping.series_id, ())
        filtered = tuple(
            item
            for item in full
            if (start is None or item.observation_date >= start)
            and (end is None or item.observation_date <= end)
        )
        if not filtered:
            return self._history(mapping, (), availability="empty_range")
        summarized = filtered
        bounded = filtered[-limit:]
        return self._history(
            mapping,
            bounded,
            summarized_observations=summarized,
            availability="available",
        )

    def _history(
        self,
        mapping: IndustryPulseRegistryEntry | None,
        observations: Sequence[IndustryPulseObservation],
        *,
        summarized_observations: Sequence[IndustryPulseObservation] | None = None,
        availability: str,
    ) -> IndustryPulseSeriesHistory:
        summary_items = tuple(summarized_observations or observations)
        latest = summary_items[-1] if summary_items else None
        freshness = self._freshness(latest)
        if latest is None:
            unavailable = IndustryPulseChangeSummary(
                value_pct=None,
                latest_period=None,
                comparison_period=None,
                reason="insufficient_history",
            )
            mom = unavailable
            yoy = unavailable
        else:
            mom = _calculate_change(summary_items, months_back=1)
            yoy = _calculate_change(summary_items, months_back=12)
        return IndustryPulseSeriesHistory(
            availability=availability,  # type: ignore[arg-type]
            mapping=mapping,
            observations=tuple(observations),
            latest_observation=latest,
            month_over_month=mom,
            year_over_year=yoy,
            freshness=freshness,
            observation_start=summary_items[0].observation_date if summary_items else None,
            observation_end=summary_items[-1].observation_date if summary_items else None,
            release_period=latest.release_period if latest else None,
            provenance=self.provenance,
            limitations=(INDUSTRY_PULSE_INTERPRETATION, INDUSTRY_PULSE_LEVEL_LIMITATION),
        )

    def _freshness(self, latest: IndustryPulseObservation | None) -> IndustryPulseFreshness:
        if latest is None:
            return IndustryPulseFreshness(
                state="unknown",
                as_of=self.as_of,
                latest_observation_date=None,
                age_days=None,
                threshold_days=self.freshness_threshold_days,
            )
        age_days = (self.as_of - latest.observation_date).days
        state: FreshnessState = "current" if age_days <= self.freshness_threshold_days else "stale"
        return IndustryPulseFreshness(
            state=state,
            as_of=self.as_of,
            latest_observation_date=latest.observation_date,
            age_days=age_days,
            threshold_days=self.freshness_threshold_days,
        )


def _calculate_change(
    observations: Sequence[IndustryPulseObservation], *, months_back: int
) -> IndustryPulseChangeSummary:
    if len(observations) < 2:
        return IndustryPulseChangeSummary(
            value_pct=None,
            latest_period=(
                observations[-1].observation_date.strftime("%Y-%m") if observations else None
            ),
            comparison_period=None,
            reason="insufficient_history",
        )
    latest = observations[-1]
    if latest.observation_date.day != 1:
        return IndustryPulseChangeSummary(
            value_pct=None,
            latest_period=latest.observation_date.isoformat(),
            comparison_period=None,
            reason="period_malformed",
        )
    target = _subtract_months(latest.observation_date, months_back)
    comparison = next(
        (item for item in observations if item.observation_date == target),
        None,
    )
    if comparison is None:
        return IndustryPulseChangeSummary(
            value_pct=None,
            latest_period=latest.observation_date.strftime("%Y-%m"),
            comparison_period=target.strftime("%Y-%m"),
            reason="comparison_period_missing",
        )
    if comparison.value == 0:
        return IndustryPulseChangeSummary(
            value_pct=None,
            latest_period=latest.observation_date.strftime("%Y-%m"),
            comparison_period=target.strftime("%Y-%m"),
            reason="denominator_zero",
        )
    return IndustryPulseChangeSummary(
        value_pct=(latest.value / comparison.value - 1) * 100,
        latest_period=latest.observation_date.strftime("%Y-%m"),
        comparison_period=target.strftime("%Y-%m"),
    )


def _subtract_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, zero_based_month = divmod(month_index, 12)
    return date(year, zero_based_month + 1, 1)


def _load_metadata(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndustryPulseSnapshotError("Unable to read Industry Pulse metadata.") from exc
    if not isinstance(payload, dict):
        raise IndustryPulseSnapshotError("Industry Pulse metadata must be a JSON object.")
    return payload


def _load_snapshot(
    path: Path, registry: IndustryPulseRegistry
) -> tuple[tuple[IndustryPulseObservation, ...], str]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise IndustryPulseSnapshotError("Unable to read Industry Pulse snapshot.") from exc
    snapshot_hash = hashlib.sha256(payload).hexdigest()
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IndustryPulseSnapshotError("Industry Pulse snapshot must be UTF-8.") from exc
    reader = csv.DictReader(decoded.splitlines())
    if tuple(reader.fieldnames or ()) != _SNAPSHOT_COLUMNS:
        raise IndustryPulseSnapshotError("Industry Pulse snapshot columns do not match schema.")
    observations: list[IndustryPulseObservation] = []
    seen: set[tuple[str, date]] = set()
    for row in reader:
        series_id = str(row["series_id"])
        mapping = registry.by_series_id(series_id)
        if mapping is None:
            raise IndustryPulseSnapshotError(
                f"Snapshot contains unregistered series: {series_id!r}."
            )
        try:
            observation_date = date.fromisoformat(str(row["observation_date"]))
            value = float(row["value"])
        except (TypeError, ValueError) as exc:
            raise IndustryPulseSnapshotError("Snapshot contains a malformed observation.") from exc
        identity = (series_id, observation_date)
        if identity in seen:
            raise IndustryPulseSnapshotError("Snapshot contains duplicate series-month rows.")
        seen.add(identity)
        expected = {
            "industry_code": mapping.industry_code,
            "industry_name": mapping.registry_label,
            "units": mapping.units,
            "seasonal_adjustment": mapping.seasonal_adjustment,
            "base_date": mapping.base_date,
        }
        mismatched = [
            field for field, expected_value in expected.items() if row[field] != expected_value
        ]
        if mismatched:
            raise IndustryPulseSnapshotError(
                f"Snapshot registry metadata mismatch: {', '.join(mismatched)}."
            )
        release_period = str(row["release_period"])
        if release_period != observation_date.strftime("%Y-%m"):
            raise IndustryPulseSnapshotError(
                "Snapshot release period must match its monthly observation."
            )
        observations.append(
            IndustryPulseObservation(
                series_id=series_id,
                industry_code=mapping.industry_code,
                industry_name=mapping.registry_label,
                observation_date=observation_date,
                value=value,
                units=mapping.units,
                seasonal_adjustment=mapping.seasonal_adjustment,
                base_date=mapping.base_date,
                release_period=release_period,
                source=str(row["source"]),
            )
        )
    ordered = tuple(sorted(observations, key=lambda item: (item.series_id, item.observation_date)))
    if tuple(observations) != ordered:
        raise IndustryPulseSnapshotError(
            "Industry Pulse snapshot must be sorted by series ID and observation date."
        )
    return ordered, snapshot_hash


def _validate_manifest(
    metadata: Mapping[str, Any],
    observations: Sequence[IndustryPulseObservation],
    snapshot_hash: str,
    registry: IndustryPulseRegistry,
) -> None:
    required = {
        "endpoint",
        "source_label",
        "retrieved_at",
        "requested_years",
        "series_ids",
        "row_count",
        "observation_range",
        "latest_release_period",
        "csv_sha256",
        "registry_version",
        "schema_version",
        "generator",
        "generator_command",
        "manifest_identity",
        "transformations",
        "interpretation_note",
    }
    missing = sorted(required.difference(metadata))
    if missing:
        raise IndustryPulseSnapshotError(
            f"Industry Pulse metadata missing fields: {', '.join(missing)}."
        )
    if metadata["endpoint"] != INDUSTRY_PULSE_ENDPOINT:
        raise IndustryPulseSnapshotError(
            "Snapshot endpoint does not match the official BLS endpoint."
        )
    if {item.source for item in observations} != {metadata["source_label"]}:
        raise IndustryPulseSnapshotError("Snapshot source label does not match metadata.")
    if metadata["csv_sha256"] != snapshot_hash:
        raise IndustryPulseSnapshotError("Industry Pulse snapshot SHA-256 does not match metadata.")
    if int(metadata["row_count"]) != len(observations):
        raise IndustryPulseSnapshotError(
            "Industry Pulse snapshot row count does not match metadata."
        )
    expected_series = [entry.series_id for entry in registry.entries]
    if list(metadata["series_ids"]) != expected_series:
        raise IndustryPulseSnapshotError("Industry Pulse metadata series registry is incomplete.")
    present_series = sorted({item.series_id for item in observations})
    if present_series != expected_series:
        raise IndustryPulseSnapshotError(
            "Industry Pulse snapshot must contain all registry series."
        )
    if metadata["registry_version"] != INDUSTRY_PULSE_REGISTRY_VERSION:
        raise IndustryPulseSnapshotError("Industry Pulse registry version is unsupported.")
    if metadata["schema_version"] != INDUSTRY_PULSE_SCHEMA_VERSION:
        raise IndustryPulseSnapshotError("Industry Pulse schema version is unsupported.")
    if not observations:
        raise IndustryPulseSnapshotError("Industry Pulse snapshot cannot be empty.")
    start = min(item.observation_date for item in observations).isoformat()
    end = max(item.observation_date for item in observations).isoformat()
    if metadata["observation_range"] != {"start": start, "end": end}:
        raise IndustryPulseSnapshotError("Snapshot observation range does not match metadata.")
    latest = max(item.release_period for item in observations)
    if metadata["latest_release_period"] != latest:
        raise IndustryPulseSnapshotError("Snapshot release period does not match metadata.")
    if metadata["interpretation_note"] != INDUSTRY_PULSE_INTERPRETATION:
        raise IndustryPulseSnapshotError("Snapshot interpretation note is not the reviewed text.")
    _parse_retrieved_at(str(metadata["retrieved_at"]))


def _parse_retrieved_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IndustryPulseSnapshotError("Snapshot retrieval timestamp is malformed.") from exc
    if parsed.tzinfo is None:
        raise IndustryPulseSnapshotError("Snapshot retrieval timestamp must include a timezone.")
    return parsed.astimezone(UTC)


__all__ = [
    "DEFAULT_FRESHNESS_THRESHOLD_DAYS",
    "DEFAULT_METADATA_PATH",
    "DEFAULT_SNAPSHOT_PATH",
    "MAX_OBSERVATION_LIMIT",
    "IndustryPulseService",
]
