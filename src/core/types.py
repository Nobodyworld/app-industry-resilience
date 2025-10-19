"""Shared type helpers used across the application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ValidationResult(Generic[T]):
    """Generic validation outcome with an optional value."""

    ok: bool
    value: Optional[T]
    message: str

    @classmethod
    def success(cls, value: T, message: str = "") -> "ValidationResult[T]":
        return cls(True, value, message)

    @classmethod
    def failure(
        cls, message: str, *, value: Optional[T] = None
    ) -> "ValidationResult[Optional[T]]":
        return cls(False, value, message)


__all__ = ["ValidationResult"]

