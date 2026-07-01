# Experimental Composite Analytics Reference

This guide explains the experimental composite score introduced in Stage 1 along with its data sources and usage patterns.

## Overview

The composite score combines four signals derived from the same source cost-structure inputs used by Idiot Index metrics:

1. **Value-added percentage** – derived from value added and gross output.
2. **Resilience score** – computed as value added ÷ intermediate inputs.
3. **Materials dependency ratio** – derived from material or intermediate-input intensity.
4. **Shock sensitivity index** – another transformation of value added, output, and input intensity.

These components are correlated and should not be read as independent evidence of industry health, resilience, or economic distress. Each component is normalised to a 0–1 range and weighted using `src/core/analytics.HealthScoreConfig` (35% value-added, 30% resilience, 20% materials dependency, 15% shock sensitivity). Scores are scaled to 0–100 and mapped into neutral review bands:

| Band | Threshold | Description |
| --- | --- | --- |
| `lower_input_intensity` | ≥ 80 | Lower input intensity under this heuristic. |
| `moderate_input_intensity` | ≥ 65 | Moderate input intensity under this heuristic. |
| `higher_input_intensity` | ≥ 45 | Higher input intensity under this heuristic. |
| `review_required` | < 45 | Review required; not evidence of economic distress. |

The analytics module exposes two public functions:

- `compute_health_scores(df, config=HealthScoreConfig())` – adds `health_score` and `health_band` columns to the dataframe returned by `compute_metrics`.
- `summarise_health(df, group_by="all", top_risk_limit=5)` – aggregates cohort metrics, band distribution, and the highest-risk industries.

## UI integration

- **Signal bar** – shows the average experimental score and review band for the current filter selection.
- **Health tab** – surfaces cohort averages, band distribution, and lowest-score industries in Streamlit.
- **Scenario Lab** – displays score deltas and band shifts when adjustments are applied.

## API integration

- `/evaluate` responses now include a `health` envelope containing summaries for the full dataset and the filtered view.
- `/scenario` responses expose `baseline_health` and `scenario_health` payloads mirroring the Streamlit scenario insights.
- New endpoint `/analytics/health` accepts the same dataset payloads as `/evaluate` and returns only the health summary, making it ideal for automation scripts.

Request example:

```json
POST /analytics/health
{
  "source": "sample",
  "year": 2021,
  "group_by": "sector",
  "top_risks": 3
}
```

Response excerpt:

```json
{
  "health": {
    "filtered": {
      "overall": {
        "average_health_score": 68.4,
        "risk_band": "moderate_input_intensity"
      },
      "top_risks": [
        {"industry_code": "44-45", "health_score": 42.1, "band": "review_required"}
      ]
    }
  }
}
```

## CLI workflow

Use `make analytics` (or run `src/scripts/analytics_health.py`) to generate JSON summaries from CSV datasets:

```bash
make analytics ARGS="--input data/sample_industries.csv --group-by sector --pretty"
```

The script normalises columns, recomputes Idiot Index metrics, derives experimental composite scores, and prints cohort statistics for automation pipelines or scheduled reports.

## Extending the model

`HealthScoreConfig` allows tuning weights, sector prefix length, and risk thresholds. Extension authors can read the `health_summary_full` and `health_summary_filtered` attributes on `IdiotIndexSummary` to surface additional insights alongside the built-in analytics.
