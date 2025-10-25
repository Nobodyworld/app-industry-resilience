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

## Health Probes

The observability layer exposes a reusable `HealthProbe` that aggregates component checks:

- **Configuration** – loads and validates environment variables via the strongly-typed config loader.
- **Cache** – ensures the configured cache directories exist and are writable.
- **Extensions** – confirms registered extensions loaded successfully.
- **Telemetry snapshot** – surfaces counts of registered metrics and exported spans.

### CLI Usage

Run the probe from the command line without hitting the HTTP API:

```bash
python scripts/check_health.py --pretty
```

Exit codes follow Unix conventions: `0` = healthy, `1` = warnings, `2` = failures. The JSON payload mirrors the
`/health` endpoint response so operators can plug it into automation or GitOps workflows.

## Continuous Integration

GitHub Actions mirrors the local quality gate. The workflow performs:

- Dependency caching and `make setup` bootstrapping.
- `make quality-gate` for lint/type/test/security enforcement.
- SBOM generation via `make sbom`.
- Upload of pytest coverage and pip-audit artefacts for later inspection.

Failures post annotated diffs directly in pull requests to guide contributors. The workflow respects the same
`SKIP_PIP` guardrails so self-hosted runners without external network access can execute the checks.

## Automation for Agents

Automation-focused contributors (including AI agents) must:

- Read `AGENTS.md` for repository-wide guardrails.
- Produce or update ExecPlans under `docs/execplans/` when delivering non-trivial changes.
- Use the health CLI or `/health` endpoint to verify readiness after deployments.
- Update `EXTENSION_GUIDE.md` and `CHANGELOG.md` when new extensions or observability hooks are introduced.

Following these patterns keeps local and remote automation aligned, reduces deployment surprises, and provides a
single source of truth for operational status.
