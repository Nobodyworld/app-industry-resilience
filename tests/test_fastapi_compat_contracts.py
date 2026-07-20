"""Contract metadata tests for the local FastAPI-compatible façade."""

from __future__ import annotations

import io
from typing import Literal

from fastapi_compat import FastAPI, Response
from fastapi_compat.testclient import TestClient
from pydantic_compat import BaseModel, Field


class EchoRequest(BaseModel):
    value: str = Field(..., description="Value to echo.")
    mode: Literal["plain", "upper"] = "plain"


class EchoResponse(BaseModel):
    value: str
    count: int


def test_testclient_exposes_response_headers() -> None:
    app = FastAPI()

    @app.get("/legacy")
    def legacy() -> Response:
        return Response(
            status_code=200,
            data={"status": "ok"},
            headers={
                "Deprecation": "true",
                "Sunset": "Thu, 15 Jan 2027 00:00:00 GMT",
                "Link": '</v1/legacy>; rel="successor-version"',
            },
        )

    response = TestClient(app).get("/legacy")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers == {
        "Deprecation": "true",
        "Sunset": "Thu, 15 Jan 2027 00:00:00 GMT",
        "Link": '</v1/legacy>; rel="successor-version"',
    }


def test_wsgi_includes_custom_response_headers() -> None:
    app = FastAPI()

    @app.get("/legacy")
    def legacy() -> Response:
        return Response(
            status_code=200,
            data={"status": "ok"},
            headers={"Deprecation": "true"},
        )

    headers: list[tuple[str, str]] = []

    def start_response(_status: str, response_headers: list[tuple[str, str]]) -> None:
        headers.extend(response_headers)

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/legacy",
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(b""),
    }

    body = b"".join(app(environ, start_response))

    assert body
    assert ("Deprecation", "true") in headers
    assert ("Content-Type", "application/json") in headers


def test_openapi_records_deprecation_models_tags_and_required_fields() -> None:
    app = FastAPI(title="Contract API", version="1.2.3")

    @app.post(
        "/echo",
        response_model=EchoResponse,
        tags=["echo"],
        deprecated=True,
        status_code=200,
    )
    def echo(request: EchoRequest) -> EchoResponse:
        value = request.value.upper() if request.mode == "upper" else request.value
        return EchoResponse(value=value, count=len(value))

    document = app.openapi()
    operation = document["paths"]["/echo"]["post"]

    assert document["openapi"] == "3.1.0"
    assert document["info"] == {"title": "Contract API", "version": "1.2.3"}
    assert operation["deprecated"] is True
    assert operation["tags"] == ["echo"]
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/EchoRequest"
    }
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/EchoResponse"
    }

    request_schema = document["components"]["schemas"]["EchoRequest"]
    response_schema = document["components"]["schemas"]["EchoResponse"]
    assert request_schema["required"] == ["value"]
    assert request_schema["properties"]["value"] == {
        "type": "string",
        "description": "Value to echo.",
    }
    assert request_schema["properties"]["mode"] == {"enum": ["plain", "upper"]}
    assert response_schema["required"] == ["value", "count"]
    assert response_schema["properties"]["value"] == {"type": "string"}
    assert response_schema["properties"]["count"] == {"type": "integer"}


def test_openapi_is_deterministic_and_does_not_execute_handlers() -> None:
    app = FastAPI(title="Contract API", version="1")
    calls = 0

    @app.get("/status", response_model=EchoResponse)
    def status_endpoint() -> EchoResponse:
        nonlocal calls
        calls += 1
        return EchoResponse(value="ok", count=1)

    first = app.openapi()
    second = app.openapi()

    assert first == second
    assert calls == 0
