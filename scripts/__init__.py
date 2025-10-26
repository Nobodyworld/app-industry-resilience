"""Utility scripts for Idiot Index development workflows."""

from __future__ import annotations

# The `_bootstrap` module ensures repo-relative imports resolve when scripts are executed
# directly via ``python scripts/<name>.py``.
from . import _bootstrap as _bootstrap  # noqa: F401

__all__ = ["_bootstrap"]
