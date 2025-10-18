import pandas as pd
import time
from ..utils import safe_get_json
from ..cache import get_api_cache
from ..logging_config import logger, log_api_call, log_cache_hit, log_cache_miss, log_performance
from ..rate_limiter import api_limiter

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
    logger.info(f"Fetching BEA data for year {year}")

    if not api_key:
        logger.error("Missing BEA API key")
        raise RuntimeError("Missing BEA API key")

    # Check cache first
    cache_key = f"bea_go_ii_{year}"
    cached_result = get_api_cache().get(cache_key)
    if cached_result is not None:
        log_cache_hit(cache_key, "api")
        log_performance("BEA API fetch (cached)", time.time() - start_time)
        return pd.DataFrame(cached_result)

    log_cache_miss(cache_key, "api")

    # Apply rate limiting
    api_limiter.wait_for_api('bea')

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
        "Year": str(year),
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
        "Year": str(year),
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
    df = pd.merge(go_df, ii_df, on=['industry_code', 'industry_name', 'year'], how='outer')

    # Add source and fill missing columns
    df['source'] = 'BEA (Economy-wide)'
    df['materials_cost'] = None  # BEA doesn't provide direct materials cost
    df['value_added'] = None     # BEA doesn't provide direct value added

    # Ensure all required columns exist
    required_cols = ['industry_code', 'industry_name', 'year', 'gross_output',
                     'materials_cost', 'intermediate_inputs', 'value_added', 'source']
    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    # Cache the result
    get_api_cache().set(cache_key, df.to_dict('records'))

    log_performance("BEA API fetch", time.time() - start_time)
    logger.info(f"Successfully processed {len(df)} BEA industry records for year {year}")

    return df

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
        row = {
            'industry_code': item.get('Industry', ''),
            'industry_name': item.get('IndustrYDescription', item.get('Industry', '')),
            'year': int(item.get('Year', 0)),
            value_column: float(item.get('DataValue', 0)) * 1000000  # Convert millions to actual dollars
        }
        rows.append(row)

    return pd.DataFrame(rows)

# TODO - Add BEA data validation and quality checks during processing
# TODO - Implement BEA industry code mapping and standardization
# TODO - Add support for BEA API metadata extraction and documentation

