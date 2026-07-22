# Complete issue 79 lineage integration

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes `.agent/PLANS.md`; this document must be maintained in accordance with that file.

## Purpose / Big Picture

After this change, users can distinguish live BEA and Census data, the official Census AIES snapshot, cached data, and scenario results through one typed and redacted lineage envelope. Downloads expose the same provenance without changing the existing tabular CSV contract: JSON includes top-level `lineage` and `records`, Excel includes a `Lineage` sheet, and each CSV has a lineage JSON companion. The behavior is observable through focused adapter, cache, API, and Streamlit export tests without any live network access.

## Progress

- [x] (2026-07-21 00:00Z) Verified `origin/main` and `origin/architecture/lineage-integration-final` both start at `0b0ebaa76ab108ac8b7352e0da948353cdbc1452`, created the clean isolated worktree, and confirmed its branch and status.
- [x] (2026-07-21 00:00Z) Read issue 79, `docs/API_VERSIONING_AND_LINEAGE.md`, the typed lineage contract, export helpers, and the provider/cache/API/download call paths.
- [x] (2026-07-21 00:00Z) Attached official live-provider and snapshot lineage at BEA, Census ASM, and Census AIES boundaries with deterministic tests.
- [x] (2026-07-21 00:00Z) Preserved allowlisted lineage through API and computation cache misses, hits, legacy payloads, and distinct provider identities with privacy tests.
- [x] (2026-07-21 00:00Z) Added typed scenario response lineage, canonical/legacy parity coverage, and OpenAPI coverage while retaining metadata.
- [x] (2026-07-21 00:00Z) Integrated lineage export helpers into JSON, XLSX, and CSV companion Streamlit artifacts while preserving existing downloads.
- [x] (2026-07-21 00:00Z) Updated exact API and export documentation examples without changing `TASKLIST.md`.
- [x] (2026-07-21 00:00Z) Completed focused/full tests, direct quality-gate constituents, security scans, diff review, Docker availability review, implementation commit `9cd998b`, and non-force push to only `architecture/lineage-integration-final`.

## Surprises & Discoveries

- Observation: The core lineage contract and non-mutating export serialization helpers are already implemented and unit tested, but the application download helper still serializes records directly and writes only the data sheet.
  Evidence: `src/application/lineage_exports.py` provides JSON, CSV companion, and XLSX row helpers; `src/interfaces/streamlit/helpers.py` does not import or call them.
- Observation: Both provider adapters cache records plus provider metadata, while the computation cache stores only records. Neither cache payload currently stores the typed lineage envelope.
  Evidence: `src/adapters/bea.py`, `src/adapters/census_asm.py`, and `src/core/metrics.py` call `Cache.set` with payloads that omit dataframe `lineage`.
- Observation: Computation cache keys originally hashed records only, so identical records from two official providers could have reused the first provider's stored lineage.
  Evidence: `_hash_dataframe` previously serialized only `df.to_dict(orient="records")`; the final implementation includes typed identity while excluding transient cache state and a regression test confirms two cache files.
- Observation: GNU Make and Docker are not installed in this Windows environment, and the global Python environment has an unrelated OpenCV/NumPy package conflict.
  Evidence: `make quality-gate` and `docker version` could not resolve their executables; `pip check` reports OpenCV requires NumPy below 2.3 while global NumPy is 2.3.4. Every Makefile quality-gate constituent was run directly and passed.

## Decision Log

- Decision: Keep source identity in `source` and `source_kind` unchanged on cache hits, using only `retrieval_mode=cache` and `cache_status=hit` to describe the current retrieval.
  Rationale: This is the documented v1 contract and prevents cached official data from being misclassified as a new source.
  Date/Author: 2026-07-21 / Codex
- Decision: Treat legacy cache payloads without lineage as readable compatibility inputs and return them without invented provider timestamps.
  Rationale: Fabricating acquisition provenance would be misleading, while rejecting every existing cache entry would create an unnecessary compatibility break.
  Date/Author: 2026-07-21 / Codex
- Decision: Add CSV lineage as an additional `DownloadArtifact` immediately after its matching CSV and leave existing CSV, JSON, and Excel labels and filenames unchanged.
  Rationale: This preserves current downloads and makes the companion relationship obvious without removing any v1 artifact.
  Date/Author: 2026-07-21 / Codex
- Decision: Include the typed source identity, timestamps, and transformations in computation-cache key material while excluding transient retrieval/cache state.
  Rationale: Identical records from different providers must never share cached lineage, while an API cache hit should still reuse computation results tied to the original acquisition.
  Date/Author: 2026-07-21 / Codex

## Outcomes & Retrospective

The implementation is complete, validated, committed, and published to the requested feature branch. Official provider/snapshot identity now reaches evaluation, scenario, caches, and downloads without copying unrestricted attributes. Cache hits retain original timestamps and transformations, legacy lineage-free payloads remain readable, and computation caches separate distinct source identities. The API and download contracts are additive: scenario metadata remains, CSV remains tabular, and existing artifact labels/files remain alongside lineage companions. No product behavior remains to implement for this plan.

## Context and Orientation

`src/core/lineage.py` defines the immutable `LineageEnvelope`, bounded `LineageStep`, dataframe attachment/parser helpers, and cache-status update behavior. A lineage envelope is an allowlisted provenance record: it identifies a public source and dataset, observation period, acquisition or snapshot time, official/sample truth, ordered transformations, and cache outcome while rejecting secrets, URLs, cache identifiers, and private paths.

`src/adapters/bea.py` and `src/adapters/census_asm.py` are the live official-provider boundaries. They validate remote payloads, normalize records, and use the API cache. `src/adapters/aies.py` builds the official Census Annual Integrated Economic Survey snapshot and knows its survey year and release date. `src/core/metrics.py` computes derived metrics and optionally uses the computation cache.

`src/application/scenario_planner.py` already propagates dataframe lineage across baseline, adjusted scenario, and delta frames. `src/interfaces/api/schemas.py` converts domain results to typed API responses; `ScenarioResponse` lacks the additive lineage field even though evaluation and health responses already expose it. `src/interfaces/api/app.py` owns canonical `/v1/scenario` and deprecated `/scenario` aliases.

`src/application/lineage_exports.py` creates non-mutating export lineage. `src/interfaces/streamlit/helpers.py` materializes CSV, JSON, and Excel `DownloadArtifact` values, and `src/interfaces/streamlit/components.py` renders every artifact as a download button. Integrating at the helper keeps the UI loop and existing labels stable.

## Plan of Work

First, add official source envelopes where provider data becomes a dataframe. BEA will use source `bea`, dataset `gdpbyindustry`, the requested year or ordered year range, the public Bureau of Economic Analysis provider name, one UTC acquisition timestamp, and a bounded source-load count. Census ASM will use source `census`, dataset `asm`, its requested year, the U.S. Census Bureau provider name, and equivalent live retrieval metadata. Census AIES will use source `census`, dataset `aies`, survey year 2023, snapshot retrieval, the known 2026-02-26 release timestamp in UTC, and official snapshot truth. Existing provider metadata remains available, but it is not copied into typed lineage.

Second, serialize only `lineage_to_dict` alongside cached records. On a miss, update the live envelope to `cache_status=miss` without changing `retrieval_mode=live`; on a hit, parse the stored allowlisted envelope and return a copy marked `cache_status=hit` and `retrieval_mode=cache`, preserving the original source, timestamps, and ordered transformations. Legacy mapping or list cache payloads without lineage remain readable and simply have no typed envelope. The computation cache will follow the same envelope-only rule while retaining existing record compatibility.

Third, add `lineage: LineageEnvelopeModel | None` to `ScenarioResponse` and populate it from `result.scenario`, the dataframe containing the scenario adjustment history. The shared scenario response builder continues to serve both canonical and deprecated routes, so payload parity remains centralized. Tests normalize nondeterministic acquisition timestamps and telemetry trace identifiers when comparing route payloads and inspect generated OpenAPI for the additive field.

Fourth, replace direct JSON record serialization in `prepare_download_artifacts` with `build_json_export_document`, add a `Lineage` dataframe from `build_xlsx_lineage_rows` to each workbook, and add one `<base>_<scope>.lineage.json` artifact from `build_csv_lineage_companion` for each existing CSV. Base-name sanitization will remain narrow and will not derive names from uploaded files. Tests will prove both scopes, existing filenames and labels, dedicated workbook sheet, top-level JSON shape, and non-mutation of in-memory lineage.

Finally, document exact provider, cache-hit, scenario, JSON, XLSX, and CSV companion examples in `docs/API_VERSIONING_AND_LINEAGE.md`. Run focused tests during each milestone, then the entire requested validation matrix, inspect the final diff and security-sensitive strings, commit with a conventional message, push without force, and verify the branch worktree is clean and synchronized with origin.

## Concrete Steps

All commands run from `C:\tmp\app-industry-resilience-lineage-final`. Implement and test provider/cache behavior with focused pytest selections for `tests/test_adapters_bea.py`, `tests/test_adapters_census_caching.py`, snapshot tests, and computation-cache tests. Implement and test API behavior with scenario and compatibility test modules. Implement and test exports with `tests/test_streamlit_helpers.py` and `tests/test_lineage_exports.py`.

Before committing, run `python --version`, `black --check app.py src tests`, `ruff check app.py src tests`, `python -m mypy src`, `pytest -q`, `make quality-gate`, `git diff --check`, `git status --short`, `pip check`, and the repository security/secret-scan target discovered from the Makefile. Check Docker availability and run the repository smoke target only when the daemon and tool are usable. Record exact results in this document.

## Validation and Acceptance

Focused tests must show BEA and Census live frames have official live lineage, AIES has official snapshot lineage, misses preserve live retrieval mode, hits preserve source/timestamps/history while switching only bounded cache state, and legacy lineage-free cache entries do not raise accidental exceptions. Serialized cache payload assertions must show no API keys, provider payloads, cache keys or directories, Redis URLs, credentials, or private paths.

API tests must show scenario responses contain typed lineage and existing metadata, canonical and deprecated payloads match after normalizing request-time timestamps and telemetry IDs, and OpenAPI exposes `ScenarioResponse.lineage`. Export tests must show JSON has exactly stable top-level lineage and records fields, Excel retains `Cost Structure` plus `Lineage`, CSV remains tabular and gains correctly named companions, existing download artifacts remain present, and serialization leaves dataframe lineage unchanged.

The full quality gate and standalone commands must exit successfully. Docker unavailability is reportable rather than a code blocker. The final branch must be pushed without force, match its upstream, and have a clean status.

## Idempotence and Recovery

All source edits and tests are confined to the isolated worktree. Provider tests mock network calls. Cache tests use temporary directories. Re-running tests and format checks is safe. If a cache payload lacks lineage, code follows the explicit legacy compatibility path rather than deleting or rewriting it. No stash, clean, hard reset, force push, main checkout mutation, or worktree deletion is part of this plan.

## Artifacts and Notes

The verified start state is:

    origin/main=0b0ebaa76ab108ac8b7352e0da948353cdbc1452
    origin/architecture/lineage-integration-final=0b0ebaa76ab108ac8b7352e0da948353cdbc1452
    HEAD=0b0ebaa76ab108ac8b7352e0da948353cdbc1452
    worktree=C:\tmp\app-industry-resilience-lineage-final

Final validation evidence before commit is:

    Python 3.14.0
    black --check app.py src tests: 141 files unchanged
    ruff check app.py src tests: all checks passed
    python -m mypy src: no issues in 100 source files
    focused final regression set: 65 passed
    pytest -q: 353 passed
    runtime coverage: 353 passed, 87.40% (required 85%)
    full src coverage: 353 passed, 82% informational
    benchmark: 100, 10,000, and 100,000 rows all PASS
    pip-audit: no known vulnerabilities
    detect-secrets-hook baseline: passed
    git diff --check: passed

The exact `make quality-gate` wrapper could not execute because GNU Make is absent; its seven constituent targets were run directly and passed. `pip check` is nonzero only for the unrelated global OpenCV/NumPy mismatch. Docker smoke is unavailable because Docker is not installed.

## Interfaces and Dependencies

Use existing `src.core` exports: `LineageStep`, `attach_lineage`, `build_lineage`, `lineage_from_dataframe`, `lineage_from_mapping`, `lineage_to_dict`, and `update_lineage_cache`. Do not add a dependency. Cache payloads remain JSON-serializable mappings with `records`, existing bounded provider `metadata` where currently supported, and optional `lineage`. `ScenarioResponse.lineage` uses the existing `LineageEnvelopeModel`. Streamlit uses existing `DownloadArtifact` values and `build_json_export_document`, `build_csv_lineage_companion`, and `build_xlsx_lineage_rows` from `src.application.lineage_exports`.

Revision note (2026-07-21): Created after preflight and repository/issue inspection to guide the final issue 79 implementation in the isolated worktree.

Revision note (2026-07-21): Updated after implementation and validation to record completed behavior, the computation-cache identity decision, exact evidence, and environment-only limitations before publication.

Revision note (2026-07-21): Closed after implementation commit `9cd998b` was pushed without force to `architecture/lineage-integration-final`; this plan-only closure will be the final synchronized branch commit.
