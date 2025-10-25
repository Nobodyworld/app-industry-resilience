# Architecture Overview

The Idiot Index application is organised into clear layers to separate domain logic from interfaces and infrastructure concerns. Each layer focuses on a single responsibility and exposes a minimal public surface.

## Layer catalogue

### Core (`src/core/`)

Holds pure domain logic and reusable utilities:

- `config` parses environment variables into an `AppConfig` dataclass and captures validation results through `ConfigValidationResult`.
- `cache` provides filesystem-backed caching primitives used by adapters to avoid redundant network calls.
- `metrics` and `normalize` turn raw industry data into consistent schema with Idiot Index, value-added %, materials share %, and friendly column names.
- `scenario_planner` reuses normalization and metrics to simulate percentage shocks and recompute resilience metrics for scenarios.
- `security` validates API keys, file uploads, and user-provided search strings.
- `types` and `utils` expose shared dataclasses and HTTP helpers (with retry policies) that stay free of Streamlit dependencies.

All of these modules are re-exported via `src/core/__init__.py`, while thin compatibility wrappers under `src/` keep older import paths operational.

### Application (`src/application/`)

Coordinates Idiot Index use cases without depending on Streamlit. The
`IdiotIndexService` exposes an injectable façade that loads configuration,
fetches datasets (via adapters or provided dataframes), normalises columns,
computes metrics, and builds leaderboards before returning immutable summaries.
The module re-exports a convenience `evaluate_idiot_index` function backed by
the same service so existing callers stay stable. Logger hooks allow
instrumentation without coupling directly to the infrastructure layer. Both the
UI and agent surfaces consume this package, and the `ScenarioPlanner` extends
the layer with percentage-based adjustments and delta summaries used by the
Scenario Lab and CLI.

### Adapters (`src/adapters/`)

External data connectors for BEA and Census ASM APIs. They depend on the core layer for caching, security, and normalisation, and log behaviour via infrastructure utilities. Legacy imports under `src/sources/` re-export the new modules to avoid breaking existing integrations.

### Infrastructure (`src/infrastructure/`)

Cross-cutting concerns such as logging configuration and rate limiting. Logging is centralised in `logging_config.py`, which emits structured JSON with optional redaction, while `rate_limiter.py` exposes token-bucket throttling used by API adapters.

### Interfaces (`src/interfaces/`)

UI presentation components. The Streamlit implementation lives in `src/interfaces/streamlit/`, exposing sidebar orchestration (`bootstrap.py`), layout helpers (`components.py`), and download preparation/state utilities (`helpers.py`). Compatibility wrappers continue to exist under `src/ui/` so legacy imports remain valid.

### Agents (`agents/`)

Agent-ready surfaces defined with dataclasses and lightweight schema metadata in `agents/idiot_index.py`. Tools are registered via `agents/toolkit.py`, which builds JSON Schema definitions so automation platforms can validate payloads before execution.

### Entry Point (`app.py`)

The Streamlit application composes the layers: it reads configuration from core, retrieves data via adapters, leverages normalisation/metric utilities, renders UI components, and provides downloads. Query parameters are encoded via helpers so deep links remain stateless.

## Data flow

1. **Configuration** – `app.py` calls `src.interfaces.streamlit.bootstrap.get_bootstrap_state()` to load and validate configuration, surfacing errors in the sidebar banner.
2. **Acquisition** – depending on the active mode, adapters load the offline CSV, call BEA with failover + caching, or contact Census ASM. Rate limiting and logging instrumentation live in `src/infrastructure`.
3. **Processing** – the resulting dataframe is normalised and passed through `compute_metrics`. Attributes on the dataframe capture provenance metadata (e.g., BEA notes) that are surfaced in downloads and agents.
4. **Application orchestration** – `src.application.idiot_index_service` prepares the display dataframe, filtered slices, leaderboard, and benchmark stats consumed by the UI and agents.
5. **Presentation** – Streamlit components render hero copy, tables, charts, and the deep-dive panel. Download buttons are powered by `prepare_download_artifacts`, which precomputes CSV/JSON/Excel payloads.
6. **Automation** – the agent toolkit wraps the same services into dataclass-driven APIs, exposing JSON schemas for integrations.

## Caching and observability

- API responses may be cached via `AppConfig.cache` settings; the cache key schema is documented in `src/core/cache` and reused by adapters.
- Logging defaults to structured JSON with redaction (see `src/logging_config.py`). Tests assert behaviour via fixtures in `tests/infrastructure`.
- Performance timing is recorded through `log_performance` so BEA/ASM fetch durations appear in logs.

## Security posture

- All user inputs (API keys, search strings, CSV uploads) pass through `SecurityUtils` for validation and sanitisation.
- File uploads are scanned for size limits, column presence, and suspicious patterns before ingestion.
- External HTTP calls rely on `safe_get_json`, which implements retries, exponential backoff, jitter, and explicit error types to keep failure modes clear.

## Testing strategy

`tests/` maps to the layered structure, exercising config validation, caching, metrics, security utilities, logging behaviour, UI helpers, and the agent tool registry. pytest fixtures wire up backwards-compatible import paths and stub network calls so tests stay deterministic.

## Backward compatibility

To avoid breaking existing imports, thin shims remain under `src/` (e.g., `src/config.py`, `src/sources/`, `src/ui/`). They forward to the reorganised modules while external consumers migrate. Legacy paths carry docstrings noting their compatibility purpose.
