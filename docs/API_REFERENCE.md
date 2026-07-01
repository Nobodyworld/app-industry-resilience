# API Reference

This reference captures the primary Python entrypoints intended for reuse across user interfaces, agents, and downstream automation. All modules live under `src/` unless otherwise noted.

## Application services

### `src.application.idiot_index_service.IdiotIndexService`

| Member | Description |
| --- | --- |
| `IdiotIndexService.evaluate(year, source, dataframe=None, top_n=50, metric_config=None, normalization_options=None, ...)` | Orchestrates dataset loading, normalisation, metric calculation, and leaderboard summarisation. Accepts a `DataSource` enum (`SAMPLE`, `CENSUS`, `BEA`), an optional pre-loaded dataframe (used for uploads/tests), an optional `MetricConfig` to control caching, and an optional `NormalizationOptions` instance to override column aliases or pandas dtypes. Returns an `IdiotIndexSummary` dataclass with `dataframe_full`, `leaderboard`, averages, and metadata. |

### `src.application.evaluate_idiot_index`

Convenience wrapper delegating to the shared `IdiotIndexService` singleton. Accepts the same parameters as `.evaluate` for easy reuse in CLI tools and automation.

## Adapters

### `src.adapters.bea`

| Member | Description |
| --- | --- |
| `fetch_go_ii_by_industry(api_key, year, normalization=None)` | Fetches Gross Output and Intermediate Inputs tables for one or more years, validates inputs, merges NAICS metadata, and returns a pandas `DataFrame` with BEA metadata attached in `df.attrs`. The optional `normalization` parameter accepts a `NormalizationOptions` to override column aliases or dtypes. Raises `BEAClientError` when validation fails or endpoints are unavailable. |
| `select_bea_endpoint(config)` | Iterates through configured BEA base URLs, returning the first healthy endpoint that responds to a `GetParameterValues` health check. |
| `BEA_TABLES` | Tuple of table descriptors fetched per year. Useful if you need to inspect or extend coverage. |

### `src.adapters.census`

Provides similar helpers for the Census ASM dataset. Use `fetch_census_asm` to fetch shipments, cost of materials, and value-added data, handling pagination and validation internally.

### `src.adapters.csv_loader`

Contains `load_sample_csv` for offline demo data and `load_csv` for arbitrary CSV inputs with schema validation.

## Core utilities

### `src.core.config`

- `load_config()` reads environment variables, `.env`, and defaults into an `AppConfig` dataclass. Distributed rate limiting is controlled via `RATE_LIMIT_BACKEND`/`RATE_LIMIT_REDIS_*` flags; dtype overrides can be configured with `NORMALIZE_DTYPE_OVERRIDES`.
- `AppConfig.supported_years_bea` / `supported_years_census` expose `range` objects for validation.

### `src.core.metrics`

- `compute_metrics(dataframe)` calculates Idiot Index, value-added share, materials share, and guards division-by-zero.
- `rank_industries(dataframe, metric="idiot_index", top_n=10)` surfaces leaderboard slices.

### `src.core.analytics`

- `compute_health_scores(dataframe, config=HealthScoreConfig())` appends `health_score` and `health_band` columns using weighted composites of resilience metrics.
- `summarise_health(dataframe, group_by="all", top_risk_limit=5)` aggregates cohort health summaries, band distribution, and the highest-risk industries.

### `src.core.utils`

- `safe_get_json(url, retry_policy=None)` fetches JSON payloads with retry/backoff. When a retry observer is registered the function emits structured events containing attempt, delay, and status information.
- `register_retry_observer(callback)` subscribes to retry events for instrumentation extensions or diagnostics.

### `src.core.security.SecurityUtils`

Collection of static methods for validating API keys, CSV uploads, and general string sanitisation. All UI entrypoints call these utilities before processing user-supplied data. Rate limiting delegates to a pluggable backend registered by infrastructure (`src.infrastructure.rate_limiter`).

## Streamlit helpers

### `src.interfaces.streamlit.helpers`

- `build_comparison_table(dataframe)` – produce a tidy summary for export tabs.
- `calculate_benchmark(dataframe)` – compute aggregated Idiot Index benchmarks for the selected filters.
- `prepare_download_artifacts(summary)` – bundle CSV/JSON/Excel outputs for downloads.
- `build_health_sector_table(summary)` – tabular view of cohort health scores used in the Streamlit health tab.
- `build_health_risk_table(summary)` / `build_health_band_distribution(summary)` – support risk tables and band distribution charts in the UI.

### `src.interfaces.streamlit.components`

Reusable rendering helpers used by `app.py`. Components include `render_page_header`, `render_signal_bar`, `render_insight_tabs`, and `render_download_panel`.

## Agents toolkit

The `agents` package exposes dataclasses and helper functions that map 1:1 with the application service. Import `agents.compute_idiot_index_summary` to trigger evaluations from CLI tools or other Python code. JSON schemas live alongside the dataclasses for validation in typed clients.

---
Licensed under the Apache License 2.0. See [LICENSE](../LICENSE).

## Headless API

### `src.interfaces.api.app`

- `app` – FastAPI-compatible application exposing `/health`, `/healthz`, `/meta/sources`, `/meta/connectors`, `/evaluate`, `/scenario`, `/analytics/health`, `/metrics`, `/observability/status`, and `/observability/digest` endpoints backed by the application services. Requests are instrumented via `ApiTelemetry` to emit Prometheus metrics, trace IDs, and feed the shared `ObservabilityRegistry`.
- `ObservabilityRegistry` – Singleton registry (see `src/infrastructure/observability/instrumentation.py`) aggregating metrics, traces, and health checks. Extensions register instrumentation hooks through it instead of modifying services directly.

### `src.interfaces.api.schemas`

- Lightweight Pydantic-style models (`EvaluateRequest`, `EvaluateResponse`, `ScenarioRequest`, etc.) plus helpers to convert pandas dataframes and service summaries into JSON-safe payloads.

### `src/scripts/run_api.py`

- CLI entrypoint to launch the headless API service with configurable host/port. Falls back to the built-in WSGI server when third-party servers are unavailable. Used by `make api` and the Docker `APP_MODE=api` entrypoint.

### `src.extensions.manager`

- `ExtensionManager` – registry that loads `SummaryExtension`, `ScenarioExtension`, `ConnectorExtension`, and `InstrumentationExtension` implementations declared in `extensions/manifest.json`. Provides helpers (`apply_*`, `connector_catalog`, `initialise_connectors`) that augment service responses with extension metadata, observability hooks, and connector catalogues.
- `load_extensions(modules=None)` – import modules and invoke their `register(manager)` function.
- `get_extension_manager()` – singleton accessor used by the API, services, and scripts.
