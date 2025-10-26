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
- **Purpose:** Provide reusable primitives such as configuration (`config`), caching (`cache`), metrics (`metrics`), health analytics (`analytics`), normalisation (`normalize`), and security validation (`security`).
- **Highlights:** Security utilities ensure API keys, uploads, and CSV content are validated before downstream processing. The analytics module computes composite health scores, risk bands, and cohort summaries that are reused by both UI components and the headless API.

### Application
- **Location:** `src/application`
- **Purpose:** Compose adapters and core services into workflows. `IdiotIndexService` coordinates dataset selection, normalisation, metrics, and leaderboard preparation. The thin wrapper `evaluate_idiot_index` powers both UI and headless automation entrypoints.

### Interfaces
- **Location:** `src/interfaces`
- **Purpose:** Present data via Streamlit (`interfaces/streamlit`), the headless API surface (`interfaces/api`) implemented with a FastAPI-compatible façade, or CLI/automation helpers. Streamlit components follow a modular pattern for reusability and test coverage, while the API reuses the same application services to support machine-to-machine access.

### Infrastructure
- **Location:** `src/infrastructure`
- **Purpose:** Cross-cutting concerns like logging, throttling (`api_limiter`), observability, and caching. These modules are shared across adapters and services to keep instrumentation consistent.
- **Highlights:** `src/infrastructure/observability` now centralises metrics, tracing, and health integration through the `ObservabilityRegistry`. Application services wrap key operations with `registry.operation(...)` so spans, Prometheus counters, and health snapshots stay in sync. Logs automatically include the active `trace_id`.

### Agents
- **Location:** `agents`
- **Purpose:** Provide dataclass-driven schemas and functions so downstream automation or LLM agents can reuse the Idiot Index service without touching Streamlit internals.

### Extensions
- **Location:** `src/extensions`
- **Purpose:** Load modular analytics via `ExtensionManager`. Summary extensions enrich `IdiotIndexSummary` objects with additional notes or metadata, scenario extensions decorate `ScenarioResult` payloads, and instrumentation extensions register metrics/health hooks against the shared observability registry. Modules are discovered through `extensions/manifest.json` and the `IDIOT_INDEX_EXTENSIONS` environment variable.
- **Highlights:** The built-in `manufacturing_cost_driver` extension demonstrates data enrichment, while `core_instrumentation` wires counters and health checks for pipeline execution.

## Data flow summary

1. **Configuration bootstrap** – `app.py` loads configuration via `src.core.config.load_config()`, validating environment variables, API keys, and file policies.
2. **Data acquisition** – `src.application.service.IdiotIndexService` requests data from adapters based on user selection (sample CSV, BEA, or Census ASM). Adapters rely on shared retry/caching utilities.
3. **Normalisation** – `src.core.normalize` ensures consistent column naming; `src.core.metrics.compute_metrics` calculates Idiot Index, value-added %, and material share metrics. `src.core.analytics.compute_health_scores` then derives composite health scores and risk bands that flow into service responses.
4. **Narrative rendering** – Streamlit components under `src.interfaces.streamlit` render hero metrics, health insights, tables, and charts while maintaining accessible structure for tests.
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
- The `ObservabilityRegistry` (in `src/infrastructure/observability/instrumentation.py`) provides a single surface for Prometheus metrics, trace spans, health probe contributions, and recent event capture. Both `IdiotIndexService` and `ScenarioPlanner` wrap their core pipelines with registry operations so successes and failures emit structured telemetry.
- Instrumentation extensions (see `src/extensions/builtins/core_instrumentation.py`) subscribe to those events and expose counters (`idiot_index_pipeline_runs_total`) and latency histograms. Additional extensions can subscribe to custom event names without touching core services.
- The headless API records request metrics via `src/interfaces/api/telemetry`, exposes Prometheus text at `/metrics`, and publishes a holistic snapshot at `/observability/status` for dashboards and air-gapped audits. The same payload is available offline via `python scripts/observability_snapshot.py --pretty`.
- `src/infrastructure/observability/health.py` provides the reusable `HealthProbe`, powering both HTTP health endpoints and the `scripts/check_health.py` CLI. The registry binds into the probe so instrumentation extensions can ship bespoke health signals.
- Incident response procedures are documented in `docs/OPERATIONS_INCIDENT_RESPONSE.md`, now referencing the observability CLI for triage and recovery.

## Future-proofing & Migration Notes

- **Plugin boundaries:** New automation, analytics, or monitoring capabilities should ship as extensions. Instrumentation plugins keep metrics decoupled from business logic, while summary/scenario plugins extend payloads. Use `python scripts/scaffold_extension.py --name <id> --instrumentation` to bootstrap both code and manifest entries.
- **Service scaffolds:** `python scripts/scaffold_service.py --name <service>` generates an observability-aware service shell under `src/application/services/` so future modules inherit tracing, metrics, and extension wiring.
- **Scaling considerations:** The observability registry is intentionally lightweight; for distributed deployments swap the tracer implementation or plug an OTLP exporter behind the same interface. Health checks already expose registry counts, simplifying readiness probes behind load balancers.
- **Next major upgrade path:** To support multi-tenant or async workloads, isolate data adapters behind explicit interfaces and let instrumentation extensions register tenant IDs as metric labels. The registry API is stable so callers can evolve without changing existing hooks.

---
Licensed under the repository's proprietary terms. See [LICENSE](../LICENSE).
