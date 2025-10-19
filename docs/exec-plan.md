```md
# Hardening Idiot Index App for Production Readiness

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Maintain this document in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

The goal is to leave the Idiot Index application production-ready. A user must be able to install the package, run the Streamlit UI or automated data processing jobs, and trust that configuration, normalization, metrics, and security layers behave predictably. By the end, the repository should expose a typed configuration system, resilient caching, strict input validation, comprehensive normalization and metric calculations, and regression tests that guarantee these guarantees. Running `pytest` should pass, and launching `streamlit run app.py` must succeed with validated config even when environment variables are missing.

## Progress

- [x] (2025-01-16 12:20Z) Captured current state and authored initial ExecPlan.
- [x] Establish Python package structure and shared constants module.
- [x] Replace ad-hoc configuration globals with typed settings loader and validation utilities.
- [x] Harden normalization and metric computation with richer validation and well-defined error handling.
- [x] Modernize security utilities (file upload, string sanitization, API keys) with deterministic policies and logging hooks.
- [x] Refactor cache helpers for deterministic TTL, statistics, and safe teardown; eliminate dead globals.
- [x] Align utility HTTP client with retry/circuit-breaker scaffolding and type hints.
- [x] Update Streamlit entrypoint to consume new modules, surface actionable errors, and remove outdated TODOs.
- [x] Expand automated tests to cover config loading, normalization edge cases, metrics caching, security policies, and HTTP utilities.
- [x] Refresh documentation (README, docs/) to describe configuration, security posture, and testing workflow.
- [x] Run full test suite and linting; ensure repository is clean.

## Surprises & Discoveries

- Observation: Streamlit uploads provide file-like objects without filesystem paths, so validation must accept raw metadata.
  Evidence: `SecurityUtils.validate_file_upload` now supports `file_size_bytes` to accommodate in-memory uploads.

## Decision Log

- Decision: Load configuration lazily inside computational modules but short-circuit caching when disabled to avoid filesystem writes during tests.
  Rationale: Ensures deterministic behavior in both production and CI environments without global state leakage.
  Date/Author: 2025-01-16 / gpt-5-codex

## Outcomes & Retrospective

- Comprehensive refactor delivered typed configuration, cache abstractions, hardened security, and updated Streamlit UX. Tests now cover configuration, metrics, normalization, security, and HTTP utilities with deterministic cache fixtures. README documents configuration validation and development workflow. No regressions observed after running `pytest`.

## Context and Orientation

The repository root contains the Streamlit entrypoint `app.py`, reusable modules under `src/`, and tests in `tests/`. Modules depend on implicit globals (e.g., `src/config.py` loads environment variables at import time) and lack package initialization, causing `ModuleNotFoundError` during tests. Many TODOs flag missing validations, secure defaults, and rate limiting. Configuration, caching, security, normalization, and metric modules are loosely typed and interdependent but unstructured.

Key modules today:
- `src/config.py` – defines module-level constants derived from environment variables without validation or encapsulation.
- `src/normalize.py` and `src/metrics.py` – operate on Pandas DataFrames but do minimal validation.
- `src/cache.py` – implements a file-based cache with global singletons and incomplete cleanup.
- `src/security.py` – provides validation helpers but lacks configurability and consistent error types.
- `src/utils.py` – exposes `safe_get_json` with primitive retry semantics.
- `tests/` – rely on importing `src` but package is not configured, leaving the suite failing at import.

We must reorganize `src/` into a proper package, introduce typed dataclasses and service objects, and ensure tests cover the critical components. Documentation should explain configuration, caching, and testing.

## Plan of Work

1. **Package Foundation and Shared Types**
   - Add `src/__init__.py` exporting key public functions and dataclasses to make `src` importable.
   - Introduce `src/types.py` (or similar) for reusable TypedDict/NamedTuple definitions for config validation results and caching stats if needed.

2. **Configuration System Overhaul**
   - Replace `src/config.py` globals with a dataclass `AppConfig` loaded through a `load_config` function that reads environment variables lazily and validates values.
   - Implement environment detection with enumerations, typed API key wrappers, caching/rate limits, and sanitized defaults.
   - Provide `validate_config` returning structured errors and warnings, plus `get_config_summary` referencing dataclass values.
   - Ensure modules consume configuration via accessor functions rather than module-level constants.

3. **Caching Infrastructure Modernization**
   - Refine `src/cache.py` with explicit `Cache` class typed methods, context-aware TTL control, instrumentation, and elimination of legacy globals.
   - Provide factory functions `get_api_cache` / `get_computation_cache` returning singleton caches using thread-safe lazy initialization.
   - Add support for clearing/inspecting caches for tests.

4. **Normalization and Metrics Improvements**
   - Update `src/normalize.py` to define required/optional columns as tuples, implement flexible column mapping (support alias dictionaries), strict dtype conversion with descriptive errors, and normalization of string columns.
   - Enhance `coerce_numeric` with Decimal-safe conversion and invalid data detection.
   - Expand `src/metrics.py` to validate denominators, guard against divide-by-zero, ensure caching keys consider schema, and produce typed floats.

5. **Security Utilities Hardening**
   - Update `SecurityUtils` methods to use consistent typed return objects (e.g., dataclasses) or `SecurityResult` tuples with reason codes.
   - Make file validation accept file-like uploads, size constraints, allowed MIME types, and sanitized filenames; integrate environment config for limits.
   - Improve CSV content scanning (sample strategy, pattern precompilation) and API key validation (prefix awareness, whitespace trimming).
   - Provide sanitized string utility with optional HTML escaping and ensure dangerous patterns compiled once.

6. **HTTP Utility Enhancements**
   - Rewrite `safe_get_json` with typed parameters, exponential backoff, jitter, maximum retry error aggregation, and optional circuit breaker stub to remove TODO.
   - Provide helper exceptions for HTTP layer.

7. **Streamlit Entrypoint Alignment**
   - Update `app.py` to use new configuration loader, handle initialization errors gracefully, and ensure TODOs for missing features are closed or replaced with actionable guidance.
   - Ensure caching/metrics/normalization imports use package-level exports and add typed hints.

8. **Testing Expansion**
   - Update `tests/` to import the new modules via package, add tests for `AppConfig`, caching behavior, normalization alias mapping, metrics caching reuse, security validators, and HTTP utility retry logic (with mocks).
   - Ensure tests clean up cache directories via fixtures.

9. **Documentation and Tooling**
   - Refresh `README.md` with setup instructions, environment configuration, security posture, and testing commands.
   - Document caching directories and config validation usage.
   - Add `pyproject.toml` or `ruff` config if missing for formatting (optional) or at least ensure `requirements-dev.txt` lists dev deps.

10. **Validation**
    - Run `pytest` to ensure green.
    - Optionally run `ruff`/`black` if configuration is added or rely on `pytest` only.

## Concrete Steps

- `touch src/__init__.py` and populate exports.
- Create `src/types.py` with dataclasses or TypedDicts for config validation results if needed.
- Rewrite `src/config.py` to define `Environment` Enum, `AppConfig` dataclass, `load_config`, `validate_config`, and summary functions.
- Refactor `src/cache.py`, `src/normalize.py`, `src/metrics.py`, `src/security.py`, and `src/utils.py` per Plan of Work.
- Adjust `app.py` imports and logic to consume new interfaces.
- Update or add tests covering config loading, caching, normalization, metrics, security, and HTTP utilities; ensure fixtures clean caches.
- Modify `requirements-dev.txt` if new dev tools introduced.
- Update `README.md` with new instructions, referencing config validation and tests.
- Execute `pytest`.

## Validation and Acceptance

- Running `pytest` from repository root must pass with all tests green.
- Manual invocation `streamlit run app.py` (not run in CI) should use new config loader without runtime errors; instructions in README must describe expected output.
- Cache directories should be created lazily and cleaned in tests; running tests twice should not leave stale state.

## Idempotence and Recovery

- Configuration loader reads environment variables on each call; rerunning tests reuses same directories but fixtures clear caches.
- Cache `clear()` methods allow manual cleanup if tests fail mid-run.
- Streamlit entrypoint handles errors by surfacing sidebar messages and `st.stop()`, preventing inconsistent state.

## Artifacts and Notes

- Capture representative outputs (e.g., config validation warnings) within tests.
- Include sample config summary in README to guide users.

## Interfaces and Dependencies

- Avoid new heavy dependencies; rely on standard library plus existing requirements.
- Introduce any new dependency (e.g., `typing_extensions`) only if necessary and document in requirements.
- Public interfaces after refactor:
    - `src.config.load_config() -> AppConfig`
    - `src.config.validate_config(config: AppConfig) -> ConfigValidationResult`
    - `src.cache.Cache`, `get_api_cache()`, `get_computation_cache()`
    - `src.normalize.normalize_columns(df: pd.DataFrame, column_aliases: Optional[Mapping[str, str]] = None) -> pd.DataFrame`
    - `src.metrics.compute_metrics(df: pd.DataFrame, cache: Optional[Cache] = None) -> pd.DataFrame`
    - `src.security.SecurityUtils` static methods returning `(bool, str)` or richer types as defined.
    - `src.utils.safe_get_json(...) -> Dict[str, Any] | List[Any]`
```
