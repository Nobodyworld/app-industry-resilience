# Release Notes

## 2025-02-18

### Highlights
- Headless API no longer depends on external FastAPI/Pydantic/Uvicorn wheels; lightweight facades provide the required behaviour for health, evaluation, and scenario endpoints.
- `scripts/run_api.py` now embeds a threaded WSGI server so the API can be launched locally or in Docker without third-party servers, while keeping the CLI interface stable.
- Added `scripts/run_pytest_trace.py` and documentation for generating offline coverage via Python's built-in trace module. Coverage artefacts are written to `build/coverage/`.
- Documentation refreshed to explain the FastAPI-compatible façade, offline coverage workflow, and the new API server semantics.

### Upgrade / Migration Notes
- Remove `fastapi`, `uvicorn`, and `pydantic` from any pinned dependency lists when rebasing; the repository now provides those modules internally.
- If production deployments rely on real FastAPI/Uvicorn features (e.g., ASGI middlewares), replace the stub modules with the genuine packages in that environment by updating `PYTHONPATH` before importing the repo's code.
- Use `python -m trace --count --coverdir build/coverage scripts/run_pytest_trace.py` to reproduce the coverage report on systems without `pytest-cov`.
- The API CLI ignores `--reload`/`--workers` flags (preserved for compatibility). Adjust automation to avoid relying on hot reload semantics.

