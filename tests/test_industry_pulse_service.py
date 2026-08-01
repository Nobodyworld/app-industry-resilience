"""Hermetic snapshot, service, calculation, export, and provenance tests."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import date

import pandas as pd
import pytest

from src.application.industry_pulse_exports import build_industry_pulse_exports
from src.application.industry_pulse_service import IndustryPulseService, _calculate_change
from src.core import LineageStep, attach_lineage, build_lineage, lineage_from_dataframe
from src.core.industry_pulse import (
    INDUSTRY_PULSE_ENDPOINT,
    INDUSTRY_PULSE_REGISTRY,
    INDUSTRY_PULSE_SOURCE,
    IndustryPulseObservation,
    IndustryPulseSnapshotError,
)
from src.scripts.generate_industry_pulse_snapshot import (
    SnapshotGenerationError,
    normalize_response,
    serialize_csv,
)


def _observation(month: str, value: float) -> IndustryPulseObservation:
    mapping = INDUSTRY_PULSE_REGISTRY.entries[0]
    return IndustryPulseObservation(
        series_id=mapping.series_id,
        industry_code=mapping.industry_code,
        industry_name=mapping.registry_label,
        observation_date=date.fromisoformat(f"{month}-01"),
        value=value,
        units=mapping.units,
        seasonal_adjustment=mapping.seasonal_adjustment,
        base_date=mapping.base_date,
        release_period=month,
        source="fixture",
    )


def _provider_payload() -> dict[str, object]:
    series = []
    for entry in INDUSTRY_PULSE_REGISTRY.entries:
        data = [
            {"year": "2024", "period": f"M{month:02d}", "value": str(100 + month)}
            for month in range(1, 13)
        ]
        data.extend(
            [
                {"year": "2025", "period": "M01", "value": "114.5"},
                {"year": "2024", "period": "M13", "value": "999"},
            ]
        )
        series.append({"seriesID": entry.series_id, "data": data})
    return {"status": "REQUEST_SUCCEEDED", "Results": {"series": series}}


def test_committed_snapshot_is_complete_sorted_hashed_and_source_consistent() -> None:
    service = IndustryPulseService(as_of=date(2026, 7, 27))
    metadata = service.metadata
    payload = open("data/industry_pulse_bls_snapshot.csv", "rb").read()
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))

    assert len(rows) == metadata["row_count"] == 240
    assert len({row["series_id"] for row in rows}) == metadata["series_count"] == 8
    assert hashlib.sha256(payload).hexdigest() == metadata["csv_sha256"]
    assert all(
        row["release_period"][5:7] in {f"{month:02d}" for month in range(1, 13)} for row in rows
    )
    assert all(row["source"] == metadata["source_label"] for row in rows)
    assert [(row["series_id"], row["observation_date"]) for row in rows] == sorted(
        (row["series_id"], row["observation_date"]) for row in rows
    )
    assert metadata["observation_range"] == {
        "start": "2024-01-01",
        "end": "2026-06-01",
    }


def test_generator_excludes_m13_rejects_unknown_and_serializes_deterministically() -> None:
    rows = normalize_response(_provider_payload())
    assert len(rows) == 8 * 13
    assert all(row["release_period"] != "2024-13" for row in rows)
    assert serialize_csv(rows) == serialize_csv(rows)

    payload = _provider_payload()
    payload["Results"]["series"][0]["seriesID"] = "PCU999999999999"  # type: ignore[index]
    with pytest.raises(SnapshotGenerationError, match="unknown series"):
        normalize_response(payload)


def test_service_available_unmapped_empty_and_deterministic_ordering() -> None:
    service = IndustryPulseService(as_of=date(2026, 7, 27))
    available = service.for_industry_code("311111")
    unmapped = service.for_industry_code("999999")
    empty = service.for_industry_code("311111", start=date(2030, 1, 1), end=date(2030, 12, 1))

    assert available.availability == "available"
    assert available.latest_observation is not None
    assert available.latest_observation.observation_date == date(2026, 6, 1)
    assert [item.observation_date for item in available.observations] == sorted(
        item.observation_date for item in available.observations
    )
    assert unmapped.availability == "unmapped"
    assert unmapped.freshness.state == "unknown"
    assert empty.availability == "empty_range"
    assert empty.month_over_month.reason == "insufficient_history"


def test_exact_monthly_and_annual_changes_do_not_substitute_missing_periods() -> None:
    complete = tuple(
        [_observation(f"2024-{month:02d}", 100 + month) for month in range(1, 13)]
        + [_observation("2025-01", 114)]
    )
    mom = _calculate_change(complete, months_back=1)
    yoy = _calculate_change(complete, months_back=12)
    assert mom.value_pct == pytest.approx((114 / 112 - 1) * 100)
    assert yoy.value_pct == pytest.approx((114 / 101 - 1) * 100)

    missing_month = (_observation("2024-01", 100), _observation("2024-03", 103))
    assert _calculate_change(missing_month, months_back=1).reason == ("comparison_period_missing")
    missing_year = (_observation("2023-12", 90), _observation("2025-01", 110))
    assert _calculate_change(missing_year, months_back=12).reason == ("comparison_period_missing")
    zero = (_observation("2024-01", 0), _observation("2025-01", 110))
    assert _calculate_change(zero, months_back=12).reason == "denominator_zero"
    assert _calculate_change((_observation("2025-01", 110),), months_back=1).reason == (
        "insufficient_history"
    )


def test_freshness_and_base_dates_remain_series_specific() -> None:
    current = IndustryPulseService(as_of=date(2026, 7, 27)).for_industry_code("311111")
    stale = IndustryPulseService(as_of=date(2027, 1, 1)).for_industry_code("311111")
    computer = IndustryPulseService(as_of=date(2026, 7, 27)).for_industry_code("334111")

    assert current.freshness.state == "current"
    assert stale.freshness.state == "stale"
    assert current.mapping is not None and computer.mapping is not None
    assert current.mapping.base_date != computer.mapping.base_date
    assert current.month_over_month.comparison_period == "2026-05"


def test_exports_parse_repeat_deterministically_and_do_not_mutate_annual_lineage() -> None:
    history = IndustryPulseService(as_of=date(2026, 7, 27)).for_industry_code(
        "311111", start=date(2025, 1, 1), limit=18
    )
    annual = attach_lineage(
        pd.DataFrame([{"industry_code": "311", "year": 2023}]),
        build_lineage(
            source="annual-fixture",
            source_kind="official_snapshot",
            dataset_id="annual-fixture",
            observation_period="2023",
            acquired_at="2026-01-01T00:00:00Z",
            retrieval_mode="snapshot",
            is_sample=False,
            is_official=True,
            transformations=(LineageStep(name="source_load"),),
        ),
    )
    before = lineage_from_dataframe(annual)
    first = build_industry_pulse_exports(history)
    second = build_industry_pulse_exports(history)
    by_extension = {artifact.file_name.rsplit(".", 1)[-1]: artifact for artifact in first}

    csv_rows = list(csv.DictReader(io.StringIO(by_extension["csv"].data.decode("utf-8"))))
    document = json.loads(by_extension["json"].data)
    with zipfile.ZipFile(io.BytesIO(by_extension["xlsx"].data)) as workbook:
        workbook_xml = workbook.read("xl/workbook.xml").decode("utf-8")

    assert len(csv_rows) == len(history.observations)
    required_csv_fields = {
        "provider",
        "source_url",
        "retrieved_at",
        "retrieval_mode",
        "manifest_identity",
        "snapshot_sha256",
        "registry_version",
        "schema_version",
        "observation_start",
        "observation_end",
        "transformations",
        "interpretation_warning",
        "level_comparison_warning",
    }
    assert required_csv_fields.issubset(csv_rows[0])
    assert all(row["manifest_identity"] == history.provenance.manifest_identity for row in csv_rows)
    assert all(row["provider"] == INDUSTRY_PULSE_SOURCE for row in csv_rows)
    assert all(row["source_url"] == INDUSTRY_PULSE_ENDPOINT for row in csv_rows)
    assert all(
        row["source"] == "BLS PPI public API v2 (offline reviewed snapshot)" for row in csv_rows
    )
    assert {row["observation_start"] for row in csv_rows} == {history.observation_start.isoformat()}
    assert {row["observation_end"] for row in csv_rows} == {history.observation_end.isoformat()}
    assert {row["retrieval_mode"] for row in csv_rows} == {"offline_reviewed_snapshot"}
    assert {row["snapshot_sha256"] for row in csv_rows} == {history.provenance.snapshot_sha256}
    assert {row["registry_version"] for row in csv_rows} == {history.provenance.registry_version}
    assert {row["schema_version"] for row in csv_rows} == {history.provenance.schema_version}
    assert all(row["transformations"] for row in csv_rows)
    assert all(row["interpretation_warning"] for row in csv_rows)
    assert all(row["level_comparison_warning"] for row in csv_rows)
    assert document["availability"] == "available"
    assert document["provenance"]["retrieval_mode"] == "offline_reviewed_snapshot"
    assert document == history.to_dict()
    assert 'name="Industry Pulse"' in workbook_xml
    assert 'name="Signal Metadata"' in workbook_xml
    assert [item.data for item in first] == [item.data for item in second]
    assert lineage_from_dataframe(annual) == before
    for serialized in (
        by_extension["csv"].data.decode("utf-8").casefold(),
        by_extension["json"].data.decode("utf-8").casefold(),
    ):
        assert "c:\\\\" not in serialized
        assert "redis" not in serialized
        assert "api_key" not in serialized
        assert "password" not in serialized
        assert "credential" not in serialized


def test_snapshot_hash_tampering_is_rejected(tmp_path) -> None:
    snapshot = tmp_path / "snapshot.csv"
    metadata = tmp_path / "metadata.json"
    snapshot.write_bytes(open("data/industry_pulse_bls_snapshot.csv", "rb").read() + b"\n")
    metadata.write_bytes(open("data/industry_pulse_bls_snapshot.metadata.json", "rb").read())
    with pytest.raises(IndustryPulseSnapshotError, match="SHA-256"):
        IndustryPulseService(snapshot_path=snapshot, metadata_path=metadata)
