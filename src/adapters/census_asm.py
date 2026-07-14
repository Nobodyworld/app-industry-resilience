"""Census ASM adapter responsible for fetching and normalising external datasets.

This module validates caller inputs and the Census Bureau Annual Survey of
Manufactures response contract before normalisation. Malformed upstream
responses fail at the adapter boundary with contextual, credential-safe errors.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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
from ._contracts import (
    ContractValidationError,
    require_finite_number,
    require_nonempty_text,
    require_sequence,
)

ASM_ENDPOINT_TEMPLATE = "https://api.census.gov/data/{year}/asm"
_REQUIRED_FIELDS: tuple[str, ...] = (
    "NAICS2017",
    "NAICS2017_LABEL",
    "RCPTOT",
    "CSTMTOT",
    "VALADD",
)
_NUMERIC_FIELDS: tuple[str, ...] = ("RCPTOT", "CSTMTOT", "VALADD")


class CensusASMClientError(RuntimeError):
    """Raised when Census ASM input or response validation fails."""


def _build_census_asm_endpoint(year: int) -> str:
    """Return the Census ASM endpoint for a validated year."""

    return ASM_ENDPOINT_TEMPLATE.format(year=year)


def fetch_asm_manufacturing(
    api_key: str,
    year: int,
    *,
    normalization: NormalizationOptions | None = None,
) -> pd.DataFrame:
    """Fetch and validate manufacturing statistics for a specific year.

    The adapter requires Census ASM rows to include an industry code, provider
    label, shipments, cost of materials, and value added. Invalid envelopes,
    headers, row widths, or numeric values raise :class:`CensusASMClientError`
    before a dataframe reaches downstream calculations.
    """

    config = load_config()
    key_result = SecurityUtils.validate_api_key(api_key, "Census")
    if not key_result.ok or key_result.value is None:
        raise CensusASMClientError(key_result.message)

    year_result = SecurityUtils.validate_year(year)
    if not year_result.ok or year_result.value is None:
        raise CensusASMClientError(year_result.message)

    if year_result.value not in config.supported_years_census:
        raise CensusASMClientError(
            f"Year {year_result.value} is outside supported Census ASM range "
            f"{config.supported_years_census.start}-{config.supported_years_census.stop - 1}."
        )

    options = normalization or NormalizationOptions()
    cache = get_api_cache(config.cache) if not options.dtype_overrides else None
    year_value = int(year_result.value)
    cache_key = f"census_asm_{year_value}"
    if cache:
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            if isinstance(cached_result, Mapping):
                frame = pd.DataFrame(cached_result.get("records", []))
                frame.attrs["census_asm_metadata"] = dict(cached_result.get("metadata", {}))
                return frame
            return pd.DataFrame(cached_result)

    params = {
        "get": ",".join(_REQUIRED_FIELDS),
        "for": "us:*",
        "key": key_result.value,
    }

    api_limiter.wait_for_api("census")
    asm_endpoint = _build_census_asm_endpoint(year_value)
    candidate_template = getattr(config, "census_asm_endpoint_template", None)
    if candidate_template:
        try:
            asm_endpoint = candidate_template.format(year=year_value)
        except KeyError as exc:  # pragma: no cover - guarded by config validation
            raise CensusASMClientError(
                "Census ASM endpoint template is misconfigured; expected '{year}' placeholder."
            ) from exc

    try:
        payload = safe_get_json(asm_endpoint, params=params)
    except Exception as exc:  # pragma: no cover - network failures are mocked in tests
        raise CensusASMClientError(
            f"Failed to fetch Census ASM data for year {year_value}: {exc}"
        ) from exc

    header, rows = _validate_census_payload(payload, year=year_value)
    frame = pd.DataFrame(rows, columns=header)
    merged_aliases = {**DEFAULT_COLUMN_ALIASES, **(options.column_aliases or {})}
    try:
        normalized = normalize_columns(
            frame.assign(year=year_value, source="Census ASM"),
            column_aliases=merged_aliases,
            dtype_overrides=options.dtype_overrides,
        )
    except (TypeError, ValueError) as exc:
        raise CensusASMClientError(
            f"Census ASM data for year {year_value} failed normalization: {exc}"
        ) from exc

    normalized["intermediate_inputs"] = pd.NA
    metadata = {
        "year": year_value,
        "row_count": len(normalized),
        "contract_validated": True,
        "required_fields": list(_REQUIRED_FIELDS),
    }
    normalized.attrs["census_asm_metadata"] = metadata

    if cache:
        cache.set(
            cache_key,
            {"records": normalized.to_dict("records"), "metadata": metadata},
        )

    return normalized


def _validate_census_payload(
    payload: object,
    *,
    year: int,
) -> tuple[list[str], list[list[Any]]]:
    """Validate the Census list-of-lists response contract."""

    if isinstance(payload, Mapping):
        detail = payload.get("error") or payload.get("message") or "unexpected object response"
        raise CensusASMClientError(f"Census ASM API error for year {year}: {detail}")

    try:
        outer = require_sequence(payload, context=f"Census ASM response for year {year}")
    except ContractValidationError as exc:
        raise CensusASMClientError(str(exc)) from exc

    if len(outer) < 2:
        raise CensusASMClientError(f"No Census ASM data rows were returned for year {year}.")

    try:
        header_values = require_sequence(
            outer[0], context=f"Census ASM header for year {year}"
        )
        header = [
            require_nonempty_text(
                value,
                field=f"column[{index}]",
                context=f"Census ASM header for year {year}",
            )
            for index, value in enumerate(header_values)
        ]
    except ContractValidationError as exc:
        raise CensusASMClientError(str(exc)) from exc

    if len(set(header)) != len(header):
        raise CensusASMClientError(f"Census ASM header for year {year} contains duplicate columns.")

    missing = [field for field in _REQUIRED_FIELDS if field not in header]
    if missing:
        raise CensusASMClientError(
            f"Census ASM response for year {year} is missing required columns: "
            + ", ".join(missing)
        )

    validated_rows: list[list[Any]] = []
    for row_index, raw_row in enumerate(outer[1:], start=1):
        context = f"Census ASM row {row_index} for year {year}"
        try:
            row = list(require_sequence(raw_row, context=context))
            if len(row) != len(header):
                raise ContractValidationError(
                    f"{context} has {len(row)} values but the header has {len(header)} columns."
                )
            record = dict(zip(header, row, strict=True))
            require_nonempty_text(record["NAICS2017"], field="NAICS2017", context=context)
            require_nonempty_text(
                record["NAICS2017_LABEL"], field="NAICS2017_LABEL", context=context
            )
            for field in _NUMERIC_FIELDS:
                require_finite_number(record[field], field=field, context=context)
        except ContractValidationError as exc:
            raise CensusASMClientError(str(exc)) from exc
        validated_rows.append(row)

    if not validated_rows:
        raise CensusASMClientError(f"No Census ASM data rows were returned for year {year}.")
    return header, validated_rows


__all__ = [
    "ASM_ENDPOINT_TEMPLATE",
    "CensusASMClientError",
    "fetch_asm_manufacturing",
]
