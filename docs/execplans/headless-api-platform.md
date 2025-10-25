# Headless Idiot Index API Platform

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Maintain this document in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

The dashboard already serves interactive analysts, but automation teams and external tools have no supported way to programmatically compute Idiot Index metrics or run Scenario Lab adjustments. This plan delivers a fully supported headless API so downstream systems can evaluate industries, orchestrate resilience simulations, and download machine-friendly payloads without screen scraping Streamlit. We will add a FastAPI service exposing health checks, evaluation endpoints, and scenario planning backed by the existing application services. The outcome is a production-ready REST surface, CLI bootstrap, and documentation for deployers.

## Progress

- [x] (2025-02-18 10:00Z) Captured current repository state and drafted the initial ExecPlan.
- [x] (2025-02-18 10:35Z) Implemented API schemas, dataframe converters, and validation helpers for evaluation/scenario payloads.
- [x] (2025-02-18 11:10Z) Added FastAPI application, dependency wiring, and version helper for headless routes.
- [x] (2025-02-18 11:40Z) Added CLI launcher, Makefile target, and Docker dual-mode entrypoint for API deployments.
- [x] (2025-02-18 12:05Z) Added FastAPI TestClient coverage for health/evaluate/scenario endpoints; local pytest run blocked by missing FastAPI dependency due to network restrictions.
- [x] (2025-02-18 12:30Z) Documented API usage, Docker dual-mode, and workflow updates; captured pytest failure linked to dependency installation restrictions.

## Surprises & Discoveries

- Observation: The execution environment blocks outbound pip installs (403 via proxy), preventing FastAPI from being installed during validation.
  Evidence: `pip install -r requirements.txt` failed with `ProxyError` and `No matching distribution found for fastapi==0.115.2` despite the dependency being valid upstream.

## Decision Log

- Decision: Extended `IdiotIndexService.evaluate` to accept an optional `MetricConfig` so headless clients can disable caching without impacting UI defaults.
  Rationale: The API needs per-request cache control when serving inline datasets, and the application service is the central orchestrator reused across entrypoints.
  Date/Author: 2025-02-18 / gpt-5-codex
- Decision: Docker image now accepts `APP_MODE` to choose between Streamlit and API entrypoints, with shared prefetch logic for parity.
  Rationale: Operators can run a single image for both dashboard and headless deployments without diverging instructions.
  Date/Author: 2025-02-18 / gpt-5-codex

## Outcomes & Retrospective

- Delivered a FastAPI surface with typed schemas, dependency wiring, and CLI/Docker integration so automation clients can reuse Idiot Index and Scenario Lab computations.
- Added comprehensive docs covering API usage, health checks, and dual-mode container deployment. Tests covering the new endpoints were authored, though execution in this environment is blocked until FastAPI wheels can be installed.

## Context and Orientation

The repository layers relevant to a headless API are:
- `src/application/idiot_index_service.py` orchestrates dataset acquisition, metric computation, and leaderboard derivation via `evaluate_idiot_index`.
- `src/application/scenario_planner.py` computes baseline/scenario metrics and deltas for Scenario Lab adjustments.
- `src/core/metrics.py` exposes `compute_metrics` and `MetricConfig`, which we will reuse to ensure consistent calculations.
- `app.py` currently hosts Streamlit UI bootstrapping; no existing HTTP API exists.
- `scripts/run_scenario.py` demonstrates CLI usage of the Scenario Planner and can inform JSON payloads.
- Tests live under `tests/` and include coverage for application services, scripts, and UI helpers. No API tests exist today.

We will introduce a new `src/interfaces/api` package containing FastAPI app, dependency wiring, and Pydantic schemas. Supporting infrastructure (CLI entrypoint, Makefile target, Docker docs) will ensure the service is runnable outside Streamlit.

## Plan of Work

1. **API Schemas & Serialisation**
   - Create `src/interfaces/api/schemas.py` defining Pydantic models for requests (`EvaluateRequest`, `ScenarioRequest`, `ScenarioAdjustmentModel`) and responses (`EvaluateResponse`, `LeaderboardEntry`, `ScenarioResponse`, etc.). Ensure conversion between pandas DataFrames and JSON-friendly structures with rounding handled by existing formatters.
   - Add helpers to convert `IdiotIndexSummary` and `ScenarioResult` into response models, capturing metadata, leaderboard, summaries, and dataset records.
2. **FastAPI Application Module**
   - Add `src/interfaces/api/dependencies.py` to wire `IdiotIndexService` and `ScenarioPlanner` instances, reading configuration via environment when needed.
   - Implement `src/interfaces/api/app.py` exposing FastAPI app with routes:
     - `GET /health` returning service status and version info.
     - `GET /meta/sources` listing available `DataSource` values.
     - `POST /evaluate` accepting request payload, invoking `evaluate_idiot_index`, optionally accepting inline dataset records, and returning computed metrics + leaderboard.
     - `POST /scenario` accepting base dataset + adjustments, running `ScenarioPlanner`, and returning baseline/scenario/delta summaries.
   - Ensure consistent error handling (validation, ValueError mapping) with structured error responses.
3. **Runtime Entrypoints & Tooling**
   - Create `scripts/run_api.py` to launch the service with environment-driven host/port for local/dev use. In restricted environments fall back to Python's built-in WSGI server instead of `uvicorn`.
   - Add Makefile target `make api` to run the FastAPI-compatible service, and update Dockerfile CMD logic to optionally run API instead of Streamlit via env toggle.
   - Where third-party dependencies cannot be fetched, provide lightweight in-repo shims mirroring the required FastAPI/Pydantic features so tests remain hermetic.
4. **Testing & Validation**
   - Add `tests/test_api.py` using FastAPI `TestClient` verifying:
     - `/health` returns status.
     - `/meta/sources` lists enumeration.
     - `/evaluate` handles sample data, optional search/top_n, inline dataset validation errors.
     - `/scenario` processes adjustments, returns expected delta metrics.
     - Error cases (missing dataset, invalid adjustments) map to 400 responses.
   - Mock BEA/Census fetchers where necessary to avoid external calls, leveraging sample data fixtures.
5. **Documentation & Quality Gate**
   - Update `README.md` and `docs/API_REFERENCE.md` with API usage instructions, authentication expectations, and sample payloads.
   - Add new guide `docs/API_HEADLESS.md` outlining deployment, environment variables, and example curl invocations.
   - Document CLI/Makefile usage in `docs/WORKFLOWS_DATA_REFRESH.md` or new doc if appropriate.
   - Run `pytest` (and any targeted lint/type checks if applicable) and capture transcripts in the ExecPlan `Progress`/`Outcomes`.

## Concrete Steps

- Edit/add files per Plan of Work using standard git workflow.
- After implementing code and tests, run from repository root:
    - `pytest`
    - Optionally `make check` if runtime permits.
- Record outputs in this plan.

## Validation and Acceptance

- `pytest` passes with new `tests/test_api.py` verifying REST behaviour.
- Manual curl (documented) demonstrates `GET /health` returning JSON `{ "status": "ok" }` and `POST /evaluate` returning metrics for the sample dataset.
- Dockerfile/Makefile instructions allow launching the API service locally.

## Idempotence and Recovery

- FastAPI app initialisation is side-effect free; repeated runs reuse configuration.
- CLI script and Makefile target invoke the bundled server and can be rerun safely.
- If configuration is missing (e.g., API keys), endpoints respond with 400 errors and instructions documented.

## Artifacts and Notes

- Capture example response payloads for `/evaluate` and `/scenario` in the documentation.
- Record final `pytest` transcript in `Progress` once green.

## Interfaces and Dependencies

- Runtime dependencies: prefer native FastAPI/uvicorn when available; otherwise rely on the bundled shims to avoid network coupling.
- Public API surfaces: HTTP endpoints described above returning JSON objects. Internal modules `IdiotIndexService` and `ScenarioPlanner` remain the source of truth.
- Scripts/CLI: `scripts/run_api.py` exposes CLI for launching the headless API; integrate with Makefile.
