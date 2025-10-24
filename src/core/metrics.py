"""Metric computation helpers for the Idiot Index application."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd

from .cache import Cache, get_computation_cache
from .config import load_config


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
    if cache_instance is None and app_config.cache.enabled:
        cache_instance = get_computation_cache(app_config.cache)

    cache_key: str | None = None
    if metric_config.use_cache and cache_instance is not None:
        cache_key = _hash_dataframe(df)
        cached = cache_instance.get(cache_key)
        if cached is not None:
            cached_df = pd.DataFrame(cached)
            cached_df.attrs.update(df.attrs)
            return cached_df

    work = df.copy()

    materials = work.get("materials_cost")
    intermediates = work.get("intermediate_inputs")
    if materials is None:
        materials = pd.Series([pd.NA] * len(work), dtype="float64")
    if intermediates is None:
        intermediates = pd.Series([pd.NA] * len(work), dtype="float64")

    denominator = materials.where(materials.notna(), intermediates)
    denominator = denominator.astype("float64")
    denominator.replace({0.0: pd.NA}, inplace=True)

    work["idiot_index"] = (
        work["gross_output"].astype("float64") / denominator
    ).replace([float("inf"), float("-inf")], pd.NA)

    fallback_inputs = denominator.fillna(0.0)
    if "value_added" not in work.columns:
        work["value_added"] = work["gross_output"].astype("float64") - fallback_inputs
    else:
        work["value_added"] = work["value_added"].astype("float64").where(
            work["value_added"].notna(),
            work["gross_output"].astype("float64") - fallback_inputs,
        )

    work["value_added_pct"] = (
        work["value_added"].astype("float64") / work["gross_output"].astype("float64")
    ) * 100.0
    work["materials_share_pct"] = (
        fallback_inputs / work["gross_output"].astype("float64")
    ) * 100.0

    work = work.replace([float("inf"), float("-inf")], pd.NA)

    if (
        metric_config.use_cache
        and cache_instance is not None
        and cache_key is not None
    ):
        cache_instance.set(cache_key, work.to_dict(orient="records"))

    work.attrs.update(df.attrs)
    return work


def format_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure numeric columns are cast to floats for UI presentation."""

    formatted = df.copy()
    numeric_columns = {
        "gross_output",
        "materials_cost",
        "intermediate_inputs",
        "value_added",
        "idiot_index",
        "value_added_pct",
        "materials_share_pct",
    }
    for column in numeric_columns.intersection(formatted.columns):
        formatted[column] = pd.to_numeric(formatted[column], errors="coerce").astype(
            "float64"
        )
    return formatted


def _hash_dataframe(df: pd.DataFrame) -> str:
    import hashlib

    payload = json.dumps(df.to_dict(orient="records"), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["MetricConfig", "compute_metrics", "format_for_display"]

