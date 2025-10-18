import requests
import time
from typing import Optional, Dict, Any

# TODO - Add request/response logging and monitoring
# TODO - Implement connection pooling for better performance
# TODO - Add support for different authentication methods (OAuth, API keys)

def safe_get_json(url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 30, max_retries: int = 3):
    last_exception = None

    for attempt in range(max_retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            r.raise_for_status()

            try:
                return r.json()
            except ValueError as e:
                raise RuntimeError(f"Invalid JSON response from {url}: {e}")

        except requests.exceptions.Timeout as e:
            last_exception = RuntimeError(f"Request timeout after {timeout}s for {url}: {e}")
        except requests.exceptions.ConnectionError as e:
            last_exception = RuntimeError(f"Network connection error for {url}: {e}")
        except requests.exceptions.HTTPError as e:
            # Don't retry on HTTP errors (4xx, 5xx) as they indicate API issues
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code} error from {url}: {r.text[:200]}...")
            last_exception = RuntimeError(f"HTTP error for {url}: {e}")
        except requests.exceptions.RequestException as e:
            last_exception = RuntimeError(f"Request error for {url}: {e}")
        except Exception as e:
            last_exception = RuntimeError(f"Unexpected error requesting {url}: {e}")

        # Wait before retry (exponential backoff)
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            time.sleep(wait_time)

    # If we get here, all retries failed
    raise last_exception or RuntimeError(f"Failed to fetch {url} after {max_retries} attempts")

# TODO - Add circuit breaker pattern for failing endpoints
# TODO - Implement response caching at HTTP level
# TODO - Add request deduplication to prevent duplicate API calls

def thousands_to_units(val):
    # ASM often returns thousands; convert to plain dollars if needed
    try:
        return float(val) * 1.0
    except Exception:
        return None

# TODO - Add unit conversion utilities for different data sources
# TODO - Implement currency conversion and inflation adjustment
# TODO - Add data scaling validation and automatic detection
