# Health Analytics Reference

This guide explains the composite health score introduced in Stage 1 along with its data sources and usage patterns.

## Overview

The health score combines four signals derived from Idiot Index metrics:

1. **Value-added percentage** – higher value-added implies healthier cost structures.
2. **Resilience score** – computed as value added ÷ intermediate inputs; reflects ability to absorb shocks.
3. **Materials dependency ratio** – lower ratios reduce exposure to supply shocks.
4. **Shock sensitivity index** – lower values indicate better balance between value added and materials costs.

Each component is normalised to a 0–1 range and weighted using `src/core/analytics.HealthScoreConfig` (35% value-added, 30% resilience, 20% materials dependency, 15% shock sensitivity). Scores are scaled to 0–100 and mapped into qualitative bands:

| Band | Threshold | Description |
| --- | --- | --- |
| `excellent` | ≥ 80 | Highly resilient industries with balanced costs. |
| `healthy` | ≥ 65 | Solid fundamentals with manageable risk. |
| `watch` | ≥ 45 | Mixed signals that warrant monitoring. |
| `critical` | < 45 | Vulnerable to materials or margin shocks. |

The analytics module exposes two public functions:

- `compute_health_scores(df, config=HealthScoreConfig())` – adds `health_score` and `health_band` columns to the dataframe returned by `compute_metrics`.
- `summarise_health(df, group_by="all", top_risk_limit=5)` – aggregates cohort metrics, band distribution, and the highest-risk industries.

## UI integration

- **Signal bar** – shows the average health score and risk band for the current filter selection.
- **Health tab** – surfaces cohort averages, band distribution, and top-risk industries in Streamlit.
- **Scenario Lab** – displays health score deltas and risk band shifts when adjustments are applied.

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
        "risk_band": "healthy"
      },
      "top_risks": [
        {"industry_code": "44-45", "health_score": 42.1, "band": "watch"}
      ]
    }
  }
}
```

## CLI workflow

Use `make analytics` (or run `scripts/analytics_health.py`) to generate JSON summaries from CSV datasets:

```bash
make analytics ARGS="--input data/sample_industries.csv --group-by sector --pretty"
```

The script normalises columns, recomputes Idiot Index metrics, derives health scores, and prints cohort statistics for automation pipelines or scheduled reports.

## Extending the model

`HealthScoreConfig` allows tuning weights, sector prefix length, and risk thresholds. Extension authors can read the `health_summary_full` and `health_summary_filtered` attributes on `IdiotIndexSummary` to surface additional insights alongside the built-in analytics.
