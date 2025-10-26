# Release Notes

## 2025-10-28 – Observability unification

### Highlights
- Added the process-wide `ObservabilityRegistry`, instrumented Idiot Index workflows, and shipped the `/observability/status` endpoint plus the `scripts/observability_snapshot.py` CLI for air-gapped inspections.
- Introduced the `core_instrumentation` extension so metrics/health hooks live outside core services and updated scaffolds to generate instrumentation-ready extensions and services.
- Refreshed documentation (architecture, automation, incident response, API guides) and automation tooling (Makefile `observability` target, Dependabot labels) to reinforce the continuous improvement loop.

### Upgrade / Migration Notes
- Deployments should expose `/observability/status` to operators alongside `/metrics`; the payload mirrors the CLI and requires no authentication changes.
- When adding metrics, implement them as instrumentation extensions via `python scripts/scaffold_extension.py --instrumentation` so they remain decoupled from core services.
- CI/CD pipelines can invoke `make observability` to capture a JSON snapshot for artefact storage or incident retrospectives.

## 2025-10-26 – Health analytics hardening

### Highlights
- Optimised `compute_health_scores` and `summarise_health` for large datasets by vectorising band classification, sanitising top risk calculations, and avoiding unnecessary sector aggregation work.
- Added resilience tests covering NaN handling, group-by parameters, and the analytics top-risk limiter to guard against regressions.
- Introduced `scripts/run_tests_with_trace.py` and wired it into the Makefile so coverage enforcement works even when `pytest-cov` is unavailable, producing JSON/text reports under `build/reports/`.

### Upgrade / Migration Notes
- `make coverage` and `make quality-gate` honour the new `COVERAGE_THRESHOLD` variable (default 90). Environments without `pytest-cov` should rely on the bundled trace script, which now runs automatically and focuses on the analytics service/API modules (override with `--paths` for broader coverage).
- Automation that previously called `scripts/run_pytest_trace.py` should switch to `scripts/run_tests_with_trace.py` (command-line usage mirrors the old script but now integrates directly with pytest).

## 2025-10-25 – Health analytics expansion

### Highlights
- Introduced composite health scoring via `src/core/analytics` and surfaced the insights across Streamlit (new Health tab, signal bar badge, Scenario Lab) and the headless API.
- Added the `/analytics/health` endpoint, enriched `/evaluate` and `/scenario` responses with health envelopes, and shipped the `scripts/analytics_health.py` CLI with a `make analytics` shortcut.
- Extended agent responses (`IdiotIndexResponse`) with health metadata and refreshed documentation (`README`, `ARCHITECTURE_OVERVIEW.md`, `API_REFERENCE.md`, `docs/ANALYTICS_HEALTH.md`).
- Relaxed dependency pins in `requirements*.txt` to track the latest compatible releases while capturing review cadence in `docs/DEPENDENCIES.md`.

### Upgrade / Migration Notes
- API consumers should tolerate the new `health` field in `/evaluate` responses and the `baseline_health`/`scenario_health` fields in `/scenario`. Existing keys remain unchanged.
- Automation pipelines can call `/analytics/health` for lightweight summaries or the new CLI; ensure JSON parsers expect the health envelope structure.
- Dependency managers should allow the widened version ranges when syncing environments.

## 2025-10-27

### Highlights
- Updated `STEWARDS_REPORT.md` with measured coverage, complexity, dependency, and latency metrics plus a refreshed roadmap.
- Delivered `scripts/audit_metrics.py`, the `make audit` target, and `AUTOMATION_ROLES.md` so agents can capture stewardship data
  and coordinate responsibilities.
- Simplified API telemetry span closure, tagged automation make targets as `# agent-safe-task`, and taught every helper script to
  bootstrap the repository path for direct execution.

### Upgrade / Migration Notes
- Local and CI environments can now invoke `make audit` to persist `build/reports/audit-metrics.json`; archive the JSON for
  release artifacts if stewardship metrics must be auditable.
- No API contract changes, but CLI scripts now expect to run from the repository root so ensure automation calls them via
  `python scripts/<name>.py` or the corresponding Make targets.

## 2025-10-25

### Highlights
- Introduced a reusable `HealthProbe` feeding richer `/health` payloads and the new `scripts/check_health.py` CLI for
  air-gapped readiness checks.
- `/health` and `/healthz` now expose component-level statuses, configuration snapshots, and telemetry counters while the
  legacy `telemetry` field remains for compatibility.
- Added `AUTOMATION.md` plus updates across README, architecture, API, and incident-response docs to document the
  automation workflow and health tooling.

### Upgrade / Migration Notes
- Clients consuming `/health` must accept the new `status` values (`pass`, `warn`, `fail`) and account for the additional
  `components` and `metadata` fields. The existing `telemetry` field is unchanged for backwards compatibility.
- Automation can now rely on `python scripts/check_health.py` exit codes (0/1/2) to gate deployments when the HTTP API is
  unavailable.

## 2025-02-18

### Highlights
- Headless API no longer depends on external FastAPI/Pydantic/Uvicorn wheels; lightweight facades provide the required behaviour for health, evaluation, and scenario endpoints.
- `scripts/run_api.py` now embeds a threaded WSGI server so the API can be launched locally or in Docker without third-party servers, while keeping the CLI interface stable.
- Added `scripts/run_tests_with_trace.py` and documentation for generating offline coverage via Python's built-in trace module. Coverage artefacts are written to `build/reports/`.
- Documentation refreshed to explain the FastAPI-compatible façade, offline coverage workflow, and the new API server semantics.

### Upgrade / Migration Notes
- Remove `fastapi`, `uvicorn`, and `pydantic` from any pinned dependency lists when rebasing; the repository now provides those modules internally.
- If production deployments rely on real FastAPI/Uvicorn features (e.g., ASGI middlewares), replace the stub modules with the genuine packages in that environment by updating `PYTHONPATH` before importing the repo's code.
- Use `python scripts/run_tests_with_trace.py --threshold 90` to reproduce the coverage report on systems without `pytest-cov`.
- The API CLI ignores `--reload`/`--workers` flags (preserved for compatibility). Adjust automation to avoid relying on hot reload semantics.

