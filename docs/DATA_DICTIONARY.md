# Data Dictionary

This document defines the fields used by the U.S. Industry Cost Structure and Resilience Dashboard across the Streamlit UI, headless API, and scenario outputs.

## Scope

- Applies to normalized datasets used for evaluation and scenario analysis.
- Covers required and optional input fields, proxy behavior, derived metrics, and scenario output conventions.

## Required Input Fields

The ingestion pipeline requires the following fields in every input row.

| Field | Type | Source | Unit | Time Basis | Missing-Value Handling |
| --- | --- | --- | --- | --- | --- |
| `industry_code` | string | Input dataset (`sample`, `bea`, `census`, uploaded CSV, or snapshot) | N/A | Annual record key | Row rejected or validation error if absent. |
| `industry_name` | string | Input dataset | N/A | Annual record key | Row rejected or validation error if absent. |
| `year` | integer | Input dataset | calendar year | Point-in-time annual observation | Row rejected or validation error if absent or non-numeric. |

## Optional Input Fields

At least one denominator candidate (`materials_cost` or `intermediate_inputs`) should be present for robust ratio outputs.

| Field | Type | Source | Unit | Time Basis | Missing-Value Handling |
| --- | --- | --- | --- | --- | --- |
| `gross_output` | float | BEA/Census/sample/upload | Monetary (nominal, source-provided) | Annual | If missing, dependent derived metrics become null. |
| `materials_cost` | float | Census/sample/upload | Monetary | Annual | Preferred denominator for `idiot_index`; if missing, fallback proxy may be used. |
| `intermediate_inputs` | float | BEA/sample/upload | Monetary | Annual | Fallback denominator when `materials_cost` is unavailable. |
| `value_added` | float | BEA/Census/sample/upload | Monetary | Annual | Optional for margin-like metrics; missing values propagate to derived percentage fields. |
| `source` | string | Pipeline metadata | N/A | Observation metadata | If missing, pipeline may assign source context during normalization. |

## Proxy and Denominator Rules

- `idiot_index` denominator precedence: `materials_cost` first, then `intermediate_inputs`.
- If both denominator fields are missing, denominator-dependent metrics are null.
- Zero-denominator handling: when selected denominator is `0`, ratio outputs are set to null/NA (not infinite) to avoid misleading results.
- Census AIES workflows may include proxy-derived operating expense fields; proxy use must be interpreted as an estimate, not a direct reported value.

## Derived Metrics

| Field | Type | Unit | Formula / Rule |
| --- | --- | --- | --- |
| `idiot_index` | float | ratio | `gross_output / denominator` with denominator rules above. |
| `value_added` | float | monetary | Source-provided or computed fallback depending on dataset availability. |
| `value_added_pct` | float | percent | `(value_added / gross_output) * 100` when both values are valid and `gross_output != 0`. |
| `materials_share_pct` | float | percent | `(materials_cost / gross_output) * 100` when values are valid and `gross_output != 0`. |
| `materials_dependency_ratio` | float | ratio | Dependency measure derived from material/intermediate input intensity. |
| `shock_sensitivity_index` | float | index score | Composite sensitivity estimate from scenario response factors. |
| `resilience_score` | float | index score | Composite resilience indicator built from margin/dependency/sensitivity signals. |
| `health_score` | float | index score | Aggregated operational health indicator used for ranking and risk banding. |

## Scenario Output Conventions

Scenario outputs can include baseline/scenario snapshots and delta fields.

| Field Pattern | Meaning |
| --- | --- |
| `*_baseline` | Baseline value before applied shock adjustments. |
| `*_scenario` | Recomputed value after scenario adjustments. |
| `*_delta` | `scenario - baseline` for the same metric. |

Common delta fields:

- `idiot_index_delta`
- `resilience_score_delta`
- `materials_dependency_ratio_delta`
- `shock_sensitivity_index_delta`
- `health_score_delta`

## Public Signal Schema

Public readiness sources that do not directly map to annual cost-structure inputs should be
stored as leading signals instead of being forced into the core evaluation schema.

| Field | Type | Meaning |
| --- | --- | --- |
| `observation_date` | string/date | Source observation period or release observation date. |
| `frequency` | string | Daily, weekly, monthly, quarterly, annual, bi-annual, or multi-annual cadence. |
| `series_id` | string | Upstream series, table, or file identifier. |
| `industry_code` | string/null | NAICS or compatible industry code when available. |
| `signal_name` | string | Human-readable signal label. |
| `signal_value` | float/string | Source-native value after cleaning. |
| `units` | string | Source-native units. |
| `seasonal_adjustment` | string/null | Seasonal adjustment flag or description when published. |
| `release_period` | string | Release batch key used by manifests and listener checks. |
| `source` | string | Dataset family or upstream agency label. |

Release manifests for public readiness data track `dataset_id`, `release_period`, `source_url`,
`fetched_at`, `content_hash`, row count, columns, schema version, cleaning version, optional ETag,
optional Last-Modified, observation range, and notes. These manifests are the duplicate-fetch
guardrail for daily, weekly, monthly, quarterly, annual, bi-annual, and multi-annual refresh jobs.

### Industry Pulse BLS PPI snapshot

The committed `data/industry_pulse_bls_snapshot.csv` specializes the monthly public-signal
contract for eight reviewed whole-industry series.

| Field | Type | Meaning |
| --- | --- | --- |
| `series_id` | uppercase string | Reviewed `PCU` ID with matching six-digit industry and product segments. |
| `industry_code` | six-digit string | Exact registered NAICS mapping; broader codes are never inferred. |
| `industry_name` | string | Readable registry label. |
| `observation_date` | date | First day of the source calendar month. |
| `value` | finite float | Source PPI index value; never compared as a raw level across unlike base dates. |
| `units` | string | Producer Price Index units with per-series base-period caveat. |
| `seasonal_adjustment` | string | Explicit BLS adjustment status. |
| `base_date` | `YYYY-MM` | Per-series BLS base date. |
| `release_period` | `YYYY-MM` | Monthly release/observation key; `M13` is excluded. |
| `source` | string | Reviewed offline BLS PPI snapshot label. |

Month-over-month is `(latest / exact prior calendar month - 1) * 100`; year-over-year uses the
exact same month one year earlier. Missing exact periods are not replaced with nearest values,
and zero denominators remain unavailable. Freshness is `current` through 90 days after the
latest monthly observation, `stale` after 90 days, and `unknown` without an observation. Tests
inject the `as_of` date.

### Industry Momentum CES and G.17 snapshots

The CES and G.17 CSVs standardize `source_family`, `signal_type`, `series_id`, published and target
industry codes, `mapping_relationship`, first-of-month `observation_date`, finite `value`, `units`,
seasonal status, optional `base_period`, `release_period`, and source label. CES employment is in
thousands of employees. G.17 production and capacity indexes use `2017=100`; utilization is a
percent. Index/count changes are percent changes; utilization changes are percentage points.

Registry metadata adds mapping level/basis, official title/table/URL, historical coverage, and
review notes. Provenance is source-family-specific and allowlisted. Broader published mappings are
not exact six-digit matches, and unlike units or index base periods must not be compared directly.

## Interpretation Limitations

- Metrics are heuristic diagnostics, not causal inference or forecasting guarantees.
- Cross-source comparisons can reflect source methodology differences (coverage, definitions, revisions).
- Monetary fields are source-native values and may not be inflation-adjusted unless explicitly transformed upstream.
- Proxy-derived fields should be treated as approximate substitutes when direct source fields are unavailable.
- Scenario outputs are deterministic recalculations from stated shocks and do not model second-order macroeconomic dynamics.
- Industry Pulse PPI is contextual producer-price movement, not the annual output-to-cost
  ratio, a profitability measure, a resilience input, an insolvency indicator, or causal
  evidence. Different series may use different base dates.

## Provenance and Validation

- Input validation and normalization occur before metric computation in application/core layers.
- Official snapshot assumptions and refresh workflow are documented in `data/README.md` and `docs/WORKFLOWS_DATA_REFRESH.md`.
- Industry Pulse signal provenance is a separate typed envelope and is never copied into annual
  dataframe lineage.
- Industry Momentum family provenance is likewise separate; snapshots and manual browsing never
  mutate annual dataframe attributes, rankings, scenarios, health scores, or bands.
