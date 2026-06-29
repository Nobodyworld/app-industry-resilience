from __future__ import annotations

import io
import json
from datetime import UTC, datetime

from fastapi_compat import FastAPI


def test_wsgi_serializes_datetime_payloads() -> None:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "checked_at": datetime(2026, 6, 28, 12, 0, tzinfo=UTC)}

    headers: list[tuple[str, str]] = []
    status_line = ""

    def start_response(status: str, response_headers: list[tuple[str, str]]) -> None:
        nonlocal status_line, headers
        status_line = status
        headers = response_headers

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/health",
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(b""),
    }

    body_chunks = app(environ, start_response)
    body = b"".join(body_chunks).decode("utf-8")
    payload = json.loads(body)

    assert status_line.startswith("200")
    assert ("Content-Type", "application/json") in headers
    assert payload["status"] == "ok"
    assert payload["checked_at"] == "2026-06-28T12:00:00+00:00"
