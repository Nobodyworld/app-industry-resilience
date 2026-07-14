# Automation Roles & Triggers

| Role | Primary Tasks | Trigger Sources | Key Tools |
| --- | --- | --- | --- |
| Stewardship Auditor | Run `make audit`, capture `build/reports/audit-metrics.json`, and update `STEWARDS_REPORT.md` metrics when coverage or architecture shifts. | Scheduled weekly or after merges touching `src/` or `tests/`. | `make audit`, `python src/scripts/audit_metrics.py`, `STEWARDS_REPORT.md` |
| Observability Sentinel | Verify `/health`, `/observability/status`, and CLI health probes; ensure recent events and metrics align with docs. When remote replication is enabled, confirm snapshots land in the configured backend and review stderr for replication warnings. | Post-deployment and when modifying instrumentation. | `python src/scripts/check_health.py`, `python src/scripts/observability_snapshot.py`, API smoke tests |
| Telemetry Archivist | Confirm dataset/scenario profiling emits via `registry.record_event(...)`, archive `/observability/digest` snapshots, and diff recent events after releases. | After observability or extension changes. | `python src/scripts/observability_tail.py`, `/observability/digest`, `STEWARDS_REPORT.md` |
| Dependency Curator | Refresh requirements, regenerate the SBOM, and review Dependabot PRs for compatibility. | Weekly Dependabot cadence or when dependency PRs open. | `make sbom`, dependency manifests, `CHANGELOG.md` |
| Extension Gatekeeper | Review new extension manifests, run scaffold scripts to reproduce contributions, and validate observability hooks. | When `extensions/manifest.json` or `src/scripts/scaffold_*.py` changes. | `python src/scripts/scaffold_extension.py`, `python src/scripts/scaffold_service.py`, `EXTENSION_GUIDE.md` |

Each role references tasks tagged with `# agent-safe-task` or `# agent-entrypoint` so automation can operate safely without bypassing guardrails. Maintain this file alongside `AUTOMATION.md` when adding new workflows or scripts.
