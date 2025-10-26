"""HTTP helper utilities shared across adapters and infrastructure layers."""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import requests  # type: ignore[import-untyped]


class HTTPRequestError(RuntimeError):
    """Raised when an HTTP request cannot be completed successfully."""


class InvalidJSONError(HTTPRequestError):
    """Raised when a response body cannot be parsed as JSON."""


@dataclass(frozen=True)
class RetryPolicy:
    """Configuration governing retry behaviour for HTTP requests."""

    max_attempts: int = 3
    base_delay: float = 1.0
    backoff_factor: float = 2.0
    jitter: bool = True


@dataclass(frozen=True)
class RetryEvent:
    """Structured payload emitted for HTTP retry instrumentation."""

    url: str
    attempt: int
    max_attempts: int
    delay_seconds: float
    status: str
    error: str | None = None


_RETRY_OBSERVER: Callable[[RetryEvent], None] | None = None


def register_retry_observer(observer: Callable[[RetryEvent], None]) -> None:
    """Register a callback receiving retry telemetry."""

    global _RETRY_OBSERVER
    _RETRY_OBSERVER = observer


def safe_get_json(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 30.0,
    retry_policy: RetryPolicy | None = None,
) -> Any:
    """Fetch JSON from an HTTP endpoint with retry support."""

    policy = retry_policy or RetryPolicy()
    session = requests.Session()
    last_error: Exception | None = None

    try:
        for attempt in range(1, policy.max_attempts + 1):
            try:
                response = session.get(
                    url,
                    params=dict(params or {}),
                    headers=dict(headers or {}),
                    timeout=timeout,
                )
                response.raise_for_status()
            except requests.exceptions.Timeout as exc:
                last_error = HTTPRequestError(f"Request to {url} timed out: {exc}")
            except requests.exceptions.ConnectionError as exc:
                last_error = HTTPRequestError(f"Connection error while requesting {url}: {exc}")
            except requests.exceptions.HTTPError as exc:
                raise HTTPRequestError(
                    f"HTTP {response.status_code} error for {url}: {response.text[:200]}"
                ) from exc
            except requests.exceptions.RequestException as exc:
                last_error = HTTPRequestError(f"Request error while contacting {url}: {exc}")
            else:
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise InvalidJSONError(f"Invalid JSON response from {url}: {exc}") from exc
                _emit_retry_event(
                    RetryEvent(
                        url=url,
                        attempt=attempt,
                        max_attempts=policy.max_attempts,
                        delay_seconds=0.0,
                        status="success",
                        error=None,
                    )
                )
                return payload

            if attempt >= policy.max_attempts:
                break

            delay = policy.base_delay * (policy.backoff_factor ** (attempt - 1))
            if policy.jitter:
                delay *= random.uniform(0.8, 1.2)
            _emit_retry_event(
                RetryEvent(
                    url=url,
                    attempt=attempt,
                    max_attempts=policy.max_attempts,
                    delay_seconds=delay,
                    status="retrying",
                    error=str(last_error) if last_error else None,
                )
            )
            time.sleep(delay)

    finally:
        session.close()

    _emit_retry_event(
        RetryEvent(
            url=url,
            attempt=policy.max_attempts,
            max_attempts=policy.max_attempts,
            delay_seconds=0.0,
            status="failed",
            error=str(last_error) if last_error else None,
        )
    )
    raise last_error or HTTPRequestError(f"Failed to fetch JSON from {url}")


def _emit_retry_event(event: RetryEvent) -> None:
    observer = _RETRY_OBSERVER
    if observer is not None:
        try:
            observer(event)
        except Exception:  # pragma: no cover - defensive
            pass


__all__ = [
    "HTTPRequestError",
    "InvalidJSONError",
    "RetryEvent",
    "RetryPolicy",
    "register_retry_observer",
    "safe_get_json",
]
