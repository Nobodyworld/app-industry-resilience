# 2025-11-12T09:15Z – feat: connector catalog & automation tooling
- **Summary:** Delivered a connector registry and catalog surfaces (`/meta/connectors`, Streamlit sidebar, observability digest, `make connectors-catalog`) so integrations expose metadata, capabilities, and health checks. Shipped built-in entries for the sample dataset, BEA API, and Census ASM with health diagnostics, added a changelog automation script, and extended the extension scaffold with connector support to streamline future plug-ins.
- **Next:** Expand the catalog with connector-specific metrics (latency, cache hit rates) and explore auto-validating connector health in CI smoke tests.

# 2025-11-10T22:45Z – feat: multi-cloud snapshot replication & UI telemetry
- **Summary:** Added first-class Google Cloud Storage and Azure Blob Storage replicators alongside the existing S3 implementation, expanded configuration/validation/tests to cover the new knobs, enriched the Streamlit observability dashboard with replication health badges, and refreshed docs (README, OBSERVABILITY_SNAPSHOTS, EXTENSION_GUIDE, AUTOMATION) plus CLI messaging to highlight the active backend URI. Unit tests now stub cloud SDKs to keep the suite hermetic.
- **Next:** Explore lifecycle/retention helpers per backend (object tags, storage class transitions) and consider surfacing replication state via the headless API for automation consumers.

# 2025-11-10T06:10Z – feat: replication plugins & telemetry uplift
- **Summary:** Generalised snapshot replication via `ReplicationExtension`, added plugin-aware config options, emitted structured `observability.snapshot.replication` events, and introduced a `snapshot_replication` instrumentation extension that tracks counts, latency, and health. Shipped built-in S3 and debug filesystem replication modules, updated the CLI to report destinations, and refreshed docs/tests (README, OBSERVABILITY_SNAPSHOTS, EXTENSION_GUIDE, AUTOMATION, STATUS, STEWARDS_REPORT, RELEASE_NOTES, CHANGELOG) to describe the plugin seam and metrics.
- **Next:** Evaluate additional remote backends (GCS/Azure) using the new extension contract and consider auto-validating replication health during CI smoke tests.

# Modernization Status

## 2025-10-19T10:30Z – docs: add repo intelligence report and modernization plan
- **Summary:** Established baseline documentation via `REPORT.md` and `PLAN.md`, capturing the current architecture, risks, and a prioritized modernization roadmap.
- **Next:** Stand up governance files, CI/CD scaffolding, and local developer tooling so follow-on tasks can build on a consistent foundation.

## 2025-11-09T11:40Z – feat: snapshot remote replication
- **Summary:** Implemented S3-compatible snapshot replication with `SnapshotRemoteStorageConfig`, a reusable replicator factory, and CLI/extension integration so every persisted observability snapshot streams to remote storage while still landing on disk. Added botocore as a runtime dependency, expanded configuration summaries/tests, and refreshed docs (README, OBSERVABILITY_SNAPSHOTS, EXTENSION_GUIDE, AUTOMATION, RELEASE_NOTES, STEWARDS_REPORT) to cover the new workflow.
- **Next:** Explore remote retention policies (object lifecycle rules, size-based pruning) and add optional server-side encryption/metadata tagging knobs for compliance-heavy deployments.

## 2025-11-08T16:40Z – feat: snapshot persistence automation
- **Summary:** Added the `snapshot_persistence` instrumentation extension to persist observability snapshots on startup, shutdown, and warn/error events with throttling plus retention pruning governed by new `OBSERVABILITY_SNAPSHOT_RETENTION_*` environment variables. Updated configuration parsing/tests, documentation (README, OBSERVABILITY_SNAPSHOTS, EXTENSION_GUIDE, AUTOMATION), and extension catalog/tests so automation inherits the workflow by default.
- **Next:** Layer size-based pruning atop count/day limits and pilot remote snapshot shipping to object storage (now available) to complete the roadmap.

## 2025-10-31T09:10Z – chore: stewardship simplification & observability polish
- **Summary:** Added `ObservabilityRegistry.record_event(...)` so services and extensions can emit telemetry without empty context managers, refreshed dataset/scenario instrumentation to use the helper, and taught `scripts/audit_metrics.py` to read `coverage.xml` when trace JSON is absent. Documentation (architecture, extension guide) and tests now reflect the streamlined API.
- **Next:** Backfill streaming digest support and persist observability snapshots so automation can diff state across deploys.

## 2025-10-26T11:45Z – feat: observability digest & extension catalog
- **Summary:** Added `/observability/digest`, the streaming `observability_tail.py` CLI, and the `extensions_catalog.py` inventory tool; introduced the `data_quality` instrumentation extension with gauges/health checks; refreshed docs (README, AUTOMATION, EXTENSION_GUIDE, OPERATIONS) and Make targets so operators can inspect telemetry and extensions without code changes.
- **Next:** Explore persistent storage for observability digests and automate extension manifest validation prior to activation.

## 2025-10-19T13:55Z – chore: bootstrap governance and automation
- **Summary:** Added governance policies (CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, SUPPORT, CODEOWNERS), standardized formatting/linting via offline-friendly pre-commit scripts, introduced Makefile + pyproject configuration, refreshed CI to run the consolidated `make check`, and documented the workflow in README/CONTRIBUTING. Implemented local commit linting and quality gates resilient to missing npm/pip connectivity.
- **Next:** Extend type and lint coverage into existing `src/` modules, upstream the offline-aware quality scripts into CI, and plan structured cleanups (e.g., renaming `src/types.py`) to enable strict mypy across the application.

## 2025-10-27T12:00Z – chore: steward audit and automation enablement
- **Summary:** Refreshed `STEWARDS_REPORT.md` with measured coverage, complexity, dependency depth, and latency metrics; shored
  up CLI ergonomics by bootstrapping all scripts for direct execution; delivered `scripts/audit_metrics.py`, `make audit`, and
  `AUTOMATION_ROLES.md` to guide agent workflows while simplifying API telemetry span bookkeeping.
- **Next:** Vendor dev dependency wheels to reinstate pytest-cov locally, then tackle the highest-complexity modules surfaced by
  the new audit (e.g., `src/core/security`).

## 2025-10-28T14:20Z – feat: observability unification
- **Summary:** Added the `ObservabilityRegistry`, instrumented core services and the API, delivered `/observability/status` plus the offline snapshot CLI, and extended scaffolds/docs so future extensions register instrumentation safely.
- **Next:** Pursue distributed rate limiting (Redis-backed) and schema override support called out in TODO-P1/TODO-P2 for multi-node readiness.

## 2025-10-19T16:45Z – chore: harden security automation and supply-chain checks
- **Summary:** Introduced `pip-audit`, `detect-secrets`, and CycloneDX SBOM generation into the Makefile, pre-commit hooks, and fallback scripts; added a dedicated `security` GitHub Actions job running gitleaks, vulnerability scans, and SBOM uploads; refreshed docs and PLAN status to reflect the new guard rails.
- **Next:** Move into Milestone 2 by tightening mypy to strict mode, backfilling missing type hints, and inventorying adapter dead-code paths before refactors.

## 2025-10-25T04:10Z – feat: health probe + automation docs
- **Summary:** Added a reusable `HealthProbe` powering richer `/health` responses, introduced the `scripts/check_health.py`
  CLI, expanded API schemas/tests, and refreshed docs (README, ARCHITECTURE_OVERVIEW, API_HEADLESS, OPERATIONS) alongside a new
  `AUTOMATION.md` guide. Updated changelog/release notes to document the API contract change and CLI workflow.
- **Next:** Monitor downstream integrations for the new health payload shape and continue iterating on extension authoring
  tooling.

## 2025-10-19T18:05Z – docs: refresh modernization baseline
- **Summary:** Rebuilt `REPORT.md` with an up-to-date system overview, dependency map, risks, and ROI-ranked opportunities, and re-authored `PLAN.md` with milestone-tagged tasks, rollback notes, and prerequisites to guide the upcoming workstreams.
- **Next:** Deliver Milestone 1 by tightening governance docs, CODEOWNERS/triage workflows, and aligning formatter/linter/type tooling with CI and pre-commit enforcement.

## 2025-10-20T09:15Z – docs: elevate repo intelligence & execution plan
- **Summary:** Rewrote `REPORT.md` with accurate module mappings, runtime/dependency insights, and a refreshed top-10 ROI list aligned to actual code hotspots; rebuilt `PLAN.md` with milestone overview tables, clarified acceptance criteria, and explicit prerequisites/rollback notes; left `STATUS.md` breadcrumbs for the governance milestone.
- **Next:** Execute Milestone 1 tasks—governance doc refresh, CODEOWNERS/template alignment, and unified formatter/linter/type tooling with matching CI enforcement.
