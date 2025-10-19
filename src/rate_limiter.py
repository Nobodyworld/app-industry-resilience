"""Simple, configurable token bucket rate limiter implementations."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict

from .config import RateLimitConfig, load_config


@dataclass
class RateLimiter:
    requests_per_minute: int

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._tokens = float(self.requests_per_minute)
        self._last_update = time.time()

    @property
    def _requests_per_second(self) -> float:
        return self.requests_per_minute / 60.0

    def acquire(self) -> bool:
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
        while not self.acquire():
            time.sleep(max(0.1, 1.0 / self._requests_per_second))


class APIRateLimiter:
    def __init__(self, limits: RateLimitConfig | None = None) -> None:
        config = limits or load_config().rate_limits
        self._limiters: Dict[str, RateLimiter] = {
            "bea": RateLimiter(config.bea),
            "census": RateLimiter(config.census),
            "default": RateLimiter(config.default),
        }

    def wait_for_api(self, api_name: str) -> None:
        limiter = self._limiters.get(api_name.lower(), self._limiters["default"])
        limiter.wait()


api_limiter = APIRateLimiter()


__all__ = ["APIRateLimiter", "RateLimiter", "api_limiter"]

