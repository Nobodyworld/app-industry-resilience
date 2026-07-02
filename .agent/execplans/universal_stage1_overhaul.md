# Stage 1 – Universal product hardening and analytics expansion

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

Deliver a production-ready upgrade that touches every layer of the Idiot Index platform. The finished work introduces a quantitative health score across industries, exposes the analytics through the API and Streamlit UI, modernises infrastructure (Docker, Makefile automation, dependency pins), patches latent reliability bugs (cache JSON import, stricter validation), and documents the refined architecture so future agents or humans can extend it confidently. Users will be able to open the dashboard, see new health insights, call an API endpoint to fetch them programmatically, and trust the hardened deployment workflow.

## Progress

- [x] (2025-10-25 20:59Z) Created Stage 1 ExecPlan after initial repository survey.
- [x] (2025-10-25 22:05Z) Backend analytics module implements health scoring, cohort aggregation, and integrates with scenario planner metrics.
- [x] (2025-10-25 22:20Z) API exposes `/analytics/health` endpoint with validation + telemetry hooks.
- [x] (2025-10-25 22:30Z) Streamlit UI surfaces new health score insights (sidebar summary + tab) and respects scenario deltas.
- [x] (2025-10-25 22:40Z) Infrastructure updated (Docker multi-stage, Makefile analytics target, dependency bumps, cache bug fix) with regression tests.
- [x] (2025-10-25 23:20Z) Documentation + reports refreshed (README, ARCHITECTURE, docs/analytics.md, REPORTS/003_STAGE1_OUTCOME.md) capturing design choices and validation evidence.
- [x] (2025-10-25 23:25Z) Quality gate executed and recorded; PR message prepared per instructions.

## Surprises & Discoveries

- Observation: Sample dataset contains a single year but the sector health summary remains meaningful because cohorts are derived from code prefixes rather than longitudinal trends.
  Evidence: Manual inspection of `build_health_sector_table` outputs during Streamlit smoke test showed balanced sector aggregates despite limited temporal data.

## Decision Log

- Decision: Relax dependency pins to compatible ranges instead of exact versions.
  Rationale: Enables environments to adopt the latest compatible releases without editing the repository each time; tracked cadence in `docs/DEPENDENCIES.md`.
  Date/Author: 2025-10-25 / gpt-5-codex

## Outcomes & Retrospective

- Quality gate passes confirm analytics integration is stable across formatting, lint, type checks, and the 103-test suite; security scans noted missing local tooling (`pip-audit`, `detect-secrets`) for follow-up installation.
- Stage 1 reports and documentation updates now align with the delivered analytics features, ensuring future agents can trace validation evidence and architectural decisions.

## Context and Orientation

The Idiot Index application combines a Streamlit UI (`app.py` + `src/interfaces/streamlit/*`) with reusable domain code inside `src/core/` and orchestration services in `src/application/`. A FastAPI-compatible headless API lives under `src/interfaces/api/`, with observability utilities in `src/infrastructure/`. Tests span `tests/`. Dependencies are pinned via `requirements*.txt` and pyproject settings. Existing metrics focus on Idiot Index and resilience values but lack a composite health score or API exposure beyond evaluation/scenario endpoints. The Dockerfile is a single-stage build and `src/core/cache.py` omits a `json` import, risking runtime errors. Documentation references previous adaptive upgrades but omits the forthcoming analytics work.

## Plan of Work

Narrative roadmap for implementing Stage 1:

1. **Foundation & bug fixes.** Patch the missing `json` import in `src/core/cache.py`, reinforce cache typing, and add guardrails for invalid TTL/paths. Update unit tests in `tests/test_core.py` or add new cache-focused tests.
2. **Analytics domain module.** Create `src/core/analytics.py` encapsulating health score computation, cohort aggregation (overall + group by NAICS 2-digit prefix), and risk band classification. Provide configuration dataclasses for weights/thresholds and ensure compatibility with pandas dataframes produced by `compute_metrics`.
3. **Service integration.** Extend `src/application/idiot_index_service.py` and `ScenarioPlanner` to optionally attach analytics summaries (baseline + scenario). Ensure extension manager hooks receive analytics metadata.
4. **API exposure.** Implement a new schema (`HealthAnalyticsRequest/Response`) in `src/interfaces/api/schemas.py`, register `/analytics/health` route in `src/interfaces/api/app.py`, and wire dependencies in `src/interfaces/api/dependencies.py`. Validate payloads, apply telemetry spans, and reuse caching where appropriate.
5. **Streamlit UI enhancements.** Add helpers in `src/interfaces/streamlit/helpers.py` for health summary tables and risk band formatting. Update `src/interfaces/streamlit/components.py` (and potentially new component) plus `app.py` to render a health insights tab, include scenario-aware deltas, and display aggregated health badges in the signal bar/sidebar.
6. **Infrastructure polish.** Convert the Dockerfile to a multi-stage build with deterministic wheels layer, install OS deps minimally, and enforce non-root runtime. Update the Makefile with a `analytics` or `health` target to run a CLI smoke test (implemented under `scripts/analytics_health.py`). Refresh dependency pins in `requirements.txt` and `requirements-dev.txt` to the latest compatible releases, documenting rationale in `docs/DEPENDENCIES.md` (or new section) if versions constrained by Streamlit.
7. **Documentation & reports.** Update README highlights, extend `ARCHITECTURE.md` with analytics module description, create `docs/ANALYTICS_HEALTH.md` explaining formulas + API usage, and append Stage 1 summary to REPORTS (new `REPORTS/003_STAGE1_OUTCOME.md`). Update CHANGELOG/RELEASE_NOTES as needed.
8. **Testing & validation.** Add targeted tests for analytics computations (`tests/test_analytics.py`), API endpoint, and UI helper transformations. Ensure `make quality-gate` passes and capture output for the verification report. Optionally run `streamlit run app.py` headless to confirm no runtime regressions.
9. **Finalisation.** Review ExecPlan sections, record surprises/decisions, stage files, commit with conforming message, and invoke `make_pr` with summary referencing analytics expansion.

## Concrete Steps

Detailed commands and checkpoints (repository root `/workspace/app-industry-resilience`):

1. Patch foundational bug and scaffolding:
       sed -n '1,120p' src/core/cache.py  # verify context
       apply fix + add tests
2. Add `src/core/analytics.py` and supporting types:
       mkdir -p src/core
       touch new module, export from `src/core/__init__.py`
3. Update application/services and scenario planner; adjust imports and dataclasses.
4. Modify API schemas & endpoints, update telemetry wiring, and extend tests (`tests/test_api.py`).
5. Enhance Streamlit helpers/components/app to surface analytics UI features; update sample data usage if needed.
6. Create CLI script under `scripts/analytics_health.py` for automation; update Makefile target.
7. Upgrade Dockerfile, requirements, docs, and architecture notes.
8. Write new tests: `tests/test_analytics.py`, extend existing ones.
9. Run formatters and full quality gate:
       make format
       make lint
       make typecheck
       make quality-gate
10. Record command outputs in `REPORTS/003_STAGE1_OUTCOME.md`, update ExecPlan progress/sections.
11. Stage, commit (after verifying clean status), call `make_pr` with summary referencing analytics/infra upgrades.

## Validation and Acceptance

Success criteria:

- `make quality-gate` passes with coverage threshold intact (capture output for reports).
- New analytics tests confirm health score math, risk banding, and scenario integration.
- `/analytics/health` endpoint returns expected JSON using pytest client tests.
- Streamlit UI renders new health insights without raising exceptions in smoke test (`streamlit run app.py --server.headless true --server.port 0` with sample data).
- Documentation updates clearly describe analytics module, API usage, and deployment adjustments.

## Idempotence and Recovery

The plan emphasises additive, deterministic edits. All scripts and Make targets can run repeatedly without side effects. Docker build remains reproducible after multi-stage conversion. If dependency upgrades fail locally, fallback is to pin to latest compatible minor versions and document constraints. Git history enables rollback; ensure working tree clean before commits.

## Artifacts and Notes

Expected artifacts:

- `src/core/analytics.py` with typed dataclasses and functions.
- Updated `src/application/idiot_index_service.py`, `src/application/scenario_planner.py`, API modules, Streamlit components/helpers, and CLI script.
- Tests: `tests/test_analytics.py` plus updates to API/UI test suites.
- Infrastructure: refined Dockerfile, Makefile, requirements, docs (README, ARCHITECTURE, docs/ANALYTICS_HEALTH.md), `REPORTS/003_STAGE1_OUTCOME.md` summarising validation.
- ExecPlan updates capturing surprises, decisions, retrospective at completion.

## Interfaces and Dependencies

Define/extend interfaces:

- In `src/core/analytics.py`, define:
        @dataclass(frozen=True)
        class HealthScoreConfig: ...
        def compute_health_scores(df: pd.DataFrame, config: HealthScoreConfig) -> pd.DataFrame: ...
        def summarise_health(df: pd.DataFrame, *, group_by: Literal["overall", "sector"] = "overall") -> HealthSummary: ...

- Export analytics helpers via `src/core/__init__.py` for broader consumption.
- Extend `IdiotIndexSummary` to include `health_summary` metadata (typed tuple) and adjust API schemas accordingly.
- New FastAPI schema classes `HealthAnalyticsRequest`, `HealthAnalyticsResponse`, `HealthAggregate`. Provide translation helpers between dataclasses and JSON.
- CLI script should accept options (e.g., `--input data/sample_industries.csv --group-by sector`) and print JSON summary.
- Requirements updated to latest stable versions for pandas, streamlit, plotly, etc., ensuring compatibility with Python 3.11.

