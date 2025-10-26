"""Stream observability events from the Idiot Index registry."""

from __future__ import annotations

import argparse
import json
import queue
import sys
from typing import Iterable, Sequence

try:
    from scripts import _bootstrap  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import _bootstrap  # type: ignore  # noqa: F401

from src.extensions.manager import get_extension_manager
from src.infrastructure.observability import ObservationEvent, bootstrap_observability


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tail observability events emitted by the Idiot Index registry."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit events as JSON instead of plain text.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output (implies --json).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print only the most recent event and exit immediately.",
    )
    parser.add_argument(
        "--follow",
        action="store_true",
        help="Follow the event stream until interrupted (Ctrl+C to stop).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Emit at most N events before exiting (applies to history and follow mode).",
    )
    return parser.parse_args(argv)


def _format_event(payload: dict[str, object], *, as_json: bool, indent: int | None) -> str:
    if as_json:
        return json.dumps(payload, indent=indent, sort_keys=True)

    parts = [
        str(payload.get("timestamp", "")),
        payload.get("status", "?") or "?",
        payload.get("name", "?"),
    ]
    attributes = payload.get("attributes")
    if isinstance(attributes, dict) and attributes:
        attrs = ", ".join(f"{key}={value!r}" for key, value in sorted(attributes.items()))
        parts.append(f"[{attrs}]")
    error = payload.get("error")
    if error:
        parts.append(f"error={error}")
    return " ".join(str(part) for part in parts if part)


def _emit_events(
    events: Iterable[dict[str, object]],
    *,
    as_json: bool,
    indent: int | None,
    limit: int | None,
) -> int:
    emitted = 0
    for event in events:
        if limit is not None and emitted >= limit:
            break
        print(_format_event(event, as_json=as_json, indent=indent))
        emitted += 1
    return emitted


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    as_json = args.json or args.pretty
    indent = 2 if (as_json and args.pretty) else None

    registry = bootstrap_observability()
    manager = get_extension_manager()
    manager.apply_instrumentation_extensions(registry)

    recent = [event.as_dict() for event in registry.iter_recent_events()]

    if args.once:
        if recent:
            _emit_events([recent[-1]], as_json=as_json, indent=indent, limit=1)
        return 0

    emitted = _emit_events(recent, as_json=as_json, indent=indent, limit=args.limit)
    if not args.follow or (args.limit is not None and emitted >= args.limit):
        return 0

    remaining = None
    if args.limit is not None:
        remaining = max(args.limit - emitted, 0)

    event_queue: "queue.SimpleQueue[dict[str, object]]" = queue.SimpleQueue()

    def _on_event(event: ObservationEvent) -> None:
        payload = event.as_dict()
        event_queue.put(payload)

    registry.subscribe("*", _on_event)

    try:
        while True:
            if remaining is not None and remaining <= 0:
                break
            payload = event_queue.get()
            print(_format_event(payload, as_json=as_json, indent=indent))
            if remaining is not None:
                remaining -= 1
    except KeyboardInterrupt:  # pragma: no cover - manual interruption path
        return 0

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
