# Complete the post-v0.4.0 all-files CI contract

This ExecPlan is a living document. Maintain it in accordance with `.agent/PLANS.md`, including the `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` sections as work proceeds.

## Purpose / Big Picture

This work makes the repository's all-files pre-commit contract real, cross-platform, idempotent, and enforced before the existing hosted quality gate. A contributor can run the literal command `pre-commit run --all-files` from the repository root and receive a clean result twice in succession, while hosted CI runs the same contract before `make quality-gate`.

The security boundary remains strict. The reviewed detect-secrets baseline is not regenerated during remediation; synthetic privacy/security fixtures receive exact-line official allowlist comments, and deterministic snapshot digest metadata receives one narrow line exclusion. No broad test, data, detector, or entropy-class exclusion is permitted.

The implementation and local remediation completed at branch commit `360cf769f7065800efe7fddd0c1081219a678321`. Exact-head CI #341 and Docker Smoke #171 passed on that commit. A later documentation-only connector correction reconciles this living record; the PR checks and conversation are canonical for the exact final branch head produced by that correction.

## Progress

- [x] (2026-08-28) Squash-merged workspace-governance PR #131 and verified post-merge CI #338 on signed `main` commit `d3c4df63ab0e473642f75a9060705f074eddefeb`.
- [x] (2026-08-28) Incorporated exact current `main` into draft PR #121 without force and preserved the published v0.4.0 records.
- [x] (2026-08-28) Added the canonical root pre-commit configuration, kept the compatibility copy byte-identical, disabled checkout credential persistence, and added only the narrow deterministic `csv_sha256` line exclusion.
- [x] (2026-08-28) Used hosted failures #339 and #340 to identify the finite all-files remediation: fourteen mechanical whitespace/end-of-file corrections and reviewed synthetic fixture findings.
- [x] (2026-08-28) Applied only the fourteen reported mechanical corrections.
- [x] (2026-08-28) Added official inline `pragma: allowlist secret` comments to fourteen exact synthetic fixture lines: the eleven initially reported findings plus three duplicate-value occurrences exposed sequentially by detect-secrets.
- [x] (2026-08-28) Preserved baseline blob `66b02a83380b2742fe31ee2d8902cc1973ec7e67` throughout final local remediation and retained every detector, filter, entropy threshold, secret hash, verification flag, and line number.
- [x] (2026-08-28) Added `src/scripts/detect_secrets_check.py`, which scans through detect-secrets 1.5.0 using a disposable baseline copy, propagates genuine finding failures, and accepts only exit code 3 after a clean comparison so reviewed baseline metadata is not rewritten.
- [x] (2026-08-28) Added the typing-only `cast(Any, row.signal_value)` at the existing float conversion to satisfy mypy 2.3.1 without changing runtime output or control flow.
- [x] (2026-08-28) Proved pre-commit 4.6.1 idempotence with two successful final-head runs and unchanged status/diff state.
- [x] (2026-08-28) Passed 107 focused fixture tests, 461 complete tests, all direct quality/security constituents, the runtime coverage gate, full-source coverage, benchmark, pip check, pip-audit, detect-secrets, and `git diff --check`.
- [x] (2026-08-28) Pushed final local implementation/evidence commit `360cf769f7065800efe7fddd0c1081219a678321` normally without force and retained PR #121 as draft.
- [x] (2026-08-28) Verified exact-head CI #341 and Docker Smoke #171 passed on `360cf769f7065800efe7fddd0c1081219a678321`.
- [x] (2026-08-28) Reconciled the final diff, baseline delta, wrapper semantics, fixture annotations, review state, release parity, and this living record through the GitHub connector.
- [ ] Observe fresh hosted checks on the documentation-only connector head and keep PR #121 draft until a separate owner-controlled ready/merge authorization.
- [ ] After an authorized merge, verify resulting `main`, push-triggered checks, preserved v0.4.0 tag/release identity, issue #134 progress, and task-owned workspace disposition.

## Surprises & Discoveries

- Observation: The dependency version itself was not the blocker.
  Evidence: Hosted failures reached the all-files stage after successful installation, configuration parity, Black, Ruff, Codespell, and mypy; the finite failures were repository hygiene and synthetic fixtures.

- Observation: The narrow `csv_sha256` exclusion works as intended.
  Evidence: After the exact line pattern was added, committed snapshot digests were no longer reported while synthetic fixture findings continued to fail the hook.

- Observation: Standard hooks identified finite repository hygiene corrections rather than runtime changes.
  Evidence: Two trailing-whitespace files and twelve end-of-file files were confined to documentation, configuration, governance, and historical planning paths.

- Observation: The baseline delta against `main` is path normalization, not policy or finding drift.
  Evidence: Keys and `filename` values change only from Windows `\` separators to repository-standard `/`; plugins, filters, thresholds, hashes, verification flags, and line numbers remain identical.

- Observation: Detect-secrets 1.5.0 reports only the first unallowlisted occurrence of an identical secret value in a file.
  Evidence: Three additional exact synthetic lines appeared sequentially after the original findings were annotated; each containing test proves redaction, rejection, bounded serialization, or non-propagation.

- Observation: The stock baseline-backed hook returns exit code 3 after a clean comparison when it wants to refresh baseline metadata.
  Evidence: The official 1.5.0 hook returns 1 for new secrets, 3 for a baseline update, and 0 for a clean unchanged baseline. The wrapper uses a disposable copy, maps only 3 to success, and propagates all other exit codes.

- Observation: The current allowed mypy 2.3.1 is stricter about pandas tuple scalar typing.
  Evidence: It rejected `float(row.signal_value)` because `itertuples()` exposes a broad scalar union; an `Any` cast at the existing conversion restored a clean 114-source-file result without runtime change.

## Decision Log

- Decision: Treat PR #121 as a CI-contract remediation rather than a blind Dependabot bump.
  Rationale: The literal all-files command exposed repository configuration and hygiene defects that hosted CI previously did not exercise.
  Date/Author: 2026-08-12 / project owner and connector.

- Decision: Preserve the reviewed baseline during final remediation and use inline official allowlist comments for reviewed synthetic fixtures.
  Rationale: Regenerating the baseline would obscure review history and risks platform-specific metadata drift; inline comments keep each false positive local and auditable.
  Date/Author: 2026-08-12 / project owner and connector.

- Decision: Normalize baseline repository paths from `\` to `/` while preserving all findings and policy.
  Rationale: Forward-slash repository paths make the baseline portable across Windows and Linux without changing what is allowed.
  Date/Author: 2026-08-12 / branch history, verified 2026-08-28 by connector.

- Decision: Exclude only a line matching the deterministic JSON field `csv_sha256` with a 64-character lowercase hexadecimal value.
  Rationale: The digest is reproducible release metadata, not a secret. A line-level pattern avoids excluding `data/`, tests, detectors, or entropy classes.
  Date/Author: 2026-08-28 / connector.

- Decision: Run baseline-backed secret detection through `src/scripts/detect_secrets_check.py` using a temporary copy of the reviewed baseline.
  Rationale: This preserves strict new-finding failures while preventing platform and line-number metadata refreshes from mutating the reviewed baseline.
  Date/Author: 2026-08-28 / Codex, independently reviewed by connector.

- Decision: Add a typing-only cast at the existing float conversion rather than pinning or weakening mypy.
  Rationale: The cast documents the already validated numeric runtime invariant, changes no output or control flow, and keeps the declared `mypy>=2.3.0,<3` range valid under 2.3.1.
  Date/Author: 2026-08-28 / Codex, independently reviewed by connector.

## Outcomes & Retrospective

Phase two's implementation is complete. At exact implementation/evidence head `360cf769f7065800efe7fddd0c1081219a678321`, pre-commit 4.6.1 passed twice with no second-run change, 107 focused tests passed, and the complete suite passed 461 tests in both runtime and full-source coverage modes. Local runtime coverage was 7,594 of 8,344 lines (91.01%), 1,597 of 2,144 branches (74.49%), and 87.63% combined, above the 85% gate. Full-source coverage was 8,903 of 10,376 lines (85.80%) and 1,836 of 2,692 branches (68.20%).

Black left 167 files unchanged, Ruff passed, mypy passed on 114 source files, pip-audit found no known vulnerabilities, pip check found no broken requirements, the non-mutating baseline-backed secret scan passed, configuration parity passed, baseline identity remained `66b02a83380b2742fe31ee2d8902cc1973ec7e67`, and `git diff --check` passed. Local benchmark medians were 0.0057 seconds for 100 rows against 0.50 seconds, 0.0115 seconds for 10,000 rows against 2.00 seconds, and 0.0649 seconds for 100,000 rows against 10.00 seconds.

GNU Make was unavailable locally, so `make quality-gate` was not run there; every current constituent ran directly. Local Docker was unavailable. Hosted CI #341 subsequently ran the literal all-files gate, `make quality-gate`, 461 runtime tests, 461 full-source tests, coverage upload, benchmark, dependency audit, and secret scan successfully. Hosted Docker Smoke #171 built the image, verified the non-root runtime user, exercised Streamlit and API modes, uploaded evidence, and removed its containers successfully.

The published v0.4.0 tag and GitHub prerelease remain unchanged. PR #121 remains open, draft, mergeable, unmerged, current with `main`, and free of submitted reviews or inline review threads at the implementation-head audit. The task-owned disposable checkout is retained clean for review with only generated ignored content; protected and historical retained paths remain untouched.

The connector found one documentation defect after the successful implementation-head checks: this living plan still described final push, hosted checks, and reconciliation as pending. The documentation-only connector correction resolves that defect. Fresh hosted checks on the corrected head are required before the owner receives an exact-head merge recommendation.

## Context and Orientation

Issue #134 coordinates post-v0.4.0 hardening. Phase one merged root `AGENTS.md`, which governs local workspace and artifact handling. Phase two is draft PR #121 on branch `dependabot/pip/pre-commit-gte-4.6.1-and-lt-5`.

The key files are:

- `.github/workflows/ci.yml`, which installs dependencies, verifies config parity, runs all hooks, then runs `make quality-gate`;
- `.pre-commit-config.yaml`, the canonical root configuration;
- `config/.pre-commit-config.yaml`, an intentionally byte-identical compatibility copy;
- `config/.secrets.baseline`, the reviewed portable baseline;
- `src/scripts/detect_secrets_check.py`, the non-mutating baseline-check wrapper;
- `requirements-dev.txt`, which requires pre-commit `>=4.6.1,<5`;
- `Makefile`, whose `quality-gate` runs formatting, linting, mypy, runtime and full-source coverage, benchmark, vulnerability audit, and secret scanning;
- the synthetic privacy/security tests carrying exact-line allowlist comments;
- this ExecPlan, which records the remediation and evidence.

The mechanical corrections are confined to `.agent/execplans/ExecPlan.md`, `.agent/PLANS.md`, `.agent/execplans/universal_stage1_overhaul.md`, `.gitattributes`, `docs/execplans/architecture-alignment.md`, `config/.editorconfig`, `.agent/execplans/repository_cleanup_restructure.md`, `REPORTS/000_CONTEXT.md`, `docs/execplans/observability-remote-shipping.md`, `AGENTS.md`, `.agent/EXEC_PLAN.md`, `docs/execplans/snapshot-replication-future-proofing.md`, `.agent/execplans/stage1_snapshot_persistence.md`, and `REPORTS/001_DIAGNOSIS.md`.

The exact annotated synthetic fixture locations at implementation head are `tests/test_lineage.py:63`, `:81`, `:106`, and `:181`; `tests/test_config.py:311` and `:323`; `tests/test_evaluation_lineage.py:89`; `tests/test_scenario_planner.py:139`; `tests/test_streamlit_provenance.py:30`; `tests/test_application.py:96`; `tests/test_lineage_exports.py:31`; `tests/test_core.py:201` and `:202`; and `tests/test_streamlit_components.py:131`.

## Plan of Work

The implementation work is complete. The remaining workflow is connector and owner controlled:

1. Verify the documentation-only correction is the sole delta after `360cf769f7065800efe7fddd0c1081219a678321`.
2. Confirm the PR remains current with `main`, mergeable, draft, and free of blocking reviews or unresolved threads.
3. Require fresh exact-head CI and Docker Smoke on the corrected head.
4. Reconfirm the v0.4.0 annotated tag object, peeled release commit, and GitHub prerelease are unchanged.
5. Update the PR and issue with the exact final audit result.
6. Present a separate owner-controlled exact-head ready/squash-merge instruction.
7. After merge, verify the resulting signed `main`, push-triggered checks, issue #134 progress, and safe cleanup disposition.

## Concrete Steps

The local implementation used Python 3.13 and an activated task-owned virtual environment with exact pre-commit 4.6.1. The canonical commands are:

    python -m pip install -r requirements.txt -r requirements-dev.txt
    python -m pip install "pre-commit==4.6.1"
    pre-commit --version
    pre-commit run --all-files --show-diff-on-failure --color=always
    pre-commit run --all-files --show-diff-on-failure --color=always
    python -m pytest -q tests/test_lineage.py tests/test_config.py tests/test_evaluation_lineage.py tests/test_scenario_planner.py tests/test_streamlit_provenance.py tests/test_application.py tests/test_lineage_exports.py tests/test_core.py tests/test_streamlit_components.py
    python -m black --check app.py src tests
    python -m ruff check app.py src tests
    python -m mypy src
    python -m pytest -q --cov=src/adapters --cov=src/agents --cov=src/application --cov=src/core --cov=src/extensions --cov=src/infrastructure --cov=src/interfaces/api --cov=src/interfaces/streamlit --cov-report=term-missing --cov-report=xml --cov-fail-under=85
    python -m pytest -q --cov=src --cov-report=term-missing --cov-report=xml
    python src/scripts/benchmark_metrics.py --check
    python -m pip_audit -r requirements.txt -r requirements-dev.txt
    python src/scripts/detect_secrets_check.py --baseline config/.secrets.baseline --exclude-lines '^\s*"csv_sha256":\s*"[0-9a-f]{64}",?\s*$'
    python -m pip check
    git diff --check

Configuration and baseline invariants are checked with:

    git diff --no-index --exit-code -- .pre-commit-config.yaml config/.pre-commit-config.yaml
    git hash-object config/.secrets.baseline

The expected baseline blob is `66b02a83380b2742fe31ee2d8902cc1973ec7e67`.

## Validation and Acceptance

Acceptance requires:

- root and compatibility pre-commit configurations are byte-identical;
- checkout credential persistence is disabled in CI;
- the baseline has repository-standard paths and unchanged policy/findings;
- the only global secret-scan exception is the exact deterministic `csv_sha256` line pattern;
- every fixture allowlist is inline, reviewed, and limited to a synthetic value used by a privacy/security test;
- all hook-generated formatting changes are mechanical and confined to the reviewed paths;
- pre-commit 4.6.1 passes twice with no second-run modification;
- focused fixture tests pass;
- Black, Ruff, mypy, full pytest, runtime coverage, full-source coverage, benchmark, pip check, pip-audit, detect-secrets, and diff checks pass;
- runtime combined coverage remains at or above 85%;
- hosted CI passes configuration parity, all-files hooks, `make quality-gate`, and coverage upload on the exact final PR head;
- hosted Docker Smoke passes on the exact final PR head;
- the PR is current with `main`, mergeable, review-clean, and remains draft until explicit owner authorization;
- the published v0.4.0 tag and release remain unchanged.

## Idempotence and Recovery

The hook command is repeatable. A clean repository produces no change on successive runs. The wrapper writes only a temporary baseline copy and removes it in a `finally` block. It propagates new-secret and operational failures and maps only detect-secrets' baseline-update exit code 3 to success after a clean comparison.

If the PR branch or `main` moves unexpectedly, stop and audit the exact SHAs rather than resetting, rebasing, or forcing. If cleanup is blocked, retain the task-owned workspace and report its exact state; do not change ACLs or ownership and do not use force retries.

## Artifacts and Notes

The task-owned local environment used Python 3.13.7, pip 26.2.1, pre-commit 4.6.1, Black 26.5.1, Ruff 0.16.5, mypy 2.3.1, pytest 9.1.1, pytest-cov 7.1.0, coverage 7.15.4, detect-secrets 1.5.0, and pip-audit 2.10.1.

Temporary virtual environments, caches, coverage files, reports, hook repositories, and logs remain local generated artifacts. The retained task-owned checkout is not evidence of unpushed work: its tracked and untracked status was clean, the exact implementation head was remotely preserved, task processes were stopped, and generated ignored content was inventoried. Cleanup remains subject to root `AGENTS.md` and must not touch the protected primary checkout or historical retained recovery/remediation paths.

Durable final exact-head hosted evidence belongs in the PR and issue conversation because recording a completed post-push run inside the same commit would create another head and another validation cycle.

## Interfaces and Dependencies

This slice changes no product API or intended runtime behavior. It preserves Python 3.13, package version 0.4.0, the published v0.4.0 tag/release, runtime dependencies, provider data, snapshots, mappings, analytics, and UI behavior.

The relevant tooling interfaces are pre-commit `>=4.6.1,<5`, Black, Ruff, mypy, pytest/pytest-cov, detect-secrets 1.5.0, pip-audit, GNU Make in hosted CI, and the existing GitHub Actions workflows pinned to full-length action SHAs.
