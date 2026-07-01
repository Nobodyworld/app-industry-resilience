# Public Release Validation (Clean Clone)

- Repository: app-economics-idiot-index
- Validation date: 2026-06-29
- Validation mode: local clean clone of remote main
- Host OS: Windows

## Source and clone metadata

- Source URL: <https://github.com/Nobodyworld/app-economics-idiot-index>
- Validation clone path: C:/Users/Nobod/Documents/GitHub/public-release-validation-app-economics-idiot-index
- Validated commit: 32a76a5
- Branch: main

## Runtime and environment

- Clean-clone Python: 3.14.0
- Packaging policy target: Python 3.13+

## Commands executed

1. git clone <https://github.com/Nobodyworld/app-economics-idiot-index> public-release-validation-app-economics-idiot-index
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
12. ./.venv/Scripts/python.exe -m pytest --cov=src/scripts --cov-report=term-missing -q
13. ./.venv/Scripts/pip-audit.exe -r requirements.txt -r requirements-dev.txt
14. ./.venv/Scripts/detect-secrets-hook.exe --baseline config/.secrets.baseline
15. ./.venv/Scripts/python.exe src/scripts/run_scenario.py --adjust "codes=311,gross=5,materials=-3" --top 5 --output build/reports/scenario_smoke.json
16. ./.venv/Scripts/python.exe -m streamlit run app.py --server.headless true --server.port 8501 and HTTP probe of <http://127.0.0.1:8501>
17. ./.venv/Scripts/python.exe src/scripts/run_api.py --host 127.0.0.1 --port 9011 and HTTP probes of <http://127.0.0.1:9011/health> and <http://127.0.0.1:9011/metrics>
18. Repository-only markdown link scan (excluding .venv): BROKEN_LINKS=0
19. docker --version (container tool availability check)

## Results summary

- Dependency installation: PASS
- Dependency integrity (pip check): PASS
- Lint (ruff): PASS
- Format check (black --check): PASS
- Type-check (mypy): PASS
- Test suite: PASS (246 passed)
- Runtime coverage gate (policy paths): PASS (86.60%, threshold 85)
- Full src coverage informational: PASS (80% informational)
- Scripts coverage informational: PASS (58% informational)
- Dependency audit (pip-audit): PASS (No known vulnerabilities found)
- Secret scan baseline check: PASS (exit code 0)
- Scenario workflow smoke: PASS (report written to build/reports/scenario_smoke.json)
- Streamlit smoke: PASS (HTTP 200 on localhost)
- API smoke: PASS (health=200, metrics=200)
- Export smoke (CSV/JSON/XLSX): PASS (XLSX mime present)
- Markdown links (repository-only): PASS (BROKEN_LINKS=0)
- Docker build capability: NOT AVAILABLE ON HOST (docker CLI not installed)

## Disposition

All P0 software-quality and release-gate checks in clean clone passed for commit 32a76a5.

## Status

READY FOR PUBLIC RELEASE (host Docker build not executed because Docker is unavailable on this validator machine)
