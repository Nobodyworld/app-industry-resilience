"""Shared validation helpers for external adapter response contracts."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

_NUMERIC_CLEANER = re.compile(r"[\s,_]")


class ContractValidationError(ValueError):
    """Raised when an upstream response violates its documented shape."""


def require_mapping(value: object, *, context: str) -> Mapping[str, Any]:
    """Return ``value`` as a mapping or raise a contextual contract error."""

    if not isinstance(value, Mapping):
        raise ContractValidationError(f"{context} must be an object mapping.")
    return value


def require_sequence(value: object, *, context: str) -> Sequence[Any]:
    """Return ``value`` as a non-string sequence or raise a contract error."""

    if isinstance(value, str | bytes | bytearray) or not isinstance(value, Sequence):
        raise ContractValidationError(f"{context} must be an array.")
    return value


def require_nonempty_text(value: object, *, field: str, context: str) -> str:
    """Validate and return a required textual field."""

    if value is None:
        raise ContractValidationError(f"{context} is missing required field '{field}'.")
    text = str(value).strip()
    if not text:
        raise ContractValidationError(f"{context} field '{field}' must not be empty.")
    return text


def require_positive_year(value: object, *, field: str, context: str) -> int:
    """Validate a finite positive integral year value."""

    text = require_nonempty_text(value, field=field, context=context)
    try:
        numeric = Decimal(text)
    except InvalidOperation as exc:
        raise ContractValidationError(
            f"{context} field '{field}' must be an integer year; received {text!r}."
        ) from exc
    if not numeric.is_finite() or numeric != numeric.to_integral_value() or numeric <= 0:
        raise ContractValidationError(
            f"{context} field '{field}' must be a positive integer year; received {text!r}."
        )
    return int(numeric)


def require_finite_number(value: object, *, field: str, context: str) -> float:
    """Validate a finite numeric field while accepting common thousands separators."""

    if value is None or isinstance(value, bool):
        raise ContractValidationError(f"{context} field '{field}' must be numeric.")

    if isinstance(value, int | float):
        numeric = float(value)
    else:
        text = str(value).strip()
        if not text:
            raise ContractValidationError(f"{context} field '{field}' must be numeric.")
        cleaned = _NUMERIC_CLEANER.sub("", text.replace("−", "-"))
        try:
            numeric = float(Decimal(cleaned))
        except (InvalidOperation, ValueError) as exc:
            raise ContractValidationError(
                f"{context} field '{field}' must be numeric; received {text!r}."
            ) from exc

    if not math.isfinite(numeric):
        raise ContractValidationError(
            f"{context} field '{field}' must be finite; received {value!r}."
        )
    return numeric


__all__ = [
    "ContractValidationError",
    "require_finite_number",
    "require_mapping",
    "require_nonempty_text",
    "require_positive_year",
    "require_sequence",
]
