"""Security validation helpers for uploads, API keys, and user-supplied input."""

from __future__ import annotations

import math
import re
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol, cast

import pandas as pd

from .types import ValidationResult

_DANGEROUS_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"<script",
        r"</script",
        r"javascript:",
        r"on\w+\s*=",
        r"eval\s*\(",
        r"document\.",
        r"window\.",
        r"alert\s*\(",
        r"prompt\s*\(",
    )
)


@dataclass(frozen=True)
class FilePolicy:
    """Constraints applied to uploaded files before persisting them."""

    allowed_extensions: frozenset[str] = frozenset({".csv", ".xlsx", ".xls"})
    max_size_mb: int = 50


@dataclass(frozen=True)
class CsvPolicy:
    """Limits applied when inspecting CSV contents for dangerous payloads."""

    max_columns: int = 100
    max_rows: int = 100_000
    max_cell_length: int = 10_000
    sample_size: int = 100


class SecurityUtils:
    """Static security validation helpers."""

    default_file_policy = FilePolicy()
    default_csv_policy = CsvPolicy()
    _rate_limit_backend: str = "memory"

    class RateLimitHandler(Protocol):
        def __call__(
            self, identifier: str, max_requests: int, window_seconds: int
        ) -> RateLimitDecision: ...

    _rate_limit_handler: RateLimitHandler | None = None

    @staticmethod
    def validate_file_upload(
        file_path: str | Path,
        policy: FilePolicy | None = None,
        *,
        file_size_bytes: int | None = None,
    ) -> ValidationResult[Path]:
        """Validate basic file attributes before any further processing."""

        policy = policy or SecurityUtils.default_file_policy
        path = Path(file_path)

        if file_size_bytes is None and not path.exists():
            return ValidationResult.failure("File does not exist.")

        if path.suffix.lower() not in policy.allowed_extensions:
            return ValidationResult.failure(
                "File type not allowed. Allowed extensions: "
                + ", ".join(sorted(policy.allowed_extensions))
            )

        if file_size_bytes is None:
            file_size_bytes = path.stat().st_size

        file_size_mb = file_size_bytes / (1024 * 1024)
        if file_size_mb > policy.max_size_mb:
            return ValidationResult.failure(
                f"File exceeds allowed size of {policy.max_size_mb} MB."
            )

        if _contains_dangerous_patterns(path.name):
            return ValidationResult.failure("Filename contains potentially dangerous characters.")

        return ValidationResult.success(path, "File validation passed.")

    @staticmethod
    def sanitize_filename(filename: str, fallback: str = "uploaded_file.csv") -> str:
        """Return a filesystem-friendly filename preserving the original suffix."""

        if not filename:
            return fallback

        sanitized = re.sub(r"[\\/]+", "", filename)
        sanitized = re.sub(r"\.\.", "", sanitized)
        sanitized = re.sub(r"[<>:\"|?*]", "", sanitized)

        if len(sanitized) > 255:
            stem, suffix = Path(sanitized).stem, Path(sanitized).suffix
            sanitized = stem[: max(1, 255 - len(suffix))] + suffix

        if not sanitized or sanitized.strip() == "":
            return fallback

        if Path(sanitized).suffix == "":
            sanitized = sanitized + Path(fallback).suffix

        return sanitized

    @staticmethod
    def validate_csv_content(
        df: pd.DataFrame, policy: CsvPolicy | None = None
    ) -> ValidationResult[None]:
        """Inspect a dataframe for unreasonably large or risky values."""

        policy = policy or SecurityUtils.default_csv_policy

        if len(df.columns) > policy.max_columns:
            return ValidationResult.failure(
                f"CSV contains {len(df.columns)} columns; maximum allowed is {policy.max_columns}."
            )

        if len(df) > policy.max_rows:
            return ValidationResult.failure(
                f"CSV contains {len(df)} rows; maximum allowed is {policy.max_rows}."
            )

        for column in df.columns:
            if _contains_dangerous_patterns(str(column)):
                return ValidationResult.failure(f"Column name contains dangerous pattern: {column}")

        sample_size = min(policy.sample_size, len(df))
        for row in range(sample_size):
            for column in df.columns:
                cell = str(df.iloc[row][column])
                if len(cell) > policy.max_cell_length:
                    return ValidationResult.failure(
                        f"Cell content too large at row {row}, column {column}."
                    )
                if _contains_dangerous_patterns(cell):
                    return ValidationResult.failure(
                        f"Cell content contains dangerous pattern at row {row}, column {column}."
                    )

        return ValidationResult.success(None, "CSV content validation passed.")

    @staticmethod
    def validate_api_key(api_key: str, service_name: str) -> ValidationResult[str]:
        """Ensure an API key resembles a valid credential before using it."""

        cleaned = api_key.strip() if api_key else ""
        if not cleaned:
            return ValidationResult.failure(f"{service_name} API key is required.")

        if len(cleaned) < 10:
            return ValidationResult.failure(f"{service_name} API key appears too short.")

        if len(cleaned) > 200:
            return ValidationResult.failure(f"{service_name} API key appears excessively long.")

        if re.search(r"[<>]", cleaned):
            return ValidationResult.failure(f"{service_name} API key contains invalid characters.")

        return ValidationResult.success(cleaned, "API key validation passed.")

    @staticmethod
    def validate_year(year: object) -> ValidationResult[int]:
        """Validate numeric year input, coercing from floats or strings when possible."""

        if year is None or isinstance(year, bool):
            return ValidationResult.failure("Year must be an integer value.")

        parsed: int | None = None
        if isinstance(year, int):
            parsed = year
        elif isinstance(year, float):
            if not math.isfinite(year) or not year.is_integer():
                return ValidationResult.failure("Year must be an integer value.")
            parsed = int(year)
        else:
            cleaned = str(year).strip()
            if not cleaned:
                return ValidationResult.failure("Year must be an integer value.")
            try:
                candidate = Decimal(cleaned)
            except (InvalidOperation, ValueError):
                return ValidationResult.failure("Year must be an integer value.")
            if not candidate.is_finite():
                return ValidationResult.failure("Year must be an integer value.")
            if candidate != candidate.to_integral_value():
                return ValidationResult.failure("Year must be an integer value.")
            parsed = int(candidate)

        if parsed < 1900 or parsed > 2100:
            return ValidationResult.failure("Year must be between 1900 and 2100.")

        return ValidationResult.success(parsed, "Year validation passed.")

    @staticmethod
    def sanitize_string_input(value: str, *, max_length: int = 1000) -> str:
        """Remove potentially harmful substrings from free-form user input."""

        if not value:
            return ""

        trimmed = value.strip()[:max_length]
        sanitized = trimmed
        for pattern in _DANGEROUS_PATTERNS:
            sanitized = pattern.sub("", sanitized)

        sanitized = sanitized.replace("<", "").replace(">", "")
        return sanitized

    @staticmethod
    def rate_limit_check(
        identifier: str,
        max_requests: int,
        window_seconds: int,
    ) -> ValidationResult[None]:
        """Perform an in-memory rate-limit check placeholder."""

        if max_requests <= 0 or window_seconds <= 0:
            return ValidationResult.failure("Rate limit parameters must be positive.")

        handler = SecurityUtils._rate_limit_handler or _DEFAULT_MEMORY_LIMITER.consume
        decision = handler(identifier, max_requests, window_seconds)
        if decision.allowed:
            return ValidationResult.success(None, "Rate limit check passed.")

        message = "Rate limit exceeded."
        if decision.retry_after_seconds is not None:
            message = (
                f"Rate limit exceeded. Retry after " f"{decision.retry_after_seconds:.1f} seconds."
            )
        return ValidationResult.failure(message)

    @staticmethod
    def register_rate_limit_handler(handler: RateLimitHandler, *, backend_name: str) -> None:
        """Register a backend-aware handler used to enforce rate limits."""

        SecurityUtils._rate_limit_handler = handler
        SecurityUtils._rate_limit_backend = backend_name

    @staticmethod
    def rate_limit_handler_summary() -> dict[str, object]:
        """Return diagnostics about the active rate limit handler."""

        base: dict[str, object] = {"backend": SecurityUtils._rate_limit_backend}
        handler = SecurityUtils._rate_limit_handler
        if handler is None:
            base["mode"] = "memory"
            return base

        summary_fn: Callable[[], Mapping[str, object]] | None
        try:
            summary_fn = cast(Callable[[], Mapping[str, object]], handler.summary)  # type: ignore[attr-defined]
        except AttributeError:
            summary_fn = None

        if summary_fn is not None:
            try:
                summary = summary_fn()
            except Exception:
                base["mode"] = "unknown"
            else:
                base.update(dict(summary))
        else:
            base["mode"] = "memory"
        return base


def _contains_dangerous_patterns(text: str) -> bool:
    """Return ``True`` when ``text`` contains substrings matching dangerous regexes."""

    lowered = text.lower()
    return any(pattern.search(lowered) for pattern in _DANGEROUS_PATTERNS)


__all__ = [
    "CsvPolicy",
    "FilePolicy",
    "RateLimitDecision",
    "SecurityUtils",
]


@dataclass(frozen=True)
class RateLimitDecision:
    """Outcome returned by rate limit handlers."""

    allowed: bool
    remaining_tokens: float | None = None
    retry_after_seconds: float | None = None
    backend: str = "memory"


class _MemoryLimiter:
    """Simple token bucket limiter scoped by identifier."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, tuple[float, float]] = {}

    def consume(self, identifier: str, max_requests: int, window_seconds: int) -> RateLimitDecision:
        refill_rate = max_requests / float(window_seconds)
        with self._lock:
            tokens, last_ts = self._state.get(identifier, (float(max_requests), time.time()))
            now = time.time()
            elapsed = max(0.0, now - last_ts)
            tokens = min(float(max_requests), tokens + elapsed * refill_rate)
            allowed = tokens >= 1.0
            if allowed:
                tokens -= 1.0
                retry_after: float | None = 0.0
            else:
                retry_after = (1.0 - tokens) / refill_rate if refill_rate else None
            self._state[identifier] = (tokens, now)
        return RateLimitDecision(
            allowed=allowed,
            remaining_tokens=tokens,
            retry_after_seconds=retry_after,
            backend="memory",
        )


_DEFAULT_MEMORY_LIMITER = _MemoryLimiter()
