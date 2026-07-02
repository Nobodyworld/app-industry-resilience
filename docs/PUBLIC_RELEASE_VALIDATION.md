# Public Release Validation (Clean Clone)

- Repository: app-economics-idiot-index
- Validation date: 2026-07-01
- Validation mode: local clean clone of remote main
- Host OS: Windows

## Immutable Reference Strategy

To avoid self-referential SHA drift, this document separates three identifiers:

1. Previously validated software candidate SHA (historical, already executed).
2. Final confirming clean-clone run (executed after this document commit).
3. Annotated publication tag (immutable release reference for publication).

This document does not pre-claim a post-commit SHA that did not yet exist at edit time.
The final immutable release reference is the annotated publication tag.

## Source and Clone Metadata

- Source URL: <https://github.com/Nobodyworld/app-economics-idiot-index>
- Previous clean-clone validation candidate SHA: 2d364a3169961dcec16383261262ba1b5e3a2157
- Final confirming clean-clone target: current main HEAD after this documentation commit
- Planned publication tag: public-release-2026-07-01
- Validation clone location style: workspace-relative ephemeral folder under build/

## Runtime and Environment

- Clean-clone Python: 3.14.0
- Packaging policy target: Python 3.13+
- GitHub Actions repository setting: disabled by owner policy (enabled: false)

## Final Confirming Clean-Clone Gate (Required)

Run this full gate against the new main HEAD created by the documentation correction commit:

1. Clone repository to a new clean folder.
2. Create virtual environment and install runtime + dev dependencies.
3. Run pip integrity: pip check.
4. Run lint and format checks: Ruff + Black --check.
5. Run type checks: Mypy.
6. Run full tests.
7. Run runtime coverage gate (policy paths, fail-under=85).
8. Run full-source informational coverage.
9. Run dependency audit: pip-audit.
10. Run baseline secret check: detect-secrets-hook --baseline config/.secrets.baseline.
11. Run scenario smoke.
12. Run public-data backfill and rolling backtest smoke.
13. Run Streamlit startup + HTTP probe.
14. Run API startup + health + metrics probes.
15. Run export smoke (CSV/JSON/XLSX MIME verification).
16. Run README+docs link validation.
17. Run full-history gitleaks scan and record exact git rev-list --all --count output.
18. Check Docker CLI availability and classify accurately.

## Full-History Secret Scan Policy

- Tool: gitleaks 8.30.1
- Command: gitleaks git . --log-opts='--all' --report-format json --report-path build/reports/gitleaks-full-history-final.json
- Scope: all reachable history from git rev-list --all
- Known repeated false-positive pattern classes to review explicitly:
  - hashed detector entries in config/.secrets.baseline
  - fixture-like key strings in tests/test_config.py

The final publication evidence must report:

- exact output of git rev-list --all --count
- findings count
- false-positive disposition
- final scan result

## Docker Classification

If Docker CLI is unavailable on the validation host, classify exactly as:

NOT EXECUTED - Docker CLI unavailable

This remains a P1 limitation, not a P0 blocker, when all required software-quality gates pass.

## Actions/CI Disposition

Repository GitHub Actions are currently disabled by owner policy.
No workflow badge/run should be used as release proof.
Local clean-clone validation is the authoritative publication gate.
