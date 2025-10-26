# Changelog

## 2025-10-28 – Observability unification
- Added the `ObservabilityRegistry` to centralise metrics, tracing, and health contributions; instrumented `IdiotIndexService`, `ScenarioPlanner`, and the API to emit structured events.
- Introduced the `core_instrumentation` extension, `/observability/status` endpoint, and `scripts/observability_snapshot.py` CLI for unified monitoring in both online and offline environments.
- Expanded developer scaffolds (`scaffold_extension.py --instrumentation`, `scaffold_service.py`) and documentation (architecture, automation, incident response) so future modules stay observability-ready.
- Updated Dependabot configuration, Makefile targets, and contributor guidance to reinforce continuous improvement loops.

## 2025-10-26 – Health analytics hardening
- Vectorised health-band classification and tightened top-risk selection so analytics run faster and handle NaN-heavy datasets without misclassifying results.
- Added targeted tests for health summaries (grouping modes, zero top-risk limit, missing values) and new script coverage helpers to keep quality high.
- Introduced `scripts/run_tests_with_trace.py` plus Makefile improvements that enforce coverage thresholds even when `pytest-cov` is unavailable, defaulting to the analytics/application/API modules with overrideable paths.

## 2025-10-25 – Health analytics expansion
- Added `src/core/analytics` with composite health scoring, band distribution, and cohort aggregation reused by services, the UI, and the API.
- Extended Idiot Index summaries, Streamlit components, and Scenario Lab to surface health insights, risk band shifts, and top-risk industries.
- Introduced the `/analytics/health` API endpoint, updated `/evaluate`/`/scenario` payloads, and added the `scripts/analytics_health.py` CLI alongside a `make analytics` target.
- Relaxed dependency pins to track latest compatible releases and refreshed documentation (README, architecture, API guides, new `docs/ANALYTICS_HEALTH.md`).

## 2025-10-27
- Completed Stage 4 steward audit with `STEWARDS_REPORT.md`, adding measured coverage/complexity/dependency/latency metrics and
  a refreshed roadmap.
- Delivered `scripts/audit_metrics.py`, the `make audit` target, and `AUTOMATION_ROLES.md` so agents can gather stewardship data
  and coordinate responsibilities.
- Simplified API telemetry span handling, tagged observability/audit make targets as `# agent-safe-task`, and ensured every
  script bootstraps the repo root for direct execution.

## 2025-10-25
- Added a reusable `HealthProbe` in `src/infrastructure/observability` powering richer `/health` responses and the new
  `scripts/check_health.py` CLI.
- Updated the headless API to expose component-level health metadata and telemetry counts while maintaining backward
  compatibility for the `telemetry` field.
- Documented automation workflows in `AUTOMATION.md`, refreshed README/architecture/API guides, and expanded the
  incident-response playbook with the CLI workflow.

## 2025-02-18
- Replaced external FastAPI, Pydantic, and Uvicorn dependencies with in-repo lightweight facades so the headless API runs and tests execute without pip access.
- Hardened the API launcher with a threaded WSGI server, updated CLI messaging, and refreshed docs/Makefile guidance for the offline-friendly workflow.
- Added a trace-based coverage harness and coverage summary artifacts to guarantee ≥99% line coverage across the core, application, and API layers.
- Documented offline coverage and server usage in the README plus updated architecture/API references to highlight the FastAPI-compatible façade.

## 2025-10-20
- Documented architecture, API contracts, workflows, and dependency posture across new `/docs` guides with README cross-links.
- Modernised tooling targets and changelog/CONTRIBUTING/SECURITY guidance to reflect ExecPlan usage, Streamlit fetch UX, and dependency monitoring.
- Optimised the BEA adapter for vectorised parsing, deduplicated metadata merging, and more informative sidebar progress cues.
- Audited runtime/dev dependencies and recorded review cadence, updating `pyproject.toml` for Python 3.11 compatibility and DX improvements.
- Added Codex Steps 5-11 report artifacts and quality gate verification instructions.

## 2025-10-19
- Reorganised source tree into layered packages (`core`, `adapters`, `infrastructure`, `interfaces`) with compatibility shims.
- Added agent toolkit with dataclass schemas and documented interface.
- Fixed missing imports across cache, security, logging, adapters, and utilities.
- Updated tests and documentation to reflect new structure; all pytest suites pass.
- Added architecture and verification reports plus expanded README guidance.
