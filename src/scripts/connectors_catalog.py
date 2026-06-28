"""Inspect the registered connector catalog."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

try:
    from src.scripts import _bootstrap  # noqa: F401
except (ModuleNotFoundError, ImportError):  # pragma: no cover - script execution fallback
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.scripts import _bootstrap  # noqa: F401

from src.extensions.manager import get_extension_manager


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit catalog as JSON.")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output (implies --json).",
    )
    parser.add_argument(
        "--kind",
        default="all",
        help="Filter connectors by kind (e.g. data_source, automation).",
    )
    return parser.parse_args(argv)


def _filter_connectors(connectors: list[dict[str, object]], kind: str) -> list[dict[str, object]]:
    if kind == "all":
        return connectors
    return [connector for connector in connectors if connector.get("kind") == kind]


def _print_text(connectors: list[dict[str, object]]) -> None:
    if not connectors:
        print("No connectors registered for the selected filter.")
        return
    for connector in connectors:
        print(f"[{connector['kind']}] {connector['identifier']} – {connector['name']}")
        description = str(connector.get("description") or "").strip()
        if description:
            for paragraph in description.splitlines():
                print(f"    {paragraph}")
        health = connector.get("health")
        if isinstance(health, dict):
            status = health.get("status")
            summary = health.get("summary")
            if status or summary:
                print(f"    health: {status} – {summary}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    as_json = args.json or args.pretty
    indent = 2 if (as_json and args.pretty) else None

    manager = get_extension_manager()
    connectors = manager.connector_catalog()
    connectors = _filter_connectors(connectors, args.kind)

    if as_json:
        print(json.dumps(connectors, indent=indent, sort_keys=True))
    else:
        _print_text(connectors)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
