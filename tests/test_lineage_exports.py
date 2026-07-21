"""Tests for non-mutating export-lineage serialization."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd
import pytest

from src.application.lineage_exports import (
    build_csv_lineage_companion,
    build_export_lineage,
    build_json_export_document,
    build_xlsx_lineage_rows,
)
from src.core import LineageStep, attach_lineage, build_lineage, lineage_from_dataframe


def _frame() -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "industry_code": ["111", "112"],
            "industry_name": ["Alpha", "Beta"],
            "year": [2023, 2023],
            "gross_output": [100.0, 200.0],
        }
    )
    frame.attrs.update(
        {
            "api_key": "sentinel-secret",
            "cache_dir": r"C:\\Users\\private\\cache",
        }
    )
    lineage = build_lineage(
        source="bea",
        source_kind="live_provider",
        dataset_id="bea-industry",
        provider="Bureau of Economic Analysis",
        observation_period="2023",
        acquired_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
        retrieval_mode="live",
        is_sample=False,
        is_official=True,
        transformations=(
            LineageStep(
                name="source_load",
                details={"record_count": len(frame)},
            ),
        ),
    )
    return attach_lineage(frame, lineage)


def test_export_lineage_appends_step_without_mutating_frame() -> None:
    frame = _frame()
    original = lineage_from_dataframe(frame)

    exported = build_export_lineage(frame, export_format="json", scope="full")
    current = lineage_from_dataframe(frame)

    assert original is not None
    assert current == original
    assert exported is not None
    assert [step["name"] for step in exported["transformations"]] == [
        "source_load",
        "export_serialization",
    ]
    assert exported["transformations"][-1]["details"] == {
        "format": "json",
        "record_count": 2,
        "scope": "full",
    }


def test_json_export_embeds_lineage_at_top_level() -> None:
    document = build_json_export_document(_frame(), scope="filtered")

    assert document["lineage"]["source"] == "bea"
    assert document["lineage"]["transformations"][-1]["details"] == {
        "format": "json",
        "record_count": 2,
        "scope": "filtered",
    }
    assert document["records"][0]["industry_code"] == "111"
    serialized = json.dumps(document)
    assert "sentinel-secret" not in serialized
    assert "Users" not in serialized


def test_csv_companion_and_xlsx_rows_use_format_specific_steps() -> None:
    frame = _frame()

    companion = json.loads(build_csv_lineage_companion(frame, scope="full"))
    rows = build_xlsx_lineage_rows(frame, scope="filtered")
    row_map = {row["field"]: row["value"] for row in rows}

    assert companion["lineage"]["transformations"][-1]["details"]["format"] == "csv"
    transformations = json.loads(row_map["transformations"])
    assert transformations[-1]["details"] == {
        "format": "xlsx",
        "record_count": 2,
        "scope": "filtered",
    }
    assert row_map["source"] == "bea"


def test_export_helpers_handle_missing_lineage_and_reject_invalid_values() -> None:
    frame = pd.DataFrame({"industry_code": ["111"]})

    assert build_export_lineage(frame, export_format="json", scope="full") is None
    assert build_json_export_document(frame, scope="full")["lineage"] is None
    assert build_csv_lineage_companion(frame, scope="full") == b'{"lineage":null}'
    assert build_xlsx_lineage_rows(frame, scope="full") == []

    with pytest.raises(ValueError, match="Unsupported export format"):
        build_export_lineage(frame, export_format="xml", scope="full")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Unsupported export scope"):
        build_export_lineage(frame, export_format="json", scope="subset")  # type: ignore[arg-type]
