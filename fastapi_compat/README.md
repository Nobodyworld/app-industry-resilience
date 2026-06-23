# FastAPI Compatibility Layer

This package provides a minimal FastAPI-like surface used by the headless API mode. It mirrors the subset of classes and helpers that the application requires so the repository can run in offline or constrained environments without installing the real FastAPI dependency.

Modules here are intentionally small and should remain API-compatible with the portions exercised by `src/interfaces/api` and the test suite. Update the documentation in [`docs/handbook/ARCHITECTURE.md`](../docs/handbook/ARCHITECTURE.md) if you expand the shim.
