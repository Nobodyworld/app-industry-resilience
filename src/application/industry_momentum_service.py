"""Offline, snapshot-backed application service for multi-source Industry Momentum."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from src.application.industry_pulse_service import (
    DEFAULT_FRESHNESS_THRESHOLD_DAYS as DEFAULT_PPI_FRESHNESS_THRESHOLD_DAYS,
)
from src.application.industry_pulse_service import IndustryPulseService
from src.core.industry_momentum import (
    INDUSTRY_MOMENTUM_COMPARISON_LIMITATION,
    INDUSTRY_MOMENTUM_INTERPRETATION,
    INDUSTRY_MOMENTUM_REGISTRY,
    INDUSTRY_MOMENTUM_REGISTRY_VERSION,
    INDUSTRY_MOMENTUM_SCHEMA_VERSION,
    ChangeMethod,
    IndustryMomentumChange,
    IndustryMomentumFamilyResult,
    IndustryMomentumFreshness,
    IndustryMomentumObservation,
    IndustryMomentumProvenance,
    IndustryMomentumRegistry,
    IndustryMomentumRegistryEntry,
    IndustryMomentumResult,
    IndustryMomentumSignalHistory,
    IndustryMomentumSnapshotError,
    MappingRelationship,
    MomentumAvailability,
    SignalType,
    SourceFamily,
)

DEFAULT_CES_SNAPSHOT_PATH = (
    Path(__file__).parents[2] / "data" / "industry_momentum_bls_ces_snapshot.csv"
)
DEFAULT_CES_METADATA_PATH = (
    Path(__file__).parents[2] / "data" / "industry_momentum_bls_ces_snapshot.metadata.json"
)
DEFAULT_G17_SNAPSHOT_PATH = (
    Path(__file__).parents[2] / "data" / "industry_momentum_fed_g17_snapshot.csv"
)
DEFAULT_G17_METADATA_PATH = (
    Path(__file__).parents[2] / "data" / "industry_momentum_fed_g17_snapshot.metadata.json"
)
DEFAULT_FRESHNESS_THRESHOLD_DAYS = 120
DEFAULT_CES_FRESHNESS_THRESHOLD_DAYS = DEFAULT_FRESHNESS_THRESHOLD_DAYS
DEFAULT_G17_FRESHNESS_THRESHOLD_DAYS = DEFAULT_FRESHNESS_THRESHOLD_DAYS
MAX_OBSERVATION_LIMIT = 120
SOURCE_FAMILIES: tuple[SourceFamily, ...] = ("bls_ppi", "bls_ces", "fed_g17")
DEFAULT_FRESHNESS_THRESHOLDS: Mapping[SourceFamily, int] = {
    "bls_ppi": DEFAULT_PPI_FRESHNESS_THRESHOLD_DAYS,
    "bls_ces": DEFAULT_CES_FRESHNESS_THRESHOLD_DAYS,
    "fed_g17": DEFAULT_G17_FRESHNESS_THRESHOLD_DAYS,
}
_SNAPSHOT_COLUMNS = (
    "source_family",
    "signal_type",
    "series_id",
    "published_industry_code",
    "target_industry_code",
    "mapping_relationship",
    "observation_date",
    "value",
    "units",
    "seasonal_adjustment",
    "base_period",
    "release_period",
    "source",
)
_PROVIDERS = {
    "bls_ppi": "U.S. Bureau of Labor Statistics Producer Price Index",
    "bls_ces": "U.S. Bureau of Labor Statistics Current Employment Statistics",
    "fed_g17": "Board of Governors of the Federal Reserve System G.17",
}
_DATASET_IDS = {
    "bls_ppi": "bls_ppi_industry_pulse",
    "bls_ces": "bls_ces_monthly",
    "fed_g17": "fed_g17_monthly",
}
_PUBLIC_SNAPSHOT_ERRORS: Mapping[SourceFamily, str] = {
    "bls_ppi": "Producer price snapshot unavailable.",
    "bls_ces": "Employment snapshot unavailable.",
    "fed_g17": "Production and capacity snapshot unavailable.",
}


class IndustryMomentumService:
    """Compose independently validated official source-family snapshots."""

    def __init__(
        self,
        *,
        ces_snapshot_path: Path | str = DEFAULT_CES_SNAPSHOT_PATH,
        ces_metadata_path: Path | str = DEFAULT_CES_METADATA_PATH,
        g17_snapshot_path: Path | str = DEFAULT_G17_SNAPSHOT_PATH,
        g17_metadata_path: Path | str = DEFAULT_G17_METADATA_PATH,
        registry: IndustryMomentumRegistry = INDUSTRY_MOMENTUM_REGISTRY,
        pulse_service: IndustryPulseService | None = None,
        as_of: date | None = None,
        ppi_freshness_threshold_days: int = DEFAULT_PPI_FRESHNESS_THRESHOLD_DAYS,
        ces_freshness_threshold_days: int = DEFAULT_CES_FRESHNESS_THRESHOLD_DAYS,
        g17_freshness_threshold_days: int = DEFAULT_G17_FRESHNESS_THRESHOLD_DAYS,
    ) -> None:
        freshness_thresholds: dict[SourceFamily, int] = {
            "bls_ppi": ppi_freshness_threshold_days,
            "bls_ces": ces_freshness_threshold_days,
            "fed_g17": g17_freshness_threshold_days,
        }
        if any(value <= 0 for value in freshness_thresholds.values()):
            raise ValueError("Freshness thresholds must be positive.")
        self.registry = registry
        self.as_of = as_of or date.today()
        self.freshness_threshold_days_by_family = freshness_thresholds
        self._by_family_series: dict[
            SourceFamily, dict[str, tuple[IndustryMomentumObservation, ...]]
        ] = {family: {} for family in SOURCE_FAMILIES}
        self._provenance: dict[SourceFamily, IndustryMomentumProvenance] = {}
        self._metadata: dict[SourceFamily, dict[str, Any]] = {}
        self._errors: dict[SourceFamily, str] = {}

        try:
            pulse = pulse_service or IndustryPulseService(
                as_of=self.as_of,
                freshness_threshold_days=ppi_freshness_threshold_days,
            )
            self.freshness_threshold_days_by_family["bls_ppi"] = pulse.freshness_threshold_days
            self._load_pulse(pulse)
        except (IndustryMomentumSnapshotError, OSError, ValueError):
            self._errors["bls_ppi"] = _PUBLIC_SNAPSHOT_ERRORS["bls_ppi"]

        self._load_family_safely("bls_ces", Path(ces_snapshot_path), Path(ces_metadata_path))
        self._load_family_safely("fed_g17", Path(g17_snapshot_path), Path(g17_metadata_path))

    @property
    def metadata(self) -> Mapping[str, Any]:
        """Return a defensive, path-free family metadata envelope."""

        return cast(
            dict[str, Any],
            json.loads(
                json.dumps(
                    {
                        "families": self._metadata,
                        "availability": self.availability_summary(),
                    }
                )
            ),
        )

    def availability_summary(self) -> dict[str, dict[str, Any]]:
        summary: dict[str, dict[str, Any]] = {}
        for family in SOURCE_FAMILIES:
            series = self._by_family_series[family]
            observation_count = sum(len(items) for items in series.values())
            dates = [item.observation_date for items in series.values() for item in items]
            summary[family] = {
                "availability": "available" if series else "unavailable",
                "series_count": len(series),
                "observation_count": observation_count,
                "observation_start": min(dates).isoformat() if dates else None,
                "observation_end": max(dates).isoformat() if dates else None,
                "error": self._errors.get(family),
            }
        return summary

    def list_mappings(
        self,
        *,
        source_family: SourceFamily | None = None,
        signal_type: SignalType | None = None,
        series_id: str | None = None,
    ) -> tuple[IndustryMomentumRegistryEntry, ...]:
        return self.registry.filtered(
            source_family=source_family,
            signal_type=signal_type,
            series_id=series_id,
        )

    def for_industry_code(
        self,
        industry_code: str,
        *,
        source_family: SourceFamily | None = None,
        signal_type: SignalType | None = None,
        series_id: str | None = None,
        start: date | None = None,
        end: date | None = None,
        limit: int = MAX_OBSERVATION_LIMIT,
    ) -> IndustryMomentumResult:
        if start is not None and end is not None and start > end:
            raise ValueError("start date cannot be after end date")
        if limit < 1 or limit > MAX_OBSERVATION_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_OBSERVATION_LIMIT}")

        mappings = tuple(
            entry
            for entry in self.registry.for_industry(
                industry_code,
                source_family=source_family,
                signal_type=signal_type,
            )
            if series_id is None or entry.series_id == series_id
        )
        requested_families = (source_family,) if source_family else SOURCE_FAMILIES
        families = tuple(
            self._family_result(
                family,
                tuple(entry for entry in mappings if entry.source_family == family),
                start=start,
                end=end,
                limit=limit,
            )
            for family in requested_families
        )
        availability = _overall_availability(families, bool(mappings))
        relationships = {entry.mapping_relationship for entry in mappings}
        relationship: MappingRelationship | None
        if not relationships:
            relationship = None
        elif relationships == {"exact"}:
            relationship = "exact"
        else:
            relationship = "broader_published"
        return IndustryMomentumResult(
            industry_code=industry_code,
            availability=availability,
            mapping_relationship=relationship,
            families=families,
            requested_filters={
                "source_family": source_family,
                "signal_type": signal_type,
                "series_id": series_id,
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
                "limit": limit,
            },
            limitations=(
                INDUSTRY_MOMENTUM_INTERPRETATION,
                INDUSTRY_MOMENTUM_COMPARISON_LIMITATION,
            ),
        )

    def for_series_id(
        self,
        series_id: str,
        *,
        start: date | None = None,
        end: date | None = None,
        limit: int = MAX_OBSERVATION_LIMIT,
    ) -> IndustryMomentumResult:
        """Manually browse one registered series without altering annual selection."""

        entry = self.registry.by_series_id(series_id)
        if entry is None:
            return self.for_industry_code(
                "000000", series_id=series_id, start=start, end=end, limit=limit
            )
        return self.for_industry_code(
            entry.target_industry_code,
            source_family=entry.source_family,
            signal_type=entry.signal_type,
            series_id=entry.series_id,
            start=start,
            end=end,
            limit=limit,
        )

    def _family_result(
        self,
        family: SourceFamily,
        mappings: tuple[IndustryMomentumRegistryEntry, ...],
        *,
        start: date | None,
        end: date | None,
        limit: int,
    ) -> IndustryMomentumFamilyResult:
        if not mappings:
            availability: MomentumAvailability = "unmapped"
            histories: tuple[IndustryMomentumSignalHistory, ...] = ()
        elif not self._by_family_series[family]:
            availability = "unavailable"
            histories = tuple(self._history(entry, (), "unavailable") for entry in mappings)
        else:
            built: list[IndustryMomentumSignalHistory] = []
            for entry in mappings:
                full = self._by_family_series[family].get(entry.series_id, ())
                filtered = tuple(
                    item
                    for item in full
                    if (start is None or item.observation_date >= start)
                    and (end is None or item.observation_date <= end)
                )
                state: MomentumAvailability = "available" if filtered else "empty_range"
                built.append(
                    self._history(
                        entry,
                        filtered[-limit:],
                        state,
                        summarized_observations=filtered,
                    )
                )
            histories = tuple(built)
            states = {history.availability for history in histories}
            availability = states.pop() if len(states) == 1 else "partial"
        limitations = [
            INDUSTRY_MOMENTUM_INTERPRETATION,
            INDUSTRY_MOMENTUM_COMPARISON_LIMITATION,
        ]
        if family in self._errors:
            limitations.append(
                f"{family} snapshot is unavailable; other source families remain usable."
            )
        return IndustryMomentumFamilyResult(
            source_family=family,
            availability=availability,
            histories=histories,
            limitations=tuple(limitations),
        )

    def _history(
        self,
        mapping: IndustryMomentumRegistryEntry,
        observations: Sequence[IndustryMomentumObservation],
        availability: MomentumAvailability,
        *,
        summarized_observations: Sequence[IndustryMomentumObservation] | None = None,
    ) -> IndustryMomentumSignalHistory:
        summary = tuple(summarized_observations or observations)
        latest = summary[-1] if summary else None
        return IndustryMomentumSignalHistory(
            availability=availability,
            mapping=mapping,
            observations=tuple(observations),
            latest_observation=latest,
            month_over_month=_calculate_change(summary, mapping.change_method, 1),
            year_over_year=_calculate_change(summary, mapping.change_method, 12),
            freshness=self._freshness(latest, mapping.source_family),
            observation_start=summary[0].observation_date if summary else None,
            observation_end=summary[-1].observation_date if summary else None,
            release_period=latest.release_period if latest else None,
            provenance=self._provenance.get(mapping.source_family),
            limitations=(
                INDUSTRY_MOMENTUM_INTERPRETATION,
                INDUSTRY_MOMENTUM_COMPARISON_LIMITATION,
            ),
        )

    def _freshness(
        self,
        latest: IndustryMomentumObservation | None,
        family: SourceFamily,
    ) -> IndustryMomentumFreshness:
        threshold_days = self.freshness_threshold_days_by_family[family]
        if latest is None:
            return IndustryMomentumFreshness(
                state="unknown",
                as_of=self.as_of,
                latest_observation_date=None,
                age_days=None,
                threshold_days=threshold_days,
            )
        age_days = (self.as_of - latest.observation_date).days
        return IndustryMomentumFreshness(
            state="current" if age_days <= threshold_days else "stale",
            as_of=self.as_of,
            latest_observation_date=latest.observation_date,
            age_days=age_days,
            threshold_days=threshold_days,
        )

    def _load_pulse(self, pulse: IndustryPulseService) -> None:
        grouped: dict[str, tuple[IndustryMomentumObservation, ...]] = {}
        for entry in self.registry.filtered(source_family="bls_ppi"):
            history = pulse.for_industry_code(entry.target_industry_code)
            grouped[entry.series_id] = tuple(
                IndustryMomentumObservation(
                    source_family="bls_ppi",
                    signal_type="producer_price_index",
                    series_id=item.series_id,
                    published_industry_code=entry.published_industry_code,
                    target_industry_code=entry.target_industry_code,
                    mapping_relationship=entry.mapping_relationship,
                    observation_date=item.observation_date,
                    value=item.value,
                    units=item.units,
                    seasonal_adjustment=item.seasonal_adjustment,
                    base_period=item.base_date,
                    release_period=item.release_period,
                    source=item.source,
                )
                for item in history.observations
            )
        self._by_family_series["bls_ppi"] = grouped
        provenance = pulse.provenance
        dates = [item.observation_date for items in grouped.values() for item in items]
        self._provenance["bls_ppi"] = IndustryMomentumProvenance(
            dataset_id=provenance.dataset_id,
            provider=provenance.provider,
            source_url=provenance.source_url,
            retrieval_mode="offline_reviewed_snapshot",
            retrieved_at=provenance.retrieved_at,
            snapshot_sha256=provenance.snapshot_sha256,
            manifest_identity=provenance.manifest_identity,
            registry_version=INDUSTRY_MOMENTUM_REGISTRY_VERSION,
            schema_version=INDUSTRY_MOMENTUM_SCHEMA_VERSION,
            observation_start=min(dates),
            observation_end=max(dates),
            transformations=provenance.transformations,
        )
        self._metadata["bls_ppi"] = dict(pulse.metadata)

    def _load_family_safely(
        self, family: SourceFamily, snapshot_path: Path, metadata_path: Path
    ) -> None:
        try:
            metadata = _load_metadata(metadata_path)
            observations, snapshot_hash = _load_snapshot(snapshot_path, family, self.registry)
            _validate_manifest(metadata, observations, snapshot_hash, family, self.registry)
            grouped: dict[str, list[IndustryMomentumObservation]] = defaultdict(list)
            for observation in observations:
                grouped[observation.series_id].append(observation)
            self._by_family_series[family] = {
                series_id: tuple(items) for series_id, items in grouped.items()
            }
            start = min(item.observation_date for item in observations)
            end = max(item.observation_date for item in observations)
            self._provenance[family] = IndustryMomentumProvenance(
                dataset_id=str(metadata["dataset_id"]),
                provider=_PROVIDERS[family],
                source_url=str(metadata["official_endpoints"][0]),
                retrieval_mode="offline_reviewed_snapshot",
                retrieved_at=_parse_retrieved_at(str(metadata["retrieved_at"])),
                snapshot_sha256=snapshot_hash,
                manifest_identity=str(metadata["manifest_identity"]),
                registry_version=str(metadata["registry_version"]),
                schema_version=str(metadata["schema_version"]),
                observation_start=start,
                observation_end=end,
                transformations=tuple(str(item) for item in metadata["transformations"]),
            )
            self._metadata[family] = metadata
        except (IndustryMomentumSnapshotError, OSError, ValueError, KeyError):
            self._errors[family] = _PUBLIC_SNAPSHOT_ERRORS[family]


def _overall_availability(
    families: Sequence[IndustryMomentumFamilyResult], mapped: bool
) -> MomentumAvailability:
    if not mapped:
        return "unmapped"
    states = {family.availability for family in families if family.availability != "unmapped"}
    if not states:
        return "unmapped"
    if states == {"available"}:
        return "available"
    if states == {"empty_range"}:
        return "empty_range"
    if states == {"unavailable"}:
        return "unavailable"
    return "partial"


def _calculate_change(
    observations: Sequence[IndustryMomentumObservation],
    method: ChangeMethod,
    months_back: int,
) -> IndustryMomentumChange:
    units = "percentage points" if method == "percentage_point_change" else "percent"
    latest = observations[-1] if observations else None
    if latest is None:
        return IndustryMomentumChange(None, method, units, None, None, "insufficient_history")
    if latest.observation_date.day != 1:
        return IndustryMomentumChange(
            None,
            method,
            units,
            latest.observation_date.isoformat(),
            None,
            "period_malformed",
        )
    target = _subtract_months(latest.observation_date, months_back)
    comparison = next((item for item in observations if item.observation_date == target), None)
    if comparison is None:
        return IndustryMomentumChange(
            None,
            method,
            units,
            latest.observation_date.strftime("%Y-%m"),
            target.strftime("%Y-%m"),
            "comparison_period_missing",
        )
    if method == "percentage_point_change":
        value = latest.value - comparison.value
    elif comparison.value == 0:
        return IndustryMomentumChange(
            None,
            method,
            units,
            latest.observation_date.strftime("%Y-%m"),
            target.strftime("%Y-%m"),
            "denominator_zero",
        )
    else:
        value = (latest.value / comparison.value - 1) * 100
    return IndustryMomentumChange(
        value,
        method,
        units,
        latest.observation_date.strftime("%Y-%m"),
        target.strftime("%Y-%m"),
    )


def _subtract_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, zero_based_month = divmod(month_index, 12)
    return date(year, zero_based_month + 1, 1)


def _load_metadata(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndustryMomentumSnapshotError("Unable to read momentum metadata.") from exc
    if not isinstance(payload, dict):
        raise IndustryMomentumSnapshotError("Momentum metadata must be a JSON object.")
    return cast(dict[str, Any], payload)


def _load_snapshot(
    path: Path, family: SourceFamily, registry: IndustryMomentumRegistry
) -> tuple[tuple[IndustryMomentumObservation, ...], str]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise IndustryMomentumSnapshotError("Unable to read momentum snapshot.") from exc
    snapshot_hash = hashlib.sha256(payload).hexdigest()
    try:
        reader = csv.DictReader(payload.decode("utf-8").splitlines())
    except UnicodeDecodeError as exc:
        raise IndustryMomentumSnapshotError("Momentum snapshot must be UTF-8.") from exc
    if tuple(reader.fieldnames or ()) != _SNAPSHOT_COLUMNS:
        raise IndustryMomentumSnapshotError("Momentum snapshot columns do not match schema.")
    observations: list[IndustryMomentumObservation] = []
    seen: set[tuple[str, date]] = set()
    for row in reader:
        series_id = str(row["series_id"])
        entry = registry.by_series_id(series_id, family)
        if entry is None:
            raise IndustryMomentumSnapshotError(f"Unregistered {family} series: {series_id}.")
        try:
            observation_date = date.fromisoformat(str(row["observation_date"]))
            value = float(row["value"])
        except (TypeError, ValueError) as exc:
            raise IndustryMomentumSnapshotError("Malformed momentum observation.") from exc
        identity = (series_id, observation_date)
        if identity in seen:
            raise IndustryMomentumSnapshotError("Duplicate momentum series-month row.")
        seen.add(identity)
        expected = {
            "source_family": family,
            "signal_type": entry.signal_type,
            "published_industry_code": entry.published_industry_code,
            "target_industry_code": entry.target_industry_code,
            "mapping_relationship": entry.mapping_relationship,
            "units": entry.units,
            "seasonal_adjustment": entry.seasonal_adjustment,
            "base_period": entry.base_period or "",
        }
        mismatched = [field for field, value in expected.items() if row[field] != value]
        if mismatched:
            raise IndustryMomentumSnapshotError(
                f"Momentum registry metadata mismatch: {', '.join(mismatched)}."
            )
        observations.append(
            IndustryMomentumObservation(
                source_family=family,
                signal_type=entry.signal_type,
                series_id=series_id,
                published_industry_code=entry.published_industry_code,
                target_industry_code=entry.target_industry_code,
                mapping_relationship=entry.mapping_relationship,
                observation_date=observation_date,
                value=value,
                units=entry.units,
                seasonal_adjustment=entry.seasonal_adjustment,
                base_period=entry.base_period,
                release_period=str(row["release_period"]),
                source=str(row["source"]),
            )
        )
    ordered = tuple(sorted(observations, key=lambda item: (item.series_id, item.observation_date)))
    if tuple(observations) != ordered:
        raise IndustryMomentumSnapshotError("Momentum snapshot must be deterministically sorted.")
    return ordered, snapshot_hash


def _validate_manifest(
    metadata: Mapping[str, Any],
    observations: Sequence[IndustryMomentumObservation],
    snapshot_hash: str,
    family: SourceFamily,
    registry: IndustryMomentumRegistry,
) -> None:
    required = {
        "csv_sha256",
        "dataset_id",
        "interpretation_notes",
        "latest_release_period",
        "manifest_identity",
        "observation_range",
        "official_endpoints",
        "registry_version",
        "requested_series",
        "retrieved_at",
        "row_count",
        "schema_version",
        "series_count",
        "transformations",
    }
    if missing := sorted(required.difference(metadata)):
        raise IndustryMomentumSnapshotError(f"Momentum metadata missing: {', '.join(missing)}.")
    expected_series = [entry.series_id for entry in registry.filtered(source_family=family)]
    present_series = sorted({item.series_id for item in observations})
    if list(metadata["requested_series"]) != expected_series or present_series != expected_series:
        raise IndustryMomentumSnapshotError("Momentum family registry coverage is incomplete.")
    if metadata["dataset_id"] != _DATASET_IDS[family]:
        raise IndustryMomentumSnapshotError("Momentum dataset identity is invalid.")
    if metadata["registry_version"] != INDUSTRY_MOMENTUM_REGISTRY_VERSION:
        raise IndustryMomentumSnapshotError("Momentum registry version is unsupported.")
    if metadata["schema_version"] != INDUSTRY_MOMENTUM_SCHEMA_VERSION:
        raise IndustryMomentumSnapshotError("Momentum snapshot schema is unsupported.")
    if metadata["csv_sha256"] != snapshot_hash:
        raise IndustryMomentumSnapshotError("Momentum snapshot SHA-256 does not match metadata.")
    if int(metadata["row_count"]) != len(observations):
        raise IndustryMomentumSnapshotError("Momentum row count does not match metadata.")
    if int(metadata["series_count"]) != len(expected_series):
        raise IndustryMomentumSnapshotError("Momentum series count does not match metadata.")
    if not observations:
        raise IndustryMomentumSnapshotError("Momentum snapshot cannot be empty.")
    start = min(item.observation_date for item in observations).isoformat()
    end = max(item.observation_date for item in observations).isoformat()
    if metadata["observation_range"] != {"start": start, "end": end}:
        raise IndustryMomentumSnapshotError("Momentum observation range does not match metadata.")
    if metadata["latest_release_period"] != max(item.release_period for item in observations):
        raise IndustryMomentumSnapshotError("Momentum release period does not match metadata.")
    if metadata["interpretation_notes"] != [INDUSTRY_MOMENTUM_INTERPRETATION]:
        raise IndustryMomentumSnapshotError("Momentum interpretation note is unreviewed.")
    endpoints = metadata["official_endpoints"]
    if (
        not isinstance(endpoints, list)
        or not endpoints
        or any(not str(endpoint).startswith("https://") for endpoint in endpoints)
    ):
        raise IndustryMomentumSnapshotError("Momentum endpoints must be official HTTPS URLs.")
    _parse_retrieved_at(str(metadata["retrieved_at"]))


def _parse_retrieved_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IndustryMomentumSnapshotError("Momentum retrieval timestamp is malformed.") from exc
    if parsed.tzinfo is None:
        raise IndustryMomentumSnapshotError("Momentum retrieval timestamp needs a timezone.")
    return parsed.astimezone(UTC)


__all__ = [
    "DEFAULT_CES_FRESHNESS_THRESHOLD_DAYS",
    "DEFAULT_CES_METADATA_PATH",
    "DEFAULT_CES_SNAPSHOT_PATH",
    "DEFAULT_FRESHNESS_THRESHOLD_DAYS",
    "DEFAULT_FRESHNESS_THRESHOLDS",
    "DEFAULT_G17_FRESHNESS_THRESHOLD_DAYS",
    "DEFAULT_G17_METADATA_PATH",
    "DEFAULT_G17_SNAPSHOT_PATH",
    "DEFAULT_PPI_FRESHNESS_THRESHOLD_DAYS",
    "MAX_OBSERVATION_LIMIT",
    "SOURCE_FAMILIES",
    "IndustryMomentumService",
]
