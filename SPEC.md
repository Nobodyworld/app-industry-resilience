# Repository Specification

> **Canonical specification:** [`docs/SPEC.md`](docs/SPEC.md)

This root file is retained as a stable entry point for repository policy and automation that expect `SPEC.md` at the repository root. Do not duplicate the full specification here; update `docs/SPEC.md` instead.

## Current Classification

- **Status:** PUBLIC BETA
- **Primary stack:** Python 3.13, Streamlit, pandas, and a FastAPI-compatible headless API
- **Purpose:** Economic and financial analysis demonstration for comparative industry cost structure and heuristic resilience diagnostics
- **Limitations:** Not a credit model, insolvency predictor, causal forecast, or source of financial, investment, credit, or policy advice

## Canonical Entry Points

- Streamlit: `streamlit run app.py`
- Headless API: `python src/scripts/run_api.py`
- Scenario CLI: `python src/scripts/run_scenario.py`
- Full validation: `make quality-gate`
- Docker validation: `.github/workflows/docker-smoke.yml`

See [`README.md`](README.md), [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md), and [`docs/SPEC.md`](docs/SPEC.md) for the maintained product, contribution, and architecture requirements.
