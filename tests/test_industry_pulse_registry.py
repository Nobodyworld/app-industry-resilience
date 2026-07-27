"""Validation tests for the reviewed Industry Pulse registry."""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.core.industry_pulse import (
    INDUSTRY_PULSE_REGISTRY,
    IndustryPulseRegistry,
    IndustryPulseRegistryEntry,
    IndustryPulseRegistryError,
)

EXPECTED = {
    "PCU311111311111": "311111",
    "PCU312120312120": "312120",
    "PCU322120322120": "322120",
    "PCU325211325211": "325211",
    "PCU326111326111": "326111",
    "PCU331110331110": "331110",
    "PCU334111334111": "334111",
    "PCU336110336110": "336110",
}


def _valid_entry() -> IndustryPulseRegistryEntry:
    return INDUSTRY_PULSE_REGISTRY.entries[0]


def test_registry_contains_exactly_the_eight_reviewed_whole_industry_mappings() -> None:
    assert {entry.series_id: entry.industry_code for entry in INDUSTRY_PULSE_REGISTRY.entries} == (
        EXPECTED
    )
    assert all(entry.source_title for entry in INDUSTRY_PULSE_REGISTRY.entries)
    assert all(entry.base_date for entry in INDUSTRY_PULSE_REGISTRY.entries)
    assert all(entry.mapping_basis for entry in INDUSTRY_PULSE_REGISTRY.entries)
    assert INDUSTRY_PULSE_REGISTRY.by_industry_code("311") is None


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("series_id", "pcu311111311111", "uppercase whole-industry"),
        ("series_id", "PCU3111113111111", "uppercase whole-industry"),
        ("series_id", "PCU311111P", "uppercase whole-industry"),
        ("series_id", "PCU311112311111", "industry segment"),
        ("series_id", "PCU311111311112", "product segment"),
        ("industry_code", "31111", "six-digit NAICS"),
        ("base_date", "", "base date"),
        ("source_title", "", "source title"),
        ("units", "", "units"),
        ("seasonal_adjustment", "", "seasonal-adjustment"),
        ("mapping_basis", "", "mapping basis"),
        ("source_url", "", "source URL"),
        ("steward_notes", (), "steward notes"),
        ("steward_notes", ("Inferred from a label.",), "reviewed"),
    ],
)
def test_registry_entry_rejects_malformed_or_undocumented_mappings(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(IndustryPulseRegistryError, match=message):
        replace(_valid_entry(), **{field: value})


def test_registry_rejects_duplicate_series_and_ambiguous_naics() -> None:
    entry = _valid_entry()
    with pytest.raises(IndustryPulseRegistryError, match="Duplicate Industry Pulse series"):
        IndustryPulseRegistry((entry, entry))

    ambiguous = object.__new__(IndustryPulseRegistryEntry)
    for field, value in entry.__dict__.items():
        object.__setattr__(ambiguous, field, value)
    object.__setattr__(ambiguous, "series_id", "PCU312120312120")
    with pytest.raises(IndustryPulseRegistryError, match="ambiguous"):
        IndustryPulseRegistry((entry, ambiguous))
