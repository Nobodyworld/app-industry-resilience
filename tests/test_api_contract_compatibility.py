"""Compatibility tests for canonical v1 and deprecated legacy API routes."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pandas as pd

from fastapi_compat.testclient import TestClient
from src.interfaces.api.app import app

client = TestClient(app)

SUNSET = "Fri, 15 Jan 2027 00:00:00 GMT"
ROUTE_PAIRS = (
    ("get", "/v1/meta/sources", "/meta/sources"),
    ("get", "/v1/meta/connectors", "/meta/connectors"),
    ("post", "/v1/evaluate", "/evaluate"),
    ("post", "/v1/scenario", "/scenario"),
    ("post", "/v1/analytics/health", "/analytics/health"),
)
OPERATIONAL_PATHS = {
    "/health",
    "/healthz",
    "/metrics",
    "/observability/status",
    "/observability/digest",
    "/observability/events",
    "/observability/snapshots",
    "/observability/snapshots/{snapshot_id}",
}


def _sample_records(limit: int = 4) -> list[dict[str, object]]:
    frame = pd.read_csv(Path("data") / "sample_industries.csv").head(limit)
    return cast(list[dict[str, object]], json.loads(frame.to_json(orient="records")))


def _evaluate_payload() -> dict[str, object]:
    records = _sample_records()
    return {
        "source": "sample",
        "year": records[0]["year"],
        "records": records,
        "top_n": 3,
    }


def _scenario_payload() -> dict[str, object]:
    return {
        "base_records": _sample_records(3),
        "adjustments": [{"gross_output_delta_pct": 5.0}],
    }


def _health_payload() -> dict[str, object]:
    records = _sample_records()
    return {
        "source": "sample",
        "year": records[0]["year"],
        "records": records,
        "group_by": "sector",
        "top_risks": 2,
    }


def _normalise_payload(payload: Any) -> Any:
    normalised = deepcopy(payload)
    if isinstance(normalised, dict):
        lineage = normalised.get("lineage")
        if isinstance(lineage, dict):
            lineage.pop("acquired_at", None)

        metadata = normalised.get("metadata")
        if isinstance(metadata, dict):
            metadata_lineage = metadata.get("lineage")
            if isinstance(metadata_lineage, dict):
                metadata_lineage.pop("acquired_at", None)

            telemetry = metadata.get("telemetry")
            if isinstance(telemetry, dict):
                telemetry.pop("trace_id", None)
                if not telemetry:
                    metadata.pop("telemetry", None)
    return normalised


def _request(method: str, path: str):
    if method == "get":
        return client.get(path)
    if path.endswith("/evaluate") or path == "/evaluate":
        return client.post(path, json=_evaluate_payload())
    if path.endswith("/scenario") or path == "/scenario":
        return client.post(path, json=_scenario_payload())
    return client.post(path, json=_health_payload())


def test_openapi_contains_canonical_and_deprecated_alias_routes() -> None:
    document = app.openapi()
    paths = document["paths"]

    for method, canonical, legacy in ROUTE_PAIRS:
        canonical_operation = paths[canonical][method]
        legacy_operation = paths[legacy][method]

        assert canonical_operation.get("deprecated") is not True
        assert legacy_operation["deprecated"] is True
        assert (
            canonical_operation["responses"]["200"]["content"]
            == legacy_operation["responses"]["200"]["content"]
        )
        if method == "post":
            assert canonical_operation["requestBody"] == legacy_operation["requestBody"]

    assert OPERATIONAL_PATHS.issubset(paths)
    assert not any(path.startswith("/v1/health") for path in paths)
    assert not any(path.startswith("/v1/metrics") for path in paths)
    assert not any(path.startswith("/v1/observability") for path in paths)
    assert not any(path.startswith("/v2/") for path in paths)


def test_legacy_aliases_include_centralized_migration_headers() -> None:
    for method, canonical, legacy in ROUTE_PAIRS:
        legacy_response = _request(method, legacy)
        canonical_response = _request(method, canonical)

        assert legacy_response.status_code == 200
        assert legacy_response.headers == {
            "Deprecation": "true",
            "Sunset": SUNSET,
            "Link": f'<{canonical}>; rel="successor-version"',
        }
        assert canonical_response.status_code == 200
        assert canonical_response.headers == {}


def test_canonical_and_legacy_payloads_are_equivalent() -> None:
    for method, canonical, legacy in ROUTE_PAIRS:
        canonical_response = _request(method, canonical)
        legacy_response = _request(method, legacy)

        assert canonical_response.status_code == legacy_response.status_code == 200
        assert _normalise_payload(canonical_response.json()) == _normalise_payload(
            legacy_response.json()
        )


def test_validation_status_is_preserved_across_evaluate_routes() -> None:
    payload = _evaluate_payload()
    payload["top_n"] = 0

    canonical = client.post("/v1/evaluate", json=payload)
    legacy = client.post("/evaluate", json=payload)

    assert canonical.status_code == legacy.status_code == 422
    assert canonical.json() == legacy.json()


def test_v2_routes_are_not_introduced() -> None:
    response = client.post("/v2/evaluate", json=_evaluate_payload())

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_compatibility_sensitive_schema_fields_remain_present() -> None:
    schemas = app.openapi()["components"]["schemas"]

    assert {
        "source",
        "year",
        "search",
        "top_n",
        "records",
        "use_cache",
    }.issubset(schemas["EvaluateRequest"]["properties"])
    assert {
        "source",
        "year",
        "filters",
        "average_idiot_index",
        "notes",
        "leaderboard",
        "dataset",
        "metadata",
        "health",
    }.issubset(schemas["EvaluateResponse"]["properties"])
    assert {
        "base_records",
        "adjustments",
        "use_cache",
    }.issubset(schemas["ScenarioRequest"]["properties"])
    assert {
        "baseline_summary",
        "scenario_summary",
        "delta_summary",
        "baseline",
        "scenario",
        "deltas",
        "metadata",
    }.issubset(schemas["ScenarioResponse"]["properties"])
