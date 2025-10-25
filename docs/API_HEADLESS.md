# Headless API Guide

The headless Idiot Index API exposes the same computation pipeline that powers the Streamlit dashboard so external systems can automate evaluations and scenario planning.

## Running the service

```bash
make api ARGS="--host 0.0.0.0 --port 9000"
```

This command executes `scripts/run_api.py`, which serves the bundled FastAPI-compatible application defined in `src/interfaces/api/app.py` using Python's built-in WSGI server. The CLI respects the following environment variables (all optional):

- `API_HOST` / `API_PORT` – default network binding (`0.0.0.0:9000`).
- `API_RELOAD` – accepted for compatibility but ignored (reload is not supported in the bundled server).
- `API_WORKERS` – accepted for compatibility but the server always runs single-threaded workers with a threaded WSGI server.
- `API_LOG_LEVEL` – echoed at startup for operator awareness.

Inside Docker, set `APP_MODE=api` to boot the same service from the container entrypoint. The image still honours `PREFETCH_ARGS` to warm caches prior to serving traffic.

## Endpoints

### `GET /health`
Returns service metadata, version, and a trace identifier useful for correlating logs.

```json
{
  "status": "ok",
  "service": "idiot-index-api",
  "version": "0.1.0",
  "trace_id": "1f3e8b7157c448c1aaeb87b7e0e1d2b6",
  "telemetry": {
    "metrics": {"counters": 4, "gauges": 1, "histograms": 1}
  }
}
```

### `GET /healthz`
Returns the same payload as `/health` and is intended for Kubernetes probes. Trace IDs rotate per request.

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

### `GET /metrics`
Exposes Prometheus-formatted metrics covering request counts, latencies, and error totals. Scrape this endpoint from your monitoring system or curl it manually:

```bash
curl http://localhost:9000/metrics
```

## Error handling

- Validation errors (missing required fields, invalid enums) return HTTP 422 with structured details from the lightweight validator.
- Domain errors (empty datasets, missing API keys) return HTTP 400 with a descriptive message from the application layer.
- Server errors return HTTP 500; check container logs for tracebacks.

## Authentication & security

The API currently trusts the environment configuration (including BEA/Census API keys). Deploy behind your preferred authentication layer or reverse proxy when exposing to untrusted networks.
