"""Collect a single-file diagnostics bundle for incident response."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:  # pragma: no cover - import side effect for script execution
    from src.scripts import _bootstrap  # noqa: F401
except (ModuleNotFoundError, ImportError):  # pragma: no cover - execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.scripts import _bootstrap  # noqa: F401

from src.core.config import get_config_summary, load_config
from src.extensions.manager import get_extension_manager
from src.infrastructure.observability import (
    ObservabilitySnapshot,
    SnapshotStorage,
    bootstrap_observability,
    build_default_probe,
    render_prometheus_text,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture health, observability, and configuration data into a single "
            "JSON diagnostics payload."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional file path for writing the diagnostics bundle.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output (also enables key sorting).",
    )
    parser.add_argument(
        "--limit-events",
        type=int,
        default=25,
        help="Number of recent observability events to include (default: 25).",
    )
    parser.add_argument(
        "--status",
        type=str,
        default=None,
        help="Optional status filter for observability events (success/error/warn).",
    )
    parser.add_argument(
        "--include-metrics",
        action="store_true",
        help="Include Prometheus-formatted metrics text in the payload.",
    )
    return parser.parse_args(argv)


def _serialise_snapshot(
    snapshot: ObservabilitySnapshot | None, storage: SnapshotStorage
) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "snapshot_id": snapshot.snapshot_id,
        "captured_at": snapshot.captured_at.isoformat(),
        "metadata": dict(snapshot.metadata),
        "path": str(storage.path_for(snapshot.snapshot_id)),
    }


def collect_bundle(
    *,
    event_limit: int,
    status: str | None,
    include_metrics: bool,
) -> dict[str, Any]:
    config = load_config()
    manager = get_extension_manager()
    registry = bootstrap_observability()
    manager.apply_instrumentation_extensions(registry)

    probe = build_default_probe(extension_manager_provider=lambda: manager)
    registry.bind_probe(probe)
    report = probe.snapshot()

    storage = SnapshotStorage(config.observability_snapshot_dir)
    snapshots = storage.list()
    latest_snapshot = snapshots[-1] if snapshots else None

    status_normalised = status.lower() if status else None
    events = registry.events(status=status_normalised)
    limited_events = events[:event_limit] if event_limit >= 0 else events

    payload: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "config": dict(get_config_summary(config)),
        "health": report.as_dict(),
        "observability": {
            "digest": registry.digest(),
            "events": {
                "applied_limit": event_limit,
                "applied_status": status_normalised,
                "total_available": len(events),
                "items": limited_events,
            },
        },
        "snapshots": {
            "directory": str(storage.base_dir),
            "count": len(snapshots),
            "latest": _serialise_snapshot(latest_snapshot, storage),
        },
    }
    if include_metrics:
        payload["metrics_text"] = render_prometheus_text(registry.metrics)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = collect_bundle(
        event_limit=args.limit_events,
        status=args.status,
        include_metrics=args.include_metrics,
    )

    indent = 2 if args.pretty else None
    sort_keys = bool(args.pretty)
    output = json.dumps(payload, indent=indent, sort_keys=sort_keys)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
