import threading
import time
from collections import deque


class RateLimiter:
    """Sliding-window limiter, per key (usually the client IP). A limit of 0 disables it."""

    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self._hits = {}
        self._lock = threading.Lock()

    def hit(self, key, now=None):
        """Record one request. Returns (allowed, retry_after_seconds)."""
        if self.limit <= 0:
            return True, 0
        now = time.monotonic() if now is None else now
        with self._lock:
            if len(self._hits) > 10_000:  # keep memory bounded
                self._prune(now)
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry = max(1, int(self.window - (now - hits[0])) + 1)
                return False, retry
            hits.append(now)
            return True, 0

    def _prune(self, now):
        for key in [k for k, h in self._hits.items() if not h or now - h[-1] >= self.window]:
            del self._hits[key]
