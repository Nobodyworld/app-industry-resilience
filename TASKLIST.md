# TASKLIST: Task Compilation

> Required root governance files: `README.md`, `SPEC.md`, `STYLE-GUIDE.md`, and `TASKLIST.md`. Do not remove them; keep the canonical links in the root entry-point files current.

Use this file as a compact repository-level index. GitHub issues are the canonical source for active work, acceptance criteria, discussion, and implementation links. Preserve completed historical entries below and represent each active workstream with one issue-linked line.

Keep entries one-line and oldest-first. When completing a task, check it off and append a one-line completion note indented underneath (date + PR/link + 1–2 sentence summary).

## Template (single-line + optional completion note)

```text
- [ ] Short task description — issue: #123
```

Completion note (indented, one line):

```text
  - Completed: YYYY-MM-DD — PR: <url> — short summary
```

---

## Completed history

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
- [x] Document error recovery procedures | owner: docs | priority: medium | added: 2025-11-14 | closed: 2026-07-14 – `docs/OPERATIONS_INCIDENT_RESPONSE.md` documents current health, observability, connector, diagnostics, rate-limiter, rollback, CI, Docker, recovery, and post-incident procedures. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [x] Implement export format validation | owner: dev | priority: low | added: 2025-11-14 | closed: 2026-07-14 – Streamlit helper tests parse generated CSV and JSON payloads and inspect the Excel workbook structure and sheet name. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [x] Document extension development workflow | owner: docs | priority: low | added: 2025-11-14 | closed: 2026-07-14 – `docs/handbook/EXTENSION_GUIDE.md`, `extensions/README.md`, and catalog/scaffolding commands document extension creation, registration, testing, observability, connectors, and deployment safety. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [x] Implement Redis connection health checks | owner: ops | priority: medium | added: 2025-11-14 | closed: 2026-07-14 – Rate-limiter status reports Redis mode, fallback state, and last errors through the registered health component and dedicated health-probe tests. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [x] Optimize Docker image size | owner: ops | priority: low | added: 2025-11-14 | closed: 2026-07-14 – The production Dockerfile uses Python slim images, a separate wheel-building stage, runtime-only dependency installation, cache cleanup, and a non-root runtime user. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [x] Add SPEC.md file | owner: docs | priority: high | added: 2025-11-14 | closed: 2025-11-14 – Basic SPEC.md created outlining dataflows, schema, and operational contracts.
- [x] Refactor metrics to avoid deprecated pandas options | owner: dev | priority: medium | added: 2025-11-14 | closed: 2026-07-14 – Metric calculations explicitly mask invalid denominators and replace infinities without using `mode.use_inf_as_na`. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [x] Add a pre-commit config or GitHub Action job to run ruff/black/mypy to avoid style drift | closed: 2026-07-14 – `config/.pre-commit-config.yaml` and the protected hosted `CI / Quality Gate` run Black, Ruff, mypy, tests, coverage, and security scans. PR: https://github.com/Nobodyworld/app-industry-resilience/pull/75
- [x] Validate upstream schemas and degrade safely for missing NAICS mappings | closed: 2026-07-14 – BEA and Census ASM now validate provider envelopes and rows before normalization; unknown BEA industry codes retain provider labels and receive explicit unmapped metadata. Issue: https://github.com/Nobodyworld/app-industry-resilience/issues/76 — PR: https://github.com/Nobodyworld/app-industry-resilience/pull/81
- [x] Instrument and benchmark automatic metric computation | closed: 2026-07-15 – Streamlit helper auto-computation now emits bounded telemetry, avoids external-cache initialization when disabled, and is covered by deterministic benchmark ceilings in the protected quality gate. Issue: https://github.com/Nobodyworld/app-industry-resilience/issues/77 — PR: https://github.com/Nobodyworld/app-industry-resilience/pull/83
- [x] Complete the public-beta accessibility, onboarding, and Markdown-quality pass | closed: 2026-07-15 – The Streamlit public beta now defaults true first-run sessions to bundled sample data, provides dismissible onboarding, clearer accessible controls and status text, table alternatives, improved semantic markup, and documented remaining browser-level verification limits. Issue: https://github.com/Nobodyworld/app-industry-resilience/issues/78 — PR: https://github.com/Nobodyworld/app-industry-resilience/pull/87
- [x] Define API versioning and end-to-end data lineage | closed: 2026-07-21 – Canonical `/v1` contracts, deprecated aliases, typed redacted lineage, provider/cache/scenario propagation, and JSON/XLSX/CSV export provenance are implemented and protected by compatibility, privacy, quality, and Docker tests. Issue: https://github.com/Nobodyworld/app-industry-resilience/issues/79 — PR: https://github.com/Nobodyworld/app-industry-resilience/pull/99
- [x] Correct uploaded lineage and surface dashboard provenance | closed: 2026-07-21 – Validated uploads now use generic privacy-safe `user-upload` lineage, and the Streamlit dashboard exposes typed source/vintage/cache/transformation provenance without copying filenames or arbitrary dataframe attributes. Issue: https://github.com/Nobodyworld/app-industry-resilience/issues/101 — PR: https://github.com/Nobodyworld/app-industry-resilience/pull/102

## Active workstreams

- [ ] Publish truthful no-auth public-data readiness catalog through typed canonical v1 API — issue: [#104](https://github.com/Nobodyworld/app-industry-resilience/issues/104)
