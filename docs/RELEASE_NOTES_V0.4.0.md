# v0.4.0 Public Beta Release Notes

**Status:** Release candidate preparation — not published<br>
**Starting main / merged-feature SHA:** `f99abbf42c898f0fe4a7494f09b4aae13bed5c40`<br>
**Release branch:** `release/v0.4.0`<br>
**Package / Commitizen / fallback version:** `0.4.0` / `0.4.0` / `0.4.0`<br>
**Planned release tag:** `v0.4.0` — not created<br>
**GitHub release:** not created<br>
**Release issue:** [#129](https://github.com/Nobodyworld/app-industry-resilience/issues/129)<br>
**Implementation pull request:** [#130](https://github.com/Nobodyworld/app-industry-resilience/pull/130)<br>
**Release pull request:** pending

These notes describe the planned `v0.4.0` Public Beta release. The complete Industry Momentum implementation is merged into `main`, but publication remains gated on version-aligned exact-head validation, release-candidate review, explicit merge authorization, an annotated immutable tag, GitHub release publication, and tag/release/fresh-checkout SHA parity.

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
- Screen-reader acceptance remains **NOT RUN** unless a real screen reader is exercised during final release-candidate validation. No screen-reader compliance claim is made.

## Upgrade notes from v0.3.0

- Existing Industry Pulse consumers may continue using `/v1/context/signals` and `/v1/context/signals/{industry_code}`.
- New consumers should use `/v1/context/momentum` for registry discovery and `/v1/context/momentum/{industry_code}` for composed monthly context.
- Do not treat broader-published CES or G.17 scopes as exact six-digit matches.
- Do not compare unlike signal units or raw index levels with different base periods.
- Use `availability`, per-family state, mapping relationship, units, method, freshness, and provenance fields rather than inferring completeness from the presence of observations.
- Annual exports and analytical lineage remain separate from Industry Momentum signal-only exports and provenance.

## Validation baseline and remaining release gates

The merged implementation candidate previously recorded:

- 458 tests passed;
- runtime line coverage of 91.01%;
- runtime branch coverage of 74.49%;
- combined runtime coverage of 87.63%, above the 85% gate;
- full-source informational line coverage of 86.04%;
- full-source informational branch coverage of 68.40%;
- passing Black, Ruff, mypy, benchmark, detect-secrets, pip check, pip-audit, generator validation-only, and diff checks;
- passing headed Microsoft Edge/Playwright acceptance for the required product states, exports, accessibility smoke, appearance, scaling, and loopback-only traffic;
- passing exact-head CI / Quality Gate #320 and Docker Smoke #162;
- passing post-merge `main` CI #323 and Docker Smoke #163.

Those results are implementation and post-merge baselines. They do not replace final validation of the version-aligned release candidate.

Before publication, record on the exact final release-candidate head:

- focused release/version tests;
- complete Python 3.13 quality gate;
- exact runtime and full-source coverage;
- Black, Ruff, mypy, benchmark, detect-secrets, pip check, pip-audit, generator validation-only, and `git diff --check` results;
- API and Streamlit loopback smoke;
- release-relevant headed Microsoft Edge acceptance, download parsing, console inspection, and network-host inventory;
- explicit screen-reader disposition;
- hosted CI / Quality Gate and Docker Smoke;
- exact release-code SHA and GO / CONDITIONAL GO / NO-GO recommendation.

## Public Beta limitations

- Industry Momentum covers a reviewed manufacturing subset rather than all NAICS industries.
- Several CES and G.17 observations are officially published for broader industry groups rather than exact six-digit annual industries.
- Contextual monthly signals do not prove profitability, resilience, distress, insolvency, creditworthiness, causation, or forecast performance.
- The annual output-to-cost ratio and composite health-style bands remain experimental heuristic measures.
- PPI, employment, industrial production, capacity, and utilization use different units and may use different bases; raw levels must not be compared as equivalent.
- The application is not financial, investment, credit, insolvency, causal-forecast, or policy advice.
- Screen-reader acceptance is not a PASS unless a real screen reader is exercised and recorded.

## Publication plan

Publication requires separate explicit owner authorization after the release pull request is validated and merged.

1. Identify the exact merged release-code SHA.
2. Create annotated immutable tag `v0.4.0` at that SHA.
3. Publish `v0.4.0 Public Beta — Industry Momentum` as the intended GitHub prerelease/release classification.
4. Verify the annotated-tag object and peeled commit.
5. Verify a fresh tag checkout resolves to the release-code SHA and reports version `0.4.0`.
6. Verify tag, GitHub release, release-code commit, and fresh-checkout parity.
7. Update these release notes and the durable publication record with exact evidence.
8. Close issue #129 only after publication bookkeeping is complete.

## Evidence

- [`docs/execplans/v0.4.0-industry-momentum.md`](execplans/v0.4.0-industry-momentum.md)
- [`docs/execplans/v0.4.0-release-preparation.md`](execplans/v0.4.0-release-preparation.md)
- [Issue #129](https://github.com/Nobodyworld/app-industry-resilience/issues/129)
- [Implementation PR #130](https://github.com/Nobodyworld/app-industry-resilience/pull/130)
