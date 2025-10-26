"""Simple, configurable token bucket rate limiter implementations."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from ..core import RateLimitConfig, load_config


@dataclass
class RateLimiter:
    """Token bucket limiter for a single logical stream of requests."""

    requests_per_minute: int

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._tokens = float(self.requests_per_minute)
        self._last_update = time.time()

    @property
    def _requests_per_second(self) -> float:
        """Return the configured throughput expressed as requests per second."""

        return self.requests_per_minute / 60.0

    def acquire(self) -> bool:
        """Return ``True`` when a token is available, ``False`` otherwise."""

        with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            self._tokens = min(
                float(self.requests_per_minute),
                self._tokens + elapsed * self._requests_per_second,
            )
            self._last_update = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    def wait(self) -> None:
        """Block until a token is available for consumption."""

        while not self.acquire():
            time.sleep(max(0.1, 1.0 / self._requests_per_second))


class APIRateLimiter:
    """Facade around multiple :class:`RateLimiter` instances for external APIs."""

    def __init__(self, limits: RateLimitConfig | None = None) -> None:
        config = limits or load_config().rate_limits
        self._limiters: dict[str, RateLimiter] = {
            "bea": RateLimiter(config.bea),
            "census": RateLimiter(config.census),
            "default": RateLimiter(config.default),
        }

    def wait_for_api(self, api_name: str) -> None:
        """Block until the caller may execute a request for ``api_name``."""

        limiter = self._limiters.get(api_name.lower(), self._limiters["default"])
        # TODO-P1(10h): Persist limiter state to coordinate across
        # horizontally scaled workers when the ingestion service is deployed.
        limiter.wait()


api_limiter = APIRateLimiter()


__all__ = ["APIRateLimiter", "RateLimiter", "api_limiter"]
