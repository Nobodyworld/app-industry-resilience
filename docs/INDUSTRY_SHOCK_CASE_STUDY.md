# Industry Shock Case Study

## Case: Food Manufacturing Cost Shock (NAICS 311)

This case study demonstrates a reproducible shock analysis using the Scenario CLI.

## Objective

Stress-test one industry for simultaneous demand/output pressure and input-cost inflation, then observe portfolio-level and industry-level metric shifts.

## Reproduction Command

```bash
python src/scripts/run_scenario.py --adjust "codes=311,gross=-10,materials=8" --top 3 --output build/reports/case-study-311.json
```

## Scenario Definition

- Target industry code: `311` (Food Manufacturing)
- Gross output shock: `-10%`
- Materials cost shock: `+8%`
- Value added shock: `0%` (unchanged)
- Intermediate input shock: `0%` (unchanged)

## Observed Portfolio-Level Outcome

From the generated run output:

- Gross output total: `7,615,900.00` -> `7,525,490.00` (delta `-90,410.00`)
- Materials cost total: `3,774,100.00` -> `3,818,316.00` (delta `+44,216.00`)
- Value added total: `2,867,800.00` -> `2,867,800.00` (delta `+0.00`)
- Average idiot index: `1.8859` -> `1.8519` (delta `-0.0341`)
- Average resilience score: `0.89` -> `0.88` (delta `-0.01`)

## Observed Industry-Level Delta (NAICS 311)

From `deltas` in `build/reports/case-study-311.json`:

- `gross_output`: `-90,410.0`
- `materials_cost`: `+44,216.0`
- `idiot_index`: `-0.2726`
- `resilience_score`: `-0.0471`
- `materials_share_pct`: `+12.2265`
- `materials_dependency_ratio`: `+0.1223`
- `shock_sensitivity_index`: `+0.0181`
- `health_score`: `-1.68`

## Interpretation

- The combination of lower output and higher materials cost compresses efficiency and weakens resilience for the targeted industry.
- At portfolio level, average performance degradation is moderate because only one industry receives the shock.
- This pattern is useful for contingency planning where demand contraction and supplier inflation occur together.

## Operational Use

- Use this case as a baseline regression scenario for Scenario Lab behavior.
- Repeat with alternative shock vectors (for example gross `-5%`, materials `+15%`) to map sensitivity bands.
- Pair with observability snapshots to track scenario behavior changes across releases.
