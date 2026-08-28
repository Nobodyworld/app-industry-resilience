"""Typed multi-source Industry Momentum contracts and verified registry."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Literal
from urllib.parse import urlparse

from src.core.industry_pulse import INDUSTRY_PULSE_REGISTRY

INDUSTRY_MOMENTUM_REGISTRY_VERSION = "industry-momentum-registry-v1"
INDUSTRY_MOMENTUM_SCHEMA_VERSION = "industry-momentum-snapshot-v1"
INDUSTRY_MOMENTUM_INTERPRETATION = (
    "Producer prices, employment, production, capacity, and utilization are contextual "
    "official observations. They do not prove profitability, resilience, distress, "
    "insolvency, or causation and do not enter annual dashboard calculations."
)
INDUSTRY_MOMENTUM_COMPARISON_LIMITATION = (
    "Unlike units and index levels with different base periods must not be compared directly. "
    "A broader published mapping is not an exact six-digit industry match."
)

SourceFamily = Literal["bls_ppi", "bls_ces", "fed_g17"]
SignalType = Literal[
    "producer_price_index",
    "employment_count",
    "average_weekly_hours",
    "average_hourly_earnings",
    "industrial_production_index",
    "capacity_index",
    "capacity_utilization_rate",
]
MappingRelationship = Literal["exact", "broader_published", "manual_only"]
MappingLevel = Literal["six_digit", "five_digit", "four_digit", "three_digit", "combined"]
ChangeMethod = Literal["percent_change", "percentage_point_change"]
MomentumAvailability = Literal["available", "partial", "unmapped", "empty_range", "unavailable"]
MomentumFreshness = Literal["current", "stale", "unknown"]
ChangeUnavailableReason = Literal[
    "comparison_period_missing",
    "denominator_zero",
    "period_malformed",
    "insufficient_history",
]

_TARGET_PATTERN = re.compile(r"^[0-9]{6}$")
_CES_PATTERN = re.compile(r"^CES[0-9]{10}$")
_FED_PATTERN = re.compile(r"^(?:IP|CAP|CAPUTL)\.[A-Z0-9@]+\.S$")
_MONTH_PATTERN = re.compile(r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
_INDEX_SIGNALS = {
    "producer_price_index",
    "industrial_production_index",
    "capacity_index",
}


class IndustryMomentumRegistryError(ValueError):
    """Raised when a verified registry entry violates the public contract."""


class IndustryMomentumSnapshotError(ValueError):
    """Raised when a committed family snapshot or manifest is invalid."""


@dataclass(frozen=True)
class IndustryMomentumRegistryEntry:
    """One officially verified source series and its selected-industry relationship."""

    source_family: SourceFamily
    signal_type: SignalType
    series_id: str
    published_industry_code: str
    target_industry_code: str
    mapping_relationship: MappingRelationship
    mapping_level: MappingLevel
    registry_label: str
    official_title: str
    units: str
    change_method: ChangeMethod
    seasonal_adjustment: str
    base_period: str | None
    source_url: str
    source_table: str
    mapping_basis: str
    historical_coverage: str
    steward_notes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _TARGET_PATTERN.fullmatch(self.target_industry_code):
            raise IndustryMomentumRegistryError("Target industry code must be six digits.")
        self._validate_series_id()
        required = {
            "published industry code": self.published_industry_code,
            "registry label": self.registry_label,
            "official title": self.official_title,
            "units": self.units,
            "seasonal adjustment": self.seasonal_adjustment,
            "source table": self.source_table,
            "mapping basis": self.mapping_basis,
            "historical coverage": self.historical_coverage,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise IndustryMomentumRegistryError(
                f"Registry entry missing documentation: {', '.join(missing)}."
            )
        parsed = urlparse(self.source_url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "api.bls.gov",
            "data.bls.gov",
            "www.bls.gov",
            "download.bls.gov",
            "www.federalreserve.gov",
        }:
            raise IndustryMomentumRegistryError("Source URL must be an official HTTPS URL.")
        if self.mapping_relationship == "exact":
            if self.mapping_level != "six_digit":
                raise IndustryMomentumRegistryError("Exact mappings must use six_digit level.")
            if self.published_industry_code != self.target_industry_code:
                raise IndustryMomentumRegistryError(
                    "Exact mappings require the official published six-digit code."
                )
        elif self.mapping_level == "six_digit" and self.mapping_relationship == "broader_published":
            raise IndustryMomentumRegistryError(
                "A broader mapping cannot claim a six-digit published level."
            )
        expected_method = (
            "percentage_point_change"
            if self.signal_type == "capacity_utilization_rate"
            else "percent_change"
        )
        if self.change_method != expected_method:
            raise IndustryMomentumRegistryError(f"{self.signal_type} requires {expected_method}.")
        if self.signal_type in _INDEX_SIGNALS:
            if self.base_period is None or not self.base_period.strip():
                raise IndustryMomentumRegistryError("Index series require a base period.")
        if not self.steward_notes or any(not note.strip() for note in self.steward_notes):
            raise IndustryMomentumRegistryError("Registry entries require review notes.")
        if "review" not in " ".join(self.steward_notes).casefold():
            raise IndustryMomentumRegistryError("Steward notes must identify official review.")

    def _validate_series_id(self) -> None:
        if self.source_family == "bls_ppi":
            if not self.series_id.startswith("PCU"):
                raise IndustryMomentumRegistryError("BLS PPI series must use a PCU identifier.")
        elif self.source_family == "bls_ces":
            if not _CES_PATTERN.fullmatch(self.series_id):
                raise IndustryMomentumRegistryError("BLS CES series ID is malformed.")
        elif not _FED_PATTERN.fullmatch(self.series_id):
            raise IndustryMomentumRegistryError("Federal Reserve G.17 series ID is malformed.")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steward_notes"] = list(self.steward_notes)
        return payload


class IndustryMomentumRegistry:
    """Validated deterministic source registry with mapping and filter lookups."""

    def __init__(self, entries: tuple[IndustryMomentumRegistryEntry, ...]) -> None:
        if not entries:
            raise IndustryMomentumRegistryError("Industry Momentum registry cannot be empty.")
        identities: set[tuple[str, str]] = set()
        for entry in entries:
            identity = (entry.source_family, entry.series_id)
            if identity in identities:
                raise IndustryMomentumRegistryError(
                    f"Duplicate source-family/series identity: {identity}."
                )
            identities.add(identity)
        self._entries = tuple(
            sorted(entries, key=lambda item: (item.source_family, item.series_id))
        )
        self._by_identity = {
            (entry.source_family, entry.series_id): entry for entry in self._entries
        }

    @property
    def entries(self) -> tuple[IndustryMomentumRegistryEntry, ...]:
        return self._entries

    def by_series_id(
        self, series_id: str, source_family: SourceFamily | None = None
    ) -> IndustryMomentumRegistryEntry | None:
        matches = [
            entry
            for entry in self._entries
            if entry.series_id == series_id
            and (source_family is None or entry.source_family == source_family)
        ]
        return matches[0] if len(matches) == 1 else None

    def for_industry(
        self,
        industry_code: str,
        *,
        source_family: SourceFamily | None = None,
        signal_type: SignalType | None = None,
    ) -> tuple[IndustryMomentumRegistryEntry, ...]:
        if not _TARGET_PATTERN.fullmatch(industry_code):
            return ()
        return tuple(
            entry
            for entry in self._entries
            if entry.target_industry_code == industry_code
            and entry.mapping_relationship != "manual_only"
            and (source_family is None or entry.source_family == source_family)
            and (signal_type is None or entry.signal_type == signal_type)
        )

    def filtered(
        self,
        *,
        source_family: SourceFamily | None = None,
        signal_type: SignalType | None = None,
        series_id: str | None = None,
    ) -> tuple[IndustryMomentumRegistryEntry, ...]:
        return tuple(
            entry
            for entry in self._entries
            if (source_family is None or entry.source_family == source_family)
            and (signal_type is None or entry.signal_type == signal_type)
            and (series_id is None or entry.series_id == series_id)
        )


@dataclass(frozen=True)
class IndustryMomentumObservation:
    """One normalized monthly observation from a committed family snapshot."""

    source_family: SourceFamily
    signal_type: SignalType
    series_id: str
    published_industry_code: str
    target_industry_code: str
    mapping_relationship: MappingRelationship
    observation_date: date
    value: float
    units: str
    seasonal_adjustment: str
    base_period: str | None
    release_period: str
    source: str

    def __post_init__(self) -> None:
        if self.observation_date.day != 1:
            raise IndustryMomentumSnapshotError(
                "Momentum observation dates must be first-of-month dates."
            )
        if not math.isfinite(self.value):
            raise IndustryMomentumSnapshotError("Momentum values must be finite.")

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "observation_date": self.observation_date.isoformat()}


@dataclass(frozen=True)
class IndustryMomentumChange:
    """A change result bound to an exact calendar comparison period."""

    value: float | None
    method: ChangeMethod
    units: str
    latest_period: str | None
    comparison_period: str | None
    unavailable_reason: ChangeUnavailableReason | None = None

    @property
    def available(self) -> bool:
        return self.value is not None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IndustryMomentumFreshness:
    state: MomentumFreshness
    as_of: date
    latest_observation_date: date | None
    age_days: int | None
    threshold_days: int

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "as_of": self.as_of.isoformat(),
            "latest_observation_date": (
                self.latest_observation_date.isoformat()
                if self.latest_observation_date is not None
                else None
            ),
        }


@dataclass(frozen=True)
class IndustryMomentumProvenance:
    dataset_id: str
    provider: str
    source_url: str
    retrieval_mode: Literal["offline_reviewed_snapshot"]
    retrieved_at: datetime
    snapshot_sha256: str
    manifest_identity: str
    registry_version: str
    schema_version: str
    observation_start: date
    observation_end: date
    transformations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "retrieved_at": self.retrieved_at.isoformat().replace("+00:00", "Z"),
            "observation_start": self.observation_start.isoformat(),
            "observation_end": self.observation_end.isoformat(),
            "transformations": list(self.transformations),
        }


@dataclass(frozen=True)
class IndustryMomentumSignalHistory:
    availability: MomentumAvailability
    mapping: IndustryMomentumRegistryEntry
    observations: tuple[IndustryMomentumObservation, ...]
    latest_observation: IndustryMomentumObservation | None
    month_over_month: IndustryMomentumChange
    year_over_year: IndustryMomentumChange
    freshness: IndustryMomentumFreshness
    observation_start: date | None
    observation_end: date | None
    release_period: str | None
    provenance: IndustryMomentumProvenance | None
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "availability": self.availability,
            "mapping": self.mapping.to_dict(),
            "latest_observation": (
                self.latest_observation.to_dict() if self.latest_observation else None
            ),
            "month_over_month": self.month_over_month.to_dict(),
            "year_over_year": self.year_over_year.to_dict(),
            "freshness": self.freshness.to_dict(),
            "observation_range": {
                "start": self.observation_start.isoformat() if self.observation_start else None,
                "end": self.observation_end.isoformat() if self.observation_end else None,
            },
            "observations": [item.to_dict() for item in self.observations],
            "release_period": self.release_period,
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class IndustryMomentumFamilyResult:
    source_family: SourceFamily
    availability: MomentumAvailability
    histories: tuple[IndustryMomentumSignalHistory, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_family": self.source_family,
            "availability": self.availability,
            "histories": [history.to_dict() for history in self.histories],
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class IndustryMomentumResult:
    industry_code: str
    availability: MomentumAvailability
    mapping_relationship: MappingRelationship | None
    families: tuple[IndustryMomentumFamilyResult, ...]
    requested_filters: dict[str, Any]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "industry_code": self.industry_code,
            "availability": self.availability,
            "mapping_relationship": self.mapping_relationship,
            "families": [family.to_dict() for family in self.families],
            "requested_filters": self.requested_filters,
            "limitations": list(self.limitations),
        }


def _ppi_entries() -> tuple[IndustryMomentumRegistryEntry, ...]:
    return tuple(
        IndustryMomentumRegistryEntry(
            source_family="bls_ppi",
            signal_type="producer_price_index",
            series_id=entry.series_id,
            published_industry_code=entry.industry_code,
            target_industry_code=entry.industry_code,
            mapping_relationship="exact",
            mapping_level="six_digit",
            registry_label=entry.registry_label,
            official_title=entry.source_title,
            units=entry.units,
            change_method="percent_change",
            seasonal_adjustment=entry.seasonal_adjustment,
            base_period=entry.base_date,
            source_url=entry.source_url,
            source_table="BLS PPI current industry series",
            mapping_basis=entry.mapping_basis,
            historical_coverage="See the reviewed PPI registry and committed snapshot.",
            steward_notes=entry.steward_notes,
        )
        for entry in INDUSTRY_PULSE_REGISTRY.entries
    )


def _ces_entry(
    series_id: str,
    published_code: str,
    target_code: str,
    level: MappingLevel,
    label: str,
    title: str,
) -> IndustryMomentumRegistryEntry:
    relationship: MappingRelationship = (
        "exact" if published_code == target_code and level == "six_digit" else "broader_published"
    )
    return IndustryMomentumRegistryEntry(
        source_family="bls_ces",
        signal_type="employment_count",
        series_id=series_id,
        published_industry_code=published_code,
        target_industry_code=target_code,
        mapping_relationship=relationship,
        mapping_level=level,
        registry_label=label,
        official_title=title,
        units="Thousands of employees",
        change_method="percent_change",
        seasonal_adjustment="Seasonally adjusted",
        base_period=None,
        source_url=f"https://data.bls.gov/timeseries/{series_id}",
        source_table="BLS CES national series and industry files",
        mapping_basis=(
            f"Official CES industry code {series_id[3:11]} publishes NAICS {published_code}; "
            f"relationship to selected NAICS {target_code} is {relationship}."
        ),
        historical_coverage="1990-01 through at least 2026-06 in the reviewed series file.",
        steward_notes=(
            "Reviewed against official BLS CES series and industry files on 2026-08-10.",
            "All-employees datatype 01; context only and not an annual dashboard input.",
        ),
    )


_CES_ENTRIES = (
    _ces_entry(
        "CES3231110001",
        "3111",
        "311111",
        "four_digit",
        "Animal food manufacturing employment",
        "All employees, thousands, animal food manufacturing, seasonally adjusted",
    ),
    _ces_entry(
        "CES3232914001",
        "31212,31213,31214",
        "312120",
        "combined",
        "Breweries, wineries, and distilleries employment",
        "All employees, thousands, breweries, wineries, and distilleries, seasonally adjusted",
    ),
    _ces_entry(
        "CES3232210001",
        "3221",
        "322120",
        "four_digit",
        "Pulp, paper, and paperboard mills employment",
        "All employees, thousands, pulp, paper, and paperboard mills, seasonally adjusted",
    ),
    _ces_entry(
        "CES3232521101",
        "325211",
        "325211",
        "six_digit",
        "Plastics material and resin manufacturing employment",
        "All employees, thousands, plastics material and resin manufacturing, seasonally adjusted",
    ),
    _ces_entry(
        "CES3232611001",
        "32611",
        "326111",
        "five_digit",
        "Plastics packaging materials and film employment",
        "All employees, thousands, plastics packaging materials and unlaminated film and sheet manufacturing, seasonally adjusted",
    ),
    _ces_entry(
        "CES3133110001",
        "3311",
        "331110",
        "four_digit",
        "Iron and steel mills and ferroalloy employment",
        "All employees, thousands, iron and steel mills and ferroalloy manufacturing, seasonally adjusted",
    ),
    _ces_entry(
        "CES3133411101",
        "334111",
        "334111",
        "six_digit",
        "Electronic computer manufacturing employment",
        "All employees, thousands, electronic computer manufacturing, seasonally adjusted",
    ),
    _ces_entry(
        "CES3133610001",
        "3361",
        "336110",
        "four_digit",
        "Motor vehicle manufacturing employment",
        "All employees, thousands, motor vehicle manufacturing, seasonally adjusted",
    ),
)


def _g17_entry(
    signal_type: SignalType,
    code: str,
    published_code: str,
    target_code: str,
    level: MappingLevel,
    title: str,
) -> IndustryMomentumRegistryEntry:
    prefixes = {
        "industrial_production_index": ("IP", "Industrial production index (2017=100)"),
        "capacity_index": ("CAP", "Industrial capacity index (2017=100)"),
        "capacity_utilization_rate": ("CAPUTL", "Percent of industrial capacity"),
    }
    prefix, units = prefixes[signal_type]
    relationship: MappingRelationship = (
        "exact" if published_code == target_code and level == "six_digit" else "broader_published"
    )
    data_file = {
        "industrial_production_index": "ip_sa.txt",
        "capacity_index": "cap_sa.txt",
        "capacity_utilization_rate": "utl_sa.txt",
    }[signal_type]
    return IndustryMomentumRegistryEntry(
        source_family="fed_g17",
        signal_type=signal_type,
        series_id=f"{prefix}.{code}.S",
        published_industry_code=published_code,
        target_industry_code=target_code,
        mapping_relationship=relationship,
        mapping_level=level,
        registry_label=title,
        official_title=title,
        units=units,
        change_method=(
            "percentage_point_change"
            if signal_type == "capacity_utilization_rate"
            else "percent_change"
        ),
        seasonal_adjustment="Seasonally adjusted",
        base_period=None if signal_type == "capacity_utilization_rate" else "2017=100",
        source_url=("https://www.federalreserve.gov/releases/g17/Current/ipdisk/" + data_file),
        source_table=(
            "G.17 tables 1, 2 and supplement"
            if signal_type == "industrial_production_index"
            else "G.17 tables 7 and 8"
        ),
        mapping_basis=(
            f"Official G.17 code {code} publishes NAICS {published_code}; relationship to "
            f"selected NAICS {target_code} is {relationship}."
        ),
        historical_coverage="Official monthly G.17 file through 2026-06; start varies by series.",
        steward_notes=(
            "Reviewed against official Federal Reserve G.17 documentation on 2026-08-10.",
            "G.17 codes may change during annual revisions; validate every refresh.",
        ),
    )


_G17_PRODUCTION = (
    _g17_entry(
        "industrial_production_index",
        "G3111",
        "3111",
        "311111",
        "four_digit",
        "Animal food industrial production",
    ),
    _g17_entry(
        "industrial_production_index",
        "N31212",
        "31212",
        "312120",
        "five_digit",
        "Breweries industrial production",
    ),
    _g17_entry(
        "industrial_production_index",
        "G32212",
        "32212",
        "322120",
        "five_digit",
        "Paper mills industrial production",
    ),
    _g17_entry(
        "industrial_production_index",
        "N325211",
        "325211",
        "325211",
        "six_digit",
        "Plastics material and resin industrial production",
    ),
    _g17_entry(
        "industrial_production_index",
        "G3261",
        "3261",
        "326111",
        "four_digit",
        "Plastics product industrial production",
    ),
    _g17_entry(
        "industrial_production_index",
        "G3311A2",
        "3311,3312",
        "331110",
        "combined",
        "Iron and steel products industrial production",
    ),
    _g17_entry(
        "industrial_production_index",
        "G3341",
        "3341",
        "334111",
        "four_digit",
        "Computer and peripheral equipment industrial production",
    ),
    _g17_entry(
        "industrial_production_index",
        "G33611",
        "33611",
        "336110",
        "five_digit",
        "Automobile and light-duty motor vehicle industrial production",
    ),
)

_CAPACITY_MAPPINGS: tuple[tuple[str, str, str, MappingLevel, str], ...] = (
    ("G311A2", "311,312", "311111", "combined", "Food, beverage, and tobacco"),
    ("G322", "322", "322120", "three_digit", "Paper"),
    ("G325", "325", "325211", "three_digit", "Chemical"),
    ("G326", "326", "326111", "three_digit", "Plastics and rubber products"),
    ("G331", "331", "331110", "three_digit", "Primary metal"),
    ("G334", "334", "334111", "three_digit", "Computer and electronic product"),
    ("G3361T3", "3361-3363", "336110", "combined", "Motor vehicles and parts"),
)

_G17_CAPACITY = tuple(
    _g17_entry("capacity_index", code, published, target, level, f"{title} industrial capacity")
    for code, published, target, level, title in _CAPACITY_MAPPINGS
)
_G17_UTILIZATION = tuple(
    _g17_entry(
        "capacity_utilization_rate",
        code,
        published,
        target,
        level,
        f"{title} capacity utilization",
    )
    for code, published, target, level, title in _CAPACITY_MAPPINGS
)

INDUSTRY_MOMENTUM_REGISTRY = IndustryMomentumRegistry(
    _ppi_entries() + _CES_ENTRIES + _G17_PRODUCTION + _G17_CAPACITY + _G17_UTILIZATION
)


def validate_observation_month(value: str) -> date:
    """Parse one strict YYYY-MM or first-of-month ISO observation period."""

    candidate = value[:7] if len(value) == 10 and value.endswith("-01") else value
    if not _MONTH_PATTERN.fullmatch(candidate):
        raise IndustryMomentumSnapshotError("Observation period must be YYYY-MM.")
    year, month = (int(part) for part in candidate.split("-"))
    return date(year, month, 1)


__all__ = [
    "ChangeMethod",
    "ChangeUnavailableReason",
    "INDUSTRY_MOMENTUM_COMPARISON_LIMITATION",
    "INDUSTRY_MOMENTUM_INTERPRETATION",
    "INDUSTRY_MOMENTUM_REGISTRY",
    "INDUSTRY_MOMENTUM_REGISTRY_VERSION",
    "INDUSTRY_MOMENTUM_SCHEMA_VERSION",
    "IndustryMomentumChange",
    "IndustryMomentumFamilyResult",
    "IndustryMomentumFreshness",
    "IndustryMomentumObservation",
    "IndustryMomentumProvenance",
    "IndustryMomentumRegistry",
    "IndustryMomentumRegistryEntry",
    "IndustryMomentumRegistryError",
    "IndustryMomentumResult",
    "IndustryMomentumSignalHistory",
    "IndustryMomentumSnapshotError",
    "MappingLevel",
    "MappingRelationship",
    "MomentumAvailability",
    "MomentumFreshness",
    "SignalType",
    "SourceFamily",
    "validate_observation_month",
]
