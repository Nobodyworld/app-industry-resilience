# Post-v0.4.0 hardening closure record

This record closes issue #134 and supersedes the remaining unchecked acceptance/merge items in `post-v0.4.0-redis-8-compatibility.md`. That earlier ExecPlan remains preserved as the implementation and local-acceptance history; its stale unchecked tail is historical rather than active work.

## Final disposition

- Published v0.4.0 remains unchanged at release-code commit `eec9886c5f0a4ef495b6b31c3c2cc6cdc52e631a`.
- Workspace-governance PR #131 merged as `d3c4df63ab0e473642f75a9060705f074eddefeb`.
- All-files CI PR #121 merged as `53d404b2e6624d55b36ac6320547613b95ada469`.
- Redis/fakeredis hardening PR #135 was accepted at head `0a8930d682fdd51b8f08be75fa1ad16df9d0b517` and squash-merged to `main` as `1918445acf28587b187d032d4cfc24e13778ccce` on 2026-09-07.

## Acceptance evidence

The owner-supplied local acceptance report for PR #135 recorded:

- Python 3.13.7, redis 8.1.0, fakeredis 2.37.1, lupa 2.8;
- focused matrix: 53 passed, 3 skipped;
- complete suite: 475 passed, 3 skipped in each coverage run;
- runtime coverage: 87.75%, above the 85% gate;
- full-source coverage: 82.31%, informational;
- installed-environment and requirements audits: no known vulnerabilities;
- two clean all-files pre-commit passes plus formatting, lint, types, benchmark, secret scan, and pip checks: pass;
- local GNU Make, Docker, and real Redis: not run because those runtimes were unavailable.

The exact merge commit then completed the hosted post-merge checks successfully:

- Quality Gate — run `34103598107`, job `101683442765`;
- Docker Deployment Smoke — run `34103598064`, job `101683442607`;
- Redis Compatibility — run `34103598090`, job `101683441743`;
- dependency graph update — run `34103603697`, job `101683465365`;
- subsequent Dependabot checks on the same merge commit also completed successfully.

Docker-hosted validation covered Streamlit and API startup/health. Redis-hosted validation covered exact minimum compatibility installation, installed-environment audit, real Redis service initialization, focused compatibility tests, and service cleanup.

## Workspace disposition

The local acceptance checkout/environment/evidence were intentionally retained through the merge decision. The last reported retained footprint was approximately 0.88 GB. Root `AGENTS.md` remains authoritative for any later local cleanup: remove only proven task-owned disposable content after checking process use, worktree/clone identity, ignored/untracked content, and preservation of unique evidence. Preserve reports, unrelated workspaces/stashes, restricted or unknown scratch paths, and shared caches. Do not force removal or change ACLs.

Local cleanup is a storage-reconciliation task, not a remaining code or acceptance blocker for issue #134.

## Outcome

Post-v0.4.0 hardening is complete. The repository returns to product work with issue #139 as the active workstream: publish a live, no-credential Streamlit public demo and deployment contract.
