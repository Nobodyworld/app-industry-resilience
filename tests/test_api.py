"""Tests for headless API endpoints including evaluation, scenario planning, and health checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pandas as pd
import pytest

from fastapi_compat.testclient import TestClient
from src.infrastructure.observability import bootstrap_observability
from src.interfaces.api import dependencies as api_dependencies
from src.interfaces.api.app import app

client = TestClient(app)


def _sample_records(limit: int = 5) -> list[dict[str, object]]:
    data_path = Path("data") / "sample_industries.csv"
    frame = pd.read_csv(data_path).head(limit)
    return cast(list[dict[str, object]], json.loads(frame.to_json(orient="records")))


def test_health_endpoint_reports_ok() -> None:
    response = client.get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] in {"pass", "warn"}
    assert payload["service"] == "idiot-index-api"
    assert "version" in payload
    assert "checked_at" in payload
    assert isinstance(payload["components"], list)
    component_names = {component["name"] for component in payload["components"]}
    assert {"configuration", "cache", "extensions"}.issubset(component_names)
    assert payload["metadata"]["config"]["environment"] in {
        "development",
        "testing",
        "production",
    }
    assert payload["telemetry"] == payload["metadata"].get("telemetry", {})
    assert payload.get("trace_id") is None or isinstance(payload["trace_id"], str)


def test_healthz_alias_matches_health() -> None:
    base = client.get("/health").json()
    probe = client.get("/healthz").json()

    ignore_keys = {"trace_id", "checked_at", "metadata", "telemetry"}
    comparable_keys = _normalise_health_payload(base, ignore_keys)
    assert comparable_keys == _normalise_health_payload(probe, ignore_keys)
    assert base["metadata"]["config"] == probe["metadata"]["config"]
    if base.get("trace_id") and probe.get("trace_id"):
        assert base["trace_id"] != probe["trace_id"]


def test_meta_sources_lists_available_values() -> None:
    response = client.get("/meta/sources")

    assert response.status_code == 200
    assert {"sample", "bea", "census"}.issubset(set(response.json()["sources"]))


def test_meta_connectors_lists_catalog() -> None:
    response = client.get("/meta/connectors")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] >= 1
    identifiers = {item["identifier"] for item in payload["connectors"]}
    assert {"sample_offline", "bea", "census_asm"}.issubset(identifiers)
    sample_entry = next(
        item for item in payload["connectors"] if item["identifier"] == "sample_offline"
    )
    assert sample_entry["kind"] == "data_source"
    assert sample_entry.get("health", {}).get("status") in {"pass", "warn", "fail"}


def test_v1_meta_public_data_lists_truthful_readiness_catalog() -> None:
    response = client.get("/v1/meta/public-data")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == len(payload["datasets"])
    assert payload["implemented_count"] == 2
    assert payload["readiness_complete_count"] == 2
    assert payload["roadmap_count"] == payload["count"] - 2
    assert payload["by_phase"]["phase_1"] == payload["count"]

    by_id = {item["dataset_id"]: item for item in payload["datasets"]}
    assert "census_asm_annual" not in by_id
    assert {item["auth_requirement"] for item in payload["datasets"]} == {"none"}
    assert by_id["census_aies_annual"]["implementation_status"] == {
        "cataloged": True,
        "endpoint_verified": True,
        "adapter_implemented": True,
        "backfill_validated": True,
        "listener_validated": True,
    }
    assert by_id["bls_ppi_monthly"]["implementation_status"]["adapter_implemented"]
    assert not by_id["census_m3_monthly"]["implementation_status"][
        "adapter_implemented"
    ]
    assert by_id["gdelt_events_daily"]["source_type"] == "event_context"
    assert by_id["gdelt_events_daily"]["economic_ground_truth"] is False
    assert client.get("/meta/public-data").status_code == 404


def test_evaluate_with_inline_dataset_returns_leaderboard() -> None:
    records = _sample_records()
    payload = {
        "source": "sample",
        "year": records[0]["year"],
        "records": records,
        "top_n": 3,
    }

    response = client.post("/evaluate", json=payload)
    data = response.json()

    assert response.status_code == 200
    assert data["filters"]["top_n"] == 3
    assert len(data["leaderboard"]) == 3
    assert data["metadata"].get("source") == "api-inline"
    assert len(data["dataset"]["full"]) == len(records)
    assert any("manufacturing_cost_driver" in note for note in data["notes"])
    assert "manufacturing_cost_driver" in data["metadata"].get("extensions", {})
    assert data["health"] is not None
    assert data["health"]["filtered"]["overall"]["average_health_score"] is not None

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    assert "idiot_index_api_requests_total" in metrics_response.text
    assert metrics_response.media_type is not None
    assert metrics_response.media_type.startswith("text/plain")


def test_observability_status_reports_metrics() -> None:
    records = _sample_records(2)
    payload = {
        "source": "sample",
        "year": records[0]["year"],
        "records": records,
        "top_n": 2,
    }
    client.post("/evaluate", json=payload)

    response = client.get("/observability/status")
    data = response.json()

    assert response.status_code == 200
    assert data["metrics"]["counters"] >= 1
    assert isinstance(data["recent_events"], list)
    assert "instrumentation_core" in data["health_checks"]
    assert data["event_counters"]["success"] >= 1
    assert data["last_error"] is None


def test_observability_digest_exposes_subscriptions() -> None:
    response = client.get("/observability/digest")
    payload = response.json()

    assert response.status_code == 200
    assert payload["events"]["total"] >= 0
    assert isinstance(payload["subscriptions"], dict)


def _normalise_health_payload(payload: dict, ignore_keys: set[str]) -> dict:
    filtered = {key: value for key, value in payload.items() if key not in ignore_keys}
    components = []
    for component in filtered.get("components", []):
        normalised = json.loads(json.dumps(component))
        if normalised.get("name") == "observability_snapshots":
            normalised.get("details", {}).pop("latest_snapshot_age_seconds", None)
        components.append(normalised)
    if components:
        filtered["components"] = components
    return filtered


def test_observability_events_endpoint_filters() -> None:
    registry = bootstrap_observability()
    registry.record_event("service.dataset.profile", attributes={"source": "api-test"})
    with pytest.raises(RuntimeError):
        with registry.operation("service.failure", attributes={"source": "api-test"}):
            raise RuntimeError("boom")

    response = client.get("/observability/events", params={"limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_available"] >= 2
    assert payload["applied_limit"] == 5
    assert payload["applied_status"] is None
    assert payload["events"][0]["name"] == "service.failure"

    filtered = client.get("/observability/events", params={"status": "error"})
    assert filtered.status_code == 200
    data = filtered.json()
    assert data["applied_status"] == "error"
    assert data["events"] and all(event["status"] == "error" for event in data["events"])


def test_observability_snapshot_endpoints(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OBSERVABILITY_SNAPSHOT_DIR", str(tmp_path))
    api_dependencies._snapshot_storage_singleton.cache_clear()

    registry = bootstrap_observability()
    storage = api_dependencies.get_snapshot_storage()
    snapshot = registry.capture_snapshot(metadata={"label": "api-test"})
    storage.save(snapshot)

    list_response = client.get("/observability/snapshots")
    assert list_response.status_code == 200
    listing = list_response.json()
    assert listing and listing[0]["snapshot_id"] == snapshot.snapshot_id

    detail_response = client.get(f"/observability/snapshots/{snapshot.snapshot_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["metadata"].get("label") == "api-test"
    assert detail["payload"]["events"]["total"] >= 0

    missing_response = client.get("/observability/snapshots/not-found")
    assert missing_response.status_code == 404

    traversal_response = client.get("/observability/snapshots/bad.id")
    assert traversal_response.status_code == 400
    assert "Snapshot identifiers" in traversal_response.json()["detail"]


def test_evaluate_rejects_invalid_top_n() -> None:
    records = _sample_records()
    payload = {
        "source": "sample",
        "year": records[0]["year"],
        "records": records,
        "top_n": 0,
    }

    response = client.post("/evaluate", json=payload)

    assert response.status_code == 422


def test_scenario_endpoint_returns_delta_metrics() -> None:
    records = _sample_records(3)
    scenario_payload = {
        "base_records": records,
        "adjustments": [
            {"gross_output_delta_pct": 5.0},
            {"materials_cost_delta_pct": -2.5},
        ],
    }

    response = client.post("/scenario", json=scenario_payload)
    data = response.json()

    assert response.status_code == 200
    assert "baseline_summary" in data
    assert "scenario_summary" in data
    assert data["deltas"]
    assert any(delta.get("idiot_index") for delta in data["deltas"])
    metadata = data["metadata"]
    assert "extensions" in metadata
    assert "manufacturing_cost_driver" in metadata["extensions"]
    assert data["baseline_health"] is not None
    assert data["scenario_health"] is not None
    assert data["metadata"]
    lineage = data["lineage"]
    assert lineage["source"] == "api-scenario"
    assert lineage["source_kind"] == "inline_records"
    assert lineage["retrieval_mode"] == "inline"
    assert lineage["is_official"] is False
    assert any(step["name"] == "scenario_adjustment" for step in lineage["transformations"])


def test_scenario_rejects_empty_dataset() -> None:
    scenario_payload: dict[str, list] = {
        "base_records": [],
        "adjustments": [],
    }

    response = client.post("/scenario", json=scenario_payload)

    assert response.status_code == 400
    assert "dataframe" in response.json()["detail"].lower()


def test_health_analytics_endpoint_returns_summary() -> None:
    records = _sample_records(4)
    payload = {
        "source": "sample",
        "year": records[0]["year"],
        "records": records,
        "group_by": "sector",
        "top_risks": 2,
    }

    response = client.post("/analytics/health", json=payload)
    data = response.json()

    assert response.status_code == 200
    assert data["health"]["full"]["overall"]["industries"] >= len(records)
    assert len(data["health"]["filtered"]["sectors"]) >= 1
    assert data["filters"]["search"] is None
