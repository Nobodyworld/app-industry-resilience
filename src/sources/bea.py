"""Compatibility module for BEA adapter legacy path."""

from ..adapters.bea import *  # noqa: F401,F403
from ..core import get_api_cache, safe_get_json  # legacy patch targets

try:
    __all__ = [*__all__, "get_api_cache", "safe_get_json"]  # type: ignore[name-defined]
except NameError:  # pragma: no cover - defensive
    __all__ = ["get_api_cache", "safe_get_json"]
