from pathlib import Path

import pandas as pd

from src.core import compute_metrics, normalize_columns
from src.core.cache import Cache


def _sample_frame() -> pd.DataFrame:
    # Create a straightforward dataset with gross_output and materials_cost
    return pd.DataFrame(
        [
            {
                "industry_code": "311",
                "industry_name": "Food",
                "year": 2020,
                "gross_output": 100.0,
                "materials_cost": 60.0,
            },
            {
                "industry_code": "312",
                "industry_name": "Beverage",
                "year": 2020,
                "gross_output": 200.0,
                "materials_cost": 120.0,
            },
        ]
    )


def test_pipeline_compute_metrics_simple() -> None:
    df = _sample_frame()
    normalized = normalize_columns(df)
    metrics = compute_metrics(normalized, config=None, cache=None)

    # Asserting important derived columns exist and are float-typed
    assert "idiot_index" in metrics.columns
    assert pd.api.types.is_float_dtype(metrics["idiot_index"])
    assert metrics.loc[0, "idiot_index"] == 100.0 / 60.0
    assert metrics.loc[1, "idiot_index"] == 200.0 / 120.0


def test_compute_metrics_caches_results(tmp_path: Path) -> None:
    df = _sample_frame()
    normalized = normalize_columns(df)

    cache_dir = tmp_path / "computation_cache"
    cache = Cache(cache_dir, ttl_seconds=60)

    # First computation writes to cache
    results = compute_metrics(normalized, cache=cache, config=None)
    stats = cache.stats()
    assert stats.files == 1

    # Second computation should be a cache hit; file count remains constant
    results2 = compute_metrics(normalized, cache=cache, config=None)
    stats2 = cache.stats()
    assert stats2.files == 1
    assert results.equals(results2)
