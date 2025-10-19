"""File-system backed caching utilities used across the application."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import CacheConfig, load_config


@dataclass(frozen=True)
class CacheStats:
    """Summary information for cache inspection and tests."""

    files: int
    total_size_bytes: int


class Cache:
    """Simple JSON-file cache with time-based expiration.

    The cache stores JSON-serialisable values on disk so data is preserved across
    restarts. Each entry is written atomically to avoid corrupted files and is
    automatically expired based on its configured TTL.
    """

    def __init__(self, cache_dir: Path, ttl_seconds: int) -> None:
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _path_for_key(self, key: str) -> Path:
        hashed = _stable_hash(key)
        return self.cache_dir / f"{hashed}.json"

    def get(self, key: str) -> Any | None:
        path = self._path_for_key(key)
        if not path.exists():
            return None
        with self._lock:
            try:
                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except (json.JSONDecodeError, OSError):
                _safe_unlink(path)
                return None

            if _is_expired(payload.get("timestamp"), self.ttl_seconds):
                _safe_unlink(path)
                return None

            return payload.get("value")

    def set(self, key: str, value: Any) -> None:
        path = self._path_for_key(key)
        payload = {"timestamp": time.time(), "value": value}
        tmp_path = path.with_suffix(".tmp")
        with self._lock:
            try:
                with tmp_path.open("w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False)
                tmp_path.replace(path)
            except OSError:
                _safe_unlink(tmp_path)

    def clear(self) -> None:
        with self._lock:
            for file in self.cache_dir.glob("*.json"):
                _safe_unlink(file)

    def stats(self) -> CacheStats:
        files = [file for file in self.cache_dir.glob("*.json") if file.exists()]
        total_size = sum(file.stat().st_size for file in files)
        return CacheStats(files=len(files), total_size_bytes=total_size)


_api_cache: Cache | None = None
_computation_cache: Cache | None = None
_api_lock = threading.Lock()
_computation_lock = threading.Lock()


def get_api_cache(cache_config: CacheConfig | None = None) -> Cache | None:
    """Return a cache instance for API responses."""

    global _api_cache
    config = cache_config or load_config().cache
    if not config.enabled:
        return None
    with _api_lock:
        if _api_cache is None or _api_cache.ttl_seconds != config.api_ttl_seconds:
            _api_cache = Cache(config.api_cache_dir(), config.api_ttl_seconds)
        return _api_cache


def get_computation_cache(cache_config: CacheConfig | None = None) -> Cache | None:
    """Return a cache instance for expensive metric calculations."""

    global _computation_cache
    config = cache_config or load_config().cache
    if not config.enabled:
        return None
    with _computation_lock:
        if (
            _computation_cache is None
            or _computation_cache.ttl_seconds != config.computation_ttl_seconds
        ):
            _computation_cache = Cache(
                config.computation_cache_dir(), config.computation_ttl_seconds
            )
        return _computation_cache


def _stable_hash(value: str) -> str:
    # Use a deterministic hash that is stable between interpreter sessions.
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def _is_expired(timestamp: float | None, ttl_seconds: int) -> bool:
    if timestamp is None:
        return True
    return (time.time() - float(timestamp)) > ttl_seconds


__all__ = ["Cache", "CacheStats", "get_api_cache", "get_computation_cache"]

