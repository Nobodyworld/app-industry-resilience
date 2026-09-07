from __future__ import annotations

import asyncio
import os
import uuid
from importlib.metadata import version as package_version

import fakeredis
import pytest
import redis

from src.infrastructure.rate_limiter import (
    RateLimiterService,
    RateLimitRule,
    RedisTokenBucket,
)


def _version_prefix(distribution: str) -> tuple[int, int]:
    parts = package_version(distribution).split(".")
    return int(parts[0]), int(parts[1])


def _fake_redis_8_server() -> fakeredis.FakeServer:
    return fakeredis.FakeServer(version=(8,), server_type="redis")


def test_dependency_floors_resolve_to_redis_8_compatible_versions() -> None:
    assert _version_prefix("redis") >= (8, 1)
    assert _version_prefix("fakeredis") >= (2, 37)


def test_fakeredis_redis_8_runs_shared_lua_token_bucket_with_resp3() -> None:
    server = _fake_redis_8_server()
    prefix = f"industry-resilience-redis8-{uuid.uuid4().hex}"
    client_a = fakeredis.FakeRedis(server=server, protocol=3)
    client_b = fakeredis.FakeRedis(server=server, protocol=3)
    rule = RateLimitRule.per_window(1, 60, scope="redis8:fakeredis")

    service_a = RateLimiterService(
        RedisTokenBucket(client=client_a, key_prefix=prefix, ttl_seconds=120)
    )
    service_b = RateLimiterService(
        RedisTokenBucket(client=client_b, key_prefix=prefix, ttl_seconds=120)
    )

    assert service_a.enforce("shared", rule).allowed is True
    blocked = service_b.enforce("shared", rule)

    assert blocked.allowed is False
    assert blocked.backend == "redis"
    assert blocked.retry_after_seconds is not None
    assert server.version == (8,)


def test_fakeredis_redis_8_disconnect_preserves_memory_fallback() -> None:
    server = _fake_redis_8_server()
    client = fakeredis.FakeRedis(server=server)
    backend = RedisTokenBucket(
        client=client,
        key_prefix=f"industry-resilience-fallback-{uuid.uuid4().hex}",
        ttl_seconds=60,
    )
    rule = RateLimitRule.per_window(1, 60, scope="redis8:fallback")

    assert backend.acquire("before-disconnect", rule).allowed is True
    server.connected = False
    decision = backend.acquire("after-disconnect", rule)

    assert decision.allowed is True
    assert decision.backend == "redis-fallback"
    assert backend.summary()["mode"] == "redis-fallback"
    assert backend.summary()["fallback"] == "memory"
    assert backend.summary()["last_error"]


def test_fakeredis_redis_8_async_resp3_smoke() -> None:
    async def exercise() -> None:
        server = _fake_redis_8_server()
        client = fakeredis.FakeAsyncRedis(server=server, protocol=3)
        key = f"industry-resilience-async-{uuid.uuid4().hex}"
        try:
            assert await client.ping() is True
            assert await client.set(key, "ok") is True
            assert await client.get(key) == b"ok"
            assert server.version == (8,)
        finally:
            await client.aclose()

    asyncio.run(exercise())


@pytest.mark.skipif(
    not os.environ.get("REDIS_COMPAT_URL"),
    reason="REDIS_COMPAT_URL is required for the real Redis 8 compatibility smoke",
)
def test_real_redis_8_runs_shared_lua_token_bucket_with_resp3() -> None:
    redis_url = os.environ["REDIS_COMPAT_URL"]
    prefix = f"industry-resilience-real-redis8-{uuid.uuid4().hex}"
    redis_key = f"{prefix}:shared"
    client_a = redis.Redis.from_url(redis_url, protocol=3, socket_timeout=2.0)
    client_b = redis.Redis.from_url(redis_url, protocol=3, socket_timeout=2.0)
    rule = RateLimitRule.per_window(1, 60, scope="redis8:real")

    try:
        server_info = client_a.info(section="server")
        assert int(str(server_info["redis_version"]).split(".", 1)[0]) == 8

        service_a = RateLimiterService(
            RedisTokenBucket(client=client_a, key_prefix=prefix, ttl_seconds=120)
        )
        service_b = RateLimiterService(
            RedisTokenBucket(client=client_b, key_prefix=prefix, ttl_seconds=120)
        )

        assert service_a.enforce("shared", rule).allowed is True
        blocked = service_b.enforce("shared", rule)
        assert blocked.allowed is False
        assert blocked.backend == "redis"
        assert blocked.retry_after_seconds is not None
    finally:
        client_a.delete(redis_key)
        client_a.close()
        client_b.close()
