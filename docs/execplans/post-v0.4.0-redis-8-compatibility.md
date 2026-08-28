# Complete Redis 8 and fakeredis 2.37.1 compatibility

This ExecPlan is a living document. Maintain it in accordance with `.agent/PLANS.md`, including the `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` sections as work proceeds.

## Purpose / Big Picture

Issue #134 coordinates post-v0.4.0 repository hardening. Workspace governance and the all-files pre-commit contract are complete. This phase validates the optional distributed rate-limiting stack as one coherent compatibility unit instead of independently merging stale Dependabot pull requests.

After this work, the repository supports redis-py 8.1 or newer within major version 8, uses fakeredis 2.37.1 or newer within major version 2 plus its Lua test extra, and proves the existing token bucket against both a Redis-8-configured fakeredis server and a real Redis 8 service. The in-memory backend, Redis failure fallback, health reporting, metrics, credential-redacted configuration summaries, package version, and published v0.4.0 identity must remain unchanged.

Success is visible when a fresh Python 3.13 environment resolves the declared exact minimum versions, focused compatibility tests pass against fakeredis and a real Redis 8 service, all-files and complete quality gates pass, hosted CI/Docker/Redis compatibility checks are green on one exact final head, and the stale one-line dependency PRs remain closed and unmerged as superseded provenance.

## Progress

- [x] (2026-08-28) Squash-merged all-files PR #121 and verified signed `main` commit `53d404b2e6624d55b36ac6320547613b95ada469`.
- [x] (2026-08-28) Verified post-merge CI #343 and Docker Smoke #173 passed on exact `main`.
- [x] (2026-08-28) Audited PR #117; its complete intended delta was `redis>=8.1.0,<9` at provenance head `8529bbee2242cad563ebe563354c920beba1901b`.
- [x] (2026-08-28) Audited PR #122; its complete intended delta was the fakeredis floor `>=2.37.1,<3`. Dependabot refreshed its final closed snapshot to `32d70577a3d96d01c347eef3ff919a8bd61fea2b`.
- [x] (2026-08-28) Created combined draft PR #135 from exact signed `main` rather than merging or rebasing either stale dependency PR.
- [x] (2026-08-28) Added `redis>=8.1.0,<9`, Redis-8-configured fakeredis sync/async/fallback tests, and a real Redis 8 hosted compatibility workflow at initial head `cd246c180326324fc8e86f8ef46193015487922f`.
- [x] (2026-08-28) Used initial hosted failures to prove plain fakeredis lacks the required `EVALSHA` command path while exact redis 8.1.0, fakeredis 2.37.1, pip check, and the real Redis 8.10.1 Lua path worked.
- [x] (2026-08-28) Added only the evidence-required `fakeredis[lua]>=2.37.1,<3` extra and Ruff's deterministic import-order correction in commit `17b9c67611933cabb00c52261fe1f59b177f344c`.
- [x] (2026-08-28) Verified Redis 8 Compatibility #2 passed 44 focused tests on exact redis 8.1.0, fakeredis 2.37.1, lupa 2.8, and disposable Redis 8.10.1.
- [x] (2026-08-28) Verified CI #346 and Docker Smoke #175 passed on implementation head `17b9c67611933cabb00c52261fe1f59b177f344c`.
- [x] (2026-08-28) Closed PRs #117 and #122 unmerged with explicit supersession links to #135.
- [x] (2026-08-28) Reconciled `docs/DEPENDENCIES.md` against the current requirements, including the Redis/fakeredis Lua contract and other directly stale dependency rows.
- [ ] Create one clean disposable Python 3.13 checkout at the exact remote PR #135 head without touching protected or retained paths.
- [ ] Re-run exact minimum installation and the complete focused matrix locally; use a task-owned Redis 8 service when Docker or another safe local service is available.
- [ ] Prove two clean all-files pre-commit runs with no second-run change.
- [ ] Run the complete quality, security, dependency, runtime/full-source coverage, benchmark, and Docker-relevant gates.
- [ ] Update this plan with exact local evidence, commit coherently, rerun final exact-head validation, and push normally without force.
- [ ] Obtain fresh exact-head CI, Docker Smoke, and Redis 8 Compatibility PASS results after the final local evidence commit.
- [ ] Keep PR #135 draft for a separate owner-controlled ready/merge authorization.
- [ ] Reconcile every task-created workspace and artifact under root `AGENTS.md`.

## Surprises & Discoveries

- Observation: The dependency floors themselves install cleanly together under Python 3.13.
  Evidence: Both initial and corrected hosted compatibility runs resolved redis 8.1.0 and fakeredis 2.37.1 and passed `pip check`.

- Observation: Plain fakeredis 2.37.1 cannot execute the repository's actual scripted token-bucket path.
  Evidence: The initial fakeredis Redis-8 test returned `ResponseError: unknown command 'evalsha'`. The existing backend correctly degraded to `redis-fallback`, proving the failure contract but not Redis-backed shared state.

- Observation: The documented fakeredis Lua extra is necessary and sufficient.
  Evidence: Adding `fakeredis[lua]` installed lupa 2.8; the corrected hosted job passed the same fakeredis RESP3 `register_script`/`EVALSHA` test without product-code changes.

- Observation: Real Redis 8 compatibility succeeded before and after the fakeredis correction.
  Evidence: The disposable `redis:8-alpine` service reported Redis 8.10.1 and passed the shared Lua token-bucket test. The focused corrected matrix finished with 44 passed.

- Observation: The production integration remains synchronous, while fakeredis exposes an async-compatible client.
  Evidence: Application code constructs `redis.Redis` and contains no `redis.asyncio` product path. Async coverage remains bounded dependency-stack smoke rather than a new interface.

- Observation: The real-server cleanup key is exact.
  Evidence: `RedisTokenBucket._redis_key` produces `<prefix>:<identifier>`, and the test deletes `<prefix>:shared`; no scope component is added by the implementation.

- Observation: The dependency register had drifted beyond Redis.
  Evidence: It reported historical Streamlit, pandas, requests, pytest, Black, mypy, pre-commit, pytest-cov, and fakeredis ranges and omitted XlsxWriter and botocore. The reconciled register now mirrors both requirements files.

## Decision Log

- Decision: Replace independent merges of PRs #117 and #122 with one current-main compatibility PR.
  Rationale: redis-py and fakeredis are coupled by scripting, fallback, health, and test behavior. One exact-head validation is safer than two stale one-line merges.
  Date/Author: 2026-08-28 / project owner and connector.

- Decision: Adopt `redis>=8.1.0,<9` and `fakeredis[lua]>=2.37.1,<3`.
  Rationale: The runtime floor comes directly from #117. Hosted exact-minimum evidence proved the 2.37.1 fakeredis floor from #122 works only with its documented Lua extra for the repository's required EVALSHA contract.
  Date/Author: 2026-08-28 / connector.

- Decision: Add a dedicated hosted Redis 8 Compatibility workflow in addition to CI and Docker Smoke.
  Rationale: Normal tests primarily use fakeredis and cannot prove the Lua token bucket against an actual Redis 8 server. The dedicated job supplies a disposable real service and exact focused contracts.
  Date/Author: 2026-08-28 / connector.

- Decision: Include fakeredis async RESP3 smoke without adding async application code.
  Rationale: It protects dependency interoperability while preserving the synchronous product architecture.
  Date/Author: 2026-08-28 / connector.

- Decision: Keep the Lua extra development-only.
  Rationale: lupa is required only to emulate Redis scripting in fakeredis tests. Production uses a real Redis server and must not inherit that compiled test dependency.
  Date/Author: 2026-08-28 / connector.

- Decision: Reconcile the complete dependency register within this slice.
  Rationale: The register is a security and upgrade-planning surface. Leaving directly adjacent declared constraints stale would make the compatibility result misleading.
  Date/Author: 2026-08-28 / connector.

## Outcomes & Retrospective

The connector phase is complete. PR #121 is merged and post-merge green; #117 and #122 are closed unmerged as provenance; combined draft PR #135 carries both dependency intents on current signed `main`. The implementation head `17b9c67611933cabb00c52261fe1f59b177f344c` passed CI #346, Docker Smoke #175, and Redis 8 Compatibility #2. The focused service job resolved redis 8.1.0, fakeredis 2.37.1, and lupa 2.8; used Redis 8.10.1; and passed 44 tests.

A documentation-focused connector commit follows that validated implementation head to reconcile this living plan and the dependency register. Fresh hosted checks on the resulting documentation head are required before local execution begins. Local exact-head reproduction, complete repository validation, final evidence, and workspace reconciliation remain.

## Context and Orientation

The optional distributed rate limiter is implemented in `src/infrastructure/rate_limiter.py`.

`InMemoryTokenBucket` is the default backend. `RedisTokenBucket` registers `_TOKEN_BUCKET_LUA` through the redis-py client, records Redis success and error state, and falls back to a private in-memory backend on `RedisError`. Its `summary()` output feeds health and observability behavior.

`src/core/config.py` parses `RATE_LIMIT_BACKEND`, Redis URL/host/port/database, username/password, TLS, timeout, key prefix, and TTL. Its public summary exposes only credential-presence booleans.

Existing focused coverage includes:

- `tests/test_rate_limiter.py` for in-memory behavior, shared fakeredis state, wait logic, security handlers, and fallback;
- `tests/test_rate_limiter_metrics_and_redis_health.py` for fallback metrics;
- `tests/test_rate_limiting_health_probe.py` for degraded health state;
- `tests/test_config.py` for Redis configuration and credential-redacted summaries.

`tests/test_redis_8_compatibility.py` adds:

- dependency-floor identity;
- `FakeServer(version=(8,), server_type="redis")`;
- sync RESP3 Lua token-bucket state across separate clients;
- disconnected-server fallback preservation;
- async RESP3 set/get smoke;
- a real Redis 8 Lua token-bucket test enabled by `REDIS_COMPAT_URL`.

`.github/workflows/redis-compatibility.yml` supplies a disposable Redis 8 service, installs the complete dependency graph under Python 3.13, reports resolved redis/fakeredis versions, runs `pip check`, and executes the focused compatibility set. CI owns all-files pre-commit and `make quality-gate`; Docker Smoke owns production-image startup and health.

## Plan of Work

Create one new independent checkout from the exact remote #135 branch. Read `AGENTS.md`, `.agent/PLANS.md`, this plan, requirements, dependency register, rate-limiter/config implementation, focused tests, and all three relevant workflows before editing.

Create a Python 3.13 environment. Install the complete requirements while forcing redis 8.1.0 and fakeredis 2.37.1 with the Lua extra. Record redis, fakeredis, lupa, Python, and pip versions and run `pip check` before tests.

Run the focused compatibility set without a service; require all fakeredis, fallback, health, metrics, config, and async tests to pass while only the real-server test skips. When Docker or another safe task-owned Redis service is available, run Redis 8 in an isolated temporary container/database, set `REDIS_COMPAT_URL`, rerun the new module, verify server major version 8, and prove shared scripted token state and exact key cleanup. Never use production or user-owned Redis data and never call `FLUSHALL` or `FLUSHDB`.

Verify the dependency register matches both requirements files. Limit additional documentation changes to facts directly necessary for this compatibility result.

Run all-files pre-commit twice and prove identical state after the second run. Run focused tests, the complete quality gate, security/dependency audit, runtime and full-source coverage, benchmark, `git diff --check`, and Docker-relevant validation. Update this plan with exact evidence before the final evidence commit. Make no commit after final exact-head validation.

Push normally without force, keep the PR draft, and observe exact-head CI, Docker Smoke, and Redis 8 Compatibility. Do not merge, mark ready, alter the published tag/release, reopen provenance PRs, or close issue #134.

## Concrete Steps

Work only in the new disposable checkout.

Create the exact-minimum environment:

    py -3.13 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt -r requirements-dev.txt "redis==8.1.0" "fakeredis[lua]==2.37.1"
    python -m pip check
    python -c "from importlib.metadata import version; print(version('redis')); print(version('fakeredis')); print(version('lupa'))"

Run focused tests without a real server:

    python -m pytest -q \
      tests/test_redis_8_compatibility.py \
      tests/test_rate_limiter.py \
      tests/test_rate_limiter_metrics_and_redis_health.py \
      tests/test_rate_limiting_health_probe.py \
      tests/test_config.py

Start a task-owned Redis 8 service when safely available, set `REDIS_COMPAT_URL` to its isolated database, and rerun `tests/test_redis_8_compatibility.py`. Record the exact server version and cleanup result.

Prove all-files idempotence:

    pre-commit run --all-files --show-diff-on-failure --color=always
    git status --short --untracked-files=all
    pre-commit run --all-files --show-diff-on-failure --color=always
    git status --short --untracked-files=all

Run the canonical gate when GNU Make is available:

    make quality-gate

If GNU Make is unavailable, report `make quality-gate: NOT RUN`, execute the exact current constituents individually, and do not infer the aggregate result.

Also run:

    python -m pip check
    python -m pip_audit -r requirements.txt -r requirements-dev.txt
    python src/scripts/detect_secrets_check.py --baseline config/.secrets.baseline --exclude-lines '^\s*"csv_sha256":\s*"[0-9a-f]{64}",?\s*$'
    git diff --check

Run the current Docker Smoke procedure when Docker is available. Report either exact local results or the precise limitation; hosted Docker evidence is separate.

## Validation and Acceptance

Acceptance requires all of the following on the exact final commit:

- `redis>=8.1.0,<9` and `fakeredis[lua]>=2.37.1,<3` remain bounded;
- exact redis 8.1.0, fakeredis 2.37.1, and its Lua extra install under Python 3.13 and pass `pip check` and `pip-audit`;
- fakeredis Redis 8 sync RESP3 EVALSHA token-bucket behavior passes across separate clients;
- disconnected-server behavior falls back to memory with truthful summary, metrics, and health;
- async RESP3 smoke passes without an async product interface;
- a real Redis 8 service reports major version 8 and passes shared Lua token-bucket behavior and exact cleanup;
- in-memory behavior and credential-redacted configuration remain unchanged;
- dependency documentation matches requirements;
- all-files hooks pass twice without a second-run change;
- Black, Ruff, mypy, complete pytest, runtime/full-source coverage, benchmark, secret scan, dependency checks, and diff checks pass;
- runtime combined coverage remains at least 85%;
- exact-head hosted CI, Docker Smoke, and Redis 8 Compatibility pass;
- no package version, provider, mapping, API, Streamlit, snapshot, analytics, tag, or release change occurs;
- #117 and #122 remain closed and unmerged as superseded provenance;
- the final branch is clean, pushed normally, and #135 remains draft for a separate owner decision.

## Idempotence and Recovery

Tests use unique prefixes and delete only the exact real-server key they create. Repeated runs must not rely on or clear unrelated Redis data.

If installation or scripting fails, preserve the resolver output and traceback before changing a requirement. Make the narrowest evidence-backed correction, recreate the disposable environment, and rerun the full focused matrix. Do not broaden version ranges merely to select a passing latest release.

If the remote branch or `main` moves, stop and report exact SHAs rather than resetting, rebasing, or force-updating. If cleanup is blocked, retain the task-owned path and report its exact state; do not change ACLs or ownership and do not repeatedly force deletion.

## Artifacts and Notes

Durable evidence belongs in this plan and the PR conversation. Virtual environments, Redis data, container layers, caches, coverage output, logs, and audit reports remain local and must be inventoried before normal exact-path cleanup. Do not commit credentials, Redis URLs containing credentials, private paths, environment dumps, container IDs, or generated reports.

## Interfaces and Dependencies

This slice preserves existing application interfaces. Relevant interfaces are:

- `RedisTokenBucket(client, key_prefix, ttl_seconds)`;
- `RateLimiterService.enforce(identifier, rule)` and `summary()`;
- `DistributedRateLimitConfig` and `RATE_LIMIT_REDIS_*` environment settings;
- redis-py `Redis`, RESP3, `register_script`, `INFO`, `DELETE`, and client close operations;
- fakeredis `FakeServer`, `FakeRedis`, and `FakeAsyncRedis` configured as Redis 8;
- Python 3.13, pytest, pre-commit, Black, Ruff, mypy, detect-secrets, pip-audit, GNU Make when available, Docker when available, and full-length-SHA-pinned GitHub Actions.
