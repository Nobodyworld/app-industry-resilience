# Public Release Validation (Clean Clone)

- Repository: app-economics-idiot-index
- Validation date: 2026-06-22
- Validation mode: local-only (owner policy keeps GitHub Actions disabled in most repositories)
- Host OS: Windows

## Source and clone metadata

- Source URL: https://github.com/Nobodyworld/app-economics-idiot-index
- Validation clone path: C:/Users/Nobod/Documents/GitHub/public-release-validation-app-economics-idiot-index
- Validated commit: 80b144b
- Branch: main

## Runtime and environment

- System Python: 3.14.0
- Clean-clone venv Python: 3.14.0

## Commands executed

1. git clone https://github.com/Nobodyworld/app-economics-idiot-index public-release-validation-app-economics-idiot-index
2. python -m venv .venv
3. ./.venv/Scripts/python.exe -m pip install --upgrade pip
4. ./.venv/Scripts/pip.exe install -r requirements.txt -r requirements-dev.txt
5. ./.venv/Scripts/python.exe -m pytest --version
6. ./.venv/Scripts/python.exe -m pytest -q
7. ./.venv/Scripts/ruff.exe check src tests app.py
8. ./.venv/Scripts/mypy.exe src
9. ./.venv/Scripts/black.exe --check app.py src tests
10. ./.venv/Scripts/python.exe -m pytest --cov=src --cov-report=term-missing --cov-report=xml --cov-fail-under=90
11. ./.venv/Scripts/pip-audit.exe -r requirements.txt -r requirements-dev.txt
12. ./.venv/Scripts/detect-secrets-hook.exe --baseline config/.secrets.baseline

## Results summary

- Dependency installation: PASS
- Build/package install smoke: PASS (no install-time failures)
- Test run (quick): PASS (214 passed)
- Lint (ruff): FAIL
- Type-check (mypy): PASS
- Format check (black --check): PASS
- Coverage gate: FAIL (required >= 90, measured 75.02)
- Dependency audit (pip-audit): FAIL (1 known vulnerability)
- Secret scan baseline check: FAIL (Invalid baseline)
- Packaging artifact build: NOT EXECUTED in this validation pass
- Application smoke test: PARTIAL (covered by test suite and dependency install; interactive Streamlit boot not run in clean clone)

## Notable failing details

### Ruff

- UP042 in src/application/idiot_index_service.py (StrEnum modernization)
- UP042 in src/core/config.py (StrEnum modernization)
- I001 import order in src/infrastructure/rate_limiter.py
- I001 import order in src/scripts/observability_snapshot.py

### Coverage

- Command failed gate: pytest --cov=src --cov-fail-under=90
- Measured total coverage: 75.02%

### pip-audit

- Package: black 25.12.0
- Finding: CVE-2026-32274
- Fixed version listed: 26.3.1

### detect-secrets

- Command failed with: Invalid baseline
- Baseline path used: config/.secrets.baseline

## Remaining limitations before release candidate

- Resolve lint findings in ruff.
- Raise or re-scope tested surface to satisfy the declared 90% coverage gate truthfully.
- Resolve detect-secrets baseline compatibility so secret checks are reproducible in clean clone on Windows.
- Decide dependency strategy for black vulnerability remediation while preserving formatting/toolchain compatibility.

## Status

KEEP PRIVATE
