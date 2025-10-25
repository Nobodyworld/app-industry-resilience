# Release Notes

## 2025-10-27

### Highlights
- Added `STEWARDS_REPORT.md` consolidating system metrics, roadmap actions, and automation roles for the steward stage.
- Simplified API span handling with context managers and marked the health CLI as an agent entrypoint for safe automation.
- Documented offline coverage workflows so teams can maintain ≥90% coverage despite PyPI restrictions.

### Upgrade / Migration Notes
- No API contract changes; downstream clients do not need to adjust requests/responses.
- Teams relying on pytest-cov should cache wheels or use the documented trace fallback to keep coverage enforcement intact.

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
- Added `scripts/run_pytest_trace.py` and documentation for generating offline coverage via Python's built-in trace module. Coverage artefacts are written to `build/coverage/`.
- Documentation refreshed to explain the FastAPI-compatible façade, offline coverage workflow, and the new API server semantics.

### Upgrade / Migration Notes
- Remove `fastapi`, `uvicorn`, and `pydantic` from any pinned dependency lists when rebasing; the repository now provides those modules internally.
- If production deployments rely on real FastAPI/Uvicorn features (e.g., ASGI middlewares), replace the stub modules with the genuine packages in that environment by updating `PYTHONPATH` before importing the repo's code.
- Use `python -m trace --count --coverdir build/coverage scripts/run_pytest_trace.py` to reproduce the coverage report on systems without `pytest-cov`.
- The API CLI ignores `--reload`/`--workers` flags (preserved for compatibility). Adjust automation to avoid relying on hot reload semantics.

