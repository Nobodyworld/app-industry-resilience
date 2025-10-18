import json
import hashlib
import time
from typing import Any, Optional, Dict
from pathlib import Path

class Cache:
    """Simple file-based cache for API responses and computations."""

    def __init__(self, cache_dir: str = ".cache", ttl_seconds: int = 3600):
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # TODO - Implement cache size limits and automatic cleanup policies
    # TODO - Add cache encryption for sensitive data storage
    # TODO - Implement distributed cache support (Redis, Memcached)

    def _get_cache_key(self, key: str) -> str:
        """Generate a safe cache key from the input key."""
        return hashlib.md5(key.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key."""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache if it exists and hasn't expired."""
        cache_key = self._get_cache_key(key)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)

            # Check if cache has expired
            if time.time() - data['timestamp'] > self.ttl_seconds:
                cache_path.unlink()  # Remove expired cache
                return None

            return data['value']

        except (json.JSONDecodeError, KeyError, OSError):
            # Invalid cache file, remove it
            if cache_path.exists():
                cache_path.unlink()
            return None

    # TODO - Implement cache hit/miss statistics and performance monitoring
    # TODO - Add cache compression for large data structures
    # TODO - Implement cache invalidation strategies and cache tags

    def set(self, key: str, value: Any) -> None:
        """Store value in cache."""
        cache_key = self._get_cache_key(key)
        cache_path = self._get_cache_path(cache_key)

        data = {
            'timestamp': time.time(),
            'value': value
        }

        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2)
        except OSError:
            # If we can't write to cache, just continue
            pass

    def clear(self) -> None:
        """Clear all cached data."""
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except OSError:
                pass

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        cache_files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files if f.exists()) 

        return {
            'files': len(cache_files),
            'total_size_bytes': total_size
        }

# TODO - Implement cache persistence across application restarts
# TODO - Add cache backup and restore functionality
# TODO - Implement cache warming and preloading strategies# Global cache instances - lazy initialization
_api_cache = None
_computation_cache = None

def get_api_cache():
    global _api_cache
    if _api_cache is None:
        _api_cache = Cache(cache_dir=".cache/api", ttl_seconds=3600)  # 1 hour for API responses
    return _api_cache

def get_computation_cache():
    global _computation_cache
    if _computation_cache is None:
        _computation_cache = Cache(cache_dir=".cache/computation", ttl_seconds=1800)  # 30 minutes for computations
    return _computation_cache

# For backward compatibility
api_cache = None  # Will be set when first accessed
computation_cache = None  # Will be set when first accessed