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

## Interpretation Limitations

- Metrics are heuristic diagnostics, not causal inference or forecasting guarantees.
- Cross-source comparisons can reflect source methodology differences (coverage, definitions, revisions).
- Monetary fields are source-native values and may not be inflation-adjusted unless explicitly transformed upstream.
- Proxy-derived fields should be treated as approximate substitutes when direct source fields are unavailable.
- Scenario outputs are deterministic recalculations from stated shocks and do not model second-order macroeconomic dynamics.

## Provenance and Validation

- Input validation and normalization occur before metric computation in application/core layers.
- Official snapshot assumptions and refresh workflow are documented in `data/README.md` and `docs/WORKFLOWS_DATA_REFRESH.md`.
