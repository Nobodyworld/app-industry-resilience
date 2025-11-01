# Test Suite Overview

Tests mirror the structure of the `src/` tree and exercise the application from multiple angles:

- `test_application.py`, `test_core.py`, etc. validate domain logic and analytics pipelines.
- `test_api.py` and `test_ui_helpers.py` cover the FastAPI-compatible service and Streamlit utilities.
- `test_observability_*.py` focus on telemetry, health reporting, and snapshot replication.
- `test_agents.py` verifies the agent-facing tool metadata and schemas stay in sync with the underlying services.

Use `make quality-gate` (or `make test` for a quicker pass) to run the full suite with coverage enforcement.
