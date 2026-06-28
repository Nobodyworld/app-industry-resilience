#!/usr/bin/env python3
"""CLI for running Idiot Index scenario simulations."""

from __future__ import annotations

try:
    from src.scripts import _bootstrap  # noqa: F401
except (ModuleNotFoundError, ImportError):  # pragma: no cover - allow CLI execution
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.scripts import _bootstrap  # noqa: F401

import argparse
import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from src.application.scenario_planner import ScenarioAdjustment, plan_scenario


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to a CSV file providing baseline data. Defaults to the bundled sample dataset.",
    )
    parser.add_argument(
        "--adjust",
        action="append",
        metavar="EXPR",
        help=(
            "Scenario adjustment expressed as comma-separated key=value pairs. "
            "Use codes=111|112 to target industries, and gross/materials/value/intermediate "
            "to specify percentage deltas. Example: --adjust codes=311,gross=5,materials=-3"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write a JSON payload with summaries and per-industry deltas.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of industries to display when printing delta rankings (default: 5).",
    )
    return parser.parse_args(argv)


def load_dataframe(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.read_csv(Path("data") / "sample_industries.csv")
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return pd.read_csv(path)


def parse_adjustment_expression(expr: str) -> ScenarioAdjustment:
    tokens = {}
    for chunk in expr.split(","):
        if not chunk.strip():
            continue
        if "=" not in chunk:
            raise ValueError(f"Invalid adjustment token '{chunk}'. Expected key=value pairs.")
        key, value = chunk.split("=", 1)
        tokens[key.strip().lower()] = value.strip()

    codes_raw = tokens.get("codes")
    codes = [code.strip() for code in codes_raw.split("|") if code.strip()] if codes_raw else None

    def _float_token(name: str) -> float | None:
        raw = tokens.get(name)
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError as exc:  # pragma: no cover - argparse should guard, defensive only
            raise ValueError(f"Invalid numeric value for {name}: {raw}") from exc

    return ScenarioAdjustment(
        industry_codes=codes,
        gross_output_delta_pct=_float_token("gross") or 0.0,
        materials_cost_delta_pct=_float_token("materials") or 0.0,
        value_added_delta_pct=_float_token("value"),
        intermediate_inputs_delta_pct=_float_token("intermediate"),
    )


def build_adjustments(raw_adjustments: Iterable[str] | None) -> list[ScenarioAdjustment]:
    adjustments: list[ScenarioAdjustment] = []
    if not raw_adjustments:
        return adjustments
    for expr in raw_adjustments:
        adjustments.append(parse_adjustment_expression(expr))
    return adjustments


def format_metric(label: str, baseline: float | None, scenario: float | None) -> str:
    if baseline is None or scenario is None:
        return f"{label}: n/a"
    delta = scenario - baseline
    return f"{label}: {baseline:,.2f} -> {scenario:,.2f} (Δ {delta:+,.2f})"


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    frame = load_dataframe(args.input)
    adjustments = build_adjustments(args.adjust)

    result = plan_scenario(frame, adjustments)

    baseline_summary = result.baseline_summary
    scenario_summary = result.scenario_summary

    print("Scenario summary")
    print(
        format_metric(
            "Gross output total",
            baseline_summary.gross_output_total,
            scenario_summary.gross_output_total,
        )
    )
    print(
        format_metric(
            "Materials cost total",
            baseline_summary.materials_cost_total,
            scenario_summary.materials_cost_total,
        )
    )
    print(
        format_metric(
            "Value added total",
            baseline_summary.value_added_total,
            scenario_summary.value_added_total,
        )
    )
    print(
        format_metric(
            "Average idiot index",
            baseline_summary.idiot_index_avg,
            scenario_summary.idiot_index_avg,
        )
    )
    print(
        format_metric(
            "Average resilience score",
            baseline_summary.resilience_score_avg,
            scenario_summary.resilience_score_avg,
        )
    )

    ranked = result.deltas.sort_values("idiot_index", ascending=False)
    top = ranked.head(args.top)
    if not top.empty:
        print("\nTop idiotic index deltas")
        for row in top.itertuples():
            print(
                f"  {row.industry_code} – {row.industry_name}: Δ Idiot Index {row.idiot_index:+.2f}, "
                f"Δ Resilience {row.resilience_score:+.2f}"
            )

    if args.output:
        payload = {
            "adjustments": [asdict(adj) for adj in adjustments],
            "baseline_summary": asdict(baseline_summary),
            "scenario_summary": asdict(scenario_summary),
            "delta_summary": result.delta_summary,
            "deltas": result.deltas.to_dict(orient="records"),
        }
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote scenario details to {args.output}")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
