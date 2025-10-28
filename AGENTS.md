# Automation Guidance for Idiot Index

This repository welcomes code-writing agents as long as they follow the guardrails below. Human contributors should also review these expectations when orchestrating automated workflows.

## Golden Rules

1. **Always run the quality gate** before committing (`make quality-gate`). This ensures linting, type checks, tests, coverage enforcement, and security scans all pass locally.
2. **Respect the extension system.** Load reusable logic via the `ExtensionManager` rather than modifying core services directly. New plugins should be created with `python scripts/scaffold_extension.py --name <snake_case_name>`.
3. **Keep telemetry intact.** The observability layer under `src/infrastructure/observability` powers Prometheus metrics, the `/observability/status` endpoint, and trace correlation. Do not remove or bypass instrumentation without updating the docs and dashboards.
4. **Prefer instrumentation extensions.** When adding metrics or health checks, register an `InstrumentationExtension` through the `ExtensionManager` instead of editing core services directly.
5. **Publish connectors via extensions.** Register new integrations as `ConnectorExtension` modules so `/meta/connectors`, Streamlit, and observability digests stay accurate. Verify catalog output with `make connectors-catalog`.
6. **Document deviations.** If an agent changes behaviour or relaxes a guard, explain the rationale in the pull request body and update the relevant guides (README, EXTENSION_GUIDE.md, RELEASE_NOTES.md).

## Safe Operating Checklist

- Run all commands from the repository root (`/workspace/idiot-index-app`).
- Prefer the provided Make targets for setup and validation (`make setup`, `make quality-gate`, `make api`).
- Use `make observability-tail` and `make extensions-catalog` for read-only diagnostics instead of modifying core services when triaging instrumentation issues.
- When creating new extensions or automation scripts, update `extensions/manifest.json` and the relevant docs (`EXTENSION_GUIDE.md`) so that humans can audit the change.
- For data-fetching tasks, avoid hitting production APIs in tests; use the bundled sample dataset instead.

## Handoff Expectations

Agents must leave the working tree clean after execution:

- No pending migrations or generated files outside `build/`.
- All manifests (`extensions/manifest.json`, `pyproject.toml`, etc.) should be formatted and valid JSON/TOML.
- The latest documentation must reflect the executed work, especially when extending the observability or plugin layers.

By adhering to this guidance, automated and human contributors can collaborate without breaking the Idiot Index platform.
