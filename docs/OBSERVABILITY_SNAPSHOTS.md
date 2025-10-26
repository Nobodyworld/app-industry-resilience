# Observability Snapshots

The observability registry now supports durable snapshots so operators can archive metrics, traces, and health summaries over time without scraping live services.

## Capturing snapshots

- Run `make observability-snapshot` to persist the current digest to the configured storage directory (`build/observability_snapshots` by default).
- Use the CLI directly for advanced flows:
  - `python scripts/observability_snapshot.py --store --label nightly` – capture and label the snapshot while still printing the digest to STDOUT.
  - `python scripts/observability_snapshot.py --list --pretty` – view stored snapshot metadata (IDs, timestamps, labels).
  - `python scripts/observability_snapshot.py --compare <snapshot.json>` – diff the latest stored snapshot against a previously captured file to see event/metric deltas.
- Storage can be relocated via the `OBSERVABILITY_SNAPSHOT_DIR` environment variable when running in multi-node or shared-volume deployments.

## Programmatic access

The API exposes snapshot history under `/observability/snapshots` (metadata) and `/observability/snapshots/{snapshot_id}` (full payload). Responses mirror the structure of `/observability/digest`, making it easy to diff or replay past states in automation scripts.

Snapshot identifiers are now validated server-side to block path traversal attacks. Identifiers must match `^[A-Za-z0-9_-]+$`; attempts to request `../foo` or other filesystem paths return `400 Bad Request` with a descriptive message. Automation that stores snapshot IDs should treat them as opaque tokens and avoid introducing separators.

The observability API also exposes `/observability/events`, which returns the most recent operation events (newest first) with optional status filters. Combine snapshot metadata with filtered events to reconstruct pre-/post-incident telemetry timelines.

## Health & metrics

The `snapshot_monitor` instrumentation extension keeps runtime health checks in sync with persisted history:

- `idiot_index_observability_snapshots_total` – gauge reflecting how many snapshots currently live in storage.
- `idiot_index_observability_snapshot_age_seconds` – gauge with the age of the latest snapshot (0 when none exist).
- `observability_snapshots` health component – `warn`s if no snapshots have been captured yet or the latest is older than 24 hours.

These signals appear under `/observability/status` and `/health`, so operators (or Kubernetes liveness probes) can detect stale archives.

## Visualising history

Streamlit’s new **Observability** tab reads the most recent snapshots from disk and surfaces:

- Rolling event totals, success/error counts, and labels.
- A timeline chart of recent captures.
- The most recent error payload, if any.

This view highlights regressions immediately after a deployment. Refresh the page after running `make observability-snapshot` to pull in fresh captures.

For automated post-incident reviews, run `python scripts/diagnostics_bundle.py --pretty --output build/reports/diagnostics.json` to capture the current health probe output, observability digest, filtered events, and snapshot metadata in a single JSON file.
