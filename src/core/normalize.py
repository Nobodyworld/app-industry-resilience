"""Column normalisation helpers for harmonising disparate economic datasets."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

from .security import SecurityUtils

REQUIRED_COLS: tuple[str, ...] = (
    "industry_code",
    "industry_name",
    "year",
    "gross_output",
)

OPTIONAL_COLS: tuple[str, ...] = (
    "materials_cost",
    "intermediate_inputs",
    "value_added",
    "source",
)

DEFAULT_COLUMN_ALIASES: Mapping[str, str] = {
    "naics": "industry_code",
    "naics_code": "industry_code",
    "naics2017": "industry_code",
    "naics2017_code": "industry_code",
    "naics2017_label": "industry_name",
    "description": "industry_name",
    "industrydescription": "industry_name",
    "industrYdescription": "industry_name",
    "valueadded": "value_added",
    "valadd": "value_added",
    "rcptot": "gross_output",
    "cstmtot": "materials_cost",
    "go": "gross_output",
    "intermediateinputs": "intermediate_inputs",
}

_NUMERIC_CLEANER = re.compile(r"[\s,_]")


@dataclass(frozen=True)
class NormalizationOptions:
    """Additional parameters controlling dataframe normalisation."""

    column_aliases: Mapping[str, str] | None = None
    dtype_overrides: Mapping[str, Any] | None = None


def normalize_columns(
    df: pd.DataFrame,
    column_aliases: Mapping[str, str] | None = None,
    *,
    dtype_overrides: Mapping[str, Any] | None = None,
    options: NormalizationOptions | None = None,
) -> pd.DataFrame:
    """Return a canonical view of the provided DataFrame.

    The function validates required columns, coerces numeric fields into floats,
    trims string columns, and ensures optional columns exist.
    """

    if df.empty:
        raise ValueError("Input dataframe is empty; cannot normalise columns.")

    opts = options or NormalizationOptions()
    alias_input = column_aliases if column_aliases is not None else opts.column_aliases
    dtype_input = dtype_overrides if dtype_overrides is not None else opts.dtype_overrides

    alias_map = {
        key.lower(): value
        for key, value in {**DEFAULT_COLUMN_ALIASES, **(alias_input or {})}.items()
    }

    normalized = df.copy()
    normalized.columns = [col.strip().lower() for col in normalized.columns]
    normalized.rename(columns=lambda c: alias_map.get(c, c), inplace=True)

    missing_required = [col for col in REQUIRED_COLS if col not in normalized.columns]
    if missing_required:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing_required)))

    for optional in OPTIONAL_COLS:
        if optional not in normalized.columns:
            normalized[optional] = pd.NA

    normalized["industry_code"] = normalized["industry_code"].astype(str).str.strip().str.upper()
    normalized["industry_name"] = normalized["industry_name"].astype(str).str.strip()
    normalized["source"] = normalized["source"].fillna("Unknown").astype(str).str.strip()

    normalized["year"] = normalized["year"].apply(_coerce_year)
    for column in ("gross_output", "materials_cost", "intermediate_inputs", "value_added"):
        normalized[column] = normalized[column].apply(_coerce_numeric)

    if dtype_input:
        apply_dtype_overrides(normalized, dtype_input)

    return normalized


def apply_dtype_overrides(df: pd.DataFrame, overrides: Mapping[str, Any]) -> None:
    """Apply dtype overrides, raising descriptive errors on failure."""

    for column, dtype in overrides.items():
        column_normalised = column.strip().lower()
        if column_normalised not in df.columns:
            raise ValueError(f"dtype override references unknown column: {column}")
        try:
            df[column_normalised] = df[column_normalised].astype(dtype)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Failed to apply dtype override for column '{column_normalised}': {exc}"
            ) from exc


def _coerce_year(value: object) -> int:
    """Validate and coerce a single year value into an integer."""

    if pd.isna(value):
        raise ValueError("Year column contains null values after normalisation.")

    result = SecurityUtils.validate_year(value)
    if not result.ok or result.value is None:
        message = result.message or f"Unable to parse year value '{value}'."
        raise ValueError(message)

    return result.value


def _coerce_numeric(value: object) -> float | None:
    """Convert free-form numeric input to a float while tolerating noise."""

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, int | float) and not pd.isna(value):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        cleaned = _NUMERIC_CLEANER.sub("", cleaned.replace("−", "-"))
        try:
            return float(Decimal(cleaned))
        except (InvalidOperation, ValueError):
            return None

    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return None


__all__ = [
    "DEFAULT_COLUMN_ALIASES",
    "OPTIONAL_COLS",
    "REQUIRED_COLS",
    "NormalizationOptions",
    "apply_dtype_overrides",
    "normalize_columns",
]
