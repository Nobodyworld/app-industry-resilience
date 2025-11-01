# Repository cleanup and restructure for Idiot Index

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

Deliver a comprehensive cleanup of the Idiot Index repository so that the project tree is intuitive, minimal at the root, and aligned with modern best practices. After finishing this plan, contributors will find documentation organized under `docs/`, source code under `src/`, automation in `scripts/`, and supporting assets within clearly named folders. `TASKLIST.md` will reflect current work, `.gitignore` will match the new layout, and changelog/README updates will communicate the restructure.

## Progress

- [x] (2025-10-30 12:05Z) Review TASKLIST.md and catalogue follow-up actions.
- [x] (2025-10-30 12:10Z) Propose directory normalization map and prepare file moves.
- [x] (2025-10-30 12:25Z) Apply file moves, update imports/configs, and prune duplicates.
- [x] (2025-10-30 12:45Z) Refresh documentation (.gitignore, README, CONTRIBUTING, CHANGELOG) for new structure.
- [x] (2025-10-30 13:10Z) Run quality gate and finalize deliverables.

## Surprises & Discoveries

- Updating references after consolidating documentation required touching a large set of ExecPlans and reports to correct relative links and citation paths.

## Decision Log

- Decision: Consolidate standalone governance and release docs into `docs/handbook/`.
  Rationale: Keeps the repository root focused on entrypoints while grouping long-form documentation in a predictable subtree.
  Date/Author: 2025-10-30 / gpt-5-codex
- Decision: Relocate the agent toolkit to `src/agents` and update imports/tests.
  Rationale: Aligns automation code with the `src/` layout so packaging and imports stay consistent with the Pythonpath configuration.
  Date/Author: 2025-10-30 / gpt-5-codex

## Outcomes & Retrospective

- Completed: Documentation consolidated under `docs/handbook/`, agent toolkit relocated to `src/agents`, README/CONTRIBUTING/CHANGELOG updated, and quality gate (format, lint, mypy, pytest) executed successfully.

## Context and Orientation

The repository root currently contains numerous Markdown documents (ARCHITECTURE, AUTOMATION, STATUS, etc.), several data/config folders (`data/`, `assets/`, `extensions/`, `agents/`, `scripts/`), and duplicate vendor directories like `fastapi/` and `pydantic/`. Core application code lives in `src/` with tests in `tests/` and an entrypoint `app.py`. Documentation is split between the root and `docs/`. `TASKLIST.md` governs outstanding work and must stay in the root alongside `SPEC.md` and `STYLE-GUIDE.md` per its banner note. `.agent/AGENTS.md` mandates running `make quality-gate` before committing.

## Plan of Work

First, audit `TASKLIST.md` to determine whether new restructure tasks need to be documented or if existing entries should be marked deprecated. Next, design the target directory schema: retain only essential metadata (README, LICENSE, SPEC, STYLE-GUIDE, TASKLIST, pyproject, requirements, app entrypoint) at the root while moving standalone guides into `docs/`, grouping operational scripts beneath `scripts/`, and relocating experimental modules (`fastapi/`, `pydantic/`) under a new `vendor/` namespace or removing them if unused. For each move, update import paths, package `__init__` files, and configuration references. Remove obsolete duplicates and ensure data/test paths still resolve. Finally, revise `.gitignore`, README, CONTRIBUTING, and CHANGELOG to explain the new layout and capture the work.

## Concrete Steps

1. From the repo root, inspect `TASKLIST.md`, existing docs, and directories (`ls`, `rg`, `tree` limited scope) to chart current placements.
2. Draft a mapping of files-to-destination within this plan and update the `Progress` section as work completes.
3. Use `git mv` to relocate Markdown guides into `docs/handbook/` (or similar), consolidate vendor packages under `src/vendor/` if required, and tidy unused assets.
4. Adjust Python imports or package initializers so the application and tests point to the new locations. Run targeted tests if needed during the move.
5. Update `.gitignore` entries for any new build or cache directories and remove stale paths.
6. Refresh README/CONTRIBUTING with structure overview and update CHANGELOG with a summary of the cleanup.
7. Run `make quality-gate` per repository rules, capture outcomes for reporting, and prepare the final summary.

## Validation and Acceptance

Successful completion requires `make quality-gate` to pass, README/CONTRIBUTING to describe the reorganized layout, CHANGELOG to record the restructure, and `TASKLIST.md` to present accurate task status. The project should start via `app.py` without missing imports after the moves, and tests should still execute under `tests/`.

## Idempotence and Recovery

File moves via `git mv` are reversible with `git restore` if needed. Documentation updates are textual and can be re-run safely. Running `make quality-gate` multiple times is safe. No destructive migrations or data deletions are planned beyond removing clearly unused duplicates after confirmation.

## Artifacts and Notes

Key artifacts will include an updated `TASKLIST.md`, reorganized documentation under `docs/`, revised `.gitignore`, README, CONTRIBUTING, and CHANGELOG entries describing the restructure. Capture any command output relevant to validation.

## Interfaces and Dependencies

Python modules in `src/` import internal packages using relative paths such as `from src.core...`. Any moved modules must preserve importable package names, potentially by adding namespace packages under `src/`. External dependencies remain defined in `pyproject.toml` and `requirements*.txt`. Scripts rely on `Makefile` targets; ensure these references stay accurate after directory adjustments.

