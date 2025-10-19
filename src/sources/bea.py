from __future__ import annotations

import time

import pandas as pd

from ..cache import get_api_cache
from ..config import load_config
from ..logging_config import (
    log_api_call,
    log_cache_hit,
    log_cache_miss,
    log_performance,
    logger,
)
from ..normalize import normalize_columns
from ..rate_limiter import api_limiter
from ..security import SecurityUtils
from ..utils import safe_get_json

# BEA API endpoints and parameters
# GDPbyIndustry dataset provides Gross Output (GO) and Intermediate Inputs (II)
# TableID 1: Gross Output by Industry
# TableID 2: Intermediate Inputs by Industry

BEA_BASE = "https://apps.bea.gov/api/data"

# TODO - Implement API endpoint health monitoring and failover
# TODO - Add support for BEA API version negotiation and compatibility
# TODO - Implement BEA API response caching with smart invalidation

def fetch_go_ii_by_industry(api_key: str, year: int) -> pd.DataFrame:
    start_time = time.time()
    config = load_config()

    key_result = SecurityUtils.validate_api_key(api_key, "BEA")
    if not key_result.ok:
        logger.error(key_result.message)
        raise RuntimeError(key_result.message)

    year_result = SecurityUtils.validate_year(year)
    if not year_result.ok:
        raise RuntimeError(year_result.message)

    if year_result.value not in config.supported_years_bea:
        raise RuntimeError(
            f"Year {year_result.value} is outside supported BEA range "
            f"{config.supported_years_bea.start}-"
            f"{config.supported_years_bea.stop - 1}."
        )

    cache = get_api_cache(config.cache)
    cache_key = f"bea_go_ii_{year_result.value}"
    if cache:
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            log_cache_hit(cache_key, "api")
            log_performance("BEA API fetch (cached)", time.time() - start_time)
            return pd.DataFrame(cached_result)

    log_cache_miss(cache_key, "api")

    api_limiter.wait_for_api("bea")

    # TODO - Implement parallel API calls for multiple years
    # TODO - Add API response compression and optimization
    # TODO - Implement BEA API pagination handling for large datasets

    # Fetch Gross Output (TableID 1)
    go_params = {
        "UserID": api_key,
        "method": "GetData",
        "datasetname": "GDPbyIndustry",
        "TableID": "1",  # Gross Output
        "Frequency": "A",
        "Year": str(year_result.value),
        "Industry": "ALL",
        "ResultFormat": "json"
    }

    go_data = safe_get_json(BEA_BASE, params=go_params)
    log_api_call("BEA", "GDPbyIndustry Table 1", go_params)

    # Fetch Intermediate Inputs (TableID 2)
    ii_params = {
        "UserID": api_key,
        "method": "GetData",
        "datasetname": "GDPbyIndustry",
        "TableID": "2",  # Intermediate Inputs
        "Frequency": "A",
        "Year": str(year_result.value),
        "Industry": "ALL",
        "ResultFormat": "json"
    }

    ii_data = safe_get_json(BEA_BASE, params=ii_params)
    log_api_call("BEA", "GDPbyIndustry Table 2", ii_params)

    # Process Gross Output data
    go_df = _process_bea_table(go_data, "gross_output")

    # Process Intermediate Inputs data
    ii_df = _process_bea_table(ii_data, "intermediate_inputs")

    # Merge the datasets
    df = pd.merge(
        go_df,
        ii_df,
        on=["industry_code", "industry_name", "year"],
        how="outer",
    )
    df["source"] = "BEA (Economy-wide)"
    normalized = normalize_columns(df)
    normalized["materials_cost"] = pd.NA
    normalized["value_added"] = pd.NA

    if cache:
        cache.set(cache_key, normalized.to_dict("records"))

    log_performance("BEA API fetch", time.time() - start_time)
    logger.info(
        "Successfully processed %s BEA industry records for year %s",
        len(normalized),
        year_result.value,
    )

    return normalized

def _process_bea_table(data: dict, value_column: str) -> pd.DataFrame:
    """Process BEA API response into standardized DataFrame format."""
    if not data or 'BEAAPI' not in data or 'Results' not in data['BEAAPI']:
        raise RuntimeError("Unexpected BEA API response structure")

    results = data['BEAAPI']['Results']

    if 'Error' in results:
        error = results['Error']
        raise RuntimeError(f"BEA API Error {error.get('APIErrorCode', 'Unknown')}: {error.get('APIErrorDescription', 'Unknown error')}")

    if 'Data' not in results:
        raise RuntimeError("No data found in BEA API response")

    rows = []
    for item in results['Data']:
        try:
            value = float(str(item.get('DataValue', '0')).replace(',', '')) * 1_000_000
        except ValueError:
            value = None
        year = item.get('Year')
        try:
            year_int = int(year)
        except (TypeError, ValueError):
            year_int = 0
        row = {
            'industry_code': item.get('Industry', ''),
            'industry_name': item.get('IndustrYDescription', item.get('Industry', '')),
            'year': year_int,
            value_column: value,
        }
        rows.append(row)

    return pd.DataFrame(rows)

# TODO - Add BEA data validation and quality checks during processing
# TODO - Implement BEA industry code mapping and standardization
# TODO - Add support for BEA API metadata extraction and documentation

