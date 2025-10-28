# Universal multi-cloud observability shipping & telemetry surfacing

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Maintain this ExecPlan per `.agent/PLANS.md`.

## Purpose / Big Picture

Operators can already persist observability snapshots locally and replicate them to S3-compatible storage, but multi-cloud teams (GCP, Azure) have to fork the codebase or build custom extensions before they gain parity. This plan delivers first-party Google Cloud Storage and Azure Blob Storage replication, surfaces replication health directly in the Streamlit UI, and rounds out automation/CLI messaging so engineers can confirm shipping status without digging into logs. By the end, observability artefacts replicate to any of the three major clouds with identical configuration ergonomics, documentation, and automated tests.

## Progress

- [x] (2025-10-27T22:22Z) Authored initial ExecPlan capturing scope, context, and implementation milestones.
- [ ] Implement configuration loader updates for new GCS/Azure knobs with validation and summaries.
- [ ] Add GCS and Azure Blob snapshot replicators with graceful degradation when SDKs are absent.
- [ ] Expose replication health in Streamlit snapshot history and adjust CLI messaging/tests.
- [ ] Expand unit/integration coverage and documentation (README, OBSERVABILITY_SNAPSHOTS, EXTENSION_GUIDE, STATUS, RELEASE_NOTES, CHANGELOG, STEWARDS_REPORT).
- [ ] Run `make quality-gate`, document outcomes, and finalise ExecPlan sections with decisions and retrospectives.

## Surprises & Discoveries

- None yet; populate as work uncovers unexpected behaviour or trade-offs.

## Decision Log

- Pending. Record concrete implementation choices (e.g., credential handling, retry semantics) as they are made.

## Outcomes & Retrospective

- Pending until implementation and validation complete; summarise feature readiness, remaining gaps, and follow-up ideas.

## Context and Orientation

Observability persistence lives under `src/infrastructure/observability/`. `storage.py` defines `ObservabilitySnapshot` and `SnapshotStorage`, while `replication.py` currently supports local-only and S3 replication via `SnapshotReplicator` implementations. Automatic persistence is wired through `src/extensions/builtins/snapshot_persistence.py`, invoked by both the Streamlit UI (`app.py` → `src/interfaces/streamlit/helpers.py`) and automation scripts (`scripts/observability_snapshot.py`). Configuration for remote replication originates in `src/core/config.py` (`SnapshotRemoteStorageConfig`) with validation in `validate_config` and coverage in `tests/test_config.py`. Observability UI helpers aggregate snapshot history in `src/interfaces/streamlit/helpers.py` with rendering in `components.py`. Tests for replication reside in `tests/test_observability_replication.py`, CLI coverage in `tests/test_scripts.py`, and UI helpers in `tests/test_ui_helpers.py`. Documentation of remote shipping spans `README.md`, `docs/OBSERVABILITY_SNAPSHOTS.md`, `EXTENSION_GUIDE.md`, `AUTOMATION.md`, `STATUS.md`, `CHANGELOG.md`, and `RELEASE_NOTES.md`.

## Plan of Work

First, extend `src/core/config.py` to recognise `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND` values `gcs` and `azure-blob`, parsing backend-specific environment variables (bucket/container names, credentials, optional prefixes) into `SnapshotRemoteStorageConfig.options`. Update `validate_config` to enforce required knobs and emit targeted warnings. Refresh `get_config_summary` if needed so secrets remain masked and option keys surface.

Next, implement `GCSnapshotReplicator` and `AzureBlobSnapshotReplicator` within `src/infrastructure/observability/replication.py`, following the existing pattern of optional SDK imports with graceful fallbacks. Introduce helper constructors `create_gcs_snapshot_replicator` and `create_azure_snapshot_replicator`, wire them into `build_snapshot_replicator`, and ensure metadata serialisation (content type, custom metadata) mirrors S3 behaviour. Add a shared URI scheme attribute so downstream tooling can report destinations generically.

Then, enrich observability summarisation: enhance `summarise_observability_snapshot` in `src/interfaces/streamlit/helpers.py` to extract the most recent `observability.snapshot.replication` event, capturing backend, status, and error metadata. Update `render_observability_snapshots` in `src/interfaces/streamlit/components.py` to display replication health badges/messages and extend snapshot tables. Adjust `scripts/observability_snapshot.py` to report non-S3 destinations based on the replicator’s URI scheme. Ensure compatibility with existing extensions.

After code changes, expand the automated suite: add configuration tests for the new backends (`tests/test_config.py`), replication tests using stub SDKs (`tests/test_observability_replication.py`), UI helper assertions for replication metadata (`tests/test_ui_helpers.py`), and CLI messaging coverage (`tests/test_scripts.py`). Where necessary, inject lightweight stubs for missing SDKs to keep tests self-contained.

Finally, refresh documentation artefacts (README, docs/OBSERVABILITY_SNAPSHOTS.md, EXTENSION_GUIDE.md, AUTOMATION.md, STATUS.md, RELEASE_NOTES.md, CHANGELOG.md, STEWARDS_REPORT.md) to describe the multi-cloud capabilities, configuration environment variables, and operator workflows. Close out by running `make quality-gate`, updating this plan’s Progress/Decisions/Outcomes, and preparing the PR summary.

## Concrete Steps

1. Edit `src/core/config.py` and related tests to parse/validate GCS and Azure backend settings; ensure summaries hide secrets.
2. Implement GCS/Azure replicators and builders in `src/infrastructure/observability/replication.py`, updating exports and tests.
3. Enhance Streamlit helpers/components and the observability CLI for replication status reporting with accompanying tests.
4. Update documentation sets (README, docs/OBSERVABILITY_SNAPSHOTS.md, EXTENSION_GUIDE.md, AUTOMATION.md, STATUS.md, RELEASE_NOTES.md, CHANGELOG.md, STEWARDS_REPORT.md) to reflect new capabilities.
5. Execute `make quality-gate` from the repository root and capture relevant output snippets for this ExecPlan and PR summary.

## Validation and Acceptance

- Run `make quality-gate` and ensure all linting, typing, tests, and security checks pass.
- Manually run `python scripts/observability_snapshot.py --store --pretty` with `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND` toggled between `gcs`, `azure-blob`, and `s3` (with stubbed env values) to observe CLI messaging; document behaviour in this plan if notable.
- Launch `streamlit run app.py` (optional smoke) to confirm the snapshot panel renders replication status without errors; capture findings in Surprises/Outcomes if deviations appear.

## Idempotence and Recovery

Configuration parsing remains additive: new environment variables default to safe values, and absence of SDKs gracefully falls back to local persistence. Replicator constructors must never raise when dependencies/options are missing—return `NullSnapshotReplicator` and log a warning instead. CLI/UI changes should handle missing replication metadata without errors. If regressions surface, re-run tests after toggling the backend to `off` and confirm behaviour reverts to pre-change state.

## Artifacts and Notes

- Capture `make quality-gate` summary output once complete.
- Record notable manual validation transcripts (CLI runs, UI observations) here once executed.

## Interfaces and Dependencies

- `src/core.config.load_config` → ensure signatures unchanged; only extend parsing logic.
- `src/infrastructure.observability.replication.SnapshotReplicator` → maintain protocol while adding optional classes `GCSnapshotReplicator` and `AzureBlobSnapshotReplicator` exposed via `__all__`.
- `scripts/observability_snapshot._report_remote_destination` → rely on replicator attributes `uri_scheme`, `bucket`/`container`, and `prefix` for messaging.
- Streamlit helpers/components must continue returning serialisable structures; new fields should be backward-compatible for downstream callers (API, agents) relying on helper outputs.
