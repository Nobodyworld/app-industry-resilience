"""Census ASM adapter responsible for fetching and normalising external datasets.

This module orchestrates requests to the Census Bureau's Annual Survey of Manufactures (ASM)
endpoint. It validates caller inputs, fetches manufacturing statistics including shipments,
cost of materials, and value added, and caches the result for reuse across requests.

Public helpers raise :class:`RuntimeError` when invalid inputs are supplied or
when Census data cannot be retrieved. All network access is wrapped in
``safe_get_json`` to ensure retries and consistent error reporting.
"""

from __future__ import annotations

import pandas as pd

from ..core import (
    DEFAULT_COLUMN_ALIASES,
    NormalizationOptions,
    SecurityUtils,
    get_api_cache,
    load_config,
    normalize_columns,
    safe_get_json,
)
from ..infrastructure import api_limiter

ASM_ENDPOINT_TEMPLATE = "https://api.census.gov/data/{year}/asm"


def _build_census_asm_endpoint(year: int) -> str:
    """Return the Census ASM endpoint for a validated year."""

    return ASM_ENDPOINT_TEMPLATE.format(year=year)


def fetch_asm_manufacturing(
    api_key: str,
    year: int,
    *,
    normalization: NormalizationOptions | None = None,
) -> pd.DataFrame:
    """Fetch manufacturing statistics for a specific year.

    Retrieves shipments (gross output), cost of materials, and value added
    from the Census Annual Survey of Manufactures for the specified year.

    Args:
        api_key: Census API key provided by the caller.
        year: Year to retrieve manufacturing data for.
        normalization: Optional normalization options to override column aliases
            or pandas dtypes.

    Returns:
        Pandas DataFrame containing Census ASM data with normalized columns.

    Raises:
        RuntimeError: If the API key or year are invalid, or if the Census API
            cannot be reached successfully after retries.
    """
    config = load_config()
    key_result = SecurityUtils.validate_api_key(api_key, "Census")
    if not key_result.ok:
        raise RuntimeError(key_result.message)

    year_result = SecurityUtils.validate_year(year)
    if not year_result.ok:
        raise RuntimeError(year_result.message)

    if year_result.value not in config.supported_years_census:
        raise RuntimeError(
            f"Year {year_result.value} is outside supported Census ASM range "
            f"{config.supported_years_census.start}-"
            f"{config.supported_years_census.stop - 1}."
        )

    options = normalization or NormalizationOptions()
    cache = get_api_cache(config.cache) if not options.dtype_overrides else None
    cache_key = f"census_asm_{year_result.value}"
    if cache:
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return pd.DataFrame(cached_result)

    params = {
        "get": "NAICS2017,NAICS2017_LABEL,RCPTOT,CSTMTOT,VALADD",
        "for": "us:*",
        "key": key_result.value,
    }

    api_limiter.wait_for_api("census")

    asm_endpoint = _build_census_asm_endpoint(year_result.value)

    data = safe_get_json(asm_endpoint, params=params)

    if not isinstance(data, list) or len(data) < 2:
        raise RuntimeError("Census ASM API returned unexpected data format.")

    header, *rows = data
    if not rows:
        raise RuntimeError(f"No Census ASM data available for {year_result.value}.")

    df = pd.DataFrame(rows, columns=header)
    merged_aliases = {**DEFAULT_COLUMN_ALIASES, **(options.column_aliases or {})}
    normalized = normalize_columns(
        df.assign(year=year_result.value, source="Census ASM"),
        column_aliases=merged_aliases,
        dtype_overrides=options.dtype_overrides,
    )
    normalized["intermediate_inputs"] = pd.NA

    if cache:
        cache.set(cache_key, normalized.to_dict("records"))

    return normalized
