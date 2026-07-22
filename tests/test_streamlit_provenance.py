from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd

from src.core import attach_lineage, build_lineage, lineage_from_dataframe
from src.interfaces.streamlit.provenance import (
    attach_uploaded_file_lineage,
    build_provenance_tables,
)


def _frame(years: list[int]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "industry_code": [f"31{index}" for index, _ in enumerate(years)],
            "industry_name": [f"Industry {index}" for index, _ in enumerate(years)],
            "year": years,
        }
    )


def test_attach_uploaded_file_lineage_is_generic_and_private() -> None:
    frame = _frame([2023])
    frame.attrs.update(
        {
            "uploaded_filename": "private-client-data.csv",
            "api_key": "sentinel-secret",
            "source_path": r"C:\Users\private\client.csv",
        }
    )
    acquired_at = datetime(2026, 7, 22, 1, 30, tzinfo=UTC)

    result = attach_uploaded_file_lineage(frame, acquired_at=acquired_at)
    lineage = lineage_from_dataframe(result)

    assert result is frame
    assert lineage is not None
    assert lineage.source == "user-upload"
    assert lineage.source_kind.value == "uploaded_file"
    assert lineage.dataset_id == "user-upload"
    assert lineage.observation_period == "2023"
    assert lineage.acquired_at == acquired_at
    assert lineage.retrieval_mode.value == "upload"
    assert lineage.is_sample is False
    assert lineage.is_official is False
    assert lineage.transformations[0].details == {"record_count": 1}
    serialized = json.dumps(lineage.as_dict())
    assert "private-client-data.csv" not in serialized
    assert "sentinel-secret" not in serialized
    assert "C:\\Users" not in serialized


def test_attach_uploaded_file_lineage_uses_bounded_mixed_period() -> None:
    frame = attach_uploaded_file_lineage(_frame([2021, 2023]))
    lineage = lineage_from_dataframe(frame)

    assert lineage is not None
    assert lineage.observation_period == "mixed"


def test_attach_uploaded_file_lineage_preserves_existing_typed_lineage() -> None:
    frame = _frame([2023])
    existing = build_lineage(
        source="census",
        source_kind="official_snapshot",
        dataset_id="aies",
        provider="U.S. Census Bureau",
        observation_period=2023,
        snapshot_at=datetime(2026, 2, 26, tzinfo=UTC),
        retrieval_mode="snapshot",
        is_sample=False,
        is_official=True,
    )

    attach_lineage(frame, existing)
    attach_uploaded_file_lineage(frame)

    assert lineage_from_dataframe(frame) == existing


def test_build_provenance_tables_returns_only_typed_fields() -> None:
    frame = _frame([2023])
    frame.attrs["private_path"] = r"C:\Users\private\file.csv"
    attach_uploaded_file_lineage(frame)

    tables = build_provenance_tables(frame)

    assert tables is not None
    summary, transformations = tables
    rendered = summary.to_string() + transformations.to_string()
    assert "user-upload" in rendered
    assert "source_load" in rendered
    assert "private_path" not in rendered
    assert r"C:\Users" not in rendered


def test_build_provenance_tables_handles_missing_lineage() -> None:
    assert build_provenance_tables(_frame([2023])) is None
