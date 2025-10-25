"""Minimal FastAPI-compatible façade used for offline testing.

The real project originally depended on the external :mod:`fastapi` package.
Network restrictions in the execution environment make downloading that
dependency unreliable, so this module implements the small subset of the API
required by the Idiot Index service.  It supports route registration, simple
dependency injection via :class:`Depends`, and error handling compatible with
``fastapi.testclient`` semantics.

Only the functions used by the code base are exposed.  When running the
``scripts/run_api.py`` helper the same implementation is used to execute
requests without relying on third-party servers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Iterable

from pydantic import BaseModel, ValidationError

__all__ = [
    "Depends",
    "FastAPI",
    "HTTPException",
    "Response",
    "status",
]


class HTTPException(Exception):
    """Exception representing an HTTP error."""

    def __init__(self, status_code: int, detail: Any | None = None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class Depends:
    """Descriptor indicating a callable dependency."""

    def __init__(self, dependency: Callable[[], Any]):
        self.dependency = dependency


@dataclass(slots=True)
class Route:
    method: str
    path: str
    endpoint: Callable[..., Any]
    status_code: int


@dataclass(slots=True)
class Response:
    """Simple response container returned by the app."""

    status_code: int
    data: Any
    media_type: str | None = None

    def json(self) -> Any:
        return self.data


class FastAPI:
    """Register HTTP routes and execute them synchronously."""

    def __init__(self, *, title: str = "", version: str = "") -> None:
        self.title = title
        self.version = version
        self._routes: list[Route] = []
        self._middleware: list[tuple[type[Any], dict[str, Any]]] = []

    # ------------------------------------------------------------------
    # Route registration helpers
    # ------------------------------------------------------------------
    def get(
        self,
        path: str,
        *,
        response_model: type[Any] | None = None,
        tags: Iterable[str] | None = None,
        status_code: int = 200,
    ):
        del response_model, tags  # Provided for parity only.

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._routes.append(Route("GET", path, func, status_code))
            return func

        return decorator

    def post(
        self,
        path: str,
        *,
        response_model: type[Any] | None = None,
        tags: Iterable[str] | None = None,
        status_code: int = 200,
    ):
        del response_model, tags  # Provided for parity only.

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._routes.append(Route("POST", path, func, status_code))
            return func

        return decorator

    # ------------------------------------------------------------------
    # Middleware registration (no-op for compatibility)
    # ------------------------------------------------------------------
    def add_middleware(self, middleware_cls: type[Any], **options: Any) -> None:
        self._middleware.append((middleware_cls, options))

    # ------------------------------------------------------------------
    # Request execution
    # ------------------------------------------------------------------
    def handle_request(self, method: str, path: str, payload: Any | None = None) -> Response:
        route = next(
            (item for item in self._routes if item.method == method and item.path == path), None
        )
        if route is None:
            return Response(status_code=404, data={"detail": "Not Found"})

        try:
            kwargs = _build_kwargs(route.endpoint, payload)
            result = route.endpoint(**kwargs)
            if isinstance(result, Response):
                return result
            data = _serialise_response(result)
            return Response(status_code=route.status_code, data=data)
        except HTTPException as exc:
            detail = exc.detail if exc.detail is not None else "Error"
            return Response(status_code=exc.status_code, data={"detail": detail})
        except ValidationError as exc:
            return Response(status_code=422, data={"detail": exc.errors})

    # ------------------------------------------------------------------
    # WSGI-compatible entry point used by the CLI server
    # ------------------------------------------------------------------
    def __call__(
        self, environ: dict[str, Any], start_response: Callable[..., Any]
    ):  # pragma: no cover - exercised via CLI
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")
        try:
            length = int(environ.get("CONTENT_LENGTH", "0"))
        except ValueError:
            length = 0
        body = environ.get("wsgi.input")
        payload: Any | None = None
        if body and length:
            raw = body.read(length)
            if raw:
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception:  # pragma: no cover - defensive
                    payload = None

        response = self.handle_request(method, path, payload)
        reason_map = {
            200: "OK",
            201: "Created",
            400: "Bad Request",
            404: "Not Found",
            422: "Unprocessable Entity",
        }
        status_line = f"{response.status_code} {reason_map.get(response.status_code, 'OK')}"
        data = response.data
        if isinstance(data, bytes):
            body_bytes = data
        elif isinstance(data, str):
            body_bytes = data.encode("utf-8")
        else:
            body_bytes = json.dumps(data).encode("utf-8")
        media_type = response.media_type
        if media_type is None:
            if isinstance(data, (str, bytes)):
                media_type = "text/plain; charset=utf-8"
            else:
                media_type = "application/json"
        headers = [("Content-Type", media_type), ("Content-Length", str(len(body_bytes)))]
        start_response(status_line, headers)
        return [body_bytes]


def _build_kwargs(func: Callable[..., Any], payload: Any | None) -> dict[str, Any]:
    import inspect

    signature = inspect.signature(func)
    type_hints = {}
    try:
        from typing import get_type_hints

        type_hints = get_type_hints(func)
    except Exception:  # pragma: no cover - defensive fallback when annotations fail to resolve
        type_hints = {}
    kwargs: dict[str, Any] = {}
    data = payload if isinstance(payload, dict) else {}

    for name, parameter in signature.parameters.items():
        default = parameter.default
        annotation = type_hints.get(name, parameter.annotation)
        if isinstance(default, Depends):
            kwargs[name] = default.dependency()
            continue

        if annotation is inspect._empty:
            if name in data:
                kwargs[name] = data[name]
            elif default is not inspect._empty:
                kwargs[name] = default
            else:
                raise ValidationError([{"loc": (name,), "msg": "Missing value"}])
            continue

        is_model = isinstance(annotation, type) and issubclass(annotation, BaseModel)
        if is_model:
            if payload is None:
                raise ValidationError([{"loc": (name,), "msg": "Body required"}])
            kwargs[name] = annotation.model_validate(data)
            continue

        if name in data:
            kwargs[name] = data[name]
        elif default is not inspect._empty:
            kwargs[name] = default
        else:
            raise ValidationError([{"loc": (name,), "msg": "Missing value"}])

    return kwargs


def _serialise_response(result: Any) -> Any:
    if isinstance(result, BaseModel):
        return result.model_dump()
    if isinstance(result, Response):
        return result.data
    return result


status = SimpleNamespace(
    HTTP_200_OK=200,
    HTTP_201_CREATED=201,
    HTTP_400_BAD_REQUEST=400,
    HTTP_404_NOT_FOUND=404,
    HTTP_422_UNPROCESSABLE_ENTITY=422,
)
