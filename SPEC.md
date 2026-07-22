# Repository Specification

This root file is the concise, authoritative repository specification. The detailed architecture and maintenance reference lives in [`docs/SPEC.md`](docs/SPEC.md); keep both documents aligned when contracts or workflows change.

## Classification

- **Status:** PUBLIC BETA
- **Primary stack:** Python 3.13, Streamlit, pandas, and a FastAPI-compatible headless API
- **Purpose:** Economic and financial analysis demonstration for comparative industry cost structure and heuristic resilience diagnostics
- **Limitations:** Not a credit model, insolvency predictor, causal forecast, or source of financial, investment, credit, or policy advice

## Core Data Contract

Normalized datasets must include:

- `industry_code`
- `industry_name`
- `year`
- `gross_output`
- at least one of `materials_cost` or `intermediate_inputs`

Derived metrics may include the informal `idiot_index`, `value_added`, `value_added_pct`, `materials_share_pct`, and experimental resilience diagnostics. Composite bands are heuristic summaries and do not independently establish industry health or distress.

Analytical dataframes carry a typed, redacted lineage envelope identifying source, dataset, provider, observation period, acquisition or snapshot time, retrieval/cache state, official/sample truth, calculation version, and ordered transformations. Uploaded files use the generic identity `user-upload`; uploaded filenames and arbitrary dataframe attributes are never lineage fields.

## Supported Entry Points

- Streamlit dashboard: `streamlit run app.py`
- Canonical headless API: `/v1/*` via `python src/scripts/run_api.py`
- Deprecated unversioned API aliases: compatibility-only during the documented migration window
- Scenario CLI: `python src/scripts/run_scenario.py`
- Public-data readiness: `python src/scripts/public_data_readiness.py catalog --pretty`
- Full validation: `make quality-gate`
- Docker validation: `.github/workflows/docker-smoke.yml`

## Architecture Boundaries

- Data access: `src/adapters/`
- Domain, analytics, cache, and lineage: `src/core/`
- Use-case orchestration and export serialization: `src/application/`
- Streamlit and API surfaces: `src/interfaces/`
- Automation clients: `src/agents/`
- Operational tooling: `src/scripts/`
- Extension contracts and implementations: `src/extensions/` and `extensions/manifest.json`

## Change Requirements

- Preserve calculation behavior unless a change is explicitly scoped and tested.
- Preserve canonical `/v1` and deprecated alias compatibility where applicable.
- Never copy credentials, filenames, private paths, cache identifiers, raw provider payloads, or arbitrary dataframe attributes into typed lineage.
- Run `make quality-gate` before merge.
- Require hosted `CI / Quality Gate` for pull requests.
- Keep external GitHub Actions pinned to full-length immutable commit SHAs.
- Update `README.md`, `docs/CONTRIBUTING.md`, and `docs/SPEC.md` when public behavior or architecture changes.
