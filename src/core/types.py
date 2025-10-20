"""Shared type helpers used across the application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ValidationResult(Generic[T]):
    """Generic validation outcome.

    ``value`` is ``None`` when ``ok`` is ``False`` unless a caller explicitly
    passes an alternate payload. Keeping the optional semantics at the class
    level avoids widening the public ``ValidationResult[T]`` type to
    ``ValidationResult[Optional[T]]`` which complicated downstream use and
    broke ``mypy`` inference.
    """

    ok: bool
    value: T | None
    message: str

    @classmethod
    def success(cls, value: T, message: str = "") -> "ValidationResult[T]":
        return cls(True, value, message)

    @classmethod
    def failure(
        cls, message: str, *, value: T | None = None
    ) -> "ValidationResult[T]":
        return cls(False, value, message)


__all__ = ["ValidationResult"]

