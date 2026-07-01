# U.S. Industry Cost Structure Dashboard

This project is a Streamlit and headless API application for exploring U.S. industry cost-structure ratios. It computes the informal "Idiot Index" ratio, supports scenario recalculation, and includes a public-data readiness foundation for reproducible no-auth source collection and rolling baseline checks.

The application is analytical tooling, not an economic distress classifier. Composite score outputs are experimental heuristics derived from correlated cost-structure inputs.

## Demonstration

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open the local Streamlit URL and use the bundled sample dataset for an offline walkthrough. The same core service can be exercised through the API with `python src/scripts/run_api.py`.

## Quick Start

Requires Python 3.13 or newer.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Optional live government adapters use environment variables:

```bash
BEA_API_KEY=...
CENSUS_API_KEY=...
```

Public readiness commands for no-auth sources:

```bash
python src/scripts/public_data_readiness.py catalog --pretty
python src/scripts/public_data_readiness.py listen --dataset-id bls_ppi_monthly --storage-root build/public-smoke
python src/scripts/public_data_readiness.py backfill --dataset-id bls_ppi_monthly --start-year 2023 --end-year 2024 --storage-root build/public-smoke --dry-run --pretty
```

## Core Features

- Streamlit dashboard for sample, BEA, Census ASM, uploaded CSV, and official snapshot workflows.
- Headless API for evaluation, scenarios, analytics, metrics, and observability probes.
- Normalization and metric computation for `industry_code`, `industry_name`, `year`, `gross_output`, `materials_cost`, `intermediate_inputs`, and `value_added`.
- Scenario Lab recalculation for stated percentage shocks.
- Public-data readiness catalog, release manifests, duplicate/revision guardrails, AIES backfill, BLS PPI monthly signal backfill, listener checks, and a naive rolling previous-period baseline.

## Methodology Limitations

- "Idiot Index" is an informal ratio: `gross_output / materials_cost` or `gross_output / intermediate_inputs` when materials are unavailable.
- Census AIES output uses a revenue-to-operating-expense proxy and is not the strict BEA gross-output-to-intermediate-inputs ratio.
- The composite score is experimental and heuristic. Several components are algebraic transformations of the same output/input relationship, so the bands do not independently prove industry health, resilience, or economic distress.
- Neutral composite bands are used: `lower_input_intensity`, `moderate_input_intensity`, `higher_input_intensity`, and `review_required`.
- GDELT and similar event feeds are contextual signals only and must not be treated as economic ground truth.

## Data Provenance

Implemented public readiness sources:

- Census AIES annual archive: keyless Census ZIP files, cleaned into the existing annual industry proxy schema.
- BLS PPI monthly signal: no-key BLS public API series `PCU311111311111`, mapped only to documented NAICS `311111` from the embedded PCU industry code.

Cataloged roadmap sources are not automatically implemented or verified. Check implementation status with:

```bash
python src/scripts/public_data_readiness.py catalog --pretty
```

Backfill outputs are designed for local or external storage and should not be committed when large:

```text
data/public/
  raw/<dataset_id>/<release_id>/
  cleaned/<dataset_id>/<release_id>/
  manifests/<dataset_id>/<release_id>.json
```

## Architecture Summary

```text
adapters/public sources -> core normalization + metrics -> application services
                                                     |-> Streamlit UI
                                                     |-> headless API
                                                     |-> scripts and agent wrappers
```

Key modules:

- [src/core](src/core/README.md) for normalization, metrics, analytics, cache, and public-data manifest primitives.
- [src/adapters](src/adapters) for source-specific data access.
- [src/application](src/application) for orchestration, scenarios, public backfill, and rolling backtests.
- [src/interfaces](src/interfaces) for Streamlit and API surfaces.
- [src/scripts](src/scripts/README.md) for operator and validation commands.

## Verification Evidence

Primary local validation commands:

```bash
python -m black --check app.py src tests
python -m ruff check app.py src tests
python -m mypy src
python -m pytest -q
python src/scripts/run_quality_checks.py --fast
git diff --check
```

Security and coverage gates are documented in [docs/PUBLIC_RELEASE_VALIDATION.md](docs/PUBLIC_RELEASE_VALIDATION.md) and should be run where `pip-audit`, `detect-secrets`, and `pytest-cov` are installed. Current branch validation should be checked in the pull request report, not inferred from this README.

## Documentation

- [Data dictionary](docs/DATA_DICTIONARY.md)
- [Public data refresh workflow](docs/WORKFLOWS_DATA_REFRESH.md)
- [Analytics methodology](docs/ANALYTICS_HEALTH.md)
- [API reference](docs/API_REFERENCE.md)
- [Headless API guide](docs/API_HEADLESS.md)
- [Architecture overview](docs/ARCHITECTURE_OVERVIEW.md)
- [Operations incident response](docs/OPERATIONS_INCIDENT_RESPONSE.md)
- [Dependency register](docs/DEPENDENCIES.md)

## Docker

```bash
docker build -t idiot-index-app .
docker run -p 8501:8501 idiot-index-app
docker run -e APP_MODE=api -p 9000:9000 idiot-index-app
```

The image uses Python 3.13 and runtime dependencies only. Docker validation status belongs in the branch or release report because it depends on local Docker availability.

## License

Apache License 2.0. See [LICENSE](LICENSE).
