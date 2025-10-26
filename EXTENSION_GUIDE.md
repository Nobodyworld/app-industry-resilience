# Idiot Index Extension Guide

The Idiot Index platform exposes a formal extension layer so new analytics, connectors, and scenario enrichments can evolve independently of the core application. This guide explains how to build, register, and validate extensions.

## Concepts

- **ExtensionManager** – runtime registry that loads modules declared in `extensions/manifest.json` and via the `IDIOT_INDEX_EXTENSIONS` environment variable. It fans out to three hook types:
  - `SummaryExtension` operates on `IdiotIndexSummary` objects and can emit additional notes or metadata.
  - `ScenarioExtension` operates on `ScenarioResult` payloads to enrich scenario planning outputs.
  - `InstrumentationExtension` registers metrics, tracing hooks, and health checks against the shared `ObservabilityRegistry`.
- **ExtensionContributions** – normalized payload returned by each extension. Notes are appended to existing domain notes with the pattern `[extension_name] <message>`, while metadata is stored under `metadata["extensions"][<extension_name>]`.

## Creating an Extension

1. **Generate a scaffold** using the helper script:
   ```bash
   python scripts/scaffold_extension.py --name supply_chain_risk --with-scenario --instrumentation
   ```
   This creates `src/extensions/community/supply_chain_risk.py`, ensures the `community` package exists, and appends the module path to `extensions/manifest.json`.

2. **Implement hooks.** Edit the generated file:
   - Populate `SummaryExtension.contribute` with domain logic that reads from the supplied `IdiotIndexSummary`.
   - If `--with-scenario` was used, implement `ScenarioExtension.contribute` to analyze `ScenarioResult` objects.
   - When `--instrumentation` is present, the scaffold includes a stub `InstrumentationExtension` that subscribes to the `ObservabilityRegistry`. Use it to emit custom counters, histograms, or health checks without touching core services.
   - Use structured metadata (dicts, lists, numbers) to keep responses JSON serialisable.

3. **Write tests.** Add unit tests under `tests/` that import the extension module, run `ExtensionManager.apply_*` helpers, and verify notes/metadata appear as expected. See `tests/test_extensions.py` for examples.

4. **Run the quality gate.** Execute `make quality-gate` to confirm linting, type checks, tests, security scans, and coverage all pass before committing.

## Loading Extensions Dynamically

- Modules listed in `extensions/manifest.json` load automatically for all entry points (API, Streamlit, scripts). The manifest accepts dotted import paths, e.g. `"src.extensions.community.supply_chain_risk"`.
- Additional modules can be injected at runtime by setting `IDIOT_INDEX_EXTENSIONS="package.module,another.module"`.
- Failed imports or exceptions are logged with trace IDs but do not crash the service. The manager skips faulty extensions and continues processing.

## Observing Extension Output

- API clients receive extension metadata via `metadata.extensions`. For example, the built-in `manufacturing_cost_driver` surfaces:
  ```json
  "extensions": {
    "manufacturing_cost_driver": {
      "top_industry": {"industry_code": "222", "materials_share_pct": 50.0},
      "average_materials_share_pct": 35.0
    }
  }
  ```
- Notes appear in the response body (for APIs) or Streamlit UI as additional bullet points.
- Prometheus metrics expose overall request counts, allowing operators to correlate extension issues with `idiot_index_api_errors_total` labels. Instrumentation extensions can subscribe to the same registry and publish dedicated metrics (see `src/extensions/builtins/core_instrumentation.py` for a reference implementation).

## Safe Deployment Checklist

- Keep extension modules pure Python with deterministic behaviour; avoid blocking I/O in hooks.
- Document new modules in `docs/ARCHITECTURE_OVERVIEW.md` or team-specific runbooks.
- Update `CHANGELOG.md` and `RELEASE_NOTES.md` when extensions introduce user-visible insights.
- When instrumenting operations, prefer descriptive event names (e.g. `service.<domain>.execute`) so future extensions can subscribe selectively.

Following this workflow ensures extensions stay modular, observable, and easy to troubleshoot.
