# Performance and automatic metrics

Streamlit helpers may compute derived metrics when given a raw dataframe. The helpers are
`build_comparison_table`, `calculate_benchmark`, `prepare_trend_data`, and the baseline and
scenario sides of `build_scenario_comparison_table`.

Automatic computation happens only when none of the required derived columns are present. It
uses a dataframe copy and `MetricConfig(use_cache=False)`, so this UI convenience path neither
reads nor initializes the external computation cache. Callers handling large frames should
compute metrics once before using multiple UI helpers.

Each implicit calculation increments
`industry_resilience_streamlit_auto_compute_total{helper="..."}`. The only allowed `helper`
labels are `build_comparison_table`, `calculate_benchmark`, `prepare_trend_data`,
`build_scenario_comparison_table_baseline`, and `build_scenario_comparison_table_scenario`.
The process-wide registry exposes the counter through the existing `/metrics` endpoint.

## Benchmark

Run `python src/scripts/benchmark_metrics.py` for readable output, or add `--json` for JSON.
`--check` exits nonzero when a ceiling is exceeded; `make benchmark-metrics` runs that check.
The harness uses deterministic in-memory frames, runs one warm-up plus three measured no-cache
runs, and reports the median. It validates row count and all derived columns.

The conservative ceilings are centralized in `src/scripts/benchmark_metrics.py`: 100 rows in
0.50 seconds, 10,000 rows in 2.00 seconds, and 100,000 rows in 10.00 seconds. They are intended
to detect material regressions on GitHub-hosted Ubuntu runners, not normal timing variation.
