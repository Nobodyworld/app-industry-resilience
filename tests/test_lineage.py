"""Tests for the typed and redacted lineage domain contract."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from src.core import (
    LINEAGE_ATTR_KEY,
    LineageCacheStatus,
    LineageRetrievalMode,
    LineageSourceKind,
    LineageStep,
    append_lineage_step,
    attach_lineage,
    build_lineage,
    lineage_from_dataframe,
    lineage_from_mapping,
    lineage_to_dict,
    update_lineage_cache,
)


def _sample_lineage():
    return build_lineage(
        source="sample",
        source_kind=LineageSourceKind.BUNDLED_SAMPLE,
        dataset_id="sample_industries",
        provider=None,
        observation_period=2023,
        snapshot_at=datetime(2026, 2, 26, tzinfo=UTC),
        retrieval_mode=LineageRetrievalMode.BUNDLED,
        is_sample=True,
        is_official=False,
    )


def test_sample_lineage_serializes_with_explicit_truth_flags() -> None:
    payload = lineage_to_dict(_sample_lineage())

    assert payload == {
        "schema_version": "1",
        "source": "sample",
        "source_kind": "bundled_sample",
        "dataset_id": "sample_industries",
        "provider": None,
        "observation_period": "2023",
        "acquired_at": None,
        "snapshot_at": "2026-02-26T00:00:00Z",
        "retrieval_mode": "bundled",
        "is_sample": True,
        "is_official": False,
        "calculation_version": "1",
        "transformations": [],
        "cache_status": "not_used",
    }


def test_lineage_round_trip_ignores_untyped_extra_fields() -> None:
    payload = lineage_to_dict(_sample_lineage())
    payload["api_key"] = "sentinel-secret"
    payload["absolute_path"] = r"C:\Users\example\private.csv"
    payload["arbitrary_metadata"] = {"token": "sentinel-token"}

    restored = lineage_from_mapping(payload)
    serialized = lineage_to_dict(restored)

    assert restored == _sample_lineage()
    assert "api_key" not in serialized
    assert "absolute_path" not in serialized
    assert "arbitrary_metadata" not in serialized
    assert "sentinel" not in str(serialized)


def test_dataframe_attachment_reads_only_typed_lineage_attribute() -> None:
    frame = pd.DataFrame([{"industry_code": "311", "year": 2023}])
    frame.attrs.update(
        {
            "api_key": "sentinel-secret",
            "cache_dir": r"C:\Users\example\.cache",
            "uploaded_filename": "private-client-data.csv",
        }
    )

    attach_lineage(frame, _sample_lineage())
    restored = lineage_from_dataframe(frame)
    serialized = lineage_to_dict(restored) if restored is not None else {}

    assert restored == _sample_lineage()
    assert LINEAGE_ATTR_KEY in frame.attrs
    assert "sentinel-secret" not in str(serialized)
    assert "private-client-data.csv" not in str(serialized)
    assert r"C:\Users" not in str(serialized)


def test_transformation_details_are_allowlisted_and_ordered() -> None:
    lineage = append_lineage_step(
        _sample_lineage(),
        "filter_records",
        details={
            "filter_applied": True,
            "result_count": 4,
            "search": "unrestricted-user-text",
            "api_key": "sentinel-secret",
        },
    )
    lineage = append_lineage_step(
        lineage,
        LineageStep(
            name="export_serialization",
            details={
                "format": "json",
                "scope": "filtered",
                "record_count": 4,
                "cache_key": "private-cache-key",
            },
        ),
    )

    payload = lineage_to_dict(lineage)

    assert [step["name"] for step in payload["transformations"]] == [
        "filter_records",
        "export_serialization",
    ]
    assert payload["transformations"][0]["details"] == {
        "filter_applied": True,
        "result_count": 4,
    }
    assert payload["transformations"][1]["details"] == {
        "format": "json",
        "record_count": 4,
        "scope": "filtered",
    }
    assert "sentinel" not in str(payload)
    assert "private-cache-key" not in str(payload)


def test_cache_hit_changes_only_cache_state_and_retrieval_mode() -> None:
    original = append_lineage_step(_sample_lineage(), "compute_metrics")
    cached = update_lineage_cache(original, LineageCacheStatus.HIT)

    assert cached.cache_status is LineageCacheStatus.HIT
    assert cached.retrieval_mode is LineageRetrievalMode.CACHE
    assert cached.source == original.source
    assert cached.source_kind is original.source_kind
    assert cached.dataset_id == original.dataset_id
    assert cached.snapshot_at == original.snapshot_at
    assert cached.transformations == original.transformations


def test_cache_miss_preserves_original_retrieval_mode() -> None:
    lineage = build_lineage(
        source="bea",
        source_kind="live_provider",
        dataset_id="bea-gdp-by-industry",
        provider="U.S. Bureau of Economic Analysis",
        observation_period="2023",
        acquired_at="2026-07-15T12:30:00-05:00",
        retrieval_mode="live",
        is_sample=False,
        is_official=True,
    )

    missed = update_lineage_cache(lineage, "miss")

    assert missed.cache_status is LineageCacheStatus.MISS
    assert missed.retrieval_mode is LineageRetrievalMode.LIVE
    assert lineage_to_dict(missed)["acquired_at"] == "2026-07-15T17:30:00Z"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source", r"C:\Users\example\data.csv"),
        ("dataset_id", "/home/example/private.csv"),
        ("dataset_id", "https://user:password@example.com/data?token=secret"),
        ("dataset_id", "client-secret"),
    ],
)
def test_private_identifiers_are_rejected(field: str, value: str) -> None:
    kwargs = {
        "source": "sample",
        "source_kind": "bundled_sample",
        "dataset_id": "sample_industries",
        "observation_period": "2023",
        "retrieval_mode": "bundled",
        "is_sample": True,
        "is_official": False,
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match="Invalid public lineage"):
        build_lineage(**kwargs)


def test_sample_lineage_cannot_claim_official_status() -> None:
    with pytest.raises(ValueError, match="cannot also be marked as official"):
        build_lineage(
            source="sample",
            source_kind="bundled_sample",
            dataset_id="sample_industries",
            observation_period="2023",
            retrieval_mode="bundled",
            is_sample=True,
            is_official=True,
        )


def test_timestamps_require_timezone_information() -> None:
    with pytest.raises(ValueError, match="must include a timezone"):
        build_lineage(
            source="api-inline",
            source_kind="inline_records",
            dataset_id="api-inline",
            observation_period="2023",
            acquired_at=datetime(2026, 7, 15, 12, 0),
            retrieval_mode="inline",
            is_sample=False,
            is_official=False,
        )


def test_unsupported_transformation_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported lineage transformation"):
        LineageStep(name="arbitrary_python_callback", details={"record_count": 1})
