from __future__ import annotations

import concurrent.futures
import time
from collections import defaultdict
from functools import lru_cache
from typing import Any, Iterable, Sequence

import pandas as pd

from ..cache import get_api_cache
from ..config import AppConfig, load_config
from ..logging_config import (
    log_api_call,
    log_cache_hit,
    log_cache_miss,
    log_data_processing,
    log_performance,
    logger,
)
from ..normalize import normalize_columns
from ..rate_limiter import api_limiter
from ..security import SecurityUtils
from ..utils import RetryPolicy, safe_get_json

_HEADERS = {"Accept-Encoding": "gzip, deflate", "User-Agent": "idiot-index/1.0"}
_HEALTH_PARAMS = {
    "method": "GetParameterValues",
    "datasetname": "GDPbyIndustry",
    "ParameterName": "TableID",
    "ResultFormat": "json",
}


class BEAClientError(RuntimeError):
    """Raised when BEA data cannot be retrieved after retries."""


def fetch_go_ii_by_industry(api_key: str, year: int | Iterable[int]) -> pd.DataFrame:
    """Fetch Gross Output and Intermediate Inputs for one or more years."""

    start_time = time.time()
    config = load_config()
    api_key_result = SecurityUtils.validate_api_key(api_key, "BEA")
    if not api_key_result.ok:
        logger.error(api_key_result.message)
        raise BEAClientError(api_key_result.message)

    years = _ensure_years(year)
    year_validation = [SecurityUtils.validate_year(item) for item in years]
    for result in year_validation:
        if not result.ok:
            raise BEAClientError(result.message)
        if result.value not in config.supported_years_bea:
            raise BEAClientError(
                "Year {year} is outside supported BEA range {start}-{end}.".format(
                    year=result.value,
                    start=config.supported_years_bea.start,
                    end=config.supported_years_bea.stop - 1,
                )
            )

    years_clean = tuple(result.value for result in year_validation)

    cache = get_api_cache(config.cache)
    cache_key = _cache_key(years_clean, config.bea_api_version)
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
    metadata_aggregate: dict[str, Any] = defaultdict(list)

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(years_clean), 4)) as executor:
        futures = {
            executor.submit(
                _fetch_year_bundle,
                base_url,
                api_key_result.value,
                year_value,
                config,
            ): year_value
            for year_value in years_clean
        }
        for future in concurrent.futures.as_completed(futures):
            year_value = futures[future]
            try:
                year_frame, year_meta = future.result()
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Failed to fetch BEA data for %s: %s", year_value, exc)
                raise
            else:
                data_frames.append(year_frame)
                for key, value in year_meta.items():
                    if isinstance(value, list):
                        metadata_aggregate[key].extend(value)
                    else:
                        metadata_aggregate[key].append(value)

    if not data_frames:
        raise BEAClientError("No BEA data returned for requested years.")

    combined = pd.concat(data_frames, ignore_index=True)
    combined = _enrich_with_naics_map(combined)
    combined = normalize_columns(combined)
    combined["materials_cost"] = pd.NA
    combined["value_added"] = pd.NA

    combined.attrs["bea_metadata"] = {
        "years": years_clean,
        "endpoint": base_url,
        "tables": ["Gross Output", "Intermediate Inputs"],
        "notes": metadata_aggregate.get("notes", []),
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
    """Return the first healthy BEA endpoint, raising if none succeed."""

    errors: list[str] = []
    for base_url in config.bea_api_base_urls:
        try:
            _ = safe_get_json(
                base_url,
                params={**_HEALTH_PARAMS, **({"v": config.bea_api_version} if config.bea_api_version else {})},
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
    params_common = {
        "UserID": api_key,
        "method": "GetData",
        "datasetname": "GDPbyIndustry",
        "Frequency": "A",
        "Industry": "ALL",
        "Year": str(year),
        "ResultFormat": "json",
    }
    if config.bea_api_version:
        params_common["v"] = config.bea_api_version

    go_rows, go_meta = _fetch_table(
        base_url,
        {**params_common, "TableID": "1"},
        description="GDPbyIndustry Table 1",
    )
    ii_rows, ii_meta = _fetch_table(
        base_url,
        {**params_common, "TableID": "2"},
        description="GDPbyIndustry Table 2",
    )

    go_df = _process_bea_table(go_rows, "gross_output")
    ii_df = _process_bea_table(ii_rows, "intermediate_inputs")
    merged = pd.merge(
        go_df,
        ii_df,
        on=["industry_code", "industry_name", "year"],
        how="outer",
    )
    merged["source"] = "BEA (Economy-wide)"
    metadata = {"notes": go_meta.get("notes", []) + ii_meta.get("notes", [])}
    return merged, metadata


def _fetch_table(
    base_url: str,
    params: dict[str, str],
    *,
    description: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch a table from BEA handling pagination and retries."""

    log_api_call("BEA", description, params)

    rows: list[dict[str, Any]] = []
    notes: list[str] = []
    page_params = dict(params)
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
            raise BEAClientError(f"Failed to fetch BEA data for params {page_params}: {exc}") from exc
        chunk_rows, chunk_notes, next_page = _parse_bea_response(payload)
        rows.extend(chunk_rows)
        notes.extend(chunk_notes)
        if not next_page:
            break
        page_params["Page"] = str(next_page)

    return rows, {"notes": notes}


def _parse_bea_response(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], str | None]:
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


def _process_bea_table(data: Sequence[dict[str, Any]], value_column: str) -> pd.DataFrame:
    rows = []
    for item in data:
        value_raw = str(item.get("DataValue", "0"))
        try:
            value = float(value_raw.replace(",", "")) * 1_000_000
        except ValueError:
            value = None
        try:
            year_int = int(item.get("Year", 0))
        except (TypeError, ValueError):
            year_int = 0
        rows.append(
            {
                "industry_code": item.get("Industry", ""),
                "industry_name": item.get("IndustrYDescription", item.get("Industry", "")),
                "year": year_int,
                value_column: value,
            }
        )
    return pd.DataFrame(rows)


@lru_cache(maxsize=1)
def _load_naics_map() -> pd.DataFrame:
    return pd.read_csv("assets/naics_map.csv")


def _enrich_with_naics_map(df: pd.DataFrame) -> pd.DataFrame:
    mapping = _load_naics_map()
    merged = df.merge(mapping, on="industry_code", how="left", suffixes=("", "_mapped"))
    if "industry_name_mapped" in merged.columns:
        merged["industry_name"] = merged["industry_name"].fillna(merged["industry_name_mapped"])
        merged.drop(columns=["industry_name_mapped"], inplace=True)
    return merged


def _ensure_years(year: int | Iterable[int]) -> tuple[int, ...]:
    if isinstance(year, int):
        return (year,)
    years = tuple(int(value) for value in year)
    if not years:
        raise BEAClientError("At least one year must be provided for BEA fetch.")
    return years


def _cache_key(years: Sequence[int], version: str | None) -> str:
    years_component = "_".join(str(y) for y in sorted(set(years)))
    version_component = version or "default"
    return f"bea_go_ii_{years_component}_v{version_component}"


__all__ = ["BEAClientError", "fetch_go_ii_by_industry", "select_bea_endpoint"]
