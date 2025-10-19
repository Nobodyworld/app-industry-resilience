# Adaptive perfection overhaul for Idiot Index app

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

Deliver a production-grade refresh of the Idiot Index Streamlit application that enforces consistent quality, documents the system, tightens security and stability, and makes the project agent-ready. After completing this plan the repository will contain contextual reports, refactored and linted source code, stronger tests, detailed documentation, and clearly defined agent integration surfaces. A newcomer should be able to run the app, read the docs, and integrate an AI agent workflow confidently.

## Progress

- [x] (2025-10-19 07:53Z) Stage 1 – capture environment context and create /REPORTS/000_CONTEXT.md.
- [x] (2025-10-19 08:00Z) Stage 2 – diagnostic review and /REPORTS/001_DIAGNOSIS.md.
- [x] (2025-10-19 09:20Z) Stage 3 – apply refactors, security hardening, documentation, and agent readiness per triggered modes.
- [x] (2025-10-19 09:45Z) Stage 4 – run tests, record verification in /REPORTS/002_VERIFICATION.md.
- [x] (2025-10-19 10:05Z) Stage 5 – finalize documentation set (README, ARCHITECTURE, AI interface, changelog, etc.).
- [x] (2025-10-19 10:10Z) Stage 6 – commit, prepare PR message, and summarize results per instructions.
- [x] (2025-10-19 10:15Z) Stage 7 – ensure all artifacts (REPORTS, AI interface, migrations, changelog) are present and consistent.

## Surprises & Discoveries

- Observation: Multiple modules (security, cache, logging, adapters) were missing foundational imports, causing runtime failures during module import.
  Evidence: Manual inspection before Stage 3 showed NameError risks in `src/core/security.py`, `src/core/cache.py`, and `src/infrastructure/logging_config.py`.
- Observation: External dependency installation (pydantic) was blocked by the execution environment.
  Evidence: `pip install` failed with proxy 403 errors (see terminal chunk `bbeac5`).

## Decision Log

- Decision: Reorganize source tree into `core`, `adapters`, `interfaces`, and `infrastructure` packages while leaving compatibility shims.
  Rationale: Satisfies architecture alignment mandate without breaking external import paths.
  Date/Author: 2025-10-19 / gpt-5-codex
- Decision: Replace planned Pydantic dependency with dataclass-based schemas for agent tooling.
  Rationale: Network restrictions prevented installing Pydantic; dataclasses plus custom schema generation meet the AI-ready requirement without extra packages.
  Date/Author: 2025-10-19 / gpt-5-codex

## Decision Log

- None yet.

## Outcomes & Retrospective

- Delivered layered architecture with compatibility shims, restored missing imports, and added agent tooling with dataclass schemas.
- Documentation set now covers architecture, agent integration, verification outputs, and changelog entries.
- All pytest suites pass (29 tests), confirming stability after large-scale refactor.

## Context and Orientation

The repository hosts a Streamlit data exploration app located at `app.py` with supporting modules in `src/` and assets in `assets/` and `data/`. Dependencies are managed by `requirements.txt` and `requirements-dev.txt`. Tests live in `tests/`. There is a Dockerfile for containerized deployment. The docs folder currently contains project documentation. No additional agent instructions beyond `.agent/AGENTS.md` apply. Primary tasks include producing report files under `/REPORTS/`, refactoring code for clarity and robustness, improving tests, and documenting architecture and AI integrations. All work must maintain behavioral parity while raising quality.

## Plan of Work

1. Explore the repository structure, gather details on languages, dependencies, tooling, and CI configurations. Capture findings in `/REPORTS/000_CONTEXT.md`.
2. Perform a diagnostic scan of the codebase: identify code smells, TODOs, typing gaps, and categorize issues by severity. Summarize conclusions and determine which adaptive modes to activate in `/REPORTS/001_DIAGNOSIS.md`.
3. For each activated mode:
   - Architecture Alignment: clarify module layering, standardize initialization, and resolve coupling.
   - Zero-Bloat Refactor: prune dead code, simplify functions, and optimize imports.
   - Full-System Polish: ensure formatting, typing, and documentation consistency.
   - Test & Verify: extend or adjust tests for reliability.
   - Security & Stability Audit: reinforce configuration validation, sanitize inputs, and update dependency checks.
   - AI-Ready Refactor: define structured agent interfaces and documentation.
   Execute these updates iteratively, ensuring each change is testable and observable.
4. Add or update documentation artifacts: README enhancements, new `ARCHITECTURE.md`, `docs/AI_INTERFACE.md`, `CHANGELOG.md`, and `/REPORTS/002_VERIFICATION.md` capturing validation output.
5. Run the project's test suite (`pytest`) and any linters or formatters adopted, recording outcomes in the verification report.
6. Prepare final summaries, follow-up tasks, and ensure all artifacts comply with instructions before committing changes with the prescribed message.

## Concrete Steps

1. From the repository root, run targeted `ls`, `sed`, and `rg` commands to inspect structure and dependencies. Capture key observations for Stage 1 and write `/REPORTS/000_CONTEXT.md`.
2. Use `rg` to locate `TODO`/`FIXME` notes, inspect modules for smells, and record them in `/REPORTS/001_DIAGNOSIS.md` along with selected modes.
3. Modify Python modules under `app.py`, `src/`, and `tests/` to fulfill chosen modes: reorganize directories if needed, refactor functions, improve typing, and clean imports. Remove obsolete assets or scripts. Update configuration handling, add caching or lazy loading, and ensure security best practices.
4. Create or update documentation files: `README.md`, `ARCHITECTURE.md`, `docs/AI_INTERFACE.md`, `/REPORTS/002_VERIFICATION.md`, and `CHANGELOG.md`. Introduce `/MIGRATION.md` if breaking changes occur.
5. Run `pytest` (and `flake8`/`mypy` if introduced) documenting results in verification report.
6. Stage all changes, commit with the required message, then invoke the `make_pr` tool with a title/body summarizing work per repository guidance.

## Validation and Acceptance

- `pytest` must pass successfully after refactors.
- If linters or formatters are configured (e.g., `ruff`, `black`), run them or document equivalently.
- The Streamlit app should start without runtime errors (`streamlit run app.py`), at least smoke-tested via log inspection.
- Documentation should describe architecture, setup, agent interfaces, and changelog entries that reflect the new release.
- `/REPORTS/002_VERIFICATION.md` must capture evidence of tests and runtime validation.

## Idempotence and Recovery

The plan relies on additive edits that can be applied incrementally. Running tests and linters multiple times is safe. Git history allows rolling back partial work. No destructive data migrations are planned; any structural reorganization should preserve functionality.

## Artifacts and Notes

Artifacts to produce: `/REPORTS/000_CONTEXT.md`, `/REPORTS/001_DIAGNOSIS.md`, `/REPORTS/002_VERIFICATION.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `docs/AI_INTERFACE.md`, optional `/MIGRATION.md`. Code modifications should include docstrings, typing, and refactors aligned with the selected modes. Maintain reproducible commands within the reports.

## Interfaces and Dependencies

Primary dependencies include Streamlit, Pandas, Plotly, and related data libraries defined in `requirements*.txt`. Security updates may involve dependency version adjustments. Agent-ready interfaces will likely utilize Pydantic models and clearly documented functions within `src/` or a new `agents/` directory. Ensure compatibility with Python 3.9+ and existing tooling. Tests leverage `pytest`. Streamlit is the runtime entrypoint via `app.py`.

