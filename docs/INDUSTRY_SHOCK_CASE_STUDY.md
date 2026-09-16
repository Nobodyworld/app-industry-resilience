# Industry Shock Case Study

## Case: Food Manufacturing Cost Shock (NAICS 311)

This case study demonstrates a reproducible shock analysis using the Scenario CLI.

## Source Dataset

- Dataset: `data/sample_industries.csv`
- Execution path: `src/scripts/run_scenario.py`
- Output artifact: `build/reports/case-study-311.json`

## Objective

Stress-test one industry for simultaneous demand/output pressure and input-cost inflation, then observe portfolio-level and industry-level metric shifts.

## Reproduction Command

```bash
python -c "from pathlib import Path; Path('build/reports').mkdir(parents=True, exist_ok=True)"
python src/scripts/run_scenario.py --adjust "codes=311,gross=-10,materials=8" --top 3 --output build/reports/case-study-311.json
```

Regenerate the result tables with `python -m src.scripts.render_industry_case_study`.
The regression `tests/test_industry_case_study.py` compares these tables to fresh calculations.

Reproducibility check:

1. Run the command from repository root.
2. Confirm `build/reports/case-study-311.json` is created.
3. Verify portfolio and target-industry deltas match (or are numerically very close to) the values documented below.

## Scenario Definition

- Target industry code: `311` (Food Manufacturing)
- Gross output shock: `-10%`
- Materials cost shock: `+8%`
- Value added shock: `0%` (unchanged)
- Intermediate input shock: `0%` (unchanged)

<!-- BEGIN GENERATED SCENARIO RESULTS -->

## Calculated Target-Industry Results (NAICS 311)

Observation year: 2021. Values below are generated from the committed CSV.

| Metric | Baseline | Scenario | Delta |
| --- | ---: | ---: | ---: |
| `gross_output` | 904,100.0000 | 813,690.0000 | -90,410.0000 |
| `materials_cost` | 552,700.0000 | 596,916.0000 | +44,216.0000 |
| `value_added` | 351,400.0000 | 351,400.0000 | +0.0000 |
| `idiot_index` | 1.6358 | 1.3632 | -0.2726 |
| `resilience_score` | 0.6358 | 0.5887 | -0.0471 |
| `value_added_pct` | 38.8674 | 43.1860 | +4.3186 |
| `materials_share_pct` | 61.1326 | 73.3591 | +12.2265 |
| `materials_dependency_ratio` | 0.6113 | 0.7336 | +0.1223 |
| `shock_sensitivity_index` | 0.6113 | 0.6294 | +0.0181 |
| `health_score` | 33.5700 | 31.8900 | -1.6800 |

## Calculated Portfolio-Level Results

These totals and means describe all eight bundled sample industries.

| Metric | Baseline | Scenario | Delta |
| --- | ---: | ---: | ---: |
| `gross_output_total` | 7,615,900.0000 | 7,525,490.0000 | -90,410.0000 |
| `materials_cost_total` | 3,774,100.0000 | 3,818,316.0000 | +44,216.0000 |
| `value_added_total` | 2,867,800.0000 | 2,867,800.0000 | +0.0000 |
| `idiot_index_avg` | 1.8859 | 1.8519 | -0.0341 |
| `resilience_score_avg` | 0.8859 | 0.8800 | -0.0059 |
| `health_score_avg` | 38.1975 | 37.9875 | -0.2100 |

<!-- END GENERATED SCENARIO RESULTS -->

## Recalculated Metrics Summary

After the defined shock is applied to NAICS 311, the model recalculates all dependent metrics for both the target industry and portfolio aggregate. Key recalculated outcomes for NAICS 311 include:

- Lower efficiency (`idiot_index` down)
- Lower resilience (`resilience_score` down)
- Higher cost burden (`materials_share_pct` up)
- Higher dependency and sensitivity (`materials_dependency_ratio` and `shock_sensitivity_index` up)

## Interpretation

- The combination of lower output and higher materials cost compresses efficiency and weakens resilience for the targeted industry.
- At portfolio level, average performance degradation is moderate because only one industry receives the shock.
- This pattern is useful for contingency planning where demand contraction and supplier inflation occur together.

## Limitations

- The sample dataset is illustrative and not a complete production census of all industries.
- Scenario adjustments are deterministic percentage shocks and do not include dynamic market feedback effects.
- Results depend on source-field availability (`materials_cost` vs `intermediate_inputs`) and denominator-selection rules.
- Values may change slightly across versions if normalization or metric formulas are updated.

## Operational Use

- Use this case as a baseline regression scenario for Scenario Lab behavior.
- Repeat with alternative shock vectors (for example gross `-5%`, materials `+15%`) to map sensitivity bands.
- Pair with observability snapshots to track scenario behavior changes across releases.
