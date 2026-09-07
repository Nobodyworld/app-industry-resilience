# Dependency Register

This document records the vetted runtime and development dependencies for the U.S. Industry Cost Structure & Resilience Dashboard. Use it during security reviews and upgrade planning. Version constraints below mirror `requirements.txt` and `requirements-dev.txt`; update all three surfaces together.

## Runtime dependencies

| Package | Version | License | Purpose | Review cadence |
| --- | --- | --- | --- | --- |
| `streamlit` | >=1.59.1,<2 | Apache-2.0 | Primary UI and local application server for the interactive dashboard. | Quarterly |
| `pandas` | >=2.3.3,<3 | BSD-3-Clause | Data wrangling, aggregation, normalization, and tabular export preparation. | Quarterly |
| `xlsxwriter` | >=3.2.0,<4 | BSD-2-Clause | Creates formula-safe multi-sheet XLSX exports. | Semi-annual |
| `python-dotenv` | >=1.0.1,<2 | BSD-3-Clause | Loads environment variables from `.env` for local development. | Semi-annual |
| `requests` | >=2.34.2,<3 | Apache-2.0 | HTTP client for official public-data providers with retry support. | Quarterly |
| `plotly` | >=6.3.1,<7 | MIT | Interactive charting components embedded in Streamlit views. | Semi-annual |
| `pytest` | >=8.4.2,<10 | MIT | Supports bundled smoke tests and Streamlit-compatible validation environments. | Quarterly |
| `redis` | >=8.1.0,<9 | MIT | Optional Redis 8 distributed rate-limiting backend used when `RATE_LIMIT_BACKEND=redis`. | Quarterly |
| `botocore` | >=1.43.59,<2 | Apache-2.0 | AWS client foundation used by optional snapshot-storage and replication integrations. | Quarterly |

## Development dependencies

| Package | Version | License | Purpose | Review cadence |
| --- | --- | --- | --- | --- |
| `black` | >=26.5.1,<27 | MIT | Code formatter enforced by pre-commit and the quality gate. | Quarterly |
| `ruff` | >=0.8.0,<1 | MIT | Fast linter covering correctness, style, and import ordering. | Quarterly |
| `mypy` | >=2.3.0,<3 | MIT | Static typing checks for source modules. | Quarterly |
| `pytest-cov` | >=6.0.0,<8 | MIT | Runtime-scoped and full-source coverage reporting. | Quarterly |
| `pre-commit` | >=4.6.1,<5 | MIT | Runs the repository's all-files formatting, linting, typing, hygiene, and secret-scanning contract. | Semi-annual |
| `codespell` | >=2.4.2,<3 | GPL-2.0 | Offline spelling checks for documentation, comments, and source text. | Semi-annual |
| `commitizen` | >=4.16.4,<5 | MIT | Conventional Commit validation and version-management support. | Semi-annual |
| `detect-secrets` | >=1.5.0,<2 | Apache-2.0 | Baseline-backed secret scanning for pre-commit and CI. | Quarterly |
| `pip-audit` | >=2.7.3,<3 | Apache-2.0 | CVE scanning of runtime and development dependency graphs. | Monthly |
| `botocore` | >=1.43.59,<2 | Apache-2.0 | Provides complete development/test coverage for optional AWS-backed integrations. | Quarterly |
| `types-requests` | >=2.32.0,<3 | Apache-2.0 | Type hints for the `requests` library used by mypy. | Semi-annual |
| `fakeredis[lua]` | >=2.37.1,<3 | MIT | Redis 8-compatible sync/async test doubles plus Lua/EVALSHA support for the distributed token bucket. | Quarterly |

## Redis compatibility contract

- `redis>=8.1.0,<9` is the supported optional runtime client range.
- `fakeredis[lua]>=2.37.1,<3` is required in development because `RedisTokenBucket` uses `register_script`, which executes through `EVALSHA`; plain fakeredis does not provide that command path.
- The dedicated Redis compatibility workflow verifies the declared exact minimums under Python 3.13 against both a Redis-8-configured fakeredis server and a disposable real Redis 8 service.
- The production client explicitly disables automatic connection/command retries. A lost Lua response may follow a successful token mutation, so replaying that operation is unsafe. Later enforcement calls can reconnect normally.
- `RATE_LIMIT_REDIS_TIMEOUT_SECONDS` applies to both socket connection and response waits. When unset (configuration value `None`), the client uses 1.0 second for each; explicit values must be finite and positive. These per-operation timeouts are not a total request deadline or a DNS deadline.
- In-memory mode remains the default. Redis failures retain the private in-memory fallback and warning health state. This fallback is not globally coordinated and cannot guarantee exactly-once accounting after a lost response.
- `rate_limit_backend_up{backend="redis"}` is updated to zero on failure and one on recovery. Active fallback mode remains available through decision counters and health summaries.
- The Lua extra installs `lupa` only in development/test environments; it is not a runtime dependency of the application image.

## Review process

1. Run the existing requirements audit through `make security` and record actionable findings in the governing issue or ExecPlan.
2. Also run `python -m pip_audit --local --strict` using the interpreter of each tested virtual environment. Requirements-file resolution alone does not audit the installed minimum-version graph. Record installed versions alongside the result; report skipped or uncollectable packages rather than treating them as covered.
3. For quarterly reviews, inspect upstream release notes for major runtime dependencies and exercise focused compatibility tests before raising version floors.
4. Update this file whenever a dependency is added, removed, or upgraded; keep its constraints identical to the requirements files.
5. Validate optional service dependencies against a disposable service rather than production or user-owned data.
6. Capture temporary pins or exceptions in the relevant ExecPlan and changelog, including an owner and revisit condition.

The [unreleased hardening notes](RELEASE_NOTES_POST_V0.4.0_HARDENING.md) describe the operational changes. Exact-head validation is recorded in PR #135, not inferred from older green runs.

## Data sources

- **BEA GDP by Industry** – accessed through the official API (<https://apps.bea.gov/api/>). Terms of use require attribution when publishing derived data.
- **Census Annual Survey of Manufactures** – accessed through the official API (<https://www.census.gov/data/developers/data-sets/asm.html>). Observe Census data usage policies.
- **BLS PPI and CES** – consumed through bounded committed public-data snapshots and official-provider refresh tooling.
- **Federal Reserve G.17** – consumed through bounded committed public-data snapshots and official-provider refresh tooling.
- **Sample dataset** – derived from public releases for offline demonstrations and stored under `data/`.

---
Licensed under the Apache License 2.0. See [LICENSE](../LICENSE).
