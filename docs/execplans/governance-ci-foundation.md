# Establish governance, automation, and quality baselines

> Historical note: version references in this ExecPlan reflect the environment at the time of writing. Current repository support policy is Python 3.13+ (see `README.md` and `pyproject.toml`).

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

See .agent/PLANS.md for required structure and maintenance practices; all guidance there applies here.

## Purpose / Big Picture

After completing this plan, contributors can clone the repository, run a single bootstrap command, and rely on automated checks that enforce formatting, linting, typing, and tests. Pull requests will open with consistent templates, commits will be linted for Conventional Commit compliance, and maintainers will have clear governance documents that set expectations for support, security, and conduct. CI will execute the same checks as the local pre-commit stack, making drift obvious and reducing regressions.

## Progress

- [x] (2025-10-19 11:05Z) Baseline repository audit complete; governance docs outlined.
- [x] (2025-10-19 11:20Z) Toolchain configuration drafted (EditorConfig, Ruff/Black, mypy, pytest, commitlint, pre-commit).
- [x] (2025-10-19 11:35Z) Local developer tooling implemented (pre-commit, Makefile tasks).
- [x] (2025-10-19 11:50Z) CI workflow updated to mirror local tooling and upload coverage artifacts.
- [x] (2025-10-19 12:10Z) Templates, CODEOWNERS, and documentation committed.
- [x] (2025-10-19 13:45Z) Validation run: local quality script (pre-commit fallback) + pytest suite with offline fallbacks.
- [x] (2025-10-19 13:55Z) Outcomes & retrospective captured; plan ready for next milestone.

## Surprises & Discoveries

- Observation: `npm install` to fetch `@commitlint/cli` fails with HTTP 403 in the execution environment, indicating external registry access is blocked.
  Evidence: `npm error 403 403 Forbidden - GET https://registry.npmjs.org/@commitlint%2fcli` during the initial tooling setup attempt.
- Observation: `pip install` for locked tooling (e.g., `black==24.10.0`) also fails with the same proxy restriction, so we must rely on the interpreter's pre-installed packages.
  Evidence: `ERROR: Could not find a version that satisfies the requirement black==24.10.0` following repeated proxy failures.

## Decision Log

- Decision: Replace the Node-based commitlint dependency with a local Python implementation invoked via pre-commit.
  Rationale: The sandbox cannot reach the public npm registry (403 errors), so a Python script keeps commit message linting available offline while matching the intended ruleset.
  Date/Author: 2025-10-19 / gpt-5-codex
- Decision: Convert pre-commit to rely solely on local scripts and system-installed tooling instead of remote hook repositories.
  Rationale: Both npm and PyPI access are blocked; shipping local Python utilities keeps the workflow functional in constrained environments.
  Date/Author: 2025-10-19 / gpt-5-codex

## Outcomes & Retrospective

Completed. Governance docs, code owners, and templates are in place. Offline-safe tooling (local pre-commit fallbacks, conditional pip/pytest-cov handling) keeps quality gates runnable without external registries. Next steps: wire the CI workflow to exercise the same fallback strategy and begin tightening lint/type coverage on the legacy `src/` modules.

## Context and Orientation

The repository hosts a Streamlit application under app.py with supporting domain code in src/. Tests live in tests/. Historical automation at this stage included .github/workflows/ci.yml with flake8, mypy, and pytest steps across Python 3.9–3.11. requirements-dev.txt already lists black, flake8, mypy, pytest-cov, and types-requests. No pre-commit hooks, commit message linting, or standardized templates exist. Governance docs like CONTRIBUTING.md, CODE_OF_CONDUCT.md, docs/handbook/SECURITY.md, docs/handbook/SUPPORT.md, and CODEOWNERS are absent. There is no EditorConfig or Renovate configuration yet. docs/handbook/PLAN.md and docs/handbook/REPORT.md describe modernization goals that call for governance, automation, linting, and supply-chain hardening.

We will adopt Ruff as the single linting tool while keeping Black for formatting; Ruff will enforce comprehensive lint rules and manage import sorting. Pre-commit will orchestrate Black, Ruff, mypy, pytest (as needed), commitlint, and other checks. The CI workflow will be updated to run the same pre-commit hooks, ensuring parity. We'll also add Makefile targets to simplify running checks locally.

## Plan of Work

Begin by drafting governance documents (CONTRIBUTING.md, CODE_OF_CONDUCT.md, docs/handbook/SECURITY.md, docs/handbook/SUPPORT.md) and CODEOWNERS that align with repository stewardship assumptions. Introduce .editorconfig at the root to enforce indentation and whitespace standards for Python, Markdown, YAML, and JSON files.

Create pyproject.toml to centralize tool configurations: define Black target version, Ruff rules (linting and import sorting), mypy strictness (initially warn for missing imports but enable strict optional checks), and coverage settings. Reference requirements files to ensure dependencies include ruff, pre-commit, commitizen (for changelog automation), and commitlint. Update requirements-dev.txt accordingly and add a dedicated constraints file if needed.

Add a Makefile with targets such as install, format, lint, typecheck, test, coverage, and check (aggregate). Provide a dev bootstrap command (e.g., `make setup` invoking pre-commit install and pip install). Document these tasks in CONTRIBUTING.md.

Configure pre-commit by creating .pre-commit-config.yaml with hooks for trailing whitespace fixes, end-of-file-fixer, mixed-line-ending, codespell (if feasible), Black, Ruff (lint + format check), mypy (using python -m mypy), pytest (optional as manual stage), commitlint, and detect-secrets or similar. Ensure hook versions are pinned.

Set up commit message linting with a lightweight Python implementation that mirrors commitlint's Conventional Commit checks. This avoids external package downloads while still enforcing the same rules via the `commit-msg` hook.

Update .github/workflows/ci.yml to use Python 3.10 as primary (historical planning context; superseded by current Python 3.13+ policy). Add caching for pip, run `pip install -r requirements.txt` and `requirements-dev`, then execute `make check`. After tests, upload coverage and lint artifacts. Also include pre-commit action to ensure consistency.

Introduce .github/ISSUE_TEMPLATE/bug_report.md, feature_request.md, and config.yml, plus PULL_REQUEST_TEMPLATE.md referencing checklists for tests, docs, and risk. Add CODEOWNERS under .github/ with default owner placeholder (e.g., `* @idiot-index/maintainers`). Document assumption.

Update README.md or CONTRIBUTING to reference new processes. Add docs/development/onboarding? For this plan, ensure README references `make setup` and `make check`.

## Concrete Steps

Work from repository root `/workspace/app-industry-resilience`.

1. Draft governance Markdown files and CODEOWNERS.
2. Add .editorconfig with consistent styles.
3. Create pyproject.toml with tool configuration for black, ruff, mypy, pytest, coverage.
4. Update requirements-dev.txt to include ruff, pre-commit, commitizen, codespell, etc.; add poetry? keep pip.
5. Create Makefile with setup and check commands.
6. Add .pre-commit-config.yaml hooking formatting, linting, typing, tests, commitlint.
7. Add `scripts/commitlint.py` and configure the pre-commit commit-msg hook to call it.
8. Update .github/workflows/ci.yml to use caching and run `make check` plus coverage upload.
9. Add .github templates and CODEOWNERS.
10. Update README.md to mention new workflow and prerequisites.
11. Run `pip install -r requirements.txt -r requirements-dev.txt`, `pre-commit install`, `pre-commit run --all-files`, and `pytest` to validate.
12. Update docs/handbook/STATUS.md with summary per governance instructions.

## Validation and Acceptance

Successful implementation allows a contributor to run:

    make setup
    make check

Both commands should succeed on a clean clone. Pre-commit must report no failures on `pre-commit run --all-files`. CI workflow should, when inspected, mirror the Makefile check target (format, lint, type, test). Governance documents must exist with clear instructions, and new templates should appear under .github/. Commitlint should reject non-conforming messages when using pre-commit commit-msg stage (documented).

## Idempotence and Recovery

All commands are safe to re-run. `make setup` reinstalls dependencies and re-initializes pre-commit. Pre-commit hooks can be rerun without side effects. If CI fails due to caching, rerun after clearing caches.

## Artifacts and Notes

To be filled with command transcripts and validation logs once executed.

## Interfaces and Dependencies

Tooling versions to pin:

    black==24.10.0
    ruff==0.6.9
    mypy==1.11.2
    pre-commit==4.0.1
    codespell==2.3.0
    commitizen==3.27.0

EditorConfig applies to `*.py`, `*.md`, `*.yml`, `*.json`. Pre-commit used a python3.11 environment by default at the time this plan was written.
