"""Exercise the application's Redis client, including bounded local fault injection."""

from __future__ import annotations

import os
import socket
import threading
import time
import uuid

import pytest
import redis

from src.core.config import load_config
from src.infrastructure.rate_limiter import (
    RateLimiterService,
    RateLimitRule,
    RedisTokenBucket,
    _create_redis_client,
)


def production_client(**env: str) -> redis.Redis:
    cfg = load_config({"RATE_LIMIT_BACKEND": "redis", **env}).rate_limits.distributed
    assert cfg is not None
    return _create_redis_client(cfg)


@pytest.mark.parametrize("timeout", [None, "0.05", "2.5"])
def test_production_client_explicit_timeouts_and_zero_retries(timeout) -> None:
    env = {} if timeout is None else {"RATE_LIMIT_REDIS_TIMEOUT_SECONDS": timeout}
    client = production_client(**env)
    try:
        settings = client.connection_pool.connection_kwargs
        expected = 1.0 if timeout is None else float(timeout)
        assert settings["socket_timeout"] == expected
        assert settings["socket_connect_timeout"] == expected
        assert settings["retry"].get_retries() == 0
        assert settings["retry_on_error"] == []
    finally:
        client.close()


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf"])
def test_production_client_rejects_unbounded_timeout(timeout) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        production_client(RATE_LIMIT_REDIS_TIMEOUT_SECONDS=timeout)


def test_production_client_connection_failure_attempts_once(monkeypatch) -> None:
    attempts = 0
    original_connect = redis.connection.Connection._connect

    def connect(connection):
        nonlocal attempts
        attempts += 1
        return original_connect(connection)

    monkeypatch.setattr(redis.connection.Connection, "_connect", connect)
    # Reserve the port without listening so no unrelated local service can claim it.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        client = production_client(
            RATE_LIMIT_REDIS_HOST="127.0.0.1",
            RATE_LIMIT_REDIS_PORT=str(reserved.getsockname()[1]),
            RATE_LIMIT_REDIS_TIMEOUT_SECONDS="0.05",
        )
        try:
            bucket = RedisTokenBucket(client=client, key_prefix="refused-test", ttl_seconds=60)
            start = time.monotonic()
            decision = bucket.acquire("key", RateLimitRule.per_window(1, 60, "refused"))
            elapsed = time.monotonic() - start
            assert decision.backend == "redis-fallback"
            assert decision.allowed is True
            assert attempts == 1
            assert elapsed < 1.0
        finally:
            client.close()


def test_production_client_stalled_response_reaches_fallback_promptly() -> None:
    accepted = threading.Event()
    release = threading.Event()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(2.0)

        def stall() -> None:
            try:
                connection, _ = listener.accept()
            except OSError:
                return
            with connection:
                accepted.set()
                release.wait(3.0)

        worker = threading.Thread(target=stall, daemon=True)
        worker.start()
        client = production_client(
            RATE_LIMIT_REDIS_HOST="127.0.0.1",
            RATE_LIMIT_REDIS_PORT=str(listener.getsockname()[1]),
            RATE_LIMIT_REDIS_TIMEOUT_SECONDS="0.05",
        )
        try:
            bucket = RedisTokenBucket(client=client, key_prefix="stalled-test", ttl_seconds=60)
            start = time.monotonic()
            decision = bucket.acquire("key", RateLimitRule.per_window(1, 60, "stalled"))
            elapsed = time.monotonic() - start
            assert accepted.is_set()
            assert decision.backend == "redis-fallback"
            assert bucket.summary()["last_error"]
            assert elapsed < 1.0
        finally:
            client.close()
            release.set()
            worker.join(timeout=3.0)
        assert not worker.is_alive()


@pytest.mark.skipif(
    not os.environ.get("REDIS_COMPAT_URL"),
    reason="REDIS_COMPAT_URL must identify a task-owned real Redis 8 service",
)
@pytest.mark.parametrize("failure_type", [redis.ConnectionError, redis.TimeoutError])
def test_real_production_client_recovers_without_replaying_lua(monkeypatch, failure_type) -> None:
    # Only task-owned services are permitted; cleanup removes exact unique keys, never databases.
    env = {
        "RATE_LIMIT_REDIS_URL": os.environ["REDIS_COMPAT_URL"],
        "RATE_LIMIT_REDIS_TIMEOUT_SECONDS": "0.1",
    }
    client = production_client(**env)
    observer = production_client(**env)
    prefix = f"industry-resilience-fault-{uuid.uuid4().hex}"
    bucket = RedisTokenBucket(client=client, key_prefix=prefix, ttl_seconds=120)
    service = RateLimiterService(bucket)
    rule = RateLimitRule.per_window(2, 60, "lost-reply")
    calls = 0
    original_parse = client.parse_response

    def lose_first_lua_reply(connection, command_name, **options):
        nonlocal calls
        response = original_parse(connection, command_name, **options)
        if command_name == "EVALSHA":
            calls += 1
            if calls == 1:
                # The server has applied the mutation, but the caller cannot know that.
                raise failure_type("controlled lost Lua reply")
        return response

    try:
        assert str(observer.info("server")["redis_version"]).split(".")[0] == "8"
        assert service.enforce("warmup", rule).backend == "redis"
        # Warmup loaded the script, so NOSCRIPT recovery cannot obscure the replay count.
        monkeypatch.setattr(client, "parse_response", lose_first_lua_reply)
        start = time.monotonic()
        decision = service.enforce("shared", rule)
        elapsed = time.monotonic() - start
        assert decision.allowed is True
        assert decision.backend == "redis-fallback"
        assert service.summary()["last_error"]
        assert calls == 1
        assert elapsed < 1.0
        assert float(observer.hget(f"{prefix}:shared", "tokens")) == pytest.approx(1.0)

        recovered = service.enforce("shared", rule)
        assert recovered.allowed is True
        assert recovered.backend == "redis"
        assert service.summary()["last_error"] is None
        assert calls == 2
        other = RateLimiterService(
            RedisTokenBucket(client=observer, key_prefix=prefix, ttl_seconds=120)
        )
        assert other.enforce("shared", rule).allowed is False
    finally:
        try:
            observer.delete(f"{prefix}:warmup", f"{prefix}:shared")
            assert observer.exists(f"{prefix}:warmup", f"{prefix}:shared") == 0
        finally:
            client.close()
            observer.close()
