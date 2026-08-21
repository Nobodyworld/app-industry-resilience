"""Canonical-only API coverage for Industry Momentum."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from fastapi_compat.testclient import TestClient
from src.application.industry_momentum_service import IndustryMomentumService
from src.interfaces.api.app import app

api_module = importlib.import_module("src.interfaces.api.app")
client = TestClient(app)


def test_list_route_exposes_registry_availability_and_snapshot_summaries() -> None:
    response = client.get("/v1/context/momentum")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 38
    assert set(payload["source_family_availability"]) == {"bls_ppi", "bls_ces", "fed_g17"}
    assert payload["latest_snapshot_summaries"]["bls_ces"]["series_count"] == 8
    assert "contextual official observations" in payload["limitations"][0]


def test_industry_route_full_broader_unmapped_and_empty_states() -> None:
    full = client.get("/v1/context/momentum/325211")
    assert full.status_code == 200
    assert full.json()["availability"] == "available"
    assert full.json()["mapping_relationship"] == "broader_published"
    unmapped = client.get("/v1/context/momentum/999999")
    assert (unmapped.status_code, unmapped.json()["availability"]) == (200, "unmapped")
    empty = client.get("/v1/context/momentum/325211?start=2030-01-01")
    assert (empty.status_code, empty.json()["availability"]) == (200, "empty_range")


def test_filters_are_bounded_and_typed() -> None:
    response = client.get(
        "/v1/context/momentum/325211",
        params={
            "source_family": "bls_ces",
            "signal_type": "employment_count",
            "series_id": "CES3232521101",
            "limit": 2,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["families"]) == 1
    assert len(payload["families"][0]["histories"][0]["observations"]) == 2
    assert client.get("/v1/context/momentum?source_family=bad").status_code == 422
    assert client.get("/v1/context/momentum/325211?limit=121").status_code == 422
    assert client.get("/v1/context/momentum/325211?start=not-a-date").status_code == 422
    assert (
        client.get("/v1/context/momentum/325211?start=2026-02-01&end=2026-01-01").status_code == 400
    )


def test_collection_series_filters_are_consistent_and_unknown_is_deliberate() -> None:
    signal_mismatch = client.get(
        "/v1/context/momentum",
        params={"series_id": "CES3232521101", "signal_type": "capacity_index"},
    )
    assert signal_mismatch.status_code == 400
    assert signal_mismatch.json() == {
        "detail": "series_id does not match the requested source_family or signal_type."
    }

    match = client.get(
        "/v1/context/momentum",
        params={
            "series_id": "CES3232521101",
            "source_family": "bls_ces",
            "signal_type": "employment_count",
        },
    )
    assert match.status_code == 200
    assert match.json()["count"] == 1
    assert match.json()["registry"][0]["series_id"] == "CES3232521101"

    family_mismatch = client.get(
        "/v1/context/momentum",
        params={"series_id": "CES3232521101", "source_family": "fed_g17"},
    )
    assert family_mismatch.status_code == 400

    unknown = client.get("/v1/context/momentum", params={"series_id": "UNKNOWN-SERIES"})
    assert unknown.status_code == 200
    assert unknown.json()["count"] == 0
    assert unknown.json()["registry"] == []


def test_malformed_code_and_mismatched_series_are_stable_errors() -> None:
    assert client.get("/v1/context/momentum/32521").status_code == 422
    mismatch = client.get(
        "/v1/context/momentum/325211?source_family=fed_g17&series_id=CES3232521101"
    )
    assert mismatch.status_code == 400
    assert "path" not in mismatch.text.lower()


def test_partial_and_all_requested_unavailable_behavior(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "not-present-SECRET_MARKER"
    service = IndustryMomentumService(ces_snapshot_path=missing, ces_metadata_path=missing)
    monkeypatch.setattr(api_module, "_industry_momentum_service", service)

    listing = client.get("/v1/context/momentum")
    assert listing.status_code == 200
    assert listing.json()["source_family_availability"]["bls_ces"]["error"] == (
        "Employment snapshot unavailable."
    )
    assert str(tmp_path) not in listing.text
    assert "SECRET_MARKER" not in listing.text

    partial = client.get("/v1/context/momentum/325211")
    assert (partial.status_code, partial.json()["availability"]) == (200, "partial")
    unavailable = client.get("/v1/context/momentum/325211?source_family=bls_ces")
    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "detail": "Requested Industry Momentum snapshots are unavailable."
    }
    assert str(tmp_path) not in unavailable.text
    assert "SECRET_MARKER" not in unavailable.text


def test_openapi_has_only_canonical_v1_routes_and_legacy_ppi_is_unchanged() -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/context/momentum" in paths
    assert "/v1/context/momentum/{industry_code}" in paths
    assert "/context/momentum" not in paths
    assert not any(path.startswith("/v2") for path in paths)
    legacy = client.get("/v1/context/signals/325211")
    assert legacy.status_code == 200
    assert "mapping" in legacy.json()
    assert "families" not in legacy.json()


def test_health_and_annual_routes_survive_momentum_service_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_module, "_industry_momentum_service", None)
    assert client.get("/health").status_code == 200
    assert client.get("/healthz").status_code == 200
    assert client.get("/metrics").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/v1/context/momentum").status_code == 503
