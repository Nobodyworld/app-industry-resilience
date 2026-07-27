"""Generate the bounded, reviewed Industry Pulse BLS PPI offline snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

try:
    from src.scripts import _bootstrap  # noqa: F401
except (ModuleNotFoundError, ImportError):  # pragma: no cover - allow direct execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.scripts import _bootstrap  # noqa: F401

from src.core.industry_pulse import (  # noqa: E402
    INDUSTRY_PULSE_ENDPOINT,
    INDUSTRY_PULSE_INTERPRETATION,
    INDUSTRY_PULSE_REGISTRY,
    INDUSTRY_PULSE_REGISTRY_VERSION,
    INDUSTRY_PULSE_SCHEMA_VERSION,
)

GENERATOR_VERSION = "industry-pulse-generator-v1"
DEFAULT_START_YEAR = 2024
DEFAULT_END_YEAR = 2026
DEFAULT_CSV_PATH = Path("data/industry_pulse_bls_snapshot.csv")
DEFAULT_METADATA_PATH = Path("data/industry_pulse_bls_snapshot.metadata.json")
_PERIOD_PATTERN = re.compile(r"^M(0[1-9]|1[0-2])$")
_CSV_FIELDS = (
    "series_id",
    "industry_code",
    "industry_name",
    "observation_date",
    "value",
    "units",
    "seasonal_adjustment",
    "base_date",
    "release_period",
    "source",
)


class SnapshotGenerationError(RuntimeError):
    """Raised when the official response cannot produce the reviewed artifact."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("--output", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--metadata-output", type=Path, default=DEFAULT_METADATA_PATH)
    parser.add_argument(
        "--retrieved-at",
        help="Optional ISO-8601 timestamp for reproducible metadata regeneration.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.start_year > args.end_year:
        raise SnapshotGenerationError("start-year cannot exceed end-year")
    if args.end_year - args.start_year > 9:
        raise SnapshotGenerationError("Unregistered BLS requests must remain within ten years.")
    retrieved_at = _retrieval_timestamp(args.retrieved_at)
    payload = _request_bls(args.start_year, args.end_year)
    rows = normalize_response(payload)
    csv_bytes = serialize_csv(rows)
    csv_hash = hashlib.sha256(csv_bytes).hexdigest()
    metadata = build_metadata(
        rows,
        start_year=args.start_year,
        end_year=args.end_year,
        retrieved_at=retrieved_at,
        csv_hash=csv_hash,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(csv_bytes)
    args.metadata_output.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "csv": args.output.as_posix(),
                "metadata": args.metadata_output.as_posix(),
                "row_count": len(rows),
                "series_count": len({row["series_id"] for row in rows}),
                "csv_sha256": csv_hash,
            },
            sort_keys=True,
        )
    )
    return 0


def normalize_response(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise SnapshotGenerationError(f"BLS request failed: {payload.get('message')}")
    raw_series = payload.get("Results", {}).get("series")
    if not isinstance(raw_series, list):
        raise SnapshotGenerationError("BLS response did not include a series list.")
    expected = {entry.series_id: entry for entry in INDUSTRY_PULSE_REGISTRY.entries}
    returned: set[str] = set()
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for series in raw_series:
        if not isinstance(series, Mapping):
            raise SnapshotGenerationError("BLS response included a malformed series.")
        series_id = str(series.get("seriesID", ""))
        entry = expected.get(series_id)
        if entry is None:
            raise SnapshotGenerationError(f"BLS returned unknown series {series_id!r}.")
        if series_id in returned:
            raise SnapshotGenerationError(f"BLS returned duplicate series {series_id}.")
        returned.add(series_id)
        data = series.get("data")
        if not isinstance(data, list):
            raise SnapshotGenerationError(f"BLS series {series_id} omitted observation data.")
        for item in data:
            if not isinstance(item, Mapping):
                raise SnapshotGenerationError(f"BLS series {series_id} has a malformed row.")
            period = str(item.get("period", ""))
            if period == "M13":
                continue
            if _PERIOD_PATTERN.fullmatch(period) is None:
                raise SnapshotGenerationError(
                    f"BLS series {series_id} returned malformed period {period!r}."
                )
            try:
                year = int(item["year"])
                month = int(period[1:])
                value = float(item["value"])
            except (KeyError, TypeError, ValueError) as exc:
                raise SnapshotGenerationError(
                    f"BLS series {series_id} returned a nonnumeric observation."
                ) from exc
            if not math.isfinite(value):
                raise SnapshotGenerationError(
                    f"BLS series {series_id} returned a non-finite observation."
                )
            observation_date = f"{year:04d}-{month:02d}-01"
            identity = (series_id, observation_date)
            if identity in seen:
                raise SnapshotGenerationError(
                    f"BLS response duplicated {series_id} at {observation_date}."
                )
            seen.add(identity)
            rows.append(
                {
                    "series_id": series_id,
                    "industry_code": entry.industry_code,
                    "industry_name": entry.registry_label,
                    "observation_date": observation_date,
                    "value": _format_value(value),
                    "units": entry.units,
                    "seasonal_adjustment": entry.seasonal_adjustment,
                    "base_date": entry.base_date,
                    "release_period": f"{year:04d}-{month:02d}",
                    "source": "BLS PPI public API v2 (offline reviewed snapshot)",
                }
            )
    missing = sorted(set(expected).difference(returned))
    if missing:
        raise SnapshotGenerationError(f"BLS response omitted series: {', '.join(missing)}.")
    rows.sort(key=lambda row: (str(row["series_id"]), str(row["observation_date"])))
    counts: dict[str, int] = {}
    for row in rows:
        series_id = str(row["series_id"])
        counts[series_id] = counts.get(series_id, 0) + 1
    insufficient = sorted(series_id for series_id, count in counts.items() if count < 13)
    if insufficient:
        raise SnapshotGenerationError(
            "Snapshot requires at least 13 monthly observations per series: "
            + ", ".join(insufficient)
        )
    return rows


def serialize_csv(rows: Sequence[Mapping[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=_CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def build_metadata(
    rows: Sequence[Mapping[str, Any]],
    *,
    start_year: int,
    end_year: int,
    retrieved_at: datetime,
    csv_hash: str,
) -> dict[str, Any]:
    dates = [str(row["observation_date"]) for row in rows]
    release_periods = [str(row["release_period"]) for row in rows]
    manifest_identity = f"industry-pulse-bls-{start_year}-{end_year}-{csv_hash[:16]}"
    return {
        "endpoint": INDUSTRY_PULSE_ENDPOINT,
        "source_label": "BLS PPI public API v2 (offline reviewed snapshot)",
        "retrieved_at": retrieved_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "requested_years": {"start": start_year, "end": end_year},
        "series_ids": [entry.series_id for entry in INDUSTRY_PULSE_REGISTRY.entries],
        "row_count": len(rows),
        "series_count": len({str(row["series_id"]) for row in rows}),
        "observation_range": {"start": min(dates), "end": max(dates)},
        "latest_release_period": max(release_periods),
        "csv_sha256": csv_hash,
        "registry_version": INDUSTRY_PULSE_REGISTRY_VERSION,
        "schema_version": INDUSTRY_PULSE_SCHEMA_VERSION,
        "generator": GENERATOR_VERSION,
        "generator_command": (
            "python src/scripts/generate_industry_pulse_snapshot.py "
            f"--start-year {start_year} --end-year {end_year}"
        ),
        "manifest_identity": manifest_identity,
        "transformations": [
            "one batched no-key request for the reviewed eight-series registry",
            "excluded BLS annual-average M13 rows",
            "validated monthly periods and finite numeric values",
            "sorted by series ID and observation date",
        ],
        "interpretation_note": INDUSTRY_PULSE_INTERPRETATION,
    }


def _request_bls(start_year: int, end_year: int) -> Mapping[str, Any]:
    response = requests.post(
        INDUSTRY_PULSE_ENDPOINT,
        json={
            "seriesid": [entry.series_id for entry in INDUSTRY_PULSE_REGISTRY.entries],
            "startyear": str(start_year),
            "endyear": str(end_year),
        },
        timeout=60,
        headers={"User-Agent": "industry-resilience-dashboard/0.2.0 (+offline-snapshot)"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise SnapshotGenerationError("BLS response was not a JSON object.")
    return payload


def _retrieval_timestamp(raw: str | None) -> datetime:
    if raw is None:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SnapshotGenerationError("--retrieved-at must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise SnapshotGenerationError("--retrieved-at must include a timezone.")
    return parsed.astimezone(UTC)


def _format_value(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
