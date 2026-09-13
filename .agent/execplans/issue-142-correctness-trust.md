# Make showcase results consistent and reproducible

This living ExecPlan follows `.agent/PLANS.md`.

## Purpose / Big Picture

A user can search punctuation safely, trust that visible summaries and exports describe the same rows, identify the actual bundled observation year, switch sources normally, and avoid applying old scenarios to new baselines. The Food Manufacturing example must be calculated from committed inputs.

## Progress

- [x] (2026-09-13) Verified clean primary main, origin Nobodyworld/app-industry-resilience, and remote fix/showcase-correctness-trust at 8fade8d1563c3a4f4d58a483350ba8e3f2ad8b43; created one independent disposable clone on that existing branch.
- [x] Read issue #142 through the GitHub connector after gh returned HTTP 401.
- [x] Implemented service-owned literal filtering, observation-derived sample provenance, initial URL hydration, baseline invalidation, and safe share-value formatting.
- [x] (2026-09-13) Added regressions and regenerated the case study. All 89 focused tests passed using declared dependency versions; original app failed all five source-switch/punctuation reproduction cases.
- [x] (2026-09-13) Completed Make-equivalent quality checks. Runtime and informational full-source runs each passed 508 tests with three real Redis integration skips.
- [x] (2026-09-13) Prepared existing-branch commit/push and draft PR delivery; retain the clone and evidence because ignored-path inventory encountered access denials. Final SHA, PR, and disposition belong in the external delivery report.

## Context and Orientation

`app.py` composes Streamlit controls with `src/application/idiot_index_service.py`. The service returns both full and filtered data and health summaries. `src/interfaces/streamlit/components.py` renders the year control; `helpers.py` holds export and state helpers. `src/application/scenario_planner.py` computes deterministic percentage shocks. Tests live under `tests/`; `docs/INDUSTRY_SHOCK_CASE_STUDY.md` documents NAICS 311.

## Plan of Work

Use the existing service search argument for every dashboard population. Make its string matching literal and null-safe. Derive the sample year from data and constrain the sidebar. Hydrate query parameters once per session. Invalidate scenarios before stopped source transitions and after detecting changed loaded values. Generate a full HTTP(S) URL only from a runtime-provided URL without credentials; otherwise accurately label query parameters. Generate the case-study tables directly from ScenarioPlanner, then assert those tables in a regression.

## Milestones

First establish consistent search and state behavior with service and Streamlit AppTest regressions. Then calculate and document the committed scenario and run the full repository checks. Finally publish only the authorized branch and a draft PR linked to #142.

## Concrete Steps

From the disposable repository root, run `python -m pytest tests/test_application.py tests/test_streamlit_apptest_ui.py tests/test_streamlit_helpers.py tests/test_scenario_planner.py -q`. Run `make quality-gate` if Make is available; otherwise execute its Black, Ruff, mypy, runtime coverage (85 percent minimum), full coverage, benchmark, pip-audit, and detect-secrets commands individually. Run `git diff --check`. Commit using a Conventional Commit and push fix/showcase-correctness-trust; create a draft PR to main.

## Validation and Acceptance

Search each of `[`, `(`, `.`, and `*` without exceptions or wildcard expansion. Search Food and verify one population across table, cards, summaries, and exports. Start a sample deep link with a different year and verify the header, disabled year, URL and provenance all report 2021. Switch Sample to Official to Sample without clearing query parameters. Commit a scenario then change source, requested year, or upload values and verify it is cleared. Preserve initial deep-linked scenario inputs and require Run scenario. Verify generated documentation matches current code and CSV values.

## Surprises & Discoveries

The app filtered after service evaluation and had two independent regex filters. Source hydration assigned the query mode on every rerun. Sample lineage trusted the caller's year. Existing source-switch testing manually cleared URL parameters and missed the defect.

## Decision Log

Use service-filtered frames and summaries together to retain existing metric normalization. Dataset-wide benchmarks remain explicitly labeled. Clear stale scenarios instead of automatically rebinding them. Do not change provider coverage or comparison-population formulas; issues #143 and #144 remain separate. Date: 2026-09-13.

## Outcomes & Retrospective

Implemented all seven correctness behaviors. Food Manufacturing uses gross output 904100 and materials cost 552700, producing ratios 1.6358 baseline and 1.3632 scenario. Black, Ruff, mypy, dependency audit, secret scan, and metric benchmark pass. The first full suite found one historical assertion expecting requested 2023 instead of observed 2021; corrected it while retaining the deliberately different requested year. The corrected full runtime suite passed 508 tests with three real Redis integration skips and 88.08 percent coverage. Informational full-source coverage also passed 508 tests with three skips. Real browser acceptance remains distinct from AppTest coverage. A later pytest run encountered an access-denied shared temporary link during session teardown; the shared path was retained and validation completed with explicitly isolated temporary directories.

## Idempotence and Recovery

Preserve the primary checkout and every pre-existing temporary directory. Reuse the single slice-owned clone. Remove it only after pushed-SHA preservation, ignored/untracked classification, and process-use checks; retain it with an explicit reason if a cleanup proof is unavailable. Never force cleanup.

## Artifacts and Notes

No release, tag, provider, CI, or deployment changes are authorized. Local validation outputs belong under ignored build paths. Do not track machine paths or credentials.

## Interfaces and Dependencies

Keep evaluate_idiot_index(search=...) as the shared filtering entry point. observation_period(frame) returns a single observed year, mixed, or unknown. invalidate_scenario_baseline(state, identity) clears scenario state on identity change. build_share_value(params, runtime_url) returns the serialized value and whether it is absolute. No new runtime dependency is required.

Revision: updated implementation, defect reproduction, and validation findings, 2026-09-13.
