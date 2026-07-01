from __future__ import annotations

import io
import zipfile
from collections.abc import Mapping
from typing import Any

import pandas as pd
import requests

from src.adapters.aies import AIES_BASIC_URL, AIES_EXPENSE_URL
from src.application.public_data_pipeline import (
    backfill_public_dataset,
    listen_for_public_release,
)
from src.core.public_data import ManifestStore


def test_aies_backfill_writes_raw_cleaned_and_manifest(tmp_path) -> None:
    result = backfill_public_dataset(
        "census_aies_annual",
        storage_root=tmp_path,
        start_year=2023,
        end_year=2023,
        download=_aies_download,
        head=_aies_head,
    )

    manifest = ManifestStore(tmp_path / "manifests").read("census_aies_annual", "2023")

    assert result.status == "ingest"
    assert result.row_count == 2
    assert result.manifest_path == "manifests/census_aies_annual/2023.json"
    assert manifest is not None
    assert manifest.etag == "basic-etag|expense-etag"
    assert len(result.raw_paths) == 2
    assert all((tmp_path / path).exists() for path in result.raw_paths)
    assert result.cleaned_path is not None
    cleaned = pd.read_csv(tmp_path / result.cleaned_path)
    assert set(["industry_code", "gross_output", "intermediate_inputs"]).issubset(cleaned.columns)


def test_aies_backfill_dry_run_does_not_write(tmp_path) -> None:
    result = backfill_public_dataset(
        "census_aies_annual",
        storage_root=tmp_path,
        start_year=2023,
        end_year=2023,
        dry_run=True,
    )

    assert result.status == "planned"
    assert not (tmp_path / "raw").exists()
    assert not (tmp_path / "manifests").exists()


def test_bls_ppi_backfill_skips_identical_and_records_revision(tmp_path) -> None:
    first = backfill_public_dataset(
        "bls_ppi_monthly",
        storage_root=tmp_path,
        start_year=2023,
        end_year=2024,
        bls_post=lambda *_: _bls_payload(value="102.0"),
    )
    duplicate = backfill_public_dataset(
        "bls_ppi_monthly",
        storage_root=tmp_path,
        start_year=2023,
        end_year=2024,
        bls_post=lambda *_: _bls_payload(value="102.0"),
    )
    revision = backfill_public_dataset(
        "bls_ppi_monthly",
        storage_root=tmp_path,
        start_year=2023,
        end_year=2024,
        bls_post=lambda *_: _bls_payload(value="103.5"),
    )
    manifest = ManifestStore(tmp_path / "manifests").read("bls_ppi_monthly", first.release_period)
    history_files = list(
        (tmp_path / "manifests" / "bls_ppi_monthly" / f"{first.release_period}.history").glob(
            "*.json"
        )
    )

    assert first.status == "ingest"
    assert duplicate.status == "skipped"
    assert duplicate.reason == "content_hash_match"
    assert revision.status == "record_revision"
    assert manifest is not None
    assert manifest.manifest_version == 2
    assert len(history_files) == 1


def test_bls_listener_reports_new_then_no_change(tmp_path) -> None:
    first = listen_for_public_release(
        "bls_ppi_monthly",
        storage_root=tmp_path,
        bls_post=lambda *_: _bls_payload(value="102.0"),
    )
    backfill_public_dataset(
        "bls_ppi_monthly",
        storage_root=tmp_path,
        start_year=2023,
        end_year=2024,
        bls_post=lambda *_: _bls_payload(value="102.0"),
    )
    second = listen_for_public_release(
        "bls_ppi_monthly",
        storage_root=tmp_path,
        bls_post=lambda *_: _bls_payload(value="102.0"),
    )

    assert first.status == "new_release_available"
    assert second.status == "no_release_changed"


def test_aies_listener_reports_revision_from_changed_headers(tmp_path) -> None:
    backfill_public_dataset(
        "census_aies_annual",
        storage_root=tmp_path,
        start_year=2023,
        end_year=2023,
        download=_aies_download,
        head=_aies_head,
    )

    changed = listen_for_public_release(
        "census_aies_annual",
        storage_root=tmp_path,
        head=lambda url: {**_aies_head(url), "etag": "changed"},
    )

    assert changed.status == "existing_release_revised"


def test_listener_reports_unavailable_and_malformed_sources(tmp_path) -> None:
    def unavailable(_url: str, _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        raise requests.Timeout("temporary timeout")

    unavailable_result = listen_for_public_release(
        "bls_ppi_monthly",
        storage_root=tmp_path,
        bls_post=unavailable,
    )
    malformed_result = listen_for_public_release(
        "bls_ppi_monthly",
        storage_root=tmp_path,
        bls_post=lambda *_: {"status": "REQUEST_SUCCEEDED", "Results": {"series": []}},
    )

    assert unavailable_result.status == "source_unavailable"
    assert malformed_result.status == "source_metadata_malformed"


def _aies_download(url: str) -> bytes:
    if url == AIES_BASIC_URL:
        return _zip_payload(
            "AIES00BASIC.dat",
            "NAICS|NAICS_LABEL|YEAR|GEOTYPE|TYPOP|TAXSTAT|RCPT_TOT_VAL\n"
            "311|Food manufacturing|2023|01|00|00|100\n"
            "312|Beverage manufacturing|2023|01|00|00|200\n",
        )
    if url == AIES_EXPENSE_URL:
        return _zip_payload(
            "AIES00EXP01.dat",
            "NAICS|NAICS_LABEL|YEAR|GEOTYPE|TYPOP|TAXSTAT|EXPS_TOT_DVAL\n"
            "311|Food manufacturing|2023|01|00|00|60\n"
            "312|Beverage manufacturing|2023|01|00|00|120\n",
        )
    raise AssertionError(f"Unexpected URL: {url}")


def _aies_head(url: str) -> Mapping[str, str]:
    if url == AIES_BASIC_URL:
        return {"etag": "basic-etag", "last-modified": "Mon, 01 Jun 2026 00:00:00 GMT"}
    if url == AIES_EXPENSE_URL:
        return {"etag": "expense-etag", "last-modified": "Mon, 01 Jun 2026 00:00:00 GMT"}
    raise AssertionError(f"Unexpected URL: {url}")


def _zip_payload(member: str, text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(member, text)
    return buffer.getvalue()


def _bls_payload(*, value: str) -> dict[str, Any]:
    return {
        "status": "REQUEST_SUCCEEDED",
        "message": [],
        "Results": {
            "series": [
                {
                    "seriesID": "PCU311111311111",
                    "data": [
                        {
                            "year": "2024",
                            "period": "M02",
                            "periodName": "February",
                            "value": value,
                            "footnotes": [{}],
                        },
                        {
                            "year": "2024",
                            "period": "M01",
                            "periodName": "January",
                            "value": "101.0",
                            "footnotes": [{}],
                        },
                        {
                            "year": "2023",
                            "period": "M12",
                            "periodName": "December",
                            "value": "100.0",
                            "footnotes": [{}],
                        },
                    ],
                }
            ]
        },
    }
