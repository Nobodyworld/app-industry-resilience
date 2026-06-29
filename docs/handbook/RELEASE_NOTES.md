# Release Notes

## 2026-06-29 - Public release alignment

### Highlights

- Standardized public-facing project title to `U.S. Industry Cost Structure and Resilience Dashboard` across the Streamlit app, README, metadata, and docs index.
- Replaced the prior proprietary license with standard Apache License 2.0 text and updated copyright attribution.
- Added/verified release assets: `docs/DATA_DICTIONARY.md` and `docs/INDUSTRY_SHOCK_CASE_STUDY.md`.

### Upgrade / Migration Notes

- Public materials and metadata now reference the professional title; downstream automation that scraped old headings should update title matching.
- License scanners should now detect Apache-2.0 from the root `LICENSE` file without custom policy exceptions.

# 2025-11-12 – Connector catalog & developer tooling

### Highlights

- Added a connector registry and catalog endpoint/CLI so data integrations expose metadata, capabilities, and health checks through `/meta/connectors`, observability digests, Streamlit configuration panels, and `make connectors-catalog`.
- Shipped built-in connector entries for the bundled sample dataset, BEA API, and Census ASM with health checks that flag missing credentials or offline resources.
- Extended developer tooling with `scripts/changelog_entry.py` for changelog automation and a connector-aware extension scaffold (`python scripts/scaffold_extension.py --with-connector`).

### Upgrade / Migration Notes

- No breaking changes. New connector health signals appear automatically once the process restarts. Run `make connectors-catalog` after deploying custom connectors to verify registration.
- Streamlit and the headless API now surface connector metadata; automation consuming `/observability/digest` will see a new `connectors` block alongside existing metrics/events.

# 2025-11-11 – Snapshot replication timeout enforcement

### Highlights

- GCS and Azure Blob replicators now honour the optional timeout configuration so uploads fail fast instead of hanging indefinitely.
- Invalid or non-positive timeout values are ignored with a warning, preventing misconfiguration from wedging replication workers.
- Documentation clarifies that the timeout knobs apply directly to upload calls, aligning operator expectations with runtime behaviour.

### Upgrade / Migration Notes

- Set `OBSERVABILITY_SNAPSHOT_GCS_TIMEOUT_SECONDS` or `OBSERVABILITY_SNAPSHOT_AZURE_TIMEOUT_SECONDS` to a positive number to enable upload timeouts; unset or invalid values are ignored safely.
- No other action is required—existing configurations continue to function, and defaults remain unchanged.

# 2025-11-10 – Multi-cloud snapshot replication & UI telemetry

### Highlights

- Introduced native Google Cloud Storage and Azure Blob Storage snapshot replicators alongside the existing S3 support, with configuration parsing/validation and stubbed unit tests for each backend.
- Streamlit’s observability panel now surfaces replication status badges and destinations, while the CLI reports `gs://` / `azure://` URIs in addition to `s3://` so operators immediately know where archives landed.
- Documentation (README, OBSERVABILITY_SNAPSHOTS, EXTENSION_GUIDE, AUTOMATION) has been expanded to cover backend-specific environment variables and automation flows.

### Upgrade / Migration Notes

- Existing S3 deployments continue to work without changes. To adopt GCS or Azure, set `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND=gcs` or `azure-blob` along with the corresponding bucket/container and credential variables documented above.
- The CLI’s replication summary now reports backend-specific URI schemes; automation that parsed the previous `s3://` prefix should treat the destination as an opaque string.

# 2025-11-10 – Replication plugins & telemetry uplift

### Highlights

- Added the `ReplicationExtension` contract and taught the extension manager to discover custom replication backends before falling back to built-ins.
- Emitted `observability.snapshot.replication` events from the persistence flow and introduced a `snapshot_replication` instrumentation extension that exposes replication counters, latency histograms, and a dedicated health component.
- Shipped built-in S3 and debug filesystem replication modules, CLI messaging for both backends, and plugin-aware configuration/tests (including the new `OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS` variable).

### Upgrade / Migration Notes

- No manual migration is required; existing S3 configurations continue to work. Optional debug mirroring is available via `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND=plugin:debug` and a JSON `OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS` payload (e.g., `{"path": "./build/debug-replication"}`).
- Observability dashboards and probes now expose `idiot_index_snapshot_replications_total`, `idiot_index_snapshot_replication_latency_seconds`, `idiot_index_snapshot_replication_age_seconds`, and a `snapshot_replication` health component.

# 2025-11-10 – Snapshot replication hardening

### Highlights

- Normalised snapshot metadata serialisation for the S3 replicator so nested dictionaries, sequences, and sets are emitted as
  deterministic JSON strings rather than Python reprs.
- Added a dedicated regression test that verifies the emitted metadata payload, covering IDs, timestamps, JSON-encoded nested
  values, boolean handling, and set ordering.

### Upgrade / Migration Notes

- No additional upgrade steps are required. Deployments already configured for remote replication inherit the fix automatically.

# 2025-11-09 – Snapshot remote replication

### Highlights

- Added an S3-compatible snapshot replicator (`SnapshotRemoteStorageConfig`, `build_snapshot_replicator`, `S3SnapshotReplicator`) so every persisted observability snapshot is streamed to object storage immediately after landing on disk.
- The observability CLI now reports remote destinations (and surfaces failures) when storing snapshots, and the `snapshot_persistence` extension invokes the same replicator on startup/shutdown/error triggers.
- New configuration knobs (`OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND`, `OBSERVABILITY_SNAPSHOT_S3_*`, `OBSERVABILITY_SNAPSHOT_REMOTE_MAX_RETRIES`) unlock remote shipping with full validation and documentation coverage.

### Upgrade / Migration Notes

- Install the new runtime dependency `botocore` and set `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND=s3` with the target bucket/prefix. Optional variables control endpoint overrides, credentials, TLS, and retry counts.
- CLI and automation workflows that previously watched for `Stored snapshot` messages now also receive `Replicated snapshot to s3://...` on success; failures log to stderr but do not block local persistence.
- Configuration summaries now include a `observability_snapshot_remote` entry; automation should treat secrets as boolean flags (`has_access_key`, etc.) rather than raw strings.

# 2025-11-08 – Snapshot persistence automation

### Highlights

- Added the `snapshot_persistence` instrumentation extension so observability snapshots are persisted automatically on startup, shutdown, and when instrumentation emits `warn`/`error` events, keeping history available for comparisons without manual CLI runs.
- Extended configuration with snapshot retention controls (`OBSERVABILITY_SNAPSHOT_RETENTION_COUNT`, `OBSERVABILITY_SNAPSHOT_RETENTION_DAYS`, `OBSERVABILITY_SNAPSHOT_MIN_INTERVAL_SECONDS`) and refreshed tests/docs to surface the new knobs across README, OBSERVABILITY_SNAPSHOTS, EXTENSION_GUIDE, AUTOMATION, and STATUS.

### Upgrade / Migration Notes

- Deployments should set retention variables to match storage expectations; defaults retain 20 snapshots for 30 days with a 10 minute minimum interval between auto-captures. Count/day thresholds can be disabled by setting them to `0`.
- Automation consuming `get_config_summary` should read snapshot metadata from the new `observability_snapshot` structure (with `dir`, `retention_count`, `retention_days`, `min_interval_seconds`).

# 2025-11-05 – Observability diagnostics & snapshot guardrails

### Highlights

- Added `/observability/events` and accompanying schemas/tests so operators and automation can fetch filtered, reverse-chronological telemetry without parsing the full digest payload.
- Introduced the `snapshot_monitor` instrumentation extension plus new `observability.snapshot.persisted` events to surface snapshot counts, latest-age gauges, and a dedicated health component that warns when archives go stale.
- Delivered `scripts/diagnostics_bundle.py` alongside documentation updates, enabling one-command capture of config summaries, health probe output, observability digests/events, and snapshot metadata.

### Upgrade / Migration Notes

- Dashboards and runbooks should incorporate `/observability/events` for quick incident timelines; the endpoint honours optional `status` and `limit` filters.
- Prometheus collectors can scrape the new `idiot_index_observability_snapshots_*` gauges; `/health` and `/observability/status` now include an `observability_snapshots` component that warns on missing or stale archives.
- Automation relying on snapshot history can consume `build/reports/diagnostics.json` produced by the new diagnostics bundle script for archival or ticket attachments.

## 2025-11-02 – Snapshot validation & operational hardening

### Highlights

- Hardened observability snapshot handling by validating identifiers in storage, the CLI, and API detail endpoint, closing the door on traversal attempts and returning explicit 400 errors for malformed IDs.
- Added a supported `SnapshotStorage.path_for` helper with regression tests so automation and tooling can resolve stored snapshot paths without bypassing validation.
- Expanded docs and API tests to document the stricter identifier rules while ensuring snapshot list/detail flows remain unchanged for valid IDs.

### Upgrade / Migration Notes

- Snapshot identifiers now must match `^[A-Za-z0-9_-]+$`. Existing stored IDs already conform, but any automation constructing IDs manually should treat them as opaque tokens and avoid path separators or dots.
- CLI users comparing snapshots by ID should continue to supply the bare identifier; external filesystem paths remain supported for explicit comparisons.

## 2025-10-31 – Observability recorders & audit resiliency

### Highlights

- Introduced `ObservabilityRegistry.record_event(...)` so application services and extensions can emit telemetry without empty `with registry.operation(...): pass` blocks, while still producing spans and event counters.
- Updated Idiot Index pipelines, instrumentation tests, and documentation to rely on the new helper for dataset/scenario profiling and extension guidance.
- Improved `scripts/audit_metrics.py` to fall back to `coverage.xml` whenever the trace JSON is absent, keeping steward audits resilient in environments that only run pytest coverage.

### Upgrade / Migration Notes

- No configuration changes are required. Existing subscriptions continue to receive `service.dataset.profile` and `service.scenario.profile` events.
- When running steward audits without the trace harness, ensure `coverage.xml` is present (generated by `pytest --cov`); the updated script now reads either artefact transparently.

## 2025-10-26 – Observability digest & extension catalog

### Highlights

- Added `/observability/digest`, the `scripts/observability_tail.py` streaming CLI, and the `scripts/extensions_catalog.py` inventory command so operators and agents can inspect telemetry and registered extensions without editing code.
- Instrumented Idiot Index services with dataset/scenario profile events and delivered the `data_quality` instrumentation extension, surfacing row-count/missing-ratio gauges and a focused health check.
- Refreshed README, automation docs, incident response guidance, and Make targets (`observability-tail`, `extensions-catalog`) to standardise diagnostics workflows.

### Upgrade / Migration Notes

- Expose `/observability/digest` alongside `/observability/status` in dashboards; the new payload includes event counters and subscriber counts.
- Incorporate `make observability-tail` into incident runbooks to capture live telemetry, and archive `extensions_catalog.py --json` output when auditing extensions.

## 2025-10-30 – Rate limiter hardening & deterministic tests

### Highlights

- Eliminated recursive blocking in the token bucket wait path and tightened rule validation so misconfigured rate limits fail
  fast instead of hanging threads.
- Redis-backed limiters now surface their active mode (`redis` vs `redis-fallback`) in health checks, metrics, and the Streamlit
  sidebar while preserving the configured backend identifier for auditing.
- Added Redis stubs to the test suite so distributed rate limiting coverage runs even when `fakeredis` is unavailable, and added
  assertions for fallback instrumentation.

### Upgrade / Migration Notes

- No configuration changes are required. Operators relying on dashboards should watch for the new `redis-fallback` mode in
  health summaries when Redis is unavailable.
- Custom automation consuming `/observability/status` or sidebar diagnostics can now distinguish configured vs active backends
  via the `backend` and `mode` fields respectively.

## 2025-10-29 – Distributed rate limiting & dtype overrides

### Highlights

- Redis-backed rate limiting is now available via `RATE_LIMIT_BACKEND=redis`, complete with Lua-driven token buckets, Prometheus counters/histograms, and a `rate_limiting` health check surfaced in `/observability/status` and the Streamlit sidebar.
- `SecurityUtils.rate_limit_check` delegates to a registered backend, ensuring the UI, API, and agents all share the same enforcement behaviour across processes.
- `NormalizationOptions` and the `NORMALIZE_DTYPE_OVERRIDES` environment variable let operators pin pandas dtypes without editing code; adapters and services respect overrides while skipping cache persistence to preserve dtype metadata.
- `safe_get_json` emits structured retry events that instrumentation extensions convert into metrics so flaky upstream APIs are easy to diagnose.

### Upgrade / Migration Notes

- Add `redis>=5` to deployment images when enabling distributed rate limiting; configure connection details via `RATE_LIMIT_REDIS_*` variables. Environments without Redis continue to operate in in-memory mode.
- Update infrastructure monitors to consume the new `rate_limit_requests_total`, `rate_limit_wait_seconds`, `http_retries_total`, and `http_retry_delay_seconds` metrics.
- When supplying `NORMALIZE_DTYPE_OVERRIDES`, use canonical column names (`materials_cost`, `industry_code`, etc.) and pandas dtype strings (e.g., `"Int64"`). Cached responses are bypassed automatically to avoid dtype drift.

## 2025-10-28 – Observability unification

### Highlights

- Added the process-wide `ObservabilityRegistry`, instrumented Idiot Index workflows, and shipped the `/observability/status` endpoint plus the `scripts/observability_snapshot.py` CLI for air-gapped inspections.
- Introduced the `core_instrumentation` extension so metrics/health hooks live outside core services and updated scaffolds to generate instrumentation-ready extensions and services.
- Refreshed documentation (architecture, automation, incident response, API guides) and automation tooling (Makefile `observability` target, Dependabot labels) to reinforce the continuous improvement loop.

### Upgrade / Migration Notes

- Deployments should expose `/observability/status` to operators alongside `/metrics`; the payload mirrors the CLI and requires no authentication changes.
- When adding metrics, implement them as instrumentation extensions via `python scripts/scaffold_extension.py --instrumentation` so they remain decoupled from core services.
- CI/CD pipelines can invoke `make observability` to capture a JSON snapshot for artefact storage or incident retrospectives.

## 2025-10-26 – Health analytics hardening

### Highlights

- Optimised `compute_health_scores` and `summarise_health` for large datasets by vectorising band classification, sanitising top risk calculations, and avoiding unnecessary sector aggregation work.
- Added resilience tests covering NaN handling, group-by parameters, and the analytics top-risk limiter to guard against regressions.
- Introduced `scripts/run_tests_with_trace.py` and wired it into the Makefile so coverage enforcement works even when `pytest-cov` is unavailable, producing JSON/text reports under `build/reports/`.

### Upgrade / Migration Notes

- `make coverage-runtime` and `make quality-gate` honour the `RUNTIME_COVERAGE_THRESHOLD` variable (default 85) for release-blocking checks, while full `src`/scripts coverage remains informational. Environments without `pytest-cov` should rely on the bundled trace script, which now runs automatically and focuses on the analytics service/API modules (override with `--paths` for broader coverage).
- Automation that previously called `scripts/run_pytest_trace.py` should switch to `scripts/run_tests_with_trace.py` (command-line usage mirrors the old script but now integrates directly with pytest).

## 2025-10-25 – Health analytics expansion

### Highlights

- Introduced composite health scoring via `src/core/analytics` and surfaced the insights across Streamlit (new Health tab, signal bar badge, Scenario Lab) and the headless API.
- Added the `/analytics/health` endpoint, enriched `/evaluate` and `/scenario` responses with health envelopes, and shipped the `scripts/analytics_health.py` CLI with a `make analytics` shortcut.
- Extended agent responses (`IdiotIndexResponse`) with health metadata and refreshed documentation (`README`, `ARCHITECTURE_OVERVIEW.md`, `API_REFERENCE.md`, `docs/ANALYTICS_HEALTH.md`).
- Relaxed dependency pins in `requirements*.txt` to track the latest compatible releases while capturing review cadence in `docs/DEPENDENCIES.md`.

### Upgrade / Migration Notes

- API consumers should tolerate the new `health` field in `/evaluate` responses and the `baseline_health`/`scenario_health` fields in `/scenario`. Existing keys remain unchanged.
- Automation pipelines can call `/analytics/health` for lightweight summaries or the new CLI; ensure JSON parsers expect the health envelope structure.
- Dependency managers should allow the widened version ranges when syncing environments.

## 2025-10-27

### Highlights

- Updated `STEWARDS_REPORT.md` with measured coverage, complexity, dependency, and latency metrics plus a refreshed roadmap.
- Delivered `scripts/audit_metrics.py`, the `make audit` target, and `AUTOMATION_ROLES.md` so agents can capture stewardship data
  and coordinate responsibilities.
- Simplified API telemetry span closure, tagged automation make targets as `# agent-safe-task`, and taught every helper script to
  bootstrap the repository path for direct execution.

### Upgrade / Migration Notes

- Local and CI environments can now invoke `make audit` to persist `build/reports/audit-metrics.json`; archive the JSON for
  release artifacts if stewardship metrics must be auditable.
- No API contract changes, but CLI scripts now expect to run from the repository root so ensure automation calls them via
  `python scripts/<name>.py` or the corresponding Make targets.

## 2025-10-25

### Highlights

- Introduced a reusable `HealthProbe` feeding richer `/health` payloads and the new `scripts/check_health.py` CLI for
  air-gapped readiness checks.
- `/health` and `/healthz` now expose component-level statuses, configuration snapshots, and telemetry counters while the
  legacy `telemetry` field remains for compatibility.
- Added `AUTOMATION.md` plus updates across README, architecture, API, and incident-response docs to document the
  automation workflow and health tooling.

### Upgrade / Migration Notes

- Clients consuming `/health` must accept the new `status` values (`pass`, `warn`, `fail`) and account for the additional
  `components` and `metadata` fields. The existing `telemetry` field is unchanged for backwards compatibility.
- Automation can now rely on `python scripts/check_health.py` exit codes (0/1/2) to gate deployments when the HTTP API is
  unavailable.

## 2025-02-18

### Highlights

- Headless API no longer depends on external FastAPI/Pydantic/Uvicorn wheels; lightweight facades provide the required behaviour for health, evaluation, and scenario endpoints.
- `scripts/run_api.py` now embeds a threaded WSGI server so the API can be launched locally or in Docker without third-party servers, while keeping the CLI interface stable.
- Added `scripts/run_tests_with_trace.py` and documentation for generating offline coverage via Python's built-in trace module. Coverage artefacts are written to `build/reports/`.
- Documentation refreshed to explain the FastAPI-compatible façade, offline coverage workflow, and the new API server semantics.

### Upgrade / Migration Notes

- Remove `fastapi`, `uvicorn`, and `pydantic` from any pinned dependency lists when rebasing; the repository now provides those modules internally.
- If production deployments rely on real FastAPI/Uvicorn features (e.g., ASGI middlewares), replace the stub modules with the genuine packages in that environment by updating `PYTHONPATH` before importing the repo's code.
- Use `python scripts/run_tests_with_trace.py --threshold 85` to reproduce runtime-gate-aligned coverage output on systems without `pytest-cov`.
- The API CLI ignores `--reload`/`--workers` flags (preserved for compatibility). Adjust automation to avoid relying on hot reload semantics.
