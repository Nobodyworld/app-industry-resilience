```md
# Scenario Modeling and Resilience Analytics Upgrade

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Maintain this document in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

Give decision-makers the ability to stress test industries against shocks and spot fragile cost structures. The upgrade introduces resilience metrics derived from existing BEA/ASM columns, a scenario planner service that lets analysts model cost/output deltas, and a Streamlit panel that visualises the impact. A CLI/prefetch workflow hardens infrastructure, and comprehensive docs/tests ensure the behaviour is verifiable end-to-end.

## Progress

- [x] (2025-02-15 10:00Z) Captured repository context and drafted the initial ExecPlan.
- [x] (2025-02-15 11:15Z) Implemented resilience metric extensions in the core computation pipeline.
- [x] (2025-02-15 12:30Z) Delivered scenario planning service + CLI utilities.
- [x] (2025-02-15 13:10Z) Expanded Streamlit UI with Scenario Lab, visualisations, and download fixes.
- [x] (2025-02-15 13:40Z) Hardened infrastructure (prefetch script, Makefile/Docker integration) and updated docs.
- [x] (2025-02-15 14:05Z) Added/extended automated tests to cover new metrics, scenario flows, helpers, and scripts.
- [x] (2025-02-15 14:10Z) Ran full quality gate (`pytest`) and recorded results for retrospective.

## Surprises & Discoveries

- Observation: Download artefact helper lacked an `io` import, which would break Excel/CSV exports at runtime.
  Evidence: Inspected `src/interfaces/streamlit/helpers.prepare_download_artifacts`; added import alongside resilience metrics work.

- Observation: Computing resilience metrics requires explicit divide-by-zero guards to avoid `inf` leaking into caches.
  Evidence: Added masked denominators in `src/core/metrics.compute_metrics` and confirmed behaviour via new tests.
- Observation: Streamlit shareable URLs needed new query parameters to persist scenario state; naive updates caused recursive reruns.
  Evidence: Added `_store_scenario_param` helper in `app.py` and verified share links load identical slider positions.
- Observation: Pandas cannot initialise `Series(float64)` with `pd.NA`; using `float('nan')` avoids TypeError when computing shock sensitivity.
  Evidence: Unit tests on `compute_metrics` and scenario planner failed until the change in `src/core/metrics.py`.

## Decision Log

- Decision: Define `resilience_score` as value added divided by external inputs, and `shock_sensitivity_index` as the share of external inputs in total cost.
  Rationale: These formulas align with the qualitative goal of spotting industries dependent on external materials while keeping metrics bounded between 0 and 1.
  Date/Author: 2025-02-15 / gpt-5-codex.
- Decision: Gate Docker prefetching behind the `PREFETCH_ARGS` environment variable to avoid mandatory network calls.
  Rationale: Keeps offline builds functional while still enabling cache warm-up in managed environments.
  Date/Author: 2025-02-15 / gpt-5-codex.

## Outcomes & Retrospective

- Resilience metrics now include resilience score, materials dependency, and shock sensitivity, with safeguards for zero denominators and cached reuse.
- The Scenario Planner service, CLI, and Streamlit Scenario Lab enable percentage-based shocks with shareable URLs, comparison tables, and delta charts.
- Infrastructure additions (scenario Make target, cache prefetch script, Docker `PREFETCH_ARGS`) and documentation updates (`README.md`, `ARCHITECTURE.md`, `docs/SCENARIO_LAB.md`) round out automation guidance.
- Automated tests cover metric computations, scenario planner logic, CLI utilities, and UI helpers; `pytest` passes end-to-end.

## Context and Orientation

The Streamlit entry point (`app.py`) orchestrates configuration bootstrap, dataset acquisition via `src/application.idiot_index_service`, and rendering through helpers in `src/interfaces/streamlit/`. Core metric computation lives in `src/core/metrics.py`, with normalisation (`src/core/normalize.py`) and security checks gating inputs. Cached sample data ships in `data/sample_industries.csv`. Tests mirror this structure under `tests/`. Scripts in `scripts/` power tooling invoked by the Makefile, while Docker builds the Streamlit app for deployment.

Scenario modelling will reuse idiomatic layers: core computations remain in `src/core`, orchestration in `src/application`, and presentation in `src/interfaces/streamlit`. Infrastructure upgrades (prefetch CLI, Docker wiring) live under `scripts/`, `Makefile`, and `Dockerfile`. Documentation updates touch `README.md` and potentially `docs/` (architecture appendix for scenario usage).

## Plan of Work

1. **Resilience Metrics Foundation**
   Elaborate `src/core/metrics.compute_metrics` to derive new columns (`resilience_score`, `materials_dependency_ratio`, `shock_sensitivity_index`) from existing numeric inputs, guarding against divide-by-zero and NaN propagation. Extend `format_for_display` to coerce the new columns. Update any downstream helpers (e.g., `build_comparison_table`, `calculate_benchmark`) to surface these metrics. Fix the missing `io` import in `src/interfaces/streamlit/helpers.prepare_download_artifacts` uncovered during review.

2. **Scenario Planning Service & CLI**
   Introduce `src/application/scenario_planner.py` defining dataclasses for `ScenarioAdjustment` and `ScenarioResult`, plus a `ScenarioPlanner` service that clones baseline dataframes, applies percentage adjustments to raw columns, recomputes metrics via the core pipeline, and returns delta summaries (per-industry + aggregate). Provide utility methods for deriving deltas and resilience score changes. Add a CLI entry (`scripts/run_scenario.py`) that loads sample/BEA/CSV data, applies adjustments from JSON/YAML or CLI flags, and emits a report (stdout + optional file). Wire this CLI into `Makefile` (e.g., `make scenario`) for convenience.

3. **Streamlit Scenario Experience**
   Extend `app.py` to offer a “Scenario Lab” section: controls to select industries, adjust sliders for gross output/materials/value added deltas, and render updated tables/charts. Build supporting helpers in `src/interfaces/streamlit/components.py` (e.g., `render_scenario_controls`, `render_scenario_results`) and `helpers.py` (e.g., `summarise_scenario_deltas`). Display resilience metrics with delta indicators, incorporate a Plotly chart comparing baseline vs scenario, and surface download buttons (leveraging the fixed helper). Ensure shareable URLs capture scenario state where feasible without breaking existing encoding.

4. **Infrastructure Hardening**
   Create a cache prefetch script (e.g., `scripts/prefetch_data.py`) leveraging `ScenarioPlanner` or `IdiotIndexService` to warm caches for configured years/sources. Optionally expose environment-driven concurrency using thread pools. Update `Dockerfile` and `Makefile` to include optional prefetch and CLI steps, documenting usage. Add logging instrumentation (leveraging existing `logging_config`) in new scripts.

5. **Documentation & Tests**
   Update `README.md`, `ARCHITECTURE.md`, and add a focused doc (`docs/SCENARIO_LAB.md`) explaining the scenario workflow, CLI usage, and resilience metrics definitions. Expand tests: unit tests for new metrics, scenario planner adjustments (including multi-industry, multi-adjustment cases), Streamlit helpers (pure functions), CLI invocation (via `subprocess` or direct function), and infrastructure scripts (prefetch logic). Ensure sample dataset includes values enabling realistic assertions.

6. **Validation & Retrospective**
   Run `pytest` (and any targeted linting if new modules demand it), capture results, and update this plan’s progress, discoveries, decisions, and retrospective entries summarising outcomes and future follow-ups.

## Concrete Steps

- Modify `src/core/metrics.py` and related helpers to emit new resilience metrics.
- Implement `src/application/scenario_planner.py` with adjustment logic and export dataclasses.
- Add CLI utilities under `scripts/` (scenario runner, cache prefetch) and register them in the Makefile.
- Expand Streamlit UI (`app.py`, `src/interfaces/streamlit/components.py`, `helpers.py`) to support scenario controls/results and fix download helper imports.
- Write/extend tests under `tests/` for metrics, scenario planner, helpers, and CLIs.
- Document the new behaviour in `README.md` and author `docs/SCENARIO_LAB.md`.
- Execute `pytest` from repository root; note outputs in this plan and final summary.

## Validation and Acceptance

Success criteria:
- Running the Streamlit app exposes the Scenario Lab with adjustable sliders, updated tables/charts, and resilience metrics deltas.
- `scripts/run_scenario.py --help` documents usage; running a sample scenario outputs a structured summary without errors.
- Cache prefetch script executes without network when using sample data, respecting logging configuration.
- `pytest` passes with coverage for scenario planner, metrics, and helper additions.
- Documentation clearly instructs users to run scenarios via UI and CLI.

## Idempotence and Recovery

Scenario adjustments operate on dataframe copies so repeated runs are safe. CLI scripts accept output paths to avoid overwriting unless explicitly requested. Prefetch script skips already cached entries (leverage cache TTL) and logs summaries. Streamlit state resets when clearing sliders/query params.

## Artifacts and Notes

Capture sample CLI output, scenario delta tables, and any notable log entries in tests/docs as indented blocks. Ensure new docs link back to existing READMEs for discoverability.

## Interfaces and Dependencies

- New module `src/application/scenario_planner.py` exporting:
    - `ScenarioAdjustment`, `ScenarioPlanner`, `ScenarioResult`, `ScenarioDelta` dataclasses.
    - `plan_scenario(base: pd.DataFrame, adjustments: Sequence[ScenarioAdjustment], *, config: AppConfig | None = None) -> ScenarioResult` convenience function.
- Streamlit components expose `render_scenario_controls(...)` and `render_scenario_results(...)` used by `app.py`.
- CLI entrypoints installed via `scripts/run_scenario.py` and `scripts/prefetch_data.py` (import-safe, no heavy deps beyond standard library + pandas).
- No new external dependencies beyond optional `pyyaml` (if required) — prefer JSON/INI to avoid new packages unless absolutely necessary.
```
