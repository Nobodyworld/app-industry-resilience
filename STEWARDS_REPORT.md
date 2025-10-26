# Steward Report – Idiot Index Platform

## System Metrics
| Metric | Value | Source |
| --- | --- | --- |
| Test coverage (src) | 93.00% | `make quality-gate` trace fallback (`scripts/run_tests_with_trace.py`). 【05f7f4†L1-L33】 |
| Avg cyclomatic complexity (core modules) | 29.22 (Top 5: `core.config` 72.0, `core.security` 56.0, `core.analytics` 34.0, `core.normalize` 30.0, `core.cache` 29.0) | `python scripts/audit_metrics.py --runs 3`. 【ecb1e0†L1-L29】 |
| Dependency depth / cohesion ratio | Depth 5 / Cohesion 0.798 (245 internal edges, 62 external) | `python scripts/audit_metrics.py --runs 3`. 【ecb1e0†L1-L29】 |
| Source footprint | 0.263 MB of Python modules under `src/` | `python scripts/audit_metrics.py --runs 3`. 【ecb1e0†L1-L29】 |
| IdiotIndexService evaluate latency | 0.0443 s average on bundled dataset (3 runs) | `python scripts/audit_metrics.py --runs 3`. 【ecb1e0†L1-L29】 |
| Quality gate duration | 54.66 s real time end-to-end (`make quality-gate`) | `time make quality-gate`. 【05f7f4†L24-L33】 |

## Audit Highlights
- Eliminated empty observability contexts by adding `ObservabilityRegistry.record_event(...)` and refactoring Idiot Index workflows plus data-quality instrumentation to emit profiling signals through the helper. 【F:src/infrastructure/observability/instrumentation.py†L109-L139】【F:src/application/idiot_index_service.py†L174-L178】【F:src/application/scenario_planner.py†L156-L164】【F:tests/test_observability.py†L33-L129】
- Hardened the steward metrics CLI with a `coverage.xml` fallback so audits succeed even when only pytest coverage artefacts are present, with regression tests covering the path. 【F:scripts/audit_metrics.py†L170-L187】【F:tests/test_scripts.py†L45-L62】
- Unified script execution by adding `_bootstrap` and packaging `scripts/` so every helper works with plain `python scripts/<tool>.py`, keeping automation resilient to PYTHONPATH differences. 【F:scripts/_bootstrap.py†L1-L10】【F:scripts/__init__.py†L1-L8】
- Introduced the steward metrics CLI (`scripts/audit_metrics.py`) and `make audit` target, wiring the output into docs and `build/reports/audit-metrics.json`. 【F:scripts/audit_metrics.py†L1-L239】【F:Makefile†L18-L33】【F:Makefile†L136-L147】
- Captured automation responsibilities in the new `AUTOMATION_ROLES.md` and updated contributor/automation guides with the audit workflow and script bootstrap expectations. 【F:AUTOMATION_ROLES.md†L1-L11】【F:AUTOMATION.md†L1-L84】【F:CONTRIBUTING.md†L1-L73】
- Delivered `/observability/digest`, the `observability_tail.py` streaming CLI, and the `extensions_catalog.py` inventory tool so operators and agents can inspect telemetry and extension metadata without code changes. 【F:src/interfaces/api/app.py†L135-L169】【F:scripts/observability_tail.py†L1-L127】【F:scripts/extensions_catalog.py†L1-L78】

## Simplification Log
- Replaced no-op observability contexts with the dedicated `record_event(...)` helper so dataset/scenario profiling emits spans and counters without boilerplate. 【F:src/infrastructure/observability/instrumentation.py†L118-L139】【F:src/application/idiot_index_service.py†L174-L178】【F:src/application/scenario_planner.py†L156-L164】
- Normalised script entry points via a shared `_bootstrap` shim and defensive imports, eliminating repeated `sys.path` hacks across the CLI surface. 【F:scripts/audit_metrics.py†L5-L21】【F:scripts/prefetch_data.py†L6-L17】
- Added a coverage report fallback that reads `coverage.xml` when the trace JSON is absent so stewardship audits continue to run in pytest-only environments. 【F:scripts/audit_metrics.py†L170-L187】【F:tests/test_scripts.py†L45-L62】

## Key Recommendations
1. Restore native `pytest-cov` availability (vendor wheels) so coverage enforcement no longer depends on the trace fallback. 【05f7f4†L1-L33】
2. Decompose `src/core/security` and `src/core/config` into focused helpers; both dominate complexity rankings in the audit output. 【ecb1e0†L1-L29】
3. Persist observability state (metrics/recent events) to survive process restarts, enabling richer long-term audit trails.

## Automation Hooks & Agent Notes
- `make quality-gate` – full lint/type/test/security pipeline (# agent-safe-task). 【F:Makefile†L54-L90】
- `make observability` – JSON snapshot of metrics/traces/health (# agent-safe-task). 【F:Makefile†L136-L142】
- `make audit` – steward metrics JSON (coverage, complexity, dependencies, latency) tagged for agents. 【F:Makefile†L139-L145】
- `AUTOMATION_ROLES.md` enumerates steward-facing agent roles and trigger points; keep it aligned with new workflows. 【F:AUTOMATION_ROLES.md†L1-L13】

## Forward Roadmap
### Short Term
- Package offline wheels for `pytest-cov` and allied tooling so CI and local runs share identical coverage enforcement.
- Refactor the heaviest complexity hotspots surfaced by the audit (`core.security`, `core.config`) into testable submodules.

### Mid Term
- Add persistent telemetry exporters (e.g., JSON or OTLP) so observability snapshots survive process restarts and feed external monitors.
- Expand stewardship metrics to include memory footprints and extension load times for regression tracking.

### Long Term
- Explore distributed observability/state backends to support multi-instance deployments with coordinated health and rate limiting.
- Define a declarative extension manifest validator so agent-authored plugins can be auto-checked before activation.

## Emerging Risks
- **Complexity concentration** – `src/core.config` and `src/core.security` now lead the branching rankings (72 and 56 respectively), increasing maintenance risk. 【ecb1e0†L1-L29】
- **Ephemeral telemetry** – observability data is in-memory only; audits lose context after restarts, reducing trend visibility.
- **Dependency gaps** – continuing without vendored coverage tooling leaves CI reliant on the trace fallback and manual JSON parsing.

## Potential Agent Roles
| Role | Mandate | Trigger |
| --- | --- | --- |
| Stewardship Auditor | Run `make audit`, archive `build/reports/audit-metrics.json`, and update this report after major merges. | Weekly cadence or when core/tests change. |
| Observability Sentinel | Verify `/health`, `/observability/status`, and CLI probes, ensuring instrumentation docs stay accurate. | Post-deployment. |
| Telemetry Archivist | Confirm dataset/scenario profiling emits via `registry.record_event(...)`, archive `/observability/digest` snapshots, and diff recent events after releases. | After observability or extension changes. |
| Extension Gatekeeper | Vet extension manifests, run scaffolds, and ensure new modules register instrumentation correctly. | When `extensions/manifest.json` changes. |

For detailed task descriptions and tool references see `AUTOMATION_ROLES.md`.
