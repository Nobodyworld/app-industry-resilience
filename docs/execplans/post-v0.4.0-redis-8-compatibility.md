# Complete Redis 8 and fakeredis 2.37.1 compatibility

This ExecPlan is a living document. Maintain it in accordance with `.agent/PLANS.md`, including the `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` sections as work proceeds.

## Purpose / Big Picture

Issue #134 coordinates post-v0.4.0 repository hardening. Workspace governance and the all-files pre-commit contract are complete. This phase validates the optional distributed rate-limiting stack as one coherent compatibility unit instead of independently merging stale Dependabot pull requests.

After this work, the repository supports redis-py 8.1 or newer within major version 8, uses fakeredis 2.37.1 or newer within major version 2 for development tests, and proves the rate limiter against both a Redis-8-configured fakeredis server and a real Redis 8 service. The in-memory backend, automatic Redis failure fallback, health reporting, metrics, configuration redaction, and published v0.4.0 identity must remain unchanged.

Success is visible when a fresh Python 3.13 environment resolves the declared minimum dependency versions, the compatibility tests pass against fakeredis and a real Redis 8 service, the complete all-files and quality gates pass, hosted CI/Docker/Redis compatibility checks are green on one exact head, and the stale one-line dependency PRs are closed as superseded provenance rather than merged.

## Progress

- [x] (2026-08-28) Squash-merged PR #121 and verified resulting signed `main` commit `53d404b2e6624d55b36ac6320547613b95ada469`.
- [x] (2026-08-28) Verified post-merge CI #343 and Docker Smoke #173 passed on that exact `main` commit.
- [x] (2026-08-28) Audited dependency provenance PR #117 at head `8529bbee2242cad563ebe563354c920beba1901b`; its complete intended delta is `redis>=8.1.0,<9`.
- [x] (2026-08-28) Audited dependency provenance PR #122 at head `1e8e4ba7def38116bacb999d78c430c47e61edf4`; its complete intended delta is `fakeredis>=2.37.1,<3`.
- [x] (2026-08-28) Created a combined compatibility branch from exact signed `main` rather than rebasing or merging either stale dependency PR.
- [x] (2026-08-28) Added both dependency floors, Redis-8-configured fakeredis sync/async/fallback coverage, and a real Redis 8 hosted compatibility workflow.
- [ ] Create a clean disposable Python 3.13 checkout at the exact combined branch head without touching protected or retained local paths.
- [ ] Validate exact minimum versions `redis==8.1.0` and `fakeredis==2.37.1`, then validate the normal declared ranges.
- [ ] Determine whether plain fakeredis provides every Lua capability required by `RedisTokenBucket`; add the narrow `fakeredis[lua]` extra only if exact-minimum execution proves it is necessary.
- [ ] Run focused in-memory, fakeredis Redis 8, real Redis 8, failure-fallback, health, metrics, configuration, and applicable async tests.
- [ ] Reconcile `docs/DEPENDENCIES.md` against installed package metadata for the Redis/fakeredis rows and any directly adjacent stale dependency facts needed for a truthful register.
- [ ] Run pre-commit twice with no second-run change, the complete quality/security/dependency/coverage/benchmark gates, and deployment-relevant Docker validation.
- [ ] Record exact evidence, push normally without force, and obtain fresh hosted CI, Docker Smoke, and Redis 8 Compatibility results.
- [ ] Keep the combined PR draft for a separate owner-controlled merge decision.
- [ ] Close PRs #117 and #122 as superseded only after their exact dependency intent is represented and validated in the combined PR.
- [ ] Reconcile every task-created workspace and artifact under root `AGENTS.md`.

## Surprises & Discoveries

- Observation: Current `main` already resolves fakeredis 2.37.1 under the broader `>=2.36.2,<3` range, while redis-py remains constrained below major version 8.
  Evidence: CI #343 passed with the current development range, and the repository requirements still declare `redis>=5.1.0,<8`.

- Observation: The production integration is synchronous, but fakeredis 2.37.1 also exposes an async Redis-compatible client.
  Evidence: Application code imports and constructs `redis.Redis`; no `redis.asyncio` application path exists. Async coverage in this slice is therefore dependency-stack smoke, not a new product interface.

- Observation: The rate limiter depends on Redis scripting through `register_script`.
  Evidence: `RedisTokenBucket` registers the token-bucket Lua program during initialization and invokes it for every Redis-backed decision. Compatibility must test actual script execution, not only `PING` or simple key operations.

- Observation: fakeredis supports Redis server-version selection and defaults its `FakeServer` to Redis 8 behavior.
  Evidence: fakeredis 2.37.1 accepts `version=(8,)` and `server_type="redis"`; the compatibility tests set these values explicitly.

## Decision Log

- Decision: Replace independent merges of PRs #117 and #122 with one current-main compatibility PR.
  Rationale: redis-py and fakeredis are coupled by the rate-limiter tests and scripting behavior. A combined exact-head validation is more reliable than two stale one-line dependency merges.
  Date/Author: 2026-08-28 / project owner and connector.

- Decision: Adopt the exact floors proposed by the provenance PRs: `redis>=8.1.0,<9` and `fakeredis>=2.37.1,<3`.
  Rationale: These are the reviewed upstream transition points and keep future compatible updates within bounded major versions.
  Date/Author: 2026-08-28 / connector.

- Decision: Add a dedicated hosted Redis 8 compatibility workflow in addition to ordinary CI and Docker Smoke.
  Rationale: The normal suite primarily uses fakeredis and cannot prove the Lua token bucket against a real Redis 8 server. The dedicated job supplies a disposable Redis 8 service and executes the same focused contracts.
  Date/Author: 2026-08-28 / connector.

- Decision: Include fakeredis async RESP3 smoke without adding async application code.
  Rationale: fakeredis 2.37.1 explicitly supports `redis.asyncio`-compatible clients. A bounded smoke protects dependency interoperability while preserving the current synchronous product architecture.
  Date/Author: 2026-08-28 / connector.

- Decision: Do not add `fakeredis[lua]` preemptively.
  Rationale: Current hosted tests already exercise `register_script` with plain fakeredis under the resolved 2.37.1 version. Exact-minimum validation should determine whether an extra is necessary before adding compiled dependency surface.
  Date/Author: 2026-08-28 / connector.

## Outcomes & Retrospective

The connector scaffold is complete. It represents the exact dependency intent of PRs #117 and #122 on current signed `main`, adds focused compatibility tests, and adds a real Redis 8 hosted job. Local exact-minimum execution, full validation, documentation reconciliation, hosted evidence, superseded-PR closure, and safe workspace reconciliation remain. At completion, summarize the resolved versions, script behavior, fallback/health/metrics outcomes, real-server identity, complete gate results, final exact head, and any retained workspace or limitation.

## Context and Orientation

The optional distributed rate limiter is implemented in `src/infrastructure/rate_limiter.py`.

`InMemoryTokenBucket` is the default backend. `RedisTokenBucket` registers a Lua token-bucket script through the redis-py client, records Redis success/error state, and falls back to a private in-memory backend when a `RedisError` occurs. Its `summary()` output drives health and observability behavior.

`src/core/config.py` parses `RATE_LIMIT_BACKEND`, `RATE_LIMIT_REDIS_URL`, host, port, database, username, password, TLS, timeout, key prefix, and TTL settings. Its public summary exposes only booleans for credential presence.

Existing focused coverage includes:

- `tests/test_rate_limiter.py` for in-memory behavior, shared fakeredis state, wait logic, registered security handlers, and Redis failure fallback;
- `tests/test_rate_limiter_metrics_and_redis_health.py` for fallback metrics;
- `tests/test_rate_limiting_health_probe.py` for degraded health state;
- `tests/test_config.py` for Redis URL and configuration parsing.

The new `tests/test_redis_8_compatibility.py` adds:

- dependency-floor identity;
- fakeredis `FakeServer(version=(8,), server_type="redis")`;
- sync RESP3 Lua token-bucket state shared by separate clients;
- disconnected-server fallback preservation;
- async RESP3 set/get smoke;
- a real Redis 8 Lua token-bucket test enabled by `REDIS_COMPAT_URL`.

The new `.github/workflows/redis-compatibility.yml` supplies a disposable Redis 8 service, installs the complete current dependency graph under Python 3.13, reports resolved redis/fakeredis versions, runs `pip check`, and executes the focused compatibility set. The existing CI still owns all-files pre-commit and the complete quality gate; Docker Smoke still owns production-image startup and health.

## Plan of Work

First create one new disposable checkout from the exact remote combined branch. Read root `AGENTS.md`, `.agent/PLANS.md`, this plan, the rate-limiter/config implementation, the focused tests, all three workflows, and the dependency register before modifying anything.

Create a Python 3.13 environment. Install the complete requirements while forcing `redis==8.1.0` and `fakeredis==2.37.1`. Run `pip check`, report package versions, and execute the focused test set. If fakeredis Lua execution fails solely because the documented Lua extra is absent, change the development requirement to `fakeredis[lua]>=2.37.1,<3`, explain the added transitive dependency, and rerun from a clean environment. Do not add the extra if plain fakeredis passes.

Exercise the real Redis test against a task-owned Redis 8 container or local service. Verify the server major version from `INFO`, the RESP3 clients, shared token consumption across independent clients, blocked-response retry metadata, deterministic key cleanup, and clean client shutdown. Do not point tests at production or user-owned Redis data.

Review fallback behavior by disconnecting a fakeredis Redis 8 server and by using the existing explicit error stubs. Confirm the backend changes to `redis-fallback`, last error is present, memory fallback remains functional, metrics report the fallback, and the health component warns rather than failing the application.

Reconcile the dependency register using actual installed metadata and the declared requirements. Keep edits bounded to truthful dependency documentation; do not mix unrelated product docs or release records into this slice.

Run all-files pre-commit twice and prove idempotence. Run focused tests, the complete quality gate, security/dependency audit, runtime and full-source coverage, benchmark, `git diff --check`, and Docker-relevant validation. Update this plan with exact evidence before the final evidence commit. Make no commit after final exact-head validation.

Push normally without force, keep the PR draft, and observe exact-head hosted CI, Docker Smoke, and Redis 8 Compatibility. Do not merge, mark ready, alter the published tag/release, or close issue #134.

## Concrete Steps

Work only in the disposable checkout.

Create the exact-minimum environment:

    py -3.13 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt -r requirements-dev.txt "redis==8.1.0" "fakeredis==2.37.1"
    python -m pip check
    python -c "from importlib.metadata import version; print(version('redis')); print(version('fakeredis'))"

Run the focused non-network tests:

    python -m pytest -q \
      tests/test_redis_8_compatibility.py \
      tests/test_rate_limiter.py \
      tests/test_rate_limiter_metrics_and_redis_health.py \
      tests/test_rate_limiting_health_probe.py \
      tests/test_config.py

The real-server test is skipped without `REDIS_COMPAT_URL`. Start a task-owned Redis 8 service, set a URL to an isolated database, and rerun the new compatibility module so the real-server test executes. Record the exact Redis server version and cleanup outcome.

Prove all-files idempotence:

    pre-commit run --all-files --show-diff-on-failure --color=always
    git status --short --untracked-files=all
    pre-commit run --all-files --show-diff-on-failure --color=always
    git status --short --untracked-files=all

Run the canonical repository gate when GNU Make is available:

    make quality-gate

Otherwise run the exact current Makefile constituents individually and report `make quality-gate: NOT RUN`.

Also run:

    python -m pip check
    python -m pip_audit -r requirements.txt -r requirements-dev.txt
    python src/scripts/detect_secrets_check.py --baseline config/.secrets.baseline --exclude-lines '^\s*"csv_sha256":\s*"[0-9a-f]{64}",?\s*$'
    git diff --check

Use the current Docker Smoke procedure when Docker is available. In addition, run the real Redis 8 compatibility test against a task-owned Redis 8 container. Report either exact results or the precise limitation; do not infer a local Docker pass from hosted evidence.

## Validation and Acceptance

Acceptance requires all of the following on the exact final commit:

- runtime requirement is `redis>=8.1.0,<9`;
- development requirement is at least `fakeredis>=2.37.1,<3`, with the Lua extra included only if exact-minimum evidence requires it;
- exact minimum versions install together under Python 3.13 and pass `pip check` and `pip-audit`;
- fakeredis Redis 8 sync RESP3 Lua token-bucket behavior passes across separate clients;
- fakeredis disconnected-server behavior falls back to memory with truthful summary, metrics, and health;
- fakeredis async RESP3 smoke passes without adding an async application interface;
- a real Redis 8 service reports major version 8 and passes the shared Lua token-bucket test;
- in-memory mode remains unchanged;
- configuration parsing and credential-redaction summaries remain unchanged;
- root all-files hooks pass twice without a second-run modification;
- Black, Ruff, mypy, complete pytest, runtime coverage, full-source coverage, benchmark, secret scan, dependency checks, and diff checks pass;
- runtime combined coverage remains at or above 85%;
- exact-head hosted CI, Docker Smoke, and Redis 8 Compatibility pass;
- no release, package version, provider, mapping, API, Streamlit, snapshot, or analytics change occurs;
- the published v0.4.0 annotated tag and GitHub release remain unchanged;
- PRs #117 and #122 are not merged and are closed only with a clear supersession link after the combined PR is validated;
- the final branch is clean, pushed normally, and the PR remains draft for a separate owner decision.

## Idempotence and Recovery

The tests use unique Redis key prefixes and delete the exact real-server key they create. Repeated runs must not rely on or clear unrelated Redis data. Never use `FLUSHALL` or `FLUSHDB` against a server not created specifically for this task.

If exact-minimum installation or scripting fails, capture the dependency resolution and traceback before changing requirements. Make the narrowest correction, recreate the disposable environment, and rerun the full focused matrix. Do not broaden version ranges merely to select a passing latest release.

If the remote branch or `main` moves, stop and report exact SHAs rather than resetting, rebasing, or force-updating. If cleanup is blocked, retain the task-owned path and report its exact state; do not change ACLs or ownership and do not use repeated force deletion.

## Artifacts and Notes

Durable evidence belongs in this plan and the PR conversation. Virtual environments, Redis data, container layers, caches, coverage output, logs, and audit reports remain local and must be inventoried before normal exact-path cleanup. Do not commit credentials, Redis URLs containing credentials, private paths, environment dumps, container IDs, or generated security reports.

## Interfaces and Dependencies

This slice preserves existing application interfaces. The relevant interfaces are:

- `src.infrastructure.rate_limiter.RedisTokenBucket(client, key_prefix, ttl_seconds)`;
- `RateLimiterService.enforce(identifier, rule)` and `summary()`;
- `DistributedRateLimitConfig` and the `RATE_LIMIT_REDIS_*` environment contract;
- redis-py `Redis`, RESP3, `register_script`, `INFO`, `DELETE`, and client close operations;
- fakeredis `FakeServer`, `FakeRedis`, and `FakeAsyncRedis` configured as Redis 8;
- Python 3.13, pytest, pre-commit, Black, Ruff, mypy, detect-secrets, pip-audit, GNU Make when available, Docker when available, and the existing full-length-SHA-pinned GitHub Actions.
