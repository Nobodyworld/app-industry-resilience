# Production-grade Hardening & Type Safety Sweep

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Maintain this document in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

The application already exposes resilient data adapters, modular Streamlit UI helpers, and structured logging, but static typing gaps and a few loose ends undermine long-term maintainability. By tightening the shared validation types, hardening normalization and security utilities, and aligning logging payload handling with strict typing, we can run `mypy` cleanly, catch issues earlier, and ensure downstream modules receive predictable inputs. The outcome should be a repository that passes tests **and** type-checking, with targeted unit tests guarding new edge cases.

## Progress

- [x] (2025-02-17 12:30Z) Captured current state and authored initial ExecPlan.
- [x] (2025-02-17 13:05Z) Align `ValidationResult` generic semantics and update security helpers to return precise types.
- [x] (2025-02-17 13:15Z) Harden normalization/year coercion and computation caching to satisfy strict typing without regressions.
- [x] (2025-02-17 13:25Z) Refine logging configuration redaction utilities for explicit payload typing and remote handler clarity.
- [x] (2025-02-17 13:45Z) Remove stale ignores, ensure optional dependencies degrade gracefully, and backfill tests/type checks (`pytest`, `mypy`).
- [x] (2025-02-17 14:05Z) Reject fractional year inputs via shared validation logic and extend tests to guard the tighter contract.
- [x] (2025-02-17 15:20Z) Tighten configuration URL validation, enforce remote logging protocol guards, and extend cache/config/logging tests for corrupted payloads and TTL expiry.

## Surprises & Discoveries

- Observation: `ValidationResult` currently models failure returns as `ValidationResult[Optional[T]]`, forcing callers to widen type expectations and breaking `mypy` invariants.
  Evidence: `src/core/types.py` failure constructor signature and resulting `mypy` errors for `SecurityUtils`.
- Observation: Logging helpers treat payload dicts as `dict[str, str]`, so merging redacted objects violates typing; explicit `dict[str, object]` typing fixes the mismatch.
  Evidence: `mypy` error `Argument 1 to "update" ... expected "SupportsKeysAndGetItem[str, str]"` when updating payload with `_redact_mapping`.
- Observation: Legacy compatibility shim `src/sources/bea.py` mutated `__all__` dynamically, confusing `mypy` once validation tightened.
  Evidence: `mypy` flagged `type: ignore` usage and unresolved `__all__` during adapter package checks.
- Observation: Configuration accepted non-HTTP URLs for BEA endpoints and remote logging protocols outside TCP/UDP, risking misconfiguration without early feedback.
  Evidence: `load_config` `_parse_url_list` and `_remote_from_env` performed only presence checks, so values like `ftp://` URLs or `smtp` protocols passed silently.

## Decision Log

- Decision: Prefer adjusting shared helper implementations (`ValidationResult`, logging utilities) over sprinkling `type: ignore` comments to keep type discipline centralized.
  Rationale: Central fixes reduce maintenance overhead and future regressions.
  Date/Author: 2025-02-17 / gpt-5-codex
- Decision: Fail fast on malformed BEA base URLs and unsupported logging protocols to avoid runtime surprises during deployment rollouts.
  Rationale: Configuration errors should surface during startup validation rather than during live API calls or logging initialisation.
  Date/Author: 2025-02-17 / gpt-5-codex

## Outcomes & Retrospective

- Tightened `ValidationResult` semantics let security, normalization, and BEA adapters propagate precise types without `Optional` noise. Logging payloads now use explicitly typed dictionaries and remote handler variables, while compatibility shims avoid runtime mutation of `__all__`. Year validation now rejects fractional inputs consistently across the security and normalization layers. Configuration now rejects non-HTTP BEA endpoints and unsupported remote logging protocols, cache resilience is covered by corruption/expiry tests, and BEA fetch failures propagate via `BEAClientError`. `mypy` passes across core modules, adapters, infrastructure, Streamlit helpers, and the Streamlit entrypoint, and the expanded test suite covers validation, configuration, caching, and logging edge cases alongside the existing suite.

## Context and Orientation

Key modules involved in this sweep:
- `src/core/types.py` defines `ValidationResult` used throughout security, config, and normalization validators.
- `src/core/security.py` and `src/core/normalize.py` rely on that type to validate uploaded CSVs, API keys, and numeric coercion.
- `src/core/metrics.py` caches computations and currently triggers optional-access typing warnings.
- `src/infrastructure/logging_config.py` implements structured logging, redaction, and remote handler wiring; typing issues surface here.
- `src/core/utils.py` hosts the HTTP retry helper used by adapters, including missing imports and typing mismatches.
- Tests in `tests/test_security.py`, `tests/test_core.py`, and `tests/test_logging.py` cover these behaviours and will need updates or additions if semantics change.

## Plan of Work

1. **ValidationResult & Security alignment**
   - Update `src/core/types.py` so `ValidationResult` holds `value: T | None`, while `success`/`failure` constructors preserve `ValidationResult[T]`. Add docstring clarifying semantics.
   - Adjust security validators in `src/core/security.py` to rely on the refined type, improving year parsing via `Decimal` to avoid float round-off, and explicitly sanitise API key handling.
2. **Normalization & Metrics hardening**
   - Modify `_coerce_year` in `src/core/normalize.py` to avoid `float` casts, using `Decimal`/string parsing instead. Ensure `_coerce_numeric` gracefully handles non-str inputs with strong typing.
   - In `src/core/metrics.py`, guard cache access with explicit `if cache_instance is not None` assertions so type checkers see non-optional values when used.
3. **Logging & HTTP utilities**
   - In `src/infrastructure/logging_config.py`, annotate payload dicts as `dict[str, object]`, ensure `_redact_mapping` returns that type, rename `handler` variables to avoid collisions, and clarify formatter behaviour in docstrings.
   - Update `log_api_call`/`log_performance` to operate on typed payload copies rather than mutating string-only dicts.
   - In `src/core/utils.py`, import `random`, add module-level annotations (or targeted `type: ignore` with rationale) for `requests`, and ensure retry loop handles HTTP errors without referencing undefined variables.
4. **UI helper cleanup & tests**
   - Remove the stale `# type: ignore[call-arg]` by wrapping Excel writer creation behind a protocol-friendly helper or cast so mypy understands the argument.
   - Extend or adjust tests (e.g., `tests/test_security.py` for refined year parsing edge cases, `tests/test_logging.py` for typed payload assertions) to cover new behaviour.
5. **Validation**
   - Run `pytest` and `mypy src` from repository root, ensuring both succeed. Document results and update this plan’s `Progress` and `Outcomes` sections accordingly.

## Concrete Steps

- Edit `src/core/types.py`, `src/core/security.py`, `src/core/normalize.py`, `src/core/metrics.py`, `src/infrastructure/logging_config.py`, `src/core/utils.py`, and `src/interfaces/streamlit/helpers.py` following the plan above.
- Update/add tests in `tests/test_security.py` and, if necessary, `tests/test_logging.py` to reflect tightened validations.
- From `/workspace/app-industry-resilience`, run:
    - `mypy src`
    - `pytest`

## Validation and Acceptance

- Segmented `mypy` runs across core packages and the Streamlit entrypoint report no errors.
- `pytest` passes with updated/added tests covering refined validators and logging payload handling.
- Manual inspection confirms logging payloads redact sensitive keys and API key/year validators behave as expected (e.g., rejecting empty strings, parsing string years without floating artefacts).

## Idempotence and Recovery

- Type changes are additive and backward compatible; rerunning `mypy`/`pytest` is safe.
- If a change introduces regressions, git checkout of individual files reverts quickly; no migrations or external state involved.

## Artifacts and Notes

- Capture `mypy` transcript in plan updates once it succeeds to document the zero-error run.
- Reference test cases demonstrating new validation outcomes for future contributors.

## Interfaces and Dependencies

- No new runtime dependencies. Optional Excel export continues to use `xlsxwriter` only when available.
- Public interfaces remain stable; `ValidationResult` still exposes `ok`, `value`, `message`, but type semantics are clarified.
- Logging functions continue to accept the same parameters with enhanced typing guarantees.
