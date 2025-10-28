# Observability Snapshots

The observability registry now supports durable snapshots so operators can archive metrics, traces, and health summaries over time without scraping live services.

## Capturing snapshots

- Run `make observability-snapshot` to persist the current digest to the configured storage directory (`build/observability_snapshots` by default).
- Use the CLI directly for advanced flows:
  - `python scripts/observability_snapshot.py --store --label nightly` – capture and label the snapshot while still printing the digest to STDOUT.
  - `python scripts/observability_snapshot.py --list --pretty` – view stored snapshot metadata (IDs, timestamps, labels).
  - `python scripts/observability_snapshot.py --compare <snapshot.json>` – diff the latest stored snapshot against a previously captured file to see event/metric deltas.
- Storage can be relocated via the `OBSERVABILITY_SNAPSHOT_DIR` environment variable when running in multi-node or shared-volume deployments.
- When the built-in `snapshot_persistence` instrumentation extension is enabled (loaded by default via `extensions/manifest.json`), snapshots are captured automatically on process startup, graceful shutdown, and whenever instrumentation emits `warn`/`error` events. This keeps history alive even if operators forget to run the CLI after an incident.

Configure the retention policy with the following environment variables:

- `OBSERVABILITY_SNAPSHOT_RETENTION_COUNT` – maximum number of snapshots to keep (`0` disables count-based pruning).
- `OBSERVABILITY_SNAPSHOT_RETENTION_DAYS` – prune snapshots older than this many days (`0` disables age-based pruning).
- `OBSERVABILITY_SNAPSHOT_MIN_INTERVAL_SECONDS` – throttle automatic persistence so repeated failures do not overwhelm disk space.

## Remote replication (built-in backends)

Set `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND` to stream every persisted snapshot to object storage immediately after it lands on disk. The Idiot Index app ships with first-class support for S3-compatible APIs, Google Cloud Storage, and Azure Blob Storage.

### S3-compatible

| Variable | Purpose |
| --- | --- |
| `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND` | Set to `s3` to enable replication (use `off`/`none` to disable). |
| `OBSERVABILITY_SNAPSHOT_S3_BUCKET` | Destination bucket name (required when backend is enabled). |
| `OBSERVABILITY_SNAPSHOT_S3_PREFIX` | Optional key prefix (e.g., `nightly/`); omit trailing slash. |
| `OBSERVABILITY_SNAPSHOT_S3_REGION` | AWS region/MinIO region (optional). |
| `OBSERVABILITY_SNAPSHOT_S3_ENDPOINT` | Custom endpoint URL for non-AWS providers. |
| `OBSERVABILITY_SNAPSHOT_S3_ACCESS_KEY` / `OBSERVABILITY_SNAPSHOT_S3_SECRET_KEY` | Credentials for environments without IAM roles (optional). |
| `OBSERVABILITY_SNAPSHOT_S3_SESSION_TOKEN` | Session token for temporary credentials. |
| `OBSERVABILITY_SNAPSHOT_S3_USE_SSL` | Set to `false`/`0` to disable TLS (defaults to `true`). |
| `OBSERVABILITY_SNAPSHOT_S3_FORCE_PATH_STYLE` | Set to `true` for path-style addressing (MinIO compatibility). |
| `OBSERVABILITY_SNAPSHOT_REMOTE_MAX_RETRIES` | Number of attempts (including the first) before giving up (defaults to `3`). |
| `OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS` | JSON object forwarded to replication extensions for backend-specific configuration. |

### Google Cloud Storage (GCS)

| Variable | Purpose |
| --- | --- |
| `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND` | Set to `gcs` to enable GCS replication. |
| `OBSERVABILITY_SNAPSHOT_GCS_BUCKET` | Destination bucket name (required). |
| `OBSERVABILITY_SNAPSHOT_GCS_PREFIX` | Optional object prefix (e.g., `cloud/`). |
| `OBSERVABILITY_SNAPSHOT_GCS_PROJECT` | Override the active project (defaults to Google SDK behaviour). |
| `OBSERVABILITY_SNAPSHOT_GCS_CREDENTIALS_FILE` | Path to a service-account JSON file (optional). |
| `OBSERVABILITY_SNAPSHOT_GCS_CREDENTIALS_JSON` | Raw service-account JSON string (optional alternative to the file). |
| `OBSERVABILITY_SNAPSHOT_GCS_TIMEOUT_SECONDS` | Optional timeout (seconds) applied to upload requests. |
| `OBSERVABILITY_SNAPSHOT_REMOTE_MAX_RETRIES` | Number of attempts before surfacing an error. |

### Azure Blob Storage

| Variable | Purpose |
| --- | --- |
| `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND` | Set to `azure-blob` to enable Azure replication. |
| `OBSERVABILITY_SNAPSHOT_AZURE_CONTAINER` | Target container name (required). |
| `OBSERVABILITY_SNAPSHOT_AZURE_PREFIX` | Optional virtual directory prefix (e.g., `nightly/`). |
| `OBSERVABILITY_SNAPSHOT_AZURE_CONNECTION_STRING` | Standard storage connection string (recommended). |
| `OBSERVABILITY_SNAPSHOT_AZURE_ACCOUNT_URL` | Account URL for SAS/managed identity authentication. |
| `OBSERVABILITY_SNAPSHOT_AZURE_CREDENTIAL` / `OBSERVABILITY_SNAPSHOT_AZURE_SAS_TOKEN` | Credential or SAS token used with `ACCOUNT_URL`. |
| `OBSERVABILITY_SNAPSHOT_AZURE_TIMEOUT_SECONDS` | Optional timeout (seconds) applied to blob uploads. |
| `OBSERVABILITY_SNAPSHOT_REMOTE_MAX_RETRIES` | Number of attempts before surfacing an error. |
| `OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS` | JSON payload forwarded to extensions/custom backends. |

Replication runs both from the automatic extension (`snapshot_persistence`) and the CLI (`python scripts/observability_snapshot.py --store`). The CLI prints a confirmation such as `Replicated snapshot to gs://bucket/nightly/<id>.json` or `azure://container/nightly/<id>.json`; failures produce a warning while keeping the local file. The replicator closes connections on shutdown so long-running Streamlit sessions do not leak sockets.

Extensions can supply additional backends: the built-in `plugin:debug` target mirrors each archive into the directory provided via `OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS` (defaults to `build/observability_snapshots/debug-replication`). Custom extensions can inspect the same options payload to connect to alternative transports without modifying core infrastructure code.

## Programmatic access

The API exposes snapshot history under `/observability/snapshots` (metadata) and `/observability/snapshots/{snapshot_id}` (full payload). Responses mirror the structure of `/observability/digest`, making it easy to diff or replay past states in automation scripts.

Snapshot identifiers are now validated server-side to block path traversal attacks. Identifiers must match `^[A-Za-z0-9_-]+$`; attempts to request `../foo` or other filesystem paths return `400 Bad Request` with a descriptive message. Automation that stores snapshot IDs should treat them as opaque tokens and avoid introducing separators.

The observability API also exposes `/observability/events`, which returns the most recent operation events (newest first) with optional status filters. Combine snapshot metadata with filtered events to reconstruct pre-/post-incident telemetry timelines.

## Health & metrics

The `snapshot_monitor` instrumentation extension keeps runtime health checks in sync with persisted history, while `snapshot_persistence` ensures new captures arrive for the monitor to evaluate. Replication adds an extra layer of observability via the `snapshot_replication` extension:

- `idiot_index_observability_snapshots_total` – gauge reflecting how many snapshots currently live in storage.
- `idiot_index_observability_snapshot_age_seconds` – gauge with the age of the latest snapshot (0 when none exist).
- `idiot_index_snapshot_replications_total` – counter tracking replication attempts by status (`success`, `error`, `skipped`) and backend.
- `idiot_index_snapshot_replication_latency_seconds` – histogram of replication durations per backend.
- `idiot_index_snapshot_replication_age_seconds` – gauge with seconds since the most recent successful replication (0 when disabled or never run).
- `observability_snapshots` health component – `warn`s if no snapshots have been captured yet or the latest is older than 24 hours.
- `snapshot_replication` health component – summarises the most recent replication outcome and surfaces the last error message when uploads fail.

These signals appear under `/observability/status` and `/health`, so operators (or Kubernetes liveness probes) can detect stale archives or remote replication issues quickly.

## Visualising history

Streamlit’s new **Observability** tab reads the most recent snapshots from disk and surfaces:

- Rolling event totals, success/error counts, and labels.
- A timeline chart of recent captures.
- The most recent error payload, if any.

This view highlights regressions immediately after a deployment. Refresh the page after running `make observability-snapshot` to pull in fresh captures.

For automated post-incident reviews, run `python scripts/diagnostics_bundle.py --pretty --output build/reports/diagnostics.json` to capture the current health probe output, observability digest, filtered events, and snapshot metadata in a single JSON file.
