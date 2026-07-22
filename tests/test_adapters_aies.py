"""Tests for the keyless Census AIES snapshot adapter."""

from __future__ import annotations

import pandas as pd
import pytest

from src.adapters.aies import (
    AIESDataError,
    attach_aies_snapshot_lineage,
    build_aies_snapshot,
)
from src.core import lineage_from_dataframe


def _frame(value_column: str, values: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "GEOTYPE": ["01", "01", "02"],
            "TYPOP": ["00", "00", "00"],
            "TAXSTAT": ["00", "00", "00"],
            "NAICS": ["31", "311", "31"],
            "NAICS_LABEL": ["Manufacturing", "Food manufacturing", "Manufacturing"],
            "YEAR": ["2023", "2023", "2023"],
            value_column: values,
        }
    )


def test_build_aies_snapshot_merges_national_industries() -> None:
    basic = _frame("RCPT_TOT_VAL", ["1000", "600", "999"])
    expenses = _frame("EXPS_TOT_DVAL", ["750", "500", "888"])

    result = build_aies_snapshot(basic, expenses)

    assert result["industry_code"].tolist() == ["31", "311"]
    assert result["gross_output"].tolist() == [1_000_000, 600_000]
    assert result["intermediate_inputs"].tolist() == [750_000, 500_000]
    assert result["value_added"].tolist() == [250_000, 100_000]
    assert result.attrs["source_metadata"]["release_date"] == "2026-02-26"
    lineage = lineage_from_dataframe(result)
    assert lineage is not None
    assert lineage.source == "census"
    assert lineage.source_kind.value == "official_snapshot"
    assert lineage.dataset_id == "aies"
    assert lineage.provider == "U.S. Census Bureau"
    assert lineage.observation_period == "2023"
    assert lineage.snapshot_at is not None
    assert lineage.snapshot_at.isoformat() == "2026-02-26T00:00:00+00:00"
    assert lineage.retrieval_mode.value == "snapshot"
    assert lineage.is_official is True
    assert lineage.transformations[0].details == {"record_count": 2}


def test_build_aies_snapshot_rejects_schema_drift() -> None:
    with pytest.raises(AIESDataError, match="missing required columns"):
        build_aies_snapshot(pd.DataFrame(), pd.DataFrame())


def test_attach_aies_lineage_after_csv_round_trip() -> None:
    frame = pd.DataFrame({"industry_code": ["31"], "year": [2023]})

    attached = attach_aies_snapshot_lineage(frame)
    lineage = lineage_from_dataframe(attached)

    assert lineage is not None
    assert lineage.source_kind.value == "official_snapshot"
    assert lineage.snapshot_at is not None
    assert lineage.transformations[0].details == {"record_count": 1}
