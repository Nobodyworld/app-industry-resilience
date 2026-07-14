# Connector Catalog & Extension Guide

The Industry Resilience platform exposes a first-class connector registry so integrations can publish metadata, capabilities, and health diagnostics without modifying core services.

## Surfaces

- **API:** `GET /meta/connectors` returns the catalog payload consumed by automation and observability dashboards.
- **CLI:** `make connectors-catalog` (or `python src/scripts/connectors_catalog.py --json --pretty`) prints the same dataset locally.
- **Streamlit:** The configuration sidebar displays connector entries, including health status summaries.
- **Observability:** `/observability/digest` and persisted snapshots include a `connectors` block summarising counts, kinds, and per-connector health components.

## Authoring Connectors

1. Create (or update) an extension module that implements `ConnectorExtension.register`.
2. Register `ConnectorRegistration` objects via the supplied registry. Each registration should set:
   - `identifier`: stable slug (e.g., `bea`, `census_asm`).
   - `name` / `description`: human-friendly labels.
   - `kind`: category (`data_source`, `automation`, `storage`, etc.).
   - `capabilities`: tuple of keywords (`read`, `normalize`, `metrics`).
   - `metadata`: optional dictionary with configuration hints or docs links.
   - `health_check`: callable returning a `HealthComponent` with actionable details.
3. Update `extensions/manifest.json` (or set `IDIOT_INDEX_EXTENSIONS`) so the module loads automatically.
4. Run `make connectors-catalog` and review the output before shipping.

The extension scaffold supports `--with-connector` to generate a pre-wired template:

```bash
python src/scripts/scaffold_extension.py --name supply_chain --with-connector
```

## Built-in Connectors

- `sample_offline` – Bundled CSV for offline exploration and automated tests.
- `bea` – Bureau of Economic Analysis Industry Accounts API.
- `census_asm` – Census Annual Survey of Manufactures data service.

Each health check reports credential status and supported year ranges. Missing or invalid credentials yield `warn` status so responders can differentiate misconfiguration from upstream outages.

## Best Practices

- Keep identifiers stable; treat them as API contracts.
- Prefer reusable helper functions for shared health logic (e.g., credential checks).
- Document connector-specific environment variables in `README.md` or dedicated runbooks.
- Consider emitting connector-specific metrics via instrumentation extensions when runtime performance or error rates are critical.
