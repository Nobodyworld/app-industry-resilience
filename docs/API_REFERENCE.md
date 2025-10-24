# API Reference

This reference captures the primary Python entrypoints intended for reuse across user interfaces, agents, and downstream automation. All modules live under `src/` unless otherwise noted.

## Application services

### `src.application.service.IdiotIndexService`

| Member | Description |
| --- | --- |
| `IdiotIndexService.evaluate(year, source, dataframe=None, top_n=50)` | Orchestrates dataset loading, normalisation, metric calculation, and leaderboard summarisation. Accepts a `DataSource` enum (`SAMPLE`, `CENSUS`, `BEA`) and an optional pre-loaded dataframe (used for uploads/tests). Returns an `IdiotIndexSummary` dataclass with `dataframe_full`, `leaderboard`, and metadata. |
| `IdiotIndexService.from_config(config)` | Convenience constructor wiring cache, adapters, and retry policies from an `AppConfig`. |

### `src.application.evaluate_idiot_index`
High-level helper that instantiates `IdiotIndexService.from_config` and calls `evaluate`. Mirrors the signature above for convenience in UI code.

## Adapters

### `src.adapters.bea`

| Member | Description |
| --- | --- |
| `fetch_go_ii_by_industry(api_key, year)` | Fetches Gross Output and Intermediate Inputs tables for one or more years, validates inputs, merges NAICS metadata, and returns a pandas `DataFrame` with BEA metadata attached in `df.attrs`. Raises `BEAClientError` when validation fails or endpoints are unavailable. |
| `select_bea_endpoint(config)` | Iterates through configured BEA base URLs, returning the first healthy endpoint that responds to a `GetParameterValues` health check. |
| `BEA_TABLES` | Tuple of table descriptors fetched per year. Useful if you need to inspect or extend coverage. |

### `src.adapters.census`
Provides similar helpers for the Census ASM dataset. Use `fetch_census_asm` to fetch shipments, cost of materials, and value-added data, handling pagination and validation internally.

### `src.adapters.csv_loader`
Contains `load_sample_csv` for offline demo data and `load_csv` for arbitrary CSV inputs with schema validation.

## Core utilities

### `src.core.config`
- `load_config()` reads environment variables, `.env`, and defaults into an `AppConfig` dataclass.
- `AppConfig.supported_years_bea` / `supported_years_census` expose `range` objects for validation.

### `src.core.metrics`
- `compute_metrics(dataframe)` calculates Idiot Index, value-added share, materials share, and guards division-by-zero.
- `rank_industries(dataframe, metric="idiot_index", top_n=10)` surfaces leaderboard slices.

### `src.core.security.SecurityUtils`
Collection of static methods for validating API keys, CSV uploads, and general string sanitisation. All UI entrypoints call these utilities before processing user-supplied data.

## Streamlit helpers

### `src.interfaces.streamlit.helpers`
- `build_comparison_table(dataframe)` – produce a tidy summary for export tabs.
- `calculate_benchmark(dataframe)` – compute aggregated Idiot Index benchmarks for the selected filters.
- `prepare_download_artifacts(summary)` – bundle CSV/JSON/Excel outputs for downloads.

### `src.interfaces.streamlit.components`
Reusable rendering helpers used by `app.py`. Components include `render_page_header`, `render_signal_bar`, `render_insight_tabs`, and `render_download_panel`.

## Agents toolkit

The `agents` package exposes dataclasses and helper functions that map 1:1 with the application service. Import `agents.compute_idiot_index_summary` to trigger evaluations from CLI tools or other Python code. JSON schemas live alongside the dataclasses for validation in typed clients.

---
Licensed under the repository's proprietary terms. See [LICENSE](../LICENSE).
