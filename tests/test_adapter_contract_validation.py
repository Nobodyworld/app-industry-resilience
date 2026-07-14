"""Boundary-contract tests for BEA and Census ASM adapters."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from src.adapters.bea import (
    BEAClientError,
    _enrich_with_naics_map,
    _parse_bea_response,
    fetch_go_ii_by_industry,
)
from src.adapters.census_asm import (
    CensusASMClientError,
    _validate_census_payload,
    fetch_asm_manufacturing,
)


def _bea_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Industry": "311",
        "IndustrYDescription": "Food",
        "Year": "2021",
        "DataValue": "100",
    }
    row.update(overrides)
    return row


def _bea_payload(*rows: object) -> dict[str, object]:
    return {"BEAAPI": {"Results": {"Data": list(rows)}}}


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({}, "BEAAPI envelope"),
        ({"BEAAPI": []}, "BEAAPI envelope"),
        ({"BEAAPI": {"Results": []}}, "BEA Results"),
        ({"BEAAPI": {"Results": {}}}, "missing required 'Data'"),
        (_bea_payload(), "contains no rows"),
    ],
)
def test_bea_rejects_malformed_envelopes(
    payload: object,
    expected: str,
) -> None:
    with pytest.raises(BEAClientError, match=expected):
        _parse_bea_response(payload)


@pytest.mark.parametrize(
    "row, expected",
    [
        ({"Industry": "311"}, "missing required fields"),
        (_bea_row(Industry=""), "must not be empty"),
        (_bea_row(IndustrYDescription=""), "must not be empty"),
        (_bea_row(Year="2021.5"), "positive integer year"),
        (_bea_row(DataValue="suppressed"), "must be numeric"),
        (_bea_row(DataValue="NaN"), "must be finite"),
    ],
)
def test_bea_rejects_malformed_rows(
    row: object,
    expected: str,
) -> None:
    with pytest.raises(BEAClientError, match=expected):
        _parse_bea_response(_bea_payload(row))


def test_bea_valid_row_contract_is_preserved() -> None:
    rows, notes, next_page = _parse_bea_response(
        {
            "BEAAPI": {
                "Results": {
                    "Data": [_bea_row(DataValue="1,234")],
                    "Notes": [{"Text": " validated "}],
                }
            }
        }
    )

    assert rows[0]["Industry"] == "311"
    assert rows[0]["IndustrYDescription"] == "Food"
    assert rows[0]["Year"] == "2021"
    assert rows[0]["DataValue"] == 1234.0
    assert notes == ["validated"]
    assert next_page is None


def test_bea_naics_enrichment_maps_ranges_and_preserves_unknown_labels() -> None:
    frame = pd.DataFrame(
        [
            {
                "industry_code": "311",
                "industry_name": "Provider Food Label",
                "year": 2021,
                "gross_output": 100.0,
                "intermediate_inputs": 60.0,
                "source": "BEA",
            },
            {
                "industry_code": "999",
                "industry_name": "Provider Novel Label",
                "year": 2021,
                "gross_output": 50.0,
                "intermediate_inputs": 20.0,
                "source": "BEA",
            },
        ]
    )
    mapping = pd.DataFrame(
        [
            {
                "industry_code": "31-33",
                "industry_name": "Manufacturing",
                "bea_group": "MANUF",
            }
        ]
    )

    with patch("src.adapters.bea._load_naics_map", return_value=mapping):
        enriched = _enrich_with_naics_map(frame)

    assert enriched.loc[0, "industry_name"] == "Provider Food Label"
    assert enriched.loc[0, "naics_sector_name"] == "Manufacturing"
    assert enriched.loc[0, "naics_mapping_status"] == "mapped"
    assert enriched.loc[1, "industry_code"] == "999"
    assert enriched.loc[1, "industry_name"] == "Provider Novel Label"
    assert enriched.loc[1, "naics_sector_name"] == "Unmapped NAICS 999"
    assert enriched.loc[1, "bea_group"] == "UNMAPPED"
    assert enriched.loc[1, "naics_mapping_status"] == "unmapped"


@patch("src.adapters.bea.get_api_cache", return_value=None)
@patch("src.adapters.bea.safe_get_json")
def test_bea_fetch_records_unmapped_metadata(mock_get_json, _cache) -> None:
    health = {"BEAAPI": {"Results": {"Data": []}}}
    go = _bea_payload(
        _bea_row(
            Industry="999",
            IndustrYDescription="Novel",
            DataValue="100",
        )
    )
    inputs = _bea_payload(
        _bea_row(
            Industry="999",
            IndustrYDescription="Novel",
            DataValue="60",
        )
    )
    mock_get_json.side_effect = [health, go, inputs]

    frame = fetch_go_ii_by_industry("valid_api_key_12345", 2021)

    assert frame.loc[0, "industry_code"] == "999"
    assert frame.loc[0, "industry_name"] == "Novel"
    assert frame.loc[0, "naics_mapping_status"] == "unmapped"
    assert frame.attrs["bea_metadata"]["contract_validated"] is True
    assert frame.attrs["bea_metadata"]["unmapped_naics_codes"] == ["999"]


def _census_payload(*rows: object) -> list[object]:
    return [
        ["NAICS2017", "NAICS2017_LABEL", "RCPTOT", "CSTMTOT", "VALADD"],
        *rows,
    ]


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"error": "provider unavailable"}, "provider unavailable"),
        ([], "No Census ASM data rows"),
        (["not-a-header", ["311"]], "header"),
        (
            [["NAICS2017", "NAICS2017_LABEL"], ["311", "Food"]],
            "missing required columns",
        ),
        (_census_payload(["311", "Food", "100"]), "header has 5 columns"),
        (
            _census_payload(["", "Food", "100", "60", "40"]),
            "must not be empty",
        ),
        (
            _census_payload(["311", "", "100", "60", "40"]),
            "must not be empty",
        ),
        (
            _census_payload(["311", "Food", "not-numeric", "60", "40"]),
            "must be numeric",
        ),
    ],
)
def test_census_rejects_malformed_contracts(
    payload: object,
    expected: str,
) -> None:
    with pytest.raises(CensusASMClientError, match=expected):
        _validate_census_payload(payload, year=2021)


def test_census_valid_fixture_normalizes_without_behavior_change() -> None:
    config = SimpleNamespace(
        supported_years_census=range(2010, 2030),
        cache=None,
        census_asm_endpoint_template="https://api.census.gov/data/{year}/asm",
    )
    payload = _census_payload(["311", "Food", "100", "60", "40"])

    with (
        patch("src.adapters.census_asm.load_config", return_value=config),
        patch("src.adapters.census_asm.get_api_cache", return_value=None),
        patch("src.adapters.census_asm.api_limiter.wait_for_api"),
        patch(
            "src.adapters.census_asm.safe_get_json",
            return_value=payload,
        ),
    ):
        frame = fetch_asm_manufacturing("valid_api_key_12345", 2021)

    assert frame.loc[0, "industry_code"] == "311"
    assert frame.loc[0, "industry_name"] == "Food"
    assert frame.loc[0, "gross_output"] == 100.0
    assert frame.loc[0, "materials_cost"] == 60.0
    assert frame.loc[0, "value_added"] == 40.0
    assert frame.attrs["census_asm_metadata"] == {
        "year": 2021,
        "row_count": 1,
        "contract_validated": True,
        "required_fields": [
            "NAICS2017",
            "NAICS2017_LABEL",
            "RCPTOT",
            "CSTMTOT",
            "VALADD",
        ],
    }
