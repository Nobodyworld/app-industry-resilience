# Repository Style Guide

> **Canonical style guide:** [`docs/STYLE-GUIDE.md`](docs/STYLE-GUIDE.md)

This root file is retained as a stable entry point for repository policy and automation that expect `STYLE-GUIDE.md` at the repository root. Do not duplicate the full organization-wide guide here.

Repository-specific enforcement is defined by:

- [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md)
- [`pyproject.toml`](pyproject.toml)
- [`Makefile`](Makefile)
- [`config/.pre-commit-config.yaml`](config/.pre-commit-config.yaml)

For this Python project, contributors must use the configured Black, Ruff, mypy, pytest, coverage, vulnerability, and secret-scanning gates through `make quality-gate`. Developer and operational scripts live under `src/scripts/`.
