# Official Snapshot Risk Brief (2026-06-27)

## Scope

- Dataset: `data/official_industry_snapshot.csv`
- Records: 87 industries (Census AIES 2023)
- Tooling run: `python src/scripts/analytics_health.py --input data/official_industry_snapshot.csv --group-by all --pretty`

## Executive signal

- Portfolio-wide health is in `critical` territory.
- Average health score: `30.21`
- Average idiot index: `2.18`
- Average materials dependency ratio: `0.694`

Interpretation: the current official snapshot indicates broad cost-structure fragility across most industries, with high dependence on operating-input proxies and limited buffer against shocks.

## Risk distribution

- Critical: 66 industries (75.86%)
- Watch: 5 industries (5.75%)
- Healthy: 4 industries (4.60%)
- Excellent: 10 industries (11.49%)

## Highest-risk industries (lowest health score)

1. `493` Warehousing and storage: `0.00` (`critical`)
2. `521` Monetary authorities - central bank: `0.00` (`critical`)
3. `622` Hospitals: `3.07` (`critical`)
4. `623` Nursing and residential care facilities: `6.14` (`critical`)
5. `484` Truck transportation: `6.38` (`critical`)

## Formula and logic validation

The bottom-risk values above were re-derived directly from the current code path (`compute_metrics` -> `compute_health_scores`) and raw snapshot rows for the same 5 industry codes.

- Current health score formula:
  - value component = `clip(value_added_pct, 0, 100) / 100`
  - resilience component = `clip(resilience_score, 0, inf) / 3`, capped at `1`
  - dependency component = `1 - clip(materials_dependency_ratio, 0, 1)`
  - shock component = `1 - clip(shock_sensitivity_index, 0, 1)`
  - score = `100 * (0.35*value + 0.30*resilience + 0.20*dependency + 0.15*shock)`

Validation outcome: results are mathematically consistent with source data. For `493` and `521`, `intermediate_inputs` exceed `gross_output`, which yields negative `value_added_pct`, negative `resilience_score`, and dependency/shock ratios above `1`. After clipping/penalty logic, components collapse toward `0`, producing a `0.00` health score.

## Mitigation review for transport and health care cohorts

Priority set (from current bottom-risk list):

1. Transport/logistics: `484` Truck transportation, `493` Warehousing and storage.
2. Health care delivery: `622` Hospitals, `623` Nursing and residential care facilities.

Recommended mitigation workflow:

1. Separate structural margin pressure vs. data-definition artifacts by tracking both:
   - published operating-expense proxy ratio (`gross_output / intermediate_inputs`), and
   - clamped resilience view (`max(value_added, 0)`) for sensitivity analysis.
2. Add cohort-level alerts when `intermediate_inputs > gross_output` to force analyst review before operational decisions.
3. For transport and health care reporting, publish both raw and adjusted views in dashboards and scenario outputs to prevent overreaction to proxy artifacts.
4. Recompute these cohorts on each data refresh and diff against prior run to detect sudden denominator shifts.

## Sector concentration notes

- Strongest sectors by average health: `42` (wholesale, `93.09`), `44` (retail, `75.96`), `45` (retail subset, `65.12`).
- Weakest sector signal includes `62` (health care) with average health `6.83`.
- Sector `49` shows negative average value-added percent (`-56.66`), suggesting especially unstable cost structure assumptions in that cohort.

## Security and quality checks run

- Formatting: `black --check` passed after auto-format.
- Lint: `ruff check` passed.
- Typing: `python -m mypy src` passed.
- Tests: `pytest -q` passed (`216 passed`).
- Dependency audit: `pip-audit` previously flagged `black` (`GHSA-3936-cmfr-pm3m` / `CVE-2026-32274`); tooling is now upgraded to `26.3.1`.
- Secret scan triage: regenerated `config/.secrets.baseline` from a full repo scan. Findings remain 14 across 5 files and are currently treated as intentional test/workflow literals pending allowlist review.

## Reproducibility procedure

Use these commands to recreate the exact analysis:

1. Refresh official snapshot:

- `python src/scripts/refresh_official_data.py`

2. Generate health analytics JSON:

- `python src/scripts/analytics_health.py --input data/official_industry_snapshot.csv --group-by all --pretty`

3. Recompute and inspect the bottom-risk rows directly from formulas:

- `python -c "import pandas as pd; from src.core.metrics import compute_metrics, MetricConfig; from src.core.analytics import compute_health_scores; df=pd.read_csv('data/official_industry_snapshot.csv'); m=compute_metrics(df, config=MetricConfig(use_cache=False)); s=compute_health_scores(m); print(s[s['industry_code'].astype(str).isin(['493','521','622','623','484'])][['industry_code','industry_name','gross_output','intermediate_inputs','value_added','idiot_index','value_added_pct','resilience_score','materials_dependency_ratio','shock_sensitivity_index','health_score']].sort_values('health_score').to_string(index=False))"`

4. Validate scan/tooling gates:

- `python -m black --check app.py src tests`
- `ruff check app.py src tests`
- `python -m mypy src`
- `pytest -q`
- `python -m detect_secrets scan . > config/.secrets.baseline`

## Recommended immediate actions

1. Implement dual-view reporting (raw proxy plus adjusted/clamped resilience) for transport and health care cohorts.
2. Keep `black` pinned to `26.3.1` or newer within major version 26 and monitor formatter deltas in pre-commit/CI.
3. Convert intentional secret-like literals to explicit allowlist pragmas where appropriate and periodically prune baseline entries.
