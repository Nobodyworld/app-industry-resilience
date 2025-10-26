# Scenario Lab & Automation Guide

The Scenario Lab lets you explore "what-if" narratives directly inside the Streamlit app while reusing the same computation pipeline in automation workflows. This guide explains how the planner works, how to operate it through the UI and CLI, and how to capture outputs for further analysis.

## Core Concepts

- **Scenario Planner (`src/application/scenario_planner.py`)** – accepts a baseline dataframe, applies percentage deltas to core columns (gross output, materials cost, value added, intermediate inputs), recomputes Idiot Index metrics plus resilience scores, and surfaces per-industry/aggregate deltas.
- **Scenario Controls** – Streamlit widgets backed by `ScenarioControlState` capture target industries and slider adjustments. Empty selections apply shocks to the entire dataset.
- **Resilience Metrics** – `resilience_score` (value added ÷ external inputs), `materials_dependency_ratio`, and `shock_sensitivity_index` add context to Idiot Index changes.
- **Health Analytics** – `ScenarioPlanner` now computes composite health scores and risk bands for baseline vs scenario outcomes, exposing deltas through the UI, API, and CLI helpers.

## Using the Streamlit Scenario Lab

1. Open the app (`streamlit run app.py`) and configure your data source.
2. Scroll to the **Scenario Lab** section.
3. Pick one or more industries (or leave blank to apply changes everywhere).
4. Adjust the sliders to model % changes in gross output, materials cost, value added, or intermediate inputs.
5. Review the updated metrics:
   - **Aggregate metrics** show totals/averages with deltas.
   - **Health summary** highlights average health scores and risk band shifts for the focus set.
   - **Scenario comparison table** lists baseline vs scenario values with per-metric deltas.
   - **Leading changes** highlights the largest Idiot Index deltas and resilience shifts.
   - **Delta chart** visualises Idiot Index changes for the current focus set.
6. Download results via the standard export panel or copy the shareable link. Scenario codes and slider values are embedded in the query parameters so others can load the same configuration instantly.

## Running Scenarios from the CLI

The CLI mirrors the planner logic for automation and offline analysis.

```bash
# Model a 5% gross-output lift and 3% materials reduction for NAICS 311 and 325
make scenario ARGS="--adjust codes=311|325,gross=5,materials=-3" > scenario.txt

# Save the result to JSON
python scripts/run_scenario.py --adjust codes=336,gross=-4 --output build/reports/scenario.json
```

`--adjust` accepts comma-separated key/value pairs:

- `codes` – pipe-delimited industry codes (omit to target the whole dataset)
- `gross` – gross output delta (%)
- `materials` – materials cost delta (%)
- `value` – value-added delta (%)
- `intermediate` – intermediate input delta (%)

Multiple `--adjust` flags may be supplied to model different clusters. Output includes aggregate summaries, per-industry deltas, and JSON payloads suitable for downstream tooling.

## Prefetching Caches

`scripts/prefetch_data.py` warms caches so first-run latency stays low. By default it loads the sample dataset; pass `--sources bea census` and `--years 2020 2021` to warm remote APIs (API keys must be configured).

```bash
make prefetch-cache ARGS="--sources sample --years 2019 2020"
```

## Extensibility Tips

- Pass custom dataframes to `plan_scenario` for programmatic pipelines.
- Extend `ScenarioAdjustment` with new fields (e.g., workforce or capex) and recompute metrics by updating `ScenarioPlanner`.
- Use `result.deltas` and `result.scenario` in notebooks to chart bespoke views; the helper `build_scenario_comparison_table` already prepares tidy tables for display.

With these pieces you can keep the Streamlit experience fast while enabling automated reviews, batch simulations, or integration into wider planning workflows.
