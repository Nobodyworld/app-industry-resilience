# TASKLIST: Task Compilation

> Required root governance files: `README.md`, `SPEC.md`, `STYLE-GUIDE.md`, and `TASKLIST.md`. Do not remove them; keep the canonical links in the root entry-point files current.

Use this file to compile and track all repository tasks. Check off items as they are finished, keep each task on a single line, and preserve chronological order. Follow the template below.

Keep entries one-line and oldest-first. When completing a task, check it off and append a one-line completion note indented underneath (date + PR/link + 1–2 sentence summary).

## Template (single-line + optional completion note)

```text
- [ ] Short task description — TK-YYYYMMDD-###
```

Completion note (indented, one line):

```text
  - Completed: YYYY-MM-DD — PR: <url> — short summary
```

---

## Tasks

- [x] Add repo defaults (no functional changes) | owner: automation | added: 2025-10-29 | closed: 2025-10-30 – `.gitattributes` committed, defaults verified.
- [x] Wire reusable CI (workflow_call) | owner: automation | added: 2025-10-29 | closed: 2025-10-30 – new `quality-gate` workflow in place and CI wired to it.
- [x] Fill URGENT.md from template | owner: automation | added: 2025-10-29 | closed: 2025-10-30 – repository plan populated with current state.
- [x] Compare dependencies to organization-wide version targets | owner: automation | added: 2025-10-29 | closed: 2025-10-30 – Dependency alignment was recorded during the original modernization pass; the obsolete snapshot file was later retired during repository cleanup.
- [x] Increase test coverage from 80% to sustained runtime-gate compliance and improved full-source trend | owner: dev | priority: high | added: 2025-11-14 | closed: 2026-07-14 – Hosted `CI / Quality Gate` enforces an 85% runtime threshold; Streamlit AppTest, component, integration, security, cache, and observability-replication suites are present and passing. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [x] Add integration tests for complete data pipeline flows | owner: dev | priority: high | added: 2025-11-14 | closed: 2025-11-14 – Added `tests/test_integration_pipeline.py` covering compute and cache behavior.
- [x] Fix Census ASM type error in line 92 | owner: dev | priority: high | added: 2025-11-14 | closed: 2025-11-14 – Guarded `year_result.value` via `year_value: int` and used `getattr(config, 'census_asm_endpoint_template', None)` to avoid AttributeError.
- [x] Implement API response caching strategy | owner: dev | priority: medium | added: 2025-11-14 | closed: 2026-07-14 – BEA and Census adapters use the configured API cache with cache-hit/miss telemetry and dedicated caching tests. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [x] Add rate limiting metrics and monitoring | owner: ops | priority: medium | added: 2025-11-14 | closed: 2026-07-14 – The `rate_limiting` instrumentation extension exposes request counters, wait histograms, backend health gauges, retry telemetry, and a registered health component. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [x] Create Streamlit component smoke tests | owner: dev | priority: medium | added: 2025-11-14 | closed: 2025-11-14 – Added a minimal smoke test suite in `tests/test_streamlit_components.py` and stubbed Streamlit primitives for deterministic checks.
- [x] Document error recovery procedures | owner: docs | priority: medium | added: 2025-11-14 | closed: 2026-07-14 – `docs/OPERATIONS_INCIDENT_RESPONSE.md` now documents current health, observability, connector, diagnostics, rate-limiter, rollback, CI, Docker, recovery, and post-incident procedures. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [ ] Add data validation layer for API responses | owner: dev | priority: medium | added: 2025-11-14 – Validate BEA/Census response schemas before normalization to catch API breaking changes early.
- [x] Implement export format validation | owner: dev | priority: low | added: 2025-11-14 | closed: 2026-07-14 – Streamlit helper tests parse generated CSV and JSON payloads and inspect the Excel workbook structure and sheet name. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [ ] Create performance benchmarking suite | owner: dev | priority: low | added: 2025-11-14 – Add performance tests for metric computation and large dataset handling.
- [ ] Add accessibility audit for Streamlit UI | owner: ux | priority: low | added: 2025-11-14 – Review color contrast, screen reader compatibility, and keyboard navigation.
- [x] Document extension development workflow | owner: docs | priority: low | added: 2025-11-14 | closed: 2026-07-14 – `docs/handbook/EXTENSION_GUIDE.md`, `extensions/README.md`, and catalog/scaffolding commands document extension creation, registration, testing, observability, connectors, and deployment safety. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [ ] Add API endpoint versioning strategy | owner: arch | priority: low | added: 2025-11-14 – Plan v2 API endpoints to support breaking changes without disrupting existing clients.
- [x] Implement Redis connection health checks | owner: ops | priority: medium | added: 2025-11-14 | closed: 2026-07-14 – Rate-limiter status reports Redis mode, fallback state, and last errors through the registered health component and dedicated health-probe tests. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [ ] Add data lineage tracking | owner: dev | priority: low | added: 2025-11-14 – Track data source, transformation steps, and computation timestamps for audit trails.
- [ ] Create user onboarding tutorial | owner: docs | priority: low | added: 2025-11-14 – Add interactive tutorial in Streamlit UI for first-time users covering key features.
- [x] Optimize Docker image size | owner: ops | priority: low | added: 2025-11-14 | closed: 2026-07-14 – The production Dockerfile uses Python slim images, a separate wheel-building stage, runtime-only dependency installation, cache cleanup, and a non-root runtime user. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [x] Add SPEC.md file | owner: docs | priority: high | added: 2025-11-14 | closed: 2025-11-14 – Basic SPEC.md created outlining dataflows, schema, and operational contracts.
- [ ] Fix markdown linting issues in README.md | owner: docs | priority: low | added: 2025-11-14 – Address MD034 bare URLs, MD040 code block languages, MD032 list spacing issues.
- [ ] Add graceful degradation for missing NAICS mappings | owner: dev | priority: medium | added: 2025-11-14 – Handle cases where industry codes don't match NAICS map without failing entire pipeline.
- [x] Refactor metrics to avoid deprecated pandas options | owner: dev | priority: medium | added: 2025-11-14 | closed: 2026-07-14 – Metric calculations explicitly mask invalid denominators and replace infinities without using `mode.use_inf_as_na`. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [ ] Add a short note to ARCHITECTURE_OVERVIEW.md or SPEC.md documenting that helpers will auto-compute derived metrics, and warn about performance on large datasets.
- [ ] Add a logger metric/count to track how often helpers trigger auto-compute (useful telemetry).
- [ ] Add a small benchmark test for compute_metrics to quantify runtime on representative sample sizes.
- [x] Add a pre-commit config or GitHub Action job to run ruff/black/mypy to avoid style drift | closed: 2026-07-14 – `config/.pre-commit-config.yaml` and the protected hosted `CI / Quality Gate` run Black, Ruff, mypy, tests, coverage, and security scans. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [ ] Add telemetry when _ensure_metrics runs (counter metric).
- [ ] Add docs mentioning auto-compute behavior and recommended usage patterns.
