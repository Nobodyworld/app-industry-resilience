"""Lightweight validation utilities inspired by Pydantic.

This module provides a very small subset of the :mod:`pydantic` API that is
required by the Idiot Index headless API.  The implementation favours
deterministic behaviour and zero third-party dependencies so the project can be
tested in restricted execution environments where installing wheels from PyPI
is not possible.

Only the features exercised by the project are implemented: ``BaseModel`` with
basic type coercion, field constraints (``ge``/``le``), support for optional
fields, container types, enumerations, and model serialisation via
``model_dump``.  The goal is to offer ergonomic data validation without the
surface area or complexity of the real Pydantic package.  The public surface is
compatible with the subset used across ``src/interfaces/api`` and the test
suite.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import NoneType, UnionType
from typing import Any, Union, get_args, get_origin

__all__ = [
    "BaseModel",
    "ConfigDict",
    "Field",
    "FieldInfo",
    "ValidationError",
]


class ValidationError(ValueError):
    """Raised when a model fails validation."""

    def __init__(self, errors: list[dict[str, Any]]):
        super().__init__("Validation failed")
        self.errors = errors

    def __str__(self) -> str:  # pragma: no cover - inherited repr is noisy
        payload = json.dumps(self.errors, default=str)
        return f"ValidationError({payload})"


@dataclass(slots=True)
class FieldInfo:
    """Metadata describing a model field."""

    default: Any = inspect._empty
    default_factory: Callable[[], Any] | None = None
    ge: float | None = None
    le: float | None = None
    description: str | None = None

    def provide_default(self) -> Any:
        if self.default is not inspect._empty:
            return self.default
        if self.default_factory is not None:
            return self.default_factory()
        return inspect._empty


def Field(
    default: Any = inspect._empty,
    *,
    default_factory: Callable[[], Any] | None = None,
    ge: float | None = None,
    le: float | None = None,
    description: str | None = None,
) -> Any:
    """Return metadata mirroring :func:`pydantic.Field`."""

    if default is not inspect._empty and default_factory is not None:
        raise TypeError("default and default_factory cannot be combined")
    return FieldInfo(
        default=default,
        default_factory=default_factory,
        ge=ge,
        le=le,
        description=description,
    )


ConfigDict = dict[str, Any]


@dataclass(slots=True)
class ModelField:
    """Runtime representation of a model field."""

    name: str
    annotation: Any
    info: FieldInfo


class BaseModelMeta(type):
    """Collect annotated fields declared on a :class:`BaseModel`."""

    def __new__(mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]):
        annotations: dict[str, Any] = {}
        for base in reversed(bases):
            annotations.update(getattr(base, "__annotations__", {}))
        annotations.update(namespace.get("__annotations__", {}))

        fields: dict[str, ModelField] = {}
        for attr, annotation in annotations.items():
            if attr == "model_config":
                continue
            default_value = namespace.get(attr, inspect._empty)
            if isinstance(default_value, FieldInfo):
                field_info = default_value
                namespace.pop(attr, None)
            else:
                field_info = FieldInfo(default=default_value)
            fields[attr] = ModelField(attr, annotation, field_info)

        namespace["__fields__"] = fields
        return super().__new__(mcls, name, bases, namespace)


class BaseModel(metaclass=BaseModelMeta):
    """Minimal stand-in for :class:`pydantic.BaseModel`."""

    model_config: ConfigDict = {}

    def __init__(self, **data: Any):
        config = getattr(self, "model_config", {})
        allow_extra = config.get("extra") == "allow"
        use_enum_values = bool(config.get("use_enum_values"))
        try:
            from typing import get_type_hints

            resolved_hints = get_type_hints(self.__class__)
        except Exception:
            resolved_hints = {}

        values: dict[str, Any] = {}
        extras: dict[str, Any] = {}
        errors: list[dict[str, Any]] = []
        payload = dict(data)

        for name, field in self.__fields__.items():
            annotation = resolved_hints.get(name, field.annotation)
            if name in payload:
                raw_value = payload.pop(name)
            else:
                default_value = field.info.provide_default()
                if default_value is inspect._empty:
                    errors.append({"loc": (name,), "msg": "Field required"})
                    continue
                raw_value = default_value

            try:
                value = _convert_value(annotation, raw_value, use_enum_values)
            except ValidationError as sub_error:
                for detail in sub_error.errors:
                    path = (name, *detail.get("loc", ()))
                    errors.append({"loc": path, "msg": detail.get("msg", "invalid value")})
                continue
            except ValueError as exc:
                errors.append({"loc": (name,), "msg": str(exc) or "invalid value"})
                continue

            constraint_error = _check_constraints(field.info, value)
            if constraint_error is not None:
                errors.append({"loc": (name,), "msg": constraint_error})
                continue

            values[name] = value

        if payload:
            if allow_extra:
                extras = payload
            else:
                for key in payload:
                    errors.append({"loc": (key,), "msg": "Extra field not permitted"})

        if errors:
            raise ValidationError(errors)

        object.__setattr__(self, "_values", values)
        object.__setattr__(self, "_extra", extras)
        object.__setattr__(self, "_use_enum_values", use_enum_values)

    def __getattr__(self, item: str) -> Any:
        if item in self._values:
            return self._values[item]
        if item in self._extra:
            return self._extra[item]
        raise AttributeError(item)

    def __setattr__(self, key: str, value: Any) -> None:  # pragma: no cover - dataclass-style
        if key.startswith("_"):
            super().__setattr__(key, value)
        else:
            self._values[key] = value

    def model_dump(self, *, mode: str = "python", exclude_none: bool = False) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the model."""

        del mode  # Unused but kept for API parity.
        result: dict[str, Any] = {}
        for name in self.__fields__:
            value = self._values.get(name)
            if exclude_none and value is None:
                continue
            result[name] = _serialise(value, self._use_enum_values)

        for name, value in self._extra.items():
            if exclude_none and value is None:
                continue
            result[name] = _serialise(value, self._use_enum_values)
        return result

    @classmethod
    def model_validate(cls: type[BaseModel], data: Mapping[str, Any]) -> BaseModel:
        if not isinstance(data, Mapping):
            raise ValidationError([{"loc": (), "msg": "Expected mapping"}])
        return cls(**dict(data))


def _check_constraints(info: FieldInfo, value: Any) -> str | None:
    if value is None:
        return None
    if info.ge is not None:
        try:
            if value < info.ge:
                return f"Value must be >= {info.ge}"
        except TypeError:
            return f"Value must be >= {info.ge}"
    if info.le is not None:
        try:
            if value > info.le:
                return f"Value must be <= {info.le}"
        except TypeError:
            return f"Value must be <= {info.le}"
    return None


def _convert_value(annotation: Any, value: Any, use_enum_values: bool) -> Any:
    if annotation is Any or annotation is object:
        return value

    if _is_optional(annotation):
        if value is None:
            return None
        return _convert_optional(annotation, value, use_enum_values)

    origin = get_origin(annotation)
    if origin in {list, tuple, set} or origin is Sequence:
        inner_type = get_args(annotation)[0]
        if not isinstance(value, list | tuple | set):
            raise ValueError("Expected a sequence")
        converted = [_convert_value(inner_type, item, use_enum_values) for item in value]
        if origin is tuple:
            return tuple(converted)
        if origin is set:
            return set(converted)
        return list(converted)

    if origin in {dict, Mapping}:
        key_type, value_type = get_args(annotation)
        if not isinstance(value, Mapping):
            raise ValueError("Expected a mapping")
        return {
            _convert_value(key_type, key, use_enum_values): _convert_value(
                value_type, item, use_enum_values
            )
            for key, item in value.items()
        }

    if origin is Union:
        for candidate in get_args(annotation):
            try:
                return _convert_value(candidate, value, use_enum_values)
            except ValueError:
                continue
        raise ValueError("Value does not match any allowed type")

    if origin is type(None):  # pragma: no cover - defensive
        return None

    if getattr(annotation, "__module__", "").startswith("typing"):
        return value

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if isinstance(value, annotation):
            return value
        if not isinstance(value, Mapping):
            raise ValueError("Expected mapping for nested model")
        return annotation(**dict(value))

    if isinstance(annotation, type) and issubclass(annotation, Enum):
        if isinstance(value, annotation):
            return value
        try:
            member = annotation(value)
        except Exception:
            try:
                member = annotation[str(value)]
            except Exception as exc:
                raise ValueError(f"Invalid enum value: {value}") from exc
        return member

    if annotation is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.lower()
            if lowered in {"true", "1", "yes", "y", "on"}:
                return True
            if lowered in {"false", "0", "no", "n", "off"}:
                return False
        if isinstance(value, int | float):
            return bool(value)
        raise ValueError("Invalid boolean value")

    if annotation is int:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid integer value") from exc

    if annotation is float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid float value") from exc

    if annotation is str:
        if value is None:
            raise ValueError("Invalid string value")
        return str(value)

    if isinstance(annotation, type) and issubclass(annotation, tuple | list | set):
        return annotation(value)

    return value


def _is_optional(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is Union:
        return any(arg is NoneType for arg in get_args(annotation))
    if isinstance(annotation, UnionType):
        return any(arg is NoneType for arg in get_args(annotation))
    return False


def _convert_optional(annotation: Any, value: Any, use_enum_values: bool) -> Any:
    args = [arg for arg in get_args(annotation) if arg is not NoneType]
    for candidate in args:
        try:
            return _convert_value(candidate, value, use_enum_values)
        except ValueError:
            continue
    raise ValueError("Value does not match optional type")


def _serialise(value: Any, use_enum_values: bool) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, Enum):
        return value.value if use_enum_values else value.name
    if isinstance(value, Mapping):
        return {key: _serialise(item, use_enum_values) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_serialise(item, use_enum_values) for item in value]
    return value


__all__ = ["BaseModel", "Field", "FieldInfo", "ValidationError", "ConfigDict"]
