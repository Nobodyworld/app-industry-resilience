"""Public data catalog, release manifests, and readiness guardrails."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

AUTH_NONE = "none"
DEFAULT_SCHEMA_VERSION = "public-data-v1"
DEFAULT_CLEANING_VERSION = "cleaning-v1"
IMPLEMENTATION_STAGES: tuple[str, ...] = (
    "cataloged",
    "endpoint_verified",
    "adapter_implemented",
    "backfill_validated",
    "listener_validated",
)

DIRECT_INDUSTRY_SCHEMA: tuple[str, ...] = (
    "industry_code",
    "industry_name",
    "year",
    "gross_output",
    "materials_cost",
    "intermediate_inputs",
    "value_added",
    "source",
)

SIGNAL_SCHEMA: tuple[str, ...] = (
    "observation_date",
    "frequency",
    "series_id",
    "industry_code",
    "signal_name",
    "signal_value",
    "units",
    "seasonal_adjustment",
    "release_period",
    "source",
)

DIRECT_INDUSTRY_FIELD_MAPPINGS: Mapping[str, str] = {
    "NAICS or source industry code": "industry_code",
    "source industry label": "industry_name",
    "source observation year": "year",
    "revenue, receipts, shipments, or gross output": "gross_output",
    "materials cost where published": "materials_cost",
    "intermediate inputs or operating-expense proxy where published": "intermediate_inputs",
    "source-provided or computed value added": "value_added",
    "dataset label": "source",
}

SIGNAL_FIELD_MAPPINGS: Mapping[str, str] = {
    "source observation period": "observation_date",
    "source publication cadence": "frequency",
    "source series/table identifier": "series_id",
    "documented NAICS or industry mapping where available": "industry_code",
    "source signal label": "signal_name",
    "source-native value": "signal_value",
    "source-native unit label": "units",
    "seasonal adjustment label": "seasonal_adjustment",
    "source release batch": "release_period",
    "dataset label": "source",
}

_ALLOWED_CADENCES = {
    "daily",
    "weekly",
    "monthly",
    "quarterly",
    "annual",
    "bi_annual",
    "multi_annual",
}
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.=-]*$")
_HASH_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.=-]*$")


class CatalogValidationError(ValueError):
    """Raised when public dataset catalog entries are not usable."""


class ManifestError(RuntimeError):
    """Raised when a release manifest cannot be read or written."""


@dataclass(frozen=True)
class ImplementationStatus:
    """Track how far a cataloged dataset has been implemented."""

    cataloged: bool = True
    endpoint_verified: bool = False
    adapter_implemented: bool = False
    backfill_validated: bool = False
    listener_validated: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {stage: bool(getattr(self, stage)) for stage in IMPLEMENTATION_STAGES}


@dataclass(frozen=True)
class DatasetDefinition:
    """Describe a public dataset family that can be collected reproducibly."""

    dataset_id: str
    name: str
    agency: str
    endpoint: str
    update_cadence: str
    frequency: str
    observation_period: str
    release_period: str
    units: str
    historical_coverage: str
    canonical_schema: tuple[str, ...]
    canonical_field_mappings: Mapping[str, str] = field(default_factory=dict)
    auth_requirement: str = AUTH_NONE
    source_type: str = "official"
    phase: str = "phase_1"
    schema_version: str = DEFAULT_SCHEMA_VERSION
    implementation_status: ImplementationStatus = field(default_factory=ImplementationStatus)
    economic_ground_truth: bool = True
    public_access_notes: str = "Public endpoint; no sign-in, subscription, or paywall required."
    release_monitor: str | None = None
    steward_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["canonical_schema"] = list(self.canonical_schema)
        payload["canonical_field_mappings"] = dict(self.canonical_field_mappings)
        payload["implementation_status"] = self.implementation_status.to_dict()
        payload["steward_notes"] = list(self.steward_notes)
        return payload


@dataclass(frozen=True)
class ReleaseIdentity:
    """Release metadata available before downloading a full payload."""

    dataset_id: str
    release_period: str
    source_url: str
    content_hash: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    schema_version: str | None = None
    cleaning_version: str | None = None


@dataclass(frozen=True)
class ReleaseManifest:
    """Persisted provenance for a raw or cleaned public data release."""

    dataset_id: str
    release_period: str
    source_url: str
    fetched_at: str
    content_hash: str
    row_count: int
    columns: tuple[str, ...]
    schema_version: str = DEFAULT_SCHEMA_VERSION
    cleaning_version: str = DEFAULT_CLEANING_VERSION
    etag: str | None = None
    last_modified: str | None = None
    observation_start: str | None = None
    observation_end: str | None = None
    release_notes_url: str | None = None
    raw_artifact_path: str | None = None
    cleaned_artifact_path: str | None = None
    transformation_provenance: tuple[str, ...] = ()
    manifest_version: int = 1
    revision_of: str | None = None
    previous_manifest_path: str | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["columns"] = list(self.columns)
        payload["transformation_provenance"] = list(self.transformation_provenance)
        payload["notes"] = list(self.notes)
        return payload

    def to_json(self) -> str:
        """Return a deterministic JSON representation of the manifest."""

        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReleaseManifest:
        required = {
            "dataset_id",
            "release_period",
            "source_url",
            "fetched_at",
            "content_hash",
            "row_count",
            "columns",
        }
        missing = sorted(required.difference(payload))
        if missing:
            raise ManifestError(f"Release manifest missing fields: {', '.join(missing)}")

        manifest = cls(
            dataset_id=str(payload["dataset_id"]),
            release_period=str(payload["release_period"]),
            source_url=str(payload["source_url"]),
            fetched_at=str(payload["fetched_at"]),
            content_hash=str(payload["content_hash"]),
            row_count=int(payload["row_count"]),
            columns=tuple(str(column) for column in payload["columns"]),
            schema_version=str(payload.get("schema_version", DEFAULT_SCHEMA_VERSION)),
            cleaning_version=str(payload.get("cleaning_version", DEFAULT_CLEANING_VERSION)),
            etag=_optional_text(payload.get("etag")),
            last_modified=_optional_text(payload.get("last_modified")),
            observation_start=_optional_text(payload.get("observation_start")),
            observation_end=_optional_text(payload.get("observation_end")),
            release_notes_url=_optional_text(payload.get("release_notes_url")),
            raw_artifact_path=_optional_text(payload.get("raw_artifact_path")),
            cleaned_artifact_path=_optional_text(payload.get("cleaned_artifact_path")),
            transformation_provenance=tuple(
                str(step) for step in payload.get("transformation_provenance", ())
            ),
            manifest_version=int(payload.get("manifest_version", 1)),
            revision_of=_optional_text(payload.get("revision_of")),
            previous_manifest_path=_optional_text(payload.get("previous_manifest_path")),
            notes=tuple(str(note) for note in payload.get("notes", ())),
        )
        _validate_manifest(manifest)
        return manifest

    @classmethod
    def from_json(cls, payload: str) -> ReleaseManifest:
        """Load a manifest from its JSON representation."""

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ManifestError(f"Invalid release manifest JSON: {exc}") from exc
        if not isinstance(data, Mapping):
            raise ManifestError("Release manifest JSON must decode to an object.")
        return cls.from_dict(data)


@dataclass(frozen=True)
class FetchDecision:
    """Explain whether a release should be collected."""

    should_fetch: bool
    reason: str
    action: str
    requires_raw_download: bool = True
    existing_manifest: ReleaseManifest | None = None


@dataclass(frozen=True)
class EraWindow:
    """A deterministic date-period slice used for rolling backtests."""

    label: str
    start_period: str
    end_period: str
    periods: tuple[str, ...]
    observations: int


class ManifestStore:
    """Read and write release manifests with duplicate-collection guardrails."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()

    def path_for(self, dataset_id: str, release_period: str) -> Path:
        dataset_segment = _validate_path_segment(dataset_id, "dataset_id")
        release_segment = _validate_path_segment(release_period, "release_period")
        return _resolve_under(self.root, dataset_segment, f"{release_segment}.json")

    def history_dir_for(self, dataset_id: str, release_period: str) -> Path:
        dataset_segment = _validate_path_segment(dataset_id, "dataset_id")
        release_segment = _validate_path_segment(release_period, "release_period")
        return _resolve_under(self.root, dataset_segment, f"{release_segment}.history")

    def read(self, dataset_id: str, release_period: str) -> ReleaseManifest | None:
        path = self.path_for(dataset_id, release_period)
        if not path.exists():
            return None
        try:
            return ReleaseManifest.from_json(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ManifestError(f"Unable to read release manifest {path}: {exc}") from exc

    def write(self, manifest: ReleaseManifest) -> Path:
        _validate_manifest(manifest)
        path = self.path_for(manifest.dataset_id, manifest.release_period)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        try:
            if path.exists():
                archived = self._archive_existing(path, manifest)
                if archived is not None:
                    existing, archived_path = archived
                    manifest = replace(
                        manifest,
                        manifest_version=existing.manifest_version + 1,
                        revision_of=manifest.revision_of or existing.content_hash,
                        previous_manifest_path=manifest.previous_manifest_path
                        or str(archived_path.relative_to(self.root)),
                    )
                    _validate_manifest(manifest)
            tmp_path.write_text(manifest.to_json(), encoding="utf-8")
            tmp_path.replace(path)
        except OSError as exc:
            raise ManifestError(f"Unable to write release manifest {path}: {exc}") from exc
        return path

    def _archive_existing(
        self, path: Path, manifest: ReleaseManifest
    ) -> tuple[ReleaseManifest, Path] | None:
        current = path.read_text(encoding="utf-8")
        if current == manifest.to_json():
            return None
        existing = ReleaseManifest.from_json(current)
        history_dir = self.history_dir_for(existing.dataset_id, existing.release_period)
        history_dir.mkdir(parents=True, exist_ok=True)
        history_name = f"{_safe_timestamp(existing.fetched_at)}-{existing.content_hash[:12]}.json"
        history_path = _resolve_under(history_dir, history_name)
        history_path.write_text(current, encoding="utf-8")
        return existing, history_path

    def should_fetch(self, identity: ReleaseIdentity, *, force: bool = False) -> FetchDecision:
        _validate_path_segment(identity.dataset_id, "dataset_id")
        _validate_path_segment(identity.release_period, "release_period")
        if identity.content_hash is not None:
            _validate_hash(identity.content_hash)
        existing = self.read(identity.dataset_id, identity.release_period)
        if force:
            return FetchDecision(True, "forced_recollection", "ingest", True, existing)
        if existing is None:
            return FetchDecision(True, "missing_manifest", "ingest")
        if identity.content_hash:
            if identity.content_hash == existing.content_hash:
                schema_decision = _schema_reprocess_decision(identity, existing)
                if schema_decision is not None:
                    return schema_decision
                return FetchDecision(False, "content_hash_match", "skip", False, existing)
            return FetchDecision(True, "content_hash_changed", "record_revision", True, existing)
        if identity.etag:
            if identity.etag == existing.etag:
                schema_decision = _schema_reprocess_decision(identity, existing)
                if schema_decision is not None:
                    return schema_decision
                return FetchDecision(False, "etag_match", "skip", False, existing)
            return FetchDecision(True, "etag_changed", "record_revision", True, existing)
        if identity.last_modified:
            if identity.last_modified == existing.last_modified:
                schema_decision = _schema_reprocess_decision(identity, existing)
                if schema_decision is not None:
                    return schema_decision
                return FetchDecision(False, "last_modified_match", "skip", False, existing)
            return FetchDecision(True, "last_modified_changed", "record_revision", True, existing)
        if identity.source_url != existing.source_url:
            return FetchDecision(True, "source_url_changed", "record_revision", True, existing)
        schema_decision = _schema_reprocess_decision(identity, existing)
        if schema_decision is not None:
            return schema_decision
        return FetchDecision(False, "manifest_exists", "skip", False, existing)


DEFAULT_PUBLIC_DATASETS: tuple[DatasetDefinition, ...] = (
    DatasetDefinition(
        dataset_id="census_aies_annual",
        name="Annual Integrated Economic Survey",
        agency="U.S. Census Bureau",
        endpoint="https://www2.census.gov/programs-surveys/aies/data/2023/AIES00BASIC.zip",
        update_cadence="annual",
        frequency="annual",
        observation_period="Survey year",
        release_period="Annual Census AIES release year",
        units="Thousands of U.S. dollars in source files; normalized to U.S. dollars",
        historical_coverage="2023-present as AIES; earlier coverage via predecessor surveys",
        canonical_schema=DIRECT_INDUSTRY_SCHEMA,
        canonical_field_mappings=DIRECT_INDUSTRY_FIELD_MAPPINGS,
        implementation_status=ImplementationStatus(
            cataloged=True,
            endpoint_verified=True,
            adapter_implemented=True,
            backfill_validated=True,
            listener_validated=True,
        ),
        release_monitor="https://www.census.gov/programs-surveys/aies.html",
        steward_notes=(
            "Existing keyless official snapshot anchor.",
            "Backfill also retrieves https://www2.census.gov/programs-surveys/aies/data/2023/AIES00EXP01.zip.",
        ),
    ),
    DatasetDefinition(
        dataset_id="census_m3_monthly",
        name="Manufacturers' Shipments, Inventories, and Orders",
        agency="U.S. Census Bureau",
        endpoint="https://api.census.gov/data/timeseries/eits/m3",
        update_cadence="monthly",
        frequency="monthly",
        observation_period="Monthly observation period",
        release_period="Monthly Census M3 release period",
        units="Source-native M3 indicator units",
        historical_coverage="Monthly manufacturing indicators exposed by Census EITS",
        canonical_schema=SIGNAL_SCHEMA,
        canonical_field_mappings=SIGNAL_FIELD_MAPPINGS,
        release_monitor="https://www.census.gov/manufacturing/m3/",
    ),
    DatasetDefinition(
        dataset_id="census_retail_monthly",
        name="Monthly Retail Trade Survey",
        agency="U.S. Census Bureau",
        endpoint="https://api.census.gov/data/timeseries/eits/marts",
        update_cadence="monthly",
        frequency="monthly",
        observation_period="Monthly observation period",
        release_period="Monthly Census retail release period",
        units="Source-native retail indicator units",
        historical_coverage="Monthly retail indicators exposed by Census EITS",
        canonical_schema=SIGNAL_SCHEMA,
        canonical_field_mappings=SIGNAL_FIELD_MAPPINGS,
        release_monitor="https://www.census.gov/retail/marts/",
    ),
    DatasetDefinition(
        dataset_id="census_wholesale_monthly",
        name="Monthly Wholesale Trade Survey",
        agency="U.S. Census Bureau",
        endpoint="https://api.census.gov/data/timeseries/eits/mwts",
        update_cadence="monthly",
        frequency="monthly",
        observation_period="Monthly observation period",
        release_period="Monthly Census wholesale release period",
        units="Source-native wholesale indicator units",
        historical_coverage="Monthly wholesale indicators exposed by Census EITS",
        canonical_schema=SIGNAL_SCHEMA,
        canonical_field_mappings=SIGNAL_FIELD_MAPPINGS,
        release_monitor="https://www.census.gov/wholesale/",
    ),
    DatasetDefinition(
        dataset_id="census_qss_quarterly",
        name="Quarterly Services Survey",
        agency="U.S. Census Bureau",
        endpoint="https://api.census.gov/data/timeseries/eits/qss",
        update_cadence="quarterly",
        frequency="quarterly",
        observation_period="Quarterly observation period",
        release_period="Quarterly Census QSS release period",
        units="Source-native services indicator units",
        historical_coverage="Quarterly services indicators exposed by Census EITS",
        canonical_schema=SIGNAL_SCHEMA,
        canonical_field_mappings=SIGNAL_FIELD_MAPPINGS,
        release_monitor="https://www.census.gov/services/qss/",
    ),
    DatasetDefinition(
        dataset_id="bls_ppi_monthly",
        name="Producer Price Index",
        agency="U.S. Bureau of Labor Statistics",
        endpoint="https://api.bls.gov/publicAPI/v2/timeseries/data/",
        update_cadence="monthly",
        frequency="monthly",
        observation_period="Monthly observation period",
        release_period="Monthly BLS PPI release period",
        units="Index value, base period varies by BLS series",
        historical_coverage="Monthly public BLS time series within no-key API limits",
        canonical_schema=SIGNAL_SCHEMA,
        canonical_field_mappings=SIGNAL_FIELD_MAPPINGS,
        implementation_status=ImplementationStatus(
            cataloged=True,
            endpoint_verified=True,
            adapter_implemented=True,
            backfill_validated=True,
            listener_validated=True,
        ),
        release_monitor="https://www.bls.gov/ppi/",
    ),
    DatasetDefinition(
        dataset_id="bls_ces_monthly",
        name="Current Employment Statistics",
        agency="U.S. Bureau of Labor Statistics",
        endpoint="https://api.bls.gov/publicAPI/v2/timeseries/data/",
        update_cadence="monthly",
        frequency="monthly",
        observation_period="Monthly observation period",
        release_period="Monthly BLS CES release period",
        units="Source-native employment, hours, or earnings units",
        historical_coverage="Monthly public BLS time series within no-key API limits",
        canonical_schema=SIGNAL_SCHEMA,
        canonical_field_mappings=SIGNAL_FIELD_MAPPINGS,
        release_monitor="https://www.bls.gov/ces/",
    ),
    DatasetDefinition(
        dataset_id="fed_g17_monthly",
        name="Industrial Production and Capacity Utilization",
        agency="Board of Governors of the Federal Reserve System",
        endpoint="https://www.federalreserve.gov/releases/g17/",
        update_cadence="monthly",
        frequency="monthly",
        observation_period="Monthly observation period",
        release_period="Monthly Federal Reserve G.17 release period",
        units="Source-native industrial production or capacity utilization index/percent units",
        historical_coverage="Monthly G.17 releases and downloadable public tables",
        canonical_schema=SIGNAL_SCHEMA,
        canonical_field_mappings=SIGNAL_FIELD_MAPPINGS,
        release_monitor="https://www.federalreserve.gov/releases/g17/",
    ),
    DatasetDefinition(
        dataset_id="gdelt_events_daily",
        name="GDELT 2.1 Events and GKG",
        agency="GDELT Project",
        endpoint="https://data.gdeltproject.org/gdeltv2/masterfilelist.txt",
        update_cadence="daily",
        frequency="daily",
        observation_period="Event file timestamp",
        release_period="GDELT file timestamp or daily batch",
        units="Event/context records, not economic measurements",
        historical_coverage="Public event files for recent and historical event context",
        canonical_schema=SIGNAL_SCHEMA,
        canonical_field_mappings=SIGNAL_FIELD_MAPPINGS,
        source_type="event_context",
        economic_ground_truth=False,
        release_monitor="https://data.gdeltproject.org/gdeltv2/masterfilelist.txt",
        steward_notes=(
            "Use for inference triggers and context, not official economic ground truth.",
        ),
    ),
)


def validate_dataset_catalog(
    definitions: Iterable[DatasetDefinition], *, require_public: bool = True
) -> tuple[DatasetDefinition, ...]:
    """Validate catalog definitions and return them as an immutable tuple."""

    catalog = tuple(definitions)
    errors: list[str] = []
    seen_ids: set[str] = set()
    for definition in catalog:
        try:
            _validate_path_segment(definition.dataset_id, "dataset_id")
        except ManifestError as exc:
            errors.append(str(exc))
        if definition.dataset_id in seen_ids:
            errors.append(f"duplicate dataset_id: {definition.dataset_id}")
        seen_ids.add(definition.dataset_id)
        if not definition.name.strip():
            errors.append(f"{definition.dataset_id}: name is required")
        if not definition.endpoint.strip():
            errors.append(f"{definition.dataset_id}: endpoint is required")
        if definition.update_cadence not in _ALLOWED_CADENCES:
            errors.append(
                f"{definition.dataset_id}: unsupported cadence {definition.update_cadence}"
            )
        if definition.frequency not in _ALLOWED_CADENCES:
            errors.append(f"{definition.dataset_id}: unsupported frequency {definition.frequency}")
        if require_public and definition.auth_requirement != AUTH_NONE:
            errors.append(f"{definition.dataset_id}: requires auth ({definition.auth_requirement})")
        if not definition.canonical_schema:
            errors.append(f"{definition.dataset_id}: canonical_schema is required")
        if not definition.canonical_field_mappings:
            errors.append(f"{definition.dataset_id}: canonical_field_mappings are required")
        if not definition.observation_period.strip():
            errors.append(f"{definition.dataset_id}: observation_period is required")
        if not definition.release_period.strip():
            errors.append(f"{definition.dataset_id}: release_period is required")
        if not definition.units.strip():
            errors.append(f"{definition.dataset_id}: units are required")
        try:
            _validate_version(definition.schema_version, "schema_version")
        except ManifestError as exc:
            errors.append(f"{definition.dataset_id}: {exc}")
        status = definition.implementation_status.to_dict()
        if set(status) != set(IMPLEMENTATION_STAGES):
            errors.append(f"{definition.dataset_id}: implementation status is incomplete")
        if definition.source_type == "event_context" and definition.economic_ground_truth:
            errors.append(f"{definition.dataset_id}: event context cannot be economic ground truth")
    if errors:
        raise CatalogValidationError("; ".join(errors))
    return catalog


def public_dataset_catalog() -> tuple[DatasetDefinition, ...]:
    """Return the phase-one public dataset catalog after validation."""

    return validate_dataset_catalog(DEFAULT_PUBLIC_DATASETS)


def hash_payload(payload: bytes) -> str:
    """Return the SHA-256 hash used for release deduplication."""

    return hashlib.sha256(payload).hexdigest()


def build_release_manifest(
    *,
    dataset_id: str,
    release_period: str,
    source_url: str,
    content_hash: str,
    row_count: int,
    columns: Iterable[str],
    fetched_at: str | None = None,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    cleaning_version: str = DEFAULT_CLEANING_VERSION,
    etag: str | None = None,
    last_modified: str | None = None,
    observation_start: str | None = None,
    observation_end: str | None = None,
    release_notes_url: str | None = None,
    raw_artifact_path: str | None = None,
    cleaned_artifact_path: str | None = None,
    transformation_provenance: Iterable[str] = (),
    notes: Iterable[str] = (),
) -> ReleaseManifest:
    """Create a release manifest from known payload and cleaning metadata."""

    manifest = ReleaseManifest(
        dataset_id=dataset_id,
        release_period=release_period,
        source_url=source_url,
        fetched_at=fetched_at or _utc_now(),
        content_hash=content_hash,
        row_count=row_count,
        columns=tuple(str(column) for column in columns),
        schema_version=schema_version,
        cleaning_version=cleaning_version,
        etag=etag,
        last_modified=last_modified,
        observation_start=observation_start,
        observation_end=observation_end,
        release_notes_url=release_notes_url,
        raw_artifact_path=raw_artifact_path,
        cleaned_artifact_path=cleaned_artifact_path,
        transformation_provenance=tuple(str(step) for step in transformation_provenance),
        notes=tuple(str(note) for note in notes),
    )
    _validate_manifest(manifest)
    return manifest


def split_periods_into_eras(
    periods: Iterable[date | datetime | str], sections: int = 3
) -> tuple[EraWindow, ...]:
    """Split date-like periods into at least three balanced eras."""

    if sections < 3:
        raise ValueError("At least three sections are required for readiness backtesting.")
    normalised_periods = [_normalise_period(period) for period in periods]
    unique_periods = sorted(set(normalised_periods), key=_period_sort_key)
    if len(unique_periods) < sections:
        raise ValueError("Not enough distinct periods to create the requested eras.")

    sizes = _balanced_sizes(len(unique_periods), sections)
    eras: list[EraWindow] = []
    cursor = 0
    for index, size in enumerate(sizes, start=1):
        era_periods = tuple(unique_periods[cursor : cursor + size])
        era_period_set = set(era_periods)
        observations = sum(1 for period in normalised_periods if period in era_period_set)
        eras.append(
            EraWindow(
                label=f"era_{index}",
                start_period=era_periods[0],
                end_period=era_periods[-1],
                periods=era_periods,
                observations=observations,
            )
        )
        cursor += size
    return tuple(eras)


def _balanced_sizes(total: int, sections: int) -> list[int]:
    base_size = total // sections
    remainder = total % sections
    return [base_size + (1 if index < remainder else 0) for index in range(sections)]


def _normalise_period(value: date | datetime | str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        raise ValueError("Period values cannot be blank.")
    return text


def _period_sort_key(value: str) -> tuple[int, str]:
    parsed = _parse_period(value)
    if parsed is None:
        return (1, value)
    return (0, parsed.isoformat())


def _parse_period(value: str) -> date | None:
    try:
        if len(value) == 4 and value.isdigit():
            return date(int(value), 1, 1)
        if len(value) == 7 and value[4] == "-":
            year, month = value.split("-", 1)
            return date(int(year), int(month), 1)
        return date.fromisoformat(value)
    except ValueError:
        return None


def _schema_reprocess_decision(
    identity: ReleaseIdentity, existing: ReleaseManifest
) -> FetchDecision | None:
    if identity.schema_version and identity.schema_version != existing.schema_version:
        return FetchDecision(
            True,
            "schema_version_changed",
            "reprocess_cleaned",
            False,
            existing,
        )
    if identity.cleaning_version and identity.cleaning_version != existing.cleaning_version:
        return FetchDecision(
            True,
            "cleaning_version_changed",
            "reprocess_cleaned",
            False,
            existing,
        )
    return None


def _validate_manifest(manifest: ReleaseManifest) -> None:
    _validate_path_segment(manifest.dataset_id, "dataset_id")
    _validate_path_segment(manifest.release_period, "release_period")
    _validate_hash(manifest.content_hash)
    _validate_version(manifest.schema_version, "schema_version")
    _validate_version(manifest.cleaning_version, "cleaning_version")
    if not manifest.source_url.strip():
        raise ManifestError("source_url is required")
    if manifest.row_count < 0:
        raise ManifestError("row_count cannot be negative")
    if not manifest.columns:
        raise ManifestError("columns cannot be empty")
    if manifest.manifest_version < 1:
        raise ManifestError("manifest_version must be greater than zero")
    for label, path_value in (
        ("raw_artifact_path", manifest.raw_artifact_path),
        ("cleaned_artifact_path", manifest.cleaned_artifact_path),
        ("previous_manifest_path", manifest.previous_manifest_path),
    ):
        if path_value is not None:
            _validate_relative_output_path(path_value, label)


def _validate_hash(content_hash: str) -> None:
    if not _HASH_PATTERN.fullmatch(content_hash):
        raise ManifestError("content_hash must be a 64-character SHA-256 hex digest")


def _validate_version(value: str, label: str) -> None:
    if not _VERSION_PATTERN.fullmatch(value):
        raise ManifestError(f"{label} must be a non-path version identifier")


def _validate_path_segment(value: str, label: str) -> str:
    text = value.strip()
    if text in {"", ".", ".."}:
        raise ManifestError(f"{label} cannot be blank or a dot path segment")
    if "/" in text or "\\" in text:
        raise ManifestError(f"{label} cannot contain path separators")
    if not _SAFE_SEGMENT.fullmatch(text):
        raise ManifestError(f"{label} contains unsupported characters")
    return text


def _validate_relative_output_path(value: str, label: str) -> None:
    path = Path(value)
    if path.is_absolute() or any(part in {"..", ""} for part in path.parts):
        raise ManifestError(f"{label} must be a relative path without traversal")


def _resolve_under(root: Path, *segments: str) -> Path:
    path = root.joinpath(*segments).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ManifestError(f"Resolved path escapes public data root: {path}") from exc
    return path


def _safe_timestamp(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.=-]+", "_", value).strip("_") or "unknown-time"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "AUTH_NONE",
    "DEFAULT_CLEANING_VERSION",
    "DEFAULT_PUBLIC_DATASETS",
    "DEFAULT_SCHEMA_VERSION",
    "DIRECT_INDUSTRY_SCHEMA",
    "DIRECT_INDUSTRY_FIELD_MAPPINGS",
    "IMPLEMENTATION_STAGES",
    "SIGNAL_SCHEMA",
    "SIGNAL_FIELD_MAPPINGS",
    "CatalogValidationError",
    "DatasetDefinition",
    "EraWindow",
    "FetchDecision",
    "ImplementationStatus",
    "ManifestError",
    "ManifestStore",
    "ReleaseIdentity",
    "ReleaseManifest",
    "build_release_manifest",
    "hash_payload",
    "public_dataset_catalog",
    "split_periods_into_eras",
    "validate_dataset_catalog",
]
