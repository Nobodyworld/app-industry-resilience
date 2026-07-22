"""Metric computation helpers for the Idiot Index application."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .cache import Cache, get_computation_cache
from .config import load_config
from .lineage import (
    LineageCacheStatus,
    attach_lineage,
    lineage_from_dataframe,
    lineage_from_mapping,
    lineage_to_dict,
    update_lineage_cache,
)


@dataclass(frozen=True)
class MetricConfig:
    """Configuration options for metric computation."""

    use_cache: bool = True


def compute_metrics(
    df: pd.DataFrame,
    *,
    cache: Cache | None = None,
    config: MetricConfig | None = None,
) -> pd.DataFrame:
    """Compute Idiot Index derived metrics for the provided dataframe."""

    if df.empty:
        raise ValueError("Cannot compute metrics for an empty dataframe.")

    if "gross_output" not in df.columns:
        raise ValueError("gross_output column is required but missing from data.")

    metric_config = config or MetricConfig()
    app_config = load_config()
    cache_instance: Cache | None = cache
    if metric_config.use_cache and cache_instance is None and app_config.cache.enabled:
        cache_instance = get_computation_cache(app_config.cache)

    cache_key: str | None = None
    input_lineage = lineage_from_dataframe(df)
    if metric_config.use_cache and cache_instance is not None:
        cache_key = _hash_dataframe(df)
        cached = cache_instance.get(cache_key)
        if cached is not None:
            cached_lineage = None
            if isinstance(cached, Mapping) and "records" in cached:
                cached_df = pd.DataFrame(cached.get("records", []))
                raw_lineage = cached.get("lineage")
                if isinstance(raw_lineage, Mapping):
                    try:
                        cached_lineage = lineage_from_mapping(raw_lineage)
                    except (KeyError, TypeError, ValueError):
                        cached_lineage = None
            else:
                cached_df = pd.DataFrame(cached)
            cached_df.attrs.update(df.attrs)
            lineage = cached_lineage or input_lineage
            if lineage is not None:
                attach_lineage(
                    cached_df,
                    update_lineage_cache(lineage, LineageCacheStatus.HIT),
                )
            return cached_df

    work = df.copy()

    materials = work.get("materials_cost")
    intermediates = work.get("intermediate_inputs")
    if materials is None:
        materials = pd.Series([float("nan")] * len(work), dtype="float64")
    if intermediates is None:
        intermediates = pd.Series([float("nan")] * len(work), dtype="float64")

    denominator = materials.where(materials.notna(), intermediates)
    denominator = denominator.astype("float64")
    # Use numpy NaN for missing denominators instead of `pd.NA` which can
    # cause object dtype downcasting when combined with other operations.
    denominator.replace({0.0: float("nan")}, inplace=True)

    work["idiot_index"] = (work["gross_output"].astype("float64") / denominator).replace(
        [float("inf"), float("-inf")], pd.NA
    )

    # Fill missing denominators with zeros for downstream calculations.
    fallback_inputs = denominator.fillna(0.0)
    if "value_added" not in work.columns:
        work["value_added"] = work["gross_output"].astype("float64") - fallback_inputs
    else:
        work["value_added"] = (
            work["value_added"]
            .astype("float64")
            .where(
                work["value_added"].notna(),
                work["gross_output"].astype("float64") - fallback_inputs,
            )
        )

    gross_output = work["gross_output"].astype("float64")

    work["value_added_pct"] = (work["value_added"].astype("float64") / gross_output) * 100.0
    work["materials_share_pct"] = (fallback_inputs / gross_output) * 100.0

    # Derived resilience metrics guard against divide-by-zero behaviour by
    # explicitly masking invalid denominators. We use explicit replacements
    # instead of `mode.use_inf_as_na` to avoid future pandas deprecation.
    denominator_resilience = fallback_inputs.where(fallback_inputs > 0)
    work["resilience_score"] = work["value_added"].astype("float64") / denominator_resilience

    work["materials_dependency_ratio"] = fallback_inputs / gross_output

    total_cost_basis = work["value_added"].astype("float64") + fallback_inputs
    shock_series = pd.Series(float("nan"), index=work.index, dtype="float64")
    valid_shock = total_cost_basis > 0
    shock_series.loc[valid_shock] = (
        fallback_inputs.loc[valid_shock] / total_cost_basis.loc[valid_shock]
    )
    work["shock_sensitivity_index"] = shock_series

    # Normalise any remaining infinities to NA given pandas deprecation warnings
    work = work.replace([float("inf"), float("-inf")], pd.NA)

    work.attrs.update(df.attrs)
    output_lineage = input_lineage
    if output_lineage is not None and cache_instance is not None and cache_key is not None:
        output_lineage = update_lineage_cache(output_lineage, LineageCacheStatus.MISS)
        attach_lineage(work, output_lineage)

    if metric_config.use_cache and cache_instance is not None and cache_key is not None:
        payload: dict[str, Any] = {"records": work.to_dict(orient="records")}
        if output_lineage is not None:
            payload["lineage"] = lineage_to_dict(output_lineage)
        cache_instance.set(cache_key, payload)

    return work


def format_for_display(
    df: pd.DataFrame, *, dtype_overrides: Mapping[str, Any] | None = None
) -> pd.DataFrame:
    """Ensure numeric columns are cast to floats for UI presentation."""

    formatted = df.copy()
    preserved = {key.strip().lower() for key in (dtype_overrides or {})}
    numeric_columns = {
        "gross_output",
        "materials_cost",
        "intermediate_inputs",
        "value_added",
        "idiot_index",
        "value_added_pct",
        "materials_share_pct",
        "resilience_score",
        "materials_dependency_ratio",
        "shock_sensitivity_index",
    }
    for column in numeric_columns.intersection(formatted.columns):
        if column in preserved:
            continue
        formatted[column] = pd.to_numeric(formatted[column], errors="coerce").astype("float64")
    return formatted


def _hash_dataframe(df: pd.DataFrame) -> str:
    import hashlib

    records = df.to_dict(orient="records")
    lineage = lineage_from_dataframe(df)
    if lineage is None:
        payload_value: Any = records
    else:
        cache_identity = lineage_to_dict(lineage)
        cache_identity.pop("cache_status", None)
        cache_identity.pop("retrieval_mode", None)
        payload_value = {"records": records, "lineage": cache_identity}
    payload = json.dumps(payload_value, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["MetricConfig", "compute_metrics", "format_for_display"]
