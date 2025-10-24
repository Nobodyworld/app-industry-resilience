# Changelog

## 2025-10-20
- Documented architecture, API contracts, workflows, and dependency posture across new `/docs` guides with README cross-links.
- Modernised tooling targets and changelog/CONTRIBUTING/SECURITY guidance to reflect ExecPlan usage, Streamlit fetch UX, and dependency monitoring.
- Optimised the BEA adapter for vectorised parsing, deduplicated metadata merging, and more informative sidebar progress cues.
- Audited runtime/dev dependencies and recorded review cadence, updating `pyproject.toml` for Python 3.11 compatibility and DX improvements.
- Added Codex Steps 5-11 report artifacts and quality gate verification instructions.

## 2025-10-19
- Reorganised source tree into layered packages (`core`, `adapters`, `infrastructure`, `interfaces`) with compatibility shims.
- Added agent toolkit with dataclass schemas and documented interface.
- Fixed missing imports across cache, security, logging, adapters, and utilities.
- Updated tests and documentation to reflect new structure; all pytest suites pass.
- Added architecture and verification reports plus expanded README guidance.
