# Repo Intelligence Report

_Last updated: 2025-02-15_

## 1. System Overview

### Domain & User Value
- **Product:** Streamlit dashboard that visualises the “Idiot Index” (gross output ÷ materials cost) for U.S. industries.
- **Primary users:** Analysts exploring industry efficiency, and automation agents that need a programmatic Idiot Index summary.
- **Data sources:**
  - **Bundled sample CSV** under `data/sample_industries.csv` for offline exploration.【F:data/sample_industries.csv†L1-L5】
  - **BEA GDP-by-Industry API** and **Census ASM API** via adapter modules in `src/adapters/` and legacy shims in `src/sources/` for backwards compatibility.【F:src/adapters/bea.py†L1-L40】【F:src/sources/__init__.py†L1-L15】

### Runtime Entrypoints & Interfaces
- **Streamlit UI (`app.py`)** orchestrates configuration loading, sidebar input validation, data fetching, metric computation, and interactive visualisations with download/export helpers.【F:app.py†L1-L120】
- **Agent Toolkit (`agents/`)** exposes `compute_idiot_index_summary` with dataclass schemas for conversational clients; it reuses the same normalization and metrics pipeline.【F:agents/idiot_index.py†L1-L160】
- **No standalone CLI or background jobs.** All long-running operations (API fetch, caching, metrics) run inside Streamlit or agent requests.

### Layered Architecture
- **Core domain (`src/core/`)**: typed configuration, caching, normalization, metrics, security, HTTP utilities, and type definitions.【F:src/core/config.py†L1-L120】【F:src/core/metrics.py†L1-L80】
- **Adapters (`src/adapters/`)**: BEA and Census API clients with retrying HTTP access, caching, and data shaping; exceptions like `BEAClientError` model remote failures.【F:src/adapters/bea.py†L1-L160】【F:src/adapters/census_asm.py†L1-L120】
- **Infrastructure (`src/infrastructure/`)**: logging configuration and rate limiter utilities for cross-cutting concerns.【F:src/infrastructure/logging_config.py†L1-L160】【F:src/infrastructure/rate_limiter.py†L1-L120】
- **Interfaces (`src/interfaces/streamlit/`)**: UI components and helpers used by `app.py`; legacy aliases remain under `src/ui/` for downstream import stability.【F:src/interfaces/streamlit/components.py†L1-L120】【F:src/ui/__init__.py†L1-L3】
- **Agents (`agents/`)**: dataclasses, tool registry, and integration helper functions for automation clients.【F:agents/toolkit.py†L1-L120】
- **Tests (`tests/`)**: pytest suite covering configuration, adapters, logging, security, UI helpers, and agent behaviours.【F:tests/test_core.py†L1-L160】【F:tests/test_logging.py†L1-L120】

### Data Flow
```
User selects data source → `app.py` validates sidebar inputs → adapters fetch data (with caching + rate limiting) → `normalize_columns` cleans schema → `compute_metrics` derives Idiot Index and value-added metrics → UI helpers format tables/charts → exports/logging handled by infrastructure modules.
```
- Caching: `Cache` in `src/core/cache.py` provides TTL-based filesystem caching used by adapters and metrics.【F:src/core/cache.py†L1-L120】
- Security: `SecurityUtils` validates file uploads, sanitizes strings, and enforces CSV hygiene for both UI and agents.【F:src/core/security.py†L1-L160】

### Observability & Config
- Logging configured via `src/infrastructure/logging_config.py`, supporting JSON/console handlers, redaction, and dynamic levels.【F:src/infrastructure/logging_config.py†L1-L160】
- Configuration loaded by `load_config` with validation and environment detection; validation surfaces warnings/errors into the Streamlit sidebar.【F:src/core/config.py†L120-L240】【F:app.py†L26-L60】

## 2. Tech Stack & Dependency Map

### Languages & Frameworks
- **Python 3.11** (typed, dataclasses, `pandas`, `requests`, `streamlit`, `plotly`).
- Tests with **pytest** + **pytest-cov**; lint/type tools include `flake8`, `black`, and `mypy` (not yet enforced via tooling config files).【F:requirements.txt†L1-L7】【F:requirements-dev.txt†L1-L8】
- Packaging via requirements files; no Poetry/Pipenv.

### Internal Module Graph (simplified)
```
app.py
├─ src.adapters (BEA/Census)
│   ├─ src.core.cache / src.core.normalize / src.core.utils
│   └─ src.infrastructure.rate_limiter
├─ src.core (config, metrics, normalize, security, cache, utils)
├─ src.interfaces.streamlit (components/helpers)
└─ src.infrastructure.logging_config

agents/
└─ src.adapters + src.core + src.infrastructure
```
- Backwards-compatibility shims under `src/` (`config.py`, `cache.py`, `normalize.py`, etc.) re-export the new layered modules; these increase surface area without adding functionality.【F:src/config.py†L1-L2】【F:src/cache.py†L1-L2】

### Third-Party Services
- **BEA API** (GDP-by-Industry / Input-Output tables) using API key with optional version + host overrides.【F:src/adapters/bea.py†L40-L120】
- **Census ASM API** (manufacturing data) with API key requirement.【F:src/adapters/census_asm.py†L1-L100】
- No databases; persistent state limited to filesystem caches and user downloads.

### Tooling & Operations
- Docker image based on `python:3.11-slim`, installs only runtime requirements; health check hits Streamlit endpoint but lacks curl dependency by default (curl is missing).【F:Dockerfile†L1-L28】
- GitHub Actions workflow runs lint (flake8), mypy (with `--ignore-missing-imports`), pytest with coverage, and uploads to Codecov.【F:.github/workflows/ci.yml†L1-L44】
- `.env.example` documents required environment variables; config loader uses `python-dotenv` to load `.env` automatically.【F:.env.example†L1-L8】【F:src/core/config.py†L12-L30】

## 3. Code Health Findings

### Hotspots (by size/complexity)
1. `src/interfaces/streamlit/components.py` (477 LOC) – dense mix of UI rendering + CSS string literals.【F:src/interfaces/streamlit/components.py†L1-L120】
2. `src/core/config.py` (360 LOC) – complex parsing/validation logic tightly coupled to environment variables.【F:src/core/config.py†L1-L160】
3. `src/adapters/bea.py` (332 LOC) – intricate pagination, caching, and metadata handling; high branching risk.【F:src/adapters/bea.py†L1-L160】
4. `app.py` (≈300 LOC) – monolithic orchestrator mixing state management, data fetching, and visualization orchestration.【F:app.py†L1-L200】

### Potential Dead/Legacy Code
- Compatibility wrappers in `src/` (`config.py`, `cache.py`, `normalize.py`, `utils.py`, `logging_config.py`, `ui/`, `sources/`) merely re-export the layered modules. They may be retired once downstream imports migrate, but removing them risks breaking unknown consumers.【F:src/normalize.py†L1-L2】【F:src/ui/__init__.py†L1-L3】
- `REPORTS/` contains historical documents; confirm whether still needed or can be archived externally.【F:REPORTS/000_CONTEXT.md†L1-L20】

### Risk Areas
- **Configuration**: `load_config` executes at import time (via `APP_CONFIG = load_config()` in `app.py`), pulling environment variables early; this complicates testing and dynamic configuration.【F:app.py†L26-L34】
- **Caching**: Filesystem cache lacks eviction strategy beyond TTL; concurrency safety relies on file locks but limited coverage for multi-process scenarios.【F:src/core/cache.py†L60-L140】
- **API keys**: Validation ensures presence and format but there is no runtime secrets scanning; `.env` handling may load values automatically in production unexpectedly.【F:src/core/security.py†L1-L160】
- **Docker healthcheck** uses `curl` but base image does not install it; health command will fail out of the box.【F:Dockerfile†L18-L28】
- **CI**: mypy runs with `--ignore-missing-imports`, reducing type-safety; there is no commitlint/format enforcement.

## 4. Testing & Quality
- Pytest suite includes config, core logic, adapters (with mocks), logging, security, UI helpers, and agent flows.【F:tests/test_config.py†L1-L160】【F:tests/test_agents.py†L1-L160】
- Coverage XML generated but no badge/report tracked; no tests for Streamlit layout or front-end snapshotting.
- No pre-commit hooks; developers rely on manual commands described in README.【F:README.md†L60-L104】

## 5. Security & Compliance Posture
- Security utilities sanitize uploads and strings, but there is no automated secret scanning or dependency audit.
- Dependencies pinned by exact version; lacks lockfile or SBOM.
- No CODEOWNERS, SECURITY policy, or contribution guidelines beyond README; governance docs missing.

## 6. Quick Wins & Top Opportunities (ROI Ranked)
1. **Fix Docker healthcheck dependency** – add `curl`/`wget` or switch to Python-based health script. Low effort, prevents false negatives. *(Reliability, DevOps)*
2. **Introduce pre-commit with black, ruff, mypy, commitlint** – standardises DX, reduces drift. *(DX, Testing)*
3. **Tighten mypy (no `--ignore-missing-imports`) and enable `strict` package config** – catches integration issues early. *(Testing, Reliability)*
4. **Modularise `app.py` state management into dedicated controller module** – increases maintainability. *(DX, Reliability)*
5. **Document architecture & onboarding in updated README/CONTRIBUTING** – reduces ramp-up time. *(Docs)*
6. **Add SBOM + dependency audit in CI (Syft/Trivy)** – improves supply-chain visibility. *(Security)*
7. **Adopt Renovate/Dependabot with policies** – ensures dependency freshness. *(Security, Reliability)*
8. **Add structured logging & metrics emission to adapters** – enhances observability. *(Reliability, Observability)*
9. **Implement integration tests for BEA/Census adapters using recorded fixtures** – protects against API schema drift. *(Testing)*
10. **Retire legacy re-export modules behind feature flag** – simplifies namespace once downstream confirmed. *(DX)*

---
This report should be updated as modernization work progresses to track new risks, architecture shifts, and test coverage.
