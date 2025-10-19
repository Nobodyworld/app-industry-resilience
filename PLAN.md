# Modernization Execution Plan

Maintain this plan in accordance with `.agent/PLANS.md`. Create or update ExecPlans for any milestone that requires multi-file code changes.

## Overview
We will modernize the Idiot Index application in vertical slices that harden governance, enforce high-signal tooling, tighten typing, expand tests, and enhance security/observability without regressing existing behaviour. Each milestone delivers a reviewable PR set with clear rollback options and documentation updates.

## Milestones, Workstreams, and Tasks

### Milestone 0 – Discovery & Orientation *(complete)*
- **Workstream D0.1 – Repository Intelligence**
  - **Task D0.1.1 – Author REPORT.md and PLAN.md** *(Tags: docs, DX)*
    - Goal: Capture current-state analysis and execution roadmap to guide follow-on work.
    - Acceptance Criteria: REPORT.md summarises system overview, dependencies, risks, and quick wins; PLAN.md outlines milestones and tasks; both committed with supporting citations.
    - Blast Radius: Documentation-only; no runtime impact.
    - Rollback Plan: Revert the documentation commit.
    - Prerequisites: None.

### Milestone 1 – Governance, Tooling, and CI Foundation
- **Workstream G1.1 – Repository Governance & Policy**
  - **Task G1.1.1 – Establish base governance docs (LICENSE audit, README refresh, CONTRIBUTING, CODE_OF_CONDUCT, SUPPORT, SECURITY)** *(Tags: docs, DX, security)*
    - Goal: Provide clear contribution, support, and security guidance aligning with enterprise expectations.
    - Acceptance Criteria: New/updated docs in root with consistent voice, cross-links, and explicit disclosure of support and vulnerability reporting paths; README references governance docs.
    - Blast Radius: Documentation; ensure external links valid.
    - Rollback Plan: Revert doc changes if issues arise.
    - Prerequisites: Milestone 0 complete.
  - **Task G1.1.2 – Define CODEOWNERS & issue/PR templates** *(Tags: DX, reliability)*
    - Goal: Encode review ownership and standardized triage process.
    - Acceptance Criteria: `.github/CODEOWNERS`, `.github/ISSUE_TEMPLATE/` set with bug/feature templates, `.github/PULL_REQUEST_TEMPLATE.md` aligning with modernization goals.
    - Blast Radius: GitHub metadata only.
    - Rollback Plan: Remove or adjust templates.
    - Prerequisites: G1.1.1 (establish maintainers to list in CODEOWNERS).

- **Workstream G1.2 – CI/CD & Automation Baseline**
  - **Task G1.2.1 – Adopt Conventional Commits & commitlint** *(Tags: DX, docs)*
    - Goal: Enforce standardized commit messages through configuration and documentation.
    - Acceptance Criteria: `package.json` or equivalent tooling (`commitlint.config.cjs`) with CI enforcement and contributing docs updated with examples.
    - Blast Radius: Developer workflow; ensure instructions to install dependencies.
    - Rollback Plan: Remove commitlint config and CI hook.
    - Prerequisites: G1.1.1 (contributing guide to describe usage).
  - **Task G1.2.2 – Introduce EditorConfig, formatter, linter, type-check orchestrations** *(Tags: DX, testing)*
    - Goal: Codify formatting with `black`, linting with `ruff` (supersedes flake8), typing via `mypy`, plus shared configuration.
    - Acceptance Criteria: `.editorconfig`, `pyproject.toml` (or tool-specific configs) enabling single-source formatting/linting; README/CONTRIBUTING updated with commands.
    - Blast Radius: Formatting changes touching many files; stage via dedicated PR with minimal churn.
    - Rollback Plan: Revert config and reformat commit; ensure backup of previous formatting instructions.
    - Prerequisites: None (can run parallel with G1.2.1 but coordinate to avoid conflicts).
  - **Task G1.2.3 – Configure pre-commit hooks & CI enforcement** *(Tags: DX, testing, security)*
    - Goal: Add `.pre-commit-config.yaml` running formatter, ruff, mypy, commitlint, secret scan (gitleaks), and trailing whitespace checks with CI job gating merges.
    - Acceptance Criteria: Pre-commit file committed; README instructs installation; GitHub Actions workflow updated to run `pre-commit run --all-files`; gitleaks configured with baseline.
    - Blast Radius: Developer local workflow; ensure instructions for dependencies.
    - Rollback Plan: Remove pre-commit config and CI step.
    - Prerequisites: G1.2.2 (formatter/linter configs ready).
  - **Task G1.2.4 – Expand CI matrix with caching, SBOM, and artifact uploads** *(Tags: security, reliability, testing)*
    - Goal: Harden pipeline with dependency caching, SBOM generation (Syft/CycloneDX), pytest coverage artifact, and gitleaks/secret scanning.
    - Acceptance Criteria: GitHub Actions workflow updated with pip caching, deterministic dependency install, SBOM artifact upload, coverage artifact, secret scanning step; CI passes in forked runs.
    - Blast Radius: CI runtime; ensure additional tooling does not leak secrets.
    - Rollback Plan: Revert workflow changes or disable problematic steps.
    - Prerequisites: G1.2.3 (pre-commit ensures consistent tool versions).
    - Status (2024-05-13): **Complete** — Added `security` job running gitleaks, `pip-audit`, `detect-secrets`, SBOM generation via `make sbom`, and artifact uploads for `build/reports` + `build/sbom`.

- **Workstream G1.3 – Status Tracking**
  - **Task G1.3.1 – Introduce STATUS.md with rolling updates per PR** *(Tags: docs, DX)*
    - Goal: Provide running ledger of modernization progress.
    - Acceptance Criteria: STATUS.md created with initial entry summarizing Milestone 0 + outline for future updates; automation/guidelines noted in CONTRIBUTING.
    - Blast Radius: Documentation only.
    - Rollback Plan: Revert STATUS file if strategy changes.
    - Prerequisites: Milestone 0 complete.

### Milestone 2 – Typing, Dead Code, and Baseline Refactors
- **Workstream T2.1 – Strict Typing & Static Analysis**
  - **Task T2.1.1 – Enable mypy strict mode and remove `ignore-missing-imports`** *(Tags: testing, reliability, DX)*
    - Goal: Achieve `mypy --strict` across `src/` and `agents/` with minimal suppressions.
    - Acceptance Criteria: `mypy.ini`/`pyproject.toml` updated; code updated with precise types; tests/CI green without blanket ignores; documentation updated.
    - Blast Radius: Touches many modules; may require targeted refactors.
    - Rollback Plan: Revert type changes or relax config temporarily (documented).
    - Prerequisites: G1.2.2 (formatter/linter config) & G1.2.3 (pre-commit pipeline) for consistent tooling.
  - **Task T2.1.2 – Adopt typing stubs or vendored types for third-party libs** *(Tags: testing, DX)*
    - Goal: Add stub packages (`types-requests`, `pandas-stubs` as needed) or local protocol wrappers to satisfy strict mypy.
    - Acceptance Criteria: Dependencies added to dev requirements; type-checks pass; docs mention new deps.
    - Blast Radius: Low; only dependency metadata.
    - Rollback Plan: Remove added packages.
    - Prerequisites: T2.1.1 (identify gaps first).

- **Workstream T2.2 – Dead Code Retirement & Modularisation**
  - **Task T2.2.1 – Inventory external dependents for legacy shim modules** *(Tags: DX, reliability)*
    - Goal: Determine whether `src/{config,cache,normalize,...}.py` wrappers can be deprecated safely.
    - Acceptance Criteria: Documented decision (ADR) on removal strategy; feature flag or environment toggle planned if needed.
    - Blast Radius: Documentation/analysis only.
    - Rollback Plan: None needed; maintain docs.
    - Prerequisites: Milestone 1 (governance & doc scaffolding).
  - **Task T2.2.2 – Migrate internal imports away from shims & gate external removal** *(Tags: DX, reliability)*
    - Goal: Update repo-internal imports to use layered modules directly; introduce feature flag or compatibility import map for external users.
    - Acceptance Criteria: All internal modules/tests import from `src.core`, `src.adapters`, etc.; shims optionally emit deprecation warnings; tests pass.
    - Blast Radius: Medium; touches many files and runtime import paths.
    - Rollback Plan: Revert commit or toggle flag to re-enable shims.
    - Prerequisites: T2.2.1 (deprecation strategy) & T2.1.1 (typing ensures safe refactors).
  - **Task T2.2.3 – Decompose `app.py` into composable controllers** *(Tags: DX, reliability)*
    - Goal: Extract state management and data orchestration into dedicated service/controller modules under `src/interfaces/streamlit`.
    - Acceptance Criteria: `app.py` limited to wiring; new modules unit-tested; Streamlit UI behaviour unchanged (verified manually + tests for helper outputs).
    - Blast Radius: High; requires careful manual regression testing.
    - Rollback Plan: Revert decomposition branch; rely on tests to detect regressions.
    - Prerequisites: G1.2 tasks (tooling) + T2.1.1 (typing) to catch issues.

### Milestone 3 – Testing & Observability Expansion
- **Workstream Q3.1 – Test Pyramid Reinforcement**
  - **Task Q3.1.1 – Add integration tests for adapters with recorded fixtures** *(Tags: testing, reliability)*
    - Goal: Use VCR/pytest-recording to capture BEA/Census responses; verify parsing, caching, metadata.
    - Acceptance Criteria: Fixture-based tests under `tests/integration/`; CI runs offline; docs describe refresh process.
    - Blast Radius: Introduces fixture data; ensure secrets not recorded.
    - Rollback Plan: Remove integration tests or disable via marker.
    - Prerequisites: Milestone 2 (typing ensures stable interfaces).
  - **Task Q3.1.2 – Introduce Streamlit component tests (snapshot or DOM diff)** *(Tags: testing, DX)*
    - Goal: Validate UI helper output via Streamlit testing tools or screenshot diffs.
    - Acceptance Criteria: Tests cover key components; baseline snapshots stored; CI job for frontend tests added.
    - Blast Radius: Medium (new tooling, potential flakiness).
    - Rollback Plan: Remove snapshots or disable test job.
    - Prerequisites: Q3.1.1 (foundation) and Milestone 1 (CI enhancements for artifact capture).

- **Workstream O3.2 – Observability & Performance**
  - **Task O3.2.1 – Add OpenTelemetry-friendly structured logging & metrics export** *(Tags: observability, reliability, performance)*
    - Goal: Integrate `opentelemetry` hooks or structured logging to emit metrics for API latency/cache hit rate.
    - Acceptance Criteria: Logging config exports metrics counters/gauges (prom-client or statsd) guarded by feature flags; docs explain enabling; tests assert instrumentation toggles.
    - Blast Radius: Runtime logging/perf overhead; gate via config flag.
    - Rollback Plan: Disable via flag or revert instrumentation commit.
    - Prerequisites: T2.2.3 (modularised app) to insert instrumentation cleanly.
  - **Task O3.2.2 – Implement health/readiness endpoints for container usage** *(Tags: reliability, performance)*
    - Goal: Provide `/healthz` HTTP endpoint (FastAPI microservice or Streamlit custom route) or CLI script for container probes.
    - Acceptance Criteria: Container exposes script/endpoint returning 200; Dockerfile healthcheck updated; tests cover CLI success.
    - Blast Radius: Container behaviour; ensure compatibility with existing deployments.
    - Rollback Plan: Revert Dockerfile & script updates.
    - Prerequisites: G1.2.4 (CI ensures container build/test pipeline).

### Milestone 4 – Security & Supply Chain Hardening
- **Workstream S4.1 – Dependency & Secret Governance**
  - **Task S4.1.1 – Introduce Renovate/Dependabot configuration** *(Tags: security, reliability)*
    - Goal: Automate dependency update PRs with grouping and scheduling.
    - Acceptance Criteria: `.github/renovate.json` or `.github/dependabot.yml` configured; documented in CONTRIBUTING; CI label automation for update PRs.
    - Blast Radius: PR volume; ensure schedules manageable.
    - Rollback Plan: Disable configuration by removing file.
    - Prerequisites: Milestone 1 (governance) for label schema.
  - **Task S4.1.2 – Add secret scanning & policy enforcement (Trivy/Gitleaks)** *(Tags: security)*
    - Goal: Extend CI with secret scanning, SAST (Bandit, Semgrep), and dependency vulnerability checks.
    - Acceptance Criteria: CI workflow includes gitleaks/bandit/semgrep steps with fail-on-high severity; documentation instructs local usage via pre-commit.
    - Blast Radius: CI noise; tune thresholds carefully.
    - Rollback Plan: Adjust severity thresholds or remove step.
    - Prerequisites: G1.2.3 (pre-commit) to align local/CI checks.

- **Workstream S4.2 – Configuration & Runtime Security**
  - **Task S4.2.1 – Validate configuration with schema (pydantic or attrs)** *(Tags: security, reliability, DX)*
    - Goal: Replace ad-hoc parsing with schema-based validation (e.g., `pydantic-settings`) while retaining existing interface.
    - Acceptance Criteria: Config loader returns same dataclasses or new typed objects; tests ensure compatibility; docs updated; `.env.example` synchronized.
    - Blast Radius: High; touches config across codebase.
    - Rollback Plan: Reintroduce previous dataclass loader; maintain branch for quick revert.
    - Prerequisites: T2.1.1 (strict typing) and T2.2.2 (imports stabilized).
  - **Task S4.2.2 – Harden file upload & CSV validation with schema enforcement** *(Tags: security, reliability)*
    - Goal: Add column schema definitions (pandera or pydantic) plus malware scanning hooks.
    - Acceptance Criteria: Upload path rejects invalid schemas with descriptive errors; tests cover malicious inputs; docs updated.
    - Blast Radius: User-facing behaviour; ensure compatibility with existing CSVs.
    - Rollback Plan: Feature flag around strict validation; revert if false positives discovered.
    - Prerequisites: S4.2.1 (config improvements) for consistent policy toggles.

### Milestone 5 – Release Automation & Final polish
- **Workstream R5.1 – Release Management**
  - **Task R5.1.1 – Implement semantic-release workflow** *(Tags: DX, reliability)*
    - Goal: Automate versioning and changelog generation from Conventional Commits.
    - Acceptance Criteria: GitHub Action creates releases/tags on main merges, updates CHANGELOG.md, and publishes container image if desired.
    - Blast Radius: Release process; ensure dry-run before enabling.
    - Rollback Plan: Disable workflow and revert versioning commits.
    - Prerequisites: G1.2.1 (Conventional Commits) & G1.2.4 (CI).
  - **Task R5.1.2 – Document release runbooks & first-hour experience** *(Tags: docs, DX)*
    - Goal: Create `docs/operations/` runbook covering deployment, rollback, troubleshooting, and developer onboarding.
    - Acceptance Criteria: New docs linked from README; includes `make`/`just` automation instructions; STATUS.md updated.
    - Blast Radius: Documentation only.
    - Rollback Plan: Revert docs if outdated.
    - Prerequisites: Prior milestones provide tooling context.

## Sequencing & Parallelism Notes
- Milestone 1 tasks lay the foundation; complete them before strict typing or security refactors.
- Within Milestone 1, tasks G1.2.1–G1.2.4 should ship across two to three PRs to keep diffs reviewable (governance docs separate from tooling configs, pre-commit separate from CI expansion).
- Milestone 2 can proceed once baseline tooling is stable; typing (T2.1.1) should precede major refactors to leverage type guarantees.
- Milestone 3 observability work depends on modularised app structure (T2.2.3) to avoid conflicting rewrites.
- Security hardening in Milestone 4 should leverage CI enhancements (G1.2.4) to run new scanners without overloading pipelines.
- Release automation (Milestone 5) is last to prevent premature tagging; ensure STATUS.md captures progress after each PR.

## Blockers & Open Questions
- Need confirmation on downstream consumers relying on `src/` legacy shims (Task T2.2.1).
- Decide on preferred structured logging/metrics stack (OpenTelemetry vs. Prometheus client).
- Confirm organisational preference for Renovate vs Dependabot.

## Rollback Philosophy
Each task’s rollback defaults to `git revert` of the PR. For runtime changes, additionally:
- Feature-flag new behaviour where feasible (e.g., strict validation, instrumentation) so rollback can happen via configuration while preserving code.
- Maintain changelog entries noting rollback levers.

## Reporting & Status Updates
After completing each task/PR, append a summary and next-step note to `STATUS.md` per instruction, linking back to relevant milestone/workstream.
