import time
import threading

# TODO - Implement distributed rate limiting with Redis for multi-instance deployments
# TODO - Add rate limit monitoring and alerting capabilities
# TODO - Implement adaptive rate limiting based on API response times

class RateLimiter:
    """Thread-safe rate limiter using token bucket algorithm."""

    # TODO - Add burst allowance configuration for handling traffic spikes
    # TODO - Implement rate limit warmup periods for new deployments
    # TODO - Add rate limit bypass mechanisms for emergency situations

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests_per_second = requests_per_minute / 60.0
        self.tokens = requests_per_minute
        self.last_update = time.time()
        self.lock = threading.Lock()

    def acquire(self) -> bool:
        """Try to acquire a token. Returns True if successful, False if rate limited."""
        with self.lock:
            now = time.time()
            time_passed = now - self.last_update

            # Add tokens based on time passed
            self.tokens = min(
                self.requests_per_minute,
                self.tokens + (time_passed * self.requests_per_second)
            )
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False

    def wait_if_needed(self) -> None:
        """Wait until a token is available."""
        while not self.acquire():
            time.sleep(1.0 / self.requests_per_second)

class APIRateLimiter:
    """Rate limiter for different APIs with different limits."""

    # TODO - Add dynamic rate limit adjustment based on API response headers
    # TODO - Implement rate limit quota tracking and usage reporting
    # TODO - Add support for different rate limit algorithms (sliding window, etc.)

    def __init__(self):
        # Government API limits (conservative)
        self.limiters = {
            'bea': RateLimiter(30),      # BEA: ~30 requests/minute
            'census': RateLimiter(50),   # Census: ~50 requests/minute
            'default': RateLimiter(20)   # Default conservative limit
        }

    def wait_for_api(self, api_name: str) -> None:
        """Wait for rate limit allowance for specific API."""
        limiter = self.limiters.get(api_name.lower(), self.limiters['default'])
        limiter.wait_if_needed()

# Global API rate limiter instance
api_limiter = APIRateLimiter()