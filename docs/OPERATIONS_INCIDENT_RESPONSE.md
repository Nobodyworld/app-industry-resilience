# Operations & Incident Response

This runbook captures the high-level steps for responding to runtime, data-source, and extension failures in the Industry Resilience platform.

## 1. Detect and triage

1. Check the Prometheus metrics endpoint (`/metrics`) for request spikes or elevated error counters such as `idiot_index_api_errors_total`.
2. Query `/observability/status`, `/observability/digest`, or `/observability/snapshots`. For local inspection, run:

   ```bash
   python src/scripts/observability_snapshot.py --store --list
   python src/scripts/observability_tail.py --follow
   ```

   The `snapshot_persistence` instrumentation extension captures snapshots automatically on startup, shutdown, and `warn` or `error` events. To compare a stored snapshot with current state, run:

   ```bash
   python src/scripts/observability_snapshot.py --compare <snapshot.json>
   ```

3. Inspect the connector catalog through `/meta/connectors` or:

   ```bash
   make connectors-catalog ARGS="--json --pretty"
   ```

   Connector health components include remediation details such as missing credentials or unsupported years.
4. Correlate trace IDs from structured logs with client reports. API responses expose the active trace ID through health and response metadata.
5. Validate service health through `/health` or `/healthz`, or run:

   ```bash
   python src/scripts/check_health.py --pretty
   ```

6. Capture a consolidated evidence bundle when the incident needs escalation or archival:

   ```bash
   python src/scripts/diagnostics_bundle.py --pretty --include-metrics --output build/reports/diagnostics.json
   ```

## 2. Contain and mitigate

- **Extension failure:** Remove the affected module from `extensions/manifest.json` or set `IDIOT_INDEX_EXTENSIONS` to a curated module list. The extension manager skips modules that fail during loading and records the failure with trace context.
- **Data-source outage:** Use the bundled sample source for continued demonstration, or rely on validated cached responses while the upstream provider recovers. Do not represent cached or sample results as current official data.
- **Connector drift:** Review the connector health details in `/meta/connectors` and `/observability/digest`. Reapply credentials, verify supported year ranges, or disable the owning extension until the contract is corrected.
- **Rate-limiter degradation:** Inspect the `rate_limiting` health component and `rate_limit_backend_up`, `rate_limit_requests_total`, and `rate_limit_wait_seconds` metrics. Redis failures should degrade to the configured in-memory fallback with warning status rather than silently disabling enforcement.
- **Performance degradation:** Inspect API-duration histograms, recent observability events, and the diagnostics bundle. Reduce scenario scope or run multiple API instances only after confirming the workload is stateless and the configured rate-limit backend supports the deployment topology.
- **Bad deployment:** Roll back through the normal deployment mechanism to the last validated commit. Do not bypass `CI / Quality Gate` or alter protected `main` directly during recovery.

### Redis failure and recovery contract (post-v0.4.0, unreleased)

Monitor `rate_limit_backend_up{backend="redis"}`: successful Redis decisions set it to `1`, failures set the same labelled sample to `0`, and recovery restores `1`. Do not use a separate `backend="redis-fallback"` gauge sample as the Redis availability signal. Active `redis-fallback` mode remains in request counters and health summaries. The health component must transition `pass` → `warn` → `pass`, clearing `last_error` after a successful Redis operation.

The application client uses no automatic connection/command retries. `RATE_LIMIT_REDIS_TIMEOUT_SECONDS` supplies both connection and response timeouts; an unset value uses 1.0 second for each. Values must be finite and positive. These are per-operation socket timeouts, not a total request deadline: DNS resolution, connection handshakes, and multiple protocol operations can add time. Increase the value explicitly only for a measured deployment need.

An interrupted Lua reply may mean the server already consumed a token. The application must not automatically replay that mutation. It retains its existing local-memory fallback, which favors availability but is not globally coordinated across processes and cannot provide exactly-once token accounting after ambiguous failures. Reconnecting on a later enforcement call is permitted; do not flush Redis databases to recover.

Use only task-owned services for fault tests. `tests/test_redis_failure_contract.py` covers the production client construction path, a reserved non-listening loopback port, a stalled loopback response, and injected lost replies after real Lua execution. The controlled 50-millisecond timeout tests require fallback within one second; this is a test bound, not a production service-level promise. Set `REDIS_COMPAT_URL` only to a disposable Redis 8 service to include the real-server cases. Tests use unique key prefixes and exact-key cleanup.

See the [unreleased hardening notes](RELEASE_NOTES_POST_V0.4.0_HARDENING.md) and [compatibility execution plan](execplans/post-v0.4.0-redis-8-compatibility.md). These changes are not part of the immutable published v0.4.0 release.

## 3. Recover and verify

1. Apply the smallest corrective change through a pull request.
2. Run `make quality-gate` locally when possible and require the hosted `CI / Quality Gate` check before merge. Audit the installed test environment with `python -m pip_audit --local --strict` in addition to the requirements audit.
3. For deployment-sensitive changes, run the pinned `Docker Smoke` workflow and confirm:
   - production image build;
   - non-root runtime user;
   - Streamlit health;
   - API `/health` and `/metrics`;
   - evidence artifact upload.
4. Confirm health components return to `pass` or an understood `warn` state, error counters stabilize, and affected connector data is current.
5. Record the resolution in the relevant issue or pull request. Add regression tests when code changes were required.

## 4. Post-incident checklist

- Update alerts or health checks based on the root cause.
- Review whether logs or evidence bundles contain sensitive data before sharing them publicly.
- Update the relevant operational, connector, extension, or architecture guide when the mitigation changed expected procedure.
- Create a focused follow-up issue for deferred reliability work rather than expanding the incident fix.

Following these steps keeps the public-beta platform observable, recoverable, and aligned with protected-branch and validation policy.
