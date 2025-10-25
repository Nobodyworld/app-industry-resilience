# Steward Report – Idiot Index Platform

## System Metrics
| Metric | Value | Method / Notes |
| --- | --- | --- |
| Test coverage (src) | 85.9% | Calculated via `python -m trace --count --summary` with offline-friendly parsing of `build/coverage/*.cover`. |
| Avg cyclomatic complexity (core modules) | 6.85 | AST walk heuristic across `src/core/**/*.py`; top modules: `core/utils.py` (15.0), `core/normalize.py` (10.67). |
| Internal dependency depth | Depth 4, cohesion ratio 0.35 | Static import graph scan (internal imports / total imports). |
| Quality gate duration | 65.2 s | `time make quality-gate` (without pytest-cov due to restricted PyPI access). |
| Source tree footprint | 804 KB | `du -sh src`. |
| IdiotIndexService evaluate latency | ~11.5 ms avg | 5-sample run of `IdiotIndexService.evaluate` with sample dataset. |

## Audit Highlights
- Naming, imports, and module boundaries remain consistent with layered architecture; new observability code reuses shared helpers.
- Documentation (README, automation guides, API docs) matches the current CLI + `/health` contract.
- Config + security artifacts (`requirements*.txt`, `Makefile`, `SECURITY.md`) remain aligned and reference the enforced quality gate.

## Simplification Log
- Replaced manual telemetry span management in `src/interfaces/api/app.py` with context manager usage for clearer flow and automatic cleanup.
- Tagged `scripts/check_health.py` CLI as an agent-safe entrypoint to codify automation boundaries.

## Key Recommendations
1. Restore `pytest-cov` availability (or vendor the wheel) so the quality gate enforces coverage ≥90% without the trace fallback.
2. Address the heaviest complexity hotspot (`src/core/utils.py`) by splitting dataset munging helpers into dedicated modules with focused responsibilities.
3. Expand scenario planner tests around cache toggling to increase coverage for the new `HealthProbe` metadata paths.

## Automation Hooks & Agent Notes
- `make quality-gate` – canonical full check; safe for CI and agents to run locally (# agent-safe-task).
- `python scripts/check_health.py --pretty` – fast readiness probe across configuration, cache, and extensions (# agent-entrypoint).
- `python -m trace --count --summary --module pytest` – offline coverage workflow when pytest-cov is unavailable.

## Forward Roadmap
### Short Term (next release)
- Package offline wheels for dev dependencies to stabilise coverage tooling and security scans under restricted networks.
- Refine `src/core/utils.py` helpers to lower complexity and improve test isolation.

### Mid Term
- Add lightweight OpenTelemetry exporter or JSON trace sink so CLI + API share span telemetry without modifying core business logic.
- Build a preflight cache warming command that surfaces progress metrics (leveraging existing telemetry registry).

### Long Term
- Containerise the headless API with baked-in health + metrics endpoints and document horizontal scaling guidance.
- Explore plugin sandboxing so third-party analytics can run with explicit resource limits and audit logs.

## Emerging Risks
- **Dependency drift**: blocked network access makes it easy for dev + CI environments to diverge; maintain an internal mirror or lock wheel artifacts.
- **Telemetry gaps**: new components depend on in-memory metrics; without persistence, long-running analytics agents may lose context after restarts.
- **Extension sprawl**: as plugins grow, ensure manifest validation keeps load order deterministic.

## Potential Agent Roles
| Role | Mandate | Trigger |
| --- | --- | --- |
| Test Maintainer | Keep coverage ≥90%, backfill missing scenarios, and manage the trace fallback workflow. | Nightly or when trace coverage <90%. |
| Observability Steward | Monitor `/metrics`, validate health probe output, and update dashboards/docs. | On each deployment. |
| Extension Curator | Review new extensions, update manifest/docs, and enforce guardrails. | When `extensions/manifest.json` changes. |

