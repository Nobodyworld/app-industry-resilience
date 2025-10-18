import pandas as pd
from typing import Any, Optional

REQUIRED_COLS = ['industry_code','industry_name','year','gross_output']
OPTIONAL_COLS = ['materials_cost','intermediate_inputs','value_added','source']

# TODO - Add support for custom column mapping configurations
# TODO - Implement data type inference for better column handling
# TODO - Add column validation rules and business logic constraints

def coerce_numeric(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

# TODO - Implement more sophisticated type coercion with unit conversion
# TODO - Add validation for reasonable numeric ranges and data quality checks
# TODO - Implement currency and unit normalization for international data

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Check for required columns
    df_columns = [col.lower().strip() for col in df.columns]
    missing_required = [col for col in REQUIRED_COLS if col not in df_columns]

    if missing_required:
        raise ValueError(f"Missing required columns: {', '.join(missing_required)}. Required: {', '.join(REQUIRED_COLS)}")

    # Lowercase headers
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    # Ensure required + optional exist
    for c in OPTIONAL_COLS:
        if c not in df.columns:
            df[c] = None
    # Types
    df['year'] = df['year'].apply(lambda v: int(float(v)) if pd.notna(v) else None)
    for c in ['gross_output','materials_cost','intermediate_inputs','value_added']:
        df[c] = df[c].apply(coerce_numeric)
    # Trim strings
    df['industry_code'] = df['industry_code'].astype(str).str.strip()
    df['industry_name'] = df['industry_name'].astype(str).str.strip()
    df['source'] = df['source'].astype(str).str.strip()
    return df

# TODO - Add data quality scoring and anomaly detection during normalization
# TODO - Implement automatic column name fuzzy matching for user-uploaded data
# TODO - Add support for custom data transformation pipelines
