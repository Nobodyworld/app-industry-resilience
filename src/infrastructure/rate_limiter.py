"""Distributed and in-memory rate limiter implementations."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass, field

try:  # pragma: no cover - optional dependency
    import redis
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover - redis optional
    redis = None
    RedisError = Exception

from src.core import DistributedRateLimitConfig, RateLimitConfig, load_config
from src.core.security import RateLimitDecision, SecurityUtils
from src.infrastructure.observability.metrics import Counter, Histogram

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitRule:
    """Token bucket rule describing capacity and refill semantics."""

    max_tokens: float
    refill_rate: float  # tokens per second
    scope: str

    @classmethod
    def per_window(cls, max_requests: int, window_seconds: int, scope: str) -> RateLimitRule:
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if not scope or not scope.strip():
            raise ValueError("scope must be a non-empty string")
        return cls(
            max_tokens=float(max_requests),
            refill_rate=max_requests / float(window_seconds),
            scope=scope.strip(),
        )


@dataclass(frozen=True)
class _Metrics:
    requests: Counter
    wait_seconds: Histogram


_METRICS: _Metrics | None = None


def configure_metrics(counter: Counter, wait_histogram: Histogram) -> None:
    """Inject metric primitives used by rate limiters."""

    global _METRICS
    _METRICS = _Metrics(counter, wait_histogram)


def _record_decision(
    rule: RateLimitRule, decision: RateLimitDecision, waited: float | None = None
) -> None:
    if _METRICS is None:
        return
    outcome = "allow" if decision.allowed else "block"
    _METRICS.requests.increment(
        labels={
            "scope": rule.scope,
            "backend": decision.backend,
            "outcome": outcome,
        }
    )
    if waited is not None and waited > 0:
        _METRICS.wait_seconds.observe(
            waited,
            labels={
                "scope": rule.scope,
                "backend": decision.backend,
            },
        )


class TokenBucketBackend:
    """Interface for token bucket implementations."""

    backend_name: str = "memory"

    def acquire(self, key: str, rule: RateLimitRule) -> RateLimitDecision:
        raise NotImplementedError

    def wait(self, key: str, rule: RateLimitRule) -> RateLimitDecision:
        """Block until a token becomes available for ``key``."""

        sleep_cap = 5.0
        while True:
            decision = self.acquire(key, rule)
            if decision.allowed:
                return decision

            retry = decision.retry_after_seconds
            if retry is not None and retry > 0:
                delay = min(retry, sleep_cap)
            else:
                delay = min(1.0 / max(rule.refill_rate, 1e-6), sleep_cap)

            if delay > 0:
                time.sleep(delay)

    def summary(self) -> dict[str, object]:
        return {"mode": self.backend_name}


@dataclass
class InMemoryTokenBucket(TokenBucketBackend):
    """Thread-safe in-process token bucket backend."""

    backend_name: str = "memory"
    _state: MutableMapping[str, tuple[float, float]] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def acquire(self, key: str, rule: RateLimitRule) -> RateLimitDecision:
        with self._lock:
            tokens, last_ts = self._state.get(key, (rule.max_tokens, time.time()))
            now = time.time()
            elapsed = max(0.0, now - last_ts)
            tokens = min(rule.max_tokens, tokens + elapsed * rule.refill_rate)
            allowed = tokens >= 1.0
            if allowed:
                tokens -= 1.0
                retry_after: float | None = 0.0
            else:
                retry_after = (1.0 - tokens) / rule.refill_rate if rule.refill_rate else None
            self._state[key] = (tokens, now)
        return RateLimitDecision(
            allowed=allowed,
            remaining_tokens=tokens,
            retry_after_seconds=retry_after,
            backend=self.backend_name,
        )


_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local ttl_seconds = tonumber(ARGV[5])
local data = redis.call('HMGET', key, 'tokens', 'timestamp')
local tokens = tonumber(data[1])
local last = tonumber(data[2])
if tokens == nil then
  tokens = max_tokens
  last = now
end
local delta = now - last
if delta < 0 then
  delta = 0
end
tokens = math.min(max_tokens, tokens + (delta * refill_rate))
local allowed = 0
local retry_after = 0
if tokens >= requested then
  allowed = 1
  tokens = tokens - requested
else
  local needed = requested - tokens
  if refill_rate > 0 then
    retry_after = needed / refill_rate
  else
    retry_after = ttl_seconds
  end
end
redis.call('HMSET', key, 'tokens', tokens, 'timestamp', now)
if ttl_seconds > 0 then
  redis.call('EXPIRE', key, math.ceil(ttl_seconds))
end
return {allowed, tokens, retry_after}
"""


@dataclass
class RedisTokenBucket(TokenBucketBackend):
    """Redis-backed token bucket with optional in-memory fallback."""

    client: redis.Redis
    key_prefix: str
    ttl_seconds: float
    backend_name: str = "redis"
    _script: Callable[..., list[float | int]] = field(init=False, repr=False)
    _fallback: InMemoryTokenBucket = field(default_factory=InMemoryTokenBucket, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _last_error: str | None = field(default=None, init=False)
    _last_success: float | None = field(default=None, init=False)
    _active_backend: str = field(default="redis", init=False)

    def __post_init__(self) -> None:
        self._script = self.client.register_script(_TOKEN_BUCKET_LUA)

    def _redis_key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def acquire(self, key: str, rule: RateLimitRule) -> RateLimitDecision:
        redis_key = self._redis_key(key)
        try:
            response = self._script(
                keys=[redis_key],
                args=[
                    rule.max_tokens,
                    rule.refill_rate,
                    time.time(),
                    1.0,
                    max(self.ttl_seconds, 1.0),
                ],
            )
            allowed = bool(int(response[0]))
            tokens = float(response[1])
            retry_after = float(response[2]) if response[2] is not None else None
            self._last_error = None
            self._last_success = time.time()
            self._active_backend = self.backend_name
            return RateLimitDecision(
                allowed=allowed,
                remaining_tokens=tokens,
                retry_after_seconds=retry_after,
                backend=self.backend_name,
            )
        except RedisError as exc:  # pragma: no cover - redis failure paths
            self._last_error = str(exc)
            LOGGER.warning("Redis rate limiter failed; falling back to memory", exc_info=exc)
            fallback = self._fallback.acquire(key, rule)
            self._active_backend = f"{self.backend_name}-fallback"
            return RateLimitDecision(
                allowed=fallback.allowed,
                remaining_tokens=fallback.remaining_tokens,
                retry_after_seconds=fallback.retry_after_seconds,
                backend=self._active_backend,
            )

    def summary(self) -> dict[str, object]:
        return {
            "mode": self._active_backend,
            "backend": self.backend_name,
            "last_error": self._last_error,
            "last_success": self._last_success,
            "fallback": self._fallback.backend_name,
        }


class RateLimiterService:
    """Coordinate rate limiting for APIs and security guards."""

    def __init__(self, backend: TokenBucketBackend) -> None:
        self._backend = backend

    def enforce(self, identifier: str, rule: RateLimitRule) -> RateLimitDecision:
        decision = self._backend.acquire(identifier, rule)
        _record_decision(rule, decision)
        return decision

    def wait(self, identifier: str, rule: RateLimitRule) -> None:
        start = time.time()
        decision = self._backend.wait(identifier, rule)
        waited = max(0.0, time.time() - start)
        _record_decision(rule, decision, waited if decision.allowed else waited)

    def summary(self) -> dict[str, object]:
        return self._backend.summary()


class _SecurityHandler:
    """Callable wrapper exposing a summary hook for SecurityUtils."""

    def __init__(self, service: RateLimiterService) -> None:
        self._service = service

    def __call__(
        self, identifier: str, max_requests: int, window_seconds: int
    ) -> RateLimitDecision:
        rule = RateLimitRule.per_window(max_requests, window_seconds, scope="security")
        key = f"security:{identifier}"
        return self._service.enforce(key, rule)

    def summary(self) -> dict[str, object]:
        return self._service.summary()


class APIRateLimiter:
    """Facade around token bucket enforcement for external APIs."""

    def __init__(
        self, config: RateLimitConfig | None = None, service: RateLimiterService | None = None
    ) -> None:
        self._config = config or load_config().rate_limits
        self._service = service or _build_service(self._config)
        self._security_adapter = _SecurityHandler(self._service)
        handler_summary = self._security_adapter.summary()
        backend_mode = handler_summary.get("backend") or handler_summary.get("mode", "memory")
        SecurityUtils.register_rate_limit_handler(
            self._security_adapter,
            backend_name=str(backend_mode),
        )

    def _rule_for(self, api: str) -> RateLimitRule:
        per_minute = self._config.as_dict().get(api, self._config.default)
        return RateLimitRule.per_window(per_minute, 60, scope=f"api:{api}")

    def wait_for_api(self, api_name: str) -> None:
        key = api_name.lower()
        rule = self._rule_for(key)
        identifier = f"api:{key}"
        self._service.wait(identifier, rule)

    def status(self) -> dict[str, object]:
        return self._service.summary()


_API_LIMITER_SINGLETON: APIRateLimiter | None = None


def get_api_limiter() -> APIRateLimiter:
    """Return the singleton API limiter."""

    global _API_LIMITER_SINGLETON
    if _API_LIMITER_SINGLETON is None:
        _API_LIMITER_SINGLETON = APIRateLimiter()
    return _API_LIMITER_SINGLETON


def _build_service(config: RateLimitConfig) -> RateLimiterService:
    backend = _build_backend(config)
    return RateLimiterService(backend)


def _build_backend(config: RateLimitConfig) -> TokenBucketBackend:
    backend_cfg = getattr(config, "distributed", None)
    if backend_cfg and backend_cfg.enabled:
        if redis is None:
            LOGGER.warning(
                "Redis backend requested but redis package unavailable; falling back to memory"
            )
            return InMemoryTokenBucket()
        client = _create_redis_client(backend_cfg)
        return RedisTokenBucket(
            client=client,
            key_prefix=backend_cfg.key_prefix,
            ttl_seconds=max(backend_cfg.window_seconds, 60.0),
        )
    return InMemoryTokenBucket()


def _create_redis_client(cfg: DistributedRateLimitConfig) -> redis.Redis:
    kwargs: dict[str, object] = {
        "host": cfg.host,
        "port": cfg.port,
        "db": cfg.db,
        "ssl": cfg.ssl,
    }
    if cfg.username:
        kwargs["username"] = cfg.username
    if cfg.password:
        kwargs["password"] = cfg.password
    if cfg.socket_timeout is not None:
        kwargs["socket_timeout"] = cfg.socket_timeout
    return redis.Redis(**kwargs)


api_limiter = get_api_limiter()
RateLimiter = APIRateLimiter


__all__ = [
    "APIRateLimiter",
    "DistributedRateLimitConfig",
    "RateLimitDecision",
    "RateLimitRule",
    "RateLimiter",
    "RateLimiterService",
    "configure_metrics",
    "get_api_limiter",
    "api_limiter",
]


def _reset_for_tests() -> None:
    """Reset singletons for deterministic testing."""

    global _API_LIMITER_SINGLETON
    _API_LIMITER_SINGLETON = None
    global _METRICS
    _METRICS = None
