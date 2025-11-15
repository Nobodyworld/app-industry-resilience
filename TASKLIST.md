# TASKLIST: Task Compilation

-*NEVER REMOVE SPEC.md, STYLE-GUIDE.md, or TASKLIST.md FROM THE ROOT*

Use this file to compile and track all tasks that need to be completed for this repository. Check off items as they are finished. Keep each task on a single line. Check off already completed tasks and keep things in chronological order when updating and adding to the file. Follow Template Entry below.

Keep entries one-line, oldest-first. When completing a task, check it off and append a one-line completion note indented underneath (date + PR/link + 1â€“2 sentence summary).

## Template (single-line + optional completion note)

```text
- [ ] Short task description â€” TK-YYYYMMDD-###
```

Completion note (indented, one line):

```text
  - Completed: YYYY-MM-DD â€” PR: <url> â€” short summary
```

---

## Tasks

- [x] Add repo defaults (no functional changes) | owner: automation | added: 2025-10-29 | closed: 2025-10-30 – `.gitattributes` committed, defaults verified.
- [x] Wire reusable CI (workflow_call) | owner: automation | added: 2025-10-29 | closed: 2025-10-30 – new `quality-gate` workflow in place and CI wired to it.
- [x] Fill URGENT.md from template | owner: automation | added: 2025-10-29 | closed: 2025-10-30 – repository plan populated with current state.
- [x] Compare dependencies to organization-wide version targets | owner: automation | added: 2025-10-29 | closed: 2025-10-30 – targets captured in `MASTER-VERSIONS.json` with alignment report.
- [ ] Increase test coverage from 80% to 90% target | owner: dev | priority: high | added: 2025-11-14 – Progress: added integration, streamlit, security, and cache tests to improve coverage; remaining work: add UI smoke tests, observability replication tests, and adapter edge-case branches.
- [x] Add integration tests for complete data pipeline flows | owner: dev | priority: high | added: 2025-11-14 | closed: 2025-11-14 – Added `tests/test_integration_pipeline.py` covering compute and cache behavior.
- [x] Fix Census ASM type error in line 92 | owner: dev | priority: high | added: 2025-11-14 | closed: 2025-11-14 – Guarded `year_result.value` via `year_value: int` and used `getattr(config, 'census_asm_endpoint_template', None)` to avoid AttributeError.
- [ ] Implement API response caching strategy | owner: dev | priority: medium | added: 2025-11-14 – Add TTL-based caching for BEA/Census responses to reduce API calls and improve performance.
- [ ] Add rate limiting metrics and monitoring | owner: ops | priority: medium | added: 2025-11-14 – Expose rate limit hit counters and remaining token gauges in Prometheus metrics; instrument Redis health status as a gauge.
- [ ] Add rate limiting metrics and monitoring | owner: ops | priority: medium | added: 2025-11-14 – Expose rate limit hit counters and remaining token gauges in Prometheus metrics; instrument Redis health status as gauge.
- [x] Create Streamlit component smoke tests | owner: dev | priority: medium | added: 2025-11-14 | closed: 2025-11-14 – Added a minimal smoke test suite in `tests/test_streamlit_components.py` and stubbed Streamlit primitives for deterministic checks.
- [ ] Document error recovery procedures | owner: docs | priority: medium | added: 2025-11-14 – Expand `OPERATIONS_INCIDENT_RESPONSE.md` with runbooks for common API failures and data quality issues.
- [ ] Add data validation layer for API responses | owner: dev | priority: medium | added: 2025-11-14 – Validate BEA/Census response schemas before normalization to catch API breaking changes early.
- [ ] Implement export format validation | owner: dev | priority: low | added: 2025-11-14 – Add schema validation for CSV/JSON/Excel exports to ensure downstream compatibility.
- [ ] Create performance benchmarking suite | owner: dev | priority: low | added: 2025-11-14 – Add performance tests for metric computation and large dataset handling.
- [ ] Add accessibility audit for Streamlit UI | owner: ux | priority: low | added: 2025-11-14 – Review color contrast, screen reader compatibility, and keyboard navigation.
- [ ] Document extension development workflow | owner: docs | priority: low | added: 2025-11-14 – Create step-by-step guide for building custom extensions with examples.
- [ ] Add API endpoint versioning strategy | owner: arch | priority: low | added: 2025-11-14 – Plan v2 API endpoints to support breaking changes without disrupting existing clients.
- [ ] Implement Redis connection health checks | owner: ops | priority: medium | added: 2025-11-14 – Add periodic health checks for Redis rate limiter backend with automatic fallback logging.
- [ ] Add data lineage tracking | owner: dev | priority: low | added: 2025-11-14 – Track data source, transformation steps, and computation timestamps for audit trails.
- [ ] Create user onboarding tutorial | owner: docs | priority: low | added: 2025-11-14 – Add interactive tutorial in Streamlit UI for first-time users covering key features.
- [ ] Optimize Docker image size | owner: ops | priority: low | added: 2025-11-14 – Use multi-stage builds and minimize layer size (current image could be optimized).
- [x] Add SPEC.md file | owner: docs | priority: high | added: 2025-11-14 | closed: 2025-11-14 – Basic SPEC.md created outlining dataflows, schema, and operational contracts.
- [ ] Fix markdown linting issues in README.md | owner: docs | priority: low | added: 2025-11-14 – Address MD034 bare URLs, MD040 code block languages, MD032 list spacing issues.
- [ ] Add graceful degradation for missing NAICS mappings | owner: dev | priority: medium | added: 2025-11-14 – Handle cases where industry codes don't match NAICS map without failing entire pipeline.
- [ ] Refactor metrics to avoid deprecated pandas options | owner: dev | priority: medium | added: 2025-11-14 – Remove use of `mode.use_inf_as_na` in `compute_metrics` and convert infinities to NA using `pd.to_numeric`/replace before operations.
- [ ] Add a short note to ARCHITECTURE_OVERVIEW.md or SPEC.md documenting that helpers will auto-compute derived metrics, and warn about performance on large datasets.
- [ ] Add a logger metric/count to track how often helpers trigger auto-compute (useful telemetry).
- [ ] Add a small benchmark test for compute_metrics to quantify runtime on representative sample sizes.
- [ ] Add a pre-commit config or GitHub Action job to run ruff/black/mypy to avoid style drift.
- [ ] Add telemetry when _ensure_metrics runs (counter metric)
- [ ] Add docs mentioning auto-compute behavior and recommended usage patterns
