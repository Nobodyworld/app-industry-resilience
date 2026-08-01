"""Typed Industry Pulse contracts and the reviewed BLS PPI registry."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Literal

INDUSTRY_PULSE_REGISTRY_VERSION = "industry-pulse-registry-v1"
INDUSTRY_PULSE_SCHEMA_VERSION = "industry-pulse-snapshot-v1"
INDUSTRY_PULSE_SOURCE = "U.S. Bureau of Labor Statistics Producer Price Index"
INDUSTRY_PULSE_ENDPOINT = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
INDUSTRY_PULSE_INTERPRETATION = (
    "Producer Price Index observations show price movement for a verified mapped BLS "
    "industry series. They are contextual signals, not the dashboard's annual "
    "output-to-cost ratio, and they do not establish profitability, resilience, "
    "insolvency risk, or causation."
)
INDUSTRY_PULSE_LEVEL_LIMITATION = (
    "Raw index levels from different BLS series must not be compared directly because "
    "their base dates can differ. A mapped signal may not represent every product or "
    "establishment in a broader industry."
)
_SERIES_PATTERN = re.compile(r"^PCU(?P<industry>[0-9]{6})(?P<product>[0-9]{6})$")
_NAICS_PATTERN = re.compile(r"^[0-9]{6}$")
_BASE_DATE_PATTERN = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")

AvailabilityState = Literal["available", "unmapped", "empty_range"]
FreshnessState = Literal["current", "stale", "unknown"]
ChangeUnavailableReason = Literal[
    "comparison_period_missing",
    "denominator_zero",
    "period_malformed",
    "insufficient_history",
]


class IndustryPulseRegistryError(ValueError):
    """Raised when a reviewed registry entry is incomplete or ambiguous."""


class IndustryPulseSnapshotError(ValueError):
    """Raised when the committed snapshot or manifest fails validation."""


@dataclass(frozen=True)
class IndustryPulseRegistryEntry:
    """One officially reviewed whole-industry BLS PPI mapping."""

    series_id: str
    industry_code: str
    registry_label: str
    source_title: str
    units: str
    seasonal_adjustment: str
    base_date: str
    source_url: str
    mapping_basis: str
    steward_notes: tuple[str, ...]

    def __post_init__(self) -> None:
        match = _SERIES_PATTERN.fullmatch(self.series_id)
        if match is None:
            raise IndustryPulseRegistryError(
                "Series ID must be an uppercase whole-industry PCU identifier with "
                "exactly two six-digit segments."
            )
        if not _NAICS_PATTERN.fullmatch(self.industry_code):
            raise IndustryPulseRegistryError("Industry code must be a six-digit NAICS code.")
        if match.group("industry") != self.industry_code:
            raise IndustryPulseRegistryError(
                "BLS series industry segment must match the registered NAICS code."
            )
        if match.group("product") != self.industry_code:
            raise IndustryPulseRegistryError(
                "BLS whole-industry product segment must match the registered NAICS code."
            )
        required = {
            "registry label": self.registry_label,
            "source title": self.source_title,
            "units": self.units,
            "seasonal-adjustment status": self.seasonal_adjustment,
            "mapping basis": self.mapping_basis,
            "source URL": self.source_url,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise IndustryPulseRegistryError(
                f"Registry entry missing required documentation: {', '.join(missing)}."
            )
        if not _BASE_DATE_PATTERN.fullmatch(self.base_date):
            raise IndustryPulseRegistryError("BLS base date must use YYYY-MM.")
        if not self.source_url.startswith("https://") or "bls.gov/" not in self.source_url:
            raise IndustryPulseRegistryError("Source URL must be an official HTTPS BLS URL.")
        if not self.steward_notes or any(not note.strip() for note in self.steward_notes):
            raise IndustryPulseRegistryError(
                "Registry entries require non-empty steward notes documenting review."
            )
        if "review" not in " ".join(self.steward_notes).casefold():
            raise IndustryPulseRegistryError(
                "Registry steward notes must identify the mapping as reviewed."
            )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steward_notes"] = list(self.steward_notes)
        return payload

    def pipeline_mapping(self) -> dict[str, str]:
        """Return the existing public-data pipeline mapping shape."""

        return {
            "series_id": self.series_id,
            "industry_code": self.industry_code,
            "industry_name": self.registry_label,
            "signal_name": self.source_title,
            "units": self.units,
            "seasonal_adjustment": self.seasonal_adjustment,
            "base_date": self.base_date,
            "source_url": self.source_url,
            "mapping_notes": self.mapping_basis,
        }


class IndustryPulseRegistry:
    """Validated bidirectional registry with exact six-digit lookups only."""

    def __init__(self, entries: tuple[IndustryPulseRegistryEntry, ...]) -> None:
        if not entries:
            raise IndustryPulseRegistryError("Industry Pulse registry cannot be empty.")
        by_series: dict[str, IndustryPulseRegistryEntry] = {}
        by_industry: dict[str, IndustryPulseRegistryEntry] = {}
        for entry in entries:
            if entry.series_id in by_series:
                raise IndustryPulseRegistryError(
                    f"Duplicate Industry Pulse series ID: {entry.series_id}."
                )
            if entry.industry_code in by_industry:
                raise IndustryPulseRegistryError(
                    f"Duplicate or ambiguous Industry Pulse NAICS mapping: {entry.industry_code}."
                )
            by_series[entry.series_id] = entry
            by_industry[entry.industry_code] = entry
        self._entries = tuple(sorted(entries, key=lambda item: item.series_id))
        self._by_series = by_series
        self._by_industry = by_industry

    @property
    def entries(self) -> tuple[IndustryPulseRegistryEntry, ...]:
        return self._entries

    def by_series_id(self, series_id: str) -> IndustryPulseRegistryEntry | None:
        return self._by_series.get(series_id)

    def by_industry_code(self, industry_code: str) -> IndustryPulseRegistryEntry | None:
        if not _NAICS_PATTERN.fullmatch(industry_code):
            return None
        return self._by_industry.get(industry_code)


@dataclass(frozen=True)
class IndustryPulseObservation:
    """One normalized monthly BLS PPI observation."""

    series_id: str
    industry_code: str
    industry_name: str
    observation_date: date
    value: float
    units: str
    seasonal_adjustment: str
    base_date: str
    release_period: str
    source: str

    def __post_init__(self) -> None:
        if self.observation_date.day != 1:
            raise IndustryPulseSnapshotError(
                "Industry Pulse observation dates must be first-of-month dates."
            )
        if not math.isfinite(self.value):
            raise IndustryPulseSnapshotError("Industry Pulse values must be finite numbers.")

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "observation_date": self.observation_date.isoformat(),
        }


@dataclass(frozen=True)
class IndustryPulseChangeSummary:
    """A change calculation tied to an exact calendar comparison period."""

    value_pct: float | None
    latest_period: str | None
    comparison_period: str | None
    reason: ChangeUnavailableReason | None = None

    @property
    def available(self) -> bool:
        return self.value_pct is not None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IndustryPulseFreshness:
    """Monthly freshness assessment relative to an injected as-of date."""

    state: FreshnessState
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
class IndustryPulseProvenance:
    """Public, redacted provenance kept separate from annual dataset lineage."""

    dataset_id: str
    provider: str
    source_url: str
    retrieval_mode: Literal["offline_reviewed_snapshot"]
    retrieved_at: datetime
    snapshot_sha256: str
    manifest_identity: str
    registry_version: str
    schema_version: str
    transformations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["retrieved_at"] = self.retrieved_at.isoformat().replace("+00:00", "Z")
        payload["transformations"] = list(self.transformations)
        return payload


@dataclass(frozen=True)
class IndustryPulseSeriesHistory:
    """Snapshot-backed series result for UI, API, and exports."""

    availability: AvailabilityState
    mapping: IndustryPulseRegistryEntry | None
    observations: tuple[IndustryPulseObservation, ...]
    latest_observation: IndustryPulseObservation | None
    month_over_month: IndustryPulseChangeSummary
    year_over_year: IndustryPulseChangeSummary
    freshness: IndustryPulseFreshness
    observation_start: date | None
    observation_end: date | None
    release_period: str | None
    provenance: IndustryPulseProvenance
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "availability": self.availability,
            "mapping": self.mapping.to_dict() if self.mapping else None,
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
            "provenance": self.provenance.to_dict(),
            "limitations": list(self.limitations),
        }


def _entry(
    series_id: str,
    industry_code: str,
    registry_label: str,
    source_title: str,
    base_date: str,
) -> IndustryPulseRegistryEntry:
    mapping_basis = (
        f"Official BLS PCU whole-industry series: industry and product segments both "
        f"equal six-digit NAICS {industry_code}."
    )
    return IndustryPulseRegistryEntry(
        series_id=series_id,
        industry_code=industry_code,
        registry_label=registry_label,
        source_title=source_title,
        units="Producer Price Index (index; base period varies by series)",
        seasonal_adjustment="Not seasonally adjusted",
        base_date=base_date,
        source_url=f"https://data.bls.gov/timeseries/{series_id}",
        mapping_basis=mapping_basis,
        steward_notes=(
            "Reviewed against the BLS current PPI industry-series file in July 2026.",
            "Context only; do not use as an annual metric, score, or causal explanation.",
        ),
    )


INDUSTRY_PULSE_REGISTRY = IndustryPulseRegistry(
    (
        _entry(
            "PCU311111311111",
            "311111",
            "Dog and cat food manufacturing",
            "PPI industry data for Dog and cat food manufacturing",
            "1985-12",
        ),
        _entry(
            "PCU312120312120",
            "312120",
            "Breweries",
            "PPI industry data for Breweries",
            "1982-06",
        ),
        _entry(
            "PCU322120322120",
            "322120",
            "Paper mills",
            "PPI industry data for Paper mills",
            "2003-12",
        ),
        _entry(
            "PCU325211325211",
            "325211",
            "Plastics material and resin manufacturing",
            "PPI industry data for Plastics material and resin manufacturing",
            "1980-12",
        ),
        _entry(
            "PCU326111326111",
            "326111",
            "Plastics bag and pouch manufacturing",
            "PPI industry data for Plastics bag and pouch manufacturing",
            "2003-12",
        ),
        _entry(
            "PCU331110331110",
            "331110",
            "Iron and steel mills and ferroalloy manufacturing",
            "PPI industry data for Iron and steel mills and ferroalloy mfg",
            "1982-06",
        ),
        _entry(
            "PCU334111334111",
            "334111",
            "Electronic computer manufacturing",
            "PPI industry data for Electronic computer mfg",
            "2023-02",
        ),
        _entry(
            "PCU336110336110",
            "336110",
            "Automobile, light truck, and utility vehicle manufacturing",
            "PPI industry data for Automobile, light truck and utility vehicle mfg",
            "1982-06",
        ),
    )
)


__all__ = [
    "AvailabilityState",
    "ChangeUnavailableReason",
    "FreshnessState",
    "INDUSTRY_PULSE_ENDPOINT",
    "INDUSTRY_PULSE_INTERPRETATION",
    "INDUSTRY_PULSE_LEVEL_LIMITATION",
    "INDUSTRY_PULSE_REGISTRY",
    "INDUSTRY_PULSE_REGISTRY_VERSION",
    "INDUSTRY_PULSE_SCHEMA_VERSION",
    "INDUSTRY_PULSE_SOURCE",
    "IndustryPulseChangeSummary",
    "IndustryPulseFreshness",
    "IndustryPulseObservation",
    "IndustryPulseProvenance",
    "IndustryPulseRegistry",
    "IndustryPulseRegistryEntry",
    "IndustryPulseRegistryError",
    "IndustryPulseSeriesHistory",
    "IndustryPulseSnapshotError",
]
