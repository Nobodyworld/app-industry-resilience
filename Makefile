.PHONY: help install pre-commit-install setup format format-check lint typecheck test coverage check pre-commit clean security sbom docs scenario prefetch-cache analytics observability audit quality-gate

PYTHON := python
SKIP_PIP ?= 0
PACKAGE_PATHS := app.py src tests
REPORT_DIR := build/reports
SBOM_DIR := build/sbom
SBOM_FILE := $(SBOM_DIR)/cyclonedx.json
SBOM_REQUIREMENTS := requirements.txt requirements-dev.txt
COVERAGE_THRESHOLD ?= 90

help:
	@echo "Available targets:"
	@echo "  install            Install runtime and development dependencies"
	@echo "  pre-commit-install Install git hooks"
	@echo "  setup              Install dependencies and configure hooks"
	@echo "  format             Auto-format code using Black"
	@echo "  format-check       Verify formatting without modifying files"
	@echo "  lint               Run Ruff lint checks"
	@echo "  typecheck          Run mypy static type checks"
	@echo "  test               Execute pytest suite"
	@echo "  coverage           Generate XML coverage report"
	@echo "  pre-commit         Run all pre-commit hooks against the repository"
	@echo "  quality-gate       Run linting, type checks, tests w/ coverage, and security scans"
	@echo "  check              Backwards-compatible alias for quality-gate"
	@echo "  docs               Show key architecture and workflow documentation"
	@echo "  scenario           Run the scenario planner CLI (pass extra args via ARGS=...)"
	@echo "  prefetch-cache     Warm caches using the prefetch utility (pass extra args via ARGS=...)"
	@echo "  analytics          Generate health analytics JSON (pass extra args via ARGS=...)"
	@echo "  observability      Print observability registry snapshot (pass extra args via ARGS=...)"
	@echo "  observability-tail Follow observability events from the registry (pass extra args via ARGS=...)"
	@echo "  extensions-catalog List registered extensions (pass extra args via ARGS=...)"
	@echo "  audit              Compute stewardship audit metrics (pass extra args via ARGS=...)"
	@echo "  api                Launch the headless API service (pass extra args via ARGS=...)"

install:
	@if [ "${SKIP_PIP}" = "1" ]; then \
	echo "Skipping pip installation because SKIP_PIP=1"; \
	else \
	${PYTHON} -m pip install --upgrade pip; \
	pip install -r requirements.txt -r requirements-dev.txt; \
	fi

pre-commit-install:
	@if command -v pre-commit >/dev/null 2>&1; then \
	pre-commit install; \
	pre-commit install --hook-type commit-msg; \
	else \
	echo "pre-commit binary not found; skipping hook installation"; \
	fi

setup: install pre-commit-install

format:
	black ${PACKAGE_PATHS}

format-check:
	black --check ${PACKAGE_PATHS}

lint:
	ruff check ${PACKAGE_PATHS}

typecheck:
	${PYTHON} -m mypy src

test:
	pytest

coverage:
	@if python -c "import importlib.util; import sys; sys.exit(0 if importlib.util.find_spec('pytest_cov') else 1)" >/dev/null 2>&1; then \
		pytest --cov=src --cov-report=term-missing --cov-report=xml --cov-fail-under=$(COVERAGE_THRESHOLD); \
	else \
		echo 'pytest-cov not installed; using trace-based coverage fallback'; \
		$(PYTHON) scripts/run_tests_with_trace.py --threshold=$(COVERAGE_THRESHOLD); \
	fi

pre-commit:
	@if command -v pre-commit >/dev/null 2>&1; then \
	pre-commit run --all-files --show-diff-on-failure --color=always; \
	else \
	echo "pre-commit not found; running local quality checks"; \
	${PYTHON} scripts/run_quality_checks.py; \
	fi

quality-gate:
	$(MAKE) format-check
	$(MAKE) lint
	$(MAKE) typecheck
	@if python -c "import importlib.util; import sys; sys.exit(0 if importlib.util.find_spec('pytest_cov') else 1)" >/dev/null 2>&1; then \
		pytest --cov=src --cov-report=term-missing --cov-report=xml --cov-fail-under=$(COVERAGE_THRESHOLD); \
	else \
		echo 'pytest-cov not installed; using trace-based coverage fallback'; \
		$(PYTHON) scripts/run_tests_with_trace.py --threshold=$(COVERAGE_THRESHOLD); \
	fi
	$(MAKE) security

check: quality-gate

security:
	@mkdir -p $(REPORT_DIR)
	@if python -c "import importlib.util; import sys; sys.exit(0 if importlib.util.find_spec('pip_audit') else 1)" >/dev/null 2>&1; then \
	$(PYTHON) -m pip_audit -r requirements.txt -r requirements-dev.txt --format json --output $(REPORT_DIR)/pip-audit.json; \
	else \
	echo 'pip-audit not installed; skipping vulnerability scan'; \
	fi
	@if command -v detect-secrets-hook >/dev/null 2>&1; then \
	detect-secrets-hook --baseline .secrets.baseline; \
	elif python -c "import importlib.util; import sys; sys.exit(0 if importlib.util.find_spec('detect_secrets') else 1)" >/dev/null 2>&1; then \
	$(PYTHON) -m detect_secrets scan --all-files --json --output $(REPORT_DIR)/.detect-secrets.scan.json; \
	echo 'detect-secrets baseline comparison requires manual review (hook binary unavailable).'; \
	else \
	echo 'detect-secrets not installed; skipping secret scan'; \
	fi

sbom:
	@mkdir -p $(SBOM_DIR)
	@if [ -x scripts/generate_sbom.py ]; then \
	$(PYTHON) scripts/generate_sbom.py --output $(SBOM_FILE) $(SBOM_REQUIREMENTS); \
	else \
	echo 'generate_sbom.py missing or not executable'; \
	fi

docs:
	@echo "Core documentation links:"
	@echo "  README.md"
	@echo "  docs/ARCHITECTURE_OVERVIEW.md"
	@echo "  docs/ANALYTICS_HEALTH.md"
	@echo "  docs/API_REFERENCE.md"
	@echo "  docs/WORKFLOWS_DATA_REFRESH.md"
	@echo "  docs/DEPENDENCIES.md"

scenario:
	${PYTHON} scripts/run_scenario.py ${ARGS}

prefetch-cache:
	${PYTHON} scripts/prefetch_data.py ${ARGS}

analytics:
	${PYTHON} scripts/analytics_health.py ${ARGS}

# agent-safe-task: produces observability metrics for agents and operators
observability:
	${PYTHON} scripts/observability_snapshot.py ${ARGS}

# agent-safe-task: streams observability events for incident response
observability-tail:
	${PYTHON} scripts/observability_tail.py ${ARGS}

# agent-safe-task: inventories extension metadata for automation
extensions-catalog:
	${PYTHON} scripts/extensions_catalog.py ${ARGS}

# agent-safe-task: generates stewardship metrics for automated audits
audit:
	${PYTHON} scripts/audit_metrics.py ${ARGS}

api:
	${PYTHON} scripts/run_api.py ${ARGS}

clean:
	rm -rf .mypy_cache .pytest_cache .ruff_cache .coverage coverage.xml htmlcov node_modules
