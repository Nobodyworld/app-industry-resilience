#!/usr/bin/env python3
"""Generate a lightweight CycloneDX SBOM from requirement files."""
from __future__ import annotations

try:
    from scripts import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - direct execution fallback
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import _bootstrap  # noqa: F401

import argparse
import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


def parse_requirements(paths: Iterable[Path]) -> list[dict[str, str]]:
    components: dict[tuple[str, str], dict[str, str]] = {}
    for path in paths:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "#" in line:
                line = line.split("#", 1)[0].strip()
            if not line or "==" not in line:
                continue
            name, version = [part.strip() for part in line.split("==", 1)]
            if not name or not version:
                continue
            key = (name.lower(), version)
            if key in components:
                continue
            purl = f"pkg:pypi/{quote(name.lower())}@{quote(version)}"
            components[key] = {
                "type": "library",
                "name": name,
                "version": version,
                "purl": purl,
            }
    return sorted(components.values(), key=lambda item: (item["name"].lower(), item["version"]))


def build_bom(components: list[dict[str, str]]) -> dict[str, object]:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "tools": [
                {
                    "vendor": "idiot-index",
                    "name": "generate_sbom.py",
                    "version": "1.0.0",
                }
            ],
        },
        "components": components,
    }


def write_bom(bom: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bom, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a CycloneDX SBOM from requirement files."
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path to write the SBOM JSON file to.",
    )
    parser.add_argument(
        "requirements",
        nargs="+",
        type=Path,
        help="Requirement files to include (e.g. requirements.txt requirements-dev.txt)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    components = parse_requirements(args.requirements)
    bom = build_bom(components)
    write_bom(bom, args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

