# Industry Resilience Specification

_Last updated: 2026-08-10_

The Industry Resilience project delivers a Streamlit dashboard and headless API for analysing industry cost structure and comparative resilience signals. This specification captures the canonical requirements for maintaining and extending the repository.

## 1. Architecture Overview

- **Presentation**: `app.py` (Streamlit UI) and the FastAPI-compatible service under `src/interfaces/api`.
- **Domain Services**: `src/application/idiot_index_service.py` orchestrates data retrieval, normalisation, analytics, and leaderboard generation.
- **Data Access**: Adapters in `src/adapters/` provide BEA, Census ASM, Census AIES, bundled sample, and public-data readiness paths with caching via `src/core/cache.py`.
- **Analytics and Provenance**: `src/core/analytics` provides heuristic scoring and cohort aggregation; `src/core/lineage.py` provides the typed, redacted provenance contract used by adapters, caches, scenarios, API responses, Streamlit, and exports.
- **Industry Pulse**: `src/core/industry_pulse.py` owns the reviewed mapping/domain contract;
  `src/application/industry_pulse_service.py` loads the verified offline snapshot and calculates
  exact-calendar changes/freshness; signal provenance remains distinct from annual lineage.
- **Industry Momentum**: `src/core/industry_momentum.py` composes the eight PPI mappings with eight
  CES and 22 G.17 mappings. Its service exposes exact/broader scope, exact-calendar changes,
  per-family degradation, freshness, and allowlisted provenance without changing annual analytics.
- **Observability**: Extensions under `src/extensions/` plus infrastructure modules handle metrics, tracing, and snapshot replication.
- **Agent Surface**: `src/agents/` exposes curated tooling for automation clients, delegating to the application layer while enforcing schema metadata.

Refer to [`ARCHITECTURE_OVERVIEW.md`](ARCHITECTURE_OVERVIEW.md) for diagrams and rationale.

## 2. Supported Workflows

| Workflow | Entry Point | Notes |
| --- | --- | --- |
| Streamlit dashboard | `streamlit run app.py` | Uses bundled sample data by default, supports an official AIES snapshot and validated uploads, exposes typed Data provenance, and provides a fifth snapshot-backed Industry Momentum tab. |
| Headless API | `make api` or `python src/scripts/run_api.py` | Serves canonical `/v1` analytical/context routes, deprecated compatibility aliases only for older contracts, typed lineage/provenance, health, and observability endpoints on port 9000. |
| Scenario planning CLI | `python src/scripts/run_scenario.py` | Applies shocks to current datasets and emits summary tables. |
| Observability snapshotting | `python src/scripts/observability_snapshot.py` | Persists local and remote snapshots with optional replication extensions. |
| Agent integrations | `src/agents/` | Provides dataclass schemas and tool metadata for conversational agents. |


## 3. API, Lineage, and Export Contracts

- Canonical consumer routes use the `/v1` prefix. Deprecated unversioned aliases remain compatibility surfaces during the documented migration window.
- Evaluation, health analytics, and scenario responses expose typed lineage while retaining generic metadata for v1 compatibility.
- Source boundaries identify bundled sample, live official providers, official snapshots, API-inline records, uploaded files, and cache retrieval without copying unrestricted metadata.
- Uploaded data uses `source=user-upload`, `source_kind=uploaded_file`, and `dataset_id=user-upload`; filenames and private paths are prohibited.
- Cache hits preserve original source identity, timestamps, and transformations while changing only retrieval/cache state.
- JSON exports use top-level `lineage` and `records`; XLSX exports include a `Lineage` sheet; CSV remains tabular and is accompanied by lineage JSON.
- The Streamlit Data provenance panel renders only the typed envelope and ordered transformation history.
- Industry Pulse routes are canonical-only at `/v1/context/signals*`, perform no provider calls,
  and return typed available/unmapped/empty-range envelopes.
- Industry Pulse CSV/JSON/XLSX exports carry separate allowlisted signal provenance and cannot
  mutate annual dataframe lineage.
- Industry Momentum routes are canonical-only at `/v1/context/momentum*`; a broken family returns
  a partial result, while every requested mapped family unavailable returns a sanitized 503.
  Momentum CSV/JSON/XLSX exports remain separate from annual exports and lineage.

## 4. Quality Gates

All contributions must pass `make quality-gate`, which executes:

1. Formatting checks (Black in check mode).
2. Linting (Ruff).
3. Type checking (mypy).
4. Pytest with coverage enforcement.
5. Security scans (`pip-audit` and `detect-secrets`).

Use `make format`, `make lint`, `make typecheck`, or `make test` for targeted debugging.

## 5. Configuration

- Configuration values are centralised in `src/core/config.py` with environment variable overrides. Key settings include API credentials, rate limiter backend, observability replication targets, and dtype overrides.
- `.env` files are not committed; developers should export variables locally when required.
- Maintained repository configuration files include:
  - `extensions/manifest.json` – declares available extensions.
  - `pyproject.toml` – Python packaging, formatter, linter, type-checker, pytest, coverage, and Commitizen metadata.
  - `config/.pre-commit-config.yaml` – local hook definitions.
  - `config/.secrets.baseline` – the reviewed `detect-secrets` baseline.
  - `.github/dependabot.yml` – bounded dependency-update policy.

Validate JSON with `python -m json.tool <file>`. Validate TOML with a short `tomllib` load, for example:

```bash
python -c "import pathlib, tomllib; tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))"
```

## 6. Repository Layout

Each major directory contains a `README.md` or maintained guide describing its scope:

- [`src/`](../src/README.md) – source code, organised by layer.
- [`tests/`](../tests/README.md) – pytest suites.
- [`src/scripts/`](../src/scripts/README.md) – automation helpers.
- [`docs/`](README.md) – documentation hub.
- [`extensions/`](../extensions/README.md) – manifest-driven plugins.
- [`data/`](../data/README.md) – sample datasets for offline usage.
- [`assets/`](../assets/README.md) – static assets for UI/docs.
- Executive summaries live in [`exec/`](exec/README.md); see the handbook for canonical stewardship reports.

## 7. Documentation

- The root [`README.md`](../README.md) provides onboarding, command references, and environment configuration tips.
- Root [`SPEC.md`](../SPEC.md) is the concise authoritative repository specification; this document supplies the detailed architecture and maintenance reference.
- [`handbook/`](handbook/README.md) hosts canonical guides for architecture, automation, releases, and security.
- [`execplans/`](execplans/README.md) archives historical execution plans, including the repository cleanup and validation pass described in the latest entry of [`CHANGELOG.md`](CHANGELOG.md).
- [`exec/`](exec/README.md) captures stakeholder-facing summaries and status reports.

Keep these documents up to date whenever workflows or architecture change.

## 8. Testing Strategy

- Unit and integration tests live under `tests/` and mirror the structure of `src/`.
- Agent tooling tests ensure schemas stay in sync with the application layer.
- Observability and replication tests rely on local stubs; avoid calling real cloud APIs in CI.
- Coverage reports are generated automatically during `make quality-gate`; minimum thresholds are enforced to catch regressions.

## 9. Extension Ecosystem

- New connectors, instrumentation modules, or replication backends must be registered in `extensions/manifest.json` and implement the appropriate contract under `src/extensions/`.
- Use `python src/scripts/scaffold_extension.py --name <snake_case_name>` to bootstrap new modules.
- Verify catalog output with `make extensions-catalog` and `make connectors-catalog`.

## 10. Release & Reporting Requirements

- Update [`CHANGELOG.md`](CHANGELOG.md) for every meaningful change.
- Track task completion in [`TASKLIST.md`](../TASKLIST.md) using the provided format.
- Provide execution context in [`execplans/`](execplans/README.md) when undertaking significant refactors.
- Adhere to coding conventions in root [`STYLE-GUIDE.md`](../STYLE-GUIDE.md), detailed [`STYLE-GUIDE.md`](STYLE-GUIDE.md), and [`CONTRIBUTING.md`](CONTRIBUTING.md); document justified deviations in an ADR or the changelog.

This specification should be treated as the detailed reference supporting the authoritative root `SPEC.md`. Revisit both documents as architecture or processes evolve.
