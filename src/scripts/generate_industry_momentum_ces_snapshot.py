"""Generate the committed BLS CES Industry Momentum snapshot from the official API."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import requests

try:
    from src.scripts import _bootstrap  # noqa: F401
except (ModuleNotFoundError, ImportError):  # pragma: no cover - direct execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.scripts import _bootstrap  # noqa: F401

from src.core.industry_momentum import (  # noqa: E402
    INDUSTRY_MOMENTUM_INTERPRETATION,
    INDUSTRY_MOMENTUM_REGISTRY,
    INDUSTRY_MOMENTUM_REGISTRY_VERSION,
    INDUSTRY_MOMENTUM_SCHEMA_VERSION,
)
from src.version import __version__  # noqa: E402

BLS_ENDPOINT = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
DEFAULT_CSV = Path("data/industry_momentum_bls_ces_snapshot.csv")
DEFAULT_METADATA = Path("data/industry_momentum_bls_ces_snapshot.metadata.json")
GENERATOR_VERSION = "industry-momentum-ces-generator-v1"
START = date(2024, 1, 1)
_FIELDS = (
    "source_family",
    "signal_type",
    "series_id",
    "published_industry_code",
    "target_industry_code",
    "mapping_relationship",
    "observation_date",
    "value",
    "units",
    "seasonal_adjustment",
    "base_period",
    "release_period",
    "source",
)


class CESSnapshotGenerationError(ValueError):
    """Raised when the official CES response is incomplete or malformed."""


def fetch_payload(*, start_year: int, end_year: int) -> dict[str, Any]:
    """Request only the reviewed CES series within unregistered API limits."""

    series = [
        entry.series_id for entry in INDUSTRY_MOMENTUM_REGISTRY.filtered(source_family="bls_ces")
    ]
    response = requests.post(
        BLS_ENDPOINT,
        json={"seriesid": series, "startyear": str(start_year), "endyear": str(end_year)},
        headers={"User-Agent": f"industry-resilience-dashboard/{__version__}"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise CESSnapshotGenerationError("BLS response must be a JSON object.")
    return payload


def normalise_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Validate and normalize an official BLS response deterministically."""

    expected = {
        entry.series_id: entry
        for entry in INDUSTRY_MOMENTUM_REGISTRY.filtered(source_family="bls_ces")
    }
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise CESSnapshotGenerationError("BLS request did not succeed.")
    series_payload = payload.get("Results", {}).get("series", [])
    if not isinstance(series_payload, list):
        raise CESSnapshotGenerationError("BLS series response is malformed.")
    observed_ids = [str(item.get("seriesID", "")) for item in series_payload]
    if len(observed_ids) != len(set(observed_ids)):
        raise CESSnapshotGenerationError("BLS response contains duplicate series.")
    unknown = sorted(set(observed_ids) - set(expected))
    missing = sorted(set(expected) - set(observed_ids))
    if unknown:
        raise CESSnapshotGenerationError(f"BLS response contains unknown series: {unknown}.")
    if missing:
        raise CESSnapshotGenerationError(f"BLS response is missing required series: {missing}.")

    parsed: dict[str, dict[date, float]] = {}
    for series in series_payload:
        series_id = str(series["seriesID"])
        values: dict[date, float] = {}
        data = series.get("data", [])
        if not isinstance(data, list):
            raise CESSnapshotGenerationError("BLS observation list is malformed.")
        for item in data:
            period = str(item.get("period", ""))
            if period == "M13":
                continue
            if not re_full_month(period):
                raise CESSnapshotGenerationError(f"Malformed BLS period: {period}.")
            month = date(int(item["year"]), int(period[1:]), 1)
            if month < START:
                continue
            try:
                value = float(item["value"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CESSnapshotGenerationError("BLS value is malformed.") from exc
            if not math.isfinite(value):
                raise CESSnapshotGenerationError("BLS value must be finite.")
            if month in values:
                raise CESSnapshotGenerationError("Duplicate BLS series-month observation.")
            values[month] = value
        if not values:
            raise CESSnapshotGenerationError(f"BLS series {series_id} has no bounded observations.")
        parsed[series_id] = values

    latest_complete = min(max(values) for values in parsed.values())
    rows: list[dict[str, str]] = []
    for series_id, mapping in expected.items():
        values = parsed[series_id]
        for month, value in sorted(values.items()):
            if month > latest_complete:
                continue
            rows.append(
                {
                    "source_family": "bls_ces",
                    "signal_type": mapping.signal_type,
                    "series_id": series_id,
                    "published_industry_code": mapping.published_industry_code,
                    "target_industry_code": mapping.target_industry_code,
                    "mapping_relationship": mapping.mapping_relationship,
                    "observation_date": month.isoformat(),
                    "value": format(value, ".10g"),
                    "units": mapping.units,
                    "seasonal_adjustment": mapping.seasonal_adjustment,
                    "base_period": mapping.base_period or "",
                    "release_period": latest_complete.strftime("%Y-%m"),
                    "source": "U.S. Bureau of Labor Statistics Current Employment Statistics",
                }
            )
    rows.sort(key=lambda row: (row["source_family"], row["series_id"], row["observation_date"]))
    return rows


def re_full_month(value: str) -> bool:
    return (
        len(value) == 3
        and value.startswith("M")
        and value[1:].isdigit()
        and 1 <= int(value[1:]) <= 12
    )


def csv_bytes(rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def build_metadata(
    rows: list[dict[str, str]], payload: bytes, retrieved_at: datetime
) -> dict[str, Any]:
    series = sorted({row["series_id"] for row in rows})
    dates = sorted({row["observation_date"] for row in rows})
    digest = hashlib.sha256(payload).hexdigest()
    return {
        "dataset_id": "bls_ces_monthly",
        "official_endpoints": [BLS_ENDPOINT],
        "retrieved_at": retrieved_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "requested_series": series,
        "observation_range": {"start": dates[0], "end": dates[-1]},
        "latest_release_period": rows[0]["release_period"],
        "row_count": len(rows),
        "series_count": len(series),
        "csv_sha256": digest,
        "registry_version": INDUSTRY_MOMENTUM_REGISTRY_VERSION,
        "schema_version": INDUSTRY_MOMENTUM_SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "generator_command": "python src/scripts/generate_industry_momentum_ces_snapshot.py",
        "manifest_identity": f"industry-momentum-ces-{dates[0][:7]}-{dates[-1][:7]}-{digest[:16]}",
        "transformations": [
            "requested reviewed CES series without a registration key",
            "excluded annual-average and non-monthly periods",
            "normalized observations to first-of-month dates",
            "bounded all series to their latest common complete month",
            "sorted by source family, series ID, and observation date",
        ],
        "interpretation_notes": [INDUSTRY_MOMENTUM_INTERPRETATION],
        "revision_notes": [
            "CES observations are revised; regenerate and review hash changes for each refresh."
        ],
    }


def write_snapshot(
    rows: list[dict[str, str]],
    *,
    csv_path: Path,
    metadata_path: Path,
    retrieved_at: datetime,
) -> dict[str, Any]:
    payload = csv_bytes(rows)
    metadata = build_metadata(rows, payload, retrieved_at)
    csv_path.write_bytes(payload)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return metadata


def validate_committed(csv_path: Path, metadata_path: Path) -> dict[str, Any]:
    payload = csv_path.read_bytes()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
    normalised = sorted(
        rows, key=lambda row: (row["source_family"], row["series_id"], row["observation_date"])
    )
    if rows != normalised:
        raise CESSnapshotGenerationError("Committed CES snapshot is not deterministically sorted.")
    if hashlib.sha256(payload).hexdigest() != metadata.get("csv_sha256"):
        raise CESSnapshotGenerationError("Committed CES snapshot hash does not match metadata.")
    expected = {
        entry.series_id for entry in INDUSTRY_MOMENTUM_REGISTRY.filtered(source_family="bls_ces")
    }
    if {row["series_id"] for row in rows} != expected:
        raise CESSnapshotGenerationError("Committed CES snapshot registry coverage is incomplete.")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        metadata = validate_committed(args.csv, args.metadata)
    else:
        now = datetime.now(UTC)
        payload = fetch_payload(start_year=START.year, end_year=now.year)
        rows = normalise_payload(payload)
        metadata = write_snapshot(
            rows, csv_path=args.csv, metadata_path=args.metadata, retrieved_at=now
        )
    print(
        json.dumps(
            {
                key: metadata[key]
                for key in ("row_count", "series_count", "csv_sha256", "manifest_identity")
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main())
