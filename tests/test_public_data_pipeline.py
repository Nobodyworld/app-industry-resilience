from __future__ import annotations

import copy
import io
import zipfile
from collections.abc import Mapping
from typing import Any

import pandas as pd
import pytest
import requests

from src.adapters.aies import AIES_BASIC_URL, AIES_EXPENSE_URL
from src.application.public_data_pipeline import (
    BLS_CES_SERIES,
    BLS_PPI_SERIES,
    FED_G17_FILES,
    FED_G17_SERIES,
    PublicDataPipelineError,
    _bls_latest_fingerprint,
    _latest_series_fingerprint,
    _normalise_bls_ces,
    _normalise_bls_ppi,
    _normalise_fed_g17,
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


def test_bls_normalization_requires_and_orders_all_reviewed_series() -> None:
    cleaned = _normalise_bls_ppi(_bls_payload(value="102.0", reverse_series=True))

    expected_series = [series["series_id"] for series in BLS_PPI_SERIES]
    assert sorted(cleaned["series_id"].unique()) == expected_series
    assert len(cleaned) == len(expected_series) * 3
    assert not cleaned["release_period"].str.endswith("-13").any()
    assert list(zip(cleaned["series_id"], cleaned["observation_date"], strict=True)) == sorted(
        zip(cleaned["series_id"], cleaned["observation_date"], strict=True)
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda payload: payload["Results"]["series"].pop(), "omitted reviewed series"),
        (
            lambda payload: payload["Results"]["series"].append(
                copy.deepcopy(payload["Results"]["series"][0])
            ),
            "duplicate series object",
        ),
        (
            lambda payload: payload["Results"]["series"][0]["data"].append(
                copy.deepcopy(payload["Results"]["series"][0]["data"][0])
            ),
            "duplicate series-month observation",
        ),
        (
            lambda payload: payload["Results"]["series"][0].update({"seriesID": "PCU999999999999"}),
            "unknown series",
        ),
        (
            lambda payload: payload["Results"].update({"series": {}}),
            "Results.series must be a list",
        ),
    ],
)
def test_bls_normalization_rejects_incomplete_or_ambiguous_registry_payloads(
    mutate: Any, message: str
) -> None:
    payload = _bls_payload(value="102.0")
    mutate(payload)

    with pytest.raises(PublicDataPipelineError, match=message):
        _normalise_bls_ppi(payload)


def test_bls_fingerprint_is_deterministic_across_provider_series_ordering() -> None:
    ordered = _normalise_bls_ppi(_bls_payload(value="102.0"))
    reversed_order = _normalise_bls_ppi(_bls_payload(value="102.0", reverse_series=True))

    assert _bls_latest_fingerprint(ordered) == _bls_latest_fingerprint(reversed_order)


def test_bls_listener_detects_revision_in_non_final_series(tmp_path) -> None:
    backfill_public_dataset(
        "bls_ppi_monthly",
        storage_root=tmp_path,
        start_year=2023,
        end_year=2024,
        bls_post=lambda *_: _bls_payload(value="102.0"),
    )
    changed_series = BLS_PPI_SERIES[0]["series_id"]

    revised = listen_for_public_release(
        "bls_ppi_monthly",
        storage_root=tmp_path,
        bls_post=lambda *_: _bls_payload(
            value="102.0",
            latest_values={changed_series: "103.5"},
        ),
    )

    assert changed_series != sorted(series["series_id"] for series in BLS_PPI_SERIES)[-1]
    assert revised.status == "existing_release_revised"


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


def _bls_payload(
    *,
    value: str,
    latest_values: Mapping[str, str] | None = None,
    reverse_series: bool = False,
) -> dict[str, Any]:
    values = latest_values or {}
    series_payload = [
        {
            "seriesID": series["series_id"],
            "data": [
                {
                    "year": "2024",
                    "period": "M02",
                    "periodName": "February",
                    "value": values.get(series["series_id"], value),
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
                {
                    "year": "2024",
                    "period": "M13",
                    "periodName": "Annual",
                    "value": "999.0",
                    "footnotes": [{}],
                },
            ],
        }
        for series in BLS_PPI_SERIES
    ]
    if reverse_series:
        series_payload.reverse()
    return {
        "status": "REQUEST_SUCCEEDED",
        "message": [],
        "Results": {"series": series_payload},
    }


def _ces_payload(*, changed_series: str | None = None) -> dict[str, Any]:
    return {
        "status": "REQUEST_SUCCEEDED",
        "message": [],
        "Results": {
            "series": [
                {
                    "seriesID": entry.series_id,
                    "data": [
                        {
                            "year": "2026",
                            "period": "M01",
                            "value": "101.0" if entry.series_id == changed_series else "100.0",
                        }
                    ],
                }
                for entry in BLS_CES_SERIES
            ]
        },
    }


def _g17_payloads(*, changed_series: str | None = None) -> dict[str, str]:
    payloads: dict[str, str] = {}
    for signal_type in FED_G17_FILES:
        lines = []
        for entry in FED_G17_SERIES:
            if entry.signal_type != signal_type:
                continue
            code = entry.series_id.split(".")[1]
            value = "101.0" if entry.series_id == changed_series else "100.0"
            lines.append(f'"{code}" 2026 {value}')
        payloads[signal_type] = "\n".join(lines)
    return payloads


def test_ces_normalization_backfill_listener_and_nonfinal_revision(tmp_path) -> None:
    baseline = _ces_payload()
    cleaned = _normalise_bls_ces(baseline)
    assert sorted(cleaned["series_id"].unique()) == sorted(
        entry.series_id for entry in BLS_CES_SERIES
    )
    dry_run = backfill_public_dataset(
        "bls_ces_monthly",
        storage_root=tmp_path,
        dry_run=True,
        bls_post=lambda *_: baseline,
    )
    assert (dry_run.status, dry_run.row_count) == ("planned", 8)
    ingested = backfill_public_dataset(
        "bls_ces_monthly", storage_root=tmp_path, bls_post=lambda *_: baseline
    )
    assert ingested.status == "ingest"
    assert (
        listen_for_public_release(
            "bls_ces_monthly", storage_root=tmp_path, bls_post=lambda *_: baseline
        ).status
        == "no_release_changed"
    )
    changed = _ces_payload(changed_series=BLS_CES_SERIES[0].series_id)
    assert (
        listen_for_public_release(
            "bls_ces_monthly", storage_root=tmp_path, bls_post=lambda *_: changed
        ).status
        == "existing_release_revised"
    )


def test_g17_normalization_backfill_listener_and_complete_fingerprint(tmp_path) -> None:
    baseline = _g17_payloads()
    cleaned = _normalise_fed_g17(baseline)
    expected = tuple(entry.series_id for entry in FED_G17_SERIES)
    assert len(cleaned) == 22
    first_fingerprint = _latest_series_fingerprint(cleaned, expected)
    changed_series = FED_G17_SERIES[0].series_id
    revised = _normalise_fed_g17(_g17_payloads(changed_series=changed_series))
    assert _latest_series_fingerprint(revised, expected) != first_fingerprint

    def download(url: str) -> bytes:
        signal_type = next(key for key, value in FED_G17_FILES.items() if value == url)
        return baseline[signal_type].encode()

    result = backfill_public_dataset("fed_g17_monthly", storage_root=tmp_path, download=download)
    assert (result.status, result.row_count, len(result.raw_paths)) == ("ingest", 22, 3)
    assert (
        listen_for_public_release(
            "fed_g17_monthly", storage_root=tmp_path, download=download
        ).status
        == "no_release_changed"
    )


def test_latest_series_fingerprint_requires_full_registry() -> None:
    cleaned = _normalise_bls_ces(_ces_payload())
    incomplete = cleaned.iloc[1:].copy()
    with pytest.raises(PublicDataPipelineError, match="every registered series"):
        _latest_series_fingerprint(incomplete, (entry.series_id for entry in BLS_CES_SERIES))


def test_g17_incomplete_registry_diagnostic_is_provider_neutral_and_revisions_register() -> None:
    baseline = _normalise_fed_g17(_g17_payloads())
    expected = tuple(entry.series_id for entry in FED_G17_SERIES)
    missing_series = FED_G17_SERIES[-1].series_id
    incomplete = baseline[baseline["series_id"] != missing_series].copy()

    with pytest.raises(PublicDataPipelineError) as error:
        _latest_series_fingerprint(incomplete, expected)

    assert str(error.value) == "Cleaned observations must contain every registered series."
    assert "bls" not in str(error.value).lower()

    changed_series = next(
        entry.series_id for entry in FED_G17_SERIES if entry.series_id != missing_series
    )
    revised = _normalise_fed_g17(_g17_payloads(changed_series=changed_series))
    assert _latest_series_fingerprint(revised, expected) != _latest_series_fingerprint(
        baseline, expected
    )
