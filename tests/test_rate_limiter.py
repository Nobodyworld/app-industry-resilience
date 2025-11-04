from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Any

import pytest

from src.core import SecurityUtils
from src.infrastructure import rate_limiter
from src.infrastructure.rate_limiter import (
    APIRateLimiter,
    InMemoryTokenBucket,
    RateLimiterService,
    RateLimitRule,
    RedisTokenBucket,
    _reset_for_tests,
)

try:  # pragma: no cover - exercised in environments with fakeredis
    import fakeredis
except ModuleNotFoundError:  # pragma: no cover - runtime fallback exercised in CI
    fakeredis = None


class StubRedis:
    """Minimal Redis client emulating Lua script execution for tests."""

    def __init__(self) -> None:
        self._state: dict[str, tuple[float, float]] = {}
        self.should_fail: bool = False

    def register_script(self, _script: str) -> Callable[..., list[float | int]]:
        def _call(*, keys: list[str], args: list[float | int]) -> list[float | int]:
            if self.should_fail:
                raise rate_limiter.RedisError("forced failure")

            key = keys[0]
            max_tokens = float(args[0])
            refill_rate = float(args[1])
            now = float(args[2])
            requested = float(args[3])
            ttl_seconds = float(args[4])

            tokens, last = self._state.get(key, (max_tokens, now))
            delta = max(0.0, now - last)
            tokens = min(max_tokens, tokens + delta * refill_rate)
            allowed = tokens >= requested
            retry_after = 0.0
            if allowed:
                tokens -= requested
            else:
                needed = requested - tokens
                retry_after = needed / refill_rate if refill_rate > 0 else ttl_seconds
            self._state[key] = (tokens, now)
            return [1 if allowed else 0, tokens, retry_after]

        return _call


@pytest.fixture
def redis_client() -> Any:
    if fakeredis is not None:
        client = fakeredis.FakeRedis()
        client.flushall()
        return client
    return StubRedis()


@pytest.fixture(autouse=True)
def reset_rate_limiter_state() -> Generator[None]:
    """Ensure singleton state does not leak between tests."""

    previous_handler = SecurityUtils._rate_limit_handler
    previous_backend = SecurityUtils._rate_limit_backend
    yield
    _reset_for_tests()
    SecurityUtils._rate_limit_handler = previous_handler
    SecurityUtils._rate_limit_backend = previous_backend


def test_in_memory_service_blocks_after_consuming_tokens() -> None:
    service = RateLimiterService(InMemoryTokenBucket())
    rule = RateLimitRule.per_window(2, 60, scope="test")

    first = service.enforce("alpha", rule)
    second = service.enforce("alpha", rule)
    third = service.enforce("alpha", rule)

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.retry_after_seconds is not None


def test_redis_backend_shares_tokens_across_services(redis_client: Any) -> None:
    backend = RedisTokenBucket(
        client=redis_client,
        key_prefix="idiot-index-test",
        ttl_seconds=120,
    )
    service_a = RateLimiterService(backend)
    service_b = RateLimiterService(backend)
    rule = RateLimitRule.per_window(1, 60, scope="api:bea")

    assert service_a.enforce("shared", rule).allowed is True
    blocked = service_b.enforce("shared", rule)
    assert blocked.allowed is False
    assert blocked.retry_after_seconds is not None


def test_security_utils_respects_registered_backend() -> None:
    backend = RateLimiterService(InMemoryTokenBucket())

    def handler(identifier: str, max_requests: int, window_seconds: int):
        rule = RateLimitRule.per_window(max_requests, window_seconds, scope="security")
        return backend.enforce(identifier, rule)

    handler.summary = backend.summary  # type: ignore[attr-defined]
    SecurityUtils.register_rate_limit_handler(handler, backend_name="memory-test")

    assert SecurityUtils.rate_limit_check("client", 1, 60).ok is True
    result = SecurityUtils.rate_limit_check("client", 1, 60)
    assert result.ok is False
    assert "Retry" in (result.message or "")


def test_api_rate_limiter_exposes_status() -> None:
    limiter = APIRateLimiter()
    status = limiter.status()
    assert "mode" in status
    assert status["mode"] in {"memory", "redis", "redis-fallback"}


def test_token_bucket_wait_blocks_until_available(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_time = _FakeTime()
    monkeypatch.setattr(rate_limiter, "time", fake_time)

    backend = InMemoryTokenBucket()
    rule = RateLimitRule.per_window(1, 1, scope="test")
    backend.acquire("key", rule)

    decision = backend.wait("key", rule)

    assert decision.allowed is True
    assert fake_time.slept
    assert fake_time.slept[0] == pytest.approx(1.0)


def test_redis_backend_reports_fallback_when_errors() -> None:
    client = StubRedis()
    backend = RedisTokenBucket(client=client, key_prefix="idiot-index-test", ttl_seconds=60)  # type: ignore[arg-type]
    rule = RateLimitRule.per_window(1, 60, scope="api:test")

    assert backend.acquire("key", rule).allowed is True

    client.should_fail = True
    fallback_decision = backend.acquire("key", rule)

    assert fallback_decision.backend == "redis-fallback"
    summary = backend.summary()
    assert summary["mode"] == "redis-fallback"
    assert summary["backend"] == "redis"
    assert summary["fallback"] == "memory"
    assert summary["last_error"]


def test_rate_limit_rule_requires_positive_parameters() -> None:
    with pytest.raises(ValueError):
        RateLimitRule.per_window(0, 10, scope="bad")
    with pytest.raises(ValueError):
        RateLimitRule.per_window(10, 0, scope="bad")
    with pytest.raises(ValueError):
        RateLimitRule.per_window(10, 60, scope="  ")


class _FakeTime:
    def __init__(self) -> None:
        self._now = 0.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self._now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self._now += seconds
