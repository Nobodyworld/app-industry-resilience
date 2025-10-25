# Operations & Incident Response

This runbook captures the high-level steps for responding to production issues in the Idiot Index platform.

## 1. Detect & Triage

1. Check the Prometheus metrics endpoint (`/metrics`) for request spikes or elevated error counters (`idiot_index_api_errors_total`).
2. Correlate trace IDs from logs (look for `trace=<id>` in structured log output) with client reports. Each API response exposes the current `trace_id` via `/health` and in the `metadata.telemetry.trace_id` field.
3. Validate platform health by calling `/healthz`.

## 2. Contain & Mitigate

- **Extension Failures:** Disable problematic extensions by removing them from `extensions/manifest.json` or setting `IDIOT_INDEX_EXTENSIONS` to a curated list. The manager skips modules that raise exceptions but logs the failure with a trace ID.
- **Data Source Outage:** Switch the `MetricConfig` cache flag via API request (`use_cache=true`) to operate on cached data while upstream services recover.
- **Performance Degradation:** Inspect `idiot_index_api_request_duration_seconds` histograms to identify slow endpoints. Consider reducing scenario complexity or scaling horizontally (run multiple API instances behind a load balancer).

## 3. Recovery & Verification

1. Redeploy updated extensions or configuration changes through the normal release process (update manifest, run `make quality-gate`, commit, and deploy).
2. Confirm metrics return to baseline and error counters stabilize.
3. Capture learnings in `CHANGELOG.md` and, if code changes were required, document them in the relevant ExecPlan.

## 4. Post-incident Checklist

- Update monitoring alerts based on the root cause.
- Add regression tests for the failure mode when feasible.
- Review documentation (`EXTENSION_GUIDE.md`, `README.md`) to ensure mitigation steps are captured for future responders.

Following these steps keeps the Idiot Index platform observable, resilient, and ready for collaborative maintenance.
