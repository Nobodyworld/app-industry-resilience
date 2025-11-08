"""Run the Idiot Index health probe from the command line."""

from __future__ import annotations

try:
    from scripts import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - allow running via `python scripts/...`
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import _bootstrap  # noqa: F401

import argparse
import json
from typing import Sequence

from src.extensions.manager import get_extension_manager
from src.infrastructure.observability.health import build_default_probe


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Format JSON output with indentation for human readability.",
    )
    return parser.parse_args(argv)


# agent-entrypoint: safe for automation to call as part of health diagnostics.
def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    probe = build_default_probe(extension_manager_provider=get_extension_manager)
    report = probe.snapshot()

    data = report.as_dict()
    indent = 2 if args.pretty else None
    print(json.dumps(data, indent=indent, sort_keys=True))

    if report.status == "fail":
        return 2
    if report.status == "warn":
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

