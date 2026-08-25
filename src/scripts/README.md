# Tooling Scripts

Scripts in this directory provide developer automation and operational helpers. Common entry points include:

- `run_quality_checks.py`, `check_trailing_whitespace.py`, and `codespell.py` – quality gates invoked from `make quality-gate`.
- `prefetch_data.py`, `observability_snapshot.py`, and `observability_tail.py` – operational utilities for cache warming and telemetry triage.
- `public_data_readiness.py` – inspect the no-auth public dataset catalog, record release manifests, check duplicate-fetch guardrails, and split periods into backtest eras.
- `extensions_catalog.py`, `connectors_catalog.py`, and `scaffold_extension.py` – manage the extension ecosystem and scaffolding.
- `run_api.py`, `run_scenario.py`, and `analytics_health.py` – CLI facades mirroring Streamlit features for automation contexts.
- `benchmark_metrics.py` – deterministic, no-cache metric-computation benchmark; use `--check` in regression gates or `--json` for automation.
- `generate_industry_pulse_snapshot.py` – makes one no-key batch request for exactly the eight
  reviewed BLS PPI series, validates/omits `M13`, sorts observations deterministically, and
  writes the bounded CSV plus SHA-256 metadata:

  ```bash
  python src/scripts/generate_industry_pulse_snapshot.py --start-year 2024 --end-year 2026
  ```

  The committed snapshot is the UI/API/test path. Running this operator command is the only
  live refresh path for the product slice.

- `generate_industry_momentum_ces_snapshot.py` requests only the eight reviewed CES employment
  series from the official keyless BLS API and writes/validates the deterministic CES snapshot.
- `generate_industry_momentum_g17_snapshot.py` downloads only official Federal Reserve G.17
  `ip_sa.txt`, `cap_sa.txt`, and `utl_sa.txt`, keeps the 22 registered series, and writes/validates
  the deterministic common-complete-month snapshot.

```bash
python src/scripts/generate_industry_momentum_ces_snapshot.py --validate-only
python src/scripts/generate_industry_momentum_g17_snapshot.py --validate-only
```

All scripts self-bootstrap the repository root onto `PYTHONPATH` so they can be executed directly via `python src/scripts/<name>.py`.
