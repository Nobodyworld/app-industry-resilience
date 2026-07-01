#!/usr/bin/env python3
"""Inspect public data catalog, release guardrails, and era splits."""

from __future__ import annotations

try:
    from src.scripts import _bootstrap  # noqa: F401
except (ModuleNotFoundError, ImportError):  # pragma: no cover - allow direct execution
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.scripts import _bootstrap  # noqa: F401

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from src.application import plan_backtest
from src.application.public_data_pipeline import backfill_public_dataset, listen_for_public_release
from src.core import (
    ManifestStore,
    ReleaseIdentity,
    build_release_manifest,
    hash_payload,
    public_dataset_catalog,
    split_periods_into_eras,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog_parser = subparsers.add_parser("catalog", help="Print the public dataset catalog.")
    _add_output_options(catalog_parser)

    check_parser = subparsers.add_parser(
        "check-release",
        help="Check whether release metadata indicates a fetch is needed.",
    )
    check_parser.add_argument("--manifest-dir", type=Path, required=True)
    check_parser.add_argument("--dataset-id", required=True)
    check_parser.add_argument("--release-period", required=True)
    check_parser.add_argument("--source-url", required=True)
    check_parser.add_argument("--content-hash")
    check_parser.add_argument("--payload-file", type=Path)
    check_parser.add_argument("--etag")
    check_parser.add_argument("--last-modified")
    check_parser.add_argument("--force", action="store_true")
    _add_output_options(check_parser)

    listen_parser = subparsers.add_parser(
        "listen",
        help="Retrieve official release metadata for an implemented source without ingesting it.",
    )
    listen_parser.add_argument(
        "--dataset-id",
        choices=["census_aies_annual", "bls_ppi_monthly"],
        required=True,
    )
    listen_parser.add_argument("--storage-root", type=Path, default=Path("data/public"))
    _add_output_options(listen_parser)

    backfill_parser = subparsers.add_parser(
        "backfill",
        help="Backfill one implemented public source into raw, cleaned, and manifest storage.",
    )
    backfill_parser.add_argument(
        "--dataset-id",
        choices=["census_aies_annual", "bls_ppi_monthly"],
        required=True,
    )
    backfill_parser.add_argument("--storage-root", type=Path, default=Path("data/public"))
    backfill_parser.add_argument("--start-year", type=int)
    backfill_parser.add_argument("--end-year", type=int)
    backfill_parser.add_argument("--dry-run", action="store_true")
    backfill_parser.add_argument("--force", action="store_true")
    _add_output_options(backfill_parser)

    record_parser = subparsers.add_parser(
        "record-manifest",
        help="Write release manifest metadata after a successful fetch and clean step.",
    )
    record_parser.add_argument("--manifest-dir", type=Path, required=True)
    record_parser.add_argument("--dataset-id", required=True)
    record_parser.add_argument("--release-period", required=True)
    record_parser.add_argument("--source-url", required=True)
    record_parser.add_argument("--content-hash")
    record_parser.add_argument("--payload-file", type=Path)
    record_parser.add_argument("--row-count", type=int, required=True)
    record_parser.add_argument("--columns", nargs="+", required=True)
    record_parser.add_argument("--etag")
    record_parser.add_argument("--last-modified")
    record_parser.add_argument("--observation-start")
    record_parser.add_argument("--observation-end")
    _add_output_options(record_parser)

    split_parser = subparsers.add_parser(
        "split-eras",
        help="Split date-like periods into balanced backtest eras.",
    )
    split_parser.add_argument("--periods", nargs="+", required=True)
    split_parser.add_argument("--sections", type=int, default=3)
    _add_output_options(split_parser)

    backtest_parser = subparsers.add_parser(
        "backtest",
        help="Run a chronological previous-period baseline against a cleaned public signal CSV.",
    )
    backtest_parser.add_argument("--input", type=Path, required=True)
    backtest_parser.add_argument("--target-field", default="signal_value")
    backtest_parser.add_argument("--date-field", default="observation_date")
    backtest_parser.add_argument("--entity-field", default="series_id")
    backtest_parser.add_argument("--release-field", default="release_period")
    backtest_parser.add_argument("--sections", type=int, default=3)
    _add_output_options(backtest_parser)

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload: Any
    if args.command == "catalog":
        payload = [definition.to_dict() for definition in public_dataset_catalog()]
    elif args.command == "check-release":
        payload = _check_release(args)
    elif args.command == "listen":
        payload = listen_for_public_release(
            args.dataset_id,
            storage_root=args.storage_root,
        ).to_dict()
    elif args.command == "backfill":
        payload = backfill_public_dataset(
            args.dataset_id,
            storage_root=args.storage_root,
            start_year=args.start_year,
            end_year=args.end_year,
            dry_run=args.dry_run,
            force=args.force,
        ).to_dict()
    elif args.command == "record-manifest":
        payload = _record_manifest(args)
    elif args.command == "split-eras":
        payload = [era.__dict__ for era in split_periods_into_eras(args.periods, args.sections)]
    elif args.command == "backtest":
        payload = _run_backtest(args)
    else:  # pragma: no cover - argparse prevents this branch
        raise ValueError(f"Unsupported command: {args.command}")

    _emit_json(payload, output=args.output, pretty=args.pretty)
    return 0


def _check_release(args: argparse.Namespace) -> dict[str, Any]:
    store = ManifestStore(args.manifest_dir)
    content_hash = _resolve_content_hash(args.content_hash, args.payload_file)
    decision = store.should_fetch(
        ReleaseIdentity(
            dataset_id=args.dataset_id,
            release_period=args.release_period,
            source_url=args.source_url,
            content_hash=content_hash,
            etag=args.etag,
            last_modified=args.last_modified,
        ),
        force=args.force,
    )
    return {
        "dataset_id": args.dataset_id,
        "release_period": args.release_period,
        "should_fetch": decision.should_fetch,
        "reason": decision.reason,
        "action": decision.action,
        "requires_raw_download": decision.requires_raw_download,
        "existing_manifest": (
            decision.existing_manifest.to_dict() if decision.existing_manifest else None
        ),
    }


def _record_manifest(args: argparse.Namespace) -> dict[str, Any]:
    content_hash = _resolve_content_hash(args.content_hash, args.payload_file)
    if content_hash is None:
        raise ValueError("record-manifest requires --content-hash or --payload-file.")
    store = ManifestStore(args.manifest_dir)
    manifest = build_release_manifest(
        dataset_id=args.dataset_id,
        release_period=args.release_period,
        source_url=args.source_url,
        content_hash=content_hash,
        row_count=args.row_count,
        columns=args.columns,
        etag=args.etag,
        last_modified=args.last_modified,
        observation_start=args.observation_start,
        observation_end=args.observation_end,
    )
    path = store.write(manifest)
    return {"manifest_path": str(path), "manifest": manifest.to_dict()}


def _run_backtest(args: argparse.Namespace) -> dict[str, Any]:
    frame = pd.read_csv(args.input)
    result = plan_backtest(
        frame,
        target_field=args.target_field,
        date_field=args.date_field,
        entity_field=args.entity_field,
        release_field=args.release_field,
        sections=args.sections,
    )
    return result.to_dict()


def _resolve_content_hash(content_hash: str | None, payload_file: Path | None) -> str | None:
    if content_hash:
        return content_hash
    if payload_file is None:
        return None
    return hash_payload(payload_file.read_bytes())


def _add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")


def _emit_json(payload: Any, *, output: Path | None, pretty: bool) -> None:
    text = json.dumps(payload, indent=2 if pretty else None, sort_keys=True)
    if output is None:
        print(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
