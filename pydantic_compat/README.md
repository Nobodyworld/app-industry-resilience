# Pydantic Shim

The real project depends on Pydantic-style models, but the repository uses this lightweight shim to keep tests and tooling self-contained. Only the subset of functionality exercised by the application is implemented here.

If you need additional features, extend the shim cautiously and add regression tests in `tests/` to confirm compatibility.
