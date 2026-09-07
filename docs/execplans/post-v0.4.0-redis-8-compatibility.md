# Complete Redis 8 compatibility and failure-contract validation

This ExecPlan is a living document. Maintain `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

Issue #134 coordinates post-v0.4.0 hardening. Workspace governance and the all-files quality contract are complete. Draft PR #135 validates the optional Redis rate limiter, including its Lua script, which updates shared token state atomically on the server. Users should receive truthful degraded-health signals and reach the existing memory fallback without inheriting an uncontrolled library retry policy.

The branch is `chore/redis-8-fakeredis-compatibility` in `Nobodyworld/app-industry-resilience`. Its base is `53d404b2e6624d55b36ac6320547613b95ada469`. The first correction commit is `31a690ee1bdbe1fdc6dd335d734d6812e5965e5c`; the final accepted head must be taken from the current PR and the operator handoff, never inferred from this historical checkpoint. Published v0.4.0 remains at `eec9886c5f0a4ef495b6b31c3c2cc6cdc52e631a` and must not be changed.

## Progress

- [x] (2026-08-28) Workspace-governance PR #131 merged as `d3c4df63ab0e473642f75a9060705f074eddefeb`; PR and post-merge CI passed.
- [x] (2026-08-28) All-files PR #121 merged as `53d404b2e6624d55b36ac6320547613b95ada469`; CI #343 and Docker Smoke #173 passed on that exact base.
- [x] (2026-08-28) Combined the dependency intent of #117 (`redis>=8.1.0,<9`) and #122 (fakeredis 2.37.1 floor) into draft #135. Both source PRs were closed unmerged as superseded.
- [x] (2026-08-28) Initial head `cd246c180326324fc8e86f8ef46193015487922f` established that plain fakeredis lacked EVALSHA while the disposable real Redis 8.10.1 path passed.
- [x] (2026-08-28) Correction `17b9c67611933cabb00c52261fe1f59b177f344c` added development-only Lua support and import ordering; CI #346, Docker #175, and Redis Compatibility #2 passed with 44 focused tests.
- [x] (2026-08-28) Reconciled the dependency register and made minimum installation explicit at `e193f0c43f8d744db07c675b32e0bcc17e5b828b`; CI #348, Docker #177, and Redis Compatibility #4 passed. These results are historical, not evidence for later changes.
- [x] (2026-09-06) Owner authorized connector corrections before a concise local-only handoff. Added stable Redis-up metrics, explicit timeouts/zero retries, health-transition and production-client fault tests, and an installed-environment audit in `31a690ee1bdbe1fdc6dd335d734d6812e5965e5c`.
- [x] (2026-09-06) Updated the incident runbook, dependency contract, unreleased notes, completed publication bookkeeping, and PowerShell acceptance instructions. These documentation changes do not alter published release artifacts.
- [ ] Verify the final correction/documentation head with hosted Quality Gate, Docker Deployment Smoke, and Redis Compatibility. Record exact run/job identities in PR #135; do not treat in-progress checks as passed.
- [ ] Reproduce that exact final head in one isolated local Python 3.13 checkout, including minimum versions, focused tests, two clean all-files passes, and complete quality/security/coverage/benchmark gates.
- [ ] Run local real-Redis/Docker checks only when safely available; otherwise record NOT RUN and distinguish the hosted evidence.
- [ ] Return local evidence and workspace dispositions without editing tracked files, committing, pushing, or changing PR state. Report a reproduced blocker for correction rather than silently widening scope.
- [ ] Obtain a separate owner decision before marking ready or merging. Issue #134 remains open until final verification and workspace reconciliation are accounted for.

## Surprises & Discoveries

Plain fakeredis 2.37.1 installed successfully but could not execute EVALSHA, the command used by the registered Lua script. Adding `fakeredis[lua]` supplied lupa and exercised actual shared token state without adding a production dependency. The historical hosted job resolved redis 8.1.0, fakeredis 2.37.1, lupa 2.8, and a Redis 8.10.1 server.

Static review found a stale-health defect: a successful request set the gauge labelled `redis` to one; failure wrote a different sample labelled `redis-fallback`, leaving the first value intact. Tests previously asserted only that samples existed. The correction updates one stable Redis-labelled sample and verifies failure-first and success/failure/recovery sequences, request counters, warning/pass health, and cleared error state.

The production client previously inherited library retry and connection-timeout defaults. Lua token consumption changes server state, so a missing response does not prove the operation failed. The correction disables automatic retries and supplies explicit connection/read timeouts. Tests exercise the actual `_create_redis_client` path and inject lost responses after real server execution; they are not claims of a real network outage or a deployment latency service-level agreement.

Auditing requirements ranges can resolve versions different from those installed for minimum-version tests. The compatibility workflow now creates an isolated virtual environment, prints installed versions, and audits that environment with `python -m pip_audit --local --strict`. The requirements audit remains independently required. A failed or partial audit must be reported, not suppressed.

## Decision Log

On 2026-08-28, the owner/connector chose one combined compatibility PR instead of independently merging stale Redis and fakeredis updates. The exact floor from #117 was `redis>=8.1.0,<9`; #122's final closed provenance head was `32d70577a3d96d01c347eef3ff919a8bd61fea2b`. Lua support remains development-only. Existing async fakeredis smoke tests exercise dependency interoperability without introducing an async product interface.

On 2026-09-06, owner-authorized review corrections expanded this maintenance slice narrowly to the existing rate-limiter implementation. The earlier description of this PR as having no product-code changes is superseded: availability metric updates and client timeout/retry behavior intentionally change. Annual analysis, API contracts, UI, providers, mappings, snapshots, scores, version `0.4.0`, and the published tag/release remain unchanged.

Use `Retry(NoBackoff(), 0)` in the production client. Set both socket timeouts to the positive finite configured value, or 1.0 second when unset. The existing configuration field may remain `None` to mean the default. This prevents inherited retry backoff and avoids automatic replay after ambiguous script execution. It does not make the process-local fallback globally coordinated or provide exactly-once accounting. DNS, protocol handshakes, and multiple operations mean per-socket limits are not a total request deadline.

Local Codex owns machine-dependent reproduction and workspace inspection only. The connector owns remote code, workflow, issue, PR, and evidence reconciliation. The prior requirement for a documentation-only local evidence commit followed by another complete hosted cycle is superseded: return evidence against the unchanged tested SHA and attach it to PR #135. Do not create a new commit solely to embed its own validation result.

## Outcomes & Retrospective

The connector has implemented the review corrections on the existing branch and retained the draft/owner-merge boundary. Historical green results apply only to their recorded SHAs. Current hosted status must be verified in PR #135 before the final handoff; local Windows reproduction and pre-existing workspace state cannot be inferred from GitHub.

The acceptance gap is now narrowly defined: validate the final head locally and return evidence. Do not restart Industry Momentum implementation, v0.4.0 publication, or the already merged governance/all-files phases. Do not absorb unrelated Dependabot PRs into this slice.

## Context and Orientation

`src/infrastructure/rate_limiter.py` contains the in-memory and Redis token buckets, `RateLimiterService`, and the production Redis client factory. `src/core/config.py` parses Redis settings and exposes only credential-presence flags in public configuration summaries. `src/extensions/builtins/rate_limiting.py` registers metrics and a health component through the existing extension system.

`tests/test_redis_8_compatibility.py` covers exact-compatible dependencies, Redis-8-configured fakeredis, synchronous Lua/RESP3 behavior, disconnected fallback, asynchronous dependency smoke, and a real-server path. `tests/test_rate_limiter_metrics_and_redis_health.py` verifies exact gauge values, counters, and health across transitions. `tests/test_redis_failure_contract.py` verifies the production factory, timeout rejection, a refused connection, a stalled loopback response, and recovery after injected lost Lua replies with no replay. Real cases require `REDIS_COMPAT_URL`; tests delete only their own uniquely prefixed keys.

The relevant workflows are `.github/workflows/ci.yml`, `.github/workflows/docker-smoke.yml`, and `.github/workflows/redis-compatibility.yml`. External actions remain pinned to full SHAs. The Redis service tag is moving within major version 8; record its actual server version instead of treating the image as immutable.

## Plan of Work

### Milestone 1: establish exact local identity

Read root `AGENTS.md`, applicable nested guidance, and this plan. Inspect the primary checkout and existing worktrees/clones/stashes read-only. Preserve every pre-existing workspace, including ignored and untracked content. Use one task-owned independent disposable checkout outside the primary checkout and one evidence directory at most. Do not put private paths into repository documentation.

From the disposable checkout, verify origin identifies `Nobodyworld/app-industry-resilience`, branch is `chore/redis-8-fakeredis-compatibility`, HEAD equals the final handoff SHA and remote branch, and merge-base with `origin/main` equals `53d404b2e6624d55b36ac6320547613b95ada469`. Fetch only in the disposable checkout. Stop on unexpected remote movement or unrelated local changes; do not reset, clean, rebase, or force-update.

### Milestone 2: reproduce minimum installation and focused behavior

Create Python 3.13's virtual environment in the disposable checkout, install the exact Redis/fakeredis minimums together with both requirements files, and record Python, pip, redis, fakeredis, and lupa versions. Run pip check and the installed-environment audit with that interpreter. Run all six focused test modules. Without a real service, only the three real-server cases should skip; all socket, fake-server, metric, health, and configuration cases must pass.

A task-owned Redis 8 service may be supplied when Docker or an already approved local runtime is available. Never point `REDIS_COMPAT_URL` at production or user-owned data. Repeat the focused set with the service enabled, record the server version, and confirm exact-key cleanup. Do not call FLUSHALL or FLUSHDB or install new system services merely to complete this slice. Unavailable local Docker/Redis is NOT RUN, not PASS; evaluate exact-head hosted evidence separately.

### Milestone 3: complete local acceptance without code churn

Run all-files hooks twice. Both must pass and leave tracked content unchanged; report any changed file rather than committing an unexplained formatter change. Run the exact current Makefile quality constituents, installed and requirements audits, pip check, and diff checks. Runtime combined coverage must be at least 85%; full-source coverage remains informational. Use local Docker smoke only where safely available.

Return a concise report with exact checkout/branch/HEAD/upstream/base identities, commands and outcomes, dependency versions, coverage scopes, skips and limitations, and root-AGENTS workspace reconciliation evidence. No tracked-file edit, commit, push, ready transition, merge, issue closure, or tag/release change belongs to this local handoff.

## Concrete Steps

Use PowerShell from the disposable repository root. Execute commands one at a time and inspect `$LASTEXITCODE`; stop and report nonzero results. The following commands deliberately avoid Bash continuation syntax.

    git remote get-url origin
    git branch --show-current
    git rev-parse HEAD
    git status --short --untracked-files=all
    git worktree list --porcelain
    git fetch origin main chore/redis-8-fakeredis-compatibility
    git rev-parse origin/main
    git rev-parse origin/chore/redis-8-fakeredis-compatibility
    git merge-base HEAD origin/main

Create and inspect the environment:

    py -3.13 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt -r requirements-dev.txt "redis==8.1.0" "fakeredis[lua]==2.37.1"
    python -m pip check
    python -c "import sys; from importlib.metadata import version; print(sys.version); print({p: version(p) for p in ('pip', 'redis', 'fakeredis', 'lupa')})"
    python -m pip list --format=json
    python -m pip_audit --local --strict
    python -m pytest -q tests/test_redis_8_compatibility.py tests/test_redis_failure_contract.py tests/test_rate_limiter.py tests/test_rate_limiter_metrics_and_redis_health.py tests/test_rate_limiting_health_probe.py tests/test_config.py

Ensure no inherited `REDIS_COMPAT_URL` targets another service before testing. Set the variable only after proving task ownership. Restore any previous process-environment setting afterward, and keep URLs with credentials out of logs.

Run all-files hooks twice and inspect status after each:

    pre-commit run --all-files --show-diff-on-failure --color=always
    git status --short --untracked-files=all
    pre-commit run --all-files --show-diff-on-failure --color=always
    git status --short --untracked-files=all

Run `make quality-gate` when GNU Make and its required shell are available. Otherwise report that aggregate command as NOT RUN and execute the current Makefile constituents individually. At this checkpoint the PowerShell-compatible equivalents are:

    python -m black --check app.py src tests
    python -m ruff check app.py src tests
    python -m mypy src
    python -m pytest --cov=src/adapters --cov=src/agents --cov=src/application --cov=src/core --cov=src/extensions --cov=src/infrastructure --cov=src/interfaces/api --cov=src/interfaces/streamlit --cov-report=term-missing --cov-report=xml --cov-fail-under=85
    python -m pytest --cov=src --cov-report=term-missing --cov-report=xml
    python src/scripts/benchmark_metrics.py --check
    python -m pip_audit -r requirements.txt -r requirements-dev.txt
    python src/scripts/detect_secrets_check.py --baseline config/.secrets.baseline --exclude-lines '^\s*"csv_sha256":\s*"[0-9a-f]{64}",?\s*$'
    python -m pip check
    git diff --check

Keep runtime/full-source coverage results distinct before the second command overwrites `coverage.xml`. Reconfirm that HEAD and tracked status remain unchanged. No package upgrade or code change may be silently substituted to obtain a pass.

## Validation and Acceptance

Acceptance requires exact redis 8.1.0 and fakeredis 2.37.1 with Lua support under Python 3.13, a passing installed-environment audit, the independent requirements audit, and pip check. Focused tests must demonstrate shared Lua state, truthful failure/recovery metrics and health, production-client timeouts with zero automatic retries, bounded controlled fault handling, and no replay after injected lost replies. A passing real Redis 8 run must be available on the final head, locally or through the hosted service workflow.

Require two clean all-files runs, format/lint/type checks, complete tests, runtime combined coverage of at least 85%, separate full-source coverage, benchmark, secret scan, and diff checks. Hosted Quality Gate, Docker Deployment Smoke, and Redis Compatibility must all pass on the exact final PR head. Unavailable local Make/Docker and real-service skips must remain explicit.

No new provider, mapping, analytics, score, snapshot, API route, UI feature, package version, tag, or release change is permitted. #117 and #122 remain superseded. #135 remains draft until a separate owner decision.

## Idempotence and Recovery

Never reset, clean, force-push, change ACLs, clear shared caches, or use a stash to hide work. A remote mismatch or local test failure requires an exact report, not an automatic branch rewrite. Normal exact-path cleanup is permitted only for current-task-owned artifacts after every root-AGENTS preservation gate passes. Retain and explain anything uncertain; do not repeatedly force removal.

## Artifacts and Notes

Public evidence belongs in PR #135 and issue #134; local reports must omit secrets and private paths before posting. The private operator report may identify workspace paths needed for preservation. Generated environments, coverage, logs, containers, and caches do not belong in source control. Record every task-created workspace/process/artifact and its disposition; do not confuse a clean tracked status with proof that ignored content is disposable.

## Interfaces and Dependencies

Preserve `RedisTokenBucket`, `RateLimiterService`, configuration parsing, canonical API/UI contracts, and credential redaction. Relevant external interfaces are redis-py `Redis`, `Retry`, `NoBackoff`, registered Lua/EVALSHA scripts, fakeredis with its Lua extra, Python 3.13, pytest, pre-commit, pip-audit, and the existing pinned GitHub Actions. Maintenance notification, provider, and async application interfaces are not expanded.

Change note (2026-09-06): Reconciled the owner-authorized review corrections, explicitly documented the narrow runtime behavior change and fallback limits, separated installed/minimum audits from requirements resolution, corrected PowerShell commands, and reduced the local handoff to exact-head reproduction and preservation reporting without a redundant evidence commit.
