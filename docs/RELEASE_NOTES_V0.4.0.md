# v0.4.0 Public Beta Release Notes

**Status:** Published GitHub prerelease / Public Beta<br>
**Published:** `2026-08-27T17:21:40Z`<br>
**Release-code SHA:** `eec9886c5f0a4ef495b6b31c3c2cc6cdc52e631a`<br>
**Release-preparation final head:** `0dd726446f2c4d9ce29acb415d6b3461c1dfdfc4`<br>
**Annotated-tag object:** `d1b777b192c97aaefe167be0018a1890250a55fe`<br>
**Peeled tag commit:** `eec9886c5f0a4ef495b6b31c3c2cc6cdc52e631a`<br>
**GitHub release ID:** `378000330`<br>
**GitHub release:** [v0.4.0 Public Beta — Industry Momentum](https://github.com/Nobodyworld/app-industry-resilience/releases/tag/v0.4.0)<br>
**Package / Commitizen / fallback version:** `0.4.0` / `0.4.0` / `0.4.0`<br>
**Release issue:** [#129](https://github.com/Nobodyworld/app-industry-resilience/issues/129)<br>
**Implementation pull request:** [#130](https://github.com/Nobodyworld/app-industry-resilience/pull/130)<br>
**Release pull request:** [#132](https://github.com/Nobodyworld/app-industry-resilience/pull/132)<br>
**Publication bookkeeping pull request:** [#133](https://github.com/Nobodyworld/app-industry-resilience/pull/133)

These notes are the durable repository record for the published `v0.4.0 Public Beta — Industry Momentum` GitHub prerelease. The release preserves the established boundary: monthly PPI, CES, and Federal Reserve G.17 observations are contextual and do not alter annual analytics.

## Highlights

### Multi-source Industry Momentum

- Expands the released BLS Producer Price Index Industry Pulse into a 38-series contextual registry:
  - eight reviewed BLS PPI producer-price series;
  - eight reviewed BLS CES employment series;
  - eight Federal Reserve G.17 industrial-production series;
  - seven Federal Reserve G.17 capacity-index series;
  - seven Federal Reserve G.17 capacity-utilization series.
- Preserves explicit exact versus broader-published mapping relationships. A broader official provider scope is never represented as an exact six-digit annual-industry match.
- Keeps producer prices, employment counts, production indexes, capacity indexes, and utilization percentages distinct. Unlike units and indexes with different base periods are not compared as equivalent levels.
- Calculates changes only from exact calendar periods:
  - percent change for indexes and employment counts;
  - percentage-point change for capacity-utilization rates.
- Uses source-family-specific freshness contracts: the released PPI 90-day behavior remains intact, while CES and G.17 use explicit 120-day thresholds.
- Provides explicit `available`, `partial`, `unmapped`, `empty_range`, and `unavailable` states with independently degrading source families.

### Offline snapshots and reproducible public-data workflows

- Adds bounded deterministic committed snapshots for BLS CES and Federal Reserve G.17, complementing the released BLS PPI snapshot.
- Adds official-provider-only generators with validation-only operation, strict registry completeness, duplicate/date/value validation, deterministic sorting, and no credential requirement.
- Extends the existing public-data catalog, normalization, backfill, dry-run, release-manifest, listener, provenance, and revision-detection workflows.
- Latest-series fingerprints include the latest relevant observation for every registered series, so a revision in any registered series changes release identity.
- Streamlit rendering and API request handling use committed snapshots and do not contact BLS or the Federal Reserve.

### Canonical v1 API

- Adds canonical-only routes:
  - `GET /v1/context/momentum`
  - `GET /v1/context/momentum/{industry_code}`
- Supports bounded `source_family`, `signal_type`, `series_id`, `start`, `end`, and `limit` filters.
- Validates registered `series_id` values consistently against both `source_family` and `signal_type`.
- Returns stable typed 200, 400, 422, and 503 behavior without exposing local paths, filenames, credentials, raw exceptions, or internal cache details.
- Preserves the existing `/v1/context/signals*` Industry Pulse contracts and existing annual-analysis API behavior.

### Streamlit experience

- Renames the fifth top-level workspace to **Industry Momentum**.
- Separates monthly context into:
  - Prices;
  - Employment;
  - Production & Capacity.
- Shows mapping relationship, official metadata, latest value, exact-period changes, method, units, freshness, source-family availability, provenance, limitations, charts, and adjacent accessible data tables.
- Supports clearly labeled manual browsing without mutating the annual industry selection.
- Adds an optional month-normalized custom history window that affects only contextual display and signal-only downloads.
- Makes populated bounded ranges and a truthful user-reachable `empty_range` state available while rejecting reversed ranges before service execution.
- Preserves annual ratios, rankings, comparisons, Scenario Lab, health scores and bands, and annual lineage unchanged.

### Structured signal exports

- CSV provides one deterministic observation table.
- JSON provides the typed complete Industry Momentum response envelope.
- XLSX provides:
  - `Price Signals`;
  - `Employment Signals`;
  - `Production Signals`;
  - `Capacity Signals`;
  - `Signal Metadata`.
- Export handling preserves typed provenance and avoids formula execution, hyperlink activation, external workbook relationships, credentials, private paths, and fixture markers.

### Accessibility, privacy, and offline behavior

- Keyboard-only traversal, logical focus order, visible focus, and no keyboard trap were accepted on the merged implementation candidate.
- Effective 200% scaling was accepted without blocking horizontal overflow.
- Selected-tab contrast was corrected and accepted in light and dark appearances.
- Charts have immediately adjacent accessible table alternatives and explicit state language.
- Streamlit usage telemetry remains disabled.
- Browser acceptance observed loopback-only application and WebSocket traffic with no automatic BLS, Federal Reserve, or unrelated external request.
- Screen-reader acceptance: NOT RUN. No screen-reader compliance claim is made.

## Upgrade notes from v0.3.0

- Existing Industry Pulse consumers may continue using `/v1/context/signals` and `/v1/context/signals/{industry_code}`.
- New consumers should use `/v1/context/momentum` for registry discovery and `/v1/context/momentum/{industry_code}` for composed monthly context.
- Do not treat broader-published CES or G.17 scopes as exact six-digit matches.
- Do not compare unlike signal units or raw index levels with different base periods.
- Use `availability`, per-family state, mapping relationship, units, method, freshness, and provenance fields rather than inferring completeness from the presence of observations.
- Annual exports and analytical lineage remain separate from Industry Momentum signal-only exports and provenance.

## Publication Result / Parity

Publication parity is **PASS**:

- CI / Quality Gate #330 and Docker Smoke #170 passed on release-code SHA
  `eec9886c5f0a4ef495b6b31c3c2cc6cdc52e631a`.
- `refs/tags/v0.4.0` points to annotated-tag object
  `d1b777b192c97aaefe167be0018a1890250a55fe`, which peels to the exact release-code SHA.
- The annotated tag is unsigned; GitHub reports verification `false` with reason `unsigned`.
- Remote `main`, the peeled annotated tag, the GitHub prerelease identity, and a clean fresh tag
  checkout all resolve to the exact release-code SHA.
- The fresh checkout reported package/Commitizen and fallback versions `0.4.0`.
- Publication created only the authorized annotated tag and GitHub prerelease; it did not mutate
  release code or the release branch.

The accepted release-candidate validation on Python 3.13.7 recorded:

- 59 focused release/Momentum tests and 461 complete tests passed;
- runtime coverage: 91.01% line, 74.49% branch, 87.63% combined (85% gate passed);
- full-source informational coverage: 86.16% line, 68.51% branch, 83% combined;
- Black, Ruff, mypy, benchmark, detect-secrets baseline, pip check, pip-audit, CES/G.17
  validate-only, committed PPI snapshot validation, and `git diff --check` passed;
- API and Streamlit loopback smoke passed with health/OpenAPI version `0.4.0`, canonical and
  compatibility routes, stable filter errors, and no observed provider or telemetry log activity;
- headed Edge passed the five top-level and three Momentum tabs, valid/empty/reversed ranges,
  keyboard-activated CSV/JSON/five-sheet XLSX exports, partial and total-unavailable states,
  adjacent accessible tables, visible focus, and selected-tab contrast of 6.57:1 light / 5.72:1
  dark;
- native effective 200% zoom was not rerun on the exact final release head;
- Screen-reader acceptance: NOT RUN;
- GNU Make and local Docker are unavailable, so `make quality-gate` and local Docker Smoke are NOT
  RUN; the exact Makefile gate constituents were run individually;
- the only `pip-audit` diagnostic was a non-vulnerability cache-deserialization warning.

## Public Beta limitations

- Industry Momentum covers a reviewed manufacturing subset rather than all NAICS industries.
- Several CES and G.17 observations are officially published for broader industry groups rather than exact six-digit annual industries.
- Contextual monthly signals do not prove profitability, resilience, distress, insolvency, creditworthiness, causation, or forecast performance.
- The annual output-to-cost ratio and composite health-style bands remain experimental heuristic measures.
- PPI, employment, industrial production, capacity, and utilization use different units and may use different bases; raw levels must not be compared as equivalent.
- The application is not financial, investment, credit, insolvency, causal-forecast, or policy advice.
- Screen-reader acceptance is not a PASS unless a real screen reader is exercised and recorded.

## Publication bookkeeping

Publication is complete. Draft PR #133 contains the documentation-only post-publication record;
issue #129 remains open until that bookkeeping PR is reviewed and merged. Neither this record nor
PR #133 changes the release-code commit, annotated tag, or published GitHub prerelease.

## Evidence

- [`docs/execplans/v0.4.0-industry-momentum.md`](execplans/v0.4.0-industry-momentum.md)
- [`docs/execplans/v0.4.0-release-preparation.md`](execplans/v0.4.0-release-preparation.md)
- [`docs/execplans/v0.4.0-publication-record.md`](execplans/v0.4.0-publication-record.md)
- [Issue #129](https://github.com/Nobodyworld/app-industry-resilience/issues/129)
- [Implementation PR #130](https://github.com/Nobodyworld/app-industry-resilience/pull/130)
- [Release PR #132](https://github.com/Nobodyworld/app-industry-resilience/pull/132)
- [Publication bookkeeping PR #133](https://github.com/Nobodyworld/app-industry-resilience/pull/133)
