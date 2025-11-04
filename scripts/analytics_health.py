#!/usr/bin/env python
"""Compute Idiot Index health analytics from the command line."""

from __future__ import annotations

try:
    from scripts import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - allow direct execution
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import _bootstrap  # noqa: F401

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from src.core import (
    MetricConfig,
    compute_health_scores,
    compute_metrics,
    format_for_display,
    normalize_columns,
    summarise_health,
)

DEFAULT_DATASET = Path("data/sample_industries.csv")


def _summary_to_dict(summary) -> dict[str, object]:
    return {
        "overall": asdict(summary.overall),
        "sectors": [asdict(item) for item in summary.sectors],
        "band_breakdown": [asdict(item) for item in summary.band_breakdown],
        "top_risks": [asdict(item) for item in summary.top_risks],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to a CSV dataset. Defaults to the bundled sample dataset.",
    )
    parser.add_argument(
        "--group-by",
        choices=["overall", "sector", "all"],
        default="all",
        help="Cohort grouping to include in the summary output.",
    )
    parser.add_argument(
        "--top-risks",
        type=int,
        default=5,
        help="Number of highest-risk industries to include (default: 5).",
    )
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON with indentation."
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Dataset not found: {args.input}")

    frame = pd.read_csv(args.input)
    normalized = normalize_columns(frame)
    metrics = compute_metrics(normalized, config=MetricConfig(use_cache=False))
    display = compute_health_scores(format_for_display(metrics))
    summary = summarise_health(
        display, group_by=args.group_by, top_risk_limit=max(args.top_risks, 0)
    )

    payload = _summary_to_dict(summary)
    if args.pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()

