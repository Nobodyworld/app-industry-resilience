"""BEA adapter responsible for fetching and normalising external datasets.

The adapter validates BEA response envelopes and rows before they reach pandas,
then enriches provider labels with explicit NAICS mapping status. Upstream schema
violations fail at this boundary with credential-safe :class:`BEAClientError`
messages instead of being silently coerced into missing or zero-like values.
"""

from __future__ import annotations

import concurrent.futures
import re
import time
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, cast

import pandas as pd

from ..core import (
    AppConfig,
    LineageCacheStatus,
    LineageStep,
    NormalizationOptions,
    RetryPolicy,
    SecurityUtils,
    attach_lineage,
    build_lineage,
    get_api_cache,
    lineage_from_mapping,
    lineage_to_dict,
    load_config,
    normalize_columns,
    safe_get_json,
    update_lineage_cache,
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
from ._contracts import (
    ContractValidationError,
    require_finite_number,
    require_mapping,
    require_nonempty_text,
    require_positive_year,
    require_sequence,
)

_HEADERS = {
    "Accept-Encoding": "gzip, deflate",
    "User-Agent": "industry-resilience/1.0",
}
_HEALTH_PARAMS = {
    "method": "GetParameterValues",
    "datasetname": "GDPbyIndustry",
    "ParameterName": "TableID",
    "ResultFormat": "json",
}
_BEA_REQUIRED_ROW_FIELDS: tuple[str, ...] = (
    "Industry",
    "IndustrYDescription",
    "Year",
    "DataValue",
)
_NAICS_RANGE = re.compile(r"^(\d{2})-(\d{2})$")
_NAICS_PREFIX = re.compile(r"^(\d{2})")


class BEAClientError(RuntimeError):
    """Raised when BEA data cannot be retrieved or validated."""


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
    BEATable(
        table_id="1",
        description="GDPbyIndustry Table 1",
        value_column="gross_output",
    ),
    BEATable(
        table_id="2",
        description="GDPbyIndustry Table 2",
        value_column="intermediate_inputs",
    ),
)


def fetch_go_ii_by_industry(
    api_key: str,
    year: int | Iterable[int],
    *,
    normalization: NormalizationOptions | None = None,
) -> pd.DataFrame:
    """Fetch validated output and input values for one or more years."""

    start_time = time.time()
    config = load_config()
    api_key_result = SecurityUtils.validate_api_key(api_key, "BEA")
    if not api_key_result.ok or api_key_result.value is None:
        logger.error(api_key_result.message)
        raise BEAClientError(api_key_result.message)
    api_key_clean = api_key_result.value

    years = _ensure_years(year)
    years_clean: list[int] = []
    for candidate in years:
        result = SecurityUtils.validate_year(candidate)
        if not result.ok or result.value is None:
            raise BEAClientError(result.message)
        if result.value not in config.supported_years_bea:
            raise BEAClientError(
                f"Year {result.value} is outside supported BEA range "
                f"{config.supported_years_bea.start}-"
                f"{config.supported_years_bea.stop - 1}."
            )
        years_clean.append(result.value)
    years_tuple = tuple(years_clean)

    options = normalization or NormalizationOptions()
    cache = get_api_cache(config.cache) if not options.dtype_overrides else None
    cache_key = _cache_key(years_tuple, config.bea_api_version)
    if cache:
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            log_cache_hit(cache_key, "api")
            if isinstance(cached_payload, Mapping):
                frame = pd.DataFrame(cached_payload.get("records", []))
                frame.attrs["bea_metadata"] = dict(cached_payload.get("metadata", {}))
                _attach_cached_lineage(frame, cached_payload)
            else:
                frame = pd.DataFrame(cached_payload)
            log_performance("BEA API fetch (cached)", time.time() - start_time)
            return frame
        log_cache_miss(cache_key, "api")

    base_url = select_bea_endpoint(config)
    data_frames: list[pd.DataFrame] = []
    metadata_notes: list[str] = []

    max_workers = min(len(years_tuple), 4)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
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
            except BEAClientError:
                raise
            except Exception as exc:  # pragma: no cover - defensive context
                logger.error(
                    "Failed to fetch BEA data for %s: %s",
                    year_value,
                    exc,
                )
                raise BEAClientError(
                    f"Failed to fetch BEA data for year {year_value}: {exc}"
                ) from exc
            data_frames.append(year_frame)
            metadata_notes.extend(year_meta.get("notes", []))

    if not data_frames:
        raise BEAClientError("No BEA data returned for requested years.")

    combined = pd.concat(data_frames, ignore_index=True)
    combined = _enrich_with_naics_map(combined)
    unmapped_codes = sorted(
        combined.loc[
            combined["naics_mapping_status"] == "unmapped",
            "industry_code",
        ]
        .astype(str)
        .unique()
    )
    if unmapped_codes:
        logger.warning(
            "BEA NAICS enrichment has no mapping for %d code(s): %s",
            len(unmapped_codes),
            ", ".join(unmapped_codes[:10]),
        )
        metadata_notes.append(
            "NAICS enrichment used provider-label fallback for " f"{len(unmapped_codes)} code(s)."
        )

    combined["materials_cost"] = pd.NA
    combined["value_added"] = pd.NA
    try:
        combined = normalize_columns(
            combined,
            column_aliases=options.column_aliases,
            dtype_overrides=options.dtype_overrides,
        )
    except (TypeError, ValueError) as exc:
        raise BEAClientError(f"Validated BEA data failed normalization: {exc}") from exc

    metadata = {
        "years": years_tuple,
        "endpoint": base_url,
        "tables": ["Gross Output", "Intermediate Inputs"],
        "notes": _merge_metadata_notes(metadata_notes),
        "contract_validated": True,
        "unmapped_naics_codes": unmapped_codes,
    }
    combined.attrs["bea_metadata"] = metadata
    lineage = build_lineage(
        source="bea",
        source_kind="live_provider",
        dataset_id="gdpbyindustry",
        provider="U.S. Bureau of Economic Analysis",
        observation_period=_observation_period(years_tuple),
        acquired_at=datetime.now(UTC),
        retrieval_mode="live",
        is_sample=False,
        is_official=True,
        transformations=(LineageStep(name="source_load", details={"record_count": len(combined)}),),
        cache_status=(
            LineageCacheStatus.MISS if cache is not None else LineageCacheStatus.NOT_USED
        ),
    )
    attach_lineage(combined, lineage)

    if cache:
        cache.set(
            cache_key,
            {
                "records": combined.to_dict(orient="records"),
                "metadata": metadata,
                "lineage": lineage_to_dict(lineage),
            },
        )

    log_performance("BEA API fetch", time.time() - start_time)
    log_data_processing(
        "BEA industry processing",
        records_processed=len(combined),
    )
    return combined


def _attach_cached_lineage(frame: pd.DataFrame, payload: Mapping[str, Any]) -> None:
    """Restore allowlisted BEA lineage when present in a compatible cache payload."""

    raw_lineage = payload.get("lineage")
    if not isinstance(raw_lineage, Mapping):
        return
    try:
        lineage = lineage_from_mapping(raw_lineage)
    except (KeyError, TypeError, ValueError):
        return
    attach_lineage(frame, update_lineage_cache(lineage, LineageCacheStatus.HIT))


def _observation_period(years: Sequence[int]) -> str:
    """Return a stable public period for one or more requested BEA years."""

    return str(years[0]) if len(years) == 1 else ",".join(str(year) for year in sorted(years))


def select_bea_endpoint(config: AppConfig) -> str:
    """Return the first responsive BEA endpoint, raising if none succeed."""

    errors: list[str] = []
    for base_url in config.bea_api_base_urls:
        try:
            safe_get_json(
                base_url,
                params={
                    **_HEALTH_PARAMS,
                    **({"v": config.bea_api_version} if config.bea_api_version else {}),
                },
                headers=_HEADERS,
                timeout=10.0,
            )
        except Exception as exc:  # pragma: no cover - network errors mocked
            logger.warning(
                "BEA endpoint health check failed for %s: %s",
                base_url,
                exc,
            )
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
    """Fetch both required BEA tables for ``year`` and return merged rows."""

    context = BEARequestContext(
        base_url=base_url,
        api_key=api_key,
        year=year,
        config=config,
    )
    frames: list[pd.DataFrame] = []
    notes_groups: list[list[str]] = []

    for table in BEA_TABLES:
        params = context.build_params(table)
        rows, metadata = _fetch_table(
            base_url,
            params,
            description=table.description,
        )
        frame = _process_bea_table(
            rows,
            value_column=table.value_column,
            expected_year=year,
        )
        frames.append(frame)
        notes_groups.append(list(metadata.get("notes", [])))

    if len(frames) != len(BEA_TABLES):
        raise BEAClientError(f"Incomplete BEA table set returned for year {year}.")

    go_df, ii_df = frames
    merged = go_df.merge(
        ii_df,
        on=["industry_code", "industry_name", "year"],
        how="outer",
        validate="one_to_one",
    )
    if merged.empty:
        raise BEAClientError(f"BEA returned no merged industry rows for year {year}.")
    merged["source"] = "BEA (Economy-wide)"
    return merged, {"notes": _merge_metadata_notes(*notes_groups)}


def _fetch_table(
    base_url: str,
    params: Mapping[str, str],
    *,
    description: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch a BEA table with pagination, retries, and response validation."""

    log_api_call("BEA", description, params)
    rows: list[dict[str, Any]] = []
    notes: list[str] = []
    page_params: MutableMapping[str, str] = dict(params)
    retry_policy = RetryPolicy(
        max_attempts=3,
        base_delay=1.0,
        backoff_factor=2.0,
    )

    while True:
        api_limiter.wait_for_api("bea")
        try:
            payload = safe_get_json(
                base_url,
                params=page_params,
                headers=_HEADERS,
                retry_policy=retry_policy,
            )
        except Exception as exc:  # pragma: no cover - network failures mocked
            safe_params = {key: value for key, value in page_params.items() if key != "UserID"}
            raise BEAClientError(
                f"Failed to fetch {description} with params {safe_params}: {exc}"
            ) from exc
        chunk_rows, chunk_notes, next_page = _parse_bea_response(payload)
        rows.extend(chunk_rows)
        notes.extend(chunk_notes)
        if not next_page:
            break
        page_params["Page"] = str(next_page)

    if not rows:
        raise BEAClientError(f"{description} returned no data rows.")
    return rows, {"notes": notes}


def _parse_bea_response(
    payload: object,
) -> tuple[list[dict[str, Any]], list[str], str | None]:
    """Validate and parse a BEA API response envelope."""

    try:
        root = require_mapping(payload, context="BEA API response")
        bea_api = require_mapping(
            root.get("BEAAPI"),
            context="BEAAPI envelope",
        )
        results = require_mapping(
            bea_api.get("Results"),
            context="BEA Results",
        )
    except ContractValidationError as exc:
        raise BEAClientError(str(exc)) from exc

    if "Error" in results:
        error = results["Error"]
        if isinstance(error, Mapping):
            code = error.get("APIErrorCode", "Unknown")
            description = error.get(
                "APIErrorDescription",
                "Unknown error",
            )
        else:
            code = "Unknown"
            description = str(error)
        raise BEAClientError(f"BEA API Error {code}: {description}")

    if "Data" not in results:
        raise BEAClientError("BEA Results is missing required 'Data' rows.")
    try:
        data_rows = require_sequence(
            results["Data"],
            context="BEA Results.Data",
        )
    except ContractValidationError as exc:
        raise BEAClientError(str(exc)) from exc
    if not data_rows:
        raise BEAClientError("BEA Results.Data contains no rows.")

    parsed_rows: list[dict[str, Any]] = []
    for index, item in enumerate(data_rows, start=1):
        parsed_rows.append(_validate_bea_row(item, row_index=index))

    notes: list[str] = []
    raw_notes = results.get("Notes") or []
    if isinstance(raw_notes, Sequence) and not isinstance(
        raw_notes,
        str | bytes | bytearray,
    ):
        for note in raw_notes:
            if isinstance(note, Mapping):
                text = str(note.get("Text", "")).strip()
            else:
                text = str(note).strip()
            if text:
                notes.append(text)

    next_page = None
    for key in ("NextPage", "Next", "NextTable", "NextRelease"):
        candidate = results.get(key)
        if candidate:
            next_page = str(candidate)
            break
    return parsed_rows, notes, next_page


def _validate_bea_row(
    item: object,
    *,
    row_index: int,
) -> dict[str, Any]:
    """Validate required fields on one BEA table row."""

    context = f"BEA data row {row_index}"
    try:
        row = require_mapping(item, context=context)
        missing = [field for field in _BEA_REQUIRED_ROW_FIELDS if field not in row]
        if missing:
            raise ContractValidationError(
                f"{context} is missing required fields: {', '.join(missing)}."
            )
        code = require_nonempty_text(
            row["Industry"],
            field="Industry",
            context=context,
        )
        label = require_nonempty_text(
            row["IndustrYDescription"],
            field="IndustrYDescription",
            context=context,
        )
        year = require_positive_year(
            row["Year"],
            field="Year",
            context=context,
        )
        value = require_finite_number(
            row["DataValue"],
            field="DataValue",
            context=context,
        )
    except ContractValidationError as exc:
        raise BEAClientError(str(exc)) from exc

    validated = dict(row)
    validated["Industry"] = code
    validated["IndustrYDescription"] = label
    validated["Year"] = str(year)
    validated["DataValue"] = value
    return validated


def _process_bea_table(
    data: Sequence[Mapping[str, Any]],
    value_column: str,
    *,
    expected_year: int | None = None,
) -> pd.DataFrame:
    """Convert validated BEA table rows into canonical numeric columns."""

    if not data:
        raise BEAClientError(f"BEA table for '{value_column}' contains no rows.")

    records: list[dict[str, Any]] = []
    for index, raw in enumerate(data, start=1):
        row = _validate_bea_row(raw, row_index=index)
        row_year = int(row["Year"])
        if expected_year is not None and row_year != expected_year:
            raise BEAClientError(
                f"BEA data row {index} reports year {row_year}; " f"expected {expected_year}."
            )
        records.append(
            {
                "industry_code": row["Industry"],
                "industry_name": row["IndustrYDescription"],
                "year": row_year,
                value_column: float(row["DataValue"]) * 1_000_000,
            }
        )

    frame = pd.DataFrame.from_records(records)
    if frame.duplicated(["industry_code", "industry_name", "year"]).any():
        raise BEAClientError(
            f"BEA table for '{value_column}' contains duplicate " "industry/year rows."
        )
    return frame


@lru_cache(maxsize=1)
def _load_naics_map() -> pd.DataFrame:
    """Load and validate the NAICS lookup table used to enrich BEA results."""

    mapping = pd.read_csv(
        "assets/naics_map.csv",
        dtype={"industry_code": "string"},
    )
    required = {"industry_code", "industry_name", "bea_group"}
    missing = sorted(required.difference(mapping.columns))
    if missing:
        raise BEAClientError("NAICS mapping file is missing columns: " + ", ".join(missing))
    mapping["industry_code"] = mapping["industry_code"].astype(str).str.strip()
    return mapping


def _enrich_with_naics_map(df: pd.DataFrame) -> pd.DataFrame:
    """Attach sector metadata while preserving provider labels and codes."""

    mapping_records = cast(list[Mapping[str, Any]], _load_naics_map().to_dict(orient="records"))
    enriched = df.copy()
    sector_names: list[str] = []
    bea_groups: list[str] = []
    statuses: list[str] = []

    for raw_code in enriched["industry_code"].astype(str):
        code = raw_code.strip()
        match = _find_naics_mapping(code, mapping_records)
        if match is None:
            sector_names.append(f"Unmapped NAICS {code}")
            bea_groups.append("UNMAPPED")
            statuses.append("unmapped")
        else:
            sector_names.append(str(match["industry_name"]).strip())
            bea_groups.append(str(match["bea_group"]).strip())
            statuses.append("mapped")

    enriched["naics_sector_name"] = sector_names
    enriched["bea_group"] = bea_groups
    enriched["naics_mapping_status"] = statuses
    return enriched


def _find_naics_mapping(
    industry_code: str,
    mapping_records: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """Resolve exact, two-digit, and two-digit-range map entries."""

    code = industry_code.strip()
    for record in mapping_records:
        if str(record.get("industry_code", "")).strip() == code:
            return record

    prefix_match = _NAICS_PREFIX.match(code)
    if prefix_match is None:
        return None
    prefix = int(prefix_match.group(1))

    for record in mapping_records:
        mapping_code = str(record.get("industry_code", "")).strip()
        range_match = _NAICS_RANGE.match(mapping_code)
        if range_match and (int(range_match.group(1)) <= prefix <= int(range_match.group(2))):
            return record
        if mapping_code.isdigit() and len(mapping_code) == 2 and int(mapping_code) == prefix:
            return record
    return None


def _ensure_years(year: int | Iterable[int]) -> tuple[int, ...]:
    """Normalise the ``year`` argument into a validated integer tuple."""

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
    """Return a stable cache key for a set of years and API version."""

    years_component = "_".join(str(value) for value in sorted(set(years)))
    version_component = version or "default"
    return f"bea_go_ii_{years_component}_v{version_component}"


def _merge_metadata_notes(*note_groups: Sequence[str]) -> list[str]:
    """Deduplicate and stabilise ordering of metadata notes."""

    ordered: dict[str, None] = {}
    for group in note_groups:
        for note in group:
            normalised = str(note).strip()
            if normalised:
                ordered.setdefault(normalised, None)
    return list(ordered.keys())


__all__: tuple[str, ...] = (
    "BEAClientError",
    "fetch_go_ii_by_industry",
    "select_bea_endpoint",
)
