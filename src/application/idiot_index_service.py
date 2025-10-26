"""Application service for orchestrating Idiot Index computations.

This module encapsulates the orchestration required to fetch datasets, normalise
columns, compute Idiot Index metrics, and derive leaderboard summaries. It sits
between domain logic (``src.core``) and presentation layers (Streamlit UI,
automation agents) so those layers can remain thin and focus on rendering or
schema concerns.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from contextlib import nullcontext
from dataclasses import dataclass, replace
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from src.core import (
    AppConfig,
    HealthSummary,
    MetricConfig,
    NormalizationOptions,
    SecurityUtils,
    apply_dtype_overrides,
    compute_health_scores,
    compute_metrics,
    format_for_display,
    load_config,
    normalize_columns,
    summarise_health,
)
from src.extensions.manager import ExtensionManager, get_extension_manager
from src.infrastructure.observability import ObservabilityRegistry, bootstrap_observability


class DataSource(str, Enum):
    """Supported data sources for Idiot Index evaluations."""

    SAMPLE = "sample"
    BEA = "bea"
    CENSUS = "census"


@dataclass(frozen=True)
class IndustryMetrics:
    """Leaderboard entry describing an industry's computed metrics."""

    industry_code: str
    industry_name: str
    idiot_index: float | None
    value_added_pct: float | None
    materials_share_pct: float | None
    gross_output: float | None
    value_added: float | None


@dataclass(frozen=True)
class IdiotIndexSummary:
    """Result returned by :func:`evaluate_idiot_index`."""

    dataframe_full: pd.DataFrame
    dataframe_filtered: pd.DataFrame
    leaderboard: tuple[IndustryMetrics, ...]
    average_idiot_index: float | None
    notes: tuple[str, ...]
    health_summary_full: HealthSummary | None = None
    health_summary_filtered: HealthSummary | None = None


@dataclass(frozen=True)
class LoggerHooks:
    """Optional logging hooks used to record orchestration metrics."""

    log_performance: Callable[[str, float], None] | None = None
    log_data_processing: Callable[[str, int], None] | None = None


@dataclass
class IdiotIndexService:
    """Coordinate Idiot Index evaluations with injectable dependencies.

    The service encapsulates the orchestration steps performed by
    :func:`evaluate_idiot_index` but allows tests or alternative entrypoints to
    override configuration loaders, dataset fetchers, and timing hooks. This
    keeps callers lightweight while preserving a single implementation of the
    orchestration pipeline.
    """

    config_loader: Callable[[], AppConfig] = load_config
    default_sample_loader: SampleLoader | None = None
    default_bea_fetcher: BEAFetcher | None = None
    default_census_fetcher: CensusFetcher | None = None
    timer: Callable[[], float] = time.perf_counter
    extension_manager: ExtensionManager | None = None
    observability: ObservabilityRegistry | None = None

    def __post_init__(self) -> None:
        if self.default_sample_loader is None:
            self.default_sample_loader = _default_sample_loader
        if self.extension_manager is None:
            self.extension_manager = get_extension_manager()
        if self.observability is None:
            self.observability = bootstrap_observability()
        if self.extension_manager is not None and self.observability is not None:
            self.extension_manager.apply_instrumentation_extensions(self.observability)

    def evaluate(
        self,
        *,
        year: int,
        source: DataSource,
        search: str | None = None,
        top_n: int = 5,
        dataframe: pd.DataFrame | None = None,
        config: AppConfig | None = None,
        fetch_bea: BEAFetcher | None = None,
        fetch_census: CensusFetcher | None = None,
        sample_loader: SampleLoader | None = None,
        logger_hooks: LoggerHooks | None = None,
        metric_config: MetricConfig | None = None,
        normalization_options: NormalizationOptions | None = None,
    ) -> IdiotIndexSummary:
        hooks = logger_hooks or LoggerHooks()
        active_config = config or self.config_loader()
        active_sample_loader = sample_loader or self.default_sample_loader or _default_sample_loader
        active_fetch_bea = fetch_bea or self.default_bea_fetcher
        active_fetch_census = fetch_census or self.default_census_fetcher

        start = self.timer()

        attributes = {"source": source.value, "year": year, "has_search": bool(search)}
        observability_cm = (
            self.observability.operation("service.idiot_index.evaluate", attributes=attributes)
            if self.observability is not None
            else nullcontext()
        )

        options = normalization_options or NormalizationOptions(
            dtype_overrides=dict(active_config.normalization_dtype_overrides)
        )

        with observability_cm:
            summary = _evaluate_idiot_index(
                year=year,
                source=source,
                search=search,
                top_n=top_n,
                dataframe=dataframe,
                config=active_config,
                fetch_bea=active_fetch_bea,
                fetch_census=active_fetch_census,
                sample_loader=active_sample_loader,
                logger_hooks=hooks,
                timer_start=start,
                timer=self.timer,
                metric_config=metric_config,
                normalization_options=options,
            )

        if self.extension_manager is not None:
            contributions = self.extension_manager.apply_summary_extensions(summary)
            if contributions.notes:
                summary = replace(summary, notes=summary.notes + contributions.notes)
            if contributions.metadata:
                for frame in (summary.dataframe_full, summary.dataframe_filtered):
                    extensions_meta = frame.attrs.setdefault("extensions", {})
                    extensions_meta.update(contributions.metadata)

        if self.observability is not None:
            dataset_attributes = _build_dataset_profile(summary, source=source, year=year)
            self.observability.record_event(
                "service.dataset.profile", attributes=dataset_attributes
            )

        return summary


class BEAFetcher(Protocol):
    """Protocol describing BEA data fetchers."""

    def __call__(
        self,
        api_key: str,
        year: int | Iterable[int],
        *,
        normalization: NormalizationOptions | None = None,
    ) -> pd.DataFrame: ...


class CensusFetcher(Protocol):
    """Protocol describing Census ASM data fetchers."""

    def __call__(
        self,
        api_key: str,
        year: int,
        *,
        normalization: NormalizationOptions | None = None,
    ) -> pd.DataFrame: ...


class SampleLoader(Protocol):
    """Protocol describing callables that load the bundled sample dataset."""

    def __call__(self) -> pd.DataFrame: ...


def sanitize_search(raw: str | None) -> str | None:
    """Return a sanitised search string safe for downstream filtering."""

    if not raw:
        return None
    cleaned = SecurityUtils.sanitize_string_input(raw)
    return cleaned or None


def evaluate_idiot_index(
    *,
    year: int,
    source: DataSource,
    search: str | None = None,
    top_n: int = 5,
    dataframe: pd.DataFrame | None = None,
    config: AppConfig | None = None,
    fetch_bea: BEAFetcher | None = None,
    fetch_census: CensusFetcher | None = None,
    sample_loader: SampleLoader | None = None,
    logger_hooks: LoggerHooks | None = None,
    metric_config: MetricConfig | None = None,
    normalization_options: NormalizationOptions | None = None,
) -> IdiotIndexSummary:
    """Return Idiot Index metrics for the requested configuration."""

    service = _DEFAULT_SERVICE
    return service.evaluate(
        year=year,
        source=source,
        search=search,
        top_n=top_n,
        dataframe=dataframe,
        config=config,
        fetch_bea=fetch_bea,
        fetch_census=fetch_census,
        sample_loader=sample_loader,
        logger_hooks=logger_hooks,
        metric_config=metric_config,
        normalization_options=normalization_options,
    )


def _evaluate_idiot_index(
    *,
    year: int,
    source: DataSource,
    search: str | None,
    top_n: int,
    dataframe: pd.DataFrame | None,
    config: AppConfig,
    fetch_bea: BEAFetcher | None,
    fetch_census: CensusFetcher | None,
    sample_loader: SampleLoader,
    logger_hooks: LoggerHooks,
    timer_start: float,
    timer: Callable[[], float],
    metric_config: MetricConfig | None,
    normalization_options: NormalizationOptions | None,
) -> IdiotIndexSummary:
    if top_n <= 0:
        raise ValueError("top_n must be greater than zero.")

    sanitized_search = sanitize_search(search)
    dataset = _resolve_dataset(
        year=year,
        source=source,
        dataframe=dataframe,
        config=config,
        fetch_bea=fetch_bea,
        fetch_census=fetch_census,
        sample_loader=sample_loader,
        normalization_options=normalization_options,
    )

    normalized = normalize_columns(
        dataset,
        column_aliases=(normalization_options.column_aliases if normalization_options else None),
        dtype_overrides=(normalization_options.dtype_overrides if normalization_options else None),
    )
    metrics = compute_metrics(normalized, config=metric_config)
    display = format_for_display(
        metrics,
        dtype_overrides=(normalization_options.dtype_overrides if normalization_options else None),
    )
    if normalization_options and normalization_options.dtype_overrides:
        apply_dtype_overrides(display, normalization_options.dtype_overrides)
    display = compute_health_scores(display)

    filtered = _filter_dataframe(display, sanitized_search)
    leaderboard = _build_leaderboard(filtered, top_n)
    notes = _extract_notes(display)
    average = float(filtered["idiot_index"].mean()) if not filtered.empty else None

    health_summary_full = summarise_health(display)
    health_summary_filtered = summarise_health(filtered)

    duration = timer() - timer_start
    if logger_hooks.log_performance is not None:
        logger_hooks.log_performance("evaluate_idiot_index", duration)
    if logger_hooks.log_data_processing is not None:
        logger_hooks.log_data_processing("idiot_index_records", len(display))

    return IdiotIndexSummary(
        dataframe_full=display,
        dataframe_filtered=filtered,
        leaderboard=leaderboard,
        average_idiot_index=average,
        notes=notes,
        health_summary_full=health_summary_full,
        health_summary_filtered=health_summary_filtered,
    )


def _resolve_dataset(
    *,
    year: int,
    source: DataSource,
    dataframe: pd.DataFrame | None,
    config: AppConfig,
    fetch_bea: BEAFetcher | None,
    fetch_census: CensusFetcher | None,
    sample_loader: SampleLoader | None,
    normalization_options: NormalizationOptions | None,
) -> pd.DataFrame:
    if dataframe is not None:
        return dataframe

    if source is DataSource.SAMPLE:
        loader = sample_loader or _default_sample_loader
        frame = loader()
        frame.attrs.setdefault("source", "sample")
        return frame

    if source is DataSource.BEA:
        if not config.bea_api_key:
            raise ValueError("BEA API key is required but missing from configuration.")
        bea_resolver = fetch_bea or _get_default_bea_fetcher()
        return bea_resolver(
            config.bea_api_key,
            year,
            normalization=normalization_options,
        )

    if source is DataSource.CENSUS:
        if not config.census_api_key:
            raise ValueError("Census API key is required but missing from configuration.")
        census_resolver = fetch_census or _get_default_census_fetcher()
        return census_resolver(
            config.census_api_key,
            year,
            normalization=normalization_options,
        )

    raise ValueError(f"Unsupported data source: {source}")


def _default_sample_loader() -> pd.DataFrame:
    path = Path("data/sample_industries.csv")
    return _read_sample_csv(path).copy()


@lru_cache(maxsize=1)
def _read_sample_csv(path: Path) -> pd.DataFrame:
    """Read and cache the bundled sample CSV for repeated use."""

    return pd.read_csv(path)


def _get_default_bea_fetcher() -> BEAFetcher:
    from src.adapters import fetch_go_ii_by_industry

    return fetch_go_ii_by_industry


def _get_default_census_fetcher() -> CensusFetcher:
    from src.adapters import fetch_asm_manufacturing

    return fetch_asm_manufacturing


def _filter_dataframe(df: pd.DataFrame, search: str | None) -> pd.DataFrame:
    if not search:
        return df.copy()
    lowered = search.lower()
    mask = df["industry_name"].str.lower().str.contains(lowered) | df[
        "industry_code"
    ].str.lower().str.contains(lowered)
    return df.loc[mask].copy()


def _build_leaderboard(df: pd.DataFrame, top_n: int) -> tuple[IndustryMetrics, ...]:
    if df.empty:
        return tuple()
    ranked = df.sort_values("idiot_index", ascending=False).head(top_n)
    entries: list[IndustryMetrics] = []
    for row in ranked.itertuples():
        entries.append(
            IndustryMetrics(
                industry_code=row.industry_code,
                industry_name=row.industry_name,
                idiot_index=float(row.idiot_index) if pd.notna(row.idiot_index) else None,
                value_added_pct=(
                    float(row.value_added_pct) if pd.notna(row.value_added_pct) else None
                ),
                materials_share_pct=(
                    float(row.materials_share_pct)
                    if hasattr(row, "materials_share_pct") and pd.notna(row.materials_share_pct)
                    else None
                ),
                gross_output=float(row.gross_output) if pd.notna(row.gross_output) else None,
                value_added=float(row.value_added) if pd.notna(row.value_added) else None,
            )
        )
    return tuple(entries)


def _frame_profile(df: pd.DataFrame) -> dict[str, Any]:
    rows = int(df.shape[0])
    columns = int(df.shape[1])
    missing_series = df.isna().sum()
    missing_cells = int(missing_series.sum())
    missing_columns = sorted(
        str(column) for column, count in missing_series.items() if int(count) > 0
    )
    total_cells = int(df.size)
    missing_ratio = float(missing_cells / total_cells) if total_cells else 0.0
    return {
        "rows": rows,
        "columns": columns,
        "missing_cells": missing_cells,
        "missing_ratio": missing_ratio,
        "missing_columns": missing_columns,
    }


def _build_dataset_profile(
    summary: IdiotIndexSummary, *, source: DataSource, year: int
) -> dict[str, Any]:
    full_profile = _frame_profile(summary.dataframe_full)
    filtered_profile = _frame_profile(summary.dataframe_filtered)
    extension_notes = summary.dataframe_filtered.attrs.get("extension_notes", [])
    health_band = None
    if summary.health_summary_filtered is not None:
        health_band = summary.health_summary_filtered.overall.risk_band
    return {
        "source": source.value,
        "year": int(year),
        "full_rows": full_profile["rows"],
        "filtered_rows": filtered_profile["rows"],
        "full_missing_cells": full_profile["missing_cells"],
        "filtered_missing_cells": filtered_profile["missing_cells"],
        "full_missing_ratio": full_profile["missing_ratio"],
        "filtered_missing_ratio": filtered_profile["missing_ratio"],
        "filtered_missing_columns": filtered_profile["missing_columns"],
        "notes": len(summary.notes),
        "extension_notes": len(extension_notes),
        "health_band": health_band,
    }


def _extract_notes(df: pd.DataFrame) -> tuple[str, ...]:
    metadata = df.attrs.get("bea_metadata") or {}
    notes = metadata.get("notes")
    if not notes:
        return tuple()
    if isinstance(notes, Sequence) and not isinstance(notes, str | bytes):
        return tuple(str(item) for item in notes)
    return (str(notes),)


__all__ = [
    "IdiotIndexService",
    "DataSource",
    "IdiotIndexSummary",
    "IndustryMetrics",
    "LoggerHooks",
    "evaluate_idiot_index",
    "sanitize_search",
]


_DEFAULT_SERVICE = IdiotIndexService()
