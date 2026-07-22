from __future__ import annotations

from dataclasses import replace

import pytest

from src.core.public_data import (
    AUTH_NONE,
    DEFAULT_PUBLIC_DATASETS,
    CatalogValidationError,
    ManifestError,
    ManifestStore,
    ReleaseIdentity,
    ReleaseManifest,
    build_release_manifest,
    hash_payload,
    split_periods_into_eras,
    validate_dataset_catalog,
)


def test_default_public_catalog_covers_readiness_sources() -> None:
    catalog = validate_dataset_catalog(DEFAULT_PUBLIC_DATASETS)

    assert len(catalog) >= 9
    assert {definition.auth_requirement for definition in catalog} == {AUTH_NONE}
    assert "annual" in {definition.update_cadence for definition in catalog}
    assert "monthly" in {definition.update_cadence for definition in catalog}
    assert "quarterly" in {definition.update_cadence for definition in catalog}
    assert "daily" in {definition.update_cadence for definition in catalog}
    assert any(definition.dataset_id == "gdelt_events_daily" for definition in catalog)
    status_by_id = {
        definition.dataset_id: definition.implementation_status for definition in catalog
    }
    assert status_by_id["census_aies_annual"].backfill_validated is True
    assert "census_asm_annual" not in status_by_id
    assert status_by_id["bls_ppi_monthly"].listener_validated is True
    assert status_by_id["census_m3_monthly"].adapter_implemented is False
    assert status_by_id["gdelt_events_daily"].backfill_validated is False


def test_catalog_validation_rejects_non_public_sources() -> None:
    keyed = replace(DEFAULT_PUBLIC_DATASETS[0], auth_requirement="api_key")

    with pytest.raises(CatalogValidationError, match="requires auth"):
        validate_dataset_catalog([keyed])


def test_manifest_store_round_trips_release_metadata(tmp_path) -> None:
    store = ManifestStore(tmp_path)
    manifest = build_release_manifest(
        dataset_id="census_aies_annual",
        release_period="2023",
        source_url="https://example.test/aies.zip",
        content_hash=hash_payload(b"payload"),
        row_count=87,
        columns=["industry_code", "year", "gross_output"],
        fetched_at="2026-07-01T00:00:00Z",
        etag="abc123",
    )

    path = store.write(manifest)
    loaded = store.read("census_aies_annual", "2023")

    assert path.exists()
    assert loaded == manifest


def test_manifest_json_round_trip_preserves_provenance() -> None:
    manifest = build_release_manifest(
        dataset_id="census_aies_annual",
        release_period="2023",
        source_url="https://example.test/aies.zip",
        content_hash=hash_payload(b"payload"),
        row_count=87,
        columns=["industry_code"],
        fetched_at="2026-07-01T00:00:00Z",
        raw_artifact_path="raw/census_aies_annual/2023/basic.zip",
        cleaned_artifact_path="cleaned/census_aies_annual/2023/data.csv",
        transformation_provenance=["downloaded Census AIES archive", "normalized AIES proxy"],
    )

    loaded = ReleaseManifest.from_json(manifest.to_json())

    assert loaded == manifest
    assert loaded.transformation_provenance == (
        "downloaded Census AIES archive",
        "normalized AIES proxy",
    )


def test_manifest_validation_rejects_unsafe_ids_and_hashes(tmp_path) -> None:
    store = ManifestStore(tmp_path)

    with pytest.raises(ManifestError, match="path separators"):
        store.path_for("../escape", "2023")

    with pytest.raises(ManifestError, match="SHA-256"):
        build_release_manifest(
            dataset_id="census_aies_annual",
            release_period="2023",
            source_url="https://example.test/aies.zip",
            content_hash="not-a-hash",
            row_count=1,
            columns=["industry_code"],
        )


def test_manifest_store_records_revision_history_for_changed_hash(tmp_path) -> None:
    store = ManifestStore(tmp_path)
    first = build_release_manifest(
        dataset_id="census_aies_annual",
        release_period="2023",
        source_url="https://example.test/aies.zip",
        content_hash=hash_payload(b"payload-one"),
        row_count=87,
        columns=["industry_code"],
        fetched_at="2026-07-01T00:00:00Z",
    )
    second = build_release_manifest(
        dataset_id="census_aies_annual",
        release_period="2023",
        source_url="https://example.test/aies.zip",
        content_hash=hash_payload(b"payload-two"),
        row_count=88,
        columns=["industry_code"],
        fetched_at="2026-07-02T00:00:00Z",
    )

    store.write(first)
    store.write(second)
    latest = store.read("census_aies_annual", "2023")
    history_files = list(store.history_dir_for("census_aies_annual", "2023").glob("*.json"))

    assert latest is not None
    assert latest.manifest_version == 2
    assert latest.revision_of == first.content_hash
    assert latest.previous_manifest_path is not None
    assert len(history_files) == 1


def test_manifest_store_decisions_cover_release_revision_force_and_schema(tmp_path) -> None:
    store = ManifestStore(tmp_path)
    manifest = build_release_manifest(
        dataset_id="census_aies_annual",
        release_period="2023",
        source_url="https://example.test/aies.zip",
        content_hash=hash_payload(b"payload"),
        row_count=87,
        columns=["industry_code"],
        fetched_at="2026-07-01T00:00:00Z",
    )
    store.write(manifest)

    unseen = store.should_fetch(
        ReleaseIdentity(
            dataset_id="census_aies_annual",
            release_period="2024",
            source_url="https://example.test/aies-2024.zip",
        )
    )
    identical = store.should_fetch(
        ReleaseIdentity(
            dataset_id="census_aies_annual",
            release_period="2023",
            source_url="https://example.test/aies.zip",
            content_hash=manifest.content_hash,
        )
    )
    revision = store.should_fetch(
        ReleaseIdentity(
            dataset_id="census_aies_annual",
            release_period="2023",
            source_url="https://example.test/aies.zip",
            content_hash=hash_payload(b"changed"),
        )
    )
    forced = store.should_fetch(
        ReleaseIdentity(
            dataset_id="census_aies_annual",
            release_period="2023",
            source_url="https://example.test/aies.zip",
            content_hash=manifest.content_hash,
        ),
        force=True,
    )
    schema_change = store.should_fetch(
        ReleaseIdentity(
            dataset_id="census_aies_annual",
            release_period="2023",
            source_url="https://example.test/aies.zip",
            content_hash=manifest.content_hash,
            schema_version="public-data-v2",
        )
    )

    assert (unseen.should_fetch, unseen.action) == (True, "ingest")
    assert (identical.should_fetch, identical.action) == (False, "skip")
    assert (revision.should_fetch, revision.action) == (True, "record_revision")
    assert (forced.should_fetch, forced.reason, forced.action) == (
        True,
        "forced_recollection",
        "ingest",
    )
    assert (schema_change.should_fetch, schema_change.action) == (True, "reprocess_cleaned")
    assert schema_change.requires_raw_download is False


def test_manifest_store_skips_existing_release_by_metadata(tmp_path) -> None:
    store = ManifestStore(tmp_path)
    manifest = build_release_manifest(
        dataset_id="census_aies_annual",
        release_period="2023",
        source_url="https://example.test/aies.zip",
        content_hash=hash_payload(b"payload"),
        row_count=87,
        columns=["industry_code"],
        fetched_at="2026-07-01T00:00:00Z",
        etag="abc123",
    )
    store.write(manifest)

    same_release = store.should_fetch(
        ReleaseIdentity(
            dataset_id="census_aies_annual",
            release_period="2023",
            source_url="https://example.test/aies.zip",
            etag="abc123",
        )
    )
    changed_release = store.should_fetch(
        ReleaseIdentity(
            dataset_id="census_aies_annual",
            release_period="2023",
            source_url="https://example.test/aies.zip",
            etag="def456",
        )
    )

    assert not same_release.should_fetch
    assert same_release.reason == "etag_match"
    assert changed_release.should_fetch
    assert changed_release.reason == "etag_changed"


def test_split_periods_into_balanced_eras() -> None:
    periods = [
        "2024-01",
        "2024-01",
        "2024-02",
        "2024-03",
        "2024-04",
        "2024-05",
        "2024-06",
        "2024-07",
        "2024-08",
        "2024-09",
    ]

    eras = split_periods_into_eras(periods, sections=3)

    assert [era.label for era in eras] == ["era_1", "era_2", "era_3"]
    assert [len(era.periods) for era in eras] == [3, 3, 3]
    assert eras[0].start_period == "2024-01"
    assert eras[0].end_period == "2024-03"
    assert eras[0].observations == 4
    assert eras[-1].end_period == "2024-09"


def test_split_periods_requires_at_least_three_sections() -> None:
    with pytest.raises(ValueError, match="At least three"):
        split_periods_into_eras(["2024-01", "2024-02", "2024-03"], sections=2)
