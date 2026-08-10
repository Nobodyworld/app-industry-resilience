"""Validation coverage for the reviewed multi-source registry."""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.core.industry_momentum import (
    INDUSTRY_MOMENTUM_REGISTRY,
    IndustryMomentumRegistry,
    IndustryMomentumRegistryError,
)


def test_registry_contains_all_reviewed_source_families_and_series() -> None:
    entries = INDUSTRY_MOMENTUM_REGISTRY.entries
    counts = {
        family: sum(entry.source_family == family for entry in entries)
        for family in ("bls_ppi", "bls_ces", "fed_g17")
    }
    assert counts == {"bls_ppi": 8, "bls_ces": 8, "fed_g17": 22}
    assert len({(entry.source_family, entry.series_id) for entry in entries}) == 38


def test_registry_mapping_claims_are_consistent() -> None:
    for entry in INDUSTRY_MOMENTUM_REGISTRY.entries:
        assert entry.official_title
        assert entry.units
        assert entry.source_url.startswith("https://")
        assert entry.mapping_basis
        assert entry.steward_notes
        if entry.mapping_relationship == "exact":
            assert entry.mapping_level == "six_digit"
            assert entry.published_industry_code == entry.target_industry_code


def test_registry_rejects_duplicate_source_series_identity() -> None:
    entry = INDUSTRY_MOMENTUM_REGISTRY.entries[0]
    with pytest.raises(IndustryMomentumRegistryError, match="Duplicate"):
        IndustryMomentumRegistry((entry, entry))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"series_id": "bad"}, "malformed"),
        ({"official_title": ""}, "missing documentation"),
        ({"units": ""}, "missing documentation"),
        ({"source_url": "https://example.com/data"}, "official HTTPS"),
        ({"mapping_basis": ""}, "missing documentation"),
        ({"steward_notes": ()}, "review notes"),
    ],
)
def test_registry_rejects_malformed_documentation(changes: dict[str, object], message: str) -> None:
    entry = INDUSTRY_MOMENTUM_REGISTRY.filtered(source_family="bls_ces")[0]
    with pytest.raises(IndustryMomentumRegistryError, match=message):
        replace(entry, **changes)


def test_registry_rejects_false_exact_and_level_claims() -> None:
    broader = INDUSTRY_MOMENTUM_REGISTRY.filtered(source_family="bls_ces")[0]
    with pytest.raises(IndustryMomentumRegistryError, match="Exact mappings"):
        replace(broader, mapping_relationship="exact")
    with pytest.raises(IndustryMomentumRegistryError, match="broader mapping"):
        replace(broader, mapping_level="six_digit")


def test_registry_rejects_invalid_change_and_base_contracts() -> None:
    production = next(
        entry
        for entry in INDUSTRY_MOMENTUM_REGISTRY.entries
        if entry.signal_type == "industrial_production_index"
    )
    utilization = next(
        entry
        for entry in INDUSTRY_MOMENTUM_REGISTRY.entries
        if entry.signal_type == "capacity_utilization_rate"
    )
    with pytest.raises(IndustryMomentumRegistryError, match="requires percent_change"):
        replace(production, change_method="percentage_point_change")
    with pytest.raises(IndustryMomentumRegistryError, match="base period"):
        replace(production, base_period=None)
    with pytest.raises(IndustryMomentumRegistryError, match="percentage_point_change"):
        replace(utilization, change_method="percent_change")


def test_filters_are_deterministic_and_support_manual_lookup() -> None:
    entries = INDUSTRY_MOMENTUM_REGISTRY.filtered(source_family="fed_g17")
    assert entries == tuple(sorted(entries, key=lambda item: item.series_id))
    selected = entries[5]
    assert INDUSTRY_MOMENTUM_REGISTRY.by_series_id(selected.series_id, "fed_g17") == selected
    assert selected in INDUSTRY_MOMENTUM_REGISTRY.for_industry(
        selected.target_industry_code, signal_type=selected.signal_type
    )
