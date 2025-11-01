# Modernization Execution Plan

Maintain this plan per `.agent/PLANS.md`. Each milestone below represents a reviewable PR (or series of tightly scoped PRs) that ships a vertical slice without regressing production behaviour.

## 0. Milestone Overview

| Milestone | Focus | Status | Exit Criteria |
| --- | --- | --- | --- |
| M0 – Discovery | Establish baseline documentation and modernization backlog. | ✅ Complete (2025-10-19) | `REPORT.md`, `PLAN.md`, and `STATUS.md` capture system map, risks, and roadmap. |
| M1 – Governance & Tooling | Align governance docs, CODEOWNERS, and CI/pre-commit quality gates. | ⏳ In progress | Contributors can clone→`make setup`→commit with enforced lint/format/type/security checks in CI & locally. |
| M2 – Typing & Code Health | Enable strict typing and retire legacy shims safely. | ⏳ Planned | `mypy --strict` clean, documented shim deprecation plan, Streamlit app decomposed into testable layers. |
| M3 – Testing & Observability | Expand integration/UI tests, add telemetry and health probes. | ⏳ Planned | API fixtures, Streamlit regression tests, OTEL metrics, container health endpoint. |
| M4 – Security & Releases | Supply chain automation, hardened configuration, release automation. | ⏳ Planned | Renovate (or Dependabot) active, pydantic settings, hardened uploads, semantic releases. |
| M5 – Performance & Resilience (Stretch) | Benchmarking, cache tuning, resilience guardrails. | ⏳ Planned | Benchmark suite, cache metrics, resilience toggles, documented outcomes. |

## 1. Milestone 0 – Discovery & Orientation *(Complete)*

- **Workstream D0.1 – Repository Intelligence** *(Tags: docs, DX)*
  - **Task D0.1.1 – Publish Repo Intelligence Report and Execution Plan**
    - **Status:** Complete (2025-10-19).
    - **Goal:** Document current architecture, risks, modernization backlog, and execution plan.
    - **Acceptance Criteria:** `REPORT.md` enumerates system overview, dependencies, hotspots, and ROI-ranked opportunities; `PLAN.md` maps milestones/workstreams/tasks with rollback strategies; `STATUS.md` updated with milestone completion.
    - **Blast Radius:** Documentation only.
    - **Rollback Plan:** Revert docs if inaccuracies surface.
    - **Prerequisites:** None.

## 2. Milestone 1 – Governance & Automation Foundation

### Workstream G1.1 – Governance & Community Health *(Tags: docs, DX, security)*
- **Task G1.1.1 – Refresh core governance docs (README, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, SUPPORT, LICENSE audit)**
  - **Goal:** Align contributor guidance, escalation paths, and vulnerability disclosure process with modernization roadmap.
  - **Acceptance Criteria:**
    - README emphasises `make setup`/`make check`, development prerequisites, and deployment story.
    - CONTRIBUTING documents Conventional Commits, required checks, triage SLAs, and how to request changes to governance files.
    - SECURITY.md details contact channels, response timelines, and disclosure expectations.
    - SUPPORT.md clarifies supported channels and response windows.
  - **Blast Radius:** Contributor onboarding experience.
  - **Rollback Plan:** Revert doc set or restore prior versions.
  - **Prerequisites:** D0.1.1 to keep messaging consistent with roadmap.

- **Task G1.1.2 – Update CODEOWNERS + PR/issue templates with modernization workflow**
  - **Goal:** Ensure ownership, labelling, and checklists reflect quality gates and roadmap.
  - **Acceptance Criteria:** CODEOWNERS includes responsible teams for core areas; PR template references required checks and status logging; issue templates surface labels (security, DX, testing) and request reproduction steps.
  - **Blast Radius:** Repository governance for every PR/issue.
  - **Rollback Plan:** Restore prior templates or CODEOWNERS file.
  - **Prerequisites:** G1.1.1 (governance language established).

### Workstream G1.2 – CI/CD & Developer Tooling *(Tags: DX, testing, security)*
- **Task G1.2.1 – Standardise formatter/linter/type checker configuration**
  - **Goal:** Ensure Black, Ruff, and mypy run with identical settings locally and in CI.
  - **Acceptance Criteria:**
    - `pyproject.toml` is the single source for formatting and linting configuration; redundant configs removed.
    - `make format`, `make lint`, `make typecheck`, and `make check` run idempotently offline (fallback scripts documented).
    - Docs updated with “quality gates” table mapping tasks to commands.
  - **Blast Radius:** Formatting churn across repo; contributor workflow updates.
  - **Rollback Plan:** Revert config change and re-run formatter to restore previous state.
  - **Prerequisites:** G1.1.1 (docs ready to communicate changes).

- **Task G1.2.2 – Enforce Conventional Commits (commitlint + Commitizen)**
  - **Goal:** Gate commits locally and in CI using commitlint/Commitizen for consistent history and release automation readiness.
  - **Acceptance Criteria:** Commit-msg hook installed via `make setup`; CI step fails on non-compliant messages; CONTRIBUTING lists examples and lint bypass procedure for emergencies.
  - **Blast Radius:** All commit authors.
  - **Rollback Plan:** Temporarily disable hook/CI job while issues addressed.
  - **Prerequisites:** G1.2.1 (quality tooling foundation) and G1.1.1 (document expectations).

- **Task G1.2.3 – Harden pre-commit & CI security checks**
  - **Goal:** Guarantee consistent execution of pip-audit, detect-secrets, gitleaks, and SBOM generation locally and in CI.
  - **Acceptance Criteria:** `.pre-commit-config.yaml` contains security hooks with documented remediation steps; CI artifacts include pip-audit results and SBOM; README/CONTRIBUTING describe how to refresh baselines.
  - **Blast Radius:** CI runtime and contributor setup time.
  - **Rollback Plan:** Disable failing hook or revert to prior config while triaging false positives.
  - **Prerequisites:** G1.2.1–G1.2.2 (shared tooling + commit policy).

## 3. Milestone 2 – Typing & Code Health

### Workstream T2.1 – Strict Typing *(Tags: testing, reliability, DX)*
- **Task T2.1.1 – Enable `mypy --strict` and resolve violations**
  - **Goal:** Catch regressions early by embracing strict typing across `src/` and `src/agents/`.
  - **Acceptance Criteria:** `pyproject.toml` updated with strict settings; targeted `# type: ignore` documented with issue numbers; CI passes without `ignore_missing_imports` blanket.
  - **Blast Radius:** Wide; may touch most modules to refine types or introduce helper abstractions.
  - **Rollback Plan:** Temporarily relax to `--strict-optional` subset or revert until blockers resolved.
  - **Prerequisites:** M1 tasks (tooling + docs) to keep CI green.

- **Task T2.1.2 – Provide third-party stubs or typed wrappers**
  - **Goal:** Supply typing information for Streamlit, pandas, and requests where upstream stubs are missing or incomplete.
  - **Acceptance Criteria:** Stub packages added to `requirements-dev.txt`; local type-checks succeed without `type: ignore[misc]` for core APIs; maintenance strategy documented.
  - **Blast Radius:** Dependency footprint increases; potential licensing considerations for bundled stubs.
  - **Rollback Plan:** Remove problematic stubs or vendor alternatives.
  - **Prerequisites:** T2.1.1 (identify gaps during strict adoption).

### Workstream T2.2 – Code Structure & Legacy Surface *(Tags: DX, reliability, docs)*
- **Task T2.2.1 – Inventory legacy shim usage and define deprecation path**
  - **Goal:** Understand external consumers of `src/{cache,config,...}.py`, `src/ui/`, and `src/sources/` to plan safe removals.
  - **Acceptance Criteria:** ADR documenting findings, proposed warning/deprecation timeline, and communication plan.
  - **Blast Radius:** Documentation only.
  - **Rollback Plan:** Update ADR if new information arises.
  - **Prerequisites:** T2.1.1 (stable imports before refactoring).

- **Task T2.2.2 – Decompose Streamlit entrypoint into orchestrator + services**
  - **Goal:** Split `app.py` into thin UI shell plus testable orchestration/services modules.
  - **Acceptance Criteria:**
    - New modules under `src/interfaces/streamlit/` encapsulate data fetching, state hydration, and download prep.
    - `app.py` primarily wires UI components and delegates logic.
    - Unit tests cover newly extracted services; manual smoke test instructions recorded in PR.
  - **Blast Radius:** High—touches UI, adapters, and tests.
  - **Rollback Plan:** Feature-flag new code path or revert merge quickly.
  - **Prerequisites:** T2.2.1 (shim strategy) and T2.1.1 (types to guard refactor).

## 4. Milestone 3 – Testing & Observability Expansion

### Workstream Q3.1 – Integration & UI Testing *(Tags: testing, reliability, DX)*
- **Task Q3.1.1 – Add recorded adapter integration tests**
  - **Goal:** Use pytest-recording or VCR.py to capture BEA/Census API responses and validate caching + rate limiting offline.
  - **Acceptance Criteria:** Fixtures under `tests/integration/`; tests run without external connectivity; docs explain refreshing fixtures and secret hygiene.
  - **Blast Radius:** Repository size increase; test runtime.
  - **Rollback Plan:** Remove flaky fixtures/tests temporarily.
  - **Prerequisites:** T2.2.2 (stable adapter orchestration) and T2.1.1 (strict typing ensures clarity).

- **Task Q3.1.2 – Introduce Streamlit component regression tests**
  - **Goal:** Guard visual regressions using Streamlit testing API, Playwright screenshots, or snapshot comparisons.
  - **Acceptance Criteria:** Deterministic snapshot artifacts stored; CI uploads diffs; docs include regeneration instructions.
  - **Blast Radius:** Potential flake due to rendering nondeterminism.
  - **Rollback Plan:** Disable snapshot job or gate behind opt-in env var while stabilising.
  - **Prerequisites:** Q3.1.1 (test infrastructure) and T2.2.2 (modular components).

### Workstream O3.2 – Observability & Operations *(Tags: observability, performance, reliability)*
- **Task O3.2.1 – Add OpenTelemetry instrumentation and metrics**
  - **Goal:** Emit latency, cache hit/miss, and error metrics with optional tracing for adapters and UI lifecycle hooks.
  - **Acceptance Criteria:** Instrumentation hidden behind env flag; metrics exported via OTLP/Prometheus; tests cover toggling; docs describe configuration.
  - **Blast Radius:** Runtime overhead, dependency additions.
  - **Rollback Plan:** Disable via configuration or revert instrumentation module.
  - **Prerequisites:** T2.2.2 (modular architecture) for insertion points.

- **Task O3.2.2 – Replace Docker health check with first-class probe**
  - **Goal:** Provide Python-based CLI or lightweight ASGI endpoint for readiness/liveness and update Dockerfile accordingly.
  - **Acceptance Criteria:** Health script packaged with app; Dockerfile uses the script (no external binaries); tests validate exit codes; README documents usage for k8s/docker-compose.
  - **Blast Radius:** Deployment runtime; requires manual validation.
  - **Rollback Plan:** Revert Dockerfile or toggle via env var.
  - **Prerequisites:** G1.2.3 (security hooks) and O3.2.1 (shared observability primitives) for consistent instrumentation.

## 5. Milestone 4 – Security, Supply Chain, and Releases

### Workstream S4.1 – Dependency & Secret Governance *(Tags: security, reliability, DX)*
- **Task S4.1.1 – Introduce Renovate (or Dependabot) with policy guardrails**
  - **Goal:** Automate dependency updates with grouping, schedule, and CODEOWNERS-based review routing.
  - **Acceptance Criteria:** Renovate config checked in; documentation outlines triage cadence; labels + auto-merge rules defined where safe.
  - **Blast Radius:** Increased PR volume; process adjustments.
  - **Rollback Plan:** Disable bot by removing configuration or pausing via dashboard.
  - **Prerequisites:** G1.1.2 (label schema) and G1.2.3 (stable CI security pipeline).

- **Task S4.1.2 – Expand SAST & secret scanning coverage**
  - **Goal:** Add Bandit or Semgrep policies alongside detect-secrets baseline enforcement in pre-commit.
  - **Acceptance Criteria:** Tools integrated with manageable baselines; severity thresholds documented; CI fails on high findings with remediation guidance.
  - **Blast Radius:** Potential CI noise; developer friction.
  - **Rollback Plan:** Relax rule set or disable step temporarily while tuning.
  - **Prerequisites:** G1.2.3 (security automation foundation).

### Workstream S4.2 – Configuration & Data Safety *(Tags: security, reliability, DX)*
- **Task S4.2.1 – Replace manual config parsing with Pydantic settings**
  - **Goal:** Use Pydantic `BaseSettings` for schema validation, secrets management, and test overrides.
  - **Acceptance Criteria:** New config module retains backwards compatibility; migration guide documents env var changes; feature flag enables rollback; strict typing maintained.
  - **Blast Radius:** Application-wide configuration behaviour.
  - **Rollback Plan:** Toggle feature flag to legacy loader or revert commit.
  - **Prerequisites:** T2.1.1 (strict typing) and T2.2.2 (modular architecture).

- **Task S4.2.2 – Harden CSV upload validation and optional malware scanning**
  - **Goal:** Add schema validation (pandera or Pydantic) and antivirus integration hook to the upload pipeline.
  - **Acceptance Criteria:** Upload path rejects malformed/malicious files with precise error messages; tests cover success/failure; docs describe enabling AV hook.
  - **Blast Radius:** User-facing uploads; risk of false positives.
  - **Rollback Plan:** Guard with feature flag or revert until tuned.
  - **Prerequisites:** S4.2.1 (config toggles) and Q3.1.1 (test harness).

### Workstream S4.3 – Releases & Distribution *(Tags: DX, reliability, security)*
- **Task S4.3.1 – Automate semantic releases**
  - **Goal:** Use Commitizen or semantic-release to generate changelog, tag releases, and publish artifacts/SBOM on tags.
  - **Acceptance Criteria:** Release workflow runs on tagged commits; CHANGELOG updates automatically; docs include release checklist with rollback guidance.
  - **Blast Radius:** Release pipeline; requires secretless publication (OIDC).
  - **Rollback Plan:** Disable workflow and revert automated changelog updates.
  - **Prerequisites:** G1.2.2 (Conventional Commits) and G1.2.3 (stable CI).

- **Task S4.3.2 – Harden Docker image with multi-stage build & scanning**
  - **Goal:** Reduce attack surface (distroless or slim runtime), ensure health check parity, and integrate Trivy scanning.
  - **Acceptance Criteria:** Dockerfile uses builder/runtime stages; `make security` (and CI) run Trivy; health probe script reused; docs updated with deployment considerations.
  - **Blast Radius:** Deployment runtime; container registries.
  - **Rollback Plan:** Revert to previous Dockerfile or pin prior image tag.
  - **Prerequisites:** O3.2.2 (health script) and S4.1.1–S4.1.2 (automated scanning).

## 6. Milestone 5 – Performance & Resilience *(Stretch Goals)*

### Workstream P5.1 – Performance Benchmarking *(Tags: performance, testing)*
- **Task P5.1.1 – Add micro-benchmarks for metrics pipeline**
  - **Goal:** Measure `normalize_columns` and `compute_metrics` throughput to detect regressions during refactors.
  - **Acceptance Criteria:** Benchmarks implemented via `pytest-benchmark` or `asv`; baseline committed; docs explain interpreting results.
  - **Blast Radius:** Additional tooling dependencies.
  - **Rollback Plan:** Remove benchmark suite if maintenance exceeds value.
  - **Prerequisites:** T2.2.2 (modular services) for isolated benchmarking.

- **Task P5.1.2 – Surface cache metrics and eviction tuning**
  - **Goal:** Track cache hit/miss ratios, TTL effectiveness, and optionally allow runtime eviction/backoff policies.
  - **Acceptance Criteria:** Metrics emitted via observability stack; tests cover TTL/eviction behaviour; docs outline tuning strategies.
  - **Blast Radius:** Runtime caching behaviour; risk of stale data.
  - **Rollback Plan:** Disable metrics or revert caching changes.
  - **Prerequisites:** O3.2.1 (observability hooks) and S4.2.1 (config schema for toggles).

This plan is living documentation—update statuses, dependencies, and tasks as milestones progress. Each PR must reference its task identifier and update `STATUS.md` upon completion.
