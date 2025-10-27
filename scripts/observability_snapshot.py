from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

try:
    from scripts import _bootstrap  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - direct execution fallback
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import _bootstrap  # type: ignore  # noqa: F401

from src.core import load_config
from src.extensions.manager import get_extension_manager
from src.infrastructure.observability import bootstrap_observability
from src.infrastructure.observability.replication import (
    NullSnapshotReplicator,
    SnapshotReplicationError,
    build_snapshot_replicator,
)
from src.infrastructure.observability.storage import (
    ObservabilitySnapshot,
    SnapshotStorage,
    load_snapshot_from_file,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print a JSON snapshot of Idiot Index observability state."
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Format the JSON payload with indentation for readability.",
    )
    parser.add_argument(
        "--store",
        action="store_true",
        help="Persist the captured snapshot into the configured storage directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the full snapshot payload to the specified file (directories are created automatically).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List previously stored snapshots and exit without capturing a new one.",
    )
    parser.add_argument(
        "--compare",
        type=str,
        help=(
            "Compare the latest stored snapshot with the snapshot at PATH or referenced by snapshot ID "
            "and print a JSON diff summary."
        ),
    )
    parser.add_argument(
        "--label",
        type=str,
        help="Optional label recorded in snapshot metadata when storing a new snapshot.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    indent = 2 if args.pretty else None
    config = load_config()
    storage = SnapshotStorage(config.observability_snapshot_dir)

    conflict_options = [
        args.list and (args.store or args.output or args.compare or args.label),
        args.compare and (args.store or args.output or args.label),
        args.list and args.compare,
    ]
    if any(conflict_options):
        print(
            "--list/--compare cannot be combined with snapshot capture options.",
            file=sys.stderr,
        )
        return 2

    if args.list:
        payload = [_serialise_snapshot_metadata(snap, storage) for snap in storage.list()]
        print(json.dumps(payload, indent=indent))
        return 0

    if args.compare:
        baseline = storage.latest()
        if baseline is None:
            print("No stored snapshots available for comparison.", file=sys.stderr)
            return 1
        try:
            target_path = _resolve_snapshot_reference(storage, args.compare)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        target = load_snapshot_from_file(target_path)
        diff = diff_snapshots(baseline, target)
        print(json.dumps(diff, indent=indent))
        return 0

    registry = bootstrap_observability()
    manager = get_extension_manager()
    manager.apply_instrumentation_extensions(registry)

    replicator = build_snapshot_replicator(config.observability_snapshot_remote)

    metadata: dict[str, Any] = {"source": "cli"}
    if args.label:
        metadata["label"] = args.label

    snapshot = registry.capture_snapshot(metadata=metadata)
    digest_payload = snapshot.payload

    try:
        if args.store:
            saved_path = storage.save(snapshot)
            print(f"Stored snapshot at {saved_path}", file=sys.stderr)
            try:
                replicator.replicate(snapshot, saved_path)
            except SnapshotReplicationError as exc:
                print(
                    f"Remote snapshot replication failed: {exc}",
                    file=sys.stderr,
                )
            else:
                _report_remote_destination(replicator, snapshot, saved_path)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
            print(f"Wrote snapshot to {args.output}", file=sys.stderr)
    finally:
        try:
            replicator.close()
        except Exception:  # pragma: no cover - defensive cleanup
            pass

    print(json.dumps(digest_payload, indent=indent))
    return 0


def _report_remote_destination(
    replicator: object, snapshot: ObservabilitySnapshot, saved_path: Path
) -> None:
    if isinstance(replicator, NullSnapshotReplicator):
        return
    if hasattr(replicator, "bucket"):
        bucket = replicator.bucket  # type: ignore[attr-defined]
        prefix = replicator.prefix if hasattr(replicator, "prefix") else ""  # type: ignore[attr-defined]
        key = f"{prefix}{snapshot.snapshot_id}.json"
        print(f"Replicated snapshot to s3://{bucket}/{key}", file=sys.stderr)
    elif hasattr(replicator, "target_dir"):
        target_dir = Path(str(getattr(replicator, "target_dir")))
        destination = target_dir / f"{snapshot.snapshot_id}.json"
        print(f"Replicated snapshot to {destination}", file=sys.stderr)


def _serialise_snapshot_metadata(
    snapshot: ObservabilitySnapshot, storage: SnapshotStorage
) -> dict[str, Any]:
    """Return basic serialisable metadata for a snapshot."""

    return {
        "snapshot_id": snapshot.snapshot_id,
        "captured_at": snapshot.captured_at.isoformat(),
        "metadata": dict(snapshot.metadata),
        "path": str(storage.base_dir / f"{snapshot.snapshot_id}.json"),
    }


def _resolve_snapshot_reference(storage: SnapshotStorage, reference: str) -> Path:
    """Return a filesystem path for ``reference`` treating bare IDs as stored files."""

    candidate = Path(reference)
    if candidate.exists():
        return candidate
    try:
        stored = storage.path_for(reference)
    except ValueError as exc:
        raise FileNotFoundError(str(exc)) from exc
    if stored.exists():
        return stored
    raise FileNotFoundError(f"Snapshot reference '{reference}' not found.")


def diff_snapshots(
    baseline: ObservabilitySnapshot, target: ObservabilitySnapshot
) -> dict[str, Any]:
    """Return a focused diff summarising target vs. baseline snapshot."""

    baseline_counts = _extract_event_counts(baseline)
    target_counts = _extract_event_counts(target)
    count_delta: dict[str, int] = {}
    for key in sorted(set(baseline_counts) | set(target_counts)):
        count_delta[key] = target_counts.get(key, 0) - baseline_counts.get(key, 0)

    baseline_metrics = _extract_metric_counts(baseline)
    target_metrics = _extract_metric_counts(target)
    metrics_delta = {
        key: target_metrics.get(key, 0) - baseline_metrics.get(key, 0)
        for key in sorted(set(baseline_metrics) | set(target_metrics))
    }

    metadata_changes = _diff_metadata(baseline.metadata, target.metadata)

    last_error_baseline = _get_last_error(baseline)
    last_error_target = _get_last_error(target)

    return {
        "baseline": {
            "snapshot_id": baseline.snapshot_id,
            "captured_at": baseline.captured_at.isoformat(),
        },
        "target": {
            "snapshot_id": target.snapshot_id,
            "captured_at": target.captured_at.isoformat(),
        },
        "event_total_delta": _extract_event_total(target) - _extract_event_total(baseline),
        "event_counts_delta": count_delta,
        "metrics_delta": metrics_delta,
        "metadata_changes": metadata_changes,
        "last_error_changed": last_error_baseline != last_error_target,
        "baseline_last_error": last_error_baseline,
        "target_last_error": last_error_target,
    }


def _extract_event_counts(snapshot: ObservabilitySnapshot) -> dict[str, int]:
    events = snapshot.payload.get("events", {})
    counts = events.get("counts", {})
    return {key: int(counts.get(key, 0) or 0) for key in counts}


def _extract_event_total(snapshot: ObservabilitySnapshot) -> int:
    events = snapshot.payload.get("events", {})
    total = events.get("total")
    return int(total or 0)


def _extract_metric_counts(snapshot: ObservabilitySnapshot) -> dict[str, int]:
    metrics = snapshot.payload.get("metrics", {})
    result: dict[str, int] = {}
    for key, value in metrics.items():
        if isinstance(value, int | float):
            result[key] = int(value)
    return result


def _diff_metadata(
    baseline: dict[str, Any], target: dict[str, Any]
) -> dict[str, Any]:
    base = dict(baseline)
    target_dict = dict(target)
    added = {k: target_dict[k] for k in target_dict.keys() - base.keys()}
    removed = sorted(base.keys() - target_dict.keys())
    changed = {
        key: {"from": base[key], "to": target_dict[key]}
        for key in base.keys() & target_dict.keys()
        if base[key] != target_dict[key]
    }
    return {"added": added, "removed": removed, "changed": changed}


def _get_last_error(snapshot: ObservabilitySnapshot) -> Any:
    return snapshot.payload.get("events", {}).get("last_error")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
