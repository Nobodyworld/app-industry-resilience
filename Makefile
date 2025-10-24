.PHONY: help install pre-commit-install setup format format-check lint typecheck test coverage check pre-commit clean security sbom docs

PYTHON := python
SKIP_PIP ?= 0
PACKAGE_PATHS := app.py src tests
REPORT_DIR := build/reports
SBOM_DIR := build/sbom
SBOM_FILE := $(SBOM_DIR)/cyclonedx.json
SBOM_REQUIREMENTS := requirements.txt requirements-dev.txt

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
        @echo "  check              Run repository-wide quality checks"
        @echo "  docs               Show key architecture and workflow documentation"

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
		pytest --cov=src --cov-report=term-missing --cov-report=xml; \
	else \
		echo 'pytest-cov not installed; running pytest without coverage'; \
		pytest; \
	fi

pre-commit:
	@if command -v pre-commit >/dev/null 2>&1; then \
		pre-commit run --all-files --show-diff-on-failure --color=always; \
	else \
		echo "pre-commit not found; running local quality checks"; \
		${PYTHON} scripts/run_quality_checks.py; \
	fi

check:
	$(MAKE) pre-commit
	$(MAKE) security
	@if python -c "import importlib.util; import sys; sys.exit(0 if importlib.util.find_spec('pytest_cov') else 1)" >/dev/null 2>&1; then \
		pytest --cov=src --cov-report=term-missing --cov-report=xml; \
	else \
		pytest; \
	fi

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
        @echo "  docs/API_REFERENCE.md"
        @echo "  docs/WORKFLOWS_DATA_REFRESH.md"
        @echo "  docs/DEPENDENCIES.md"

clean:
        rm -rf .mypy_cache .pytest_cache .ruff_cache .coverage coverage.xml htmlcov node_modules
