# Changelog

## 2025-10-27
- Completed Stage 4 steward audit with `STEWARDS_REPORT.md`, capturing metrics, automation hooks, and roadmap guidance for the
  Idiot Index ecosystem.
- Simplified API telemetry span handling and tagged the health CLI as an agent entrypoint to clarify automation boundaries.
- Documented offline coverage workflow and agent touchpoints for future autonomy-focused maintenance.

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
