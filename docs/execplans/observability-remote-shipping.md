# Observability Snapshot Remote Shipping

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Reference: `.agent/PLANS.md` governs all ExecPlans in this repository; this document complies with those rules and remains self-contained for future contributors.

## Purpose / Big Picture

Operators want observability snapshots not only on the local disk but also in a durable remote store so post-incident forensics survive node loss and automation can inspect history from any region. Today snapshots stay on the filesystem. After this change, enabling an S3-compatible backend (AWS S3, MinIO, etc.) will replicate every persisted snapshot automatically (extension and CLI) with retries and structured logging. Validation comes from integration tests using `botocore` stubs and updated documentation so an operator can configure the feature from environment variables.

## Progress

- [x] (2025-11-09T10:00Z) Captured current architecture, configuration surfaces, and observability workflow.
- [x] (2025-11-09T11:05Z) Parsed remote snapshot configuration into a strongly-typed dataclass with validation, summaries, and tests.
- [x] (2025-11-09T11:25Z) Implemented snapshot replication primitives (noop + S3) with botocore-based clients and unit tests using `Stubber`.
- [x] (2025-11-09T12:05Z) Updated the `snapshot_persistence` extension and observability CLI to invoke/close replicators with scripted tests covering delegation, success, and failure paths.
- [x] (2025-11-09T12:45Z) Refreshed docs (README, OBSERVABILITY_SNAPSHOTS, EXTENSION_GUIDE, AUTOMATION, RELEASE_NOTES, CHANGELOG, STATUS, STEWARDS_REPORT, ARCHITECTURE_OVERVIEW) for the remote backend configuration.
- [x] (2025-11-09T13:10Z) Ran `make quality-gate` (lint/type/test/security) and archived results for the retrospective.

## Surprises & Discoveries

- Observation: `botocore.session.get_session().create_client` requires concrete clients even when stubbed; wrapping the client with a lightweight session shim allowed the replicator factory to remain production-like while `Stubber` intercepted network calls.
  Evidence: `tests/test_observability_replication.py` uses `_DummySession` with `Stubber` to assert uploads without touching AWS. 【F:tests/test_observability_replication.py†L1-L144】

- Observation: Streamlit CLI tests needed explicit monkeypatching of `build_snapshot_replicator` to avoid touching S3; stubbing replicators surfaced the new stderr messages for success/failure paths.
  Evidence: `tests/test_scripts.py` remote replication tests patch the builder and assert stderr content. 【F:tests/test_scripts.py†L205-L256】

## Decision Log

- Decision: Prefer `botocore` over `boto3` to minimise dependency weight while still exposing the low-level S3 client API required for replication.
  Rationale: `botocore` ships the necessary client/session primitives without the heavier paginator/resource layers we do not use.
  Date/Author: 2025-11-09 / Steward Agent

- Decision: Surface replication success/failure via CLI stderr rather than raising, keeping the command idempotent and ensuring local persistence never fails when remote credentials are misconfigured.
  Rationale: Operators need digest output even if remote upload fails; logging to stderr preserves behaviour and supports automation parsing.
  Date/Author: 2025-11-09 / Steward Agent

## Outcomes & Retrospective

- Delivered end-to-end remote snapshot shipping with configuration, runtime primitives, CLI/extension integration, and documentation, allowing operators to opt into durable archives without custom scripts. Tests cover config parsing, replicator uploads/failures, extension delegation, and CLI messaging. Remaining work includes running the full quality gate and planning follow-up encryption/lifecycle knobs before GA.

## Context and Orientation

The observability subsystem lives under `src/infrastructure/observability/`. `instrumentation.py` exposes `ObservabilityRegistry.persist_snapshot` which saves snapshots via `SnapshotStorage` defined in `storage.py`. Automatic persistence comes from `src/extensions/builtins/snapshot_persistence.py`, registered through `extensions/manifest.json`. CLI workflows run through `scripts/observability_snapshot.py`. Configuration is loaded in `src/core/config.py` into `AppConfig`, surfaced in docs (`README.md`, `docs/OBSERVABILITY_SNAPSHOTS.md`) and automation guides. Tests for configuration (`tests/test_config.py`), observability (`tests/test_observability.py`), and extensions (`tests/test_extensions.py`) ensure behaviour.

Remote replication requires a new configuration surface (environment variables), dataclass plumbing, and a replicator component invoked after every `save()`. For S3 compatibility we will use the lightweight `botocore` library (already accepted in many Python projects) to create an S3 client without the heavier `boto3` dependency. Tests can stub the S3 client with `botocore.stub.Stubber` to avoid network calls.

## Plan of Work

1. Extend configuration:
   - Add `SnapshotRemoteStorageConfig` dataclass with fields for backend (`"s3"`), bucket, prefix, region, endpoint, credentials, SSL/path-style flags, and retry count.
   - Parse environment variables `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND`, `OBSERVABILITY_SNAPSHOT_S3_BUCKET`, `OBSERVABILITY_SNAPSHOT_S3_PREFIX`, `OBSERVABILITY_SNAPSHOT_S3_REGION`, `OBSERVABILITY_SNAPSHOT_S3_ENDPOINT`, `OBSERVABILITY_SNAPSHOT_S3_ACCESS_KEY`, `OBSERVABILITY_SNAPSHOT_S3_SECRET_KEY`, `OBSERVABILITY_SNAPSHOT_S3_SESSION_TOKEN`, `OBSERVABILITY_SNAPSHOT_S3_USE_SSL`, `OBSERVABILITY_SNAPSHOT_S3_FORCE_PATH_STYLE`, `OBSERVABILITY_SNAPSHOT_REMOTE_MAX_RETRIES`. Integrate into `AppConfig` (attribute `observability_snapshot_remote` defaulting to `None`).
   - Update `validate_config` to enforce bucket/prefix constraints, positive retry counts, and warn when credentials absent for custom endpoints. Adjust `get_config_summary` to surface non-sensitive remote settings.
   - Add tests in `tests/test_config.py` verifying parsing, validation errors, and summary redaction.

2. Implement replication primitives in a new module `src/infrastructure/observability/replication.py`:
   - Define `SnapshotReplicator` protocol/base with `replicate(snapshot, path)` and `close()` for resource cleanup (noop default).
   - Implement `NullSnapshotReplicator` (no-op) and `S3SnapshotReplicator` using `botocore.session.get_session().create_client("s3", ...)` with configurable retries (using `botocore.config.Config`), optional endpoint, path-style addressing, and SSL toggle. Encode metadata keys safely (lowercase, hyphen) and ensure values converted to strings capped to S3 limits.
   - Provide `build_snapshot_replicator(remote_config: SnapshotRemoteStorageConfig | None)` to return replicator + context manager; when botocore missing or backend disabled, return null replicator and log.
   - Add unit tests `tests/test_observability_replication.py` verifying key formatting, stubbed uploads (using `Stubber`), retry/backoff invocation (simulate failure then success), and no-op behaviour.

3. Integrate replicator with persistence flows:
   - Update `snapshot_persistence` extension to instantiate replicator during `register()` (store on self). After `registry.persist_snapshot(...)`, compute file path (`storage.path_for(snapshot.snapshot_id)`), call replicator, and handle exceptions with logging but no crash. Ensure replicator cleaned up via `atexit` (call `close()` and guard idempotency).
   - Modify CLI `scripts/observability_snapshot.py` to build replicator from config; when `--store` set, after saving call replicator (and optionally print remote location message). Provide flag `--no-ship`? maybe not; rely on config. Provide log to stderr.
   - Update observability registry tests to check replicator events via patched stub replicator.
   - Extend extension tests to assert replicator invoked once per persistence and errors captured.

4. Documentation & release updates:
   - README quickstart: mention remote snapshot shipping env variables.
   - `docs/OBSERVABILITY_SNAPSHOTS.md`: add section describing S3 backend, configuration steps, CLI interactions, verification tips.
   - `EXTENSION_GUIDE.md` instrumentation extension section referencing replicator.
   - `docs/handbook/AUTOMATION.md`: update guidance for agents/operators.
   - `CHANGELOG.md`, `docs/handbook/RELEASE_NOTES.md`, `docs/handbook/STATUS.md`, `docs/handbook/STEWARDS_REPORT.md` (observability metrics/risks), `docs/handbook/ARCHITECTURE_OVERVIEW.md` if necessary, and `docs/handbook/AUTOMATION_ROLES.md`/`REPORTS` if they reference snapshot operations.
   - Provide sample `.env` snippet maybe? ensure `Makefile` unaffected but mention new env in docs.

5. Tooling & validation:
   - Add `botocore` dependency to `requirements.txt` and `requirements-dev.txt` (matching version spec). Possibly adjust packaging docs to mention optional install.
   - Run `make quality-gate`. Capture output for retrospective.
   - Update ExecPlan sections: mark completed steps, add decisions (e.g., using botocore, metadata formatting), record surprises, and summarise outcomes.

## Concrete Steps

- Edit `src/core/config.py`, `src/core/__init__.py`, and relevant modules to include new config dataclass and parsing/validation. Update tests.
- Add new module `src/infrastructure/observability/replication.py` and export replicator helpers in `src/infrastructure/observability/__init__.py` if needed.
- Modify `src/extensions/builtins/snapshot_persistence.py` and `scripts/observability_snapshot.py` to use replicator.
- Write tests `tests/test_observability_replication.py`, extend existing extension/config tests, and update fixtures if necessary.
- Update docs, changelog, release notes, automation guides, status, steward report.
- Add dependency to requirement files.
- Run `make quality-gate`.

## Validation and Acceptance

- Run `make quality-gate` from repository root; all lint, mypy, pytest (including new replication tests) must pass.
- Unit tests should include cases where replicator stubs confirm S3 `put_object` invoked, failure logs without raising, and CLI uses replicator when storing.
- Manual dry-run: configure environment variables via test script (monkeypatch) ensuring replicator builds and receives metadata. CLI `python scripts/observability_snapshot.py --store --pretty` should show remote shipping message (via tests capturing stderr).
- Documentation updates should clearly state new env vars and remote workflow; release notes describe migration steps (set env + install botocore dependency).

## Idempotence and Recovery

- Configuration parsing remains pure; enabling/disabling remote backend toggled through envs with safe defaults. Failing uploads log warnings but do not break persistence; retention still applies locally.
- Replicator `close()` ensures network resources cleaned; errors during replication do not leave partial state because S3 upload atomic per object.
- CLI `--store` remains idempotent; repeated uploads with same snapshot_id simply overwrite same key (documented). Provide prefix to avoid collisions.

## Artifacts and Notes

- Include key code excerpts (replicator class, config snippet) in final retrospective.
- Capture `make quality-gate` output chunk ID for citation.

## Interfaces and Dependencies

- New dataclass `SnapshotRemoteStorageConfig` lives in `src/core/config.py` with fields described above.
- New module `src/infrastructure/observability/replication.py` defines:

    class SnapshotReplicator(Protocol):
        def replicate(self, snapshot: ObservabilitySnapshot, path: Path) -> None: ...
        def close(self) -> None: ...

    @dataclass
    class S3SnapshotReplicator(SnapshotReplicator):
        bucket: str
        prefix: str
        client: BaseClient
        max_retries: int
        ...

    def build_snapshot_replicator(config: SnapshotRemoteStorageConfig | None) -> SnapshotReplicator:
        ...

- `snapshot_persistence` obtains replicator via `build_snapshot_replicator` and stores it on `self._replicator`.
- CLI imports `build_snapshot_replicator` to replicate when storing snapshots manually.

