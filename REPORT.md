# Repo Intelligence Report

_Last updated: 2025-10-20_

## 1. Product & Architecture Snapshot

### Domain & Value Proposition
- **Purpose:** Idiot Index quantifies the materials efficiency of U.S. industries by comparing gross output to materials and intermediate input spend. Analysts and automation agents explore historical trends, benchmark peers, and export curated datasets.【F:app.py†L1-L136】【F:agents/idiot_index.py†L1-L160】
- **Core behaviours:**
  1. Collect source data from BEA and Census ASM APIs or user uploads.【F:app.py†L41-L110】【F:src/adapters/__init__.py†L1-L40】
  2. Normalise datasets, compute Idiot Index metrics, and prepare trend/comparison tables.【F:src/core/normalize.py†L1-L200】【F:src/core/metrics.py†L1-L200】
  3. Present insights via Streamlit (charts, benchmarks, downloads) and agent-friendly toolkits.【F:src/interfaces/streamlit/components.py†L1-L200】【F:src/interfaces/streamlit/helpers.py†L1-L200】【F:agents/toolkit.py†L1-L160】

### Execution Surfaces
| Surface | Entry Point | Notes |
| --- | --- | --- |
| Interactive UI | `app.py` | Streamlit app orchestrating config validation, data acquisition, stateful UI, downloads, and caching.【F:app.py†L12-L220】 |
| Automation toolkit | `agents/idiot_index.py` | Dataclasses + helper functions for LangChain/OpenAI agents to compute Idiot Index scenarios headlessly.【F:agents/idiot_index.py†L1-L160】 |
| Developer CLI | `Makefile` targets | `make setup`, `make check`, `make security`, and `make sbom` provide one-command automation for contributors and CI.【F:Makefile†L1-L120】 |

### Deployable Footprint & Ops Hooks
- **Container:** Single-stage Dockerfile on `python:3.11-slim`; installs runtime deps, copies repo, runs as non-root, and defines a `curl` health check (fails today because `curl` is not installed).【F:Dockerfile†L1-L30】
- **CI/CD:** GitHub Actions `ci.yml` fan-out for Python 3.9–3.11 running `make check` (format, lint, types, tests) plus a security job executing gitleaks, `make security`, and SBOM generation.【F:.github/workflows/ci.yml†L1-L80】
- **Local automation:** `scripts/run_quality_checks.py` and `scripts/generate_sbom.py` mirror CI behaviour for offline/air-gapped workflows.【F:scripts/run_quality_checks.py†L1-L200】【F:scripts/generate_sbom.py†L1-L160】

### Data & Control Flow
```
User/Agent request
  ↓
app.py initialises configuration and sidebar state【F:app.py†L16-L140】
  ↓
Data source chosen (sample CSV, upload, BEA, Census)【F:app.py†L41-L115】
  ↓                                ↘
Adapters fetch API payloads with retries/rate limits【F:src/adapters/bea.py†L1-L200】【F:src/adapters/census_asm.py†L1-L200】
  ↓                                ↙
Core layer normalises columns, computes Idiot Index metrics, enforces security policies【F:src/core/normalize.py†L1-L200】【F:src/core/metrics.py†L1-L200】【F:src/core/security.py†L1-L200】
  ↓
Interfaces format tables, charts, and downloads for Streamlit components【F:src/interfaces/streamlit/helpers.py†L1-L200】【F:src/interfaces/streamlit/components.py†L1-L200】
  ↓
Outputs rendered in UI or returned to agent callers
```
- **Caching:** `src/core/cache.py` provides disk-backed TTL caches for API responses and computed tables; adapters opt-in to reuse results.【F:src/core/cache.py†L1-L140】【F:src/adapters/bea.py†L210-L320】
- **Rate limiting:** Shared `RateLimiter` throttles outbound HTTP calls to respect vendor policies.【F:src/infrastructure/rate_limiter.py†L1-L200】

### Configuration & Secrets
- `src/core/config.py` lazily parses environment variables (dotenv support) into a strongly typed `AppConfig`. `app.py` currently loads configuration at import time, which couples runtime state to process start-up and complicates tests that need custom env overrides.【F:src/core/config.py†L1-L200】【F:app.py†L30-L40】
- Key knobs: environment (`ENVIRONMENT`), logging level, default analysis year, API keys, API base URLs, cache toggle/TTLs, CSV upload policy (size/year ranges).【F:src/core/config.py†L70-L190】
- Security policies (max CSV size, allowed columns) flow through `SecurityUtils` for both uploads and API usage.【F:src/core/security.py†L1-L200】

## 2. Module & Dependency Map

### Layered Modules
| Layer | Directory | Responsibilities | Notable Dependencies |
| --- | --- | --- | --- |
| Interfaces | `src/interfaces/streamlit/` | UI orchestration, sidebar, charts, downloads, query param encoding, style injection. | Streamlit, Plotly.【F:src/interfaces/streamlit/components.py†L1-L240】【F:src/interfaces/streamlit/helpers.py†L1-L220】 |
| Application Core | `src/core/` | Config, caching, normalization, Idiot Index metrics, security validation, domain types/utilities. | pandas, dataclasses, dotenv.【F:src/core/__init__.py†L1-L40】【F:src/core/metrics.py†L1-L200】 |
| Adapters | `src/adapters/` | BEA and Census API clients, response parsing, caching integration, request payload builders. | requests, `RateLimiter`, `Cache`.【F:src/adapters/bea.py†L1-L320】【F:src/adapters/census_asm.py†L1-L320】 |
| Infrastructure | `src/infrastructure/` & `src/logging_config.py` | Structured logging defaults, CLI to configure logging handlers. | logging, JSON, os.【F:src/infrastructure/logging_config.py†L1-L180】【F:src/logging_config.py†L1-L200】 |
| Legacy Shims | `src/{cache,config,metrics,normalize,security}.py`, `src/ui/`, `src/sources/` | Re-export layered modules for backwards compatibility with older import paths. | Internal modules only.【F:src/cache.py†L1-L20】【F:src/ui/__init__.py†L1-L20】 |
| Agents | `agents/` | Agent toolkit for conversational automation (tools, schemas, prompts). | Core + adapters.【F:agents/toolkit.py†L1-L200】 |

### External Dependencies & Hotspots
- **Runtime dependencies:** Streamlit, pandas, Plotly, requests, python-dotenv, pytest (bundled for Streamlit scripting needs).【F:requirements.txt†L1-L7】
- **Dev tooling:** Black, Ruff, mypy, pytest-cov, pre-commit, Codespell, Commitizen, detect-secrets, pip-audit, types-requests.【F:requirements-dev.txt†L1-L13】
- **High-churn files:** `app.py` (480 LOC), `src/interfaces/streamlit/components.py` (477), `src/core/config.py` (360), `src/adapters/bea.py` (332). These monolithic modules increase regression risk when editing UI or configuration flows.【F:app.py†L1-L200】【F:src/interfaces/streamlit/components.py†L1-L200】【F:src/core/config.py†L1-L200】【F:src/adapters/bea.py†L1-L200】
- **Duplicated tooling:** `scripts/run_quality_checks.py` replicates Makefile logic to support environments without `pre-commit`, leading to dual maintenance burden.【F:scripts/run_quality_checks.py†L1-L200】

## 3. Quality, Observability, and Security Posture

### Testing & Coverage
- Pytest suite covers configuration parsing, cache behaviour, adapter request factories, logging redaction, security validators, and Streamlit helper utilities.【F:tests/test_config.py†L1-L220】【F:tests/test_security.py†L1-L200】【F:tests/test_ui_helpers.py†L1-L200】
- Coverage is generated via `pytest --cov` in `make check`, but no minimum threshold or badge enforcement exists; UI rendering lacks integration or snapshot validation.【F:Makefile†L33-L80】

### Static Analysis & Typing
- Formatting (Black), linting (Ruff), typing (mypy) unified through the Makefile and CI. Mypy currently runs in non-strict mode with `ignore_missing_imports`, so incorrect assumptions around pandas/Streamlit remain unchecked.【F:pyproject.toml†L1-L80】【F:Makefile†L1-L80】
- `pre-commit` orchestrates Black, Ruff, Codespell, detect-secrets, pip-audit, and commit message linting; fallback Python script ensures parity without the `pre-commit` binary.【F:.pre-commit-config.yaml†L1-L200】【F:scripts/run_quality_checks.py†L1-L200】

### Observability & Operations
- Logging is centralised in `src/infrastructure/logging_config.py`, enabling JSON/plain outputs, redaction, rotation, and integration with the config subsystem.【F:src/infrastructure/logging_config.py†L1-L180】
- No metrics or tracing are emitted; Streamlit UI relies on log statements only. There is no readiness endpoint beyond the Docker health check, and health currently fails because `curl` is absent in the runtime image.【F:Dockerfile†L1-L30】

### Security & Supply Chain
- Upload validation enforces file size, allowed extensions, and column schema; CSV contents are sanity-checked before use.【F:src/core/security.py†L1-L200】
- `make security` runs pip-audit and detect-secrets (with fallback scanning when hooks are unavailable). CI adds gitleaks and SBOM generation via `make sbom`.【F:Makefile†L81-L130】【F:.github/workflows/ci.yml†L40-L80】
- Missing pieces: Renovate/Dependabot automation, SLSA provenance/signing, container hardening (multi-stage build, minimal packages), and documented vulnerability disclosure response timeline in `SECURITY.md`.

## 4. Risks & Constraints
1. **Configuration coupling:** `app.py` loads and validates configuration at import time, making environment overrides in tests brittle and preventing lazy secrets loading.【F:app.py†L30-L50】
2. **UI monolith:** Streamlit module mixes state management, data orchestration, and rendering, inflating surface area per change and impeding reuse.【F:app.py†L1-L220】【F:src/interfaces/streamlit/components.py†L1-L200】
3. **Adapter resilience:** External API integrations depend on runtime environment variables with limited circuit breaking; retries/backoff are inline without observability hooks.【F:src/adapters/bea.py†L1-L320】
4. **Container health:** Health check relies on `curl` which is not installed, causing false negatives in container orchestration systems.【F:Dockerfile†L1-L30】
5. **Governance drift:** Governance docs exist but do not yet reflect the modernization roadmap, release automation strategy, or dependency update policy (tracked in PLAN Milestone 1).

## 5. High-ROI Opportunities (90-Day Horizon)
| # | Opportunity | Impact | Effort | Tags | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | Fix Docker health check by installing `curl` or switching to a Python probe script packaged with the app. | High | Small | reliability, DX | Prevents immediate health probe failures and unblocks container adoption.【F:Dockerfile†L1-L30】 |
| 2 | Enable `mypy --strict` with targeted suppressions/stubs for Streamlit and pandas. | High | Medium | testing, DX | Tighten regressions detection ahead of architectural refactors.【F:pyproject.toml†L1-L80】 |
| 3 | Decompose `app.py` into controller/service modules with feature-flagged rollout. | High | Large | DX, reliability | Unlocks unit testing for orchestration logic and reduces Streamlit monolith risk.【F:app.py†L1-L220】 |
| 4 | Record adapter interactions (pytest-recording/VCR) and validate cache/rate limit paths offline. | Medium | Medium | testing, reliability | Current tests exercise only the sample dataset, leaving BEA/Census flows unverified offline.【F:tests/test_agents.py†L14-L30】 |
| 5 | Introduce Renovate with dependency grouping and CODEOWNERS routing. | Medium | Small | security, reliability | Keeps runtime + tooling fresh with manageable review flow. |
| 6 | Add OpenTelemetry instrumentation for adapter latency and cache hits behind an env-flag. | Medium | Medium | observability, performance | Enables dashboards and regression detection. |
| 7 | Replace legacy shim modules with warnings + migration guide, reducing duplicate imports. | Medium | Medium | DX, reliability | Shrinks surface area once dependent integrations are audited.【F:src/cache.py†L1-L20】【F:src/ui/__init__.py†L1-L20】 |
| 8 | Harden configuration via Pydantic `BaseSettings`, central schema, and explicit override hooks for tests. | High | Medium | security, DX | Eliminates manual parsing and ensures safe defaults.【F:src/core/config.py†L1-L200】 |
| 9 | Enforce coverage thresholds and publish reports (Codecov/pytest-html) in CI. | Medium | Small | testing, reliability | Raises feedback quality on PRs.【F:.github/workflows/ci.yml†L1-L80】 |
| 10 | Expand onboarding docs (First Hour Guide, troubleshooting) aligned with new tooling defaults. | Medium | Small | docs, DX | Ensures engineers can ship within the “5-minute” directive. |

The opportunities map directly to Milestone tasks in `PLAN.md` and will gain dedicated ExecPlans as work initiates.
