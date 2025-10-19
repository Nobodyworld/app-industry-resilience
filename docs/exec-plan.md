```md
# Production Hardening Follow-Up: Closing TODOs and Elevating UX

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Maintain this document in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

The Idiot Index application already exposes typed configuration, caching, normalization, and API adapters, but lingering TODOs block a production release. This follow-up focuses on eliminating those TODO markers through concrete features: richer Streamlit workflows (comparisons, historical trends, shareable URLs, diversified exports), resilient BEA integrations (health monitoring, failover, pagination, metadata enrichment, NAICS mapping), and observability enhancements (structured logging with redaction and remote shipping). By the end, the UI should surface the new insights without regressions, BEA fetches should adapt to adverse conditions, logging must be structured and configurable, and the automated test suite should pin the new behaviour.

## Progress

- [x] (2025-01-16 12:20Z) Captured current state and authored initial ExecPlan.
- [x] Established Python package structure and shared constants module.
- [x] Replaced ad-hoc configuration globals with typed settings loader and validation utilities.
- [x] Hardened normalization and metric computation with richer validation and well-defined error handling.
- [x] Modernized security utilities (file upload, string sanitization, API keys) with deterministic policies and logging hooks.
- [x] Refactored cache helpers for deterministic TTL, statistics, and safe teardown; eliminated dead globals.
- [x] Aligned utility HTTP client with retry/circuit-breaker scaffolding and type hints.
- [x] Updated Streamlit entrypoint to consume new modules, surface actionable errors, and remove outdated TODOs.
- [x] Expanded automated tests to cover config loading, normalization edge cases, metrics caching, security policies, and HTTP utilities.
- [x] Refreshed documentation (README, docs/) to describe configuration, security posture, and testing workflow.
- [x] Ran full test suite and linting; ensured repository is clean.
- [x] (2025-02-14 19:05Z) Deliver Streamlit feature upgrades covering comparisons, historical trends, benchmarking, diversified exports, and shareable URLs while preserving existing interactions.
- [x] (2025-02-14 19:05Z) Implement BEA client resiliency upgrades: endpoint health monitoring, failover across base URLs, pagination, multi-year parallel fetch, metadata extraction, validation, and NAICS enrichment.
- [x] (2025-02-14 19:05Z) Enhance logging configuration with structured JSON output, sensitive-field redaction, remote shipping hooks, and runtime log-level controls.
- [x] (2025-02-14 19:05Z) Extend automated tests to lock in new BEA behaviours, logging outputs, and UI helper utilities.
- [x] (2025-02-14 19:05Z) Update documentation to explain new UI capabilities, BEA resiliency, logging knobs, and export options; rerun full test suite.

## Surprises & Discoveries

- Observation: Existing BEA adapter already caches per-year responses but lacks metadata or alternate host support; modifications must keep cache compatibility while adding metadata.
  Evidence: `src/sources/bea.py` returns a DataFrame built from cached JSON records without attrs.
- Observation: Excel exports require optional tooling; export helper now degrades gracefully when `xlsxwriter` is unavailable.
  Evidence: `prepare_download_artifacts` checks for the module and tests assert CSV/JSON outputs regardless.

## Decision Log

- Decision: Represent shareable UI state as encoded query parameters instead of server-side persistence so Streamlit sessions stay stateless.
  Rationale: Works with Streamlit's rerun model and avoids external storage requirements while still satisfying the sharing TODO.
  Date/Author: 2025-02-14 / gpt-5-codex

## Outcomes & Retrospective

- Streamlit now supports multi-industry comparisons, historical trend charts, benchmarking deltas, diversified exports, and shareable URLs without regressing existing flows. BEA integrations added endpoint health checks, failover rotation, pagination, multi-year concurrency, NAICS enrichment, and metadata-rich caching. Logging emits redacted structured output with dynamic level controls, and new tests cover BEA behaviours, logging utilities, and UI helpers. Documentation highlights the new capabilities and `pytest` passes.

## Context and Orientation

Repository structure remains: `app.py` orchestrates Streamlit UI, `src/` contains reusable modules (configuration, caching, normalization, metrics, security, HTTP utils, rate limiting, sources, UI components). Tests live in `tests/`. Outstanding TODOs target `app.py`, `src/sources/bea.py`, and `src/logging_config.py`. Assets include `assets/naics_map.csv` for industry metadata. Requirements specify Streamlit, pandas, requests, python-dotenv, plotly, and pytest.

Key current behaviours:
- `app.py` loads config at import, renders sidebar, uses normalization/metrics, but lacks comparison/trend/export enhancements and shareable URLs.
- `src/sources/bea.fetch_go_ii_by_industry` fetches two tables sequentially for a single year, caches results, and returns normalized data without metadata or failover.
- `src/logging_config.setup_logging` configures console/file handlers but lacks structured JSON, redaction, remote shipping, or dynamic level adjustments.

## Plan of Work

1. **Streamlit Feature Enhancements**
   - Add imports (`io`, `pandas as pd`, `plotly.express as px`, typing helpers) and restructure state management into helper functions enabling multi-select comparisons and query parameter syncing.
   - Introduce new helper utilities (possibly under `src/ui`) to manage comparison tables, benchmarking calculations, filtered exports, and shareable URL encoding.
   - Update the UI to include comparison panels, historical trend charts (line chart aggregated by industry/year), benchmarking summary against dataset averages, and multiple export buttons (CSV, JSON, Excel) for both full and filtered datasets.
   - Generate shareable links by updating Streamlit query parameters and surface a copy-ready URL.

2. **BEA Client Resiliency**
   - Expand `fetch_go_ii_by_industry` to accept `year | Iterable[int]`, performing per-year fetches concurrently using thread pools, aggregating results, deduplicating, and storing metadata in `DataFrame.attrs`.
   - Implement endpoint health checks and failover: derive base URLs from config/env, probe endpoints via lightweight metadata requests, and gracefully fall back when necessary while logging outcomes.
   - Support API version negotiation via config (e.g., optional `BEA_API_VERSION`) by injecting into params when provided.
   - Handle pagination by iterating while the BEA response exposes next-page markers; accumulate data rows accordingly.
   - Integrate NAICS mapping by joining with `assets/naics_map.csv` for friendly names/grouping and validate essential columns, raising descriptive errors otherwise.
   - Ensure caching keys remain stable (include sorted years) and incorporate compression-aware headers when calling `safe_get_json`.

3. **Logging Enhancements**
   - Create structured formatter with automatic redaction for sensitive fields (`key`, `token`, etc.), toggleable via parameters/environment.
   - Allow dynamic log level updates (function to set global/app logger levels) and auto-read environment variables.
   - Add optional remote shipping using `SocketHandler` or `SysLogHandler` when configuration/environment requests it.
   - Provide helper APIs (`configure_logging_from_config`) hooking into `src.config.AppConfig` to align log settings with app configuration.

4. **Testing & Tooling**
   - Extend tests in `tests/` to cover: BEA multi-year fetch behaviour with caching, metadata attrs, fallback logic (mocked), and NAICS enrichment; logging structured output and redaction; UI helper computations for benchmarking/export state.
   - Add fixtures/mocks to avoid network usage and to simulate endpoint failures and pagination.
   - Ensure new helper modules are imported in tests using package-relative paths.

5. **Documentation & Validation**
   - Update `README.md` (and possibly docs) summarizing new comparison/trend/export features, shareable URLs, logging options, and BEA resiliency.
   - Confirm requirements remain minimal (no new heavy dependencies) and adjust dev requirements if tests rely on new tooling.
   - Run `pytest` to ensure green.

## Concrete Steps

- Modify `app.py` and potentially add helper modules under `src/ui/` for comparison logic and shareable URL encoding.
- Update `src/sources/bea.py` to incorporate multi-year support, failover, metadata, NAICS mapping, and pagination handling.
- Enhance `src/logging_config.py` with structured logging, redaction, remote shipping, and dynamic level controls.
- Add/modify tests: extend `tests/test_core.py` or create focused test files for BEA/logging/UI helpers using mocks.
- Refresh documentation (README) for new features and logging instructions.
- Execute `pytest` from repository root.

## Validation and Acceptance

- `pytest` must pass, including new tests verifying BEA multi-year aggregation, logging format redaction, and helper computations.
- Manual Streamlit run (`streamlit run app.py`) should present new comparison/trend/export/share panels without exceptions; README outlines how to observe them.
- BEA client should handle fallback gracefully (tested via mocks) and attach metadata/NAICS mapping, with caching still functional.

## Idempotence and Recovery

- BEA cache keys incorporate years; rerunning fetches reuses existing entries while metadata is stored per-year without duplicates.
- Logging configuration functions are idempotent, replacing handlers when called repeatedly.
- Streamlit query parameter updates happen deterministically; clearing browser query resets shareable state.

## Artifacts and Notes

- Capture sample JSON-formatted log output in tests to assert redaction.
- Provide test fixture data for BEA responses including pagination tokens and metadata fields.

## Interfaces and Dependencies

- No new heavy dependencies; rely on standard library (e.g., `json`, `concurrent.futures`) and existing packages.
- Public interface updates:
    - `src.sources.bea.fetch_go_ii_by_industry(api_key: str, year: int | Iterable[int]) -> pd.DataFrame`
    - New helper `src.sources.bea.select_bea_endpoint(...) -> str`
    - Logging config exposes `configure_logging_from_config(app_config: AppConfig, *, structured: bool | None = None) -> logging.Logger`
    - UI helpers (e.g., `src/ui/state.py` or similar) provide shareable URL/state encoding functions used by `app.py`.
```
