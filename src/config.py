import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

# Environment detection
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT in ["production", "prod"]
IS_DEVELOPMENT = ENVIRONMENT in ["development", "dev"]
IS_TESTING = ENVIRONMENT in ["testing", "test"]

# TODO - Add environment-specific configuration validation
# TODO - Implement configuration hot-reloading for development
# TODO - Add configuration encryption for sensitive values in production

# API Keys
BEA_API_KEY = os.getenv("BEA_API_KEY", "").strip()
CENSUS_API_KEY = os.getenv("CENSUS_API_KEY", "").strip()

# Application settings
DEFAULT_YEAR = int(os.getenv("DEFAULT_YEAR", "2021"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"

# TODO - Implement API key rotation and refresh mechanisms
# TODO - Add API key validation against service endpoints on startup
# TODO - Implement secure key storage with encryption at rest

# Rate limiting settings (more conservative in production)
API_RATE_LIMITS = {
    'bea': int(os.getenv("BEA_RATE_LIMIT", "10" if IS_PRODUCTION else "30")),
    'census': int(os.getenv("CENSUS_RATE_LIMIT", "20" if IS_PRODUCTION else "50")),
    'default': int(os.getenv("DEFAULT_RATE_LIMIT", "5" if IS_PRODUCTION else "20"))
}

# Cache settings
CACHE_TTL_API = int(os.getenv("CACHE_TTL_API", "3600"))  # 1 hour default
CACHE_TTL_COMPUTATION = int(os.getenv("CACHE_TTL_COMPUTATION", "1800"))  # 30 minutes default

# TODO - Implement dynamic rate limiting based on API response times
# TODO - Add cache compression for large datasets to reduce memory usage
# TODO - Implement cache warming strategies for frequently accessed data

# Data validation settings
MAX_CSV_SIZE_MB = int(os.getenv("MAX_CSV_SIZE_MB", "50"))
SUPPORTED_YEARS_BEA = range(1997, 2025)  # BEA data availability
SUPPORTED_YEARS_CENSUS = range(1997, 2024)  # Census ASM data availability

# TODO - Implement dynamic data validation based on data source capabilities
# TODO - Add data quality scoring and validation feedback
# TODO - Implement automatic data source compatibility checking

# Environment validation
def validate_config() -> List[str]:
    """Validate configuration and provide helpful error messages."""
    issues = []

    # Check environment
    if ENVIRONMENT not in ["development", "dev", "production", "prod", "testing", "test"]:
        issues.append(f"Invalid ENVIRONMENT '{ENVIRONMENT}'. Must be one of: development, production, testing")

    # TODO - Add configuration schema validation with JSON schema
    # TODO - Implement configuration dependency checking and warnings
    # TODO - Add configuration migration support for version upgrades

    # Check API keys based on environment
    if IS_PRODUCTION:
        if not BEA_API_KEY:
            issues.append("BEA_API_KEY is required in production environment")
        if not CENSUS_API_KEY:
            issues.append("CENSUS_API_KEY is required in production environment")
    else:
        # In development/testing, warn but don't fail if keys are missing
        if not BEA_API_KEY:
            issues.append("Warning: BEA_API_KEY not set - app will work with sample data only")
        if not CENSUS_API_KEY:
            issues.append("Warning: CENSUS_API_KEY not set - app will work with sample data only")

    # Validate numeric settings
    if not (1997 <= DEFAULT_YEAR <= 2025):
        issues.append(f"DEFAULT_YEAR {DEFAULT_YEAR} is outside valid range (1997-2025)")

    if LOG_LEVEL not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        issues.append(f"Invalid LOG_LEVEL '{LOG_LEVEL}'. Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL")

    # Validate rate limits
    for api, limit in API_RATE_LIMITS.items():
        if limit <= 0:
            issues.append(f"Invalid rate limit for {api}: {limit}. Must be positive integer")

    return issues

def get_config_summary() -> dict:
    """Get a summary of current configuration (without sensitive data)."""
    return {
        "environment": ENVIRONMENT,
        "is_production": IS_PRODUCTION,
        "default_year": DEFAULT_YEAR,
        "log_level": LOG_LEVEL,
        "cache_enabled": CACHE_ENABLED,
        "bea_key_set": bool(BEA_API_KEY),
        "census_key_set": bool(CENSUS_API_KEY),
        "api_rate_limits": API_RATE_LIMITS,
        "supported_years_bea": f"{min(SUPPORTED_YEARS_BEA)}-{max(SUPPORTED_YEARS_BEA)}",
        "supported_years_census": f"{min(SUPPORTED_YEARS_CENSUS)}-{max(SUPPORTED_YEARS_CENSUS)}"
    }
