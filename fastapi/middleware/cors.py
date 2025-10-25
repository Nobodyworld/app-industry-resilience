"""CORS middleware placeholder for compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(slots=True)
class CORSMiddleware:  # pragma: no cover - behaviour is a no-op placeholder
    app: Any
    allow_origins: Iterable[str] | None = None
    allow_methods: Iterable[str] | None = None
    allow_headers: Iterable[str] | None = None
    allow_credentials: bool = False

    def __call__(self, scope: Any) -> Any:
        return self.app(scope)


__all__ = ["CORSMiddleware"]

