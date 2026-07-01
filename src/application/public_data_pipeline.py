"""Public data backfill and release-listener workflow for implemented sources."""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import requests

from src.adapters.aies import (
    AIES_BASIC_URL,
    AIES_EXPENSE_URL,
    AIES_RELEASE_DATE,
    AIES_SURVEY_YEAR,
    build_aies_snapshot,
)
from src.core.public_data import (
    DEFAULT_CLEANING_VERSION,
    DEFAULT_SCHEMA_VERSION,
    DIRECT_INDUSTRY_SCHEMA,
    SIGNAL_SCHEMA,
    ManifestStore,
    ReleaseIdentity,
    build_release_manifest,
    hash_payload,
)

DatasetId = Literal["census_aies_annual", "bls_ppi_monthly"]
Download = Callable[[str], bytes]
Head = Callable[[str], Mapping[str, str]]
BLSPost = Callable[[str, Mapping[str, Any]], Mapping[str, Any]]

PUBLIC_DATA_ROOT = Path("data/public")
BLS_PPI_ENDPOINT = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_PPI_SERIES: tuple[dict[str, str], ...] = (
    {
        "series_id": "PCU311111311111",
        "industry_code": "311111",
        "industry_name": "Dog and Cat Food Manufacturing",
        "signal_name": "PPI industry index for NAICS 311111",
        "units": "Index value, base period varies by BLS series",
        "seasonal_adjustment": "not seasonally adjusted",
        "mapping_notes": "BLS PCU series identifier embeds industry code 311111 and product code 311111.",
    },
)


class PublicDataPipelineError(RuntimeError):
    """Raised when public data readiness workflows cannot complete."""


@dataclass(frozen=True)
class BackfillResult:
    """Outcome of a public data backfill operation."""

    dataset_id: str
    release_period: str
    status: str
    reason: str
    dry_run: bool
    row_count: int = 0
    raw_paths: tuple[str, ...] = ()
    cleaned_path: str | None = None
    manifest_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "release_period": self.release_period,
            "status": self.status,
            "reason": self.reason,
            "dry_run": self.dry_run,
            "row_count": self.row_count,
            "raw_paths": list(self.raw_paths),
            "cleaned_path": self.cleaned_path,
            "manifest_path": self.manifest_path,
        }


@dataclass(frozen=True)
class ReleaseListenerResult:
    """Release metadata observed by a public-source listener."""

    dataset_id: str
    release_period: str | None
    status: str
    source_url: str | None = None
    content_hash: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "release_period": self.release_period,
            "status": self.status,
            "source_url": self.source_url,
            "content_hash": self.content_hash,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "message": self.message,
        }


def backfill_public_dataset(
    dataset_id: DatasetId,
    *,
    storage_root: Path | str = PUBLIC_DATA_ROOT,
    start_year: int | None = None,
    end_year: int | None = None,
    dry_run: bool = False,
    force: bool = False,
    download: Download | None = None,
    head: Head | None = None,
    bls_post: BLSPost | None = None,
) -> BackfillResult:
    """Backfill one implemented public dataset into raw, cleaned, and manifest storage."""

    root = Path(storage_root)
    if dataset_id == "census_aies_annual":
        return _backfill_aies(root, start_year, end_year, dry_run, force, download, head)
    if dataset_id == "bls_ppi_monthly":
        return _backfill_bls_ppi(root, start_year, end_year, dry_run, force, bls_post)
    raise PublicDataPipelineError(f"Dataset is cataloged but not implemented: {dataset_id}")


def listen_for_public_release(
    dataset_id: DatasetId,
    *,
    storage_root: Path | str = PUBLIC_DATA_ROOT,
    head: Head | None = None,
    bls_post: BLSPost | None = None,
) -> ReleaseListenerResult:
    """Check official release metadata without performing a full ingestion."""

    root = Path(storage_root)
    if dataset_id == "census_aies_annual":
        return _listen_aies(root, head)
    if dataset_id == "bls_ppi_monthly":
        return _listen_bls_ppi(root, bls_post)
    raise PublicDataPipelineError(f"Dataset is cataloged but not implemented: {dataset_id}")


def _backfill_aies(
    root: Path,
    start_year: int | None,
    end_year: int | None,
    dry_run: bool,
    force: bool,
    download: Download | None,
    head: Head | None,
) -> BackfillResult:
    year = AIES_SURVEY_YEAR
    if start_year is not None and year < start_year:
        return _unsupported_range("census_aies_annual", str(year), dry_run)
    if end_year is not None and year > end_year:
        return _unsupported_range("census_aies_annual", str(year), dry_run)

    if dry_run:
        return BackfillResult(
            dataset_id="census_aies_annual",
            release_period=str(year),
            status="planned",
            reason="dry_run",
            dry_run=True,
        )

    downloader = download or _download_url
    basic_payload = downloader(AIES_BASIC_URL)
    expense_payload = downloader(AIES_EXPENSE_URL)
    content_hash = hash_payload(basic_payload + b"\0" + expense_payload)
    etag, last_modified = _aies_listener_headers(head)

    store = _manifest_store(root)
    decision = store.should_fetch(
        ReleaseIdentity(
            dataset_id="census_aies_annual",
            release_period=str(year),
            source_url=AIES_BASIC_URL,
            content_hash=content_hash,
            etag=etag,
            last_modified=last_modified,
            schema_version=DEFAULT_SCHEMA_VERSION,
            cleaning_version=DEFAULT_CLEANING_VERSION,
        ),
        force=force,
    )
    if not decision.should_fetch:
        return BackfillResult(
            dataset_id="census_aies_annual",
            release_period=str(year),
            status="skipped",
            reason=decision.reason,
            dry_run=False,
        )

    basic = _read_aies_zip_table(basic_payload, "AIES00BASIC.dat")
    expenses = _read_aies_zip_table(expense_payload, "AIES00EXP01.dat")
    cleaned = build_aies_snapshot(basic, expenses)
    _validate_columns(cleaned, DIRECT_INDUSTRY_SCHEMA, "census_aies_annual")

    raw_dir = _artifact_dir(root, "raw", "census_aies_annual", str(year))
    cleaned_dir = _artifact_dir(root, "cleaned", "census_aies_annual", str(year))
    raw_basic = raw_dir / f"AIES00BASIC-{content_hash[:12]}.zip"
    raw_expense = raw_dir / f"AIES00EXP01-{content_hash[:12]}.zip"
    cleaned_path = cleaned_dir / f"census_aies_annual-{content_hash[:12]}.csv"
    _write_bytes_if_missing(raw_basic, basic_payload)
    _write_bytes_if_missing(raw_expense, expense_payload)
    _write_csv(cleaned_path, cleaned)

    manifest = build_release_manifest(
        dataset_id="census_aies_annual",
        release_period=str(year),
        source_url=AIES_BASIC_URL,
        content_hash=content_hash,
        row_count=int(cleaned.shape[0]),
        columns=cleaned.columns,
        etag=etag,
        last_modified=last_modified,
        observation_start=str(year),
        observation_end=str(year),
        release_notes_url="https://www.census.gov/programs-surveys/aies.html",
        raw_artifact_path=_relative_to(root, raw_basic),
        cleaned_artifact_path=_relative_to(root, cleaned_path),
        transformation_provenance=(
            "downloaded Census AIES basic and operating-expense ZIP archives",
            "merged national 2- and 3-digit NAICS rows",
            "normalized revenue and operating expenses into the application proxy schema",
        ),
        notes=(
            f"AIES release date: {AIES_RELEASE_DATE}",
            "AIES operating expenses are a proxy denominator, not BEA intermediate inputs.",
        ),
    )
    manifest_path = store.write(manifest)
    return BackfillResult(
        dataset_id="census_aies_annual",
        release_period=str(year),
        status=decision.action,
        reason=decision.reason,
        dry_run=False,
        row_count=int(cleaned.shape[0]),
        raw_paths=(_relative_to(root, raw_basic), _relative_to(root, raw_expense)),
        cleaned_path=_relative_to(root, cleaned_path),
        manifest_path=_relative_to(root, manifest_path),
    )


def _backfill_bls_ppi(
    root: Path,
    start_year: int | None,
    end_year: int | None,
    dry_run: bool,
    force: bool,
    bls_post: BLSPost | None,
) -> BackfillResult:
    end = end_year or pd.Timestamp.utcnow().year
    start = start_year or max(end - 2, 1913)
    if start > end:
        raise PublicDataPipelineError("start_year cannot be greater than end_year")
    poster = bls_post or _post_bls_json
    payload = poster(
        BLS_PPI_ENDPOINT,
        {
            "seriesid": [series["series_id"] for series in BLS_PPI_SERIES],
            "startyear": str(start),
            "endyear": str(end),
        },
    )
    cleaned = _normalise_bls_ppi(payload)
    if cleaned.empty:
        raise PublicDataPipelineError("BLS PPI response did not contain usable observations.")
    release_period = str(cleaned["release_period"].max())
    content_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    raw_hash = hash_payload(content_bytes)
    content_hash = hash_payload(cleaned.to_csv(index=False).encode("utf-8"))
    latest_fingerprint = _bls_latest_fingerprint(cleaned)
    if dry_run:
        return BackfillResult(
            dataset_id="bls_ppi_monthly",
            release_period=release_period,
            status="planned",
            reason="dry_run",
            dry_run=True,
            row_count=int(cleaned.shape[0]),
        )

    store = _manifest_store(root)
    decision = store.should_fetch(
        ReleaseIdentity(
            dataset_id="bls_ppi_monthly",
            release_period=release_period,
            source_url=BLS_PPI_ENDPOINT,
            content_hash=content_hash,
            etag=latest_fingerprint,
            schema_version=DEFAULT_SCHEMA_VERSION,
            cleaning_version=DEFAULT_CLEANING_VERSION,
        ),
        force=force,
    )
    if not decision.should_fetch:
        return BackfillResult(
            dataset_id="bls_ppi_monthly",
            release_period=release_period,
            status="skipped",
            reason=decision.reason,
            dry_run=False,
        )

    raw_dir = _artifact_dir(root, "raw", "bls_ppi_monthly", release_period)
    cleaned_dir = _artifact_dir(root, "cleaned", "bls_ppi_monthly", release_period)
    raw_path = raw_dir / f"bls_ppi_monthly-{raw_hash[:12]}.json"
    cleaned_path = cleaned_dir / f"bls_ppi_monthly-{content_hash[:12]}.csv"
    _write_bytes_if_missing(raw_path, json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"))
    _write_csv(cleaned_path, cleaned)
    manifest = build_release_manifest(
        dataset_id="bls_ppi_monthly",
        release_period=release_period,
        source_url=BLS_PPI_ENDPOINT,
        content_hash=content_hash,
        row_count=int(cleaned.shape[0]),
        columns=cleaned.columns,
        etag=latest_fingerprint,
        observation_start=str(cleaned["observation_date"].min()),
        observation_end=str(cleaned["observation_date"].max()),
        release_notes_url="https://www.bls.gov/ppi/",
        raw_artifact_path=_relative_to(root, raw_path),
        cleaned_artifact_path=_relative_to(root, cleaned_path),
        transformation_provenance=(
            "downloaded BLS public API v2 time-series response without an API key",
            "kept only explicitly mapped PCU industry series",
            "normalized monthly PPI values into public signal schema",
        ),
        notes=tuple(series["mapping_notes"] for series in BLS_PPI_SERIES),
    )
    manifest_path = store.write(manifest)
    return BackfillResult(
        dataset_id="bls_ppi_monthly",
        release_period=release_period,
        status=decision.action,
        reason=decision.reason,
        dry_run=False,
        row_count=int(cleaned.shape[0]),
        raw_paths=(_relative_to(root, raw_path),),
        cleaned_path=_relative_to(root, cleaned_path),
        manifest_path=_relative_to(root, manifest_path),
    )


def _listen_aies(root: Path, head: Head | None) -> ReleaseListenerResult:
    header_getter = head or _head_url
    try:
        basic = header_getter(AIES_BASIC_URL)
        expense = header_getter(AIES_EXPENSE_URL)
    except requests.RequestException as exc:
        return ReleaseListenerResult(
            dataset_id="census_aies_annual",
            release_period=str(AIES_SURVEY_YEAR),
            status="source_unavailable",
            source_url=AIES_BASIC_URL,
            message=str(exc),
        )
    release_period = str(AIES_SURVEY_YEAR)
    fingerprint = json.dumps(
        {
            "basic": _metadata_subset(basic),
            "expense": _metadata_subset(expense),
            "release_period": release_period,
        },
        sort_keys=True,
    ).encode("utf-8")
    metadata_hash = hash_payload(fingerprint)
    return _classify_listener_result(
        root,
        dataset_id="census_aies_annual",
        release_period=release_period,
        source_url=AIES_BASIC_URL,
        content_hash=None,
        etag="|".join(filter(None, [basic.get("etag"), expense.get("etag")])) or None,
        last_modified="|".join(
            filter(None, [basic.get("last-modified"), expense.get("last-modified")])
        )
        or None,
        metadata_hash=metadata_hash,
    )


def _listen_bls_ppi(root: Path, bls_post: BLSPost | None) -> ReleaseListenerResult:
    poster = bls_post or _post_bls_json
    current_year = pd.Timestamp.utcnow().year
    try:
        payload = poster(
            BLS_PPI_ENDPOINT,
            {
                "seriesid": [series["series_id"] for series in BLS_PPI_SERIES],
                "startyear": str(current_year - 1),
                "endyear": str(current_year),
            },
        )
    except requests.RequestException as exc:
        return ReleaseListenerResult(
            dataset_id="bls_ppi_monthly",
            release_period=None,
            status="source_unavailable",
            source_url=BLS_PPI_ENDPOINT,
            message=str(exc),
        )
    try:
        cleaned = _normalise_bls_ppi(payload)
    except (KeyError, ValueError, TypeError) as exc:
        return ReleaseListenerResult(
            dataset_id="bls_ppi_monthly",
            release_period=None,
            status="source_metadata_malformed",
            source_url=BLS_PPI_ENDPOINT,
            message=str(exc),
        )
    if cleaned.empty:
        return ReleaseListenerResult(
            dataset_id="bls_ppi_monthly",
            release_period=None,
            status="source_metadata_malformed",
            source_url=BLS_PPI_ENDPOINT,
            message="BLS response contained no observations.",
        )
    latest = cleaned.sort_values("observation_date").iloc[-1]
    release_period = str(latest["release_period"])
    latest_fingerprint = _bls_latest_fingerprint(cleaned)
    return _classify_listener_result(
        root,
        dataset_id="bls_ppi_monthly",
        release_period=release_period,
        source_url=BLS_PPI_ENDPOINT,
        content_hash=None,
        etag=latest_fingerprint,
        metadata_hash=latest_fingerprint,
    )


def _classify_listener_result(
    root: Path,
    *,
    dataset_id: str,
    release_period: str,
    source_url: str,
    content_hash: str | None,
    etag: str | None = None,
    last_modified: str | None = None,
    metadata_hash: str | None = None,
) -> ReleaseListenerResult:
    store = _manifest_store(root)
    decision = store.should_fetch(
        ReleaseIdentity(
            dataset_id=dataset_id,
            release_period=release_period,
            source_url=source_url,
            content_hash=content_hash,
            etag=etag,
            last_modified=last_modified,
        )
    )
    if not decision.should_fetch:
        status = "no_release_changed"
    elif decision.action == "record_revision":
        status = "existing_release_revised"
    else:
        status = "new_release_available"
    return ReleaseListenerResult(
        dataset_id=dataset_id,
        release_period=release_period,
        status=status,
        source_url=source_url,
        content_hash=metadata_hash or content_hash,
        etag=etag,
        last_modified=last_modified,
        message=decision.reason,
    )


def _normalise_bls_ppi(payload: Mapping[str, Any]) -> pd.DataFrame:
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise PublicDataPipelineError(f"BLS API request did not succeed: {payload.get('message')}")
    series_payload = payload.get("Results", {}).get("series", [])
    mapping = {series["series_id"]: series for series in BLS_PPI_SERIES}
    records: list[dict[str, Any]] = []
    for series in series_payload:
        series_id = str(series.get("seriesID", ""))
        if series_id not in mapping:
            continue
        series_meta = mapping[series_id]
        for item in series.get("data", []):
            period = str(item.get("period", ""))
            if not period.startswith("M") or period == "M13":
                continue
            month = int(period[1:])
            year = int(item["year"])
            records.append(
                {
                    "observation_date": f"{year:04d}-{month:02d}-01",
                    "frequency": "monthly",
                    "series_id": series_id,
                    "industry_code": series_meta["industry_code"],
                    "industry_name": series_meta["industry_name"],
                    "signal_name": series_meta["signal_name"],
                    "signal_value": float(item["value"]),
                    "units": series_meta["units"],
                    "seasonal_adjustment": series_meta["seasonal_adjustment"],
                    "release_period": f"{year:04d}-{month:02d}",
                    "source": "BLS PPI public API",
                }
            )
    frame = pd.DataFrame.from_records(records)
    if frame.empty:
        return pd.DataFrame(columns=[*SIGNAL_SCHEMA, "industry_name"])
    frame.sort_values(["observation_date", "series_id"], inplace=True)
    frame.reset_index(drop=True, inplace=True)
    _validate_columns(frame, SIGNAL_SCHEMA, "bls_ppi_monthly")
    return frame


def _read_aies_zip_table(payload: bytes, member: str) -> pd.DataFrame:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            with archive.open(member) as stream:
                frame = pd.read_csv(stream, sep="|", dtype="string")
    except (KeyError, OSError, ValueError, zipfile.BadZipFile) as exc:
        raise PublicDataPipelineError(f"Invalid AIES archive; expected {member}.") from exc
    frame.rename(columns=lambda name: str(name).removeprefix("#"), inplace=True)
    return frame


def _download_url(url: str) -> bytes:
    response = requests.get(
        url,
        timeout=60,
        headers={"User-Agent": "idiot-index/0.1 (+public-data-readiness)"},
    )
    response.raise_for_status()
    return response.content


def _head_url(url: str) -> Mapping[str, str]:
    response = requests.head(
        url,
        timeout=30,
        allow_redirects=True,
        headers={"User-Agent": "idiot-index/0.1 (+public-data-readiness-listener)"},
    )
    response.raise_for_status()
    return {key.lower(): value for key, value in response.headers.items()}


def _post_bls_json(url: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    response = requests.post(url, json=dict(payload), timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, Mapping):
        raise PublicDataPipelineError("BLS API response was not a JSON object.")
    return data


def _metadata_subset(headers: Mapping[str, str]) -> dict[str, str | None]:
    return {
        "etag": headers.get("etag"),
        "last_modified": headers.get("last-modified"),
        "content_length": headers.get("content-length"),
    }


def _aies_listener_headers(head: Head | None) -> tuple[str | None, str | None]:
    header_getter = head or _head_url
    try:
        basic = header_getter(AIES_BASIC_URL)
        expense = header_getter(AIES_EXPENSE_URL)
    except requests.RequestException:
        return None, None
    etag = "|".join(filter(None, [basic.get("etag"), expense.get("etag")])) or None
    last_modified = (
        "|".join(filter(None, [basic.get("last-modified"), expense.get("last-modified")])) or None
    )
    return etag, last_modified


def _bls_latest_fingerprint(cleaned: pd.DataFrame) -> str:
    latest = cleaned.sort_values("observation_date").iloc[-1]
    return hash_payload(
        json.dumps(
            {
                "release_period": str(latest["release_period"]),
                "series_id": str(latest["series_id"]),
                "value": float(latest["signal_value"]),
            },
            sort_keys=True,
        ).encode("utf-8")
    )


def _manifest_store(root: Path) -> ManifestStore:
    return ManifestStore(root / "manifests")


def _artifact_dir(root: Path, kind: str, dataset_id: str, release_period: str) -> Path:
    if kind not in {"raw", "cleaned"}:
        raise PublicDataPipelineError(f"Unsupported artifact kind: {kind}")
    target = root / kind / _safe_path_segment(dataset_id) / _safe_path_segment(release_period)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _safe_path_segment(value: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise PublicDataPipelineError("Public data path segment is unsafe.")
    return value


def _write_bytes_if_missing(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_bytes(payload)
    tmp_path.replace(path)


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    frame.to_csv(tmp_path, index=False)
    tmp_path.replace(path)


def _validate_columns(frame: pd.DataFrame, required: Iterable[str], dataset_id: str) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise PublicDataPipelineError(
            f"{dataset_id} cleaned output missing required columns: {', '.join(missing)}"
        )


def _relative_to(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _unsupported_range(dataset_id: str, release_period: str, dry_run: bool) -> BackfillResult:
    return BackfillResult(
        dataset_id=dataset_id,
        release_period=release_period,
        status="skipped",
        reason="requested_range_excludes_supported_release",
        dry_run=dry_run,
    )


__all__ = [
    "BLS_PPI_ENDPOINT",
    "BLS_PPI_SERIES",
    "BackfillResult",
    "PublicDataPipelineError",
    "ReleaseListenerResult",
    "backfill_public_dataset",
    "listen_for_public_release",
]
