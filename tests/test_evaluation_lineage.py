"""Evaluation and API tests for typed data-lineage propagation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pandas as pd

from fastapi_compat.testclient import TestClient
from src.application import DataSource, IdiotIndexService
from src.core import MetricConfig, lineage_from_dataframe, lineage_to_dict
from src.interfaces.api.app import app

client = TestClient(app)


def _sample_records(limit: int = 4) -> list[dict[str, object]]:
    frame = pd.read_csv(Path("data") / "sample_industries.csv").head(limit)
    return cast(list[dict[str, object]], json.loads(frame.to_json(orient="records")))


def test_sample_evaluation_tracks_full_and_filtered_pipeline_steps() -> None:
    service = IdiotIndexService(extension_manager=None, observability=None)

    summary = service.evaluate(
        year=2023,
        source=DataSource.SAMPLE,
        search="food",
        top_n=3,
        metric_config=MetricConfig(use_cache=False),
    )

    full_lineage = lineage_from_dataframe(summary.dataframe_full)
    filtered_lineage = lineage_from_dataframe(summary.dataframe_filtered)

    assert full_lineage is not None
    assert filtered_lineage is not None
    assert full_lineage.source == "sample"
    assert full_lineage.source_kind.value == "bundled_sample"
    assert full_lineage.dataset_id == "sample_industries"
    assert full_lineage.observation_period == "2023"
    assert full_lineage.retrieval_mode.value == "bundled"
    assert full_lineage.is_sample is True
    assert full_lineage.is_official is False
    assert full_lineage.cache_status.value == "not_used"
    assert [step.name for step in full_lineage.transformations] == [
        "source_load",
        "normalize_columns",
        "compute_metrics",
        "compute_health_scores",
    ]
    assert [step.name for step in filtered_lineage.transformations] == [
        "source_load",
        "normalize_columns",
        "compute_metrics",
        "compute_health_scores",
        "filter_records",
    ]
    assert filtered_lineage.transformations[-1].details == {
        "filter_applied": True,
        "result_count": len(summary.dataframe_filtered),
    }
    assert "food" not in str(lineage_to_dict(filtered_lineage)).lower()


def test_sample_evaluation_without_search_records_unfiltered_result_count() -> None:
    service = IdiotIndexService(extension_manager=None, observability=None)

    summary = service.evaluate(
        year=2023,
        source=DataSource.SAMPLE,
        top_n=3,
        metric_config=MetricConfig(use_cache=False),
    )
    filtered_lineage = lineage_from_dataframe(summary.dataframe_filtered)

    assert filtered_lineage is not None
    assert filtered_lineage.transformations[-1].name == "filter_records"
    assert filtered_lineage.transformations[-1].details == {
        "filter_applied": False,
        "result_count": len(summary.dataframe_filtered),
    }


def test_v1_evaluate_inline_records_exposes_redacted_typed_lineage() -> None:
    records = _sample_records()
    records[0]["api_key"] = "sentinel-api-key"
    records[0]["cache_dir"] = r"C:\Users\example\.cache"
    records[0]["uploaded_filename"] = "private-client-data.csv"

    response = client.post(
        "/v1/evaluate",
        json={
            "source": "sample",
            "year": records[0]["year"],
            "records": records,
            "top_n": 3,
            "use_cache": False,
        },
    )

    assert response.status_code == 200
    lineage = response.json()["lineage"]
    assert lineage["source"] == "api-inline"
    assert lineage["source_kind"] == "inline_records"
    assert lineage["dataset_id"] == "api-inline"
    assert lineage["observation_period"] == str(records[0]["year"])
    assert lineage["retrieval_mode"] == "inline"
    assert lineage["is_sample"] is False
    assert lineage["is_official"] is False
    assert lineage["acquired_at"].endswith("Z")
    assert [step["name"] for step in lineage["transformations"]] == [
        "source_load",
        "normalize_columns",
        "compute_metrics",
        "compute_health_scores",
    ]
    serialized = json.dumps(lineage)
    assert "sentinel-api-key" not in serialized
    assert "C:\\Users" not in serialized
    assert "private-client-data.csv" not in serialized


def test_v1_health_analytics_exposes_inline_lineage() -> None:
    records = _sample_records()

    response = client.post(
        "/v1/analytics/health",
        json={
            "source": "sample",
            "year": records[0]["year"],
            "records": records,
            "group_by": "sector",
            "top_risks": 2,
        },
    )

    assert response.status_code == 200
    lineage = response.json()["lineage"]
    assert lineage["source"] == "api-inline"
    assert lineage["source_kind"] == "inline_records"
    assert lineage["dataset_id"] == "api-inline"
    assert lineage["transformations"][-1]["name"] == "compute_health_scores"


def test_openapi_exposes_typed_lineage_on_evaluation_responses() -> None:
    schemas = app.openapi()["components"]["schemas"]

    assert schemas["EvaluateResponse"]["properties"]["lineage"] == {
        "anyOf": [
            {"$ref": "#/components/schemas/LineageEnvelopeModel"},
            {"type": "null"},
        ]
    }
    assert schemas["HealthAnalyticsResponse"]["properties"]["lineage"] == {
        "anyOf": [
            {"$ref": "#/components/schemas/LineageEnvelopeModel"},
            {"type": "null"},
        ]
    }
    lineage_schema = schemas["LineageEnvelopeModel"]
    assert {
        "schema_version",
        "source",
        "source_kind",
        "dataset_id",
        "provider",
        "observation_period",
        "acquired_at",
        "snapshot_at",
        "retrieval_mode",
        "is_sample",
        "is_official",
        "calculation_version",
        "transformations",
        "cache_status",
    }.issubset(lineage_schema["properties"])
