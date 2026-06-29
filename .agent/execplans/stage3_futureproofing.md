# Stage 3 Future-Proofing ExecPlan

This ExecPlan is a living document. Maintain it in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

Stage 3 elevates Idiot Index from a hardened product to a long-lived platform. Contributors will be able to introspect telemetry, plug in new instrumentation or analytics modules without touching core services, and bootstrap automation scripts that surface the same health signals available over HTTP. After this work, operators can tail observability events offline, extension authors can enumerate and test their modules quickly, and steward reports draw from richer system diagnostics.

## Progress

- [x] (2025-10-26 09:35Z) Draft ExecPlan capturing scope, architecture context, and validation workflow.
- [x] (2025-10-26 09:35Z) Implement observability digest export, CLI tail command, and API endpoint wiring.
- [x] (2025-10-26 09:35Z) Extend `ExtensionManager` with catalog/introspection helpers plus tests.
- [x] (2025-10-26 09:35Z) Add reference instrumentation extension demonstrating event subscriptions and health integration.
- [x] (2025-10-26 09:35Z) Ship developer enablement tooling (extension catalog CLI, Make target) and document workflows.
- [x] (2025-10-26 09:35Z) Update docs (architecture, automation, extension guide, incident response, contributing) and changelog/release artefacts.
- [x] (2025-10-26 10:34Z) Run `make quality-gate`, capture artefacts, and summarise outcomes.

## Surprises & Discoveries

- Observation: Resetting the observability singleton was necessary to keep the streaming CLI test deterministic.
  Evidence: `tests/test_observability.py` clears `instrumentation._REGISTRY_SINGLETON` before invoking `observability_tail.main` to avoid residual events from prior tests.

## Decision Log

- Decision: Emit dataset/scenario quality metrics via lightweight `ObservabilityRegistry.operation(...)` contexts rather than new APIs so extensions can subscribe without extra plumbing.
  Rationale: Keeps instrumentation consistent with existing event semantics, enabling histogram/gauge updates through the shared registry and simplifying tests.
  Date/Author: 2025-10-26 / gpt-5-codex

## Outcomes & Retrospective

- Validation: `make quality-gate` completed successfully (`chunk b1ed4d`, `chunk b25a8d`, `chunk 29d88d`, `chunk bddbee`), exercising black, ruff, mypy (56 files, clean), pytest (135 tests, trace coverage 93.01%), and security fallbacks.
- Coverage: Trace instrumentation reports stored under `build/reports/coverage-trace.*` supplement the enforced runtime-path gate (default 85) and informational full-source tracking.
- Observations: CLI/event tests remain deterministic after resetting `_REGISTRY_SINGLETON`; no new TODO-Px items required.

## Context and Orientation

The repository already exposes an `ObservabilityRegistry` under `src/infrastructure/observability/instrumentation.py` that emits recent event payloads and binds a `HealthProbe`. FastAPI routes live in `src/interfaces/api/app.py`, where `/observability/status` returns metrics, trace counts, and recent events. CLI tooling in `scripts/observability_snapshot.py` prints the same snapshot, and `scripts/check_health.py` wraps the health probe. The extension system is implemented in `src/extensions/manager.py` with contracts in `src/extensions/contracts.py`. Built-in instrumentation modules live under `src/extensions/builtins/`, notably `core_instrumentation.py` and `rate_limiting.py`. Tests covering observability behaviour reside in `tests/test_observability.py` and `tests/test_observability_health.py`. Documentation describing these systems is split across `docs/ARCHITECTURE_OVERVIEW.md`, `AUTOMATION.md`, `EXTENSION_GUIDE.md`, and `docs/OPERATIONS_INCIDENT_RESPONSE.md`.

Gap analysis for Stage 3:

1. There is no durable API to export an observability "digest" combining metrics, traces, health status, and event timelines suitable for dashboards or incident post-mortems. The snapshot endpoint exposes only limited metadata, and no CLI can stream or tail events.
2. Extension authors lack introspection helpers or CLI commands to list registered modules, check hook types, or verify health contributions. The `ExtensionManager` maintains internal lists but does not expose them in a stable format.
3. Reference instrumentation is limited to core/rate limiting. Adding another plugin that listens to custom events and reports health will demonstrate the extension boundary and encourage reuse.
4. Developer ergonomics can improve with CLI wrappers (e.g., `python scripts/extensions_catalog.py`) and Make targets. Documentation must describe incident response workflows, observability tooling, and extension testing. CHANGELOG/RELEASE_NOTES should capture the platform upgrades.

## Plan of Work

1. **Observability digest & CLI tailing**
   - Enhance `ObservabilityRegistry` with a new `digest()` method returning metrics, trace counts, registered health checks, and recent events separated into successes, warnings, and failures. Track event statistics (counts by status, last error) to aid incident review.
   - Add an optional subscriber that records log-friendly lines; expose a helper `iter_events()` yielding `ObservationEvent` dictionaries.
   - Introduce `scripts/observability_tail.py` that subscribes to `registry.subscribe("*", ...)` and streams events to stdout with optional JSON formatting, plus `--once`/`--follow` flags.
   - Extend FastAPI app with a `/observability/digest` endpoint returning the new payload. Update Pydantic schema models under `src/interfaces/api/schemas.py` accordingly.
   - Write tests in `tests/test_observability.py` asserting digest structure, event counters, and CLI parsing behaviour (use `capsys` to capture output).

2. **Extension catalog & introspection tooling**
   - Augment `ExtensionManager` with a `catalog()` method returning dataclasses describing registered extensions (name, type, docstring, module). Provide helper functions to list instrumentation health contributions (hook names).
   - Create `scripts/extensions_catalog.py` that prints the catalog (support `--json`/`--pretty`). Add a Make target (`make extensions-catalog`) invoking the script.
   - Update tests (`tests/test_extensions.py`) to cover catalog output and ensure instrumentation extensions register only once per registry instance.

3. **Reference instrumentation extension**
   - Add `src/extensions/builtins/data_quality.py` capturing observation events named `service.idiot_index.evaluate` and `service.scenario.plan`, computing basic data quality stats (e.g., NaN counts) via event attributes (requires instrumentation to emit dataset stats) or hooking into the new digest aggregator. If direct metrics are not available, instrument pipeline functions to publish `service.dataset.export` events with dataset metadata, then subscribe in the extension.
   - Register the new extension in `extensions/manifest.json` and document its purpose. Provide tests validating the extension's health check and event subscription.

4. **Pipeline instrumentation enhancements**
   - Update `src/application/idiot_index_service.py` and `src/application/scenario_planner.py` to publish additional observation events, including dataset row counts, NaN totals, and scenario adjustment counts. Use `registry.operation(..., attributes=...)` plus explicit `registry.subscribe` hooks.
   - Ensure instrumentation remains optional when the registry is absent; preserve backwards compatibility.

5. **Documentation & automation updates**
   - Refresh `docs/ARCHITECTURE_OVERVIEW.md` with diagrams/sections describing the new digest endpoint, extension catalog, and observability tail CLI.
   - Update `AUTOMATION.md`, `AGENTS.md`, `EXTENSION_GUIDE.md`, `CONTRIBUTING.md`, and `docs/OPERATIONS_INCIDENT_RESPONSE.md` to reference the new tooling, Make targets, and incident flow.
   - Add guidance in `docs/API_REFERENCE.md` and `README.md` for the `/observability/digest` endpoint and CLI usage. Update `CHANGELOG.md`, `RELEASE_NOTES.md`, `STATUS.md`, and steward reports accordingly. Ensure TODO comments include priority/effort tags if new ones are introduced.

6. **Validation**
   - Run `make quality-gate` at the end. Capture CLI output and note coverage deltas.
   - Summarise results in ExecPlan `Outcomes & Retrospective`, referencing tests and artefacts.

## Concrete Steps

1. Update the ExecPlan (this document) before starting implementation.
2. Modify `src/infrastructure/observability/instrumentation.py` to add digest/event helpers and supporting data structures.
3. Adjust `src/interfaces/api/schemas.py` and `src/interfaces/api/app.py` to expose the new digest endpoint.
4. Create/modify CLI scripts under `scripts/` (`observability_tail.py`, `extensions_catalog.py`) and wire them into the Makefile.
5. Extend application services to emit richer observation attributes or additional events needed by the new extension.
6. Implement the new `data_quality` instrumentation extension and register it in `extensions/manifest.json`.
7. Write or update tests covering observability digest, CLI behaviour, extension catalog, and the new instrumentation extension.
8. Update documentation and release artefacts.
9. Run `make quality-gate`. If it fails, iterate until green.
10. Capture outputs (test results, CLI transcripts) in the ExecPlan.

## Validation and Acceptance

- `make quality-gate` must pass with the runtime-path coverage gate (`RUNTIME_COVERAGE_THRESHOLD`, default 85).
- `python scripts/observability_snapshot.py --pretty` should include digest metadata and reference the new extension health check.
- `python scripts/observability_tail.py --once` must print a well-formatted event.
- `python scripts/extensions_catalog.py --json` should list all registered extensions, including the new data quality plugin, grouped by type.
- FastAPI `/observability/digest` endpoint should return HTTP 200 with the new schema and contain event counters.
- Tests validating the new extension and CLI must pass.

## Idempotence and Recovery

Edits are additive and configuration driven. Running the CLI scripts multiple times is safe; they are read-only views. If schema changes break tests, revert the affected modules via `git checkout -- <path>` and reapply carefully. Registry modifications are backward compatible (new helpers default to existing behaviour). Ensure `extensions/manifest.json` remains valid JSON to avoid loader failures.

## Artifacts and Notes

- Capture `make quality-gate` output in the ExecPlan once executed.
- Record snippets from the new CLI commands to demonstrate behaviour.
- Document any deviations or follow-up TODOs (tagged with `TODO-Px(<hours>)`).

## Interfaces and Dependencies

- Continue relying on built-in observability primitives; no new third-party dependencies are required.
- CLI scripts use `argparse` and standard library only.
- API schema updates must use Pydantic models defined in `src/interfaces/api/schemas.py`.
- Tests rely on pytest fixtures already defined in `tests/conftest.py`.

## Change Log

- 2025-10-26: Initial ExecPlan drafted to cover Stage 3 future-proofing scope.
