# Data Refresh Workflow

This guide explains how to refresh the Idiot Index datasets, rotate API keys, and validate the results before publishing updates.

## 1. Prepare credentials and configuration

1. Request updated BEA and Census ASM API keys if they changed.
2. Store keys in your `.env` file (`BEA_API_KEY`, `CENSUS_API_KEY`). Do **not** commit secrets.
3. Review `src/core/config.py` for supported year ranges. Adjust if new data releases require extending the range.

## 2. Update bundled datasets (optional)

1. Replace `data/sample_industries.csv` with the refreshed dataset if you want the offline demo to mirror the latest metrics.
2. Run `python scripts/validate_sample_dataset.py` (or `pytest tests/test_sample_dataset.py` if added) to ensure schema compliance.
3. Document the refresh in `CHANGELOG.md` and, if applicable, `docs/DEPENDENCIES.md` under "Data sources".

## 3. Validate adapters

1. Run targeted adapter tests:
   ```bash
   pytest tests/test_adapters_bea.py -k "not slow"
   pytest tests/test_adapters_census.py
   ```
2. If new variables are required, update the adapter table definitions and extend coverage in the corresponding test modules.
3. Confirm logs show healthy endpoint checks (`log_api_call`, `log_performance`). Investigate warnings about retries or degraded endpoints.

## 4. Smoke-test the Streamlit UI

1. Launch the app: `streamlit run app.py`.
2. Verify each data source:
   - **Sample:** Should load instantly with the offline dataset banner.
   - **BEA:** Sidebar fetch indicator should progress from info to success with fresh data.
   - **Census ASM:** Should display success messaging and updated metrics for the selected year.
3. Capture screenshots for regression history if UI changes accompany the refresh.
4. Optionally launch the headless API (`make api`) and call `POST /evaluate` with the refreshed dataset to verify automation clients observe the same metrics.

## 5. Update documentation & changelog

- Note the refresh in `CHANGELOG.md` and mention any schema changes.
- Update `docs/API_REFERENCE.md` if public adapter signatures changed.
- Add operational notes to `REPORTS/` if the refresh required manual steps worth preserving.

## 6. Run the full quality gate

```bash
make check
```

Address any linting, typing, or security findings before publishing. Review `build/reports` for vulnerability scan artifacts if `pip-audit` ran.

## 7. Ship confidently

- Merge the update using Conventional Commits.
- Tag a release via Commitizen (`cz bump --increment minor`) if the refresh materially changes outcomes.
- Monitor BEA/ASM dashboards for discrepancies immediately after deployment.

---
Licensed under the repository's proprietary terms. See [LICENSE](../LICENSE).
