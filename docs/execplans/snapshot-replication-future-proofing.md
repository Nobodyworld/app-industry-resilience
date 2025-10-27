# Snapshot replication modularisation and telemetry uplift

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Maintain this ExecPlan per `.agent/PLANS.md`.

## Purpose / Big Picture

Remote observability snapshot replication now exists but operates as a single S3-specific pathway with minimal telemetry. After delivering this plan, operators and automation will be able to plug in additional replication backends, observe replication health through metrics and health checks, and scaffold new replication connectors without touching core infrastructure code. A debug-friendly reference extension will demonstrate the pattern while documentation, automation guides, and architecture notes will show contributors how to build on the modular layer.

Observable outcomes:

* `build_snapshot_replicator` can delegate to registered replication extensions and honours plugin-specific configuration options.
* The observability registry emits `observability.snapshot.replication` events with structured success and failure metadata, and metrics/health gauges expose replication status.
* A built-in debug replication extension writes snapshots to a local directory when configured via `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND=plugin:debug`, proving the new interface and scaffolding pattern.
* Docs (EXTENSION_GUIDE, ARCHITECTURE_OVERVIEW, OBSERVABILITY_SNAPSHOTS, AUTOMATION, README) and automation assets describe the plugin seam, the new environment knobs, and the observability guarantees.

## Progress

- [x] (2025-11-10 03:40Z) Draft ExecPlan covering replication modularisation, telemetry, and documentation deliverables.
- [x] (2025-11-10 05:05Z) Implement replication extension contract, manager support, and configuration plumbing for plugin backends/options.
- [x] (2025-11-10 05:50Z) Emit replication events from the snapshot persistence flow and add instrumentation/health surfaces.
- [x] (2025-11-10 06:25Z) Add the debug replication extension, update manifests/tests, and refresh docs/automation notes.
- [x] (2025-11-10 07:20Z) Run `make quality-gate`, capture artefacts, and complete retrospective with Evolvability score and opportunities.

## Surprises & Discoveries

- Observation: `get_extension_manager()` recursively loaded extensions while `_MANAGER_SINGLETON` was `None`, so the snapshot persistence extension attempted to build a replicator before replication providers registered.
  Evidence: Without pre-seeding the singleton, `build_snapshot_replicator` re-entered `load_extensions`, leading to duplicate registrations in exploratory runs.

## Decision Log

- Decision: Pre-seed the global `ExtensionManager` singleton before loading modules so replication builders can consult extensions safely during import-time registration.
  Rationale: Snapshot persistence registers during `load_extensions`; without an initialised manager the replicator builder would recursively trigger manifest loading.
  Date/Author: 2025-11-10 / gpt-5-codex

- Decision: Emit `observability.snapshot.replication` events with status `success|error|skipped` and capture them via a dedicated instrumentation extension rather than embedding metrics in the persistence hook itself.
  Rationale: Separating event emission from metric collection keeps the persistence extension focused on durability while allowing additional listeners (e.g., future alerting extensions) to subscribe without tight coupling.
  Date/Author: 2025-11-10 / gpt-5-codex

## Outcomes & Retrospective

### Validation Snapshot

- `make quality-gate` succeeded locally, covering formatting, linting, type checks, tests, and security placeholders. Trace coverage held at **93.26 %** with the replication plugin suite included.
- Added regression coverage for replication instrumentation and CLI reporting so replication events coexist with existing snapshot persistence telemetry.
- Confirmed optional botocore dependency handling continues to skip S3-specific tests without failures.

### Evolvability Score

- **Score:** 8.5 / 10 — modular replication extensions, manifest-driven discovery, and instrumentation hooks provide clear seams; further work could include async replication pipelines and richer plugin scaffolds.

### Opportunities

- Build an integration-test harness that simulates plugin-provided replicators emitting failure events to exercise backoff/retry behaviours.
- Automate coverage report publishing for observability modules to monitor regressions in instrumentation quality.
- Explore agent-runbooks that tail replication events and trigger automated remediation workflows.

## Context and Orientation

Snapshot replication is orchestrated from `src/infrastructure/observability/replication.py`, where `build_snapshot_replicator` constructs either a no-op or `S3SnapshotReplicator`. The `src/extensions/builtins/snapshot_persistence.py` instrumentation extension invokes this builder to upload snapshots after persistence. Configuration is parsed in `src/core/config.py`, tests live in `tests/test_config.py` and `tests/test_observability_replication.py`, and automation/CLI entry points (notably `scripts/observability_snapshot.py`) call into the same builder. Documentation for observability lives across `docs/OBSERVABILITY_SNAPSHOTS.md`, `ARCHITECTURE_OVERVIEW.md`, `EXTENSION_GUIDE.md`, and automation guides such as `AUTOMATION.md`.

The extension system is implemented in `src/extensions/manager.py` with contracts in `src/extensions/contracts.py` and built-in modules under `src/extensions/builtins/`. Any new extension type must hook into this manager so manifest-driven loading remains consistent for humans and agents.

## Plan of Work

First, extend `SnapshotRemoteStorageConfig` to capture backend-specific options and permit plugin-oriented backend identifiers while updating validation logic to recognise S3 vs. plugin backends. Expand config tests to cover options parsing and plugin scenarios.

Second, introduce a `ReplicationExtension` protocol and teach `ExtensionManager` to register and resolve replicator implementations. Adjust `get_extension_manager` initialisation to avoid recursion when the builder consults the manager during module loading. Update `build_snapshot_replicator` to prefer extension-provided replicators before falling back to the built-in S3 logic, and expose helper functions so extensions can reuse S3 creation utilities without duplicating internals.

Third, modify the snapshot persistence extension to time replication operations, emit `observability.snapshot.replication` events with attributes describing backend, reason, duration, and errors, and to always close replicators cleanly. Create a companion instrumentation extension that subscribes to these events, maintains counters/histograms/gauges, and registers a health check reflecting the last replication status and age of the most recent success.

Fourth, add a reference debug replication extension that implements the new contract by copying snapshot files to a configured directory (from options or defaults). Register both the S3 and debug replication extensions in a new `snapshot_replication` module and update `extensions/manifest.json` so they load automatically before snapshot persistence runs. Expand the snapshot CLI and tests to exercise plugin resolution, metrics updates, and error paths without requiring S3 credentials.

Finally, refresh documentation and automation artefacts (docs mentioned above, README, STATUS, STEWARDS_REPORT, RELEASE_NOTES, CHANGELOG, AUTMATION) to describe the new plugin seam, instrumentation surfaces, Evolvability score, and next-generation opportunities. Conclude by running `make quality-gate` and recording outcomes in this ExecPlan.

## Concrete Steps

1. Edit `src/core/config.py` to add `options` support, broaden backend parsing, and update validation/summary helpers. Update associated tests under `tests/test_config.py`.
2. Update `src/extensions/contracts.py` and `src/extensions/manager.py` for the replication extension contract, adjusting `get_extension_manager` initialisation and adding tests under `tests/test_extensions.py`.
3. Enhance `src/infrastructure/observability/replication.py` with extension-aware builder logic and helper exports, plus new unit tests in `tests/test_observability_replication.py`.
4. Update `src/extensions/builtins/snapshot_persistence.py` to emit replication events and ensure replicator closure. Create `src/extensions/builtins/snapshot_replication.py` with S3/debug replication extensions and instrumentation, updating the manifest and writing targeted tests.
5. Refresh CLI/tests (`scripts/observability_snapshot.py`, `tests/test_scripts.py`) and documentation assets (README, docs/OBSERVABILITY_SNAPSHOTS.md, docs/ARCHITECTURE_OVERVIEW.md, EXTENSION_GUIDE.md, AUTOMATION.md, STATUS.md, STEWARDS_REPORT.md, RELEASE_NOTES.md, CHANGELOG.md) to reflect the modular replication layer, telemetry, and future-proofing guidance.
6. Run `make quality-gate` and capture any artefacts or surprises for inclusion in this ExecPlan.

## Validation and Acceptance

Run `make quality-gate` from the repository root. Acceptance requires all checks to pass and the new tests covering replication extensions, metrics, and CLI behaviour to succeed. Manual validation can invoke `python scripts/observability_snapshot.py --store --pretty` with `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND=plugin:debug` and `OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS` pointing at a temp directory to confirm debug replication writes files and logs events.

## Idempotence and Recovery

Configuration parsing changes are pure functions; rerunning `make quality-gate` is safe. Replication event emission is guarded and the debug extension copies files deterministically into its target directory; deleting that directory resets state. If new metrics or health checks misbehave, disabling the manifest entry or setting the backend to `off` restores the previous behaviour without code changes.

## Artifacts and Notes

Planned artefacts include updated unit test snapshots (if any), coverage metrics from the quality gate, and documentation diffs describing the new plugin seam. Capture representative stderr output from the snapshot CLI running in debug mode to include in the retrospective if it illuminates the workflow.

## Interfaces and Dependencies

Define `ReplicationExtension` in `src/extensions/contracts.py` with methods `supports(config: SnapshotRemoteStorageConfig) -> bool` and `build(config: SnapshotRemoteStorageConfig) -> SnapshotReplicator`. Update `ExtensionManager` with `register_replication_extension` and `build_replication_backend`. Provide helper `_build_s3_replicator(config)` returning `S3SnapshotReplicator`. Expose metrics named `idiot_index_snapshot_replications_total`, `idiot_index_snapshot_replication_latency_seconds`, and `idiot_index_snapshot_replication_age_seconds`. Debug replication extension should honour option key `path` (string) defaulting to `observability_snapshot_dir / "debug-replication"`.

