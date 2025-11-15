"""Inspect registered Idiot Index extensions."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict

try:
    from scripts import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import _bootstrap  # noqa: F401

from src.extensions.manager import ExtensionManager, get_extension_manager


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List registered Idiot Index extensions and their metadata."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the catalog as JSON (default is plain text).",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output with indentation (implies --json).",
    )
    parser.add_argument(
        "--kind",
        choices=["all", "summary", "scenario", "instrumentation", "replication", "connector"],
        default="all",
        help="Filter catalog entries by extension type.",
    )
    return parser.parse_args(argv)


def _filter_catalog(manager: ExtensionManager, kind: str) -> list[dict[str, object]]:
    catalog = manager.catalog()
    if kind != "all":
        catalog = [entry for entry in catalog if entry.kind == kind]
    return [asdict(entry) for entry in catalog]


def _print_text(catalog: list[dict[str, object]]) -> None:
    if not catalog:
        print("No extensions registered for the selected filter.")
        return

    for entry in catalog:
        line = f"[{entry['kind']}] {entry['name']} – {entry['module']}"
        print(line)
        description = str(entry.get("description") or "").strip()
        if description:
            for paragraph in description.splitlines():
                print(f"    {paragraph}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    as_json = args.json or args.pretty
    indent = 2 if (as_json and args.pretty) else None

    manager = get_extension_manager()
    catalog = _filter_catalog(manager, args.kind)

    if as_json:
        print(json.dumps(catalog, indent=indent, sort_keys=True))
    else:
        _print_text(catalog)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
