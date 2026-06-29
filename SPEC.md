Project specification for the Idiot Index application

# Overview

The Idiot Index is a small analytics application that computes the ratio of gross output to materials cost (the "Idiot Index"). It supports multiple data sources (BEA, Census ASM, and CSV uploads), normalization, metric computation, and a Streamlit UI with an optional FastAPI headless server.

## Key APIs and Data Flows

- Sources: `src/sources/*` and `src/adapters/*` implement fetching functions that return normalized rows mapping to the expected schema.

- Sources: `src/sources/*` and `src/adapters/*` implement fetching functions that return normalized rows mapping to the expected schema.
- Normalization: `src/core/normalize.py` standardizes column names and types.
- Metrics: `src/core/metrics.py` computes derived metrics like `idiot_index`, `value_added_pct`, `resilience_score`, etc.
- Presentation: `app.py` and `src/interfaces/streamlit/` provide UI widgets and charts. `fastapi/` includes an optional headless API server implementation.

## Schema

- `industry_code` (string)
- `industry_name` (string)
- `year` (int)
- `gross_output` (float)

All normalized dataframes must contain at a minimum the columns:

- `industry_code` (string)
- `industry_name` (string)
- `year` (int)
- `gross_output` (float)
And at least one of:
- `materials_cost` (float) OR
- `intermediate_inputs` (float)

Computed columns (derived by `compute_metrics`):

- `idiot_index`, `value_added`, `value_added_pct`, `materials_share_pct`, `resilience_score`, `materials_dependency_ratio`, `shock_sensitivity_index`.

## Operational Contracts

- API request/response contracts for BEA/Census are described in `docs/CONNECTORS.md` and Validate responses using `safe_get_json`.
- Caching: API responses and computation results are cached when enabled in `AppConfig` via `get_api_cache` and `get_computation_cache`.

## Versioning and Extensions

- Extensions follow the manifest-driven plugin model and must be sandboxed under `src/extensions/`.
- Major API changes should be released under a new version (v2) while maintaining v1 support.

## Appendix: Acceptance Criteria

- Unit tests for all adapters and core components (runtime-path coverage gate enforced at >= 85% by default; full-source coverage tracked informationally)
- Integration tests for a full pipeline roundtrip
- Prometheus metrics exposed for production observability
