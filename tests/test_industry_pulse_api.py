"""Canonical-only API contract tests for Industry Pulse."""

from __future__ import annotations

from fastapi_compat.testclient import TestClient
from src.interfaces.api.app import app

client = TestClient(app)


def test_signal_list_route_exposes_all_verified_mappings_and_bounded_summaries() -> None:
    response = client.get("/v1/context/signals")
    payload = response.json()

    assert response.status_code == 200
    assert response.headers == {}
    assert payload["count"] == 8
    assert all(item["availability"] == "available" for item in payload["signals"])
    assert all(len(item["observations"]) == 1 for item in payload["signals"])
    assert {item["mapping"]["industry_code"] for item in payload["signals"]} == {
        "311111",
        "312120",
        "322120",
        "325211",
        "326111",
        "331110",
        "334111",
        "336110",
    }


def test_industry_route_available_unmapped_and_empty_range_states() -> None:
    available = client.get("/v1/context/signals/311111")
    unmapped = client.get("/v1/context/signals/999999")
    empty = client.get(
        "/v1/context/signals/311111",
        params={"start": "2030-01", "end": "2030-12"},
    )

    assert available.status_code == unmapped.status_code == empty.status_code == 200
    assert available.json()["availability"] == "available"
    assert available.json()["latest_observation"]["observation_date"] == "2026-06-01"
    assert unmapped.json()["availability"] == "unmapped"
    assert empty.json()["availability"] == "empty_range"


def test_signal_filters_series_lookup_and_result_bounds() -> None:
    filtered = client.get(
        "/v1/context/signals/311111",
        params={"start": "2025-01", "end": "2025-06", "limit": 3},
    )
    by_series = client.get(
        "/v1/context/signals",
        params={"series_id": "PCU311111311111", "limit": 2},
    )

    assert filtered.status_code == 200
    assert [row["observation_date"] for row in filtered.json()["observations"]] == [
        "2025-04-01",
        "2025-05-01",
        "2025-06-01",
    ]
    assert by_series.json()["count"] == 1
    assert len(by_series.json()["signals"][0]["observations"]) == 2


def test_signal_validation_errors_are_stable_and_typed() -> None:
    assert client.get("/v1/context/signals/311").status_code == 422
    assert (
        client.get("/v1/context/signals/311111", params={"start": "not-a-date"}).status_code == 422
    )
    reversed_range = client.get(
        "/v1/context/signals/311111",
        params={"start": "2026-06", "end": "2025-01"},
    )
    mismatch = client.get(
        "/v1/context/signals/311111",
        params={"series_id": "PCU312120312120"},
    )
    assert reversed_range.status_code == 400
    assert reversed_range.json() == {"detail": "start date cannot be after end date."}
    assert mismatch.status_code == 400


def test_live_openapi_contains_only_canonical_context_routes() -> None:
    document = client.get("/openapi.json").json()
    paths = document["paths"]

    assert "/v1/context/signals" in paths
    assert "/v1/context/signals/{industry_code}" in paths
    assert paths["/v1/context/signals"]["get"].get("deprecated") is not True
    assert paths["/v1/context/signals/{industry_code}"]["get"].get("deprecated") is not True
    assert "/context/signals" not in paths
    assert "/context/signals/{industry_code}" not in paths
    assert not any(path.startswith("/v2/") for path in paths)
    schemas = document["components"]["schemas"]
    assert "IndustryPulseResponse" in schemas
    assert "IndustryPulseProvenanceModel" in schemas
