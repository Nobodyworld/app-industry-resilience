"""Lightweight registry and schema helpers for agent-callable tools."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import MISSING, dataclass, fields, is_dataclass
from enum import Enum
from typing import Any, Union, cast, get_args, get_origin, get_type_hints


@dataclass(frozen=True)
class ToolMetadata:
    """Metadata captured for each registered tool."""

    name: str
    description: str
    input_model: type[Any]
    output_model: type[Any]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


_TOOL_REGISTRY: dict[str, ToolMetadata] = {}


def tool(name: str, description: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator used to register functions as agent-callable tools."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        hints = get_type_hints(func)
        input_model = hints.get("payload")
        output_model = hints.get("return")

        if not isinstance(input_model, type) or not is_dataclass(input_model):
            raise TypeError(
                f"Tool '{name}' must type annotate its first argument with a dataclass type, received {input_model!r}."
            )
        if not isinstance(output_model, type) or not is_dataclass(output_model):
            raise TypeError(
                f"Tool '{name}' must return a dataclass type, received {output_model!r}."
            )

        metadata = ToolMetadata(
            name=name,
            description=description,
            input_model=input_model,
            output_model=output_model,
            input_schema=_schema_for_dataclass(input_model),
            output_schema=_schema_for_dataclass(output_model),
        )
        _TOOL_REGISTRY[name] = metadata
        func_with_metadata = cast(Any, func)
        func_with_metadata.__tool_metadata__ = metadata
        return func

    return decorator


def list_tools() -> list[ToolMetadata]:
    """Return metadata for all registered tools."""

    return list(_TOOL_REGISTRY.values())


def get_tool(name: str) -> ToolMetadata:
    """Return metadata for a specific tool by name."""

    try:
        return _TOOL_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"No tool registered with name '{name}'.") from exc


def tool_names() -> Iterable[str]:
    """Convenience helper returning registered tool names."""

    return _TOOL_REGISTRY.keys()


def _schema_for_dataclass(cls: type[Any]) -> dict[str, Any]:
    """Return a JSON schema dictionary for the provided dataclass type.

    The schema is intentionally minimal, focusing on field names, basic typing,
    and optional descriptions sourced from ``field.metadata``. Required fields
    are derived from dataclass defaults so downstream tooling can validate
    payloads before invoking a tool.
    """
    if not is_dataclass(cls):  # pragma: no cover - defensive guard
        raise TypeError(f"{cls!r} is not a dataclass.")

    properties: dict[str, Any] = {}
    required: list[str] = []

    for field in fields(cls):
        schema = _schema_for_annotation(field.type)
        description = field.metadata.get("description") if field.metadata else None
        if description:
            schema = {**schema, "description": description}
        properties[field.name] = schema
        if field.default is MISSING and field.default_factory is MISSING:
            required.append(field.name)

    schema_dict: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema_dict["required"] = required
    return schema_dict


def _schema_for_annotation(annotation: Any) -> dict[str, Any]:
    """Translate a Python typing annotation into a JSON schema fragment."""
    origin = get_origin(annotation)
    if origin in {list, tuple, Iterable}:
        args = get_args(annotation) or (Any,)
        return {"type": "array", "items": _schema_for_annotation(args[0])}

    if origin is set:
        args = get_args(annotation) or (Any,)
        return {"type": "array", "uniqueItems": True, "items": _schema_for_annotation(args[0])}

    if origin is dict:
        key_type, value_type = get_args(annotation) or (Any, Any)
        return {
            "type": "object",
            "additionalProperties": _schema_for_annotation(value_type),
            "propertyNames": _schema_for_annotation(key_type),
        }

    if origin is Union:
        args = get_args(annotation)
        non_null = [arg for arg in args if arg is not type(None)]  # noqa: E721
        schemas = [_schema_for_annotation(arg) for arg in non_null]
        if len(non_null) != len(args):
            schemas.append({"type": "null"})
        if len(schemas) == 1:
            return schemas[0]
        return {"anyOf": schemas}

    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return {"type": "string", "enum": [member.value for member in annotation]}

    if is_dataclass(annotation):
        return _schema_for_dataclass(cast(type[Any], annotation))

    python_type_to_json = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }
    json_type = python_type_to_json.get(annotation, "string")
    return {"type": json_type}
