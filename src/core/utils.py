"""Utility helpers shared between API modules and the Streamlit app."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Mapping

import requests  # type: ignore[import-untyped]


class HTTPRequestError(RuntimeError):
    """Raised when an HTTP request cannot be completed successfully."""


class InvalidJSONError(HTTPRequestError):
    """Raised when a response body cannot be parsed as JSON."""


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 1.0
    backoff_factor: float = 2.0
    jitter: bool = True


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
                last_error = HTTPRequestError(
                    f"Connection error while requesting {url}: {exc}"
                )
            except requests.exceptions.HTTPError as exc:
                raise HTTPRequestError(
                    f"HTTP {response.status_code} error for {url}: {response.text[:200]}"
                ) from exc
            except requests.exceptions.RequestException as exc:
                last_error = HTTPRequestError(
                    f"Request error while contacting {url}: {exc}"
                )
            else:
                try:
                    return response.json()
                except ValueError as exc:
                    raise InvalidJSONError(
                        f"Invalid JSON response from {url}: {exc}"
                    ) from exc

            if attempt >= policy.max_attempts:
                break

            delay = policy.base_delay * (policy.backoff_factor ** (attempt - 1))
            if policy.jitter:
                delay *= random.uniform(0.8, 1.2)
            time.sleep(delay)

    finally:
        session.close()

    raise last_error or HTTPRequestError(f"Failed to fetch JSON from {url}")


__all__ = ["HTTPRequestError", "InvalidJSONError", "RetryPolicy", "safe_get_json"]

