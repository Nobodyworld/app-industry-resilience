# Contributing Guide

Thanks for investing time in the Industry Resilience project. This guide explains how to set up a development environment, propose changes, and meet the repository's quality standards.

## Core Expectations

- **Preserve behavior** unless you have evidence it is broken. Document any intentional change.
- **Write tests** for every bug fix or feature. Maintain the existing coverage goals.
- **Keep pull requests focused.** Ship reviewable slices; avoid unrelated refactors.
- **Adopt Conventional Commits.** Every commit message must follow the `<type>(optional scope): <subject>` format using the types enforced by `scripts/commitlint.py`.
- **Run the full quality suite** (`make quality-gate`) before opening a pull request.
- **Document significant work with an ExecPlan.** Place plans under `.agent/execplans/` so reviewers can trace decisions.

## Repository Layout

- `app.py` – Streamlit entrypoint that wires the UI to the application layer.
- `src/` – Production code, including the agent toolkit under `src/agents`, application services, core logic, adapters, interfaces, and infrastructure packages.
- `docs/` – Reference material and runbooks. Long-form governance and release docs live under `docs/handbook/`.
- `docs/execplans/` – Historical ExecPlans documenting major refactors and investigations.
- `extensions/`, `scripts/`, `tests/`, `assets/`, `data/` – Extension modules, automation helpers, test suites, static assets, and sample datasets.

## Prerequisites

- Python 3.13 or newer.
- `pip` and `make` available on your PATH.

## First-time Setup

From the repository root:

```bash
make setup
```

`make setup` upgrades `pip`, installs runtime and development dependencies, and registers the `pre-commit` hooks, including the `commit-msg` hook that enforces Conventional Commits.

For manual setup:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
pre-commit install
pre-commit install --hook-type commit-msg
```

> **Offline note:** When external package indexes are inaccessible, run `SKIP_PIP=1 make setup`. Quality targets fall back to repository scripts when the `pre-commit` binary is unavailable.

## Development Workflow

1. Create a focused feature branch, such as `git checkout -b feat/add-capability`.
2. Make the change and add or update tests.
3. Run the local quality gate:

   ```bash
   make quality-gate
   ```

   `make quality-gate` runs Black in check mode, Ruff, mypy, runtime-scoped pytest coverage enforcement (`make coverage-runtime`, default fail-under 85), an informational full-`src` coverage report, and the security gate (`pip-audit` plus `detect-secrets`). While repository Actions are disabled, this local gate is the authoritative validation path. When Actions are enabled, the hosted workflow should invoke the same target.

4. Run additional focused commands as needed:

   ```bash
   make format        # Apply auto-formatting
   make lint          # Ruff checks without auto-fixing
   make typecheck     # Run mypy directly
   make test          # Run pytest without coverage
   make security      # Run pip-audit and detect-secrets checks
   make sbom          # Build a CycloneDX SBOM for dependencies
   make audit         # Generate stewardship metrics
   make docs          # List key documentation links
   ```

5. Commit using Conventional Commits. The `commit-msg` hook rejects non-compliant messages.
6. Push the branch and open a pull request using the provided template.

## Pull Request Checklist

Before requesting review, verify that:

- `make quality-gate` passes locally.
- Documentation is updated when behavior changes or new workflows are introduced.
- New or changed configuration is explained in PR notes.
- Screenshots are attached for user-interface changes.
- No secrets, generated build output, or large local datasets are included.

### Extensions, Services, and Telemetry

- Use the scaffolds to keep new modules consistent:
  - `python scripts/scaffold_extension.py --name <name> --with-scenario --instrumentation` seeds summary, scenario, and instrumentation hooks and updates `extensions/manifest.json`.
  - `python scripts/scaffold_service.py --name <service>` creates an observability-aware service skeleton under `src/application/services/`.
- Instrumentation extensions should subscribe to events on the shared `ObservabilityRegistry` instead of mutating core services.
- Use `src/extensions/builtins/data_quality.py` as an instrumentation example and run `make extensions-catalog` before publishing extension changes.
- When shipping connectors, implement `ConnectorExtension.register` and run `make connectors-catalog` so `/meta/connectors` and observability digests remain accurate.
- When adding analytics, prefer a module under `src/extensions` and add tests mirroring `tests/test_extensions.py`.
- Do not remove or bypass telemetry hooks. Changes affecting `/metrics`, `/observability/status`, `/health`, or trace logging must update `docs/OPERATIONS_INCIDENT_RESPONSE.md` and the release notes.

## Code Review

Reviews focus on correctness, clarity, test coverage, performance, security, and scope control. Explain meaningful trade-offs and link to relevant ExecPlans where appropriate.

## Releases

Release automation is not yet wired to production deployment. Coordinate release tagging with the repository owner, keep existing tags immutable, and update `CHANGELOG.md` for notable changes.

## Getting Help

- Open an issue using the provided templates; use GitHub Discussions when enabled.
- Request review from `@Nobodyworld`.
- For security-sensitive disclosures, follow [docs/handbook/SECURITY.md](handbook/SECURITY.md) and do not file a public issue.

Thank you for helping make the Industry Resilience dashboard easier to run, safer to operate, and more useful to analysts.
