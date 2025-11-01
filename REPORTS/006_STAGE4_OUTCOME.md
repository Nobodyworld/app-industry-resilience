# Stage 4 – Stewardship Audit & Tooling Alignment

## Outcomes
- Produced reproducible stewardship metrics via `scripts/audit_metrics.py` and surfaced them in `docs/handbook/STEWARDS_REPORT.md`.
- Unified script execution by auto-bootstrapping the repository root, enabling direct `python scripts/<tool>.py` invocations.
- Simplified API telemetry span handling and tagged automation entry points (`make observability`, `make audit`) for agents.
- Captured automation responsibilities in `AUTOMATION_ROLES.md` and updated contributor docs with the new audit workflow.

## Verification
- `python scripts/audit_metrics.py --runs 3`
- `python scripts/observability_snapshot.py --pretty`
- `python scripts/check_health.py --pretty`
- `pytest` (via `make quality-gate`)

## Follow-ups
- Vendor offline wheels for `pytest-cov` to restore native coverage enforcement in the quality gate.
- Break down `src/core/security` and `src/core/config` into smaller helpers to reduce audit-highlighted complexity.
- Add long-running telemetry persistence (e.g., file-backed spans) so audit histories survive restarts.
