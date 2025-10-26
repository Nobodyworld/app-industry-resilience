# Stage 3 – Stabilise, Extend, Future-Proof

## Highlights
- Implemented the `ObservabilityRegistry` and instrumented the Idiot Index service, scenario planner, and API, delivering a unified `/observability/status` endpoint plus an offline `observability_snapshot` CLI.
- Extended the extension system with instrumentation plugins (reference `core_instrumentation`) and added scaffolds for new extensions/services to keep future contributions observability-ready.
- Hardened developer automation through the new `make observability` target, updated quality gate docs, Dependabot labelling, and refreshed incident-response guidance.

## Verification
- `make quality-gate`
- `pytest tests/test_observability.py tests/test_scripts.py::test_observability_snapshot_outputs_json`

## Follow-ups
- TODO-P1(12h): Implement distributed rate limiting via Redis to unlock multi-instance deployments.
- TODO-P2(8h): Allow explicit dtype overrides in `normalize.py` for evolving partner schemas.
