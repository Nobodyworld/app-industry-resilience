# Stage 1 – Environment & Context Detection

## Languages, Frameworks, Tooling
- **Primary language:** Python 3 (CI targets 3.9–3.11).
- **Application framework:** Streamlit dashboard served from `app.py`.
- **Data/visualization stack:** pandas, Plotly, requests.
- **Configuration helpers:** python-dotenv for `.env` loading.

## Dependency & Build Management
- Uses `pip` with pinned dependencies in `requirements.txt` and development tooling in `requirements-dev.txt` (black, flake8, mypy, pytest-cov, types-requests).
- No pyproject/poetry; packaging is app-centric.
- Dockerfile builds a Streamlit image (Python base with pip installs).

## Repository Structure
- Root entrypoint: `app.py` (Streamlit UI wiring).
- Core modules under `src/` (config, caching, normalization, metrics, security, logging, rate limiting, source connectors, UI helpers, utilities).
- Assets in `assets/`; sample datasets in `data/`.
- Automated tests in `tests/` covering config, core logic, logging, security, and UI helpers.
- Documentation under `docs/`; includes existing user guides.
- `.env.example` for environment variable reference.
- `.github/workflows/ci.yml` defines lint/type/test CI on push & PR.

## Conventions & Quality Gates
- **Linting:** flake8 with max line length 120 and complexity ≤10.
- **Formatting:** black listed as dependency but not enforced in CI.
- **Typing:** mypy (`--ignore-missing-imports`) runs in CI; project uses type hints in `src/`.
- **Testing:** pytest with coverage (`pytest tests/ -v --cov=src`).
- **CI/CD:** GitHub Actions `CI` workflow installs prod + dev requirements, runs flake8, mypy, pytest, uploads coverage to Codecov.

## Observations
- Development requirements file lacks trailing newline on the `types-requests` entry.
- CI workflow's final `fail_ci_if_error` line lacks newline; otherwise standard.
- No `pyproject.toml`; rely on requirements files and manual tooling invocation.

