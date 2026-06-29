# Extensions Catalog

Extensions expand the Idiot Index platform without modifying core services. The `manifest.json` file declares built-in modules so automation can discover available connectors, instrumentation hooks, and scenario planners.

To add a new extension:

1. Run `python src/scripts/scaffold_extension.py --name <snake_case_name>`.
2. Implement the generated module under `src/extensions/`.
3. Update `manifest.json` with the new entry and rerun `make extensions-catalog` to verify.

Refer to [`docs/handbook/EXTENSION_GUIDE.md`](../docs/handbook/EXTENSION_GUIDE.md) for a deeper walkthrough.
