# Complete the post-v0.4.0 all-files CI contract

This ExecPlan is a living document. Maintain it in accordance with `.agent/PLANS.md`, including the `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` sections as work proceeds.

## Purpose / Big Picture

The repository currently has a strong quality gate, but its proposed all-files pre-commit gate is not yet idempotent: hosted CI correctly detects historical whitespace and end-of-file drift and reviewed synthetic privacy/security fixtures. After this work, a contributor can run the literal command `pre-commit run --all-files` from the repository root and receive a clean result twice in succession, while hosted CI enforces the same contract before the existing quality gate. Secret detection must remain strict; only reviewed synthetic fixtures and the deterministic snapshot digest field may receive narrow, auditable treatment.

Success is visible when PR #121 remains limited to CI, hook configuration, deliberate formatting corrections, narrow fixture annotations, and this plan; exact-head hosted CI then passes the all-files hook stage, the complete quality gate, and coverage upload.

## Progress

- [x] (2026-08-28) Merged workspace-governance PR #131 and verified post-merge CI #338 on signed `main` commit `d3c4df63ab0e473642f75a9060705f074eddefeb`.
- [x] (2026-08-28) Incorporated exact current `main` into draft PR #121 without force and preserved the published v0.4.0 records.
- [x] (2026-08-28) Kept root and compatibility pre-commit configurations byte-identical, disabled checkout credential persistence, and added only the narrow deterministic `csv_sha256` line exclusion.
- [x] (2026-08-28) Observed CI #339 at connector checkpoint `e1fef1d087c8ebc7276d4b9164acc13e6632fa31`; configuration parity, Black, Ruff, Codespell, and mypy passed, while the expected whitespace/EOF modifications and reviewed synthetic-fixture findings blocked the all-files gate.
- [ ] Create a clean disposable Python 3.13 checkout at the exact remote PR head without touching protected or retained local paths.
- [ ] Apply only the hook-generated whitespace/EOF corrections reported by the exact current all-files run.
- [ ] Add official inline `pragma: allowlist secret` comments only to the synthetic fixture lines reported by detect-secrets.
- [ ] Prove the reviewed secret baseline remains byte-identical and no detector, entropy threshold, or broad path exclusion changed.
- [ ] Run pre-commit 4.6.1 twice successfully with no second-run change.
- [ ] Run focused fixture tests, the complete quality gate, security/dependency checks, coverage, benchmark, and Docker-relevant validation.
- [ ] Update this plan with exact local evidence, commit coherently, rerun the final exact-head gate, and push normally without force.
- [ ] Observe fresh hosted CI on the final pushed head and leave PR #121 draft for a separate owner-controlled merge decision.
- [ ] Reconcile every task-created workspace and artifact under the root `AGENTS.md` gate.

## Surprises & Discoveries

- Observation: The dependency version itself is not the blocker. Historical validation passed installation, Black, Ruff, mypy, tests, benchmark, security checks, and runtime coverage; the failure is the newly enforced all-files contract.
  Evidence: CI #339 reached the all-files stage after successful dependency installation and configuration parity, then passed Black, Ruff, Codespell, and mypy.

- Observation: The narrow `csv_sha256` exclusion works as intended.
  Evidence: CI #339 no longer reported `data/industry_pulse_bls_snapshot.metadata.json`; only synthetic test fixtures remained.

- Observation: Standard hooks identify finite repository hygiene corrections rather than runtime changes.
  Evidence: CI #339 reported two trailing-whitespace files and twelve end-of-file files, all documentation/configuration/governance paths.

- Observation: The reviewed baseline must not be regenerated on Windows.
  Evidence: An earlier rejected attempt produced platform-specific paths, self-findings, and an unexplained stale-entry removal. The branch retains the valid reviewed baseline.

## Decision Log

- Decision: Treat PR #121 as a CI-contract remediation rather than a blind Dependabot bump.
  Rationale: The literal all-files command exposed repository configuration and hygiene defects that hosted CI previously did not exercise.
  Date/Author: 2026-08-12 / project owner and connector.

- Decision: Preserve `config/.secrets.baseline` exactly and use inline official allowlist comments for reviewed synthetic fixtures.
  Rationale: Regenerating the baseline would obscure review history and risks platform-specific drift; inline comments keep each false positive local and auditable.
  Date/Author: 2026-08-12 / project owner and connector.

- Decision: Exclude only a line matching the deterministic JSON field `csv_sha256` with a 64-character lowercase hexadecimal value.
  Rationale: The digest is reproducible release metadata, not a secret. A line-level pattern avoids excluding `data/`, tests, detectors, or entropy classes.
  Date/Author: 2026-08-28 / connector.

- Decision: Use a new disposable checkout and do not reuse the retained dirty PR #121 remediation clone.
  Rationale: The retained clone contains prior uncommitted hook output and is protected evidence; a fresh checkout produces an auditable exact-head result.
  Date/Author: 2026-08-28 / connector.

## Outcomes & Retrospective

The connector phase is complete. PR #121 is current with signed `main`, remains draft, and has a bounded exact failure. Local remediation, exact-head validation, and safe workspace reconciliation remain. At completion, summarize the final changed files, all-files idempotence proof, security posture, quality/coverage results, hosted CI identity, and any retained workspace or limitation.

## Context and Orientation

Issue #134 coordinates post-v0.4.0 hardening. Phase one merged root `AGENTS.md`, which governs all local workspace and artifact handling. Phase two is this plan and draft PR #121 on branch `dependabot/pip/pre-commit-gte-4.6.1-and-lt-5`.

The key files are:

- `.github/workflows/ci.yml`, which installs dependencies, verifies config parity, runs all hooks, then runs `make quality-gate`;
- `.pre-commit-config.yaml`, the canonical root configuration;
- `config/.pre-commit-config.yaml`, an intentionally byte-identical compatibility copy;
- `config/.secrets.baseline`, the reviewed detect-secrets baseline that must remain unchanged;
- `requirements-dev.txt`, which requires pre-commit `>=4.6.1,<5`;
- `Makefile`, whose `quality-gate` runs formatting, linting, mypy, runtime and full-source coverage, benchmark, vulnerability audit, and secret scanning;
- the synthetic privacy/security tests reported by CI #339;
- this ExecPlan, which records the exact remediation and evidence.

At connector checkpoint `e1fef1d087c8ebc7276d4b9164acc13e6632fa31`, CI #339 reported these standard-hook corrections:

- trailing whitespace: `.agent/execplans/ExecPlan.md`, `.agent/PLANS.md`;
- end-of-file normalization: `.agent/execplans/universal_stage1_overhaul.md`, `.gitattributes`, `docs/execplans/architecture-alignment.md`, `config/.editorconfig`, `.agent/execplans/repository_cleanup_restructure.md`, `REPORTS/000_CONTEXT.md`, `docs/execplans/observability-remote-shipping.md`, `docs/execplans/snapshot-replication-future-proofing.md`, `AGENTS.md`, `.agent/EXEC_PLAN.md`, `.agent/execplans/stage1_snapshot_persistence.md`, and `REPORTS/001_DIAGNOSIS.md`.

The same run reported eleven findings on nine synthetic test-fixture files:

- `tests/test_streamlit_provenance.py`;
- `tests/test_config.py` at the synthetic credential URL and password assertion;
- `tests/test_evaluation_lineage.py`;
- `tests/test_lineage.py` at the synthetic metadata and credential-bearing URL cases;
- `tests/test_lineage_exports.py`;
- `tests/test_application.py`;
- `tests/test_scenario_planner.py`;
- `tests/test_core.py`;
- `tests/test_streamlit_components.py`.

These fixtures deliberately test redaction, rejection, or non-propagation. Review each exact line before adding `# pragma: allowlist secret`. Do not annotate unrelated lines or whole files.

## Plan of Work

First create a fresh independent clone outside the protected checkout and verify the exact remote `main` and PR branch heads. Read root `AGENTS.md` and this plan before changing anything. Create and activate a Python 3.13 virtual environment, install repository requirements, and explicitly install pre-commit 4.6.1 so the minimum supported version—not merely the newest compatible version—executes the system-language hooks.

Run the literal all-files command once. Review its modifications against the exact list above. Retain only mechanical whitespace and end-of-file changes; stop if source behavior, release records, snapshots, or an unexpected file changes. Review each detect-secrets finding and append the official inline allowlist comment only where the value is clearly synthetic and the test proves redaction, rejection, or non-propagation.

Do not regenerate or edit `config/.secrets.baseline`. Do not broaden the existing line exclusion. Do not exclude `tests/`, `data/`, a detector, or an entropy class. Keep both pre-commit config files byte-identical.

Run all hooks again. Address any newly reported finding using the same narrow review standard. Once the run passes, run it a second time and prove `git status` and `git diff` are unchanged. Run the focused tests for every annotated fixture file, then run the complete repository gate and supporting checks. Update this plan with exact evidence before the final evidence commit. After that commit, rerun the complete final gate on the exact final SHA and make no further commit.

Push normally without force. Keep PR #121 draft. Observe current-head hosted CI if authenticated inspection is available, but never merge, mark ready, enable auto-merge, modify the published tag/release, or touch PRs #117 and #122.

## Concrete Steps

Work only in the new disposable clone. Record exact commands and outputs in this plan as they are executed.

Create and activate the environment, then install dependencies:

    py -3.13 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt -r requirements-dev.txt
    python -m pip install "pre-commit==4.6.1"
    python -m pip check
    pre-commit --version

Require `pre-commit 4.6.1`.

Verify config and baseline invariants before and after remediation:

    git diff --no-index --exit-code -- .pre-commit-config.yaml config/.pre-commit-config.yaml
    git hash-object config/.secrets.baseline

The baseline blob must remain `66b02a83380b2742fe31ee2d8902cc1973ec7e67` throughout local work.

Run the modifying hook pass and inspect the diff:

    pre-commit run --all-files --show-diff-on-failure --color=always
    git status --short --untracked-files=all
    git diff --stat
    git diff

After reviewed annotations and mechanical corrections, prove idempotence:

    pre-commit run --all-files --show-diff-on-failure --color=always
    git diff --exit-code
    pre-commit run --all-files --show-diff-on-failure --color=always
    git diff --exit-code

The two final hook runs must pass and the second must make no change.

Run focused tests for all annotated fixture files, then the full gate. Use `make quality-gate` when GNU Make is available. If it is unavailable, run the exact current Makefile constituents individually and report that the aggregate target was not run. Also run `python -m pip check`, the configured pip-audit command, the baseline-backed detect-secrets hook, and `git diff --check`.

## Validation and Acceptance

Acceptance requires all of the following on the exact final commit:

- root and compatibility pre-commit configurations are byte-identical;
- checkout credential persistence is disabled in CI;
- `config/.secrets.baseline` has the original blob identity and unchanged detector/filter policy;
- the only global secret-scan exception is the exact deterministic `csv_sha256` line pattern;
- every fixture allowlist is inline, reviewed, and limited to a synthetic value used by a privacy/security test;
- all hook-generated formatting changes are mechanical and confined to the exact reviewed paths;
- pre-commit 4.6.1 passes twice with no second-run modification;
- focused fixture tests pass;
- Black, Ruff, mypy, full pytest, runtime coverage, full-source coverage, benchmark, pip check, pip-audit, detect-secrets, and diff checks pass;
- runtime combined coverage remains at or above the repository's 85% threshold;
- Docker-relevant validation passes when locally available, or the limitation is reported accurately;
- the final branch is clean, pushed normally, current with `main`, and PR #121 remains draft;
- fresh hosted CI passes the configuration-parity step, all-files hooks, complete quality gate, and coverage upload before any merge recommendation.

## Idempotence and Recovery

The hook command is intentionally repeatable. The first run may make reviewed mechanical corrections; subsequent runs must be clean. If an unexpected file changes, restore only that file from the known starting branch in the disposable clone and investigate—never reset, clean, force-push, or touch the protected checkout.

If the remote branch or `main` moves, stop and report the exact SHAs rather than rebasing, resetting, or force-updating. If local cleanup is blocked, retain the task-owned workspace and report its precise state; do not change ACLs or ownership and do not use force retries.

## Artifacts and Notes

Durable evidence belongs in this plan and the PR conversation. Temporary virtual environments, caches, coverage files, reports, and hook repositories remain local and must be inventoried before normal exact-path cleanup. Do not commit private paths, credentials, environment dumps, or generated security reports.

## Interfaces and Dependencies

This slice changes no product API or runtime behavior. It preserves Python 3.13, package version 0.4.0, the published v0.4.0 tag/release, existing tests, and runtime dependencies. The relevant tooling interfaces are pre-commit `>=4.6.1,<5`, Black, Ruff, mypy, pytest/pytest-cov, detect-secrets 1.5, pip-audit, GNU Make when available, and the existing GitHub Actions workflow pinned to full-length action SHAs.
