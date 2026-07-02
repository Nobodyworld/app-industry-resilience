# Public Release Validation (Clean Clone)

- Repository: app-economics-idiot-index
- Validation date: 2026-07-01
- Validation mode: local clean clone of remote main
- Host OS: Windows

## Source and clone metadata

- Source URL: <https://github.com/Nobodyworld/app-economics-idiot-index>
- Validation clone location: workspace-relative ephemeral folder (`build/public-release-validation-final`)
- Validated commit: 2d364a3169961dcec16383261262ba1b5e3a2157
- Branch: main

## Runtime and environment

- Clean-clone Python: 3.14.0
- Packaging policy target: Python 3.13+
- GitHub Actions repository setting: disabled by owner policy (`enabled: false`)

## Commands executed

1. git clone <https://github.com/Nobodyworld/app-economics-idiot-index> build/public-release-validation-final
2. python -m venv .venv
3. ./.venv/Scripts/python.exe -m pip install --upgrade pip
4. ./.venv/Scripts/pip.exe install -r requirements.txt -r requirements-dev.txt
5. ./.venv/Scripts/python.exe -m pip check
6. ./.venv/Scripts/python.exe -m ruff check app.py src tests
7. ./.venv/Scripts/python.exe -m black --check app.py src tests
8. ./.venv/Scripts/python.exe -m mypy src
9. ./.venv/Scripts/python.exe -m pytest -q
10. ./.venv/Scripts/python.exe -m pytest --cov=src/adapters --cov=src/agents --cov=src/application --cov=src/core --cov=src/extensions --cov=src/infrastructure --cov=src/interfaces/api --cov=src/interfaces/streamlit --cov-report=term-missing --cov-report=xml --cov-fail-under=85 -q
11. ./.venv/Scripts/python.exe -m pytest --cov=src --cov-report=term-missing --cov-report=xml -q
12. ./.venv/Scripts/pip-audit.exe -r requirements.txt -r requirements-dev.txt
13. ./.venv/Scripts/detect-secrets-hook.exe --baseline config/.secrets.baseline
14. ./.venv/Scripts/python.exe src/scripts/run_scenario.py --adjust "codes=311,gross=5,materials=-3" --top 5 --output build/reports/scenario_smoke.json
15. ./.venv/Scripts/python.exe src/scripts/public_data_readiness.py backfill --dataset-id bls_ppi_monthly --start-year 2023 --end-year 2024 --storage-root build/public-smoke --pretty
16. ./.venv/Scripts/python.exe src/scripts/public_data_readiness.py backtest --input build/public-smoke/cleaned/bls_ppi_monthly/2024-12/bls_ppi_monthly-ec19de77f94c.csv --target-field signal_value --date-field observation_date --entity-field industry_code --release-field release_period --sections 3 --output build/reports/public_backtest_smoke.json --pretty
17. ./.venv/Scripts/python.exe -m streamlit run app.py --server.headless true --server.port 8503 and HTTP probe of <http://127.0.0.1:8503>
18. ./.venv/Scripts/python.exe src/scripts/run_api.py --host 127.0.0.1 --port 9013 and HTTP probes of <http://127.0.0.1:9013/health> and <http://127.0.0.1:9013/metrics>
19. Export smoke via `src.interfaces.streamlit.helpers.prepare_download_artifacts` (CSV/JSON/XLSX MIME verification)
20. README+docs markdown link validation (internal and external links)
21. Full-history gitleaks scan (`gitleaks git . --log-opts='--all' --report-format json --report-path build/reports/gitleaks-full-history-final.json`)
22. docker --version (container tool availability check)

## Results summary

- Dependency installation: PASS
- Dependency integrity (pip check): PASS
- Lint (ruff): PASS
- Format check (black --check): PASS
- Type-check (mypy): PASS
- Test suite: PASS (271 passed)
- Runtime coverage gate (policy paths): PASS (86.01%, threshold 85)
- Full src coverage informational: PASS (80% informational)
- Dependency audit (pip-audit): PASS (No known vulnerabilities found)
- Secret scan baseline check: PASS (exit code 0)
- Scenario workflow smoke: PASS (report written to build/reports/scenario_smoke.json)
- Public-data backfill/backtest smoke: PASS (artifacts written under build/reports)
- Streamlit smoke: PASS (HTTP 200 on localhost:8503)
- API smoke: PASS (health=200, metrics=200 on 9013)
- Export smoke (CSV/JSON/XLSX): PASS (6 artifacts, expected MIME types present)
- Markdown links (README + docs): PASS (internal broken=0, external broken=0)
- Full-history gitleaks: REVIEWED FINDINGS ONLY (16 detections, all classified false-positive/test-artifact context)
- Docker build capability: NOT AVAILABLE ON HOST (docker CLI not installed)

## Full-History Secret Scan Details

- Tool: gitleaks 8.30.1
- Command: `gitleaks git . --log-opts='--all' --report-format json --report-path build/reports/gitleaks-full-history-final.json`
- Commit range scanned: all reachable history (`git rev-list --all`, 84 commits during scan run)
- Findings: 16
- Finding groups:
	- 14 in `config/.secrets.baseline` (`generic-api-key` rule, hashed detector values)
	- 2 in `tests/test_config.py` (fixture-like key strings used in tests)
- False-positive disposition: accepted as non-credential artifacts; no live credentials, private keys, or tokens detected.
- Final result: PASS FOR PUBLICATION RISK REVIEW (with documented false positives).

## Actions/CI Disposition

Repository GitHub Actions are currently disabled by owner policy. No CI badge or workflow-run claim is used as release proof. Local clean-clone validation is the authoritative release gate evidence.

## Disposition

All required local P0 software-quality and release-gate checks completed successfully for the validated commit listed above. Docker validation was not executable on this host due missing Docker CLI.

## Status

LOCAL VALIDATION PASSED FOR THE RECORDED CLEAN-CLONE RUN. This repository can be presented with clear Docker limitation disclosure until a host with Docker CLI validates container startup.
