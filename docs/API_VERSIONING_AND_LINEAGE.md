# API Versioning and Data Lineage Architecture

**Status:** Accepted for implementation  
**Date:** 2026-07-15  
**Issue:** [#79](https://github.com/Nobodyworld/app-industry-resilience/issues/79)

## Context

The public-beta API currently exposes useful analytical, metadata, and operational endpoints without a path-level contract version. Evaluation and scenario responses also expose a flexible `metadata` object derived from pandas dataframe attributes, but there is no typed, consistently propagated lineage contract.

Downstream clients need a stable compatibility boundary before they depend on undocumented response details. Operators and users also need to distinguish bundled sample data, inline records, cached results, snapshots, and live-provider data without exposing credentials, private paths, or deployment internals.

## Decision

### Consumer API versioning

Canonical consumer-facing endpoints will use a major path prefix:

```text
/v1/evaluate
/v1/scenario
/v1/analytics/health
/v1/meta/sources
/v1/meta/connectors
```

The current unversioned forms remain compatibility aliases during migration:

```text
/evaluate
/scenario
/analytics/health
/meta/sources
/meta/connectors
```

The alias and canonical route must execute the same handler and return the same response model. Introducing `/v1` is additive; this decision does not create a `/v2` endpoint.

### Operational endpoints

Operational endpoints remain unversioned because they are deployment and diagnostics surfaces rather than consumer analytical contracts:

```text
/health
/healthz
/metrics
/observability/status
/observability/digest
/observability/events
/observability/snapshots
/observability/snapshots/{snapshot_id}
```

Their schemas still require tests and documentation, but they do not move under `/v1` unless a future operational compatibility requirement justifies a separate decision.

### Deprecation window

An unversioned consumer alias may be removed only after both conditions are met:

1. at least 90 days have elapsed since deprecation was announced; and
2. at least two minor application releases containing the canonical replacement have been published.

Deprecated aliases will return the normal payload plus migration headers:

```text
Deprecation: true
Sunset: <HTTP-date>
Link: </v1/...>; rel="successor-version"
```

The API documentation and changelog must identify the replacement route and planned removal window. Removal of an alias is a breaking change and requires a new major contract version or an explicitly completed deprecation cycle.

### Compatibility classification

An **additive** change may ship within the current major contract when it:

- adds an optional response field with a stable default;
- adds a new endpoint;
- adds an optional request field;
- adds documentation or non-semantic descriptions; or
- broadens accepted input without changing existing successful results.

A **deprecating** change retains the old behavior while announcing a replacement and migration window.

A **breaking** change includes:

- removing or renaming an endpoint or field;
- changing a field type, unit, requiredness, or semantic meaning;
- narrowing accepted input;
- changing successful status codes or established error shapes;
- removing an enum value;
- adding enum values where exhaustive clients would no longer be safe without an announced compatibility policy;
- changing metric interpretation or lineage semantics; or
- removing a deprecated alias before its window completes.

Breaking consumer changes require a new major path such as `/v2`. A new major path is not created merely to mark repository progress.

## Current public-beta contract inventory

| Method | Current path | Intended canonical path | Request model | Response model | Compatibility-sensitive notes |
| --- | --- | --- | --- | --- | --- |
| GET | `/health` | unchanged | none | `HealthResponse` | Operational status, service version, component details, telemetry metadata. |
| GET | `/healthz` | unchanged | none | `HealthResponse` | Alias of `/health`; timing and trace identifiers may differ. |
| GET | `/metrics` | unchanged | none | Prometheus text | Content type and metric names are operational contracts. |
| GET | `/observability/status` | unchanged | none | `ObservabilityStatusResponse` | Operational digest of metrics, traces, events, and health checks. |
| GET | `/observability/digest` | unchanged | none | `ObservabilityDigestResponse` | Enriched operational digest including subscriptions. |
| GET | `/observability/events` | unchanged | `limit`, `status` query parameters | `ObservabilityEventsResponse` | Query bounds, ordering, event shape, and status filtering are compatibility-sensitive. |
| GET | `/observability/snapshots` | unchanged | none | list of `ObservabilitySnapshotMeta` | Snapshot identifiers and capture timestamps are operational data. |
| GET | `/observability/snapshots/{snapshot_id}` | unchanged | path identifier | `ObservabilitySnapshotResponse` | Returns 400 for invalid identifiers and 404 for missing snapshots. |
| GET | `/meta/sources` | `/v1/meta/sources` | none | `MetaSourcesResponse` | Source identifiers are client-visible enum values. |
| GET | `/meta/connectors` | `/v1/meta/connectors` | none | `MetaConnectorsResponse` | Connector identifiers, kinds, versions, capabilities, metadata, and health shape are client-visible. |
| POST | `/evaluate` | `/v1/evaluate` | `EvaluateRequest` | `EvaluateResponse` | Dataset record fields, filters, leaderboard, notes, dataset rows, metadata, health envelope, status codes, and metric units are contract-sensitive. |
| POST | `/scenario` | `/v1/scenario` | `ScenarioRequest` | `ScenarioResponse` | Adjustment semantics, baseline/scenario/delta rows, summaries, metadata, and health envelopes are contract-sensitive. |
| POST | `/analytics/health` | `/v1/analytics/health` | `HealthAnalyticsRequest` | `HealthAnalyticsResponse` | Grouping choices, risk limits, aggregate fields, metadata, and status codes are contract-sensitive. |

The OpenAPI document generated from these typed request and response models is the machine-readable contract source. Compatibility tests should snapshot or structurally assert the documented paths, methods, required fields, field types, and response models without overfitting descriptions or generated ordering.

## Typed lineage contract

Consumer analytical responses will add a typed `lineage` field while retaining the existing generic `metadata` field for backward compatibility.

### `LineageEnvelope`

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string literal (`"1"`) | Version of the lineage envelope itself. |
| `source` | string | Stable application source identifier such as `sample`, `bea`, `census`, `api-inline`, or `user-upload`. |
| `source_kind` | enum | `bundled_sample`, `official_snapshot`, `live_provider`, `inline_records`, `uploaded_file`, or `cache`. |
| `dataset_id` | string | Stable non-secret dataset identifier. User filenames and absolute paths are not permitted. |
| `provider` | string or null | Public provider name when applicable. |
| `observation_period` | string | Provider year, quarter, month, or a stable textual period. |
| `acquired_at` | UTC datetime or null | When live or inline data entered the application boundary. |
| `snapshot_at` | UTC datetime or null | Published or locally recorded snapshot time when known. |
| `retrieval_mode` | enum | `bundled`, `snapshot`, `live`, `inline`, `upload`, or `cache`. |
| `is_sample` | boolean | Explicitly marks demonstration data. |
| `is_official` | boolean | True only for an identified official-provider dataset or snapshot. |
| `calculation_version` | string | Version of the metric/calculation contract used for derived values. |
| `transformations` | list of `LineageStep` | Ordered, bounded descriptions of normalization, calculations, filtering, health aggregation, scenarios, and exports. |
| `cache_status` | enum | `not_used`, `miss`, or `hit`; must not contain cache keys or paths. |

### `LineageStep`

Each transformation step contains:

- `name`: stable bounded identifier;
- `version`: transformation contract version;
- `details`: optional JSON-safe, non-secret bounded metadata.

Initial step names should come from a fixed set such as:

```text
source_load
normalize_columns
compute_metrics
compute_health_scores
filter_records
scenario_adjustment
export_serialization
```

Scenario details may include bounded percentages and the number of targeted industries, but must not include credentials, raw provider payloads, private paths, or unrestricted user content.

## Propagation requirements

### Source boundary

- Bundled sample data must set `source_kind=bundled_sample`, `retrieval_mode=bundled`, `is_sample=true`, and `is_official=false`.
- Inline API records must set `source_kind=inline_records`, `retrieval_mode=inline`, and a stable dataset identifier such as `api-inline`.
- Uploaded data must use a generic identifier such as `user-upload`; user filenames must not be exposed as lineage identifiers.
- Live BEA and Census adapters must identify the public provider, requested observation period, and acquisition time.
- Official snapshots must identify the provider dataset, observation period, and snapshot time when known.

A successful live BEA result for 2021 exposes this source boundary before later calculation steps are appended (the timestamp shown is illustrative):

```json
{
  "source": "bea",
  "source_kind": "live_provider",
  "dataset_id": "gdpbyindustry",
  "provider": "U.S. Bureau of Economic Analysis",
  "observation_period": "2021",
  "acquired_at": "2026-07-21T12:00:00Z",
  "snapshot_at": null,
  "retrieval_mode": "live",
  "is_sample": false,
  "is_official": true,
  "cache_status": "not_used",
  "transformations": [
    {"name": "source_load", "version": "1", "details": {"record_count": 1}}
  ]
}
```

Census ASM uses `source=census`, `dataset_id=asm`, and the same `live_provider`/`live` truth. The dashboard's Census AIES 2023 file is an official snapshot with `source=census`, `dataset_id=aies`, `observation_period=2023`, `snapshot_at=2026-02-26T00:00:00Z`, `retrieval_mode=snapshot`, and `is_official=true`. Neither envelope contains provider URLs, payload fields, credentials, filenames, or local paths.

### Evaluation pipeline

Normalization, metric calculation, health scoring, and filtering append ordered transformation steps. Filtering does not change source identity or acquisition time.

### Scenario pipeline

The baseline preserves its incoming lineage. Scenario and delta frames preserve the same source lineage and append a `scenario_adjustment` step containing only bounded, non-secret adjustment summaries.

### Cache pipeline

Cached values preserve the original source and transformation history. A cache hit changes only `retrieval_mode`/`cache_status`; it must not replace the original acquisition or snapshot timestamp. Cache keys, directories, and backend connection details are never exposed.

For example, the cached form of the BEA envelope above retains `source=bea`, `source_kind=live_provider`, `dataset_id=gdpbyindustry`, `acquired_at=2026-07-21T12:00:00Z`, and every ordered transformation, while its cache fields are exactly:

```json
{
  "retrieval_mode": "cache",
  "cache_status": "hit"
}
```

A cache miss instead sets `cache_status=miss` and leaves `retrieval_mode=live`. Serialized cache entries retain only the typed, allowlisted lineage mapping; legacy entries with no lineage remain readable without inventing an acquisition or snapshot timestamp.

### API responses

`EvaluateResponse`, `ScenarioResponse`, and `HealthAnalyticsResponse` expose `lineage: LineageEnvelope`. The existing `metadata` object remains during the v1 compatibility period. Telemetry trace identifiers remain telemetry, not lineage.

Both `POST /v1/scenario` and deprecated `POST /scenario` return the same typed scenario lineage (apart from request-time acquisition timestamps and telemetry trace identifiers). A response excerpt is:

```json
{
  "metadata": {"extensions": {}},
  "lineage": {
    "source": "api-scenario",
    "source_kind": "inline_records",
    "dataset_id": "api-scenario",
    "retrieval_mode": "inline",
    "is_sample": false,
    "is_official": false,
    "transformations": [
      {"name": "source_load", "version": "1", "details": {"record_count": 3}},
      {"name": "scenario_adjustment", "version": "1", "details": {"adjustment_count": 1, "all_industries": true}}
    ]
  }
}
```

The actual envelope also includes all required version, period, timestamp, calculation, and cache fields. The generic `metadata` field remains present for v1 clients; arbitrary baseline/scenario dataframe attributes are not copied into typed lineage.

### Exports

- JSON exports use the stable top-level document `{"lineage": {...}, "records": [...]}`. The lineage ends with a non-mutating `export_serialization` step whose details identify `format=json`, `scope=full` or `filtered`, and the record count.
- XLSX exports retain the `Cost Structure` data sheet and include a dedicated `Lineage` sheet containing `field` and `value` columns.
- CSV data remains tabular and backward compatible; the UI supplies a companion lineage JSON artifact sharing the safe export base and scope. For the default downloads, the exact names are `industry_cost_structure_results_full.lineage.json` and `industry_cost_structure_results_filtered.lineage.json` alongside the existing CSV files.
- Export serialization appends an `export_serialization` step without mutating the in-memory source lineage.

An exact JSON export shape is:

```json
{
  "lineage": {
    "source": "census",
    "transformations": [
      {"name": "export_serialization", "version": "1", "details": {"format": "json", "record_count": 2, "scope": "full"}}
    ]
  },
  "records": [
    {"industry_code": "311", "industry_name": "Food"}
  ]
}
```

The abbreviated lineage above illustrates placement; produced exports contain the complete typed envelope.

## Privacy and security constraints

Lineage must never expose:

- API keys, authorization headers, cookies, or tokens;
- absolute filesystem paths or user home directories;
- cache keys, Redis URLs, storage credentials, or private bucket paths;
- raw exception traces or deployment environment dumps;
- uploaded filenames where they may contain personal information;
- unrestricted provider payloads or arbitrary user content.

Serialization must use explicit typed fields and allowlisted transformation details. It must not copy arbitrary dataframe attributes into the typed lineage envelope.

## Compatibility and security tests

Implementation must add tests that verify:

1. `/v1` and unversioned aliases return equivalent successful payloads.
2. Deprecated aliases include migration headers.
3. OpenAPI exposes all inventoried routes and stable request/response structures.
4. Sample lineage is explicitly marked as sample and not official.
5. Live, inline, upload, and snapshot lineage use the correct source kind.
6. Lineage survives normalization, metric calculation, health aggregation, filtering, scenarios, cache hits, and exports.
7. Scenario lineage adds bounded adjustment details without raw records.
8. Serialization contains no credentials, absolute paths, cache keys, or private deployment details.
9. Existing metadata remains available for v1 compatibility.
10. `make quality-gate` passes.

## Rejected alternatives

### Header-only or media-type versioning

Rejected for the public beta because it is less discoverable in browsers, examples, and generated client tooling. Headers may advertise versions but do not replace the major path boundary.

### Query-parameter versioning

Rejected because cache behavior, documentation, and route discovery are clearer with major path prefixes.

### Immediately replacing unversioned routes

Rejected because existing users and smoke tests may rely on them. The aliases remain through the documented migration window.

### Versioning every operational endpoint

Rejected because health, metrics, and observability endpoints serve deployment tooling rather than the analytical consumer contract. They remain explicitly documented and tested.

### Creating `/v2` now

Rejected because no breaking v1 migration is required. The repository must not introduce a new major endpoint solely to close an issue.

## Implementation sequence

1. Add typed lineage domain models and safe construction/serialization helpers.
2. Add canonical `/v1` consumer routes backed by shared handlers.
3. Retain unversioned aliases with deprecation headers and migration documentation.
4. Propagate lineage through source loading, evaluation, scenarios, caches, and exports.
5. Add OpenAPI compatibility, alias parity, lineage propagation, and redaction tests.
6. Update API and export documentation with exact payload examples.
7. Run the full protected quality gate before merge.
