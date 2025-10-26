```md
# Distributed Rate Limiting, Normalisation Overrides, and Retry Telemetry

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Reference: `.agent/PLANS.md` — this plan follows its formatting and maintenance rules.

## Purpose / Big Picture

Operators need Idiot Index to scale horizontally, adapt to evolving partner schemas, and offer richer diagnostics when external APIs misbehave. Today, rate limiting only works per-process, column normalisation assumes static dtypes, and HTTP retries disappear into logs. After this change, multiple instances will coordinate rate limits through Redis with health checks and metrics, callers will be able to override column dtypes safely, and retry attempts will emit structured observability events. Streamlit will surface the new configuration so operators can confirm the backend mode visually.

## Progress

- [x] (2025-10-29T12:45Z) Survey existing rate limiting, normalisation, and observability modules.
- [x] (2025-10-29T13:30Z) Implement Redis-backed token bucket backend with instrumentation and health reporting.
- [x] (2025-10-29T13:30Z) Wire SecurityUtils to configurable rate-limit handlers and add shared backend hookup.
- [x] (2025-10-29T13:30Z) Support dtype overrides in `normalize_columns` and propagate through application/service layers.
- [x] (2025-10-29T13:30Z) Emit retry metrics/events from `safe_get_json` via observability registry hooks.
- [x] (2025-10-29T12:30Z) Update UI config summary, docs, and changelog/release notes to reflect new capabilities.
- [x] (2025-10-29T13:55Z) Add unit tests for Redis backend (using fakeredis), dtype overrides, and retry telemetry plus update fixtures.
- [x] (2025-10-29T12:30Z) Run `make quality-gate` and document outcomes (`make quality-gate`, chunk `16611c`).

## Surprises & Discoveries

- Observation: fakeredis faithfully executes the Lua token-bucket script, letting us verify shared Redis state without an external server.
  Evidence: `tests/test_rate_limiter.py::test_redis_backend_shares_tokens_across_services` exercises two services against a single `FakeRedis` instance.
- Observation: Serialising customised dtypes through the existing cache would downcast them to Python objects, so overrides bypass cache persistence.
  Evidence: Manual inspection while enabling overrides showed Pandas reloading `dict` payloads lost `Int64` metadata; we now skip caching when overrides are active (see `src/adapters/bea.py`).

## Decision Log

- Decision: Replaced the stubbed `SecurityUtils.rate_limit_check` with a pluggable handler contract so infrastructure can inject Redis-backed coordination without violating layering.
  Rationale: Keeps `core` independent of Redis while allowing in-process defaults for tests; the handler pattern also powers UI diagnostics.
  Date/Author: 2025-10-29 / gpt-5-codex
- Decision: Chose a Lua-script token bucket for Redis to maintain parity with the existing in-memory semantics and emit retry-after estimates.
  Rationale: Sliding-window counters would have altered burst behaviour; scripting keeps throughput identical while remaining atomic.
  Date/Author: 2025-10-29 / gpt-5-codex
- Decision: Introduced the `NORMALIZE_DTYPE_OVERRIDES` JSON env var and skipped cache persistence when overrides are set.
  Rationale: Provides declarative control for operators without risking dtype loss through JSON serialisation.
  Date/Author: 2025-10-29 / gpt-5-codex
- Decision: Routed HTTP retry telemetry through the new rate limiting instrumentation extension instead of a standalone module.
  Rationale: The extension already owns outbound API metrics, so consolidating counters avoids scattering observability wiring.
  Date/Author: 2025-10-29 / gpt-5-codex

## Outcomes & Retrospective

- Redis-backed rate limiting now powers both API and security throttling with shared health/metrics surfaced through the new instrumentation extension. The Streamlit UI and config summaries show backend mode, last-seen status, and retry telemetry counters.
- `NormalizationOptions` flow end-to-end: adapters, services, scripts, and agents accept dtype overrides, and formatted outputs preserve caller-specified dtypes across leaderboard and health summaries.
- HTTP retry telemetry emits structured events into the observability registry, enabling dashboards to chart retries and backoff delays.
- Documentation (README, architecture, API reference, dependencies) and release artifacts explain the new configuration flags, Redis requirements, and monitoring endpoints. CHANGELOG and RELEASE_NOTES record the feature bundle.
- Full quality gate (format, lint, mypy, pytest, security placeholders) passes locally (`make quality-gate`, chunk `16611c`).

## Context and Orientation

Relevant modules and their responsibilities:

- `src/infrastructure/rate_limiter.py` – current in-process token bucket (`RateLimiter`, `APIRateLimiter`, global `api_limiter`). TODO comments require distributed coordination.
- `src/core/security.py` – validation helpers including `rate_limit_check`, currently a stub returning success with TODO to integrate Redis.
- `src/core/normalize.py` – normalises incoming data. Optional columns default to nullable floats; TODO requests dtype overrides.
- `src/core/utils.py` – `safe_get_json` implements retries without observability hooks.
- `src/application/idiot_index_service.py` – orchestrates evaluation pipeline, calls `normalize_columns` without options.
- `src/interfaces/streamlit/bootstrap.py` and `app.py` – surface configuration summary in UI; need to expose new rate limit status.
- Observability: `src/infrastructure/observability/instrumentation.py` (registry), `src/extensions/builtins/core_instrumentation.py` (baseline metrics). Extensions manifest at `extensions/manifest.json` ensures built-ins load.
- Tests mirroring layers reside under `tests/`, notably `test_security.py`, `test_application.py`, `test_core.py`, `test_ui_helpers.py`, `test_observability.py`, etc.
- Documentation: `README.md`, `docs/ARCHITECTURE_OVERVIEW.md`, `docs/API_REFERENCE.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, and `STATUS.md` record shipped capabilities.

We must keep core free of infrastructure dependencies, so Redis wiring must be injected from infrastructure into `SecurityUtils` via a handler registration rather than direct imports.

## Plan of Work

1. **Design distributed backend primitives.**
   - Introduce `RateLimitRule` and `RateLimitDecision` dataclasses plus a `RateLimitHandler` Protocol in `src/infrastructure/rate_limiter.py` (or supporting module) to express token bucket semantics shared across APIs and security checks.
   - Implement a thread-safe in-memory backend (refactoring existing `RateLimiter`) to use the new primitives.
   - Add a Redis-backed backend using the `redis` client with a Lua script to atomically manage tokens (`HMSET` storing `tokens` and `timestamp`), returning decision metadata including retry-after seconds. Provide graceful degradation when Redis is unavailable by surfacing errors through metrics/health checks and falling back to local mode if configured.
   - Register observability metrics (counter for acquisitions by backend/outcome, histogram for wait seconds) via a new instrumentation extension (`src/extensions/builtins/rate_limiting.py`). The extension should call a helper in `rate_limiter.py` to inject counters/histograms and register a health check reporting backend mode and last connectivity status. Update `extensions/manifest.json` to include the module.

2. **Integrate configuration.**
   - Extend `RateLimitConfig` in `src/core/config.py` with a nested dataclass `DistributedRateLimitConfig` capturing Redis configuration (`enabled`, `url`, `host`, `port`, `db`, `username`, `password`, `ssl`, `socket_timeout`, `key_prefix`). Parse new environment variables (`RATE_LIMIT_BACKEND`, `RATE_LIMIT_REDIS_URL`, `RATE_LIMIT_REDIS_HOST`, `RATE_LIMIT_REDIS_PORT`, `RATE_LIMIT_REDIS_DB`, `RATE_LIMIT_REDIS_USERNAME`, `RATE_LIMIT_REDIS_PASSWORD`, `RATE_LIMIT_REDIS_SSL`, `RATE_LIMIT_REDIS_TIMEOUT_SECONDS`, `RATE_LIMIT_REDIS_KEY_PREFIX`). Provide validation warnings when Redis is enabled but credentials are missing, and update `get_config_summary` to expose backend mode (without leaking secrets).
   - Update `validate_config` to ensure Redis configuration is coherent (port > 0, key prefix safe, URL parse success) and to add warnings for fallback scenarios.

3. **Wire backend into infrastructure and security.**
   - Refactor `APIRateLimiter` to accept a backend (defaulting to the in-memory backend created from config). When Redis is enabled, instantiate the Redis backend, call `SecurityUtils.register_rate_limit_handler` (new API) so security checks share the same backend, and provide a `status()` method that returns diagnostics for UI/doc display.
   - Replace the global `api_limiter` initialisation with a factory that loads config once and exposes `get_api_limiter()` returning a singleton to avoid eager Redis connections during import. Ensure tests can reset state via helper (e.g., `_reset_backend_for_tests`).
   - In `src/core/security.py`, add `RateLimitDecision` dataclass and `_rate_limit_handler` default, plus `register_rate_limit_handler` and optional `RateLimitHandler` Protocol to allow infrastructure injection. Implement a local default handler using per-identifier in-memory token buckets. Update `rate_limit_check` to delegate to the handler and return failure with descriptive message when the backend rejects the request (include `retry_after` seconds when available). Ensure this logic avoids infrastructure imports.

4. **Add dtype override support.**
   - Extend `normalize_columns` signature to accept `dtype_overrides: Mapping[str, str | type | pd.api.extensions.ExtensionDtype] | None`. Apply overrides after column aliasing but before numeric coercion: create columns with specified dtype, using pandas `astype` with error handling that falls back gracefully and surfaces clear exceptions when conversion fails.
   - Provide helper dataclass `NormalizationOptions` (in `normalize.py` or a new module) to bundle column aliases and dtype overrides for clarity.
   - Update adapters (`src/adapters/bea.py`, `src/adapters/census_asm.py`) and `IdiotIndexService` to accept optional `NormalizationOptions` or `dtype_overrides`, wiring them through from `evaluate_idiot_index` parameter (`normalization_options` defaulting to None).
   - Update UI entrypoint `app.py` to respect optional overrides from configuration (read from new env var `NORMALIZE_DTYPE_OVERRIDES` JSON?) or scenario? For this iteration, expose overrides via config by reading `APP_CONFIG` attribute (to be added) and display them in config summary; allow CLI/API to inject overrides via new parameter (ensure API schema updated if necessary).

5. **Emit retry telemetry.**
   - In `src/core/utils.py`, integrate observability by importing `bootstrap_observability` lazily to avoid heavy dependency in core? Since `core` should not depend on infrastructure, introduce a callable hook similar to rate limiting: define `set_retry_observer` function to register instrumentation handlers. Provide default no-op. Infrastructure extension can attach to `ObservabilityRegistry` to increment counters/histograms and publish events (operation name `http.retry`). Alternatively, since instrumentation requires infrastructure, implement helper in `rate_limiter` instrumentation extension to register a callback located in `src/core/utils.py` by calling a new setter.
   - On each retry attempt and final failure, emit event data to the observer (attempt number, url, reason, backoff). Ensure tests capture the callback invocation.

6. **Surface configuration in UI and docs.**
   - Update `get_config_summary` output to include `rate_limit_backend` dictionary (mode, redis_host, redis_port, key_prefix, health state) without secrets.
   - Modify `app.py` configuration sidebar display to render backend mode, last backend status, and dtype override summary (maybe as `st.sidebar.metric` or in summary JSON). Document new section on distributed rate limiting in README, architecture docs, API reference, plus update `STATUS.md`, `CHANGELOG.md`, `RELEASE_NOTES.md` to record the feature. Add environment variable descriptions to `docs/DEPENDENCIES.md` or other config docs if present.

7. **Testing and fixtures.**
   - Add fakeredis (`fakeredis>=2.23.2,<3`) to `requirements-dev.txt` and `redis>=5.0.1,<6` to runtime requirements. Update detect-secrets baseline if necessary.
   - Create new tests: 
     * `tests/test_rate_limiter.py` verifying local vs Redis backend behaviour, wait logic, and instrumentation hooks (monkeypatching fakeredis).
     * Extend `tests/test_security.py` for handler registration and failure messaging.
     * Extend `tests/test_application.py` to ensure dtype overrides propagate and metrics unaffected.
     * Add tests around retry observer (new test module or extend `test_core.py`).
     * Update UI helper tests if config summary structure changes.

8. **Quality gate and polish.**
   - Ensure new code is typed (mypy adjustments, stub usage). Document new dataclasses in docstrings.
   - Update `CHANGELOG.md`, `RELEASE_NOTES.md`, `STATUS.md` entries with timestamps and summary per repo conventions.
   - Run `make quality-gate` from repo root. Capture output for the final report and add to `Progress` section with timestamp.

## Concrete Steps

1. From `/workspace/idiot-index-app`, read and modify the Python modules listed above, following the sequence in the Plan of Work. Use incremental edits with focused commits.
2. Install any new dev dependencies locally if needed: `pip install fakeredis redis` (will also be handled by updated requirements).
3. Execute unit tests focused on new functionality before the full gate, e.g., `pytest tests/test_rate_limiter.py tests/test_security.py` to iterate quickly.
4. Once the implementation stabilises, run the full gate: `make quality-gate`.
5. Update documentation files and ensure Markdown linting passes (pre-commit handles this).

Expected command transcripts (approximate):

    $ make quality-gate
    black --check app.py src tests
    ruff check app.py src tests
    python -m mypy src
    pytest --cov=src --cov-report=term-missing --cov-report=xml --cov-fail-under=90
    python -m pip_audit ...

## Validation and Acceptance

- Distributed rate limiting: start two `APIRateLimiter` instances with shared Redis backend (fakeredis in tests), confirm they share state by exhausting quota in one and observing blocking in the other. Health check reports `pass` when Redis reachable and `fail` otherwise.
- Security rate limit: calling `SecurityUtils.rate_limit_check("user", 2, 60)` three times returns failure with retry-after metadata on the third call when distributed backend enabled.
- Dtype overrides: pass overrides for a column (e.g., force `industry_code` to `string[python]`) and confirm `normalize_columns` respects dtype while still computing metrics.
- Retry telemetry: when `safe_get_json` experiences transient error (mock `requests.Session.get` to throw) ensure observer receives event with attempt count and delay; tests assert callback invocation.
- Streamlit summary: `app.py` (via tests or manual run) includes new `rate_limit_backend` info in `get_config_summary` JSON; dtype override summary appears.
- Documentation updated with environment variable table and release notes mention.
- `make quality-gate` succeeds.

## Idempotence and Recovery

- Redis backend setup is conditional; if configuration errors occur, fallback to local backend with warning logged. Provide instructions in docs for disabling distributed mode (`RATE_LIMIT_BACKEND=memory`).
- Lua script registration caches SHA hashes; re-running after failure reuses script. Include note to flush fallback state by calling helper `_reset_for_tests()` in tests if needed.
- Changes are additive; rollback can be achieved via `git revert` on the commits.

## Artifacts and Notes

- Capture Lua script snippet and metrics names in docs.
- Record `fakeredis` usage in tests to justify dependency.
- Include health check JSON example in README or docs.

## Interfaces and Dependencies

- New dependency: `redis>=5.0.1,<6` runtime; `fakeredis>=2.23.2,<3` dev/test.
- Lua script executed via `redis.Redis.register_script` or `evalsha` (provide helper function `RedisScriptManager`).
- Observability metrics: counters `rate_limit_requests_total{backend, outcome, scope}`, histogram `rate_limit_wait_seconds{backend, scope}`.
- New dataclasses: `RateLimitRule`, `RateLimitDecision`, `NormalizationOptions`.
- New functions: `SecurityUtils.register_rate_limit_handler`, `SecurityUtils.rate_limit_handler_summary`, `normalize_columns(..., options=NormalizationOptions | None)`, `safe_get_json.set_retry_observer` (name TBD).

Update this plan as milestones complete, documenting surprises, decisions, and final outcomes.
```
