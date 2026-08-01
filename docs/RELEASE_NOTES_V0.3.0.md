# v0.3.0 Public Beta Release Notes

**Status:** Published Public Beta prerelease<br>
**Published:** `2026-08-01T18:42:36Z`<br>
**Starting main SHA:** `185c61379430bd641435681249933d29c90ea469`<br>
**Authorized PR head:** `91f435e3f1af40e17f433e11f4fb151c5971ddb3`<br>
**Merged main / release-code SHA:** `5168f33a784f478f900079ee5db3e76c9637777f`<br>
**Annotated-tag object SHA:** `dcf7b2ca587978d07bb59e0309da3c8044975c9d`<br>
**Peeled tag SHA:** `5168f33a784f478f900079ee5db3e76c9637777f`<br>
**Final protected CI:** Quality Gate #263 — passed<br>
**Final Docker Smoke:** #132 — passed<br>
**Package / Commitizen / fallback version:** `0.3.0` / `0.3.0` / `0.3.0`<br>
**Release tag:** `v0.3.0`<br>
**GitHub release:** [v0.3.0 Public Beta — Industry Pulse](https://github.com/Nobodyworld/app-industry-resilience/releases/tag/v0.3.0)<br>
**Release issue:** [#113](https://github.com/Nobodyworld/app-industry-resilience/issues/113)<br>
**Release pull request:** [#114](https://github.com/Nobodyworld/app-industry-resilience/pull/114)

These notes describe the published `v0.3.0` Public Beta prerelease. PR #114 was squash-merged after exact-head authorization, and the annotated tag, merged `main`, fresh tag clone, and published release were verified to identify the same release-code SHA.

## Highlights

### Industry Pulse monthly context

- Eight officially reviewed whole-industry BLS Producer Price Index mappings with strict duplicate, ambiguity, malformed-code, and undocumented-mapping rejection.
- Exact six-digit mapping, explicit unmapped states, and clearly labeled manual browsing without broader-code or display-label inference.
- Latest observation, month-over-month and year-over-year changes, freshness, units, seasonal status, base date, mapping basis, release period, source, provenance, and limitations.
- A monthly chart with adjacent accessible table and text summaries. Unlike raw PPI series levels are not charted together.
- Industry Pulse remains contextual and does not change annual ratios, rankings, scenarios, composite scores, or bands.

### Offline snapshot and provenance

- A bounded, deterministic, hash-verified committed snapshot covers eight series from 2024-01 through 2026-06 with 240 observations.
- UI and API request handling use the reviewed snapshot without provider network access.
- Snapshot identity, SHA-256, retrieval mode, provider/source URL, registry/schema versions, observation bounds, transformations, and interpretation warnings remain explicit.
- Streamlit browser usage telemetry is disabled in committed configuration and included in the Docker build context.
- The strict remediation acceptance run observed zero external requests, zero Streamlit metrics requests, and zero BLS/provider requests.

### Canonical v1 API and WSGI hardening

- Canonical-only `GET /v1/context/signals` and `GET /v1/context/signals/{industry_code}` routes support bounded industry, series, date, and limit filters with typed mapped, unmapped, empty-range, validation, and unavailable-snapshot states.
- No unversioned context alias or `/v2` route was introduced.
- The WSGI compatibility entry point preserves non-empty query strings without adding an empty trailing delimiter or double-encoding existing query text.
- An unavailable optional snapshot leaves health, OpenAPI, metrics, and existing analytical routes usable while context routes return stable HTTP 503 without private-path leakage.

### Structured exports

- Separate deterministic CSV, JSON, and XLSX Industry Pulse downloads retain mapping, summaries, observations, release period, allowlisted provenance, and limitations without changing annual lineage.
- XLSX contains `Industry Pulse` and `Signal Metadata` sheets.
- Default column widths can clip long headers or metadata until expanded; this is a non-blocking presentation limitation, not a data-loss issue.

## Validation and acceptance

- 408 tests passed.
- Runtime coverage: 87.45% against the 85% gate.
- Full-source informational coverage: 82%.
- Black, Ruff, mypy, metric benchmark, detect-secrets, pip check, pip-audit, and `git diff --check` passed.
- Installed package metadata, source fallback, API `/health`, and OpenAPI all reported `0.3.0`.
- CI / Quality Gate #263 passed on the exact authorized PR head.
- Docker Deployment Smoke #132 passed, including image build, non-root runtime, Streamlit health, API health/metrics, and evidence upload.
- Headed Microsoft Edge acceptance passed under Playwright with a strict loopback-only request policy.
- Mapped, unmapped, manual-browse, comparison, API/WSGI, unavailable-snapshot, export, keyboard, focus, effective-200%-scale, light/dark, and chart-alternative checks passed.
- Screen reader: **NOT RUN**. No screen-reader PASS is claimed.

## Public Beta limitations

- Industry coverage remains limited to the eight reviewed mappings.
- PPI is contextual producer-price information, not profitability, resilience, insolvency, causation, credit, investment, or policy advice.
- Raw index levels from unlike base dates must not be compared directly.
- Long XLSX metadata may require manual column expansion.

## Publication parity

Publication completed successfully:

- annotated tag `v0.3.0` was created at release-code SHA `5168f33a784f478f900079ee5db3e76c9637777f`;
- the tag object is `dcf7b2ca587978d07bb59e0309da3c8044975c9d`;
- the published GitHub release is a prerelease and not a draft;
- a fresh clone of `v0.3.0` resolved to the release-code SHA and passed source-version parity;
- remote `main`, peeled tag, fresh tag clone, and release identity all matched.

## Evidence

- [`docs/execplans/v0.3.0-industry-pulse.md`](execplans/v0.3.0-industry-pulse.md)
- [`docs/execplans/v0.3.0-publication-record.md`](execplans/v0.3.0-publication-record.md)
- [Issue #113](https://github.com/Nobodyworld/app-industry-resilience/issues/113)
- [PR #114](https://github.com/Nobodyworld/app-industry-resilience/pull/114)
- [GitHub release v0.3.0](https://github.com/Nobodyworld/app-industry-resilience/releases/tag/v0.3.0)
