"""BEA adapter responsible for fetching and normalising external datasets.

This module orchestrates requests to the Bureau of Economic Analysis (BEA)
GDP-by-industry endpoints. It validates caller inputs, selects a healthy API
endpoint, downloads the Gross Output and Intermediate Inputs tables, enriches
them with NAICS metadata, and caches the result for reuse across requests.

Public helpers raise :class:`BEAClientError` when invalid inputs are supplied or
when BEA data cannot be retrieved. All network access is wrapped in
``safe_get_json`` to ensure retries and consistent error reporting.
"""

from __future__ import annotations

import concurrent.futures
import time
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import pandas as pd

from ..core import (
    AppConfig,
    RetryPolicy,
    SecurityUtils,
    get_api_cache,
    load_config,
    normalize_columns,
    safe_get_json,
)
from ..infrastructure import (
    api_limiter,
    log_api_call,
    log_cache_hit,
    log_cache_miss,
    log_data_processing,
    log_performance,
    logger,
)

_HEADERS = {"Accept-Encoding": "gzip, deflate", "User-Agent": "idiot-index/1.0"}
_HEALTH_PARAMS = {
    "method": "GetParameterValues",
    "datasetname": "GDPbyIndustry",
    "ParameterName": "TableID",
    "ResultFormat": "json",
}


class BEAClientError(RuntimeError):
    """Raised when BEA data cannot be retrieved after retries or validation."""


@dataclass(frozen=True)
class BEATable:
    """Representation of a BEA table to fetch for a given year."""

    table_id: str
    description: str
    value_column: str


@dataclass(frozen=True)
class BEARequestContext:
    """Context for building BEA requests for a specific year."""

    base_url: str
    api_key: str
    year: int
    config: AppConfig

    def build_params(self, table: BEATable) -> dict[str, str]:
        """Return BEA request parameters for ``table`` and ``self.year``."""

        params = {
            "UserID": self.api_key,
            "method": "GetData",
            "datasetname": "GDPbyIndustry",
            "Frequency": "A",
            "Industry": "ALL",
            "Year": str(self.year),
            "TableID": table.table_id,
            "ResultFormat": "json",
        }
        if self.config.bea_api_version:
            params["v"] = self.config.bea_api_version
        return params


BEA_TABLES: tuple[BEATable, ...] = (
    BEATable(table_id="1", description="GDPbyIndustry Table 1", value_column="gross_output"),
    BEATable(table_id="2", description="GDPbyIndustry Table 2", value_column="intermediate_inputs"),
)


def fetch_go_ii_by_industry(api_key: str, year: int | Iterable[int]) -> pd.DataFrame:
    """Fetch Gross Output and Intermediate Inputs for one or more years.

    Args:
        api_key: BEA API key provided by the caller.
        year: Single year or iterable of years to retrieve.

    Returns:
        Pandas DataFrame containing merged BEA tables enriched with NAICS data.

    Raises:
        BEAClientError: If the API key or years are invalid, or if the BEA API
            cannot be reached successfully after retries.
    """

    start_time = time.time()
    config = load_config()
    api_key_result = SecurityUtils.validate_api_key(api_key, "BEA")
    if not api_key_result.ok or api_key_result.value is None:
        logger.error(api_key_result.message)
        raise BEAClientError(api_key_result.message)
    api_key_clean = api_key_result.value

    years = _ensure_years(year)
    year_validation = [SecurityUtils.validate_year(item) for item in years]
    years_clean: list[int] = []
    for result in year_validation:
        if not result.ok or result.value is None:
            raise BEAClientError(result.message)
        if result.value not in config.supported_years_bea:
            raise BEAClientError(
                f"Year {result.value} is outside supported BEA range {config.supported_years_bea.start}-{config.supported_years_bea.stop - 1}."
            )
        years_clean.append(result.value)

    years_tuple = tuple(years_clean)

    cache = get_api_cache(config.cache)
    cache_key = _cache_key(years_tuple, config.bea_api_version)
    if cache:
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            log_cache_hit(cache_key, "api")
            frame = pd.DataFrame(cached_payload["records"])
            frame.attrs["bea_metadata"] = cached_payload.get("metadata", {})
            log_performance("BEA API fetch (cached)", time.time() - start_time)
            return frame
        log_cache_miss(cache_key, "api")

    base_url = select_bea_endpoint(config)

    data_frames: list[pd.DataFrame] = []
    metadata_notes: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(years_tuple), 4)) as executor:
        futures = {
            executor.submit(
                _fetch_year_bundle,
                base_url,
                api_key_clean,
                year_value,
                config,
            ): year_value
            for year_value in years_tuple
        }
        for future in concurrent.futures.as_completed(futures):
            year_value = futures[future]
            try:
                year_frame, year_meta = future.result()
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Failed to fetch BEA data for %s: %s", year_value, exc, exc_info=exc)
                raise BEAClientError(f"Failed to fetch BEA data for {year_value}: {exc}") from exc
            else:
                data_frames.append(year_frame)
                metadata_notes.extend(year_meta.get("notes", []))

    if not data_frames:
        raise BEAClientError("No BEA data returned for requested years.")

    combined = pd.concat(data_frames, ignore_index=True)
    combined = _enrich_with_naics_map(combined)
    combined = normalize_columns(combined)
    combined["materials_cost"] = pd.NA
    combined["value_added"] = pd.NA

    combined.attrs["bea_metadata"] = {
        "years": years_tuple,
        "endpoint": base_url,
        "tables": ["Gross Output", "Intermediate Inputs"],
        "notes": _merge_metadata_notes(metadata_notes),
    }

    if cache:
        cache.set(
            cache_key,
            {
                "records": combined.to_dict(orient="records"),
                "metadata": combined.attrs["bea_metadata"],
            },
        )

    log_performance("BEA API fetch", time.time() - start_time)
    log_data_processing(
        "BEA industry processing",
        records_processed=len(combined),
    )
    return combined


def select_bea_endpoint(config: AppConfig) -> str:
    """Return the first healthy BEA endpoint, raising if none succeed.

    Args:
        config: Application configuration containing the ordered list of BEA
            base URLs to test.

    Returns:
        Base URL for the first endpoint that responds successfully.

    Raises:
        BEAClientError: If no configured endpoints respond successfully.
    """

    errors: list[str] = []
    for base_url in config.bea_api_base_urls:
        try:
            _ = safe_get_json(
                base_url,
                params={
                    **_HEALTH_PARAMS,
                    **({"v": config.bea_api_version} if config.bea_api_version else {}),
                },
                headers=_HEADERS,
                timeout=10.0,
            )
        except Exception as exc:  # pragma: no cover - network errors mocked in tests
            logger.warning("BEA endpoint health check failed for %s: %s", base_url, exc)
            errors.append(f"{base_url}: {exc}")
            continue
        logger.debug("BEA endpoint healthy: %s", base_url)
        return base_url
    raise BEAClientError("All BEA endpoints failed health check: " + "; ".join(errors))


def _fetch_year_bundle(
    base_url: str,
    api_key: str,
    year: int,
    config: AppConfig,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fetch both BEA tables for ``year`` and return merged results.

    Args:
        base_url: Healthy BEA endpoint URL.
        api_key: Sanitised BEA API key.
        year: Year to fetch.
        config: Application configuration supplying version metadata.

    Returns:
        Tuple containing the merged DataFrame and metadata dictionary.

    Raises:
        BEAClientError: If either table cannot be retrieved.
    """

    context = BEARequestContext(base_url=base_url, api_key=api_key, year=year, config=config)

    frames: list[pd.DataFrame] = []
    notes_groups: list[list[str]] = []

    for table in BEA_TABLES:
        params = context.build_params(table)
        rows, metadata = _fetch_table(base_url, params, description=table.description)
        frame = _process_bea_table(rows, value_column=table.value_column)
        frames.append(frame)
        notes_groups.append(list(metadata.get("notes", [])))

    if len(frames) != len(BEA_TABLES):
        raise BEAClientError("Incomplete BEA data returned for requested year.")

    go_df, ii_df = frames
    merged = go_df.merge(
        ii_df,
        on=["industry_code", "industry_name", "year"],
        how="outer",
    )
    merged["source"] = "BEA (Economy-wide)"
    metadata = {"notes": _merge_metadata_notes(*notes_groups)}
    return merged, metadata


def _fetch_table(
    base_url: str,
    params: Mapping[str, str],
    *,
    description: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch a table from BEA handling pagination and retries.

    Args:
        base_url: Endpoint used for the request.
        params: Request parameters constructed for the table.
        description: Human readable table description for logging.

    Returns:
        Tuple of row dictionaries and metadata including accumulated notes.

    Raises:
        BEAClientError: When the request fails even after retries.
    """

    log_api_call("BEA", description, params)

    rows: list[dict[str, Any]] = []
    notes: list[str] = []
    page_params: MutableMapping[str, str] = dict(params)
    retry_policy = RetryPolicy(max_attempts=3, base_delay=1.0, backoff_factor=2.0)

    while True:
        api_limiter.wait_for_api("bea")
        try:
            payload = safe_get_json(
                base_url,
                params=page_params,
                headers=_HEADERS,
                retry_policy=retry_policy,
            )
        except Exception as exc:  # pragma: no cover - network exceptions mocked in tests
            raise BEAClientError(
                f"Failed to fetch BEA data for params {page_params}: {exc}"
            ) from exc
        chunk_rows, chunk_notes, next_page = _parse_bea_response(payload)
        rows.extend(chunk_rows)
        notes.extend(chunk_notes)
        if not next_page:
            break
        page_params["Page"] = str(next_page)

    return rows, {"notes": notes}


def _parse_bea_response(
    payload: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str], str | None]:
    """Parse a BEA API payload returning rows, notes, and next page token.

    Args:
        payload: Raw JSON payload returned by ``safe_get_json``.

    Returns:
        Tuple containing parsed row dictionaries, textual notes, and an
        optional pagination token.

    Raises:
        BEAClientError: When the payload reports an API error or has an
            unexpected structure.
    """

    if not payload or "BEAAPI" not in payload:
        raise BEAClientError("Unexpected BEA API response structure")

    results = payload["BEAAPI"].get("Results", {})
    if "Error" in results:
        error = results["Error"]
        raise BEAClientError(
            "BEA API Error {code}: {desc}".format(
                code=error.get("APIErrorCode", "Unknown"),
                desc=error.get("APIErrorDescription", "Unknown error"),
            )
        )

    data_rows = results.get("Data", [])
    notes = []
    raw_notes = results.get("Notes") or []
    for note in raw_notes:
        if isinstance(note, dict):
            notes.append(note.get("Text", ""))
        else:
            notes.append(str(note))

    next_page = None
    for key in ("NextPage", "Next", "NextTable", "NextRelease"):
        candidate = results.get(key)
        if candidate:
            next_page = str(candidate)
            break

    parsed_rows: list[dict[str, Any]] = []
    for item in data_rows:
        parsed_rows.append(dict(item))
    return parsed_rows, notes, next_page


def _process_bea_table(data: Sequence[Mapping[str, Any]], value_column: str) -> pd.DataFrame:
    """Convert BEA table rows into a DataFrame with numeric values.

    Args:
        data: Sequence of row mappings returned by the BEA API.
        value_column: Name of the numeric column to populate.

    Returns:
        DataFrame with standardised columns for downstream processing.
    """

    if not data:
        return pd.DataFrame(columns=["industry_code", "industry_name", "year", value_column])

    frame = pd.DataFrame(list(data)).rename(
        columns={"Industry": "industry_code", "IndustrYDescription": "industry_name"}
    )

    if "industry_code" not in frame:
        frame["industry_code"] = ""
    frame["industry_code"] = frame["industry_code"].astype(str)

    if "industry_name" not in frame:
        frame["industry_name"] = frame["industry_code"]
    else:
        frame["industry_name"] = frame["industry_name"].fillna(frame["industry_code"])

    value_series = frame.get("DataValue", pd.Series(index=frame.index, dtype="object")).astype(str)
    value_series = value_series.str.replace(",", "", regex=False)
    frame[value_column] = pd.to_numeric(value_series, errors="coerce") * 1_000_000

    year_series = pd.to_numeric(frame.get("Year", 0), errors="coerce").fillna(0).astype(int)
    frame["year"] = year_series

    return frame.loc[:, ["industry_code", "industry_name", "year", value_column]]


@lru_cache(maxsize=1)
def _load_naics_map() -> pd.DataFrame:
    """Load the NAICS lookup table used to enrich BEA results.

    Returns:
        DataFrame containing NAICS codes and friendly names.
    """

    return pd.read_csv("assets/naics_map.csv")


def _enrich_with_naics_map(df: pd.DataFrame) -> pd.DataFrame:
    """Merge NAICS metadata, preferring provided names when available.

    Args:
        df: DataFrame produced from BEA data.

    Returns:
        DataFrame enriched with NAICS names.
    """

    mapping = _load_naics_map()
    merged = df.merge(mapping, on="industry_code", how="left", suffixes=("", "_mapped"))
    if "industry_name_mapped" in merged.columns:
        merged["industry_name"] = merged["industry_name"].fillna(merged["industry_name_mapped"])
        merged.drop(columns=["industry_name_mapped"], inplace=True)
    return merged


def _ensure_years(year: int | Iterable[int]) -> tuple[int, ...]:
    """Normalise the ``year`` argument into a validated tuple of integers.

    Args:
        year: Single year or iterable of candidate years.

    Returns:
        Sorted tuple of validated years.

    Raises:
        BEAClientError: If values are missing, duplicated, or invalid.
    """

    years: tuple[int, ...]
    if isinstance(year, int):
        years = (year,)
    else:
        try:
            years = tuple(int(value) for value in year)
        except (TypeError, ValueError) as exc:
            raise BEAClientError(f"Invalid BEA year value: {year}") from exc

    if not years:
        raise BEAClientError("At least one year must be provided for BEA fetch.")

    if any(item <= 0 for item in years):
        raise BEAClientError("Years must be positive integers for BEA fetch.")

    if len(set(years)) != len(years):
        raise BEAClientError("Duplicate years are not allowed in BEA fetch.")

    return tuple(sorted(years))


def _cache_key(years: Sequence[int], version: str | None) -> str:
    """Return a stable cache key for a set of years and API version.

    Args:
        years: Iterable of year integers.
        version: Optional BEA API version string.

    Returns:
        Cache key combining the year set and version.
    """

    years_component = "_".join(str(y) for y in sorted(set(years)))
    version_component = version or "default"
    return f"bea_go_ii_{years_component}_v{version_component}"


def _merge_metadata_notes(*note_groups: Sequence[str]) -> list[str]:
    """Deduplicate and stabilise ordering of metadata notes.

    Args:
        *note_groups: Iterables of note strings captured during fetches.

    Returns:
        Deterministically ordered list of unique note strings.
    """

    ordered: dict[str, None] = {}
    for group in note_groups:
        for note in group:
            normalised = str(note).strip()
            if not normalised:
                continue
            ordered.setdefault(normalised, None)
    return list(ordered.keys())


__all__: tuple[str, ...] = ("BEAClientError", "fetch_go_ii_by_industry", "select_bea_endpoint")
