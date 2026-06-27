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

Do not commit other production datasets here. Large or sensitive data should remain in external storage.
