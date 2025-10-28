# Contributing Guide

Thanks for investing time in the Idiot Index project! This guide explains how to set up a development environment, propose changes, and meet the repository's quality standards.

## Core Expectations

- **Preserve behavior** unless you have evidence it is broken. Document any intentional change.
- **Write tests** for every bug fix or feature. Maintain the existing coverage goals.
- **Keep pull requests focused.** Ship reviewable slices; avoid unrelated refactors.
- **Adopt Conventional Commits.** Every commit message must follow the `<type>(optional scope): <subject>` format using the types enforced by `scripts/commitlint.py`.
- **Run the full quality suite** (`make quality-gate`) before opening a pull request.
- **Document significant work with an ExecPlan.** Place plans under `.agent/execplans/` so reviewers can trace decisions.

## Prerequisites

- Python 3.11 or newer.
- `pip` and `make` available on your PATH.

## First-time Setup

From the repository root:

```bash
make setup
```

`make setup` upgrades `pip`, installs runtime + development dependencies, and registers the `pre-commit` hooks (including the `commit-msg` hook that enforces Conventional Commits).

If you prefer to perform the steps manually:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
pre-commit install
pre-commit install --hook-type commit-msg
```

> **Offline note:** When external package indexes are inaccessible, run `SKIP_PIP=1 make setup`. The quality targets automatically fall back to the Python scripts in `scripts/` when the `pre-commit` binary is unavailable.

## Development Workflow

1. Create a feature branch (`git checkout -b feat/add-cool-thing`).
2. Make your changes.
3. Run the local quality gate:

   ```bash
   make quality-gate
   ```

   `make quality-gate` runs Black (check mode), Ruff, mypy, pytest with coverage enforcement (`--cov-fail-under=90`), and the security gate (`pip-audit` + `detect-secrets`). This mirrors the CI workflow so failures are caught locally.

4. Run additional focused commands as needed:

   ```bash
   make format        # Apply auto-formatting
   make lint          # Ruff checks without auto-fixing
   make typecheck     # Run mypy directly
   make test          # Run pytest without coverage
   make security      # Run pip-audit and detect-secrets checks
   make sbom          # Build a CycloneDX SBOM for dependencies
   make audit         # Generate stewardship metrics (coverage, complexity, dependency graph)
   make docs          # List key documentation links in the terminal
   ```

The helper scripts invoked by these targets now auto-bootstrap the repository root onto `PYTHONPATH`, so you can run
`python scripts/<name>.py` directly without installing the project as a package.

5. Commit using Conventional Commits. The `commit-msg` hook will reject messages that do not comply.
6. Push and open a pull request using the provided template.

## Pull Request Checklist

Before requesting a review, verify that:

- `make quality-gate` passes locally.
- Documentation is updated when behavior changes or new workflows are introduced.
- New or changed configuration is explained in PR notes (feature flags, environment variables, migrations).
- Screenshots are attached for UI changes.

### Extensions, Services & Telemetry

- Use the scaffolds to keep new modules consistent:
  - `python scripts/scaffold_extension.py --name <name> --with-scenario --instrumentation` seeds summary/scenario/instrumentation hooks and updates `extensions/manifest.json`.
  - `python scripts/scaffold_service.py --name <service>` creates an observability-aware service skeleton under `src/application/services/`.
- Instrumentation extensions should subscribe to events on the shared `ObservabilityRegistry` instead of mutating core services. The reference implementation lives in `src/extensions/builtins/core_instrumentation.py`.
- Use `src/extensions/builtins/data_quality.py` as a second example of instrumentation that listens for dataset/scenario profile events, emits gauges, and registers health checks. Run `make extensions-catalog` to confirm your module appears with the expected metadata before publishing.
- When shipping connectors, implement `ConnectorExtension.register` (see `src/extensions/builtins/connector_catalog.py`) and verify catalog output with `make connectors-catalog` so `/meta/connectors` and observability digests stay accurate.
- When adding analytics, prefer creating a module under `src/extensions` using the scaffold above. Add tests mirroring `tests/test_extensions.py`.
- Do not remove or bypass telemetry hooks. If a change impacts `/metrics`, `/observability/status`, `/health`, or trace logging, update `docs/OPERATIONS_INCIDENT_RESPONSE.md` and mention the change in the release notes.

## Code Review

Reviews focus on correctness, clarity, test coverage, performance, and security. Be ready to explain trade-offs and link to design context (e.g., entries in `docs/execplans`). Address feedback promptly and document meaningful decisions in the relevant ExecPlan.

## Releases

Release automation is planned but not yet wired to production deployment. For now, coordinate with maintainers for release tagging. Keep `CHANGELOG.md` up to date by summarizing notable changes per release.

## Getting Help

- Open a GitHub Discussion or issue using the provided templates.
- Tag `@idiot-index/maintainers` in pull requests for review.
- For security-sensitive disclosures, follow the instructions in `SECURITY.md` instead of filing a public issue.

We appreciate every contribution that makes the Idiot Index easier to run, safer to operate, and more insightful for end users!
