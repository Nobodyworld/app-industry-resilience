"""Committed snapshot and generator validation tests."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import pytest

from src.application.industry_momentum_service import IndustryMomentumService
from src.core.industry_momentum import INDUSTRY_MOMENTUM_REGISTRY
from src.scripts.generate_industry_momentum_ces_snapshot import validate_committed as validate_ces
from src.scripts.generate_industry_momentum_g17_snapshot import validate_committed as validate_g17

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("stem", "family", "expected_count"),
    [
        ("industry_momentum_bls_ces_snapshot", "bls_ces", 8),
        ("industry_momentum_fed_g17_snapshot", "fed_g17", 22),
    ],
)
def test_committed_snapshot_manifest_hash_and_registry_parity(
    stem: str, family: str, expected_count: int
) -> None:
    csv_path = ROOT / "data" / f"{stem}.csv"
    metadata = json.loads((ROOT / "data" / f"{stem}.metadata.json").read_text())
    payload = csv_path.read_bytes()
    rows = list(csv.DictReader(payload.decode().splitlines()))
    assert hashlib.sha256(payload).hexdigest() == metadata["csv_sha256"]
    assert len(rows) == metadata["row_count"]
    assert len({row["series_id"] for row in rows}) == expected_count
    assert {row["series_id"] for row in rows} == {
        entry.series_id
        for entry in INDUSTRY_MOMENTUM_REGISTRY.filtered(source_family=family)  # type: ignore[arg-type]
    }
    assert rows == sorted(
        rows, key=lambda row: (row["source_family"], row["series_id"], row["observation_date"])
    )
    assert len({(row["series_id"], row["observation_date"]) for row in rows}) == len(rows)
    assert all(math.isfinite(float(row["value"])) for row in rows)
    assert min(row["observation_date"] for row in rows) == "2024-01-01"


def test_generator_validation_only_contracts_accept_committed_files() -> None:
    assert (
        validate_ces(
            ROOT / "data" / "industry_momentum_bls_ces_snapshot.csv",
            ROOT / "data" / "industry_momentum_bls_ces_snapshot.metadata.json",
        )["series_count"]
        == 8
    )
    assert (
        validate_g17(
            ROOT / "data" / "industry_momentum_fed_g17_snapshot.csv",
            ROOT / "data" / "industry_momentum_fed_g17_snapshot.metadata.json",
        )["series_count"]
        == 22
    )


def test_service_construction_is_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("network called")

    monkeypatch.setattr("requests.get", blocked)
    monkeypatch.setattr("requests.post", blocked)
    service = IndustryMomentumService()
    assert service.availability_summary()["bls_ces"]["series_count"] == 8
