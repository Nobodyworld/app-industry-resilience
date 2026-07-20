"""Synchronous TestClient compatible with the local FastAPI façade."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

from . import FastAPI


@dataclass
class _TestResponse:
    status_code: int
    data: Any
    media_type: str | None = None
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        return self.data

    @property
    def text(self) -> str:
        if isinstance(self.data, str):
            return self.data
        if isinstance(self.data, bytes):
            return self.data.decode("utf-8")
        return json.dumps(self.data)


class TestClient:
    """Simple client used by the test-suite to exercise the API."""

    __test__ = False  # Prevent pytest from collecting this helper as a test class.

    def __init__(self, app: FastAPI):
        self.app = app

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> _TestResponse:
        if params:
            query = urlencode([(key, value) for key, value in params.items() if value is not None])
            if query:
                separator = "&" if "?" in path else "?"
                path = f"{path}{separator}{query}"
        response = self.app.handle_request("GET", path)
        return _TestResponse(
            status_code=response.status_code,
            data=response.json(),
            media_type=response.media_type,
            headers=dict(response.headers),
        )

    def post(self, path: str, *, json: Any | None = None) -> _TestResponse:
        response = self.app.handle_request("POST", path, payload=json)
        return _TestResponse(
            status_code=response.status_code,
            data=response.json(),
            media_type=response.media_type,
            headers=dict(response.headers),
        )


__all__ = ["TestClient"]
