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

## Sector concentration notes

- Strongest sectors by average health: `42` (wholesale, `93.09`), `44` (retail, `75.96`), `45` (retail subset, `65.12`).
- Weakest sector signal includes `62` (health care) with average health `6.83`.
- Sector `49` shows negative average value-added percent (`-56.66`), suggesting especially unstable cost structure assumptions in that cohort.

## Security and quality checks run

- Formatting: `black --check` passed after auto-format.
- Lint: `ruff check` passed.
- Typing: `python -m mypy src` passed.
- Tests: `pytest -q` passed (`216 passed`).
- Dependency audit: `pip-audit` found 1 vulnerability:
  - `black==25.12.0`, `GHSA-3936-cmfr-pm3m` (`CVE-2026-32274`), fixed in `26.3.1`.
- Secret scan: `detect-secrets` produced 14 unverified findings across 5 files (mostly test fixtures and workflow strings), requiring triage before release sign-off.

## Recommended immediate actions

1. Prioritize mitigation review for the bottom-risk industries in transport and health care cohorts.
2. Upgrade `black` to `26.3.1` after confirming formatter stability across CI and hooks.
3. Triage secret-scan findings and baseline/allowlist intentional test literals.
