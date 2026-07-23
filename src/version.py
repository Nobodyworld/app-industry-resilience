"""Project version helpers."""

from __future__ import annotations

from importlib import metadata

try:
    __version__ = metadata.version("industry-resilience-dashboard")
except metadata.PackageNotFoundError:  # pragma: no cover - fallback during local execution
    __version__ = "0.2.0rc1"

__all__ = ["__version__"]
