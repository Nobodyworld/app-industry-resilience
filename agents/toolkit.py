"""Lightweight registry and schema helpers for agent-callable tools."""

from __future__ import annotations

from dataclasses import MISSING, dataclass, fields, is_dataclass
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Set,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)


@dataclass(frozen=True)
class ToolMetadata:
    """Metadata captured for each registered tool."""

    name: str
    description: str
    input_model: Type[Any]
    output_model: Type[Any]
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]


_TOOL_REGISTRY: Dict[str, ToolMetadata] = {}


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
        setattr(func, "__tool_metadata__", metadata)
        return func

    return decorator


def list_tools() -> List[ToolMetadata]:
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


def _schema_for_dataclass(cls: Type[Any]) -> Dict[str, Any]:
    if not is_dataclass(cls):  # pragma: no cover - defensive guard
        raise TypeError(f"{cls!r} is not a dataclass.")

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for field in fields(cls):
        schema = _schema_for_annotation(field.type)
        description = field.metadata.get("description") if field.metadata else None
        if description:
            schema = {**schema, "description": description}
        properties[field.name] = schema
        if field.default is MISSING and field.default_factory is MISSING:
            required.append(field.name)

    schema: Dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _schema_for_annotation(annotation: Any) -> Dict[str, Any]:
    origin = get_origin(annotation)
    if origin in {list, List, tuple, Tuple, Iterable}:
        args = get_args(annotation) or (Any,)
        return {"type": "array", "items": _schema_for_annotation(args[0])}

    if origin in {set, Set}:
        args = get_args(annotation) or (Any,)
        return {"type": "array", "uniqueItems": True, "items": _schema_for_annotation(args[0])}

    if origin in {dict, Dict}:
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
        return _schema_for_dataclass(annotation)

    python_type_to_json = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }
    json_type = python_type_to_json.get(annotation, "string")
    return {"type": json_type}
