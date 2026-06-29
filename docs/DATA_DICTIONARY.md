# Data Dictionary

This document defines the primary columns used across the dashboard, API responses, and scenario outputs.

## Scope

- Applies to datasets rendered in the Streamlit UI and returned by the API.
- Includes base input fields, derived metrics, and scenario-delta fields.

## Identifier and Context Fields

| Column | Type | Unit | Description |
| --- | --- | --- | --- |
| `industry_code` | string | N/A | Industry identifier (NAICS-style code where available). |
| `industry_name` | string | N/A | Human-readable industry label. |
| `year` | integer | calendar year | Observation year associated with the row. |
| `source` | string | N/A | Data source label (for example `sample`, `bea`, `census`, or snapshot source labels). |

## Base Economic Fields

| Column | Type | Unit | Description |
| --- | --- | --- | --- |
| `gross_output` | float | monetary (source currency) | Top-line output/revenue proxy used in ratio calculations. |
| `materials_cost` | float | monetary | Materials expense used for cost intensity and efficiency metrics. |
| `intermediate_inputs` | float | monetary | Intermediate input costs when provided by source data. |
| `value_added` | float | monetary | Economic value retained after intermediate/material costs. |

## Derived Dashboard Metrics

| Column | Type | Unit | Formula / Rule |
| --- | --- | --- | --- |
| `idiot_index` | float | ratio | `gross_output / denominator`, where denominator prefers `materials_cost` and falls back to `intermediate_inputs` when needed. |
| `value_added_pct` | float | percent | `(value_added / gross_output) * 100`, when both fields are available. |
| `materials_share_pct` | float | percent | `(materials_cost / gross_output) * 100`, when both fields are available. |
| `resilience_score` | float | index score | Composite score generated from margin, dependency, and shock sensitivity signals. |
| `materials_dependency_ratio` | float | ratio | Dependency intensity on materials/intermediate cost inputs. |
| `shock_sensitivity_index` | float | index score | Relative sensitivity to modeled scenario shocks. |
| `health_score` | float | index score | Composite health indicator used for risk-banding and ranking. |

## Scenario Output Fields

Scenario runs typically include baseline and shocked values and/or delta rows:

| Field Pattern | Meaning |
| --- | --- |
| `*_baseline` | Baseline metric before any applied scenario adjustment. |
| `*_scenario` | Metric after scenario adjustments are applied. |
| `*_delta` | `scenario - baseline` for the same metric. |

Common delta fields include:

- `idiot_index_delta`
- `resilience_score_delta`
- `materials_dependency_ratio_delta`
- `shock_sensitivity_index_delta`
- `health_score_delta`

## Notes on Interpretation

- A higher `idiot_index` indicates more output per cost denominator, but should be interpreted with source and denominator context.
- `materials_share_pct` and `materials_dependency_ratio` are related but not identical; the former is a direct share, while the latter is part of a broader dependency modeling layer.
- Scenario deltas are comparative analytics outputs and do not represent forecast certainty.

## Provenance and Validation

- Input validation and normalization are handled in application/core layers prior to metric computation.
- The official snapshot workflow and assumptions are documented in `data/README.md` and related operational docs.
