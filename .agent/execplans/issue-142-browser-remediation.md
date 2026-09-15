# Make public diagnostics safe and resolve browser acceptance findings

This living ExecPlan follows `.agent/PLANS.md`. It continues issue #142 and draft PR #145 from `36f02b24cebe2a4bc0efefa37c9157a49e45d562` on `fix/showcase-correctness-trust`.

## Purpose / Big Picture

Anonymous users must see useful diagnostic status without seeing operator filesystem locations, infrastructure coordinates or raw errors. A search with no results must show an intentional empty mean ratio. Every current download must work; stale resource requests must be distinguished from a broken visible download before changing the implementation.

## Progress

- [x] (2026-09-15) Verified the required local and remote head and draft state, inventoried protected workspaces, and created one disposable independent clone and one external evidence directory.
- [x] (2026-09-15) Added explicit public configuration and snapshot projections, removed free-text operator details from public error messages, and replaced missing mean ratios with an em dash.
- [x] (2026-09-15) Passed 113 focused tests and the Make-equivalent quality gate: 538 passed / three real Redis skips, 88.01 percent runtime coverage, informational full-source coverage, Black, Ruff, mypy, benchmark, dependency audit and secret scan.
- [ ] Isolate Sample and upload/replacement downloads in headed Edge and the in-app Chromium browser, including console and request status evidence.
- [ ] Commit and push only this remediation, wait for both hosted gates on the exact head, and repeat privacy/error acceptance. Post evidence to PR #145 while retaining draft state.
- [ ] Reconcile the owned clone, processes and external artifacts, preserving evidence and every pre-existing workspace.

## Context and Orientation

`app.py` renders configuration in sidebar Technical diagnostics and calls `render_observability_snapshots()` in `src/interfaces/streamlit/components.py` for the main diagnostic expander. Previously the configuration summary included paths, service coordinates and arbitrary mappings; snapshot rendering forwarded labels, destinations and raw errors. `src/interfaces/streamlit/diagnostics.py` is the public presentation boundary. Internal configuration and snapshot loaders remain unchanged. `render_signal_bar()` formats the mean ratio and must handle pandas missing values.

## Plan of Work

Build configuration diagnostics by explicitly naming scalar fields and nested numeric fields. Do not serialise internal configuration mappings. For observability, accept only parsed timestamps, nonnegative finite counts, fixed replication status labels and an error-present boolean before rendering any table, chart or message. Discard labels, snapshot identifiers, arbitrary metric names, destinations and error payloads. Never interpolate bootstrap error or warning text in public diagnostic messages.

Use Streamlit AppTest, which runs the application and exposes its rendered elements, to inspect text, JSON, metrics, tables and chart specifications with private sentinels. Extend existing punctuation searches to require an em dash and no `nan` badge. Browser automation must use visible tabs and real download/upload controls, with distinct evidence for Sample idle, each Sample download, each uploaded-data download, and each replacement-data download after rerender settles.

## Concrete Steps

From the disposable clone, run `python -m pytest tests/test_streamlit_diagnostics.py tests/test_streamlit_apptest_ui.py tests/test_streamlit_components.py tests/test_streamlit_helpers.py tests/test_application.py tests/test_scenario_planner.py -q`. Run `make quality-gate`, or its individual commands when Make is unavailable: Black check, Ruff, mypy, runtime pytest coverage at 85 percent, informational full-source coverage, metric benchmark, pip-audit and detect-secrets with the unchanged reviewed baseline. Store logs and browser artifacts outside tracked source.

Start Streamlit from this clone on an unused loopback port with external cache/snapshot storage and no provider credentials. Record the served commit, installed versions and browser user agents. First load Sample without interactions. Then click each annual CSV, lineage JSON, JSON and XLSX control individually. Upload a local synthetic CSV, click every generated download, replace it with changed data, wait for settled output, and repeat downloads. Record actual download events, resource status and console entries after every stage. Investigate current failures before changing any download code.

## Validation and Acceptance

The rendered diagnostic protobufs must contain none of the sentinel identifiers, even when injected into unexpected snapshot fields or free-text version/status values. Safe counts and fixed failure notices remain visible. Zero-match searches show an em dash. Existing issue #142 regression behavior remains intact. Both hosted CI Quality Gate and Docker Deployment Smoke must pass on the pushed head; subsequent headed privacy and error results must identify that exact SHA. A current failed download requires a demonstrated fix and regression; stale requests with successful current downloads require a documented non-user-facing disposition.

## Surprises & Discoveries

The empty observability message also interpolated its storage directory. Snapshot metadata labels and table identifiers were additional leak paths beyond replication destination and raw last_error. All public snapshot output must therefore consume the projection, including Plotly data and Arrow tables. Fourteen targeted regressions fail against the original app/components: configuration and snapshot sentinels leak, malformed timestamps render exceptions, and all four punctuation searches show a missing-value badge. They pass after the remediation.

Missing snapshot counts require a consistent numeric type before Plotly wide-form charting. Windows validation requires task-local temporary and tool-cache directories, including an explicit pip-audit cache directory. Browser download-event waits were delayed by native file-save dialogs; file completion must be observed separately from successful HTTP responses.

## Decision Log

Keep `get_config_summary()` and stored snapshot summaries available to operators. Add a dedicated presentation module instead of a denylist that could miss future fields. Numeric BEA versions can be shown; arbitrary version strings fall back to a fixed label. These choices keep the public output stable as internal configuration grows. Date: 2026-09-15.

## Outcomes & Retrospective

The public projection and empty-state regressions pass. Runtime coverage remains above the unchanged 85 percent threshold. The dependency audit resolved 101 dependencies with zero known vulnerabilities; the reviewed secret baseline is unchanged. Initial Sample browser loads and CSV responses are HTTP 200 with no console errors. Browser download/upload completion, hosted checks and reconciliation remain pending; their final exact-head record belongs in PR #145. No change to download behavior is justified yet. Issues #143 and #144, deployment and release work remain outside this slice.

## Idempotence and Recovery

Preserve the primary checkout and every pre-existing temporary path. Reuse the one owned clone and evidence directory. Before removal, stop task-created processes, inventory ignored/untracked content, verify exact pushed-head preservation and ownership, and use normal exact-path removal only when all reconciliation proofs pass. Retain any unexplained or inaccessible path and report its reason.

## Artifacts and Notes

The external workspace inventory records owned and protected paths without introducing machine locations into tracked documentation. Final PR evidence must name the exact SHA, browser versions, individual gate results and limitations. PR #145 stays draft and unmerged.

## Interfaces and Dependencies

`build_public_diagnostics(config)` returns an explicit JSON-compatible public mapping. `build_public_snapshot_history(history)` returns timestamp/count/status-only rows consumed by the renderer. No new runtime dependency or internal configuration contract is needed.

Revision: created the bounded browser remediation plan and recorded the public-output boundary, 2026-09-15.
