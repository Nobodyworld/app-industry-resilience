# Dependency Register

This document records the vetted runtime and development dependencies for the Idiot Index application. Use it during security reviews and upgrade planning.

## Runtime dependencies

| Package | Version | License | Purpose | Review cadence |
| --- | --- | --- | --- | --- |
| `streamlit` | 1.39.0 | Apache-2.0 | Primary UI framework powering the interactive dashboard. | Quarterly |
| `pandas` | 2.2.2 | BSD-3-Clause | Data wrangling, aggregation, and CSV handling. | Quarterly |
| `python-dotenv` | 1.0.1 | BSD-3-Clause | Loads environment variables from `.env` for local development. | Semi-annual |
| `requests` | 2.32.3 | Apache-2.0 | HTTP client for BEA and Census APIs with retry support. | Quarterly |
| `plotly` | 5.24.1 | MIT | Interactive charting components embedded in Streamlit views. | Semi-annual |
| `pytest` | 8.3.3 | MIT | Bundled for lightweight runtime smoke tests and integration with Streamlit cloud deployments. | Quarterly |

## Development dependencies

| Package | Version | License | Purpose | Review cadence |
| --- | --- | --- | --- | --- |
| `black` | 24.10.0 | MIT | Code formatter enforcing repository style. | Quarterly |
| `ruff` | 0.6.9 | MIT | Fast linter covering PyFlakes, pycodestyle, and modernisation rules. | Quarterly |
| `mypy` | 1.11.2 | MIT | Static typing checks for Python modules. | Quarterly |
| `pytest-cov` | 5.0.0 | MIT | Coverage reporting for tests. | Quarterly |
| `pre-commit` | 4.0.1 | MIT | Manages lint/test hooks and commit policy enforcement. | Semi-annual |
| `codespell` | 2.3.0 | GPL-2.0 | Spell checking for docs and comments. | Semi-annual |
| `commitizen` | 3.27.0 | MIT | Conventional Commit automation and version bumping. | Semi-annual |
| `detect-secrets` | 1.4.0 | Apache-2.0 | Secret scanning for commits and CI. | Quarterly |
| `pip-audit` | 2.7.3 | Apache-2.0 | CVE scanning of Python dependency graphs. | Monthly |
| `types-requests` | 2.32.0 | Apache-2.0 | Type hints for the `requests` library used by mypy. | Semi-annual |

## Review process

1. Run `pip-audit` monthly (triggered via `make security`). Document any findings in `REPORTS/` and raise issues for remediation.
2. For quarterly reviews, check upstream release notes for major runtime dependencies (Streamlit, pandas, requests). Smoke-test upgrades locally before bumping versions.
3. Update this file whenever a dependency is added, removed, or upgraded outside its review window.
4. Capture exceptions (e.g., pinning due to upstream regression) in `CHANGELOG.md` and note the revisit date.

## Data sources

- **BEA GDP by Industry** – accessed via API (https://apps.bea.gov/api/). Terms of use require attribution when publishing derived data.
- **Census Annual Survey of Manufactures** – accessed via API (https://www.census.gov/data/developers/data-sets/asm.html). Observe Census data usage policies.
- **Sample dataset** – derived from public BEA/ASM releases for offline demos; stored in `data/sample_industries.csv`.

---
Licensed under the repository's proprietary terms. See [LICENSE](../LICENSE).
