# Idiot Index Clean Architecture Alignment

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Maintain this ExecPlan per `.agent/PLANS.md`.

## Purpose / Big Picture

The Idiot Index app currently spreads orchestration logic across the Streamlit entrypoint and the agent toolkit. This plan introduces an explicit application layer that encapsulates domain orchestration (fetching datasets, computing metrics, deriving leaderboards) so that both the UI and automation surfaces depend on shared, testable services. The outcome is a codebase that matches the documented layered architecture, enforces dependency direction, and improves maintainability.

After implementation a contributor should be able to:

- Import a single service from `src.application` to run the Idiot Index computation for any data source without touching Streamlit or agent modules.
- Observe that both `app.py` and `src/agents/idiot_index.py` delegate to that service while focusing on presentation- or schema-specific responsibilities.
- Run the test suite to validate behaviour, including new unit tests covering the application layer.

## Progress

- [x] (2025-10-24 01:22Z) Draft ExecPlan capturing goals, context, and planned milestones.
- [x] (2025-10-24 01:28Z) Implement application service module with shared orchestration logic and accompanying tests.
- [x] (2025-10-24 01:28Z) Refactor agents and Streamlit entrypoint to consume the new service and remove duplicated logic.
- [x] (2025-10-24 01:30Z) Run quality gate (`make check`) and finalise documentation/retrospective updates.

## Surprises & Discoveries

- Discovery: Streamlit sidebar allows runtime API key overrides independent of `AppConfig`.
  Evidence: Needed to derive a per-request config via `dataclasses.replace` before invoking `evaluate_idiot_index`.

## Decision Log

- Decision: Retain UI-level filtering while centralising computation in the application service.
  Rationale: Streamlit's interactive search box manipulates session state each rerun; keeping filtering in the UI avoids double evaluation while agents rely on the service filter.
  Date/Author: 2025-10-24 / gpt-5-codex

## Outcomes & Retrospective

- Application services now back the Streamlit UI and agent surface with shared orchestration logic, reducing duplication and ensuring future changes propagate consistently. All tests and quality checks pass, and documentation reflects the new layer.

## Context and Orientation

The repository already documents a layered architecture (`core`, `adapters`, `infrastructure`, `interfaces`, `agents`), but orchestration logic that should live in an "application" layer is duplicated:

- `app.py` contains functions to fetch BEA/Census/sample data, normalise, compute metrics, and derive UI state. It imports adapters and core utilities directly, blurring presentation and orchestration concerns.
- `src/agents/idiot_index.py` reimplements similar fetching, normalisation, and filtering logic for headless usage. It depends on adapters and core modules in parallel to the UI, increasing maintenance cost.
- There is no shared interface for data retrieval; dependency direction flows from UI/agents directly to adapters and infrastructure.

The goal is to introduce `src/application/` to host orchestrators that sit between domain logic (`src/core`) and external surfaces (`app.py`, `src/agents/`). This aligns with Clean Architecture by keeping the UI and automation layers thin and directing all use cases through clearly defined interfaces. New tests should target this application layer to guarantee behaviour without exercising Streamlit.

## Plan of Work

1. **Establish application layer structure.** Create a new `src/application/` package with an `__init__.py` that re-exports public services. Document the purpose in module docstrings to guide contributors.
2. **Implement Idiot Index service module.** Add `src/application/idiot_index_service.py` that defines:
   - A `DataSource` enum covering `sample`, `bea`, and `census`.
   - Dataclasses for `IndustryMetrics` (leaderboard entry) and `IdiotIndexSummary` (full orchestration result, including full dataframe, filtered dataframe, leaderboard, benchmark values, and notes).
   - Pure functions `evaluate_idiot_index` (or similar) that accept sanitised parameters plus optional dependency injection hooks for data fetchers and sample loader. The function should rely on core utilities (`load_config`, `SecurityUtils`, `compute_metrics`, `normalize_columns`, `format_for_display`) and capture logging hooks by delegating to infrastructure functions passed as callables to avoid hard dependencies.
   - Helper functions (e.g., `_load_dataset`, `_filter_frame`, `_build_leaderboard`) kept private to maintain clarity and ensure reusability in tests.
3. **Unit tests for the application layer.** Add `tests/test_application.py` (or similar) to exercise the service in isolation using pandas fixtures and stub fetchers. Validate behaviour for sample datasets, search filtering, leaderboard trimming, and metadata propagation. Ensure tests assert dependency injection behaviour (e.g., custom fetcher invoked, search sanitised).
4. **Refactor agents to consume the service.** Update `src/agents/idiot_index.py` to import `DataSource` and the new service. Replace duplicated fetch/filter/metric logic with calls to the application layer, adapting the returned `IdiotIndexSummary` into existing agent dataclasses (`IndustrySnapshot`, `IdiotIndexResponse`). Ensure metadata mapping (notes, averages) remains intact. Retain dataclass metadata for schema generation.
5. **Refactor Streamlit entrypoint.** Update `app.py` to use the new service for BEA/Census/Sample paths. Remove redundant helper functions (`try_fetch_*`, etc.) where they become thin wrappers. Ensure UI-specific logic (Session State management, download preparation, charts) stays within Streamlit layer, while data acquisition/metrics rely on the shared service. Confirm file upload handling still performs security checks before handing data to the service (the service may receive a pre-loaded dataframe for uploads).
6. **Fix existing layering blemishes.** Address syntax issues uncovered during review, notably the missing module docstring opening quotes in `src/interfaces/streamlit/bootstrap.py` and missing `json` import/docstring in `src/core/cache.py`. Verify other compatibility shims remain intact.
7. **Documentation alignment.** If necessary, update `docs/handbook/ARCHITECTURE.md` and/or `README.md` to mention the new application layer and how UI/agents depend on it.
8. **Validation.** Run `make check` to execute linting, tests, and type checks. Capture relevant excerpts for documentation.

## Concrete Steps

1. Create `src/application/__init__.py` and `src/application/idiot_index_service.py` with the described API. Ensure module docstrings explain responsibilities and dependencies. Implement dependency injection points for fetchers, sample loader, and logging callbacks (defaulting to infrastructure functions).
2. Add unit tests under `tests/test_application.py` covering:
   - Sample dataset evaluation (no search, default top_n).
   - Search filtering and leaderboard trimming.
   - Propagation of metadata and benchmark calculation.
   - Dependency injection (custom fetcher for BEA/Census raising when API keys absent).
3. Update `src/agents/idiot_index.py` to reuse the new service. Remove duplicate `_load_dataset` and `_filter_dataset` helpers, mapping service results into agent responses. Ensure exported API remains unchanged for callers.
4. Refactor `app.py` to construct a `DataSource` enum based on sidebar selection and delegate to the service. For uploaded CSVs, normalise columns and pass the dataframe to a helper that invokes the service with a "custom" dataset path (e.g., new service function to accept existing dataframe). Keep UI state, downloads, and charts unchanged otherwise.
5. Correct layering blemishes: add the missing opening triple quotes to `src/interfaces/streamlit/bootstrap.py` and import `json` at the top of `src/core/cache.py`, adding a module docstring clarifying intent.
6. Update architecture documentation if needed to mention the new application layer.
7. Run `make check` from the repository root. If runtime is excessive, run targeted commands (`pytest`, `ruff`, `mypy`) and document reasoning.

## Validation and Acceptance

- `pytest` (or `make test`) should pass, including new application-layer tests that fail on the previous code structure.
- `make check` completes successfully, demonstrating formatting, linting, type checking, security scans, and unit tests remain green.
- Manual smoke test (optional) by running `streamlit run app.py` and confirming dataset loads still work via sample mode (documented but not mandatory if automated tests suffice).

## Idempotence and Recovery

- New modules and tests are additive; rerunning the steps is safe.
- Refactors should maintain backwards-compatible imports. If regressions appear, revert the commits touching `app.py` or `src/agents/idiot_index.py` while leaving the new application layer in place for incremental adoption.

## Artifacts and Notes

- Capture key test outputs (e.g., snippets from `pytest` and `make check`) in the final PR summary.
- Document any new environment variables or configuration toggles introduced (none anticipated currently).

## Interfaces and Dependencies

- `src/application/idiot_index_service.evaluate_idiot_index` should expose the signature:

    def evaluate_idiot_index(
        *,
        year: int,
        source: DataSource,
        search: str | None = None,
        top_n: int = 5,
        dataframe: pd.DataFrame | None = None,
        config: AppConfig | None = None,
        fetch_bea: Callable[[str, int], pd.DataFrame] = fetch_go_ii_by_industry,
        fetch_census: Callable[[str, int], pd.DataFrame] = fetch_asm_manufacturing,
        sample_loader: Callable[[], pd.DataFrame] | None = None,
        logger_hooks: IdiotIndexLoggerHooks | None = None,
    ) -> IdiotIndexSummary

  where `IdiotIndexLoggerHooks` is a dataclass or protocol bundling optional callables (`log_performance`, `log_data_processing`). The function raises descriptive `ValueError` exceptions when API keys are missing or inputs invalid.

- `IdiotIndexSummary` dataclass should include fields:

    dataframe_full: pd.DataFrame
    dataframe_filtered: pd.DataFrame
    leaderboard: tuple[IndustryMetrics, ...]
    benchmark: Mapping[str, float | None]
    notes: tuple[str, ...]

- `IndustryMetrics` should expose:

    industry_code: str
    industry_name: str
    idiot_index: float | None
    value_added_pct: float | None
    materials_share_pct: float | None
    gross_output: float | None
    value_added: float | None

- Provide helper `sanitize_search(search: str | None) -> str | None` and `resolve_dataframe(...)` functions to keep logic small and testable.

