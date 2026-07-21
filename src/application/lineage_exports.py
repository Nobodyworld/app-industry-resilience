"""Typed, non-mutating lineage serialization for analytical exports."""

from __future__ import annotations

import json
from typing import Any, Literal, cast

import pandas as pd

from src.core import append_lineage_step, lineage_from_dataframe, lineage_to_dict

ExportFormat = Literal["json", "xlsx", "csv"]
ExportScope = Literal["full", "filtered"]

_EXPORT_FORMATS = frozenset({"json", "xlsx", "csv"})
_EXPORT_SCOPES = frozenset({"full", "filtered"})


def build_export_lineage(
    frame: pd.DataFrame,
    *,
    export_format: ExportFormat,
    scope: ExportScope,
) -> dict[str, Any] | None:
    """Return public lineage for an export without mutating ``frame``."""

    _validate_export_request(export_format=export_format, scope=scope)
    lineage = lineage_from_dataframe(frame)
    if lineage is None:
        return None

    exported = append_lineage_step(
        lineage,
        "export_serialization",
        details={
            "format": export_format,
            "scope": scope,
            "record_count": len(frame),
        },
    )
    return lineage_to_dict(exported)


def build_json_export_document(
    frame: pd.DataFrame,
    *,
    scope: ExportScope,
) -> dict[str, Any]:
    """Return the stable top-level JSON export document."""

    records = cast(
        list[dict[str, Any]],
        json.loads(frame.to_json(orient="records", date_format="iso")),
    )
    return {
        "lineage": build_export_lineage(frame, export_format="json", scope=scope),
        "records": records,
    }


def build_csv_lineage_companion(
    frame: pd.DataFrame,
    *,
    scope: ExportScope,
) -> bytes:
    """Return the JSON lineage companion served alongside a tabular CSV."""

    payload = {
        "lineage": build_export_lineage(frame, export_format="csv", scope=scope),
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def build_xlsx_lineage_rows(
    frame: pd.DataFrame,
    *,
    scope: ExportScope,
) -> list[dict[str, str]]:
    """Return two-column records suitable for a dedicated XLSX Lineage sheet."""

    lineage = build_export_lineage(frame, export_format="xlsx", scope=scope)
    if lineage is None:
        return []

    rows: list[dict[str, str]] = []
    for field_name, value in lineage.items():
        rendered = (
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if isinstance(value, (dict, list))
            else "" if value is None else str(value)
        )
        rows.append({"field": field_name, "value": rendered})
    return rows


def _validate_export_request(
    *,
    export_format: str,
    scope: str,
) -> None:
    if export_format not in _EXPORT_FORMATS:
        raise ValueError(f"Unsupported export format: {export_format}")
    if scope not in _EXPORT_SCOPES:
        raise ValueError(f"Unsupported export scope: {scope}")


__all__ = [
    "ExportFormat",
    "ExportScope",
    "build_csv_lineage_companion",
    "build_export_lineage",
    "build_json_export_document",
    "build_xlsx_lineage_rows",
]
