# Tooling Scripts

Scripts in this directory provide developer automation and operational helpers. Common entry points include:

- `run_quality_checks.py`, `check_trailing_whitespace.py`, and `codespell.py` – quality gates invoked from `make quality-gate`.
- `prefetch_data.py`, `observability_snapshot.py`, and `observability_tail.py` – operational utilities for cache warming and telemetry triage.
- `public_data_readiness.py` – inspect the no-auth public dataset catalog, record release manifests, check duplicate-fetch guardrails, and split periods into backtest eras.
- `extensions_catalog.py`, `connectors_catalog.py`, and `scaffold_extension.py` – manage the extension ecosystem and scaffolding.
- `run_api.py`, `run_scenario.py`, and `analytics_health.py` – CLI facades mirroring Streamlit features for automation contexts.
- `benchmark_metrics.py` – deterministic, no-cache metric-computation benchmark; use `--check` in regression gates or `--json` for automation.

All scripts self-bootstrap the repository root onto `PYTHONPATH` so they can be executed directly via `python src/scripts/<name>.py`.
