#!/usr/bin/env python
"""Benchmark dependency-free derived-metric computation on synthetic data."""

from __future__ import annotations

try:
    from src.scripts import _bootstrap  # noqa: F401
except (ModuleNotFoundError, ImportError):  # pragma: no cover - allow direct execution
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.scripts import _bootstrap  # noqa: F401

import argparse
import json
import statistics
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass

import pandas as pd

from src.core.metrics import MetricConfig, compute_metrics

# These ceilings intentionally allow substantial GitHub-hosted runner variance.
BENCHMARK_CEILINGS_SECONDS: dict[int, float] = {100: 0.50, 10_000: 2.00, 100_000: 10.00}
REQUIRED_DERIVED_COLUMNS = frozenset(
    {
        "idiot_index",
        "value_added_pct",
        "materials_share_pct",
        "resilience_score",
        "materials_dependency_ratio",
        "shock_sensitivity_index",
    }
)


@dataclass(frozen=True)
class BenchmarkResult:
    """The measured duration and check status for one deterministic frame size."""

    rows: int
    duration_seconds: float
    threshold_seconds: float
    passed: bool


def build_benchmark_frame(rows: int) -> pd.DataFrame:
    """Return a deterministic, in-memory input frame with the required base columns."""

    if rows < 1:
        raise ValueError("rows must be positive")
    values = range(rows)
    gross_output = [1000.0 + (value % 100) for value in values]
    return pd.DataFrame(
        {
            "industry_code": [f"{310 + (value % 90):03d}" for value in range(rows)],
            "industry_name": [f"Synthetic industry {value % 90}" for value in range(rows)],
            "year": [2020 + (value % 5) for value in range(rows)],
            "gross_output": gross_output,
            "materials_cost": [output * 0.6 for output in gross_output],
            "value_added": [output * 0.4 for output in gross_output],
        }
    )


def benchmark_metrics(
    rows: int,
    *,
    runs: int = 3,
    threshold_seconds: float | None = None,
) -> BenchmarkResult:
    """Warm up and measure median no-cache metric computation for ``rows`` inputs."""

    if runs < 3:
        raise ValueError("runs must be at least three")
    threshold = (
        threshold_seconds if threshold_seconds is not None else BENCHMARK_CEILINGS_SECONDS[rows]
    )
    frame = build_benchmark_frame(rows)
    _validate_result(compute_metrics(frame, config=MetricConfig(use_cache=False)), rows)
    durations: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        result = compute_metrics(frame, config=MetricConfig(use_cache=False))
        durations.append(time.perf_counter() - started)
        _validate_result(result, rows)
    duration = statistics.median(durations)
    return BenchmarkResult(
        rows=rows,
        duration_seconds=duration,
        threshold_seconds=threshold,
        passed=duration <= threshold,
    )


def _validate_result(result: pd.DataFrame, rows: int) -> None:
    missing = REQUIRED_DERIVED_COLUMNS.difference(result.columns)
    if missing:
        raise ValueError(f"Metric computation omitted derived columns: {sorted(missing)}")
    if len(result) != rows:
        raise ValueError(
            f"Metric computation changed row count: expected {rows}, got {len(result)}"
        )


def run_benchmarks(*, threshold_seconds: float | None = None) -> list[BenchmarkResult]:
    """Run every standard benchmark size without using filesystem or network resources."""

    return [
        benchmark_metrics(rows, threshold_seconds=threshold_seconds)
        for rows in BENCHMARK_CEILINGS_SECONDS
    ]


def _render_human(results: Sequence[BenchmarkResult]) -> str:
    lines = ["Metric computation benchmark (median of three measured runs after warm-up)"]
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(
            f"{result.rows:>7,} rows: {result.duration_seconds:.4f}s "
            f"(ceiling {result.threshold_seconds:.2f}s) {status}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON results.")
    parser.add_argument(
        "--check", action="store_true", help="Exit nonzero when a ceiling is exceeded."
    )
    parser.add_argument(
        "--threshold-seconds",
        type=float,
        help="Override every ceiling; intended for deterministic check-mode testing.",
    )
    args = parser.parse_args()
    results = run_benchmarks(threshold_seconds=args.threshold_seconds)
    if args.json:
        print(json.dumps([asdict(result) for result in results]))
    else:
        print(_render_human(results))
    if args.check and not all(result.passed for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
