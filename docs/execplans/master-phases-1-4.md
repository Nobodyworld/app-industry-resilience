# Master Phases 1-4 Stewardship Uplift

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Maintain this ExecPlan per `.agent/PLANS.md`.

## Purpose / Big Picture

Combine the remaining stewardship deliverables from stages 1–4 into a focused uplift: automate observability snapshot persistence so deployments retain telemetry across restarts, prune archives to avoid unbounded growth, and document the new operational workflow. While doing so we will refresh steward metrics, changelog/release notes, and supporting docs so contributors inherit an accurate, self-auditing system. Success means operators can enable periodic snapshot capture without touching core services, automation can diff retained state safely, and the repo’s stewardship artefacts reflect the new capabilities with updated quality metrics.

## Progress

- [x] (2025-11-08 12:00Z) Draft ExecPlan capturing goals, context, and proposed implementation steps.
- [x] (2025-11-08 15:05Z) Snapshot persistence extension implemented, registered, and covered by tests (startup capture, error-triggered persistence, retention pruning).
- [x] (2025-11-08 16:10Z) Configuration/schema/docs updated for snapshot retention knobs and automation workflow; CHANGELOG/RELEASE_NOTES/STEWARDS_REPORT refreshed with latest metrics.
- [x] (2025-11-08 16:40Z) Validation complete (`make quality-gate`, audit metrics captured) and ExecPlan sections updated with learnings & outcomes.

## Surprises & Discoveries

- Observation: `observability.snapshot.persisted` events fire from the storage layer when archives rotate, which would recursively trigger the new extension if not filtered.
  Evidence: Guard clause added in `snapshot_persistence.register` to skip events with that name and unit tests asserting only warn/error payloads trigger snapshots.
- Observation: Importing Redis remains optional in quality-gate environments; without defensive guards, the new tests would raise `ModuleNotFoundError` despite using in-memory backends.
  Evidence: Refactored `src/infrastructure/rate_limiter.py` to cast the optional module and synthesise `RedisError` when the dependency is absent.

## Decision Log

- Decision: Load configuration lazily inside the instrumentation extension instead of passing a snapshot at registration.
  Rationale: Ensures retention knobs update automatically when agents reload environment variables without restarting the process.
  Date/Author: 2025-11-08 – Steward Agent.
- Decision: Use the registry’s wildcard subscription with an internal throttle rather than per-event listeners.
  Rationale: Centralises filtering logic (warn/error only) while avoiding missed instrumentation coming from future extensions.
  Date/Author: 2025-11-08 – Steward Agent.

## Outcomes & Retrospective

- Snapshot persistence is hands-off: startup/shutdown and warn/error events capture archives, retention policies are enforced, and automation has a new Snapshot Custodian role.
- Configuration/docs/tests now surface retention knobs consistently, with audit metrics refreshed (93.26% coverage, complexity average 30.0).
- Quality gate and audit runs remain deterministic; optional Redis imports no longer break when the dependency is absent, keeping CI mirrors stable.

## Context and Orientation

Observability snapshots are currently persisted only when operators run the CLI or instrumentation triggers manual saves. `src/extensions/builtins/snapshot_monitor.py` tracks stored archives but does not create them. `SnapshotStorage` (in `src/infrastructure/observability/storage.py`) writes JSON files to a configurable directory (`OBSERVABILITY_SNAPSHOT_DIR`, default `build/observability_snapshots`). Automation relies on `scripts/observability_snapshot.py` and `scripts/diagnostics_bundle.py` to inspect archives, while docs (`docs/OBSERVABILITY_SNAPSHOTS.md`, README Observability section, EXTENSION_GUIDE) describe manual workflows. Configuration lives in `src/core/config.py` with validation/tests under `tests/test_config.py`. Instrumentation extensions register via `extensions/manifest.json` and are orchestrated by `src/extensions/manager.py`. Steward metrics are captured by `scripts/audit_metrics.py` and reported through `STEWARDS_REPORT.md`, `CHANGELOG.md`, and `RELEASE_NOTES.md`.

The new work will add configuration knobs (retention count/age, minimum persistence interval) parsed by `load_config`, expose them in summaries/docs, and implement a new instrumentation extension (e.g., `snapshot_persistence`) that:

1. Captures and persists a snapshot on startup and at shutdown.
2. Subscribes to observability events and records a snapshot when errors occur, throttled by a configurable minimum interval.
3. Prunes stored snapshots according to retention limits.

Tests will cover configuration parsing/validation, extension behaviour, and retention pruning using a temporary storage directory. Documentation must call out new environment variables, configuration summary fields, extension behaviour, and updated operational playbooks.

## Plan of Work

1. **Configuration updates** – Extend `AppConfig` with snapshot retention settings (`observability_snapshot_retention_count`, `observability_snapshot_retention_days`, `observability_snapshot_min_interval_seconds`). Parse environment variables (`OBSERVABILITY_SNAPSHOT_RETENTION_COUNT`, `OBSERVABILITY_SNAPSHOT_RETENTION_DAYS`, `OBSERVABILITY_SNAPSHOT_MIN_INTERVAL_SECONDS`) in `load_config`, add validation rules and config summary output, and update tests in `tests/test_config.py` plus fixtures referencing configuration. Document new knobs in README (`Configuration`/`Observability` sections), `docs/OBSERVABILITY_SNAPSHOTS.md`, and `docs/ARCHITECTURE_OVERVIEW.md`.
2. **Snapshot persistence extension** – Create `src/extensions/builtins/snapshot_persistence.py` implementing an `InstrumentationExtension` that loads config, captures an initial snapshot via `registry.persist_snapshot`, registers an `atexit` hook for shutdown persistence, subscribes to registry events (using `"*"` wildcard) to persist snapshots on error/warn events respecting the min-interval throttle, and prunes archives exceeding retention limits (by count or age). Ensure thread-safety with a lock and exclude the `observability.snapshot.persisted` event to avoid recursion. Register the extension in `extensions/manifest.json`, update tests (`tests/test_extensions.py`) to assert startup capture, error-triggered persistence, and retention pruning using a temp directory and patched config. Add observability docs describing the new automation behaviour.
3. **Docs & stewardship artefacts** – Update `EXTENSION_GUIDE.md`, `AUTOMATION.md`, `README.md`, `docs/OBSERVABILITY_SNAPSHOTS.md`, and `docs/OPERATIONS_INCIDENT_RESPONSE.md` as needed to explain automatic snapshot persistence, retention knobs, and the new extension. Refresh `CHANGELOG.md`, `RELEASE_NOTES.md`, `STATUS.md`, and `STEWARDS_REPORT.md` with the new feature summary, upgrade notes, updated metrics (using `python scripts/audit_metrics.py --runs 3`), and revised roadmap items.
4. **Validation** – Run `make quality-gate`. Capture steward metrics via `python scripts/audit_metrics.py --runs 3` to update `build/reports/audit-metrics.json` and cite results in `STEWARDS_REPORT.md`. Update ExecPlan sections (`Surprises`, `Decision Log`, `Outcomes`) with discoveries and final summary.

## Concrete Steps

1. Modify `src/core/config.py` and related tests/docs for new snapshot retention configuration. Update config summary outputs and environment variable documentation.
2. Implement `snapshot_persistence` instrumentation extension with startup/shutdown/error persistence, throttling, and pruning; register it in `extensions/manifest.json` and cover with unit tests.
3. Refresh documentation (`README.md`, `docs/OBSERVABILITY_SNAPSHOTS.md`, `EXTENSION_GUIDE.md`, `AUTOMATION.md`, `STATUS.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `STEWARDS_REPORT.md`) to describe the new automation, metrics, and roadmap adjustments.
4. Run `make quality-gate` and `python scripts/audit_metrics.py --runs 3`, update ExecPlan log sections, and ensure all artefacts (coverage report, metrics JSON) are committed.

## Validation and Acceptance

- `make quality-gate` passes with all lint/type/test/security checks succeeding.
- `python scripts/audit_metrics.py --runs 3` completes, producing updated metrics referenced in `STEWARDS_REPORT.md`.
- Tests cover the new extension’s startup persistence, error-triggered snapshot, and retention pruning, plus configuration parsing/validation for new env vars.
- Documentation explicitly references the automatic snapshot persistence extension, new env variables, and updated operational workflow.
- `extensions_catalog.py` lists the new instrumentation extension.

## Idempotence and Recovery

- Configuration parsing defaults ensure deployments without the new env vars maintain previous behaviour (manual snapshot capture only). Retention defaults use conservative values to avoid mass deletion; pruning routines operate on copies and skip when thresholds are non-positive.
- The extension’s `atexit` handler runs best-effort; failures log events but do not raise at interpreter exit. Persistence functions guard with locks and throttle intervals, so repeated registration is safe.
- Tests reset environment and extension state after execution; any stored snapshots reside under `tmp_path` and are cleaned up automatically.

## Artifacts and Notes

- Will capture excerpts from `make quality-gate`, `python scripts/audit_metrics.py --runs 3`, and unit test output demonstrating snapshot persistence.

## Interfaces and Dependencies

- New config fields surfaced via `AppConfig` and `get_config_summary`.
- `snapshot_persistence` instrumentation extension depends on `ObservabilityRegistry.persist_snapshot`, `SnapshotStorage`, and `load_config`.
- Tests rely on pytest fixtures (`tmp_path`, `monkeypatch`) and ObservabilityRegistry.
- Documentation updates reference existing scripts (`scripts/observability_snapshot.py`, `scripts/diagnostics_bundle.py`) and automation guides.
