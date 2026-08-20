"""Calculation, service degradation, and export contracts for Industry Momentum."""

from __future__ import annotations

import csv
import json
from datetime import date
from io import BytesIO, StringIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from src.application.industry_momentum_exports import build_industry_momentum_exports
from src.application.industry_momentum_service import (
    IndustryMomentumService,
    _calculate_change,
)
from src.application.industry_pulse_service import IndustryPulseService
from src.core.industry_momentum import (
    INDUSTRY_MOMENTUM_REGISTRY,
    IndustryMomentumObservation,
)


def _observation(
    period: date, value: float, *, utilization: bool = False
) -> IndustryMomentumObservation:
    signal_type = "capacity_utilization_rate" if utilization else "employment_count"
    return IndustryMomentumObservation(
        source_family="fed_g17" if utilization else "bls_ces",
        signal_type=signal_type,
        series_id="CAPUTL.G325.S" if utilization else "CES3232521101",
        published_industry_code="325" if utilization else "325211",
        target_industry_code="325211",
        mapping_relationship="broader_published" if utilization else "exact",
        observation_date=period,
        value=value,
        units="Percent" if utilization else "Thousands of employees",
        seasonal_adjustment="Seasonally adjusted",
        base_period=None,
        release_period=period.strftime("%Y-%m"),
        source="official fixture",
    )


def test_exact_percent_mom_and_yoy_changes() -> None:
    observations = (
        _observation(date(2025, 2, 1), 100),
        _observation(date(2026, 1, 1), 110),
        _observation(date(2026, 2, 1), 120),
    )
    assert _calculate_change(observations, "percent_change", 1).value == pytest.approx(9.090909)
    assert _calculate_change(observations, "percent_change", 12).value == pytest.approx(20)


def test_exact_percentage_point_mom_and_yoy_changes() -> None:
    observations = (
        _observation(date(2025, 2, 1), 70, utilization=True),
        _observation(date(2026, 1, 1), 72, utilization=True),
        _observation(date(2026, 2, 1), 75, utilization=True),
    )
    mom = _calculate_change(observations, "percentage_point_change", 1)
    yoy = _calculate_change(observations, "percentage_point_change", 12)
    assert (mom.value, mom.units, mom.method) == (3, "percentage points", "percentage_point_change")
    assert yoy.value == 5


def test_change_reasons_do_not_substitute_nearest_or_divide_by_zero() -> None:
    observations = (
        _observation(date(2026, 1, 1), 0),
        _observation(date(2026, 3, 1), 10),
    )
    assert (
        _calculate_change(observations, "percent_change", 1).unavailable_reason
        == "comparison_period_missing"
    )
    assert (
        _calculate_change(observations, "percent_change", 2).unavailable_reason
        == "denominator_zero"
    )
    assert _calculate_change((), "percent_change", 1).unavailable_reason == "insufficient_history"
    malformed = SimpleNamespace(observation_date=date(2026, 3, 2), value=10)
    assert _calculate_change((malformed,), "percent_change", 1).unavailable_reason == "period_malformed"  # type: ignore[arg-type]


def test_full_service_state_filters_order_and_broader_mapping() -> None:
    service = IndustryMomentumService(as_of=date(2026, 8, 10))
    result = service.for_industry_code("325211")
    assert result.availability == "available"
    assert [family.source_family for family in result.families] == ["bls_ppi", "bls_ces", "fed_g17"]
    assert sum(len(family.histories) for family in result.families) == 5
    assert result.mapping_relationship == "broader_published"
    employment = service.for_industry_code("325211", source_family="bls_ces", limit=2)
    assert len(employment.families) == 1
    assert len(employment.families[0].histories[0].observations) == 2
    assert service.for_series_id("CES3232521101").availability == "available"
    assert service.for_series_id("unknown").availability == "unmapped"


def test_unmapped_empty_stale_current_unknown_and_family_freshness_states() -> None:
    as_of = date(2026, 8, 10)
    service = IndustryMomentumService(as_of=as_of)
    assert service.for_industry_code("999999").availability == "unmapped"
    empty = service.for_industry_code("325211", start=date(2030, 1, 1))
    assert empty.availability == "empty_range"
    assert all(
        history.freshness.state == "unknown"
        for family in empty.families
        for history in family.histories
    )

    ppi_freshness = service.for_industry_code(
        "325211", source_family="bls_ppi"
    ).families[0].histories[0].freshness
    released_ppi_freshness = IndustryPulseService(as_of=as_of).for_industry_code(
        "325211"
    ).freshness
    assert ppi_freshness.state == released_ppi_freshness.state
    assert ppi_freshness.age_days == released_ppi_freshness.age_days
    assert ppi_freshness.threshold_days == released_ppi_freshness.threshold_days == 90

    ces_freshness = service.for_industry_code(
        "325211", source_family="bls_ces"
    ).families[0].histories[0].freshness
    g17_freshness = service.for_industry_code(
        "325211", source_family="fed_g17"
    ).families[0].histories[0].freshness
    assert ces_freshness.threshold_days == 120
    assert g17_freshness.threshold_days == 120
    assert ces_freshness.state == "current"

    stale = IndustryMomentumService(as_of=date(2027, 1, 1)).for_industry_code("325211")
    assert all(
        history.freshness.state == "stale"
        for family in stale.families
        for history in family.histories
    )


def test_one_family_failure_is_partial_requested_failure_and_summary_are_sanitized(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-SECRET_MARKER.csv"
    service = IndustryMomentumService(ces_snapshot_path=missing, ces_metadata_path=missing)
    assert service.for_industry_code("325211").availability == "partial"
    requested = service.for_industry_code("325211", source_family="bls_ces")
    assert requested.availability == "unavailable"
    assert requested.families[0].histories[0].provenance is None

    public_payload = json.dumps(
        {
            "result": requested.to_dict(),
            "availability": service.availability_summary(),
            "metadata": service.metadata,
        }
    )
    assert str(tmp_path) not in public_payload
    assert "SECRET_MARKER" not in public_payload
    assert service.availability_summary()["bls_ces"]["error"] == "Employment snapshot unavailable."


def test_ppi_failure_summary_is_sanitized() -> None:
    class BrokenPulse:
        freshness_threshold_days = 90

        def for_industry_code(self, industry_code: str) -> object:
            raise ValueError(f"private snapshot failure for {industry_code}: SECRET_MARKER")

    service = IndustryMomentumService(pulse_service=BrokenPulse())  # type: ignore[arg-type]
    public_payload = json.dumps(service.availability_summary())
    assert "SECRET_MARKER" not in public_payload
    assert "private snapshot failure" not in public_payload
    assert service.availability_summary()["bls_ppi"]["error"] == (
        "Producer price snapshot unavailable."
    )


def test_filter_validation() -> None:
    service = IndustryMomentumService()
    with pytest.raises(ValueError, match="start date"):
        service.for_industry_code("325211", start=date(2026, 2, 1), end=date(2026, 1, 1))
    with pytest.raises(ValueError, match="limit"):
        service.for_industry_code("325211", limit=121)
    with pytest.raises(ValueError, match="Freshness thresholds"):
        IndustryMomentumService(ppi_freshness_threshold_days=0)
    with pytest.raises(ValueError, match="Freshness thresholds"):
        IndustryMomentumService(ces_freshness_threshold_days=0)
    with pytest.raises(ValueError, match="Freshness thresholds"):
        IndustryMomentumService(g17_freshness_threshold_days=0)


def test_exports_parse_and_are_deterministic_and_private() -> None:
    result = IndustryMomentumService(as_of=date(2026, 8, 10)).for_industry_code("325211")
    first = build_industry_momentum_exports(result)
    second = build_industry_momentum_exports(result)
    assert [item.data for item in first] == [item.data for item in second]
    rows = list(csv.DictReader(StringIO(first[0].data.decode())))
    assert rows
    assert {row["source_family"] for row in rows} == {"bls_ppi", "bls_ces", "fed_g17"}
    assert json.loads(first[1].data)["availability"] == "available"
    with ZipFile(BytesIO(first[2].data)) as archive:
        workbook = archive.read("xl/workbook.xml").decode()
    for sheet in (
        "Price Signals",
        "Employment Signals",
        "Production Signals",
        "Capacity Signals",
        "Signal Metadata",
    ):
        assert f'name="{sheet}"' in workbook
    private_markers = (b"C:\\", b".venv", b"REDIS", b"API_KEY")
    assert not any(marker in item.data for item in first for marker in private_markers)


def test_registry_listing_is_independent_of_snapshot_state(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    service = IndustryMomentumService(
        ces_snapshot_path=missing,
        ces_metadata_path=missing,
        g17_snapshot_path=missing,
        g17_metadata_path=missing,
    )
    assert service.list_mappings() == INDUSTRY_MOMENTUM_REGISTRY.entries
