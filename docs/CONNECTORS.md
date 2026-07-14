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

## Provider Contract Validation

BEA and Census ASM responses are validated at the adapter boundary before normalization or metric calculation.

### BEA

A valid table response must contain the `BEAAPI.Results.Data` envelope and at least one row. Every row must contain a non-empty `Industry` code, `IndustrYDescription` provider label, positive integral `Year`, and finite numeric `DataValue`. Malformed envelopes, missing fields, mismatched years, duplicate rows, empty tables, and invalid numeric values raise `BEAClientError` with provider and row context but without credentials or full payload contents.

BEA provider labels are preserved. The adapter adds:

- `naics_sector_name` – the matching sector label, or `Unmapped NAICS <code>`;
- `bea_group` – the mapped group, or `UNMAPPED`;
- `naics_mapping_status` – `mapped` or `unmapped`.

Two-digit and two-digit-range entries such as `31-33` are applied to more detailed codes such as `311`. Codes that still have no mapping remain in the dataset, retain their provider label, and are listed in `dataframe.attrs["bea_metadata"]["unmapped_naics_codes"]`. A bounded warning is emitted without logging API credentials or complete upstream rows.

### Census ASM

A valid Census ASM response must be a list containing a header and at least one row. The header must include `NAICS2017`, `NAICS2017_LABEL`, `RCPTOT`, `CSTMTOT`, and `VALADD`. Each row must match the header width, include non-empty code and label values, and provide finite numeric shipment, material-cost, and value-added values. Violations raise `CensusASMClientError` before normalization.

Validated Census frames include `dataframe.attrs["census_asm_metadata"]` with the provider year, row count, required fields, and `contract_validated: true`. Cached responses preserve the same metadata.

These checks detect provider schema drift early. They do not change analytical formulas, heuristic bands, or the project’s public-beta limitations.

## Best Practices

- Keep identifiers stable; treat them as API contracts.
- Prefer reusable helper functions for shared health logic (e.g., credential checks).
- Validate external envelopes and rows before normalization; do not rely on coercion to hide malformed provider values.
- Preserve provider codes and labels when enrichment metadata is unavailable.
- Document connector-specific environment variables in `README.md` or dedicated runbooks.
- Consider emitting connector-specific metrics via instrumentation extensions when runtime performance or error rates are critical.
