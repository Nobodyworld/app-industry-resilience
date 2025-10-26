# Automation & Health Operations

This guide documents the automation surfaces that keep the Idiot Index project healthy—local quality gates, continuous
integration, health probes, and agent-friendly entry points.

## Local Quality Gate

Use `make quality-gate` before every commit. The target runs:

1. Black (check mode) against `app.py`, `src/`, and `tests/`.
2. Ruff linting with the repo-standard rule set.
3. mypy type checks (strict optional handling for the core packages).
4. `pytest --cov=src --cov-fail-under=90` to enforce coverage.
5. `pip-audit` plus `detect-secrets` scans with JSON artefacts in `build/reports/`.

If PyPI access is unavailable, generate coverage with the built-in trace harness instead:

```bash
python -m trace --count --summary --coverdir build/coverage --module pytest
```

The steward report documents how to parse `build/coverage/*.cover` to confirm the line-rate remains above the 90% target.

If any tool is unavailable offline, the Makefile falls back to the Python helper scripts inside `scripts/` so the
quality gate can still run in air-gapped environments.

## Health Probes & Observability

The observability layer exposes a reusable `HealthProbe` that aggregates component checks and binds into the shared `ObservabilityRegistry` so metrics, traces, and health stay aligned:

- **Configuration** – loads and validates environment variables via the strongly-typed config loader.
- **Cache** – ensures the configured cache directories exist and are writable.
- **Extensions** – confirms registered extensions loaded successfully.
- **Telemetry snapshot** – surfaces counts of registered metrics and exported spans.

The registry powers `/observability/status` and the enriched `/observability/digest` endpoint on the API surface and can be queried offline:

```bash
python scripts/observability_snapshot.py --pretty
python scripts/observability_tail.py --follow --limit 20
```

The snapshot mirrors the HTTP payload and includes recent operation events, metric counts, registered health checks, and event counters. Use it alongside the health probe for incident reviews, and reach for `observability_tail.py` when you need a streaming view without hitting the HTTP API.

### CLI Usage

Run the probe from the command line without hitting the HTTP API:

```bash
python scripts/check_health.py --pretty
```

Exit codes follow Unix conventions: `0` = healthy, `1` = warnings, `2` = failures. The JSON payload mirrors the
`/health` endpoint response so operators can plug it into automation or GitOps workflows.

## Stewardship Metrics

Run `make audit` (or `python scripts/audit_metrics.py --runs 3`) to capture the metrics that feed the steward report:

- Trace-based coverage percentage sourced from `build/reports/coverage-trace.json`.
- Cyclomatic complexity averages plus the top five core modules by branching factor.
- Internal dependency graph depth, cohesion ratio, and total edge counts.
- Idiot Index service latency sampled against the bundled dataset for regression tracking.

The command writes `build/reports/audit-metrics.json` and prints the JSON payload so agents can archive or diff the results.
The script carries an `# agent-entrypoint` tag to signal safe automation use.


## Continuous Integration & Dependency Hygiene

GitHub Actions mirrors the local quality gate. The workflow performs:

- Dependency caching and `make setup` bootstrapping.
- `make quality-gate` for lint/type/test/security enforcement.
- SBOM generation via `make sbom`.
- Upload of pytest coverage and pip-audit artefacts for later inspection.
- Weekly Dependabot checks for both `pip` and GitHub Actions (labelled `dependencies`/`automated`) to keep the stack current without manual babysitting.

Failures post annotated diffs directly in pull requests to guide contributors. The workflow respects the same
`SKIP_PIP` guardrails so self-hosted runners without external network access can execute the checks.

## Automation for Agents

Automation-focused contributors (including AI agents) must:

- Read `AGENTS.md` for repository-wide guardrails.
- Produce or update ExecPlans under `docs/execplans/` when delivering non-trivial changes.
- Use the health CLI or `/health` endpoint to verify readiness after deployments.
- Refresh stewardship metrics with `make audit` whenever architecture or coverage changes.
- Update `EXTENSION_GUIDE.md` and `CHANGELOG.md` when new extensions or observability hooks are introduced. Verify registration with `make extensions-catalog` (or `python scripts/extensions_catalog.py --json`).
- Capture live telemetry during incident response by running `make observability-tail ARGS="--follow --limit 50"` and archiving the stream alongside `/observability/digest` snapshots.

Following these patterns keeps local and remote automation aligned, reduces deployment surprises, and provides a
single source of truth for operational status.

> **Tip:** All scripts under `scripts/` now self-bootstrap the repository root onto `PYTHONPATH`, so running `python scripts/<tool>.py` works without `pip install -e .`.

