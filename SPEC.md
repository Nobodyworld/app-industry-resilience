# Idiot Index Specification

_Last updated: 2025-10-31_

The Idiot Index project delivers a Streamlit dashboard and headless API for analysing industry cost efficiency. This specification captures the canonical requirements for maintaining and extending the repository after the restructuring.

## 1. Architecture Overview

- **Presentation**: `app.py` (Streamlit UI) and the FastAPI-compatible service under `src/interfaces/api`.
- **Domain Services**: `src/application/idiot_index_service.py` orchestrates data retrieval, normalisation, analytics, and leaderboard generation.
- **Data Access**: Adapters in `src/adapters/` provide BEA, Census ASM, and sample dataset connectors with caching via `src/cache.py`.
- **Analytics**: `src/core/analytics` offers composite health scoring, resilience metrics, and cohort aggregations consumed by both UI and API layers.
- **Observability**: Extensions under `src/extensions/` plus infrastructure modules handle metrics, tracing, and snapshot replication.
- **Agent Surface**: `src/agents/` exposes curated tooling for automation clients, delegating to the application layer while enforcing schema metadata.

Refer to [`docs/handbook/ARCHITECTURE.md`](docs/handbook/ARCHITECTURE.md) for diagrams and rationale.

## 2. Supported Workflows

| Workflow | Entry Point | Notes |
| --- | --- | --- |
| Streamlit dashboard | `streamlit run app.py` | Uses cached sample data by default; BEA and ASM integrations activate when API keys are supplied. |
| Headless API | `make api` or `python scripts/run_api.py` | Serves a minimal FastAPI-compatible app on port 9000 with health and observability endpoints. |
| Scenario planning CLI | `python scripts/run_scenario.py` | Applies shocks to current datasets and emits summary tables. |
| Observability snapshotting | `python scripts/observability_snapshot.py` | Persists local and remote snapshots with optional replication extensions. |
| Agent integrations | `src/agents/` | Provides dataclass schemas and tool metadata for conversational agents. |

## 3. Quality Gates

All contributions must pass `make quality-gate`, which executes:

1. Formatting checks (Black in check mode).
2. Linting (Ruff).
3. Type checking (mypy).
4. Pytest with coverage enforcement.
5. Security scans (`pip-audit` and `detect-secrets`).

Use `make format`, `make lint`, `make typecheck`, or `make test` for targeted debugging.

## 4. Configuration

- Configuration values are centralised in `src/config.py` with environment variable overrides. Key settings include API credentials, rate limiter backend, observability replication targets, and dtype overrides.
- `.env` files are not committed; developers should export variables locally when required.
- JSON/TOML configuration files:
  - `extensions/manifest.json` – declares available extensions.
  - `MASTER-VERSIONS.json` – records dependency alignment snapshots.
  - `pyproject.toml` – Python packaging metadata.
  - `codex_chain.json` – automation hints for Codex agents.

Validate changes to these files by loading them in tests or via `python -m json.tool <file>` / `python -m tomllib <file>`.

## 5. Repository Layout

Each major directory now contains a `README.md` describing its scope:

- [`src/`](src/README.md) – source code, organised by layer.
- [`tests/`](tests/README.md) – pytest suites.
- [`scripts/`](scripts/README.md) – automation helpers.
- [`docs/`](docs/README.md) – documentation hub.
- [`extensions/`](extensions/README.md) – manifest-driven plugins.
- [`data/`](data/README.md) – sample datasets for offline usage.
- [`assets/`](assets/README.md) – static assets for UI/docs.
- [`REPORTS/`](REPORTS/README.md) – archived stewardship reports.

## 6. Documentation

- The root [`README.md`](README.md) provides onboarding, command references, and environment configuration tips.
- [`docs/handbook/`](docs/handbook/README.md) hosts canonical guides for architecture, automation, releases, and security.
- [`docs/execplans/`](docs/execplans/README.md) archives historical execution plans, including the repository cleanup and validation pass described in the latest entry of [`CHANGELOG.md`](CHANGELOG.md).
- [`docs/exec/`](docs/exec/README.md) captures stakeholder-facing summaries and status reports.

Keep these documents up to date whenever workflows or architecture change.

## 7. Testing Strategy

- Unit and integration tests live under `tests/` and mirror the structure of `src/`.
- Agent tooling tests ensure schemas stay in sync with the application layer.
- Observability and replication tests rely on local stubs; avoid calling real cloud APIs in CI.
- Coverage reports are generated automatically during `make quality-gate`; minimum thresholds are enforced to catch regressions.

## 8. Extension Ecosystem

- New connectors, instrumentation modules, or replication backends must be registered in `extensions/manifest.json` and implement the appropriate contract under `src/extensions/`.
- Use `python scripts/scaffold_extension.py --name <snake_case_name>` to bootstrap new modules.
- Verify catalog output with `make extensions-catalog` and `make connectors-catalog`.

## 9. Release & Reporting Requirements

- Update [`CHANGELOG.md`](CHANGELOG.md) for every meaningful change.
- Track task completion in [`TASKLIST.md`](TASKLIST.md) using the provided format.
- Provide execution context in [`docs/execplans/`](docs/execplans/README.md) when undertaking significant refactors.
- Adhere to coding conventions in [`STYLE-GUIDE.md`](STYLE-GUIDE.md) and document any deviations in an ADR or the changelog.

This specification should be treated as the authoritative reference for repository expectations. Revisit and update it as architecture or processes evolve.
