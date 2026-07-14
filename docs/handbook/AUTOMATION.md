# Automation & Health Operations

This guide documents the automation surfaces that keep the Industry Resilience project healthy: local quality gates, continuous integration, health probes, and agent-friendly entry points.

## Local Quality Gate

Current Python support policy: use Python 3.13+ for local and CI validation. Historical plans may reference older versions; treat those as archival context only.

Use `make quality-gate` before every commit. The target runs:

1. Black in check mode against `app.py`, `src/`, and `tests/`.
2. Ruff linting with the repository-standard rule set.
3. mypy type checks.
4. `make coverage-runtime` to enforce runtime-path coverage (default fail-under 85), followed by `make coverage-full` for an informational full-`src` report.
5. `pip-audit` plus the configured `detect-secrets` baseline check.

If PyPI access is unavailable, the runtime coverage target can use the repository's trace-based fallback. Other missing tools may be skipped locally where the Makefile explicitly allows it, but CI treats required security tools as hard requirements.

The steward report documents how to interpret coverage output and confirm runtime-path coverage stays above the enforced threshold.

Repository helper scripts live under `src/scripts/` and self-bootstrap the repository root onto `PYTHONPATH` for direct execution.

## Health Probes & Observability

The observability layer exposes a reusable `HealthProbe` that aggregates component checks and binds into the shared `ObservabilityRegistry` so metrics, traces, and health stay aligned:

- **Configuration** – loads and validates environment variables via the strongly typed config loader.
- **Cache** – ensures the configured cache directories exist and are writable.
- **Extensions** – confirms registered extensions loaded successfully.
- **Telemetry snapshot** – surfaces counts of registered metrics and exported spans.

The registry powers `/observability/status` and the enriched `/observability/digest` endpoint on the API surface and can be queried offline:

```bash
python src/scripts/observability_snapshot.py --pretty
python src/scripts/observability_tail.py --follow --limit 20
```

The snapshot mirrors the HTTP payload and includes recent operation events, metric counts, registered health checks, and event counters. Use it alongside the health probe for incident reviews, and use `observability_tail.py` when you need a streaming view without hitting the HTTP API.

Snapshot persistence is automated by the `snapshot_persistence` instrumentation extension. It records a snapshot on process startup or shutdown and whenever instrumentation publishes `warn` or `error` events, then prunes history according to `OBSERVABILITY_SNAPSHOT_RETENTION_COUNT`, `OBSERVABILITY_SNAPSHOT_RETENTION_DAYS`, and `OBSERVABILITY_SNAPSHOT_MIN_INTERVAL_SECONDS`. Each persistence run emits an `observability.snapshot.replication` event so the companion `snapshot_replication` instrumentation extension can update replication counters, latency histograms, and a health component summarising the latest remote outcome.

Enable remote shipping by exporting `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND` with the desired backend (`s3`, `gcs`, or `azure-blob`) alongside the backend-specific configuration variables. When set, every persisted snapshot—whether triggered by the extension or `python src/scripts/observability_snapshot.py --store`—is uploaded after the local write completes. Failures are surfaced in CLI output but do not block local disk persistence. For local mirroring or dry runs, set `OBSERVABILITY_SNAPSHOT_REMOTE_BACKEND=plugin:debug` and optionally `OBSERVABILITY_SNAPSHOT_REMOTE_OPTIONS='{"path": "./build/debug-replication"}'`.

When you need a single artefact for a ticket or incident record, run:

```bash
python src/scripts/diagnostics_bundle.py --pretty --include-metrics --output build/reports/diagnostics.json
```

The bundle combines the health probe output, observability digest, filtered recent events, and snapshot metadata.

### Connector Catalog

The connector registry powers `/meta/connectors`, Streamlit's configuration sidebar, and downstream automation. Inspect the current catalog and health snapshots without hitting the API:

```bash
make connectors-catalog ARGS="--json --pretty"
python src/scripts/connectors_catalog.py --kind data_source --pretty
```

Each entry includes identifier, version, capabilities, metadata, and the most recent health component published through the observability registry. Built-in connectors cover the bundled sample CSV, BEA API, and Census ASM sources; custom extensions should register additional connectors so operators and agents can track rollout status centrally.

### CLI Usage

Run the probe from the command line without hitting the HTTP API:

```bash
python src/scripts/check_health.py --pretty
```

Exit codes follow Unix conventions: `0` = healthy, `1` = warnings, `2` = failures. The JSON payload mirrors the `/health` endpoint response so operators can plug it into automation or GitOps workflows.

## Stewardship Metrics

Run `make audit` or `python src/scripts/audit_metrics.py --runs 3` to capture the metrics that feed the steward report:

- Coverage percentage sourced from the current coverage artefacts.
- Cyclomatic complexity averages plus the highest-complexity core modules.
- Internal dependency graph depth, cohesion ratio, and total edge counts.
- Service latency sampled against the bundled dataset for regression tracking.

The command writes `build/reports/audit-metrics.json` and prints the JSON payload so agents can archive or diff the results. The script carries an `# agent-entrypoint` tag to signal safe automation use.

## Continuous Integration & Dependency Hygiene

The pinned GitHub Actions workflow mirrors the supported local quality gate. It:

- Checks out the repository using a full-length immutable action SHA.
- Configures Python 3.13 with pip caching.
- Installs `requirements.txt` and `requirements-dev.txt`.
- Runs `make quality-gate` for formatting, linting, type checking, coverage, vulnerability scanning, and secret-baseline enforcement.
- Uploads `coverage.xml` as the `coverage-xml` artifact when the report exists.

The workflow uses the standard `ubuntu-latest` runner, read-only `contents` permission, and a 30-minute timeout. The separate Docker Smoke workflow validates the production image, non-root runtime user, Streamlit health, API health and metrics, and uploads `docker-validation-evidence` on deployment-relevant changes.

Dependabot checks both `pip` and GitHub Actions weekly. Python updates are capped at three simultaneous pull requests and Actions updates at two; both use the existing `dependencies` label and automatic rebasing.

Every external `uses:` reference must remain pinned to a full-length immutable commit SHA. Moving action tags are not accepted by repository policy.

## Automation for Agents

Automation-focused contributors, including AI agents, must:

- Read [`docs/AGENTS.md`](../AGENTS.md) for repository-wide guardrails.
- Produce or update ExecPlans under `docs/execplans/` when delivering non-trivial changes.
- Use the health CLI or `/health` endpoint to verify readiness after deployments.
- Refresh stewardship metrics with `make audit` whenever architecture or coverage changes.
- Update `EXTENSION_GUIDE.md` and `CHANGELOG.md` when new extensions or observability hooks are introduced. Verify registration with `make extensions-catalog` or `python src/scripts/extensions_catalog.py --json`.
- Audit connector coverage with `make connectors-catalog` or `python src/scripts/connectors_catalog.py --json` whenever integrations are added or retired.
- Capture live telemetry during incident response with `make observability-tail ARGS="--follow --limit 50"` and archive the stream alongside `/observability/digest` snapshots.

Following these patterns keeps local and hosted automation aligned, reduces deployment surprises, and provides a single source of truth for operational status.

> **Tip:** Scripts under `src/scripts/` self-bootstrap the repository root onto `PYTHONPATH`, so `python src/scripts/<tool>.py` works without `pip install -e .`.
