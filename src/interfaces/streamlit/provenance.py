"""Privacy-safe lineage helpers for Streamlit upload and display workflows."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from src.core import (
    LineageStep,
    attach_lineage,
    build_lineage,
    lineage_from_dataframe,
    lineage_to_dict,
)


def attach_uploaded_file_lineage(
    frame: pd.DataFrame,
    *,
    acquired_at: datetime | None = None,
) -> pd.DataFrame:
    """Attach generic upload lineage without exposing the user-provided filename."""

    if lineage_from_dataframe(frame) is not None:
        return frame

    lineage = build_lineage(
        source="user-upload",
        source_kind="uploaded_file",
        dataset_id="user-upload",
        observation_period=_upload_observation_period(frame),
        acquired_at=acquired_at or datetime.now(UTC),
        retrieval_mode="upload",
        is_sample=False,
        is_official=False,
        transformations=(
            LineageStep(
                name="source_load",
                details={"record_count": len(frame)},
            ),
        ),
    )
    return attach_lineage(frame, lineage)


def build_provenance_tables(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """Build display tables from the typed lineage envelope only."""

    lineage = lineage_from_dataframe(frame)
    if lineage is None:
        return None

    payload = lineage_to_dict(lineage)
    summary_fields = (
        ("Source", "source"),
        ("Provider", "provider"),
        ("Dataset", "dataset_id"),
        ("Observation period", "observation_period"),
        ("Acquired", "acquired_at"),
        ("Snapshot", "snapshot_at"),
        ("Retrieval mode", "retrieval_mode"),
        ("Cache status", "cache_status"),
        ("Sample data", "is_sample"),
        ("Official data", "is_official"),
        ("Calculation version", "calculation_version"),
        ("Lineage schema", "schema_version"),
    )
    summary = pd.DataFrame(
        [
            {
                "Field": label,
                "Value": _display_value(payload.get(field_name)),
            }
            for label, field_name in summary_fields
        ]
    )

    transformations = payload.get("transformations", [])
    steps = pd.DataFrame(
        [
            {
                "Step": str(step.get("name", "")),
                "Version": str(step.get("version", "")),
                "Details": json.dumps(
                    step.get("details", {}),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            }
            for step in transformations
            if isinstance(step, dict)
        ],
        columns=["Step", "Version", "Details"],
    )
    return summary, steps


def _upload_observation_period(frame: pd.DataFrame) -> str:
    if "year" not in frame.columns:
        return "unknown"
    years = pd.to_numeric(frame["year"], errors="coerce").dropna().astype("int64").unique()
    if len(years) == 1:
        return str(int(years[0]))
    if len(years) > 1:
        return "mixed"
    return "unknown"


def _display_value(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


__all__ = ["attach_uploaded_file_lineage", "build_provenance_tables"]
