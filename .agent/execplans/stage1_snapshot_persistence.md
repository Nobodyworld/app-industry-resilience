# Stage 1 – Observability snapshot persistence and surfacing

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

Operators currently have to query `/observability/status` or run the snapshot CLI manually to inspect live metrics. There is no durable history for audits, no API to fetch previous states, and the Streamlit UI cannot surface instrumentation trends. After this change, the registry can persist timestamped snapshots, the API exposes them over HTTP, the CLI can archive and diff them, and the Streamlit dashboard visualises recent snapshots. The new storage path is configurable so multi-instance deployments can share a volume. Users will be able to run `make observability-snapshot`, download the stored JSON via the API, and read a lightweight timeline inside the dashboard without breaking existing observability features.

## Progress

- [x] (2025-10-31 11:15Z) Drafted Stage 1 snapshot persistence ExecPlan after surveying observability modules and docs.
- [x] (2025-10-31 12:05Z) Implemented snapshot dataclasses/storage helpers and registry capture method with tests.
- [x] (2025-10-31 12:50Z) Extended configuration, CLI, and Makefile to persist/list/diff snapshots with tests.
- [x] (2025-10-31 13:25Z) Added API schemas/routes/tests for snapshot listing & retrieval.
- [x] (2025-10-31 13:45Z) Streamlit UI exposes observability snapshot history and metrics.
- [x] (2025-10-31 14:10Z) Updated README, architecture, API, operations docs, and added snapshot guide.
- [x] (2025-10-31 14:55Z) Run quality gate, update reports, finalise plan sections, commit, and prepare PR message.

## Surprises & Discoveries

- Observation: Observability metric summaries embed non-numeric `subscriptions` dictionaries, so CLI diffs now filter numeric keys before computing deltas.
  Evidence: `scripts/observability_snapshot.py`'s `_extract_metric_counts` filters values to avoid `TypeError` when diffing snapshots.
- Discovery: The in-repo FastAPI shim did not support path parameters, causing `/observability/snapshots/{snapshot_id}` to 404 until the router gained pattern matching.
  Evidence: Added `_match_path` helper in `fastapi/__init__.py` with tests showing detail endpoint succeeds once path params resolve.

## Decision Log

- Decision: Preserve JSON snapshot payloads on STDOUT for backward compatibility while emitting storage paths/messages on STDERR.
  Rationale: Existing automation and tests parse JSON output directly; keeping stdout stable avoids breaking downstream tooling while still surfacing file locations to operators.
  Date/Author: 2025-10-31 / gpt-5-codex
- Decision: Extend the FastAPI shim to decode path parameters instead of adding bespoke routing in the endpoint module.
  Rationale: Centralising path parsing ensures future endpoints can rely on idiomatic FastAPI patterns without duplicating logic.
  Date/Author: 2025-10-31 / gpt-5-codex

## Outcomes & Retrospective

- Outcome: Quality gate now passes end-to-end (format, lint, type-check, tests, trace coverage) validating the new observability snapshot surfaces and infrastructure.
- Retrospective: The need to enhance the FastAPI shim highlighted hidden coupling with framework expectations; future work should schedule upstream documentation or tooling to flag unsupported features earlier.

## Context and Orientation

The observability layer lives in `src/infrastructure/observability`. `instrumentation.py` houses `ObservabilityRegistry` with `digest()` and `health_overview()` helpers. `scripts/observability_snapshot.py` prints the digest, while `scripts/observability_tail.py` streams events. API endpoints for observability exist in `src/interfaces/api/app.py` and `src/interfaces/api/routes/observability.py` (if separated) with schemas defined in `src/interfaces/api/schemas.py`. The Streamlit UI in `app.py` uses helpers under `src/interfaces/streamlit/` to render metrics tabs. Configuration is loaded via `src/core/config.py`; `AppConfig` presently lacks a path for observability storage. Tests covering observability features are located in `tests/test_observability.py`, `tests/test_api.py`, and CLI behaviour in `tests/test_scripts.py`. Documentation describing observability flows appears in `README.md`, `docs/API_HEADLESS.md`, `docs/ARCHITECTURE_OVERVIEW.md`, and `docs/OPERATIONS_INCIDENT_RESPONSE.md`.

## Plan of Work

Introduce a reusable snapshot storage facility that `ObservabilityRegistry` can feed, then propagate support through the CLI, API, UI, and docs.

1. **Snapshot data model and capture hooks.** Add `ObservabilitySnapshot` and `SnapshotStorage` classes under a new module `src/infrastructure/observability/storage.py`. Extend `ObservabilityRegistry` with `capture_snapshot()` (returning `ObservabilitySnapshot`) and `persist_snapshot(storage, metadata)` convenience wrappers. Ensure persisted payloads include digest plus metadata (timestamp, optional labels). Add tests validating serialization, listing, and cleanup helpers. Update `__all__` exports.
2. **Configuration and automation.** Extend `AppConfig` with `observability_snapshot_dir: Path` derived from new env var `OBSERVABILITY_SNAPSHOT_DIR` (default `build/observability_snapshots`). Update `load_config`, validation, and `to_dict` exporter. Add Makefile target `observability-snapshot` invoking `python scripts/observability_snapshot.py --store`. Ensure directory creation is safe and documented.
3. **CLI enhancements.** Update `scripts/observability_snapshot.py` to accept options: `--store` (persist using config path, printing location), `--output <path>` for explicit file, `--list` to enumerate stored snapshots, and `--compare <path>` to diff with latest stored snapshot (basic structural diff summarizing keys changed). Factor out logic into helper functions for testability. Add tests in `tests/test_scripts.py` covering store/list and diff operations with temporary directories.
4. **API surface.** Create schemas in `src/interfaces/api/schemas.py` for `ObservabilitySnapshotMeta` and `ObservabilitySnapshotResponse`. Add routes under `src/interfaces/api/app.py` (or submodule) for `GET /observability/snapshots` (list metadata) and `GET /observability/snapshots/{snapshot_id}` (return stored snapshot). Wire dependencies to use storage configured via `AppConfig`. Add tests in `tests/test_api.py` verifying responses with temporary storage seeded during test setup. Ensure telemetry instrumentation wraps the new routes.
5. **Streamlit dashboard.** Introduce helper in `src/interfaces/streamlit/helpers.py` to load recent snapshots and compute quick stats (e.g., span counts, error totals). Update `src/interfaces/streamlit/components.py` to render a collapsible section or new tab showing snapshot timeline (timestamp, event totals, last error). Wire into `app.py` sidebar or analytics page so UI surfaces stored observability history. Add UI helper tests verifying transformation logic.
6. **Documentation and developer workflow.** Update README and `docs/ARCHITECTURE_OVERVIEW.md` to mention persistent snapshots, automation command, and configuration. Extend `docs/API_HEADLESS.md` with endpoint descriptions, and `docs/OPERATIONS_INCIDENT_RESPONSE.md` with procedures for archiving and diffing snapshots. Create or update a doc under `docs/` if deeper explanation needed (e.g., `docs/OBSERVABILITY_SNAPSHOTS.md`). Mention new env var in `docs/DEPENDENCIES.md` or appropriate location. Update any reports if required.
7. **Validation.** Add tests for storage module, CLI, API, and UI helpers. Run `make quality-gate`. Capture relevant command output for reports (if Stage 1 doc expects). Update ExecPlan sections (progress, decisions, surprises) with findings.

## Concrete Steps

1. Inspect existing observability modules and tests to confirm integration points.
2. Implement storage module and registry hooks; update `__init__.py` exports; create unit tests under `tests/test_observability.py` or new `tests/test_observability_storage.py`.
3. Extend configuration (`src/core/config.py`), ensure `AppConfig` includes snapshot path, adjust tests in `tests/test_config.py`.
4. Update Makefile with `observability-snapshot` target invoking CLI with `--store` and `--pretty` for readability. Document in README.
5. Enhance CLI script with new arguments, file writing, listing, and optional diff. Write tests using temp directories.
6. Implement API endpoints and schemas; add tests in `tests/test_api.py` using FastAPI test client. Ensure storage is injectable/mocked for tests.
7. Modify Streamlit helpers/components/app to surface snapshot summaries. Add tests covering new helper functions.
8. Update docs (README, architecture, API headless, operations). Create dedicated doc if necessary.
9. Run `make format`, targeted linters if needed, then full `make quality-gate`. Capture output for docs/reports as needed.
10. Finalise ExecPlan sections with discoveries, decisions, and retrospective. Stage/commit files. Call `make_pr` with summary referencing observability snapshot persistence.

## Validation and Acceptance

- `make quality-gate` passes without regressions.
- New tests for storage, CLI, API, and UI helpers succeed.
- Running `python scripts/observability_snapshot.py --store` creates a JSON file under the configured directory and prints the path.
- API `GET /observability/snapshots` returns at least one stored snapshot metadata entry when storage contains data; retrieving a specific ID returns the JSON payload.
- Streamlit dashboard shows a “Observability Snapshots” section with timestamped summaries, verified via headless run or helper tests.
- Documentation clearly explains configuration, CLI usage, API endpoints, and UI elements.

## Idempotence and Recovery

Snapshot storage writes new files per timestamp to avoid overwriting; CLI uses atomic writes. Make target and CLI handle missing directories by creating them. If storage path is not writable, CLI/API should raise descriptive errors and documentation should mention required permissions. Rolling back the feature involves deleting new files/modules and removing new config entries; no destructive migrations are introduced.

## Artifacts and Notes

Expected artifacts include:

- `src/infrastructure/observability/storage.py` with snapshot dataclass and file-based storage implementation.
- Updated `ObservabilityRegistry` with capture/persist helpers.
- Enhanced CLI script and Makefile target.
- New API schemas/routes and Streamlit UI updates.
- Tests for storage, CLI, API, and helpers.
- Documentation updates describing snapshot persistence.

## Interfaces and Dependencies

- Storage class signature:

      @dataclass(frozen=True)
      class ObservabilitySnapshot:
          snapshot_id: str
          captured_at: datetime
          payload: Mapping[str, Any]
          metadata: Mapping[str, Any]

      class SnapshotStorage:
          def __init__(self, base_dir: Path) -> None: ...
          def save(self, snapshot: ObservabilitySnapshot) -> Path: ...
          def list(self) -> list[ObservabilitySnapshot]: ...
          def get(self, snapshot_id: str) -> ObservabilitySnapshot: ...
          def latest(self) -> ObservabilitySnapshot | None: ...

- Extend `ObservabilityRegistry`:

      def capture_snapshot(self, *, metadata: Mapping[str, Any] | None = None) -> ObservabilitySnapshot: ...
      def persist_snapshot(self, storage: SnapshotStorage, *, metadata: Mapping[str, Any] | None = None) -> ObservabilitySnapshot: ...

- API schemas under `src/interfaces/api/schemas.py`:

      class ObservabilitySnapshotMeta(BaseModel):
          snapshot_id: str
          captured_at: datetime

      class ObservabilitySnapshotResponse(BaseModel):
          snapshot_id: str
          captured_at: datetime
          payload: dict[str, Any]
          metadata: dict[str, Any]

- CLI should access config via `load_config()` to resolve storage path and call `SnapshotStorage` for operations.
- Streamlit helpers operate on stored `ObservabilitySnapshot` objects and convert them into display rows (timestamp, total events, error counts, last error summary).

