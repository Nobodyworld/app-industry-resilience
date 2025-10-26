from __future__ import annotations

import argparse
import json
from typing import Sequence

try:
    from scripts import _bootstrap  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - direct execution fallback
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import _bootstrap  # type: ignore  # noqa: F401

from src.extensions.manager import get_extension_manager
from src.infrastructure.observability import bootstrap_observability


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print a JSON snapshot of Idiot Index observability state."
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Format the JSON payload with indentation for readability.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    registry = bootstrap_observability()
    manager = get_extension_manager()
    manager.apply_instrumentation_extensions(registry)
    snapshot = registry.health_overview()
    indent = 2 if args.pretty else None
    print(json.dumps(snapshot, indent=indent))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
