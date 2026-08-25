# Industry Momentum Official Source Registry Record

**Status:** Official registry and committed snapshots verified for issue [#129](https://github.com/Nobodyworld/app-industry-resilience/issues/129)
**Target:** `v0.4.0` Industry Momentum product slice; package version remains `0.3.0` in this pull request  
**Starting main:** `4b76841c4a28c8657336de3c2864b8ac070e68fb`

## Purpose and product boundary

Industry Momentum adds recent official producer-price, employment, production, capacity, and
capacity-utilization observations beside the dashboard's annual cost-structure analysis. These
monthly signals are contextual observations only. They do not enter the output-to-cost ratio,
annual rankings, Scenario Lab, health scores, health bands, annual dataframe lineage, or causal
narratives. No composite momentum score is defined.

The existing eight-series BLS Producer Price Index registry remains authoritative as documented in
[`INDUSTRY_PULSE_BLS_SERIES.md`](INDUSTRY_PULSE_BLS_SERIES.md). This record adds BLS Current
Employment Statistics and Federal Reserve G.17 verification without weakening the existing PPI
contracts.

## Verification rules

Every implemented entry must be recoverable from an official provider file or official series
response. The registry records the provider's published industry code separately from the selected
six-digit annual industry code. `exact` means the provider publishes the same industry scope;
`broader_published` means the official series covers a broader group and the product must say so;
`manual_only` means the series may be browsed but is not presented as a selected-industry mapping.
Labels never establish mappings on their own.

Index series require their provider base period. Utilization rates use percentage points for month-
over-month and year-over-year changes; indexes, counts, hours, and earnings use percent change.
Missing exact calendar observations remain unavailable. Unlike units or different base periods are
never compared as raw levels.

Freshness is source-family specific rather than one global Momentum rule. BLS PPI preserves the
released Industry Pulse threshold of **90 days**. BLS CES employment uses **120 days**, and Federal
Reserve G.17 production/capacity/utilization uses **120 days**. Every returned history exposes its
applied `threshold_days`; these thresholds affect only current/stale context labeling and never
annual calculations, rankings, scenarios, scores, bands, or lineage.

## BLS Current Employment Statistics

Official verification inputs:

- CES home and documentation: <https://www.bls.gov/ces/>
- BLS series identifier format: <https://www.bls.gov/help/hlpforma.htm>
- public API limits: <https://www.bls.gov/developers/api_faqs.htm>
- keyless Public Data API v2: <https://api.bls.gov/publicAPI/v2/timeseries/data/>
- national CES series file: <https://download.bls.gov/pub/time.series/ce/ce.series>
- CES industry file: <https://download.bls.gov/pub/time.series/ce/ce.industry>
- CES datatype file: <https://download.bls.gov/pub/time.series/ce/ce.datatype>

The accepted set uses seasonally adjusted all-employees datatype `01`. CES identifiers begin `CE`,
use seasonal code `S`, carry the eight-digit CES industry code, and end in datatype `01`. The
reviewed official series file reports coverage from January 1990 through at least June 2026 for all
eight entries.

### CES verification evidence

Status: **PASS — reviewed 2026-08-10 against the official CES series, industry, datatype, and
identifier-format files.**

| Target industry | Candidate series | Published code/level | Relationship | Decision and evidence |
| --- | --- | --- | --- | --- |
| `311111` | `CES3231110001` | `3111` / four digit | `broader_published` | Animal food manufacturing, all employees, thousands, seasonally adjusted |
| `312120` | `CES3232914001` | `31212,31213,31214` / combined | `broader_published` | Breweries, wineries, and distilleries, all employees, thousands, seasonally adjusted |
| `322120` | `CES3232210001` | `3221` / four digit | `broader_published` | Pulp, paper, and paperboard mills, all employees, thousands, seasonally adjusted |
| `325211` | `CES3232521101` | `325211` / six digit | `exact` | Plastics material and resin manufacturing, all employees, thousands, seasonally adjusted |
| `326111` | `CES3232611001` | `32611` / five digit | `broader_published` | Plastics packaging materials and film/sheet, all employees, thousands, seasonally adjusted |
| `331110` | `CES3133110001` | `3311` / four digit | `broader_published` | Iron and steel mills and ferroalloy, all employees, thousands, seasonally adjusted |
| `334111` | `CES3133411101` | `334111` / six digit | `exact` | Electronic computer manufacturing, all employees, thousands, seasonally adjusted |
| `336110` | `CES3133610001` | `3361` / four digit | `broader_published` | Motor vehicle manufacturing, all employees, thousands, seasonally adjusted |

Hours and earnings series were not added. The reviewed release requires a consistent, defensible
eight-industry contract; a complete like-for-like hours/earnings set was not established, and
adding a few aggregate series would imply coverage the registry does not have.

## Federal Reserve G.17

Official verification inputs:

- current G.17 release: <https://www.federalreserve.gov/releases/g17/>
- official downloads: <https://www.federalreserve.gov/releases/g17/download.htm>
- source and revision documentation: <https://www.federalreserve.gov/releases/g17/about.htm>
- release feed: <https://www.federalreserve.gov/feeds/g17.html>

The final registry must distinguish industrial-production indexes, capacity indexes, and capacity-
utilization percentages. It must record the official series or industry code, title, units,
seasonal status, current base period, source table, published industry scope and mapping level,
historical coverage, and annual-revision behavior. Direct Federal Reserve files are the primary
provider; a third-party substitute is not permitted.

### G.17 verification evidence

Status: **PASS — reviewed 2026-08-10 against the official current `ip_sa.txt`, `cap_sa.txt`, and
`utl_sa.txt` files and G.17 source/revision documentation.** Production and capacity indexes use
base `2017=100`; utilization is a percent and changes in percentage points. All are seasonally
adjusted. G.17 identifiers may change at annual revision and are revalidated on every refresh.

| Signal | Official code → target | Published scope / level | Relationship |
| --- | --- | --- | --- |
| Production | `G3111` → `311111` | `3111` / four digit | broader |
| Production | `N31212` → `312120` | `31212` / five digit | broader |
| Production | `G32212` → `322120` | `32212` / five digit | broader |
| Production | `N325211` → `325211` | `325211` / six digit | exact |
| Production | `G3261` → `326111` | `3261` / four digit | broader |
| Production | `G3311A2` → `331110` | `3311,3312` / combined | broader |
| Production | `G3341` → `334111` | `3341` / four digit | broader |
| Production | `G33611` → `336110` | `33611` / five digit | broader |
| Capacity + utilization | `G311A2` → `311111` | `311,312` / combined | broader |
| Capacity + utilization | `G322` → `322120` | `322` / three digit | broader |
| Capacity + utilization | `G325` → `325211` | `325` / three digit | broader |
| Capacity + utilization | `G326` → `326111` | `326` / three digit | broader |
| Capacity + utilization | `G331` → `331110` | `331` / three digit | broader |
| Capacity + utilization | `G334` → `334111` | `334` / three digit | broader |
| Capacity + utilization | `G3361T3` → `336110` | `3361-3363` / combined | broader |

No separate brewery capacity/utilization mapping was accepted: the official combined `G311A2`
scope spans food, beverage, and tobacco, and assigning that same aggregate to multiple selected
industries would overstate mapping specificity. No third-party candidate was used.

## Snapshot evidence fields

The committed record lists, separately for CES and G.17, the official endpoint or file URLs,
retrieval UTC timestamp, requested and accepted series, January 2024 through latest-complete-month
observation range, latest release period, row and series counts, deterministic CSV SHA-256,
manifest identity, registry/schema/generator versions, generator command, transformations,
interpretation notes, and revision notes. The committed product path is offline and request handling
must perform no provider calls.

| Family | Range / latest common month | Rows / series | SHA-256 | Manifest identity |
| --- | --- | --- | --- | --- |
| BLS CES | 2024-01 through 2026-06 | 240 / 8 | `4115607936cf15d80ecbb0f3924dc8611527d150fd7b106733b2c06389904de6` | `industry-momentum-ces-2024-01-2026-06-4115607936cf15d8` |
| Federal Reserve G.17 | 2024-01 through 2026-04 | 616 / 22 | `d29a2b31edb86a0353cfc04e77503411aacf523c95cbb653b3cbaed5de9ee954` | `industry-momentum-g17-2024-01-2026-04-d29a2b31edb86a03` |

April 2026 is the latest complete month common to every registered G.17 series in the reviewed
current files; later partial detailed-series values are deliberately excluded.

## Interpretation text

Producer prices, employment, hours, earnings, production, capacity, and utilization describe
observed official series. No source proves profitability, resilience, distress, insolvency, or
causation. A broader published series is not an exact six-digit match. Raw signals with unlike
units or different base periods must not be compared directly.

## Change history

- 2026-08-10: Created the verification scaffold before official series review so no candidate is
  presented as implemented or accepted without evidence.
- 2026-08-10: Recorded the accepted 8 CES and 22 G.17 series, explicit broader mappings, candidate
  exclusions, snapshot bounds, hashes, and manifest identities.
- 2026-08-20: Preserved the released PPI 90-day freshness contract and documented explicit 120-day
  CES and G.17 thresholds; public snapshot degradation remains bounded and path-free.
