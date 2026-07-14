# Architecture Overview

This repository ships a layered Python platform with Streamlit/CLI user interfaces, a FastAPI-compatible headless API, and an extension-driven core. The visual below summarises the runtime boundaries:

```text
┌──────────────┬────────────────────────────┬─────────────┐
│  interfaces  │        application         │ extensions  │
│ (Streamlit,  │ (services orchestrating    │ (summary,   │
│  API, CLI)   │  adapters + domain logic)  │  scenario,  │
│              │                            │  connector, │
│              │                            │  observability)
└──────────────┴───────────────┬────────────┴─────────────┘
                               │
                             core
                               │
                           adapters
                               │
                         external data
```

- **Core services** (`src/application`, `src/core`, `src/infrastructure`) remain stable and observable via the shared `ObservabilityRegistry`. Metrics, traces, health checks, and persisted snapshots surface through `/metrics`, `/observability/*`, Streamlit dashboards, and CLI tooling.
- **Extension system** spans summary/scenario analytics, instrumentation hooks, replication backends, and the `ConnectorExtension` contract. Connector plug-ins register metadata and health probes with `ConnectorRegistry`, exposing integrations through `/meta/connectors`, Streamlit configuration panels, observability digests, and the catalog CLI (`make connectors-catalog`).
- **Developer ergonomics** include scaffolding helpers (`src/scripts/scaffold_extension.py`, `src/scripts/scaffold_service.py`), a changelog appender (`src/scripts/changelog_entry.py`), and automation targets under the Makefile (`make quality-gate`, `make extensions-catalog`, `make connectors-catalog`).
- **Documentation** in `../ARCHITECTURE_OVERVIEW.md` expands on the module responsibilities, observability strategy, incident response flow, and future-proofing notes. Use it alongside `AUTOMATION.md`, `EXTENSION_GUIDE.md`, and `docs/OPERATIONS_INCIDENT_RESPONSE.md` when onboarding new contributors or agents.

For detailed diagrams, connector health semantics, and extension recipes, read the [full architecture overview](../ARCHITECTURE_OVERVIEW.md).
