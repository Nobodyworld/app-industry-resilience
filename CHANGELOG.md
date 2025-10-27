# Changelog

# 2025-11-10 – Replication plugins & telemetry uplift
- Introduced the `ReplicationExtension` contract and taught `ExtensionManager` to resolve plugin backends before falling back to built-in replicators, enabling out-of-tree connectors.
- Emitted `observability.snapshot.replication` events from the persistence extension and shipped the `snapshot_replication` instrumentation module with replication counters, latency histograms, and a dedicated health component.
- Added a debug filesystem replicator (`plugin:debug`), CLI messaging for both S3 and debug backends, plugin-aware configuration options (`OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS`), and comprehensive unit tests/docs covering the new workflow.

# 2025-11-10 – Snapshot replication hardening
- Normalised metadata serialisation in the S3 replicator so nested mappings, sequences, and sets are encoded as deterministic
  JSON strings instead of relying on Python reprs, keeping remote archives friendly to consumers expecting structured metadata.
- Added a targeted regression test that validates the S3 replicator emits normalised metadata (IDs, timestamps, JSON-encoded
  nested values) so future refactors keep remote archives queryable.

# 2025-11-09 – Snapshot remote replication
- Added S3-compatible snapshot replication with the new `SnapshotRemoteStorageConfig`, `build_snapshot_replicator(...)`, and the `S3SnapshotReplicator`, ensuring automatic uploads whenever snapshots are persisted by the extension or CLI while preserving local disk durability.
- Extended configuration parsing/validation and `get_config_summary` with remote backend settings plus environment-variable support for bucket, prefix, endpoint, credentials, and retry tuning.
- Updated the observability CLI to report remote destinations, added replication unit tests (`tests/test_observability_replication.py`, script/extension stubs), and refreshed docs (README, OBSERVABILITY_SNAPSHOTS, EXTENSION_GUIDE, AUTOMATION, STATUS, RELEASE_NOTES, STEWARDS_REPORT) so operators can enable the feature confidently.

# 2025-11-08 – Snapshot persistence automation
- Introduced the `snapshot_persistence` instrumentation extension so observability snapshots are captured automatically on startup/shutdown and after `warn`/`error` events, including retention pruning governed by new configuration knobs.
- Extended configuration loading/validation with `OBSERVABILITY_SNAPSHOT_RETENTION_COUNT`, `OBSERVABILITY_SNAPSHOT_RETENTION_DAYS`, and `OBSERVABILITY_SNAPSHOT_MIN_INTERVAL_SECONDS`, refreshed tests, and exposed the values via `get_config_summary`.
- Updated docs (README, OBSERVABILITY_SNAPSHOTS, EXTENSION_GUIDE, AUTOMATION, STATUS) and extension catalog/tests to reflect the new workflow and ensure automation inherits the extension by default.

# 2025-11-05 – Observability diagnostics & snapshot guardrails
- Added `/observability/events` to expose filtered, reverse-chronological telemetry along with unit tests and schema updates so automation can replay recent incidents without parsing full digests.
- Introduced the `snapshot_monitor` instrumentation extension plus `observability.snapshot.persisted` events, publishing gauges/health checks for snapshot freshness and tightening documentation around archival workflows.
- Shipped `scripts/diagnostics_bundle.py` and refreshed README, architecture, and automation guides so operators (and agents) can capture one-shot JSON bundles combining health probes, digests, events, and snapshot metadata.

## 2025-11-02 – Snapshot validation & operational hardening
- Sanitised observability snapshot identifiers across storage, the CLI, and API detail endpoint to reject path traversal attempts and return clear 400 responses for malformed IDs.
- Added a `SnapshotStorage.path_for` helper and associated unit tests, ensuring automation can safely resolve stored snapshot paths without bypassing validation.
- Tightened docs and analytics API tests to cover the new security guardrails while preserving snapshot list/detail behaviour for well-formed identifiers.

## 2025-10-31 – Observability recorders & audit resiliency
- Added `ObservabilityRegistry.record_event(...)` so services and extensions can emit telemetry without spinning up empty context managers, and refactored Idiot Index pipelines to use the helper for dataset/scenario profiling.
- Updated observability tests, documentation, and the data-quality instrumentation workflow to cover the new API while preserving existing event subscriptions.
- Enhanced `scripts/audit_metrics.py` with a `coverage.xml` fallback so steward audits stay functional even when the trace coverage JSON is unavailable.

## 2025-10-26 – Observability digest & extension catalog
- Introduced `/observability/digest`, the `observability_tail.py` streaming CLI, and the `extensions_catalog.py` inventory command so operators can inspect telemetry and registered extensions without code changes.
- Instrumented dataset and scenario pipelines with profile events and shipped the `data_quality` instrumentation extension, exposing gauges for row counts/missing ratios plus a targeted health check.
- Expanded Make targets, automation docs, and tests to cover the new tooling while updating README, EXTENSION_GUIDE, and incident response playbooks.

## 2025-10-30 – Rate limiter hardening & deterministic tests
- Removed the recursive wait loop from token buckets to prevent stack growth under heavy contention and added guard rails that
  reject zero/blank rule definitions.
- Tracked the active backend for Redis token buckets so fallbacks surface as `redis-fallback` in summaries, metrics, and health
  diagnostics while preserving the configured backend label for security handlers.
- Added self-contained tests covering wait semantics, fallback instrumentation, and configuration validation without requiring
  `fakeredis`, using a lightweight stub to emulate Lua script execution.

## 2025-10-29 – Distributed rate limiting & schema overrides
- Added Redis-backed token bucket coordination with in-memory fallback, health reporting, and Prometheus metrics via the new `rate_limiting` instrumentation extension.
- Replaced the stubbed security rate-limit check with a pluggable handler and surfaced backend diagnostics in the Streamlit sidebar and `/observability/status` payload.
- Introduced `NormalizationOptions` and the `NORMALIZE_DTYPE_OVERRIDES` env var so operators can pin pandas dtypes without code changes; adapters and services honour overrides while bypassing caches to preserve metadata.
- Emitted structured HTTP retry events from `safe_get_json` and wired them into observability metrics to highlight flaky upstream dependencies.
- Documented the new configuration knobs, dependencies (`redis`, `fakeredis`), and added targeted tests for distributed rate limiting, dtype overrides, and retry telemetry.

## 2025-10-28 – Observability unification
- Added the `ObservabilityRegistry` to centralise metrics, tracing, and health contributions; instrumented `IdiotIndexService`, `ScenarioPlanner`, and the API to emit structured events.
- Introduced the `core_instrumentation` extension, `/observability/status` endpoint, and `scripts/observability_snapshot.py` CLI for unified monitoring in both online and offline environments.
- Expanded developer scaffolds (`scaffold_extension.py --instrumentation`, `scaffold_service.py`) and documentation (architecture, automation, incident response) so future modules stay observability-ready.
- Updated Dependabot configuration, Makefile targets, and contributor guidance to reinforce continuous improvement loops.

## 2025-10-26 – Health analytics hardening
- Vectorised health-band classification and tightened top-risk selection so analytics run faster and handle NaN-heavy datasets without misclassifying results.
- Added targeted tests for health summaries (grouping modes, zero top-risk limit, missing values) and new script coverage helpers to keep quality high.
- Introduced `scripts/run_tests_with_trace.py` plus Makefile improvements that enforce coverage thresholds even when `pytest-cov` is unavailable, defaulting to the analytics/application/API modules with overrideable paths.

## 2025-10-25 – Health analytics expansion
- Added `src/core/analytics` with composite health scoring, band distribution, and cohort aggregation reused by services, the UI, and the API.
- Extended Idiot Index summaries, Streamlit components, and Scenario Lab to surface health insights, risk band shifts, and top-risk industries.
- Introduced the `/analytics/health` API endpoint, updated `/evaluate`/`/scenario` payloads, and added the `scripts/analytics_health.py` CLI alongside a `make analytics` target.
- Relaxed dependency pins to track latest compatible releases and refreshed documentation (README, architecture, API guides, new `docs/ANALYTICS_HEALTH.md`).

## 2025-10-27
- Completed Stage 4 steward audit with `STEWARDS_REPORT.md`, adding measured coverage/complexity/dependency/latency metrics and
  a refreshed roadmap.
- Delivered `scripts/audit_metrics.py`, the `make audit` target, and `AUTOMATION_ROLES.md` so agents can gather stewardship data
  and coordinate responsibilities.
- Simplified API telemetry span handling, tagged observability/audit make targets as `# agent-safe-task`, and ensured every
  script bootstraps the repo root for direct execution.

## 2025-10-25
- Added a reusable `HealthProbe` in `src/infrastructure/observability` powering richer `/health` responses and the new
  `scripts/check_health.py` CLI.
- Updated the headless API to expose component-level health metadata and telemetry counts while maintaining backward
  compatibility for the `telemetry` field.
- Documented automation workflows in `AUTOMATION.md`, refreshed README/architecture/API guides, and expanded the
  incident-response playbook with the CLI workflow.

## 2025-02-18
- Replaced external FastAPI, Pydantic, and Uvicorn dependencies with in-repo lightweight facades so the headless API runs and tests execute without pip access.
- Hardened the API launcher with a threaded WSGI server, updated CLI messaging, and refreshed docs/Makefile guidance for the offline-friendly workflow.
- Added a trace-based coverage harness and coverage summary artifacts to guarantee ≥99% line coverage across the core, application, and API layers.
- Documented offline coverage and server usage in the README plus updated architecture/API references to highlight the FastAPI-compatible façade.

## 2025-10-20
- Documented architecture, API contracts, workflows, and dependency posture across new `/docs` guides with README cross-links.
- Modernised tooling targets and changelog/CONTRIBUTING/SECURITY guidance to reflect ExecPlan usage, Streamlit fetch UX, and dependency monitoring.
- Optimised the BEA adapter for vectorised parsing, deduplicated metadata merging, and more informative sidebar progress cues.
- Audited runtime/dev dependencies and recorded review cadence, updating `pyproject.toml` for Python 3.11 compatibility and DX improvements.
- Added Codex Steps 5-11 report artifacts and quality gate verification instructions.

## 2025-10-19
- Reorganised source tree into layered packages (`core`, `adapters`, `infrastructure`, `interfaces`) with compatibility shims.
- Added agent toolkit with dataclass schemas and documented interface.
- Fixed missing imports across cache, security, logging, adapters, and utilities.
- Updated tests and documentation to reflect new structure; all pytest suites pass.
- Added architecture and verification reports plus expanded README guidance.
