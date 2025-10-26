from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from fastapi.testclient import TestClient
from src.interfaces.api.app import app

client = TestClient(app)


def _sample_records(limit: int = 5) -> list[dict[str, object]]:
    data_path = Path("data") / "sample_industries.csv"
    frame = pd.read_csv(data_path).head(limit)
    return json.loads(frame.to_json(orient="records"))


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
    comparable_keys = {key: value for key, value in base.items() if key not in ignore_keys}
    assert comparable_keys == {key: value for key, value in probe.items() if key not in ignore_keys}
    assert base["metadata"]["config"] == probe["metadata"]["config"]
    if base.get("trace_id") and probe.get("trace_id"):
        assert base["trace_id"] != probe["trace_id"]


def test_meta_sources_lists_available_values() -> None:
    response = client.get("/meta/sources")

    assert response.status_code == 200
    assert {"sample", "bea", "census"}.issubset(set(response.json()["sources"]))


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


def test_scenario_rejects_empty_dataset() -> None:
    scenario_payload = {
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
