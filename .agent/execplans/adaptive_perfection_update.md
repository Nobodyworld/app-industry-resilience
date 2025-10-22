# Adaptive perfection update – Streamlit bootstrap hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

Tighten the Idiot Index app's bootstrap sequence so configuration is loaded lazily, tests can override environment variables reliably, and the Streamlit entrypoint surfaces validation feedback without import-time side effects. The resulting flow should let operators toggle settings without restarting processes, while preserving UI behaviour. Documentation and reports will capture the repository context, risk posture, and verification evidence for future maintainers.

## Progress

- [x] (2025-02-14 05:40Z) Capture repository context and diagnostics for REPORT.md.
- [x] (2025-02-14 06:05Z) Implement lazy config bootstrap module and refactor app.py to use it.
- [x] (2025-02-14 06:20Z) Update/add tests covering new bootstrap utilities and existing hot paths.
- [x] (2025-02-14 06:30Z) Run verification commands and record outcomes.
- [x] (2025-02-14 06:40Z) Finalize REPORT.md, mode selections, and follow-up notes.
- [x] (2025-02-14 07:10Z) Extend bootstrap helper with readiness/warning helpers and derived sidebar bounds; expand regression tests.
- [x] (2025-02-14 07:55Z) Harden bootstrap convenience APIs with error/warning accessors and string-normalised env handling; update UI wiring and tests accordingly.
- [x] (2025-02-14 08:35Z) Introduced sidebar context helpers with clamped defaults and null-safe env overrides, refreshing UI usage and regression tests.

## Surprises & Discoveries

- Observation: Dockerfile health check used curl without installing it.
  Evidence: Inspecting `Dockerfile` showed `HEALTHCHECK CMD curl ...` while apt package list omitted curl.

## Decision Log

- Decision: Introduced `src/interfaces/streamlit/bootstrap.py` to lazily cache configuration and validation while keeping Streamlit imports isolated.
  Rationale: Enables deterministic tests and avoids import-time side effects in the entrypoint.
  Date/Author: 2025-02-14 / gpt-5-codex
- Decision: Aligned sidebar year bounds with configuration ranges and fixed Docker health check by installing curl.
  Rationale: Keeps UI consistent with validated config values and prevents false-negative container probes.
  Date/Author: 2025-02-14 / gpt-5-codex

## Outcomes & Retrospective

- Added bootstrap helper with caching + error wrapping, refactored `app.py` to use it, expanded tests (57 total) to cover bootstrap, and documented results in REPORT.md.
- Refined helper ergonomics with readiness/warning accessors plus sidebar year bounds, locking behaviour in with additional regression tests.
- Added ergonomic accessors for validation errors/warnings, improved error messaging, and normalised env overrides to handle non-string inputs.
- Delivered sidebar context utilities for bound-aware defaults, tightened env normalisation, and updated docs/tests to capture the new behaviour.

## Context and Orientation

The repository contains a Streamlit application (`app.py`) backed by layered Python packages under `src/`. Configuration helpers in `src/core/config.py` provide `load_config` and `validate_config`, but `app.py` currently imports configuration at module import time, which complicates tests that need environment overrides. Tests live in `tests/`, with existing coverage for configuration parsing but not for the Streamlit bootstrap path. Documentation and governance artefacts exist under the repo root and `docs/`. Tooling relies on Poetry-compatible `pyproject.toml`, `requirements.txt`, and `Makefile` automation. Our work will add a REPORT summarising structure and risk, refactor the bootstrap into a dedicated module (e.g., `src/interfaces/streamlit/bootstrap.py`), update Streamlit entrypoint usage, extend tests, and record verification evidence.

## Plan of Work

1. Audit existing configuration usage in `app.py` and related modules; note global side effects and how validation results are displayed.
2. Draft REPORT.md capturing structure, dependencies, key findings, risks, test posture, and CI/CD posture derived from repo inspection.
3. Implement a new bootstrap helper (proposed path `src/interfaces/streamlit/bootstrap.py`) exposing:
   - `BootstrapState` dataclass capturing `config`, `validation`, and convenience helpers for readiness, warnings, and derived sidebar bounds.
   - `get_bootstrap_state()` that lazily loads configuration (with optional env override), caches the result via `functools.lru_cache`, and re-validates on demand.
   - Functions to reset cached state for tests.
4. Refactor `app.py` to remove module-level config loading. Instead, retrieve bootstrap state inside the Streamlit runtime, surface errors/warnings, and expose config summary.
5. Update tests:
   - Add a dedicated test module for the bootstrap helper verifying lazy loading, cache reset, and error propagation.
   - Adjust existing tests if necessary to import new helper.
6. Ensure new module exports are documented in `src/interfaces/streamlit/__init__.py` or equivalent for compatibility.
7. Run `pytest` and capture output for verification; if new lint/tool commands are introduced, execute them as well.
8. Update REPORT.md with selected modes (e.g., Architecture Alignment, Zero-Bloat Refactor, Test & Verify) justified by findings, and summarise verification results.
9. Stage changes, craft commit message, and prepare PR body per instructions.

## Concrete Steps

1. Use `ls`, `rg`, and `sed` from the repo root to inspect `app.py`, `src/core/config.py`, tests, and tooling. Take notes for REPORT.md sections.
2. Author REPORT.md capturing structure/dependency map, findings, risks, test posture, and CI/CD posture. Include chosen update modes with rationale.
3. Create `src/interfaces/streamlit/bootstrap.py` implementing lazy bootstrap helpers and reset capabilities; update package `__init__` if needed.
4. Modify `app.py` to consume new bootstrap helpers, eliminating module-level `APP_CONFIG`/`CONFIG_VALIDATION` globals while preserving UI behaviour (warnings/errors, config summary display, caching).
5. Add tests in `tests/test_bootstrap.py` (or similar) verifying lazy evaluation, environment overrides, reset functionality, and validation merge semantics. Update `tests/__init__.py` if required.
6. Run `pytest` from the repo root, storing the transcript for REPORT.md and final summary.
7. Review formatting/linting compliance; run `ruff format`/`black` or rely on `ruff` via `make format` if necessary.
8. Update REPORT.md with verification command outputs and selected modes; ensure all instructions satisfied.

## Validation and Acceptance

- `pytest` must pass locally after refactor.
- Streamlit bootstrap should expose the same validation errors/warnings as before when running `streamlit run app.py` (manual check via code inspection and optional smoke run).
- REPORT.md must document selected modes and verification evidence.
- New tests should fail against the pre-change codebase (conceptually) and pass now, proving lazy bootstrap behaviour.

## Idempotence and Recovery

The bootstrap helper uses pure Python functions with optional cache reset; re-running the module import is safe. Git provides rollback capability. REPORT.md updates are additive and can be edited safely. No destructive migrations are planned.

## Artifacts and Notes

- New module: `src/interfaces/streamlit/bootstrap.py`.
- New tests: `tests/test_bootstrap.py`.
- Updated docs: `REPORT.md` with structure, findings, risks, test posture, CI/CD posture, and mode selections.
- Recorded verification output from `pytest`.

## Interfaces and Dependencies

- `src/interfaces/streamlit/bootstrap.py` should import from `src.core.config` only (no UI dependencies) to keep layering clean.
- Export functions: `get_bootstrap_state`, `reset_bootstrap_state`, and dataclass `BootstrapState`.
- `app.py` should call `get_bootstrap_state()` early in the `main` flow, using returned `AppConfig` and `ConfigValidationResult`.
- Tests should use `reset_bootstrap_state()` to clear caches between scenarios.
