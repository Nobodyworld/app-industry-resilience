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
    assert payload["status"] == "ok"
    assert payload["service"] == "idiot-index-api"
    assert "version" in payload
    assert "telemetry" in payload
    assert payload["telemetry"]["metrics"]["counters"] >= 1
    assert payload.get("trace_id") is None or isinstance(payload["trace_id"], str)


def test_healthz_alias_matches_health() -> None:
    base = client.get("/health").json()
    probe = client.get("/healthz").json()

    comparable_keys = {key: value for key, value in base.items() if key != "trace_id"}
    assert comparable_keys == {key: value for key, value in probe.items() if key != "trace_id"}
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

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    assert "idiot_index_api_requests_total" in metrics_response.text
    assert metrics_response.media_type is not None
    assert metrics_response.media_type.startswith("text/plain")


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


def test_scenario_rejects_empty_dataset() -> None:
    scenario_payload = {
        "base_records": [],
        "adjustments": [],
    }

    response = client.post("/scenario", json=scenario_payload)

    assert response.status_code == 400
    assert "dataframe" in response.json()["detail"].lower()
