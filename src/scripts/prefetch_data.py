#!/usr/bin/env python3
"""Warm Idiot Index caches for selected sources/years."""

from __future__ import annotations

try:
    from scripts import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - allow direct execution
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import _bootstrap  # noqa: F401

import argparse
import logging
from collections.abc import Iterable, Sequence

from src.application import DataSource, NormalizationOptions, evaluate_idiot_index
from src.core import AppConfig, load_config
from src.logging_config import setup_logging

LOGGER = logging.getLogger("prefetch")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["sample", "bea", "census"],
        default=["sample"],
        help="Data sources to prefetch (default: sample).",
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        help="Years to warm. Defaults to config default year if omitted.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging for prefetch operations.",
    )
    return parser.parse_args(argv)


def resolve_sources(raw: Iterable[str]) -> list[DataSource]:
    mapping = {
        "sample": DataSource.SAMPLE,
        "bea": DataSource.BEA,
        "census": DataSource.CENSUS,
    }
    return [mapping[item] for item in raw]


def warm_cache(config: AppConfig, *, sources: Sequence[DataSource], years: Sequence[int]) -> None:
    for source in sources:
        for year in years:
            try:
                LOGGER.info("Prefetching source=%s year=%s", source.value, year)
                evaluate_idiot_index(
                    year=year,
                    source=source,
                    config=config,
                    top_n=1,
                    normalization_options=NormalizationOptions(
                        dtype_overrides=dict(config.normalization_dtype_overrides)
                    ),
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                LOGGER.warning("Prefetch failed for source=%s year=%s: %s", source.value, year, exc)
            else:
                LOGGER.info("Prefetch complete for source=%s year=%s", source.value, year)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config()
    setup_logging(level="DEBUG" if args.verbose else "INFO")

    years = args.years or [config.default_year]
    sources = resolve_sources(args.sources)

    LOGGER.info(
        "Starting cache prefetch for sources=%s years=%s", [s.value for s in sources], years
    )
    warm_cache(config, sources=sources, years=years)
    LOGGER.info("Prefetch run complete")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
