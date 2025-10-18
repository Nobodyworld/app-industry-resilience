import pandas as pd
from ..utils import safe_get_json
from ..cache import get_api_cache
from ..rate_limiter import api_limiter

# ASM time series endpoints evolve; consult https://api.census.gov/data.html
# Classic variables:
# - RCPTOT: Value of shipments
# - CSTMTOT: Cost of materials
# - VALADD:  Value added
#
# Example endpoint (subject to change):
# https://api.census.gov/data/2021/asm?get=NAICS2017,RCPTOT,CSTMTOT,VALADD&for=us:*

ASM_BASE = "https://api.census.gov/data/2021/asm"

def fetch_asm_manufacturing(api_key: str, year: int) -> pd.DataFrame:
    if not api_key:
        raise RuntimeError("Missing Census API key")

    # Validate year range for Census ASM data
    if year < 1997 or year > 2023:  # Census ASM data availability
        raise RuntimeError(f"Year {year} is outside Census ASM data range (1997-2023)")

    # Check cache first
    cache_key = f"census_asm_{year}"
    cached_result = get_api_cache().get(cache_key)
    if cached_result is not None:
        return pd.DataFrame(cached_result)

    params = {
        "get": "NAICS2017,NAICS2017_LABEL,RCPTOT,CSTMTOT,VALADD",
        "for": "us:*",
        "key": api_key
    }

    # Apply rate limiting
    api_limiter.wait_for_api('census')

    try:
        data = safe_get_json(ASM_BASE, params=params)
    except RuntimeError as e:
        if "GET failed" in str(e):
            raise RuntimeError(f"Census ASM API request failed. This may indicate: 1) Invalid API key, 2) Network connectivity issues, 3) API endpoint changes. Original error: {e}")
        raise

    if not isinstance(data, list) or len(data) < 2:
        raise RuntimeError("Census ASM API returned unexpected data format. The API response structure may have changed.")

    header, *rows = data
    if not rows:
        raise RuntimeError(f"No data available for year {year}. This industry may not have data for the selected year.")

    df = pd.DataFrame(rows, columns=header)

    # Validate expected columns exist
    expected_cols = ["NAICS2017", "NAICS2017_LABEL", "RCPTOT", "CSTMTOT", "VALADD"]
    missing_cols = [col for col in expected_cols if col not in df.columns]
    if missing_cols:
        raise RuntimeError(f"Census ASM API response missing expected columns: {missing_cols}. The API schema may have changed.")

    # Coerce numerics (ASM values often are in thousands of dollars)
    for col in ["RCPTOT","CSTMTOT","VALADD"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.rename(columns={
        "NAICS2017": "industry_code",
        "NAICS2017_LABEL": "industry_name",
        "RCPTOT": "gross_output",
        "CSTMTOT": "materials_cost",
        "VALADD": "value_added"
    })
    df["year"] = year
    df["intermediate_inputs"] = None  # not directly provided
    df["source"] = "Census ASM"
    # Keep plausible columns
    keep = ["industry_code","industry_name","year","gross_output","materials_cost","intermediate_inputs","value_added","source"]
    result_df = df[keep]

    # Cache the result
    get_api_cache().set(cache_key, result_df.to_dict('records'))

    return result_df
