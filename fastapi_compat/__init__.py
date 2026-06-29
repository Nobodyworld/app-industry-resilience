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
from datetime import date, datetime, time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs

from pydantic_compat import BaseModel, ValidationError

__all__ = [
    "Depends",
    "FastAPI",
    "HTTPException",
    "Query",
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


def _split_path(path: str) -> list[str]:
    if path in {"", "/"}:
        return []
    return [segment for segment in path.strip("/").split("/") if segment]


def _match_path(pattern: str, path: str) -> tuple[bool, dict[str, str]]:
    """Return ``(matched, params)`` for ``pattern`` against ``path``."""

    pattern_segments = _split_path(pattern)
    path_segments = _split_path(path)
    if len(pattern_segments) != len(path_segments):
        return False, {}
    params: dict[str, str] = {}
    for pattern_part, path_part in zip(pattern_segments, path_segments, strict=False):
        if pattern_part.startswith("{") and pattern_part.endswith("}"):
            key = pattern_part[1:-1]
            if not key:
                return False, {}
            params[key] = path_part
            continue
        if pattern_part != path_part:
            return False, {}
    return True, params


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
        route = None
        path_params: dict[str, str] = {}
        raw_path, _, query_string = path.partition("?")
        for candidate in self._routes:
            if candidate.method != method:
                continue
            matched, params = _match_path(candidate.path, raw_path)
            if matched:
                route = candidate
                path_params = params
                break
        if route is None:
            return Response(status_code=404, data={"detail": "Not Found"})

        try:
            query_params = _parse_query(query_string)
            kwargs = _build_kwargs(route.endpoint, payload, path_params, query_params)
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
            body_bytes = json.dumps(data, default=_json_default).encode("utf-8")
        media_type = response.media_type
        if media_type is None:
            if isinstance(data, (str, bytes)):
                media_type = "text/plain; charset=utf-8"
            else:
                media_type = "application/json"
        headers = [("Content-Type", media_type), ("Content-Length", str(len(body_bytes)))]
        start_response(status_line, headers)
        return [body_bytes]


def _build_kwargs(
    func: Callable[..., Any],
    payload: Any | None,
    path_params: dict[str, str],
    query_params: dict[str, str] | None,
) -> dict[str, Any]:
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
        if name in path_params:
            raw_value = path_params[name]
            if isinstance(annotation, type) and annotation is not inspect._empty:
                try:
                    kwargs[name] = annotation(raw_value)
                except Exception as exc:  # pragma: no cover - defensive
                    raise ValidationError(
                        [{"loc": (name,), "msg": f"Invalid value: {raw_value!r}"}]
                    ) from exc
            else:
                kwargs[name] = raw_value
            continue
        if query_params and name in query_params:
            raw_value = query_params[name]
            kwargs[name] = _coerce_query_value(annotation, raw_value)
            continue
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
        return result.model_dump(mode="json")
    if isinstance(result, Response):
        return result.data
    return result


def _json_default(value: Any) -> Any:
    """Serialize common Python objects for JSON responses."""

    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def _parse_query(raw: str) -> dict[str, str]:
    if not raw:
        return {}
    parsed = parse_qs(raw, keep_blank_values=True)
    return {key: (values[-1] if values else "") for key, values in parsed.items()}


def _coerce_query_value(annotation: Any, raw_value: str | None) -> Any:
    import inspect
    from typing import get_args, get_origin

    if raw_value is None:
        return None
    if annotation is inspect._empty:
        return raw_value

    origin = get_origin(annotation)
    if origin is None:
        candidate_types = (annotation,)
    else:
        candidate_types = tuple(
            candidate for candidate in get_args(annotation) if candidate is not type(None)
        )
        if not candidate_types:
            return raw_value

    for candidate in candidate_types:
        try:
            return candidate(raw_value)
        except Exception:  # pragma: no cover - fallback to raw string
            continue
    return raw_value


status = SimpleNamespace(
    HTTP_200_OK=200,
    HTTP_201_CREATED=201,
    HTTP_400_BAD_REQUEST=400,
    HTTP_404_NOT_FOUND=404,
    HTTP_422_UNPROCESSABLE_ENTITY=422,
)


def Query(default: Any | None = None, **_: Any) -> Any:
    """Compatibility helper mirroring :func:`fastapi.Query` semantics."""

    return default
