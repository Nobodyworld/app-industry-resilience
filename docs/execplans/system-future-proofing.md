# Idiot Index Platform Stabilisation and Extension

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Maintain this ExecPlan per `.agent/PLANS.md`.

## Purpose / Big Picture

Stage 3 requires the Idiot Index platform to evolve from a hardened product into a long-lived ecosystem. After implementing this plan contributors will be able to observe the system with Prometheus-compatible metrics and trace spans, plug in new data sources or analytics modules through a documented extension registry, bootstrap new services using curated scaffolds, and rely on automated quality gates that guard the mainline. The reference plugin and automation docs will show both humans and agents how to extend the platform safely.

Observable outcomes:

* The headless API exposes `/metrics` and `/healthz` endpoints with structured metrics and trace correlation IDs logged for each request.
* A new extension registry loads contributions declared in `extensions/` and via configuration. A sample `manufacturing_cost_driver` plugin adds a computed insight to Idiot Index responses without touching core services.
* `make quality-gate` (and the CI workflow) runs lint, type checks, tests with coverage enforcement, security scans, and metrics export validation in sequence.
* Contributors find `EXTENSION_GUIDE.md`, `AGENTS.md`, and updated `ARCHITECTURE_OVERVIEW.md` describing extension seams, incident response, and migration notes.

## Progress

- [x] (2025-10-25 00:12Z) Draft ExecPlan describing observability, extension, and automation deliverables.
- [x] (2025-10-25 02:05Z) Instrumented API/service flows with telemetry registry, Prometheus exporter, request tracing, and log correlation IDs.
- [x] (2025-10-25 03:18Z) Added extension registry, manufacturing cost driver plugin, and hooked contributions into services/tests.
- [x] (2025-10-25 04:05Z) Shipped developer/agent enablement assets including the health probe CLI, automation guide, and documentation refresh across README, API, architecture, and incident response.
- [x] (2025-10-25 04:15Z) Confirmed quality gate automation, updated changelog/release notes, and recorded API contract changes for `/health` consumers.
- [x] (2025-10-25 04:25Z) Ran validation commands, captured artefacts, and completed Outcomes & Retrospective for this plan.

## Surprises & Discoveries

- Observation: Dataclasses with `slots=True` reject late-bound attributes, requiring explicit metric fields on the telemetry helper.
  Evidence: `pytest tests/test_api.py::test_health_endpoint_reports_ok` initially failed with `AttributeError: 'ApiTelemetry' object has no attribute '_request_counter'` until dataclass fields were declared.
- Observation: Extension-generated notes augmented existing expectations; tests assuming fixed tuples required updates to accommodate plugin output.
  Evidence: `pytest tests/test_application.py::test_evaluate_sample_uses_loader` failed until assertions checked for both original and extension notes.
- Observation: Development environments without BEA/Census keys naturally surface `configuration` warnings in the new health probe.
  Evidence: `/health` returned status `warn` until tests were updated to accept `pass` or `warn`, ensuring we treat missing keys as degraded but not fatal in non-production setups.

## Decision Log

- Decision: Introduced an `InstrumentedFastAPI` subclass to host telemetry instead of reworking the façade's middleware stack.
  Rationale: Preserves compatibility with the in-repo FastAPI shim while guaranteeing both WSGI and TestClient paths emit metrics and traces.
  Date/Author: 2025-10-25 / gpt-5-codex
- Decision: Namespace extension metadata under the plugin name and surface contributions via dataframe attrs so downstream clients inherit context without schema changes.
  Rationale: Keeps responses backward compatible while enabling discovery of plugin output from both API and Streamlit layers.
  Date/Author: 2025-10-25 / gpt-5-codex
- Decision: Promote `/health` status semantics from "ok" to `pass`/`warn`/`fail` and surface component breakdowns while keeping the legacy telemetry field for compatibility.
  Rationale: Operators gain actionable readiness signals without breaking existing clients that rely on the old telemetry payload.
  Date/Author: 2025-10-25 / gpt-5-codex

## Outcomes & Retrospective

The observability and extensibility goals for Stage 3 are complete. Metrics, tracing, and the new health probe provide
actionable telemetry across the API and CLI surfaces, while the extension system remains stable through documentation and
tests. Automation guidance now lives in `AUTOMATION.md`, and the quality gate enforces lint/type/test/security parity
locally and in CI. Remaining opportunities include expanding extension scaffolds for scenario plugins and evaluating
multi-tenant configuration strategies documented in future roadmap work.

## Context and Orientation

The repository already exposes a headless API under `src/interfaces/api/app.py`, application services in `src/application`, and infrastructure utilities under `src/infrastructure`. Logging is centralised in `src/infrastructure/logging_config.py` but lacks metrics/tracing and Prometheus export. There is no explicit plugin system; metrics and scenario logic are hard-coded within `src/application/idiot_index_service.py` and `src/application/scenario_planner.py`. Developer automation scripts live in `scripts/`, while quality gates run via `make check`. Documentation spans `README.md`, `docs/ARCHITECTURE_OVERVIEW.md`, and workflow guides. Stage 3 requires layering observability, modular extensions, and automation scaffolds without breaking existing behaviour.

## Plan of Work

1. **Telemetry foundation**
   * Create `src/infrastructure/observability/` package with modules for metrics (counter, histogram, gauge abstractions, registry, exporter), tracing (span context, tracer, correlation ID propagation), and logging helpers that inject trace IDs. Provide Prometheus text exposition and simple OpenTelemetry-compatible span records saved to log-friendly storage.
   * Wire instrumentation into `src/interfaces/api/app.py` by adding middleware that starts/ends traces per request, increments counters, observes latency histograms, and exposes `/metrics` plus enhanced `/health` (aliased `/healthz`). Ensure metrics are thread-safe and optionally disable via config.
   * Update `scripts/run_api.py` to enable telemetry, including CLI flags or env var to toggle metrics endpoint, and ensure WSGI server serves new routes. Extend existing tests (or add new ones) to validate metrics output and correlation IDs.

2. **Extension registry and reference plugin**
   * Define contracts in `src/extensions/` for lifecycle hooks (e.g., `Extension`, `MetricAugmentor`, `ScenarioAdapter`). Provide loader that discovers built-in modules declared in a config file (e.g., `extensions/manifest.json`) and optional env var `IDIOT_INDEX_EXTENSIONS` listing dotted paths.
   * Refactor `IdiotIndexService` to accept an optional `ExtensionManager` that can augment computed summaries (e.g., append plugin insights) and allow `ScenarioPlanner` to consult plugin-provided adjusters. Maintain backward compatibility by defaulting to no-op manager.
   * Implement a sample plugin `src/extensions/builtins/manufacturing_cost_driver.py` that registers a new insight (e.g., calculates average materials share). Ensure plugin contributions are surfaced in API responses and Streamlit components via non-breaking addition (e.g., extend summary notes / metadata field).
   * Provide tests covering extension loading, plugin invocation, and failure isolation (bad plugin should be logged and skipped).

3. **Developer and agent enablement**
   * Add CLI scaffolding under `scripts/` for generating new plugins or service modules (e.g., `scripts/scaffold_extension.py`). Provide cookiecutter-like template using built-in string formatting.
   * Update documentation: new `EXTENSION_GUIDE.md`, refreshed `ARCHITECTURE_OVERVIEW.md` with observability layers and extension seams, new `AGENTS.md` at repo root explaining safe automation usage, and incident response guides in docs.
   * Enhance `CONTRIBUTING.md` with branching model, quality gate command, telemetry expectations, and linking to scaffolding script.

4. **Continuous improvement and future-proofing**
   * Extend `Makefile` with `quality-gate` target running lint, type, tests with coverage threshold (fail if below 90% for critical modules), security scan, metrics validation, and documentation check. Update CI by adding `.github/workflows/ci.yml` orchestrating the same pipeline with caching.
   * Introduce `.github/dependabot.yml` (or Renovate spec) to keep dependencies fresh. Provide script `scripts/bump_version.py` for version increments and changelog entry validation.
   * Update CHANGELOG and RELEASE_NOTES to describe telemetry, extension system, and automation. Ensure TODOs include priority/effort tags.
   * Draft future-proofing notes under `docs/FUTURE_ROADMAP.md` covering scaling, multi-tenant, and migration strategies. Include security checklist and incident response doc.

5. **Validation and wrap-up**
   * Run unit/integration tests plus new coverage enforcement. Capture metrics endpoint sample output and store under `build/observability/` for reference.
   * Update ExecPlan sections (Progress, Decisions, Surprises, Outcomes) to reflect discoveries and final state.

## Concrete Steps

1. Scaffold observability package and middleware, update API + scripts, and add tests validating `/metrics`, `/healthz`, and trace propagation.
2. Implement extension registry, integrate with application services, write reference plugin, and extend API/Streamlit/test coverage.
3. Create developer enablement tooling, AGENTS guidance, and extension documentation updates.
4. Configure quality gate automation, Dependabot, version bump script, and future-proofing docs.
5. Execute validation commands (`make quality-gate`, `pytest`, API smoke via TestClient), collect artefacts, and finalise documentation.

## Validation and Acceptance

* `pytest` passes with >90% coverage enforced by coverage config.
* `make quality-gate` completes successfully (lint, typecheck, tests, security, metrics validation).
* Running `python scripts/run_api.py --once` logs correlation IDs and exposes `/metrics` returning Prometheus text with request counters.
* Invoking `python scripts/scaffold_extension.py --name demo` generates a template extension under `extensions/demo`. Tests confirm plugin contributions appear in API responses (e.g., additional note key `extensions.manufacturing_cost_driver`).

## Idempotence and Recovery

The observability registry, extension loader, and CLI scaffolds must be additive and resilient. Middleware should handle plugin errors by logging and skipping the faulty extension. Configuration-driven loaders should ignore duplicates. Scripts should refuse to overwrite existing directories unless `--force` is specified. Quality gate commands leave build artefacts under `build/` which can be safely deleted with `make clean`.

## Artifacts and Notes

- `make quality-gate` (2025-10-25 04:22Z) – lint, mypy, pytest with coverage ≥90%, and security scans all succeeded.
- `python scripts/check_health.py --pretty` – emitted the aggregated health snapshot matching the `/health` endpoint, exiting
  with status `1` under development warnings.

## Interfaces and Dependencies

* `src/infrastructure/observability.metrics` and `.tracing` expose counters/gauges/histograms and the in-memory tracer consumed by API telemetry.
* `src/infrastructure/observability.health` defines `HealthProbe`, `HealthComponent`, and `HealthReport` used by both the API and CLI.
* `src/interfaces/api/telemetry.ApiTelemetry` now exposes `health_snapshot()` alongside metrics export helpers.
* `src/interfaces/api/app.py` builds the health probe with the shared extension manager to serve `/health` and `/healthz` payloads.
* Tests under `tests/test_api.py` and `tests/test_observability_health.py` validate the API contract and CLI behaviour.

