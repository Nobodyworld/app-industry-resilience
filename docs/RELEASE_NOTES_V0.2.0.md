# v0.2.0 Public Beta Release Notes

**Status:** Release candidate draft  
**Candidate package version:** `0.2.0rc1`  
**Final intended version/tag:** `0.2.0` / `v0.2.0`  
**Release issue:** [#107](https://github.com/Nobodyworld/app-industry-resilience/issues/107)

These notes describe the intended `v0.2.0` Public Beta release. Publication remains blocked until protected automated validation and the recorded Windows/Edge manual acceptance pass are complete.

## Highlights

### Stable v1 consumer boundary

- Canonical `/v1` routes for evaluation, scenarios, health analytics, sources, connectors, and public-data readiness metadata.
- Deprecated unversioned aliases retain migration headers and compatibility tests where a legacy contract exists.
- No `/v2` contract is introduced.

### End-to-end typed provenance

- Typed lineage for bundled sample data, official snapshots, live providers, inline API records, uploaded files, cache retrieval, evaluation, scenarios, and exports.
- Original source identity, observation period, timestamps, cache state, calculation version, and ordered transformations remain visible across supported workflows.
- Privacy guardrails exclude credentials, uploaded filenames, private paths, cache keys, Redis details, raw provider payloads, and arbitrary dataframe attributes.

### Dashboard provenance and upload privacy

- The Streamlit **Data provenance** panel exposes the typed, allowlisted lineage envelope and transformation history.
- Validated CSV uploads use the generic `user-upload` identity rather than bundled-sample provenance.
- Single-year, mixed-year, and unknown-period upload states are represented without retaining filenames.

### Structured exports

- JSON exports contain top-level `lineage` and `records` fields.
- XLSX exports contain `Cost Structure` and `Lineage` sheets.
- CSV remains tabular and is accompanied by full/current-view `.lineage.json` artifacts.
- Export serialization appends a bounded transformation step without mutating in-memory lineage.

### Truthful public-data readiness catalog

- Typed canonical-only `GET /v1/meta/public-data` metadata distinguishes implemented, readiness-complete, roadmap, and contextual sources.
- Census AIES and BLS PPI are identified as implemented no-auth readiness paths.
- Credentialed Census ASM remains available through the existing adapter/connector surfaces but is excluded from the no-auth catalog.
- GDELT remains explicitly contextual and not economic ground truth.

### Public-beta quality and operations

- Protected hosted quality gate with Black, Ruff, mypy, tests, runtime/full coverage, benchmarks, dependency audit, and secret scanning.
- Production Docker smoke checks image construction, non-root runtime, Streamlit health, and API health.
- First-run sample workflow, clearer source controls, table alternatives, and documented accessibility limitations.

## Methodology and product limitations

This remains a **Public Beta analytical demonstration**.

- The informal output-to-cost ratio is not a credit model, insolvency predictor, or causal forecast.
- Census AIES uses a revenue-to-operating-expense proxy and is not identical to the BEA gross-output-to-intermediate-inputs ratio.
- Composite indicators are experimental and algebraically related; they do not independently establish industry health, resilience, or distress.
- Event/context feeds must not be treated as official economic ground truth.
- Manual keyboard, focus, screen-reader, 200% zoom, and light/dark rendered-browser acceptance must be recorded before publication.

## Upgrade notes from 0.1.0

- Prefer canonical `/v1` API routes for consumer integrations.
- Treat unversioned consumer aliases as deprecated compatibility surfaces.
- Consume typed `lineage` fields rather than parsing unrestricted metadata for provenance.
- Expect JSON and XLSX exports to include explicit lineage structures and CSV downloads to have companion lineage artifacts.
- Use `/v1/meta/public-data` to distinguish implemented readiness paths from roadmap catalog entries.

## Validation evidence

Exact automated and manual results will be recorded in:

- [`docs/execplans/v0.2.0-public-beta-release-candidate.md`](execplans/v0.2.0-public-beta-release-candidate.md)
- [issue #107](https://github.com/Nobodyworld/app-industry-resilience/issues/107)
- the final release pull request and protected workflow runs

The final release notes must name the exact merged `main` SHA, CI run, Docker Smoke run, annotated tag, and GitHub release URL before publication is considered complete.
