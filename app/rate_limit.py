import time
from collections import defaultdict
from datetime import datetime, timezone


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s")


class RateLimiter:
    """In-memory sliding window rate limiter."""

    def __init__(self):
        # key: (did, endpoint) -> list of timestamps
        self._hits: dict[tuple[str, str], list[float]] = defaultdict(list)

    def _clean(self, key: tuple[str, str], window_seconds: int):
        cutoff = time.time() - window_seconds
        self._hits[key] = [t for t in self._hits[key] if t > cutoff]

    def check(self, did: str, endpoint: str, max_count: int, window_seconds: int):
        key = (did, endpoint)
        self._clean(key, window_seconds)
        if len(self._hits[key]) >= max_count:
            oldest = min(self._hits[key])
            retry_after = int(oldest + window_seconds - time.time()) + 1
            raise RateLimitExceeded(retry_after=max(retry_after, 1))
        self._hits[key].append(time.time())

    def get_info(self, did: str, endpoint: str, max_count: int, window_seconds: int) -> dict:
        key = (did, endpoint)
        self._clean(key, window_seconds)
        count = len(self._hits[key])
        remaining = max(0, max_count - count)
        reset_at = datetime.now(timezone.utc).isoformat()
        if self._hits[key]:
            oldest = min(self._hits[key])
            reset_time = datetime.fromtimestamp(oldest + window_seconds, tz=timezone.utc)
            reset_at = reset_time.isoformat()
        return {
            "limit": max_count,
            "remaining": remaining,
            "reset": reset_at,
        }


# Singleton
rate_limiter = RateLimiter()

# Rate limit configs per endpoint (from API contract)
RATE_LIMITS = {
    "profile": {"max_count": 10, "window_seconds": 3600},
    "search": {"max_count": 20, "window_seconds": 3600},
    "interest": {"max_count": 5, "window_seconds": 86400},
    "connections": {"max_count": 60, "window_seconds": 3600},
    "delete_profile": {"max_count": 1, "window_seconds": 86400},
}
