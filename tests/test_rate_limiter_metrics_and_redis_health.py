from __future__ import annotations

from src.infrastructure.observability.metrics import MetricRegistry
from src.infrastructure.rate_limiter import (
    RateLimitRule,
    RedisError,
    RedisTokenBucket,
    configure_metrics,
)


def test_redis_fallback_sets_gauge(monkeypatch) -> None:
    registry = MetricRegistry()
    counter = registry.counter(
        "rate_limit_requests_total", "desc", label_names=("scope", "backend", "outcome")
    )
    wait_histogram = registry.histogram(
        "rate_limit_wait_seconds", "desc", label_names=("scope", "backend")
    )
    backend_gauge = registry.gauge("rate_limit_backend_up", "backend up", label_names=("backend",))
    configure_metrics(counter, wait_histogram, backend_gauge)

    # Create a fake redis client that will raise a RedisError on script execution
    class _FakeClient:
        def register_script(self, script):
            def _script(*args, **kwargs):
                raise RedisError("redis failure")

            return _script

    client = _FakeClient()
    bucket = RedisTokenBucket(client=client, key_prefix="test", ttl_seconds=60)

    # This should fall back to in-memory and set gauge accordingly (backend=redis-fallback)
    bucket.acquire("k1", RateLimitRule.per_window(1, 10, "test"))
    # Gauge samples should have been set at least once
    samples = list(backend_gauge.samples())
    assert samples
