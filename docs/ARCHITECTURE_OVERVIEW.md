# Architecture Overview

The Idiot Index application follows a layered Python architecture designed for testability and safe data handling. The layout keeps adapters, core logic, interfaces, and automation surfaces isolated so that each concern can evolve independently.

```text
┌───────────────────────────────────────────────────────────────────────┐
│  interfaces/streamlit                     agents                      │
│  (user experience + narrative)            (automation toolkit)        │
└──────────────┬──────────────────────────────────────────────┬─────────┘
               │                                              │
        application                                infrastructure
 (service orchestration + pipelines)      (logging, rate limits, caching)
               │                                              │
                        core (config, security, metrics)
                                   │
                          adapters (BEA, ASM, CSV)
                                   │
                         external data providers
```

## Layer responsibilities

### Adapters
- **Location:** `src/adapters`
- **Purpose:** Translate external data sources into normalized frames ready for the domain layer. The BEA adapter handles endpoint health checks, retries, caching, and NAICS enrichment.
- **Key modules:** `bea.py`, `census.py`, `csv_loader.py`

### Core
- **Location:** `src/core`
- **Purpose:** Provide reusable primitives such as configuration (`config`), caching (`cache`), metrics (`metrics`), normalisation (`normalize`), and security validation (`security`).
- **Highlights:** Security utilities ensure API keys, uploads, and CSV content are validated before downstream processing.

### Application
- **Location:** `src/application`
- **Purpose:** Compose adapters and core services into workflows. `IdiotIndexService` coordinates dataset selection, normalisation, metrics, and leaderboard preparation. The thin wrapper `evaluate_idiot_index` powers both UI and headless automation entrypoints.

### Interfaces
- **Location:** `src/interfaces`
- **Purpose:** Present data via Streamlit (`interfaces/streamlit`), the headless API surface (`interfaces/api`) implemented with a FastAPI-compatible façade, or CLI/automation helpers. Streamlit components follow a modular pattern for reusability and test coverage, while the API reuses the same application services to support machine-to-machine access.

### Infrastructure
- **Location:** `src/infrastructure`
- **Purpose:** Cross-cutting concerns like logging, throttling (`api_limiter`), and telemetry. These modules are shared across adapters and services to keep observability consistent.
- **Highlights:** `src/infrastructure/observability` provides Prometheus-compatible metrics, lightweight tracing, and helpers used by the instrumented FastAPI façade. Logs automatically include the active `trace_id`.

### Agents
- **Location:** `agents`
- **Purpose:** Provide dataclass-driven schemas and functions so downstream automation or LLM agents can reuse the Idiot Index service without touching Streamlit internals.

### Extensions
- **Location:** `src/extensions`
- **Purpose:** Load modular analytics via `ExtensionManager`. Summary extensions enrich `IdiotIndexSummary` objects with additional notes or metadata, while scenario extensions decorate `ScenarioResult` payloads. Modules are discovered through `extensions/manifest.json` and the `IDIOT_INDEX_EXTENSIONS` environment variable.
- **Highlights:** The built-in `manufacturing_cost_driver` extension demonstrates how to calculate additional insights and surface them in API responses.

## Data flow summary

1. **Configuration bootstrap** – `app.py` loads configuration via `src.core.config.load_config()`, validating environment variables, API keys, and file policies.
2. **Data acquisition** – `src.application.service.IdiotIndexService` requests data from adapters based on user selection (sample CSV, BEA, or Census ASM). Adapters rely on shared retry/caching utilities.
3. **Normalisation** – `src.core.normalize` ensures consistent column naming; `src.core.metrics.compute_metrics` calculates Idiot Index, value-added %, and material share metrics.
4. **Narrative rendering** – Streamlit components under `src.interfaces.streamlit` render hero metrics, tables, and charts while maintaining accessible structure for tests.
5. **Automation reuse** – The `agents` package exports typed request/response contracts mirroring the application service so CLI or AI clients can trigger evaluations safely.

## Caching & performance

- The BEA adapter caches merged responses using the configured cache backend (`src.core.cache`).
- NAICS lookup tables load once per process (`functools.lru_cache`).
- Thread pools fetch multiple years concurrently while respecting rate limits through `src.infrastructure.api_limiter`.

## Security boundaries

- API keys are validated and stripped using `src.core.security.SecurityUtils` before network calls.
- CSV uploads pass both metadata and content validation, ensuring only expected schemas reach the pipeline.
- Secrets (API keys) should be supplied through environment variables or `.env`; commit hooks prevent accidental leakage.

## Observability

- Structured logging is handled through `src.infrastructure.logging_config` which attaches trace IDs and redacts sensitive data.
- The headless API records request metrics via `src/interfaces/api/telemetry` and serves them under `/metrics`. Latency histograms, in-flight gauges, and error counters are available for Prometheus scrapers.
- `log_performance`, `log_api_call`, and `log_data_processing` annotate key milestones for debugging and performance monitoring.
- Incident response procedures are documented in `docs/OPERATIONS_INCIDENT_RESPONSE.md`.

---
Licensed under the repository's proprietary terms. See [LICENSE](../LICENSE).
