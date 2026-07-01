# Headless API Guide

The headless Idiot Index API exposes the same computation pipeline that powers the Streamlit dashboard so external systems can automate evaluations and scenario planning.

## Running the service

```bash
make api ARGS="--host 0.0.0.0 --port 9000"
```

This command executes `src/scripts/run_api.py`, which serves the bundled FastAPI-compatible application defined in `src/interfaces/api/app.py` using Python's built-in WSGI server. The CLI respects the following environment variables (all optional):

- `API_HOST` / `API_PORT` – default network binding (`0.0.0.0:9000`).
- `API_RELOAD` – accepted for compatibility but ignored (reload is not supported in the bundled server).
- `API_WORKERS` – accepted for compatibility but the server always runs single-threaded workers with a threaded WSGI server.
- `API_LOG_LEVEL` – echoed at startup for operator awareness.

Inside Docker, set `APP_MODE=api` to boot the same service from the container entrypoint. The image still honours `PREFETCH_ARGS` to warm caches prior to serving traffic.

## Endpoints

### `GET /health`

Returns service metadata, component-level health status, and a trace identifier useful for correlating logs.

```json
{
  "status": "warn",
  "service": "idiot-index-api",
  "version": "0.1.0",
  "checked_at": "2025-10-25T03:45:12.456789+00:00",
  "trace_id": "1f3e8b7157c448c1aaeb87b7e0e1d2b6",
  "components": [
    {"name": "configuration", "status": "warn", "summary": "Configuration validated with warnings"},
    {"name": "cache", "status": "pass", "summary": "Cache directories ready"},
    {"name": "extensions", "status": "pass", "summary": "1 summary extensions, 0 scenario extensions active"}
  ],
  "metadata": {
    "config": {
      "environment": "development",
      "log_level": "INFO"
    },
    "telemetry": {
      "metrics": {"counters": 4, "gauges": 1, "histograms": 1},
      "tracing": {"exported_spans": 12}
    }
  },
  "telemetry": {
    "metrics": {"counters": 4, "gauges": 1, "histograms": 1},
    "tracing": {"exported_spans": 12}
  }
}
```

### `GET /healthz`

Returns the same payload as `/health` and is intended for Kubernetes probes. Trace IDs rotate per request, while component
status and metadata remain aligned.

### `GET /meta/sources`

Lists supported data sources (`sample`, `bea`, `census`). Use this to drive UI dropdowns or validation in clients.

### `POST /evaluate`

Compute Idiot Index metrics for a given year. Provide either a `source` (which will use configured API keys) or `records` containing inline data. Inline datasets must include at least `industry_code`, `industry_name`, `year`, and `gross_output` columns.

```bash
curl -X POST http://localhost:9000/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "source": "sample",
    "year": 2021,
    "records": [
      {"industry_code": "311", "industry_name": "Food manufacturing", "year": 2021, "gross_output": 123.4, "materials_cost": 87.6},
      {"industry_code": "312", "industry_name": "Beverages", "year": 2021, "gross_output": 98.7, "materials_cost": 62.1}
    ],
    "top_n": 5
  }'
```

Successful responses include leaderboard entries, metadata, and the full/filtered datasets:

```json
{
  "source": "sample",
  "year": 2021,
  "filters": {"search": null, "top_n": 5},
  "average_idiot_index": 1.42,
  "notes": [
    "[manufacturing_cost_driver] Materials share leader: Food manufacturing (311) at 52.1%"
  ],
  "leaderboard": [
    {"industry_code": "311", "industry_name": "Food manufacturing", "idiot_index": 1.51}
  ],
  "dataset": {
    "full": [
      {"industry_code": "311", "idiot_index": 1.51, "resilience_score": 0.44}
    ],
    "filtered": [
      {"industry_code": "311", "idiot_index": 1.51, "resilience_score": 0.44}
    ]
  },
  "health": {
    "filtered": {
      "overall": {"average_health_score": 68.4, "risk_band": "moderate_input_intensity"},
      "band_breakdown": [
        {"band": "moderate_input_intensity", "industries": 3, "percentage": 60.0},
        {"band": "higher_input_intensity", "industries": 2, "percentage": 40.0}
      ],
      "top_risks": [
        {"industry_code": "44-45", "industry_name": "Retail", "health_score": 42.1, "band": "review_required"}
      ]
    }
  },
  "metadata": {
    "source": "api-inline",
    "extensions": {
      "manufacturing_cost_driver": {
        "top_industry": {"industry_code": "311", "materials_share_pct": 52.1},
        "average_materials_share_pct": 38.2
      }
    },
    "telemetry": {"trace_id": "dd7b0a3f1a6a4f5e97d060e0c67d833e"}
  }
}
```

### `POST /scenario`

Runs Scenario Lab adjustments on a supplied dataset. The baseline records should typically be taken from an `/evaluate` response.

```bash
curl -X POST http://localhost:9000/scenario \
  -H "Content-Type: application/json" \
  -d '{
    "base_records": [...],
    "adjustments": [
      {"gross_output_delta_pct": 5.0},
      {"materials_cost_delta_pct": -2.0, "industry_codes": ["311"]}
    ]
  }'
```

The response contains baseline/scenario summaries, per-industry deltas, and metadata copied from the dataset.

### `POST /analytics/health`

Returns only the health analytics envelope for the supplied dataset. Accepts the same payload as `/evaluate` plus optional `group_by` (`overall`, `sector`, or `all`) and `top_risks` parameters.

```bash
curl -X POST http://localhost:9000/analytics/health \
  -H "Content-Type: application/json" \
  -d '{
    "source": "sample",
    "year": 2021,
    "group_by": "sector",
    "top_risks": 3
  }'
```

The response mirrors the `health` section embedded in `/evaluate` but omits leaderboard and dataset payloads, making it ideal for dashboards and scheduled reporting.

### `GET /metrics`

Exposes Prometheus-formatted metrics covering request counts, latencies, and error totals. Scrape this endpoint from your monitoring system or curl it manually:

```bash
curl http://localhost:9000/metrics
```

### `GET /observability/status`

Returns a JSON snapshot of the observability registry, including metric counts, exported span totals, registered health checks, and the most recent operations recorded by instrumentation extensions. The response mirrors `python src/scripts/observability_snapshot.py --pretty` for use in air-gapped environments.

```json
{
  "metrics": {
    "counters": 6,
    "gauges": 1,
    "histograms": 2,
    "subscriptions": {"service.idiot_index.evaluate": 2}
  },
  "traces": {"exported_spans": 24},
  "recent_events": [
    {
      "name": "service.idiot_index.evaluate",
      "duration": 0.183,
      "status": "success",
      "attributes": {"source": "sample", "year": 2021, "has_search": false},
      "trace_id": "ff2c7f264bfb4cc2b7f0a4c947f8a85a"
    }
  ],
  "health_checks": ["configuration", "cache", "extensions", "instrumentation_core"]
}
```

### `GET /observability/digest`

Provides the same observability snapshot as `/observability/status` but enriches it with aggregate event counters, subscription counts, and the last error payload.

```json
{
  "metrics": {"counters": 6, "gauges": 1, "histograms": 2, "subscriptions": {"service.idiot_index.evaluate": 2}},
  "traces": {"exported_spans": 24},
  "health_checks": ["configuration", "cache", "extensions", "instrumentation_core"],
  "events": {
    "counts": {"success": 20, "error": 1},
    "total": 21,
    "recent": [...],
    "last_error": {
      "name": "service.scenario.plan",
      "status": "error",
      "error": "ValueError('invalid adjustment')",
      "timestamp": "2025-11-05T13:58:01.000000+00:00"
    }
  },
  "subscriptions": {"service.dataset.profile": 1, "service.scenario.profile": 1}
}
```

### `GET /observability/events`

Returns the most recent observation events emitted by the registry in reverse chronological order. Optional query parameters allow filtering by status (`success`, `error`, etc.) and limiting the number of events returned (default `25`, maximum `100`).

```json
{
  "events": [
    {
      "name": "service.idiot_index.evaluate",
      "status": "success",
      "duration": 0.241,
      "timestamp": "2025-11-05T14:11:03.123456+00:00",
      "attributes": {"source": "sample", "year": 2021},
      "trace_id": "f1d2315f7bd34ea5"
    }
  ],
  "total_available": 12,
  "applied_limit": 25,
  "applied_status": null
}
```

### `GET /observability/snapshots`

Returns metadata for every persisted snapshot in capture order (newest first). Use this catalogue to discover snapshot identifiers before fetching the full payload.

```json
[
  {
    "snapshot_id": "20251031T120512345Z-nightly01",
    "captured_at": "2025-10-31T12:05:12.345000+00:00",
    "metadata": {"label": "nightly"}
  },
  {
    "snapshot_id": "20251030T235959000Z-cli42a7",
    "captured_at": "2025-10-30T23:59:59+00:00",
    "metadata": {"source": "cli"}
  }
]
```

### `GET /observability/snapshots/{snapshot_id}`

Returns the full snapshot payload (matching the structure of `/observability/digest`) alongside metadata for the supplied identifier. Snapshots are stored on disk and can be captured via `make observability-snapshot` or `python src/scripts/observability_snapshot.py --store`.

```json
{
  "snapshot_id": "20251031T120512345Z-nightly01",
  "captured_at": "2025-10-31T12:05:12.345000+00:00",
  "metadata": {"label": "nightly"},
  "payload": {
    "metrics": {"counters": 6, "gauges": 1, "histograms": 2},
    "traces": {"exported_spans": 28},
    "health_checks": ["configuration", "cache", "extensions", "instrumentation_core"],
    "events": {
      "total": 17,
      "counts": {"success": 16, "error": 1},
      "recent": [
        {"name": "service.dataset.profile", "status": "success", "duration": 0.08},
        {"name": "service.idiot_index.evaluate", "status": "error", "duration": 0.31}
      ],
      "last_error": {"name": "service.idiot_index.evaluate", "status": "error", "error": "ValueError('no data')"}
    },
    "subscriptions": {"service.idiot_index.evaluate": 2}
  }
}
```

## Error handling

- Validation errors (missing required fields, invalid enums) return HTTP 422 with structured details from the lightweight validator.
- Domain errors (empty datasets, missing API keys) return HTTP 400 with a descriptive message from the application layer.
- Server errors return HTTP 500; check container logs for tracebacks.

## Authentication & security

The API currently trusts the environment configuration (including BEA/Census API keys). Deploy behind your preferred authentication layer or reverse proxy when exposing to untrusted networks.
