# Idiot Index – U.S. Industry Dashboard

A pragmatic Streamlit app to estimate and visualize the so‑called **“Idiot Index”** across industries:

> **Idiot Index = Gross Output ÷ Cost of Materials (or Intermediate Inputs)**

This isn’t an academic metric; it’s a blunt heuristic popularized in engineering circles to spot bloated cost structures. Use it as a red‑flag indicator, then dig deeper.

---

## Verification status

- Verified:
  - Streamlit dashboard startup and offline sample-dataset workflow.
  - Headless API test suite paths covered by `tests/test_api.py`.
  - Clean-clone dependency install and full test run (`214 passed`).
- Partial:
  - Repository-wide quality gate is partially passing in clean-clone validation. `mypy` and `black --check` pass, but `ruff check` currently reports import-order and enum-modernization findings.
  - Coverage enforcement is configured at `90%`, while clean-clone measured coverage is currently `75.02%`.
- Experimental:
  - Remote observability snapshot replication backends (S3, GCS, Azure) are available but environment-dependent and require external infrastructure/configuration.
- Planned:
  - Final release-candidate hardening pass to close lint findings, coverage deficit, and detect-secrets baseline compatibility issues on Windows.

## Public-release limitations

- Local validation is authoritative for this repository at this stage because GitHub Actions is intentionally disabled by owner policy in most repositories.
- `detect-secrets-hook --baseline config/.secrets.baseline` currently fails with `Invalid baseline` in clean-clone Windows validation and needs baseline format/compatibility remediation.
- `pip-audit` reports a vulnerability for `black==25.12.0` with an available fixed version (`26.3.1`), which must be reconciled against current version constraints before public release.
- Coverage quality gate (`--cov-fail-under=90`) fails in clean-clone validation and currently blocks release-candidate readiness.

---

## What this app does

- Pulls industry data from **BEA** (Gross Output, Intermediate Inputs, Value Added) and **Census ASM** (Shipments, Cost of Materials, Value Added) when API keys are provided.
- Computes:
  - Idiot Index (Output ÷ Materials / Intermediate Inputs)
  - Value‑Added %
  - Gross‑margin analogs
  - Resilience score, materials dependency ratio, and shock sensitivity index
- Lets you:
  - Compare sectors via sortable tables
  - Build multi-industry comparison sets with historical trend charts
  - Drill down by NAICS code with robust error handling
  - Generate shareable URLs that preserve filters and selections
  - Upload your own CSVs with automatic schema validation
  - Export results in CSV, JSON, or Excel, including the current filtered view
  - Explore data with interactive Plotly charts
  - Stress test industries with the Scenario Lab to model cost/output shocks
- Works **offline** out of the box via a bundled sample dataset.
- Computes a **composite health score** with risk banding so you can spot fragile industries at a glance.
- **Robust error handling** with graceful degradation and clear user feedback
- **Input validation** for all user inputs and data sources

> **Blunt reality:** Official APIs evolve. The BEA and ASM endpoints/variables change over time.
> This app isolates API calls so you can fix one file when the feds reshuffle schemas.

---

## Quick start (no keys, offline demo)

```bash
# 1) Create and activate a virtual environment (optional but recommended)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 2) Install deps
pip install -r requirements.txt

# 3) Run
streamlit run app.py
```

Open the local URL it prints (usually <http://localhost:8501>). The app will load the **sample dataset** so you can click around immediately.

## Usage examples

### Compare BEA industries for a target year

1. Launch the app (`streamlit run app.py`).
2. Enter your BEA API key in the sidebar and pick **BEA (Economy-wide)** from the data source selector.
3. Select a year supported by BEA (the sidebar highlights the available range).
4. Watch the new **fetch progress indicator** in the sidebar. When the call succeeds, the dashboard populates with the requested industries and a success callout confirming the fetch.
5. Use the search box to filter industries or switch to *Focus mode* for a heads-up view of the highest Idiot Index readings.

### Upload a custom CSV baseline

1. Choose **Upload CSV** from the sidebar.
2. Provide a CSV with the columns `industry_code`, `industry_name`, and `year` plus at least one metric column (`gross_output`, `materials_cost`, or `intermediate_inputs`).
3. The upload validator confirms schema alignment; successful loads render instantly with local-only messaging so you know nothing leaves your machine.
4. Combine the CSV data with BEA or ASM metrics by switching data sources and comparing Idiot Index narratives side-by-side.

### Model a shock scenario

1. Scroll to the **Scenario Lab** section after configuring your dataset.
2. Select one or more industries (leave blank to apply the shock to the entire view).
3. Adjust the sliders to reflect changes in gross output, materials cost, value added, or intermediate inputs.
4. Review the comparison table, resilience metrics, and delta chart to understand how the shock shifts the Idiot Index.
5. Copy the shareable link or export the scenario-adjusted dataset using the existing download panel.

## Docker Deployment

For easy deployment and development:

```bash
# Build the Docker image
docker build -t idiot-index-app .

# Run the container
docker run -p 8501:8501 idiot-index-app
```

Set `PREFETCH_ARGS="--sources sample --years 2019 2020"` when starting the container to warm caches before Streamlit boots. The runtime entrypoint invokes `scripts/prefetch_data.py` whenever the variable is non-empty.

### Run the headless API

Set `APP_MODE=api` (and optionally `API_PORT`) to launch the headless API service instead of Streamlit:

```bash
docker run -e APP_MODE=api -p 9000:9000 idiot-index-app
```

The image shares the same cache prefetch hook regardless of mode. Health checks probe `/health` when `APP_MODE=api` and the Streamlit endpoint otherwise.

## Development

Install development and tooling dependencies plus git hooks with a single command:

```bash
make setup
```

`make setup` installs Python runtime + dev dependencies and registers the `pre-commit` hooks (including the `commit-msg` hook that enforces Conventional Commits). Set `SKIP_PIP=1 make setup` if you are working in an offline environment where pip cannot reach PyPI.

Every change should pass the repository quality gate before you push:

```bash
make quality-gate
```

`make quality-gate` executes linting (Black in check mode + Ruff), mypy, full pytest with coverage enforcement, and the security scans (`pip-audit` + `detect-secrets`). The target mirrors the CI pipeline to keep local and remote checks aligned.

Targeted commands are also available:

```bash
make format        # Auto-format using Black
make lint          # Ruff linting without auto-fix
make typecheck     # mypy static analysis
make test          # pytest without coverage
make security      # pip-audit + detect-secrets baseline validation
make sbom          # Generate CycloneDX SBOM at build/sbom/cyclonedx.json
make scenario      # Run the scenario planner CLI (pass ARGS="--adjust codes=311,gross=5")
make prefetch-cache # Warm caches using the prefetch utility
make analytics     # Emit health analytics JSON from a CSV dataset
make observability # Print a JSON observability snapshot (pass ARGS="--pretty")
make observability-snapshot # Persist an observability snapshot to disk (pass ARGS="--label nightly")
make observability-tail # Follow observability events in real time (pass ARGS="--limit 5 --follow")
make extensions-catalog # List registered extensions (pass ARGS="--json --pretty")
make connectors-catalog # List registered connectors and health (pass ARGS="--json --pretty")
make audit         # Capture stewardship metrics and write build/reports/audit-metrics.json
make api             # Launch the headless API service (pass ARGS="--port 9100" for custom ports)
make docs          # List key documentation links in the terminal
python scripts/check_health.py --pretty  # Run the consolidated health probe without the HTTP API
python scripts/observability_snapshot.py --store --pretty  # Persist + print a snapshot (use --list/--compare for history)
python scripts/observability_tail.py --follow --limit 10  # Stream recent observability events for triage
python scripts/diagnostics_bundle.py --pretty --output build/reports/diagnostics.json  # Capture config, health, events, and metrics in one bundle
python scripts/extensions_catalog.py --json --pretty  # Inspect registered summary/scenario/instrumentation extensions
python scripts/connectors_catalog.py --json --pretty  # Inspect registered data source and automation connectors
python scripts/run_tests_with_trace.py --threshold 90  # Offline coverage for analytics/API critical paths (override with --paths)
python scripts/audit_metrics.py --runs 3  # Compute coverage/complexity/dependency metrics for the steward report
```

To replicate observability snapshots to a remote object store in addition to local disk, set `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND` and the backend-specific variables before running the app or CLI. Built-in options include:

- `s3` – supply `OBSERVABILITY_SNAPSHOT_S3_BUCKET` plus optional prefix/region/endpoint/credentials (`OBSERVABILITY_SNAPSHOT_S3_PREFIX`, `OBSERVABILITY_SNAPSHOT_S3_REGION`, `OBSERVABILITY_SNAPSHOT_S3_ENDPOINT`, `OBSERVABILITY_SNAPSHOT_S3_ACCESS_KEY`, etc.).
- `gcs` – supply `OBSERVABILITY_SNAPSHOT_GCS_BUCKET` with optional `OBSERVABILITY_SNAPSHOT_GCS_PREFIX`, project overrides, and credentials (`OBSERVABILITY_SNAPSHOT_GCS_PROJECT`, `OBSERVABILITY_SNAPSHOT_GCS_CREDENTIALS_FILE`, `OBSERVABILITY_SNAPSHOT_GCS_CREDENTIALS_JSON`).
- `azure-blob` – supply `OBSERVABILITY_SNAPSHOT_AZURE_CONTAINER` with optional `OBSERVABILITY_SNAPSHOT_AZURE_PREFIX` and either `OBSERVABILITY_SNAPSHOT_AZURE_CONNECTION_STRING` or the combination of `OBSERVABILITY_SNAPSHOT_AZURE_ACCOUNT_URL` + credential (`OBSERVABILITY_SNAPSHOT_AZURE_CREDENTIAL` or `OBSERVABILITY_SNAPSHOT_AZURE_SAS_TOKEN`).

```bash
# S3 example
export OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND=s3
export OBSERVABILITY_SNAPSHOT_S3_BUCKET=idiot-index-snapshots
export OBSERVABILITY_SNAPSHOT_S3_PREFIX=nightly/

# Google Cloud Storage example
export OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND=gcs
export OBSERVABILITY_SNAPSHOT_GCS_BUCKET=idiot-index-snapshots
export OBSERVABILITY_SNAPSHOT_GCS_PROJECT=idiot-index

# Azure Blob example
export OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND=azure-blob
export OBSERVABILITY_SNAPSHOT_AZURE_CONTAINER=idiot-index-snapshots
export OBSERVABILITY_SNAPSHOT_AZURE_CONNECTION_STRING=UseDevelopmentStorage=true
```

Extensions can also provide alternative backends. For example, setting `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND=plugin:debug` and `OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS='{"path": "./build/debug-replication"}'` mirrors every snapshot into a local directory without touching cloud storage. Custom replication modules registered via `ExtensionManager` can read the same options payload to discover per-backend configuration.

The CLI automatically reports whether replication succeeded and where the object landed (S3 URLs or debug filesystem paths), while failures log to stderr without interrupting local persistence.

All helper scripts now self-bootstrap the repository root onto `PYTHONPATH`, so running `python scripts/<name>.py` works without
activating editable installs or manually exporting environment variables.

Commit messages must follow the Conventional Commits spec; the provided hooks will prevent non-conforming messages.

## Headless API usage

Launch the API locally with:

```bash
make api
```

This invokes `scripts/run_api.py`, which serves the lightweight FastAPI-compatible app using Python's built-in WSGI server at `http://localhost:9000` by default. Key endpoints:

- `GET /health` – readiness probe returning service metadata, component-level status, and telemetry counts.
- `GET /healthz` – Kubernetes-style alias that also exposes trace correlation IDs.
- `GET /observability/status` – Prometheus/OpenTelemetry summary (metrics, traces, recent operation events).
- `GET /observability/digest` – enriched observability payload with event counters, last-error context, and subscriber counts.
- `GET /observability/events` – recent observation events with optional status filters for automated incident triage.
- `GET /observability/snapshots` – list of stored observability snapshots (metadata + capture timestamps).
- `GET /observability/snapshots/{snapshot_id}` – full persisted snapshot payload including event counters and last-error context.
- `GET /meta/sources` – list of supported data sources.
- `GET /meta/connectors` – catalog of registered connectors including health summaries and capabilities.
- `POST /evaluate` – compute Idiot Index metrics for a dataset or remote source.
- `POST /scenario` – run Scenario Lab adjustments on a supplied dataset.
- `POST /analytics/health` – return composite health scores, band distribution, and top-risk industries for the requested dataset.
- `GET /metrics` – Prometheus text exposition with counters, histograms, and gauges.

### Command-line health analytics

Generate a JSON summary of industry health directly from a CSV without starting Streamlit:

```bash
make analytics ARGS="--input data/sample_industries.csv --group-by sector --pretty"
```

The script normalises the dataset, computes Idiot Index metrics, derives health scores, and prints cohort summaries with top-risk industries.

See [docs/API_HEADLESS.md](docs/API_HEADLESS.md) for payload schemas and sample `curl` invocations.

## Architecture

The project is organised into dedicated layers (`core`, `adapters`, `application`, `infrastructure`, `interfaces`, and `src/agents`) to keep domain logic decoupled from presentation and automation surfaces.

```
Data sources (BEA, Census, CSV) ──▶ adapters ──▶ core (normalize + metrics)
                                              │
                                              └──▶ application (orchestrate Idiot Index use cases)
                                                        │
                                                        ├──▶ interfaces/streamlit (app.py)
                                                        └──▶ src/agents (toolkit + schemas)
```

### Observability & Extensions

- The headless API is instrumented with `src/interfaces/api/telemetry`, exposing Prometheus metrics at `/metrics`, `/observability/status`, the richer `/observability/digest`, and the snapshot catalogue endpoints under `/observability/snapshots` for historical exports.
- Streamlit's dashboard includes an Observability tab that visualises stored snapshots (event totals, error trends, and last-error payloads). Snapshots persist under `build/observability_snapshots` by default and respect the `OBSERVABILITY_SNAPSHOT_DIR` environment variable. Retention and auto-capture cadence are controlled via `OBSERVABILITY_SNAPSHOT_RETENTION_COUNT`, `OBSERVABILITY_SNAPSHOT_RETENTION_DAYS`, and `OBSERVABILITY_SNAPSHOT_MIN_INTERVAL_SECONDS`.
- Reusable analytics live under `src/extensions` and are orchestrated by `ExtensionManager`. Modules declared in `extensions/manifest.json` load automatically; refer to [docs/handbook/EXTENSION_GUIDE.md](docs/handbook/EXTENSION_GUIDE.md) for scaffolding and testing guidance. The built-in `data_quality` instrumentation extension demonstrates how to subscribe to dataset/scenario profile events, emit gauges, and contribute health checks, while the `snapshot_replication` package wires both S3 and debug replication extensions together with a metrics/health observer that tracks the `observability.snapshot.replication` events emitted by `snapshot_persistence` on startup/shutdown and whenever instrumentation emits `warn`/`error` events. Retention and auto-capture cadence remain governed by the `OBSERVABILITY_SNAPSHOT_RETENTION_*` knobs.
- Connector extensions share the same lifecycle: `ConnectorRegistry` (see `src/extensions/connectors.py`) catalogues data/automation integrations, publishes health/metrics through the observability registry, and surfaces them via `/meta/connectors`, `make connectors-catalog`, and the Streamlit sidebar. The built-in catalog ships entries for the bundled sample CSV, BEA API, and Census ASM sources; custom connectors can be shipped as extensions without modifying core services.

Each layer exposes public APIs via `__init__.py` shims so imports stay stable. The flow when a user opens the dashboard looks like this:

1. **Bootstrap** – `app.py` loads configuration through `src.core.config`, validates environment state, and renders the sidebar context.
2. **Acquire data** – depending on the selected mode, adapters fetch BEA/ASM datasets or load the bundled CSV. Responses are cached on disk when enabled.
3. **Normalise & compute** – `src.core.normalize` standardises column names before `src.core.metrics.compute_metrics` derives Idiot Index, value-added %, and related measures.
4. **Application orchestration** – `src.application` bundles dataset loading, normalisation, metric computation, and leaderboard derivation into testable services (`IdiotIndexService` and the convenience `evaluate_idiot_index`) that power both UI and automation flows. The service accepts injected fetchers/config so other entrypoints can reuse the pipeline without touching Streamlit internals.
5. **Render narrative** – Streamlit components under `src.interfaces.streamlit` build the hero header, signal cards, tables, charts, and deep-dive story, exposing the same helpers used by automated tests.
6. **Share or automate** – downloads are prepared through `src.interfaces.streamlit.helpers`, while the agent toolkit (`src/agents/`) reuses the application services for headless clients. See [docs/handbook/ARCHITECTURE.md](docs/handbook/ARCHITECTURE.md) for an expanded breakdown of each module and data contract.

### Typical workflows

- **Offline demo** – launch `streamlit run app.py`, keep the default "Sample" data source, and explore tables/charts instantly. Use the "Comparisons & benchmarking" section to see relative performance.
- **Live BEA data** – add a BEA API key to `.env`, select "BEA (Economy-wide)" in the sidebar, and fetch multi-year data with automatic NAICS enrichment, caching, and retry logic.
- **Bring your own CSV** – choose "Upload CSV" and drop a file that matches the schema outlined below. The app validates file metadata and contents before merging with the same metrics pipeline.

Deeper context lives in the `/docs` directory:

- [Architecture overview](docs/handbook/ARCHITECTURE_OVERVIEW.md) summarises system boundaries, caching flows, and fault domains.
- [API reference](docs/API_REFERENCE.md) enumerates service entrypoints, adapter helpers, and expected responses.
- [Data refresh workflow](docs/WORKFLOWS_DATA_REFRESH.md) guides rotating API keys, syncing assets, and validating new datasets.
- [Dependency register](docs/DEPENDENCIES.md) tracks runtime and tooling libraries with license and review cadence notes.
- Handbook-style governance and release guides (plan, status, report, automation, release notes, security, support) live under `docs/handbook/` to keep the repository root focused on entrypoints and metadata.

### Key metrics

- **Idiot Index** – `gross_output ÷ materials_cost` or `gross_output ÷ intermediate_inputs` when materials are absent.
- **Value-Added %** – `(value_added ÷ gross_output) × 100` when both fields exist.
- **Materials Share %** – `(materials_cost ÷ gross_output) × 100`.

The `src/core.metrics` module documents the calculations in depth, while the agent docs detail the JSON responses that expose them for automation.

## Agent integrations

Automated clients can call the Idiot Index pipeline through the agent toolkit under `src/agents/`. The primary tool, `compute_idiot_index_summary`, exposes validated dataclass payloads and JSON schemas for integration. See [docs/AI_INTERFACE.md](docs/AI_INTERFACE.md) for invocation details and schema definitions.

## Programmatic usage example

```python
from src.agents import IdiotIndexRequest, compute_idiot_index_summary

payload = IdiotIndexRequest(year=2022, source="sample", top_n=3)
result = compute_idiot_index_summary(payload)

for industry in result.top_industries:
    print(industry.code, industry.name, f"Index: {industry.idiot_index:.2f}")
```

The agent toolkit mirrors the Streamlit pipeline, making it safe to reuse for background jobs, chat assistants, or scheduled reporting.

## API Keys

To access live government data, create a `.env` file:

```bash
BEA_API_KEY=your_bea_api_key_here
CENSUS_API_KEY=your_census_api_key_here
```

Get API keys from:

- [BEA API](https://apps.bea.gov/API/signup/)
- [Census API](https://www.census.gov/data/developers/data-sets.html)

### Configuration reference

The app validates configuration at startup before rendering the UI. Key environment variables:

- `ENVIRONMENT`: `development` (default), `testing`, or `production`.
- `DEFAULT_YEAR`: Initial year selection when the sidebar loads.
- `CACHE_ENABLED`: Enable/disable filesystem caches (`true`/`false`).
- `CACHE_DIR`: Base directory for cache files (defaults to `.cache`).
- `OBSERVABILITY_SNAPSHOT_DIR`: Directory where observability snapshots are persisted (defaults to `build/observability_snapshots`).
- `OBSERVABILITY_SNAPSHOT_RETENTION_COUNT`: Maximum number of snapshots to retain before pruning oldest archives (`0` disables count-based pruning).
- `OBSERVABILITY_SNAPSHOT_RETENTION_DAYS`: Age threshold (in days) for pruning historical snapshots (`0` disables age-based pruning).
- `OBSERVABILITY_SNAPSHOT_MIN_INTERVAL_SECONDS`: Minimum number of seconds between automatic snapshot captures triggered by the persistence extension.
- `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND`: Remote replication backend identifier (`s3`, `plugin:<name>`, or `off`).
- `OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS`: JSON object handed to replication extensions for backend-specific configuration (e.g., `{"path": "./build/debug-replication"}`).
- `BEA_API_KEY`, `CENSUS_API_KEY`: Required when `ENVIRONMENT=production`.

Launch the app and open the “Configuration summary” expander in the sidebar to review resolved values and warnings.

---

## Using real data (recommended)

1. Get keys:
   - **BEA API Key**: <https://apps.bea.gov/API/signup/index.cfm>
   - **Census API Key** (ASM): <https://api.census.gov/data/key_signup.html>
2. Put them in a `.env` file (see `.env.example`) or paste them into the sidebar at runtime.
3. In the app sidebar, choose **Data → “BEA”** for economy‑wide aggregates or **“Census ASM”** for detailed manufacturing NAICS. Fetch, compute, explore.

### Notes on data mappings

- **BEA** exposes **GDP by Industry** and **Input‑Output** datasets. We request **Gross Output** and **Intermediate Inputs** at annual cadence. BEA industry codes are close to NAICS groupings; we ship a simple `assets/naics_map.csv` for friendly names and a lightweight mapping.
- **Census ASM** provides **Value of Shipments (RCPTOT)**, **Cost of Materials (CSTMTOT)**, **Value Added (VALADD)** for manufacturing (NAICS 31‑33). Data are annual and sometimes suppressed at very fine granularity.

If an API call fails or a series isn’t available, the app will surface a terse error and gracefully fall back.

---

## Bring your own data

Want to avoid APIs entirely or use proprietary data? Go to **Data → “Upload CSV”** and drop in a file with columns:

```
industry_code,industry_name,year,gross_output,materials_cost,intermediate_inputs,value_added,source
```

At minimum, provide: `industry_code`, `industry_name`, `year`, and either:

- `gross_output` + `materials_cost`, **or**
- `gross_output` + `intermediate_inputs` (used as materials proxy).

---

## Testing & quality gates

- `make quality-gate` (or `pytest` + `ruff` + `mypy` individually) should pass before merging.
- Agents rely on type hints; run `mypy` to ensure interface compatibility when editing dataclasses or adapters.
- Streamlit helpers have unit tests in `tests/interfaces/streamlit`; add coverage there when altering UI-facing utilities.

## Troubleshooting

- **API failures** – check the sidebar banner for validation errors. Enable debug logs with `LOG_LEVEL=DEBUG` when running `streamlit run app.py` to see adapter retries.
- **Slow dashboard** – enable caching via `.env` (`CACHE_ENABLED=true`) to persist API responses between sessions.
- **Excel downloads missing** – install `xlsxwriter` (already included in `requirements.txt`) or rely on CSV/JSON outputs if the optional dependency is unavailable.

For architecture deep dives, see [docs/handbook/ARCHITECTURE.md](docs/handbook/ARCHITECTURE.md). For agent schemas and JSON examples, see [docs/AI_INTERFACE.md](docs/AI_INTERFACE.md).

## Export

Use the "Download Results (CSV)" button to export all computed metrics.

---

## Recent Improvements

This application has been significantly enhanced with production-ready features:

### **Robustness & Error Handling**

- **Comprehensive input validation** for all user inputs and data sources
- **Graceful error handling** with clear user feedback instead of crashes
- **API resilience** with retry logic and detailed error differentiation
- **Data validation** at multiple pipeline stages to prevent invalid computations

### **Enhanced User Experience**

- **Interactive Plotly charts** replacing basic visualizations
- **Multi-industry comparisons and benchmarking** with historical trendlines and dataset averages
- **Shareable URLs** so teams can jump straight to the same insights
- **CSV upload validation** with clear schema requirements and error messages
- **Improved deep-dive views** with safe handling of missing data
- **Multi-format exports** (CSV, JSON, Excel) for both full datasets and filtered perspectives

### **Platform Resilience & Observability**

- **BEA API failover and pagination handling** with NAICS enrichment and metadata capture
- **Structured logging with redaction** plus remote shipping hooks and dynamic log-level controls
- **Better sidebar feedback** for data loading and error states

### **Code Quality & Security**

- **Typed configuration loader** with validation and sidebar warnings
- **Deterministic caching** with TTL management and per-test isolation
- **Hardened security utilities** covering uploads, strings, and API keys
- **Retriable HTTP client** with typed errors and exponential backoff
- **Expanded automated tests** spanning config, metrics, normalization, and API clients

### **API Integration**

- **Complete BEA API implementation** (previously stubbed)
- **Enhanced Census ASM client** with better error handling
- **HTTP client improvements** with retry logic and timeout handling

---

## Limitations (don't kid yourself)

- This is a **ratio**, not gospel. High values can reflect IP, safety, regulation, or capital intensity—not “idiocy.”
- Different sources define outputs/inputs differently; read their docs. We annotate the source on each row.
- Retail and services accounting can be weird in national accounts (e.g., margins vs merchandise). Interpret with care.

---

## Project layout

```
.
├── app.py
├── requirements.txt
├── .env.example
├── LICENSE
├── README.md
├── assets/
│   └── naics_map.csv
├── data/
│   └── sample_industries.csv
├── src/
│   ├── __init__.py
│   ├── cache.py
│   ├── config.py
│   ├── metrics.py
│   ├── normalize.py
│   ├── rate_limiter.py
│   ├── security.py
│   ├── types.py
│   ├── utils.py
│   └── sources/
│       ├── bea.py
│       └── census_asm.py
└── tests/
    ├── test_config.py
    ├── test_core.py
    └── test_security.py
```

---

## License

MIT. See `LICENSE`.

---

## Enterprise Features

This application implements production-grade features for reliability, performance, and maintainability:

### 🚀 Performance & Caching

- **File-based caches** for API responses and metric computations with configurable TTLs
- **Atomic writes** to prevent partial cache files and reduce corruption risk
- **Cache statistics helper** for inspecting cache size and entry counts during diagnostics

### 🔒 Security & Rate Limiting

- **API rate limiting** via configurable token buckets per provider
- **Environment-aware defaults** for stricter production limits
- **Upload hygiene** with filename sanitization, file-size enforcement, and CSV content scans
- **API key validation** with length checks and character whitelists
- **String sanitization** to strip dangerous HTML/script patterns
- **Year and numeric validation** before expensive computations

### 📊 Observability

- **Rotating file and console logs** via `src/logging_config.py`
- **API call logging hooks** to trace outbound requests and timings

### ⚙️ Configuration Management

- **Environment Detection**: Automatic production/development/test environment handling
- **Dynamic Settings**: Configurable cache TTL, logging levels, and API limits via environment variables
- **Validation on Startup**: Comprehensive configuration validation with helpful error messages
- **Security-Conscious**: No sensitive data exposure in logs or configuration summaries

### 🏗️ Infrastructure & DevOps

- **Dockerfile** for reproducible local or cloud deployments
- **Development tooling** pinned in `requirements-dev.txt` (black, flake8, mypy, pytest-cov)
- **Type hints** and linting integrated into the codebase

### 🧪 Quality Assurance

- **Pytest suite** covering configuration, normalization, metrics, security, and API clients
- **Mock-based integration tests** for BEA and Census API adapters
- **Type hints** throughout core modules for editor and static analysis support

---

## Architecture Overview

```text
idiot-index-app/
├── app.py                 # Streamlit UI with validation and caching
├── src/
│   ├── cache.py          # Intelligent file-based caching system
│   ├── config.py         # Environment-aware configuration management
│   ├── logging_config.py # Structured logging with performance tracking
│   ├── metrics.py        # Business logic with defensive programming
│   ├── normalize.py      # Data validation and schema normalization
│   ├── rate_limiter.py   # Token bucket rate limiting
│   ├── sources/          # Isolated API client modules
│   │   ├── bea.py       # BEA GDPbyIndustry API client
│   │   └── census_asm.py # Census ASM API client
│   └── utils.py          # HTTP client with retry logic
├── tests/                # Comprehensive test suite
├── Dockerfile           # Containerization with health checks
├── .dockerignore       # Docker build optimization
├── .github/workflows/  # CI/CD pipeline
├── requirements.txt    # Production dependencies
└── requirements-dev.txt # Development tooling
```

Scenario modelling lives in `src/application/scenario_planner.py`, which powers both the Streamlit Scenario Lab and the `scripts/run_scenario.py` CLI. It reuses the normalization and metric pipeline to recompute Idiot Index derivatives after applying percentage shocks to baseline datasets.

### Data Flow Pipeline

```text
User Input → Validation → Caching Check → API Call (Rate Limited) →
Data Processing → Metrics Computation → Caching Storage →
UI Rendering → Logging & Monitoring
```

---

## Configuration Options

Configure the application via environment variables:

```bash
# Environment
ENVIRONMENT=production  # development | production | testing

# API Keys
BEA_API_KEY=your_key
CENSUS_API_KEY=your_key

# Performance
CACHE_ENABLED=true
CACHE_TTL_API=3600      # API cache TTL in seconds
CACHE_TTL_COMPUTATION=1800  # Computation cache TTL

# Rate Limiting (requests per minute)
BEA_RATE_LIMIT=10       # Production: 10, Development: 30
CENSUS_RATE_LIMIT=20    # Production: 20, Development: 50

# Distributed Rate Limiting
RATE_LIMIT_BACKEND=redis              # memory | redis
RATE_LIMIT_REDIS_HOST=redis           # Hostname or IP for Redis
RATE_LIMIT_REDIS_PORT=6379            # Port number
RATE_LIMIT_REDIS_DB=0                 # Logical database index
RATE_LIMIT_REDIS_KEY_PREFIX=idiot-index
RATE_LIMIT_REDIS_TIMEOUT_SECONDS=2.5  # Optional socket timeout
RATE_LIMIT_REDIS_TTL_SECONDS=300      # State expiry horizon in seconds

# Normalisation Overrides
NORMALIZE_DTYPE_OVERRIDES='{"materials_cost": "Int64"}'

# Logging
LOG_LEVEL=INFO          # DEBUG | INFO | WARNING | ERROR | CRITICAL

# Data Validation
MAX_CSV_SIZE_MB=50
DEFAULT_YEAR=2021
```

Enable multi-instance coordination by setting `RATE_LIMIT_BACKEND=redis`; the service will fall back to in-process memory when Redis is unavailable and surface the current mode in the Streamlit sidebar and `/observability/status` (look for `mode: redis-fallback` when Redis is unhealthy). You can also customise dataframe dtypes by supplying a JSON object via `NORMALIZE_DTYPE_OVERRIDES`—use canonical column names (after normalisation) and pandas dtype strings such as `"Int64"` or `"string"`.

---

## API Integration Details

### BEA (Bureau of Economic Analysis)

- **Dataset**: GDPbyIndustry
- **Tables**: Gross Output (Table 1), Intermediate Inputs (Table 2)
- **Rate Limit**: 10 requests/minute (production), 30/minute (development)
- **Cache TTL**: 1 hour
- **Data Range**: 1997-2024

### Census ASM (Annual Survey of Manufactures)

- **Dataset**: Manufacturing statistics
- **Variables**: RCPTOT (shipments), CSTMTOT (materials), VALADD (value added)
- **Rate Limit**: 20 requests/minute (production), 50/minute (development)
- **Cache TTL**: 1 hour
- **Data Range**: 1997-2023

---

## Monitoring & Logs

The application generates structured logs for monitoring:

```text
logs/app.log  # Rotating file logs (DEBUG level)
console       # Console logs (INFO level)
```

Log entries include:

- API call success/failure with timing
- Cache hits/misses
- Performance metrics
- Error details with context
- Configuration validation results

---

## Troubleshooting

- **Port in use**: `streamlit run app.py --server.port 8502`
- **SSL issues** behind proxies: set `REQUESTS_CA_BUNDLE` or disable SSL verification in a pinch (not recommended).
- **Corporate networks** blocking APIs: use the **Upload CSV** path.

---

## Why this exists

You asked for a no‑nonsense tool to interrogate cost structure by industry. This gives you the lever:
pull fresh official stats, compute the ratio, and then challenge the assumptions.

## Repository layout

The repository follows a layered structure with lightweight indexes in each directory:

- [`src/`](src/README.md) – application code organised by adapters, core domain logic, infrastructure, interfaces, and agent wrappers.
- [`tests/`](tests/README.md) – pytest suites mirroring the source layout with coverage for analytics, observability, and agent tooling.
- [`scripts/`](scripts/README.md) – developer and operator automation including quality gates, observability utilities, and scaffolding helpers.
- [`docs/`](docs/README.md) – long-form documentation, execution plans, and handbook references.
- [`extensions/`](extensions/README.md) – manifest-driven plugin catalog used by the ExtensionManager.
- [`data/`](data/README.md) – offline sample dataset powering the demo and regression tests.
- [`assets/`](assets/README.md) – lightweight imagery and UI assets referenced by Streamlit components and docs.
- Executive reports live under [`docs/exec/`](docs/exec/README.md); see handbook/report links from exec plans for archived summaries.

Refer to [`SPEC.md`](SPEC.md) for the canonical requirements snapshot and [`STYLE-GUIDE.md`](STYLE-GUIDE.md) for coding conventions.
