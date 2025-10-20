"""Compatibility module for BEA adapter legacy path."""

from ..adapters.bea import *  # noqa: F401,F403
from ..adapters.bea import __all__ as _adapter_all
from ..core import get_api_cache, safe_get_json  # legacy patch targets

__all__ = [*_adapter_all, "get_api_cache", "safe_get_json"]
