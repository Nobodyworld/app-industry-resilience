# Public Release Validation (Pre-Rename + Post-Rename Normalization)

- Repository (canonical): app-industry-resilience
- Owner: Nobodyworld
- Validation date: 2026-07-01
- Validation mode: local clean clone of remote main on Windows

## Policy Constraints Confirmed

1. Repository visibility unchanged (private).
2. Existing tag `public-release-2026-07-01` preserved without deletion or force-move.
3. Post-rename publication uses a new annotated tag `public-release-2026-07-01-r2`.

## A. Pre-Rename Candidate Evidence (Historical Baseline)

This section preserves the evidence anchor from the original repository identity before rename.

- Historical repository identity: `Nobodyworld/app-economics-idiot-index`
- Historical anchor commit (main + old publication tag target commit): `797ce5c92f7defa4aa59f6ad818733d651a3c9e6`
- Quality gates passed: pip check, Ruff, Black --check, mypy, pytest
- Test outcome: `271 passed`
- Runtime coverage gate: `86.01%` (threshold `>=85%`, passed)
- Full-source informational coverage: `80%`
- pip-audit: no known vulnerabilities
- detect-secrets baseline: passed
- Full-history gitleaks findings: `16` (classified false positives)
- Historical `git rev-list --all --count`: `123`

## B. Repository Identity Normalization Performed

Completed changes after the pre-rename baseline:

1. GitHub repository renamed to `Nobodyworld/app-industry-resilience`.
2. Local `origin` updated to canonical URL.
3. Description/topics normalized to release naming requirements.
4. Identity metadata and docs normalized where repository naming was stale.
5. Product analytics terminology (`Idiot Index`) retained where semantically correct.

## C. Post-Rename Clean-Clone Validation Evidence

Validation clone source:

- Source URL: <https://github.com/Nobodyworld/app-industry-resilience>
- Clone path style: clean ephemeral folder outside active workspace edits
- Python: 3.14.0

Post-rename gate outcomes:

1. `pip check`: passed (`No broken requirements found.`)
2. `ruff check app.py src tests`: passed (`All checks passed!`)
3. `black --check app.py src tests`: passed (`129 files would be left unchanged.`)
4. `mypy src`: passed (`Success: no issues found in 96 source files`)
5. `pytest -q`: passed (`271 passed`)
6. Runtime coverage gate (`--cov-fail-under=85`): passed (`86.01%`)
7. Full-source informational coverage (`--cov=src`): completed (`80%`)
8. `pip-audit`: passed (`No known vulnerabilities found`)
9. `detect-secrets-hook --baseline config/.secrets.baseline`: passed (`exit=0`)
10. Scenario smoke: passed; report emitted to `build/reports/scenario_smoke.json`
11. Public-data backfill smoke: passed; report emitted to `build/reports/public_backfill_smoke.json`
12. Public-data backtest smoke: passed; report emitted to `build/reports/public_backtest_smoke.json`
13. Streamlit startup + HTTP probe: passed (`status=200`)
14. API startup + `/health` + `/metrics` probes: passed (`200/200`)
15. Export smoke: passed (`count=6`, mimes include CSV/JSON/XLSX)
16. README+docs link validation: passed (`0` internal broken, `0` external broken)
17. Full-history gitleaks: findings `16` (false-positive disposition unchanged)
18. Post-rename `git rev-list --all --count`: `127`
19. Docker CLI availability: `NOT EXECUTED - Docker CLI unavailable`

False-positive classification for gitleaks findings remains:

- `14` findings from detector hashes in `config/.secrets.baseline`
- `2` findings from fixture-like strings in `tests/test_config.py`

## D. Actions/CI Disposition

- GitHub Actions remain disabled by owner policy.
- Local clean-clone validation is the authoritative release gate for this publication.

## E. Immutable Publication Tag (Post-Rename)

Publication tag policy for this normalization pass:

1. Keep `public-release-2026-07-01` immutable.
2. Create new annotated tag: `public-release-2026-07-01-r2`.
3. Ensure `public-release-2026-07-01-r2` resolves to the exact validated `main` commit used for publication.

Release classification: `READY FOR PUBLIC RELEASE`
