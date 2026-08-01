# v0.3.0 Public Beta Release Candidate Notes

**Status:** Final candidate; merge and publication pending<br>
**Candidate branch:** `feature/industry-pulse-context`<br>
**Starting main SHA:** `185c61379430bd641435681249933d29c90ea469`<br>
**Accepted implementation/evidence SHA:** `a1c270e27752c15eee7445ca85c34375ecfd9f50`<br>
**Candidate code SHA:** `95a47ec8b99df01cf666e15d78942f99e6c7edda`<br>
**Pre-version protected CI:** Quality Gate #262 — passed<br>
**Pre-version Docker Smoke:** #131 — passed<br>
**Final-version protected checks:** pending after the candidate commits are pushed<br>
**Package / Commitizen / fallback version:** `0.3.0` / `0.3.0` / `0.3.0`<br>
**Target tag:** `v0.3.0` — not created<br>
**Release issue:** [#113](https://github.com/Nobodyworld/app-industry-resilience/issues/113)<br>
**Draft pull request:** [#114](https://github.com/Nobodyworld/app-industry-resilience/pull/114) — unmerged

These notes describe the final `v0.3.0` Public Beta candidate. The release owner accepted the
Industry Pulse implementation and Windows/Microsoft Edge evidence as GO for candidate preparation.
They do not claim a merged-main SHA, tag, GitHub release, publication smoke, or parity result.

## Highlights

### Industry Pulse monthly context

- Eight officially reviewed whole-industry BLS Producer Price Index mappings with strict duplicate,
  ambiguity, malformed-code, and undocumented-mapping rejection.
- Exact six-digit mapping, explicit unmapped states, and clearly labeled manual browsing without
  broader-code or display-label inference.
- Latest observation, month-over-month and year-over-year changes, freshness, units, seasonal
  status, base date, mapping basis, release period, source, provenance, and limitations.
- A monthly chart with adjacent accessible table and text summaries. Unlike raw PPI series levels
  are not charted together.
- Industry Pulse remains contextual and does not change annual ratios, rankings, scenarios,
  composite scores, or bands.

### Offline snapshot and provenance

- A bounded, deterministic, hash-verified committed snapshot covers eight series from 2024-01
  through 2026-06 with 240 observations.
- UI and API request handling use the reviewed snapshot without provider network access.
- Snapshot identity, SHA-256, retrieval mode, provider/source URL, registry/schema versions,
  observation bounds, transformations, and interpretation warnings remain explicit.
- Streamlit browser usage telemetry is disabled in committed configuration and included in the
  Docker build context. The strict remediation rerun observed zero external requests, zero
  Streamlit metrics requests, and zero BLS/provider requests.

### Canonical v1 API and WSGI hardening

- Canonical-only `GET /v1/context/signals` and
  `GET /v1/context/signals/{industry_code}` routes support bounded industry, series, date, and limit
  filters with typed mapped, unmapped, empty-range, validation, and unavailable-snapshot states.
- No unversioned context alias or `/v2` route is introduced.
- The WSGI compatibility entry point preserves non-empty query strings without adding an empty
  trailing delimiter or double-encoding existing query text.
- An unavailable optional snapshot leaves health, OpenAPI, metrics, and existing analytical routes
  usable while context routes return a stable HTTP 503 without private-path leakage.

### Structured exports

- Separate deterministic CSV, JSON, and XLSX Industry Pulse downloads retain mapping, summaries,
  observations, release period, allowlisted provenance, and limitations without changing annual
  lineage.
- XLSX contains `Industry Pulse` and `Signal Metadata` sheets. Default column widths can clip long
  headers or metadata until expanded; this is a non-blocking presentation limitation, not a data
  loss issue.

## Acceptance and limitations

- Accepted on Windows 11 build `26200` using installed Microsoft Edge `150.0.4078.105` in headed
  mode under Playwright `1.62.0` with `channel="msedge"`, a fresh process, isolated contexts, and a
  strict loopback-only request policy.
- Mapped, unmapped, manual-browse, comparison, API/WSGI, unavailable-snapshot, export, keyboard,
  focus, effective-200%-scale, light/dark, and chart-alternative checks passed.
- Screen reader: **NOT RUN**. No screen-reader PASS is claimed.
- Industry coverage remains limited to the eight reviewed mappings. PPI is contextual producer-price
  information, not profitability, resilience, insolvency, causation, or investment advice.

## Validation and publication gates

Quality Gate #262 and Docker Deployment Smoke #131 support the accepted pre-version evidence head
`a1c270e27752c15eee7445ca85c34375ecfd9f50`. Fresh protected CI and Docker Smoke are still required
on the exact final-version evidence head after it is pushed.

Local validation of candidate code SHA `95a47ec8b99df01cf666e15d78942f99e6c7edda` passed:

- focused release-version, telemetry-config, Industry Pulse API, and WSGI regressions: 12 passed;
- complete suite: 408 passed;
- CI-equivalent runtime coverage: 87.45% against the 85% threshold;
- full-source informational coverage: 82%;
- Black, Ruff, mypy, metric benchmark, detect-secrets baseline, pip check, pip-audit, and
  `git diff --check`: passed. Pip-audit reported no known vulnerabilities and skipped only the
  unpublished local `industry-resilience-dashboard==0.3.0` distribution because it is not on PyPI;
- force-reinstalled package metadata and `src.version` both reported `0.3.0`;
- live API `/health` and `/openapi.json` both reported version `0.3.0`;
- Streamlit returned HTTP 200, rendered the five-tab dashboard and selected Industry Pulse without
  a rendered exception, external resource entry, console warning, or console error; effective
  `browser.gatherUsageStats = false` remained in force.

The local Docker CLI was unavailable, so local Docker smoke was not run. The fresh hosted Docker
Smoke on the final pushed evidence head remains authoritative and is pending alongside protected CI.

Publication remains pending: exact-head review and authorization, merge of draft PR #114, creation
of annotated tag `v0.3.0`, GitHub Public Beta prerelease publication, published-state smoke testing,
and tag/release SHA-parity verification. The currently published prior release remains `v0.2.0`.

## Evidence

- [`docs/execplans/v0.3.0-industry-pulse.md`](execplans/v0.3.0-industry-pulse.md)
- [Issue #113](https://github.com/Nobodyworld/app-industry-resilience/issues/113)
- [Draft PR #114](https://github.com/Nobodyworld/app-industry-resilience/pull/114)
