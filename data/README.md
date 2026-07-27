# Sample Data

The CSV files in this directory provide offline fixtures used by the Streamlit demo, test suite, and documentation examples. They mirror the schema returned by the BEA and Census adapters so you can explore the app without API credentials.

`official_industry_snapshot.csv` is a small, reproducible public-data snapshot generated from
the Census Bureau's 2023 Annual Integrated Economic Survey files released on February 26,
2026. Refresh it with:

```bash
python src/scripts/refresh_official_data.py
```

The snapshot uses revenue as gross output and total operating expenses as an intermediate-input
proxy. It must not be described as the strict BEA Idiot Index.

`industry_pulse_bls_snapshot.csv` is the bounded January 2024–June 2026 monthly PPI context
snapshot for the eight mappings in `docs/INDUSTRY_PULSE_BLS_SERIES.md`.
`industry_pulse_bls_snapshot.metadata.json` records the official endpoint, one-batch requested
window, retrieval time, ordered series IDs, row/date/release bounds, deterministic CSV SHA-256,
registry/schema versions, generator identity, transformations, and interpretation note.
Regenerate both files with:

```bash
python src/scripts/generate_industry_pulse_snapshot.py --start-year 2024 --end-year 2026
```

The generator uses no credential or registration key. Dashboard rendering, API requests, and
tests never call BLS. Do not hand-edit the snapshot or commit the large raw provider response.

Do not commit other production datasets here. Large or sensitive data should remain in external storage.
