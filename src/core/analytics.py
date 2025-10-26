from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

_HEALTH_REQUIRED_COLUMNS: tuple[str, ...] = (
    "value_added_pct",
    "resilience_score",
    "materials_dependency_ratio",
    "shock_sensitivity_index",
    "idiot_index",
    "industry_code",
    "industry_name",
)


@dataclass(frozen=True)
class HealthBand:
    """Describe a qualitative risk band for health scores."""

    name: str
    min_score: float
    description: str = ""


@dataclass(frozen=True)
class HealthScoreConfig:
    """Configuration controlling health score computation."""

    value_added_pct_weight: float = 0.35
    resilience_score_weight: float = 0.3
    materials_dependency_weight: float = 0.2
    shock_sensitivity_weight: float = 0.15
    resilience_reference: float = 3.0
    dependency_penalty_multiplier: float = 1.0
    shock_penalty_multiplier: float = 1.0
    sector_prefix_length: int = 2
    bands: tuple[HealthBand, ...] = field(
        default_factory=lambda: (
            HealthBand(
                name="excellent",
                min_score=80.0,
                description="Highly resilient and value-additive industries",
            ),
            HealthBand(
                name="healthy",
                min_score=65.0,
                description="Balanced performance with manageable risk",
            ),
            HealthBand(
                name="watch",
                min_score=45.0,
                description="Mixed signals that require monitoring",
            ),
            HealthBand(
                name="critical",
                min_score=0.0,
                description="Immediate intervention recommended",
            ),
        )
    )

    @property
    def total_weight(self) -> float:
        return (
            self.value_added_pct_weight
            + self.resilience_score_weight
            + self.materials_dependency_weight
            + self.shock_sensitivity_weight
        )

    def normalised_weights(self) -> tuple[float, float, float, float]:
        total = self.total_weight
        if total <= 0:
            raise ValueError("Health score weights must sum to a positive value.")
        return (
            self.value_added_pct_weight / total,
            self.resilience_score_weight / total,
            self.materials_dependency_weight / total,
            self.shock_sensitivity_weight / total,
        )


@dataclass(frozen=True)
class HealthAggregate:
    """Aggregate health insights for a cohort of industries."""

    label: str
    industries: int
    average_health_score: float | None
    risk_band: str | None
    average_idiot_index: float | None
    average_value_added_pct: float | None
    average_resilience_score: float | None
    average_materials_dependency_ratio: float | None
    average_shock_sensitivity_index: float | None


@dataclass(frozen=True)
class HealthBandBreakdown:
    """Count how many industries fall into each risk band."""

    band: str
    industries: int
    percentage: float


@dataclass(frozen=True)
class HealthRisk:
    """Describe an industry that ranks low on the health scale."""

    industry_code: str
    industry_name: str
    health_score: float | None
    band: str | None


@dataclass(frozen=True)
class HealthSummary:
    """Summaries derived from health score analytics."""

    overall: HealthAggregate
    sectors: tuple[HealthAggregate, ...]
    band_breakdown: tuple[HealthBandBreakdown, ...]
    top_risks: tuple[HealthRisk, ...]


def compute_health_scores(
    df: pd.DataFrame, *, config: HealthScoreConfig | None = None
) -> pd.DataFrame:
    """Return a dataframe with health score columns added."""

    config = config or HealthScoreConfig()
    _ensure_required_columns(df)
    weights = config.normalised_weights()
    sorted_bands = _sort_bands(config.bands)

    work = df.copy()
    work["value_added_pct"] = pd.to_numeric(work["value_added_pct"], errors="coerce").astype(
        "float64"
    )
    work["resilience_score"] = pd.to_numeric(work["resilience_score"], errors="coerce").astype(
        "float64"
    )
    work["materials_dependency_ratio"] = pd.to_numeric(
        work["materials_dependency_ratio"], errors="coerce"
    ).astype("float64")
    work["shock_sensitivity_index"] = pd.to_numeric(
        work["shock_sensitivity_index"], errors="coerce"
    ).astype("float64")

    value_added_component = work["value_added_pct"].clip(lower=0.0, upper=100.0) / 100.0
    resilience_component = (
        work["resilience_score"].clip(lower=0.0) / max(config.resilience_reference, 1.0)
    ).clip(upper=1.0)
    dependency_component = 1.0 - work["materials_dependency_ratio"].clip(lower=0.0, upper=1.0)
    dependency_component = (
        dependency_component.clip(lower=0.0) * config.dependency_penalty_multiplier
    )
    shock_component = 1.0 - work["shock_sensitivity_index"].clip(lower=0.0, upper=1.0)
    shock_component = shock_component.clip(lower=0.0) * config.shock_penalty_multiplier

    value_weight, resilience_weight, dependency_weight, shock_weight = weights
    raw_score = (
        (value_added_component * value_weight)
        + (resilience_component * resilience_weight)
        + (dependency_component * dependency_weight)
        + (shock_component * shock_weight)
    )

    score = (raw_score.clip(lower=0.0) * 100.0).round(2)
    work["health_score"] = score
    work["health_band"] = _classify_series(score, sorted_bands)
    return work


def summarise_health(
    df: pd.DataFrame,
    *,
    config: HealthScoreConfig | None = None,
    top_risk_limit: int = 5,
    group_by: Literal["sector", "overall", "all"] = "all",
) -> HealthSummary:
    """Summarise health analytics for overall and sector cohorts."""

    config = config or HealthScoreConfig()
    sorted_bands = _sort_bands(config.bands)
    scored = compute_health_scores(df, config=config)

    overall = _aggregate("overall", scored, bands=sorted_bands)
    include_sectors = group_by in {"sector", "all"}
    sector_aggregates = _aggregate_sectors(scored, config, sorted_bands) if include_sectors else []
    breakdown = _band_breakdown(scored, sorted_bands)
    top_risks = _top_risks(scored, limit=max(top_risk_limit, 0))

    return HealthSummary(
        overall=overall,
        sectors=tuple(sector_aggregates),
        band_breakdown=tuple(breakdown),
        top_risks=tuple(top_risks),
    )


def _ensure_required_columns(df: pd.DataFrame) -> None:
    missing = [column for column in _HEALTH_REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(
            "Dataframe missing required columns for health analytics: " + ", ".join(missing)
        )


def _classify_band(score: float | None, bands: Iterable[HealthBand]) -> str | None:
    if score is None or pd.isna(score):
        return None
    for band in bands:
        if score >= band.min_score:
            return band.name
    return None


def _aggregate(label: str, df: pd.DataFrame, *, bands: Iterable[HealthBand]) -> HealthAggregate:
    if df.empty:
        return HealthAggregate(
            label=label,
            industries=0,
            average_health_score=None,
            risk_band=None,
            average_idiot_index=None,
            average_value_added_pct=None,
            average_resilience_score=None,
            average_materials_dependency_ratio=None,
            average_shock_sensitivity_index=None,
        )

    mean_health = float(df["health_score"].mean()) if "health_score" in df else None
    band = _classify_band(mean_health, bands) if mean_health is not None else None
    return HealthAggregate(
        label=label,
        industries=int(df.shape[0]),
        average_health_score=mean_health,
        risk_band=band,
        average_idiot_index=float(df["idiot_index"].mean()) if "idiot_index" in df else None,
        average_value_added_pct=(
            float(df["value_added_pct"].mean()) if "value_added_pct" in df else None
        ),
        average_resilience_score=(
            float(df["resilience_score"].mean()) if "resilience_score" in df else None
        ),
        average_materials_dependency_ratio=(
            float(df["materials_dependency_ratio"].mean())
            if "materials_dependency_ratio" in df
            else None
        ),
        average_shock_sensitivity_index=(
            float(df["shock_sensitivity_index"].mean()) if "shock_sensitivity_index" in df else None
        ),
    )


def _aggregate_sectors(
    df: pd.DataFrame, config: HealthScoreConfig, bands: Iterable[HealthBand]
) -> list[HealthAggregate]:
    if df.empty:
        return []
    sector_keys = (
        df["industry_code"]
        .astype(str)
        .apply(lambda value: _sector_key(value, config.sector_prefix_length))
    )
    sector_df = df.assign(_sector_key=sector_keys)
    aggregates: list[HealthAggregate] = []
    for sector, group in sector_df.groupby("_sector_key", sort=True):
        aggregates.append(_aggregate(sector, group, bands=bands))
    return aggregates


def _band_breakdown(df: pd.DataFrame, bands: Iterable[HealthBand]) -> list[HealthBandBreakdown]:
    total = df.shape[0]
    if total == 0:
        return [HealthBandBreakdown(band=band.name, industries=0, percentage=0.0) for band in bands]

    counts = df["health_band"].value_counts(dropna=True)
    breakdown: list[HealthBandBreakdown] = []
    for band in bands:
        count = int(counts.get(band.name, 0))
        percentage = (count / total) * 100.0
        breakdown.append(
            HealthBandBreakdown(band=band.name, industries=count, percentage=percentage)
        )
    return breakdown


def _top_risks(df: pd.DataFrame, *, limit: int) -> list[HealthRisk]:
    if df.empty or limit <= 0:
        return []
    if "health_score" not in df:
        return []
    valid = df.dropna(subset=["health_score"])
    if valid.empty:
        return []
    sorted_df = valid.nsmallest(limit, "health_score")
    risks = []
    for row in sorted_df.itertuples(index=False):
        row_data = row._asdict()
        band_value = row_data.get("health_band")
        risks.append(
            HealthRisk(
                industry_code=str(row_data.get("industry_code", "")),
                industry_name=str(row_data.get("industry_name", "")),
                health_score=float(row_data.get("health_score", 0.0)),
                band=str(band_value) if pd.notna(band_value) else None,
            )
        )
    return risks


def _classify_series(scores: pd.Series, bands: Iterable[HealthBand]) -> pd.Series:
    """Vectorise band classification for a health score series."""

    if scores.empty:
        return pd.Series([], dtype="object", index=scores.index)
    bands_sequence = list(bands)
    assignments = pd.Series([None] * len(scores), index=scores.index, dtype="object")
    remaining = pd.Series(True, index=scores.index, dtype="bool")
    for band in bands_sequence:
        band_mask = (scores >= band.min_score) & remaining
        if not band_mask.any():
            continue
        assignments.loc[band_mask] = band.name
        remaining.loc[band_mask] = False
    assignments.loc[scores.isna()] = None
    return assignments


def _sort_bands(bands: Iterable[HealthBand]) -> tuple[HealthBand, ...]:
    """Return risk bands sorted from highest to lowest threshold."""

    return tuple(sorted(bands, key=lambda item: item.min_score, reverse=True))


def _sector_key(value: str, prefix_length: int) -> str:
    if not value:
        return "unknown"
    cleaned = value.split("-")[0].strip()
    cleaned = "".join(ch for ch in cleaned if ch.isalnum())
    if not cleaned:
        return value[:prefix_length] or "unknown"
    return cleaned[:prefix_length]


__all__ = [
    "HealthAggregate",
    "HealthBand",
    "HealthBandBreakdown",
    "HealthRisk",
    "HealthScoreConfig",
    "HealthSummary",
    "compute_health_scores",
    "summarise_health",
]
