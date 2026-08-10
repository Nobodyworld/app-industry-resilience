"""Privacy-safe compatibility metadata for dataframe transformations.

Typed lineage is intentionally managed separately by :mod:`src.core.lineage`.
This module preserves only the small, established dataframe metadata surface
still consumed by API and application compatibility paths.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit

import pandas as pd

APPROVED_COMPATIBILITY_KEYS: tuple[str, ...] = (
    "source",
    "source_origin",
    "bea_metadata",
    "census_asm_metadata",
    "source_metadata",
)

APPROVED_BEA_FIELDS: tuple[str, ...] = (
    "years",
    "endpoint",
    "tables",
    "notes",
    "contract_validated",
    "unmapped_naics_codes",
)

APPROVED_CENSUS_ASM_FIELDS: tuple[str, ...] = (
    "year",
    "row_count",
    "contract_validated",
    "required_fields",
)

APPROVED_AIES_FIELDS: tuple[str, ...] = (
    "agency",
    "survey",
    "survey_year",
    "release_date",
    "basic_url",
    "expense_url",
    "denominator",
    "notes",
)

_SOURCE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,63}\Z")
_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:api[_ -]?key|password|access[_ -]?token|auth[_ -]?token|"
    r"secret|credential|cache[_ -]?key|redis[_ -]?url)\b\s*[:=]"
)
_PRIVATE_PATH = re.compile(r"(?i)(?:[a-z]:[\\/]|\\\\|/(?:users|home|tmp|var)/)")

_MAX_COLLECTION_ITEMS = 256
_MAX_TEXT_LENGTH = 2_000
_MAX_URL_LENGTH = 2_048


def sanitize_compatibility_metadata(frame: pd.DataFrame) -> dict[str, Any]:
    """Return a deep, allowlisted copy of established dataframe metadata."""

    attrs = frame.attrs
    sanitized: dict[str, Any] = {}

    for key in ("source", "source_origin"):
        value = _safe_source_identifier(attrs.get(key))
        if value is not None:
            sanitized[key] = value

    bea_metadata = _sanitize_bea_metadata(attrs.get("bea_metadata"))
    if bea_metadata is not None:
        sanitized["bea_metadata"] = bea_metadata

    census_metadata = _sanitize_census_asm_metadata(attrs.get("census_asm_metadata"))
    if census_metadata is not None:
        sanitized["census_asm_metadata"] = census_metadata

    source_metadata = _sanitize_aies_metadata(attrs.get("source_metadata"))
    if source_metadata is not None:
        sanitized["source_metadata"] = source_metadata

    return deepcopy(sanitized)


def apply_compatibility_metadata(target: pd.DataFrame, metadata: Mapping[str, Any]) -> pd.DataFrame:
    """Replace inherited attrs with an isolated copy of sanitized metadata."""

    target.attrs.clear()
    target.attrs.update(
        deepcopy({key: metadata[key] for key in APPROVED_COMPATIBILITY_KEYS if key in metadata})
    )
    return target


def _sanitize_bea_metadata(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None

    sanitized: dict[str, Any] = {}
    _add(sanitized, "years", _copy_sequence(value.get("years"), _safe_nonnegative_int))
    _add(sanitized, "endpoint", _safe_public_url(value.get("endpoint")))
    _add(sanitized, "tables", _copy_sequence(value.get("tables"), _safe_text))
    _add(sanitized, "notes", _safe_notes(value.get("notes")))
    _add(sanitized, "contract_validated", _safe_bool(value.get("contract_validated")))
    _add(
        sanitized,
        "unmapped_naics_codes",
        _copy_sequence(value.get("unmapped_naics_codes"), _safe_short_text),
    )
    return sanitized or None


def _sanitize_census_asm_metadata(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None

    sanitized: dict[str, Any] = {}
    _add(sanitized, "year", _safe_nonnegative_int(value.get("year")))
    _add(sanitized, "row_count", _safe_nonnegative_int(value.get("row_count")))
    _add(sanitized, "contract_validated", _safe_bool(value.get("contract_validated")))
    _add(
        sanitized,
        "required_fields",
        _copy_sequence(value.get("required_fields"), _safe_short_text),
    )
    return sanitized or None


def _sanitize_aies_metadata(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None

    sanitized: dict[str, Any] = {}
    for key in ("agency", "survey", "release_date", "denominator"):
        _add(sanitized, key, _safe_text(value.get(key)))
    _add(sanitized, "survey_year", _safe_nonnegative_int(value.get("survey_year")))
    _add(sanitized, "basic_url", _safe_public_url(value.get("basic_url")))
    _add(sanitized, "expense_url", _safe_public_url(value.get("expense_url")))
    _add(sanitized, "notes", _safe_notes(value.get("notes")))
    return sanitized or None


def _safe_source_identifier(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or not _SOURCE_IDENTIFIER.fullmatch(normalized):
        return None
    if ".." in normalized or _SECRET_ASSIGNMENT.search(normalized):
        return None
    return normalized


def _safe_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > _MAX_TEXT_LENGTH:
        return None
    if _CONTROL_CHARACTER.search(normalized):
        return None
    if _SECRET_ASSIGNMENT.search(normalized) or _PRIVATE_PATH.search(normalized):
        return None
    return normalized


def _safe_short_text(value: object) -> str | None:
    normalized = _safe_text(value)
    if normalized is None or len(normalized) > 256:
        return None
    return normalized


def _safe_public_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > _MAX_URL_LENGTH:
        return None
    if _CONTROL_CHARACTER.search(normalized) or _SECRET_ASSIGNMENT.search(normalized):
        return None
    try:
        parsed = urlsplit(normalized)
        _ = parsed.port
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None
    return normalized


def _safe_nonnegative_int(value: object) -> int | None:
    if type(value) is not int or value < 0:
        return None
    return value


def _safe_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _safe_notes(value: object) -> str | list[str] | tuple[str, ...] | None:
    if isinstance(value, str):
        return _safe_text(value)
    return _copy_sequence(value, _safe_text)


def _copy_sequence[T](
    value: object, sanitizer: Callable[[object], T | None]
) -> list[T] | tuple[T, ...] | None:
    if not isinstance(value, list | tuple) or len(value) > _MAX_COLLECTION_ITEMS:
        return None
    copied: list[T] = []
    for item in value:
        sanitized = sanitizer(item)
        if sanitized is not None:
            copied.append(sanitized)
    if isinstance(value, tuple):
        return tuple(copied)
    return copied


def _add(target: dict[str, Any], key: str, value: object) -> None:
    if value is not None:
        target[key] = value


__all__ = [
    "APPROVED_AIES_FIELDS",
    "APPROVED_BEA_FIELDS",
    "APPROVED_CENSUS_ASM_FIELDS",
    "APPROVED_COMPATIBILITY_KEYS",
    "apply_compatibility_metadata",
    "sanitize_compatibility_metadata",
]
