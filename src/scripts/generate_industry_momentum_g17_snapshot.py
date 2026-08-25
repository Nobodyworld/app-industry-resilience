"""Generate the committed Federal Reserve G.17 Industry Momentum snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

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
    IndustryMomentumRegistryEntry,
)
from src.version import __version__  # noqa: E402

G17_FILES = {
    "industrial_production_index": "https://www.federalreserve.gov/releases/g17/Current/ipdisk/ip_sa.txt",
    "capacity_index": "https://www.federalreserve.gov/releases/g17/Current/ipdisk/cap_sa.txt",
    "capacity_utilization_rate": "https://www.federalreserve.gov/releases/g17/Current/ipdisk/utl_sa.txt",
}
DEFAULT_CSV = Path("data/industry_momentum_fed_g17_snapshot.csv")
DEFAULT_METADATA = Path("data/industry_momentum_fed_g17_snapshot.metadata.json")
GENERATOR_VERSION = "industry-momentum-g17-generator-v1"
START = date(2024, 1, 1)
_LINE_PATTERN = re.compile(r'^"(?P<code>[^"]+)"\s+(?P<year>[0-9]{4})\s+(?P<values>.+)$')
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


class G17SnapshotGenerationError(ValueError):
    """Raised when an official G.17 file is incomplete or malformed."""


def fetch_files() -> dict[str, str]:
    payloads: dict[str, str] = {}
    for signal_type, url in G17_FILES.items():
        response = requests.get(
            url,
            headers={"User-Agent": f"industry-resilience-dashboard/{__version__}"},
            timeout=60,
        )
        response.raise_for_status()
        payloads[signal_type] = response.text
    return payloads


def _official_code(entry: IndustryMomentumRegistryEntry) -> str:
    return entry.series_id.split(".")[1]


def normalise_files(payloads: dict[str, str]) -> list[dict[str, str]]:
    entries = INDUSTRY_MOMENTUM_REGISTRY.filtered(source_family="fed_g17")
    expected_types = set(G17_FILES)
    if set(payloads) != expected_types:
        raise G17SnapshotGenerationError(
            "G.17 payload set is incomplete or contains unknown files."
        )
    values_by_series: dict[str, dict[date, float]] = {}
    for signal_type, text in payloads.items():
        matching = {entry.series_id: entry for entry in entries if entry.signal_type == signal_type}
        codes = {_official_code(entry): entry.series_id for entry in matching.values()}
        parsed: dict[str, dict[date, float]] = {series_id: {} for series_id in matching}
        for line in text.splitlines():
            match = _LINE_PATTERN.match(line.strip())
            if match is None or match.group("code") not in codes:
                continue
            series_id = codes[match.group("code")]
            year = int(match.group("year"))
            tokens = match.group("values").split()
            if not tokens or len(tokens) > 12:
                raise G17SnapshotGenerationError(
                    "G.17 annual row must contain between 1 and 12 ordered monthly values."
                )
            for month, token in enumerate(tokens, start=1):
                period = date(year, month, 1)
                if period < START or token.upper() in {"NA", "N.A.", "ND"}:
                    continue
                try:
                    value = float(token)
                except ValueError as exc:
                    raise G17SnapshotGenerationError("G.17 value is malformed.") from exc
                if not math.isfinite(value):
                    raise G17SnapshotGenerationError("G.17 value must be finite.")
                if period in parsed[series_id]:
                    raise G17SnapshotGenerationError("Duplicate G.17 series-month observation.")
                parsed[series_id][period] = value
        missing = sorted(
            series_id for series_id, observations in parsed.items() if not observations
        )
        if missing:
            raise G17SnapshotGenerationError(f"G.17 files are missing required series: {missing}.")
        values_by_series.update(parsed)

    latest_complete = min(max(values) for values in values_by_series.values())
    rows: list[dict[str, str]] = []
    mapping_by_series = {entry.series_id: entry for entry in entries}
    for series_id, values in values_by_series.items():
        mapping = mapping_by_series[series_id]
        for observation_month, value in sorted(values.items()):
            if observation_month > latest_complete:
                continue
            rows.append(
                {
                    "source_family": "fed_g17",
                    "signal_type": mapping.signal_type,
                    "series_id": series_id,
                    "published_industry_code": mapping.published_industry_code,
                    "target_industry_code": mapping.target_industry_code,
                    "mapping_relationship": mapping.mapping_relationship,
                    "observation_date": observation_month.isoformat(),
                    "value": format(value, ".10g"),
                    "units": mapping.units,
                    "seasonal_adjustment": mapping.seasonal_adjustment,
                    "base_period": mapping.base_period or "",
                    "release_period": latest_complete.strftime("%Y-%m"),
                    "source": "Board of Governors of the Federal Reserve System G.17",
                }
            )
    rows.sort(key=lambda row: (row["source_family"], row["series_id"], row["observation_date"]))
    return rows


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
        "dataset_id": "fed_g17_monthly",
        "official_endpoints": sorted(G17_FILES.values()),
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
        "generator_command": "python src/scripts/generate_industry_momentum_g17_snapshot.py",
        "manifest_identity": f"industry-momentum-g17-{dates[0][:7]}-{dates[-1][:7]}-{digest[:16]}",
        "transformations": [
            "downloaded official seasonally adjusted G.17 production, capacity, and utilization files",
            "kept only registered source codes",
            "excluded missing and non-monthly values",
            "normalized observations to first-of-month dates",
            "bounded all series to their latest common complete month",
            "sorted by source family, series ID, and observation date",
        ],
        "interpretation_notes": [INDUSTRY_MOMENTUM_INTERPRETATION],
        "revision_notes": [
            "G.17 series are revised and codes may change during annual revisions; validate each refresh.",
            "The reviewed current files reflect the November 24, 2025 annual revision structure.",
        ],
    }


def write_snapshot(
    rows: list[dict[str, str]], *, csv_path: Path, metadata_path: Path, retrieved_at: datetime
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
        raise G17SnapshotGenerationError("Committed G.17 snapshot is not deterministically sorted.")
    if hashlib.sha256(payload).hexdigest() != metadata.get("csv_sha256"):
        raise G17SnapshotGenerationError("Committed G.17 snapshot hash does not match metadata.")
    expected = {
        entry.series_id for entry in INDUSTRY_MOMENTUM_REGISTRY.filtered(source_family="fed_g17")
    }
    if {row["series_id"] for row in rows} != expected:
        raise G17SnapshotGenerationError("Committed G.17 registry coverage is incomplete.")
    return cast(dict[str, Any], metadata)


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
        rows = normalise_files(fetch_files())
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
