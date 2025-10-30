<!-- Detected primary: python -->
# URGENT: Repo Standardization Plan

This plan captures the state of the Idiot Index repository as we finish Phase 1 defaults and
prepare for broader modernization. Tasks remain tracked exclusively in `TASKLIST.md`.

- Repo: app-economics-idiot-index
- Maintainers: @idiot-index/maintainers
- Contacts: GitHub Discussions (community support); security issues via SECURITY.md process
- Last Updated: 2025-10-30

## Summary
- Stack classification (choose one primary):
  - [ ] Tauri (Rust + TS + React + Vite)
  - [ ] Electron (Node + TS + React)
  - [ ] React + Vite (SPA/PWA)
  - [ ] Next.js (SSR/ISR)
  - [x] Python service/app
  - [ ] Rust CLI/service
  - [ ] Other: _n/a_
- Current CI: GitHub Actions workflow `CI` delegates to reusable `quality-gate` (workflow_call) to run `make quality-gate` on Python 3.11.
- Current tests: `make quality-gate` executes Ruff lint, Black formatting check, mypy, pytest with coverage, detect-secrets, and pip-audit.

## Phase 0  Audit (read-only)
- Git state clean and fetched: [x] Managed via `make` workflows and CI protections.
- Language(s) and runtime(s): Python 3.11 (Streamlit dashboard + domain services).
- Package manager(s): pip with `requirements.txt` and `requirements-dev.txt`.
- Build tooling: Makefile (`make quality-gate`, `make api`, `make security`), Dockerfile for Streamlit image.
- Lint/format/test: Ruff, Black, mypy, pytest (+ coverage) invoked by `make quality-gate`.
- CI/CD: GitHub Actions (`ci.yml`) using reusable `quality-gate` workflow; uploads coverage artefacts.
- Releases/versioning: Conventional commits via Commitizen; CHANGELOG and RELEASE_NOTES maintained manually.
- Security: detect-secrets baseline, gitleaks in CI, pip-audit, SBOM generation (`make security`).
- Docs: README, docs/ knowledge base, REPORT/STATUS/PLAN suites kept current.
- License & NOTICE: LICENSE (proprietary terms), no additional NOTICE file required.
- Special notes: Observability snapshots generated under `build/`; no submodules or LFS.

## Phase 1  Defaults (no functional changes)
- [.editorconfig] Add/verify: [x] Existing file aligned with org defaults.
- [.gitattributes] Add/verify: [x] Added repository-wide normalization rules (2025-10-30).
- [.gitignore] Language-appropriate: [x] Python-focused ignore list confirmed.
- [CODEOWNERS] Define or confirm: [x] `.github/CODEOWNERS` routes reviews to @idiot-index/maintainers.
- [CONTRIBUTING.md] Add/refresh: [x] Current guidelines cover workflow and quality expectations.
- [SECURITY.md] Add/refresh: [x] Private disclosure workflow documented.
- [PR/Issue templates] Add/refresh: [x] Bug/feature templates and PR template present.
- [CI check-only] Lint/format/test baseline: [x] Reusable `quality-gate` workflow enforces checks.
- [Pre-commit] Whitespace/EOL/secret scan (check-only): [x] `.pre-commit-config.yaml` with hooks for formatting, Ruff, detect-secrets.
- [README] Standard sections present: [x] Overview, setup, and governance documented.

## Version Alignment Plan
- Refer to root `MASTER-VERSIONS.json` for target versions.
- Node (dev tooling):
  - [ ] Align TypeScript/ESLint/Prettier/@typescript-eslint/vitest to org targets. _Not applicable – no Node toolchain._
  - [ ] Re-run lint/format in check-only mode. _Not applicable – no Node toolchain._
- Node (runtime, if applicable):
  - [ ] Review `react`, `vite`, `next`, `zod` against targets, plan upgrades if safe. _Not applicable – no Node runtime._
- Python:
  - [x] Align `numpy`, `pandas`, `pydantic`, `fastapi`, `uvicorn`, `requests`, `pyyaml`, `matplotlib`, `scikit-learn`, `prometheus-client`, `torch`, `torchvision`, `streamlit`. _All listed packages absent or already compliant per comparison; see repo-specific deltas._
  - [x] Decide pinned vs compatible specifiers; prefer pinned + lockfile where feasible. _Using compatible floor/ceiling specifiers consistent with stewardship policy._
- Rust:
  - [ ] Align key crates (`tauri`, `tokio`, `serde`, `anyhow`) if present. _Not applicable – no Rust components._

### Repo-specific deltas vs Master Versions
- All monitored Python runtime and development dependencies match master targets (see `REPORTS/009_DEPENDENCY_ALIGNMENT.md`). No upgrades required at this stage.

## Risks & Constraints
- Standardization work may touch generated artefacts (e.g., coverage reports); keep `.gitattributes` in sync to avoid churn.
- Dependency upgrades rely on upstream Streamlit ecosystem stability; continue running full `make quality-gate` before releases.

## Decisions & ADRs
- 2025-10-30: Introduced reusable `quality-gate` workflow and `.gitattributes` to enforce defaults without touching application code.
- 2025-10-30: Authored `MASTER-VERSIONS.json` and comparison report to document dependency parity with organization baselines.

## Timeline & Owners
- Target window: 2025-10-30 → 2025-11-05 for Phase 1 wrap-up.
- Responsible: Automation Stewardship Team (@idiot-index/maintainers).
- Reviewers: @idiot-index/maintainers, CI guardians.

## Definition of Done (Phase 1)
- Defaults added, CI check-only green.
- Version alignment plan approved (no functional changes yet).
- No behavioral changes introduced.

## Upgrade Playbook (Concise)

- Pre-flight
  - [ ] Create branch `chore/align-versions`
  - [ ] Ensure clean git state and fetched remotes
  - [ ] Open repository `TASKLIST.md` and confirm modernization tasks

- Node (TypeScript/React/Vite/Next) – _not applicable_

- Python
  - [x] Update requirements/pyproject to targets; refresh lock if used (not required – ranges already aligned).
  - [x] Run tests; fix minimal type/compat issues (`make quality-gate`).
  - [x] Record blockers in `TASKLIST.md` (none observed during comparison).

- Rust – _not applicable_

- Wrap-up
  - [x] Ensure CI check-only passes (lint/format/test/security/license).
  - [ ] Update repo `README` only if necessary (current content sufficient; revisit after future upgrades).
  - [x] Summarize changes and deltas vs Master Versions in PR body and `REPORTS/009_DEPENDENCY_ALIGNMENT.md`.
