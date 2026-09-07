# Unreleased: post-v0.4.0 Redis hardening

This is the change record for draft PR #135 under issue #134. It is not a new release, a version bump, or an amendment to the published v0.4.0 artifacts. Merge and publication require separate owner decisions.

## Changes

- Validate `redis>=8.1.0,<9` together with development-only `fakeredis[lua]>=2.37.1,<3`, including a disposable real Redis 8 service and exact-minimum installation.
- Correct Redis availability metrics so the stable `backend="redis"` sample becomes zero during failure and returns to one on recovery. Regression tests also check decision counters and health transitions rather than merely checking that samples exist.
- Explicitly disable automatic retries in the application Redis client. A lost Lua reply can follow a completed token mutation; automatically replaying it can consume another token.
- Apply `RATE_LIMIT_REDIS_TIMEOUT_SECONDS` to both socket connection and response waits, using 1.0 second for each when unset. Reject non-finite or non-positive explicit values. These timeouts do not establish a total request or DNS deadline.
- Test production client configuration, connection refusal, stalled responses, and recovery after injected connection/timeout errors following actual Lua execution. Real-server tests verify one mutation attempt and exact-key cleanup.
- Audit the actual installed minimum-version virtual environment with `python -m pip_audit --local --strict`; retain the independent requirements audit in the quality gate.
- Correct completed v0.4.0 publication bookkeeping and use PowerShell-compatible local acceptance instructions.

## Operator notes

Watch `rate_limit_backend_up{backend="redis"}` and the `rate_limiting` health component. Active fallback remains visible as `redis-fallback` in decision counters and summaries. Later enforcement calls may reconnect after an error.

Memory remains the default backend. The existing Redis-to-memory fallback favors continued service but is process-local, not a global quota guarantee or exactly-once token-accounting mechanism after an ambiguous response. No new providers, analytics, snapshots, API routes, or UI features are introduced.

See [incident response](OPERATIONS_INCIDENT_RESPONSE.md), the [dependency register](DEPENDENCIES.md), and the [living execution plan](execplans/post-v0.4.0-redis-8-compatibility.md). Hosted results must match the exact PR head. Windows/local reproduction and workspace preservation evidence remain separate acceptance items.
