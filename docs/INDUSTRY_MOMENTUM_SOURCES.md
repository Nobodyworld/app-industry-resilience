# Industry Momentum Official Source Registry Record

**Status:** Verification in progress for issue [#129](https://github.com/Nobodyworld/app-industry-resilience/issues/129)  
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

## BLS Current Employment Statistics

Official verification inputs:

- CES home and documentation: <https://www.bls.gov/ces/>
- BLS series identifier format: <https://www.bls.gov/help/hlpforma.htm>
- public API limits: <https://www.bls.gov/developers/api_faqs.htm>
- keyless Public Data API v2: <https://api.bls.gov/publicAPI/v2/timeseries/data/>
- national CES series file: <https://download.bls.gov/pub/time.series/ce/ce.series>
- CES industry file: <https://download.bls.gov/pub/time.series/ce/ce.industry>
- CES datatype file: <https://download.bls.gov/pub/time.series/ce/ce.datatype>

The implementation candidate set will be filled only after those files are checked for each of the
eight PPI industries. For each accepted entry the final record must show the complete series ID,
seasonal-adjustment code, published industry code and level, datatype, official title, units,
historical begin/end, target industry code, relationship, mapping basis, and steward notes. A
missing exact six-digit series is not an error: a truthful broader mapping or manual-only series is
preferred to a fabricated exact mapping.

### CES verification evidence

Status: **NOT RUN** at scaffold commit.

| Target industry | Candidate series | Published code/level | Relationship | Decision and evidence |
| --- | --- | --- | --- | --- |
| `311111` | Pending official-file query | Pending | Pending | Not yet reviewed |
| `312120` | Pending official-file query | Pending | Pending | Not yet reviewed |
| `322120` | Pending official-file query | Pending | Pending | Not yet reviewed |
| `325211` | Pending official-file query | Pending | Pending | Not yet reviewed |
| `326111` | Pending official-file query | Pending | Pending | Not yet reviewed |
| `331110` | Pending official-file query | Pending | Pending | Not yet reviewed |
| `334111` | Pending official-file query | Pending | Pending | Not yet reviewed |
| `336110` | Pending official-file query | Pending | Pending | Not yet reviewed |

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

Status: **NOT RUN** at scaffold commit. Candidate rows, exact/broader/manual decisions, rejected
series, base periods, and official-file evidence will be appended after direct-file review.

## Snapshot evidence fields

The completed record will list, separately for CES and G.17, the official endpoint or file URLs,
retrieval UTC timestamp, requested and accepted series, January 2024 through latest-complete-month
observation range, latest release period, row and series counts, deterministic CSV SHA-256,
manifest identity, registry/schema/generator versions, generator command, transformations,
interpretation notes, and revision notes. The committed product path is offline and request handling
must perform no provider calls.

## Interpretation text

Producer prices, employment, hours, earnings, production, capacity, and utilization describe
observed official series. No source proves profitability, resilience, distress, insolvency, or
causation. A broader published series is not an exact six-digit match. Raw signals with unlike
units or different base periods must not be compared directly.

## Change history

- 2026-08-10: Created the verification scaffold before official series review so no candidate is
  presented as implemented or accepted without evidence.
