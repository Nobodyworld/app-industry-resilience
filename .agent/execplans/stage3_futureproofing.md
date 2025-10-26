# Stage 3 Future-Proofing ExecPlan

## Goals
- Establish a reusable observability registry that bridges metrics, tracing, and health probes.
- Extend the extension system with an instrumentation plugin interface and ship a built-in reference plugin.
- Provide developer tooling (CLI, scaffolds, docs) to accelerate future module/extension creation.
- Strengthen continuous improvement loops through automation configs and dependency freshness.

## Tasks
1. Implement `ObservabilityRegistry` with event publication, metric/tracing helpers, and health probe integration.
2. Update API telemetry and IdiotIndexService to leverage the registry; expose an `/observability/status` endpoint.
3. Extend `ExtensionManager` contracts for instrumentation extensions and add a built-in observability plugin.
4. Ship supporting tooling: observability snapshot CLI, updated scaffolds, Dependabot config, Make target for releases.
5. Update documentation (architecture, automation, extension guide, contributing, incident response, reports) reflecting new workflows.
6. Ensure TODO comments include priority/effort metadata and refresh CHANGELOG/RELEASE_NOTES/REPORTS.

## Validation
- `make quality-gate`
- New unit tests covering observability registry behaviour, instrumentation plugin, and CLI scaffolds.
