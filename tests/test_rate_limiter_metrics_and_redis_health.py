from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.extensions.builtins import rate_limiting
from src.infrastructure import rate_limiter
from src.infrastructure.observability.instrumentation import ObservabilityRegistry
from src.infrastructure.rate_limiter import RateLimiterService, RateLimitRule, RedisTokenBucket


@pytest.mark.parametrize("failures", [(False, True, False), (True, False, True, False)])
def test_redis_fallback_sets_gauge_and_recovers(monkeypatch, failures) -> None:
    # Restore the previous registry after the test, rather than leaking global metrics.
    monkeypatch.setattr(rate_limiter, "_METRICS", None)
    monkeypatch.setattr(rate_limiting, "register_retry_observer", lambda observer: None)

    class FakeClient:
        should_fail = False

        def register_script(self, script):
            def execute(*args, **kwargs):
                if self.should_fail:
                    raise rate_limiter.RedisError("controlled connection failure")
                return [1, 0, 0]

            return execute

    client = FakeClient()
    bucket = RedisTokenBucket(client=client, key_prefix="transition-test", ttl_seconds=60)
    service = RateLimiterService(bucket)
    monkeypatch.setattr(
        rate_limiting, "get_api_limiter", lambda: SimpleNamespace(status=service.summary)
    )
    monkeypatch.setattr(
        rate_limiting,
        "SecurityUtils",
        SimpleNamespace(rate_limit_handler_summary=service.summary),
    )
    registry = ObservabilityRegistry()
    rate_limiting._RateLimitingInstrumentation().register(registry)
    gauge = registry.metrics.gauges["rate_limit_backend_up"]
    health = registry._health_checks["rate_limiting"]
    rule = RateLimitRule.per_window(1, 60, "transition-test")

    for index, failing in enumerate(failures):
        client.should_fail = failing
        decision = service.enforce(f"key-{index}", rule)
        expected_mode = "redis-fallback" if failing else "redis"
        assert decision.allowed is True
        assert decision.backend == expected_mode
        assert dict(gauge.samples()) == {("redis",): 0.0 if failing else 1.0}
        assert service.summary()["mode"] == expected_mode
        assert bool(service.summary()["last_error"]) is failing
        report = health()
        assert report.status == ("warn" if failing else "pass")
        assert report.details["limiter"]["mode"] == expected_mode

    counter = registry.metrics.counters["rate_limit_requests_total"]
    counts = dict(counter.samples())
    assert counts[("transition-test", "redis", "allow")] == failures.count(False)
    assert counts[("transition-test", "redis-fallback", "allow")] == failures.count(True)
