from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from unittest.mock import patch

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

    with patch.object(app, "handle_request", wraps=app.handle_request) as handle_request:
        body_chunks = app(environ, start_response)
    body = b"".join(body_chunks).decode("utf-8")
    payload = json.loads(body)

    assert handle_request.call_args.args[1] == "/health"
    assert status_line.startswith("200")
    assert ("Content-Type", "application/json") in headers
    assert payload["status"] == "ok"
    assert payload["checked_at"] == "2026-06-28T12:00:00+00:00"


def test_wsgi_forwards_query_string_to_request_handler() -> None:
    app = FastAPI()

    @app.get("/items")
    def items(limit: int = 10, label: str = "") -> dict[str, int | str]:
        return {"limit": limit, "label": label}

    status_line = ""

    def start_response(status: str, _response_headers: list[tuple[str, str]]) -> None:
        nonlocal status_line
        status_line = status

    query_string = "limit=3&label=hello%20world%2Fv1"
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/items",
        "QUERY_STRING": query_string,
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(b""),
    }

    with patch.object(app, "handle_request", wraps=app.handle_request) as handle_request:
        body = b"".join(app(environ, start_response))

    assert handle_request.call_args.args[1] == f"/items?{query_string}"
    assert status_line.startswith("200")
    assert json.loads(body) == {"limit": 3, "label": "hello world/v1"}


def test_industry_pulse_filters_are_applied_through_wsgi() -> None:
    from src.interfaces.api.app import app

    statuses: list[str] = []

    def start_response(status: str, _response_headers: list[tuple[str, str]]) -> None:
        statuses.append(status)

    filtered_body = b"".join(
        app(
            {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": "/v1/context/signals/311111",
                "QUERY_STRING": "start=2025-01&end=2025-06&limit=3",
                "CONTENT_LENGTH": "0",
                "wsgi.input": io.BytesIO(b""),
            },
            start_response,
        )
    )
    series_body = b"".join(
        app(
            {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": "/v1/context/signals",
                "QUERY_STRING": "series_id=PCU311111311111&limit=2",
                "CONTENT_LENGTH": "0",
                "wsgi.input": io.BytesIO(b""),
            },
            start_response,
        )
    )

    filtered = json.loads(filtered_body)
    series = json.loads(series_body)
    assert statuses == ["200 OK", "200 OK"]
    assert [row["observation_date"] for row in filtered["observations"]] == [
        "2025-04-01",
        "2025-05-01",
        "2025-06-01",
    ]
    assert series["count"] == 1
    assert len(series["signals"][0]["observations"]) == 2
