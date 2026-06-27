#!/usr/bin/env python3
"""Refresh the keyless official Census AIES snapshot used by the dashboard."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.adapters.aies import fetch_latest_aies_snapshot  # noqa: E402

DEFAULT_OUTPUT = Path("data/official_industry_snapshot.csv")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    snapshot = fetch_latest_aies_snapshot()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    snapshot.to_csv(args.output, index=False)
    print(
        f"Wrote {len(snapshot)} official AIES industry rows "
        f"for {snapshot['year'].min()} to {args.output}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
