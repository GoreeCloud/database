"""Minimal single-process administrative write burst safeguard.

No user/IP/token data is stored. Not a distributed or production anti-abuse
system. Shared administrator credentials intentionally share one write bucket.
"""
from __future__ import annotations

import math
import time
from collections import deque
from threading import Lock

from fastapi import HTTPException


class SlidingWindowQuota:
    def __init__(self, limit: int, window_seconds: int) -> None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("Rate limit and period must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = Lock()

    def check(self) -> None:
        now = time.monotonic()
        with self._lock:
            cutoff = now - self.window_seconds
            while self._timestamps and self._timestamps[0] <= cutoff:
                self._timestamps.popleft()
            if len(self._timestamps) >= self.limit:
                delay = max(1, math.ceil(self.window_seconds - (now - self._timestamps[0])))
                raise HTTPException(
                    status_code=429,
                    detail="Administrative write rate limit exceeded",
                    headers={"Retry-After": str(delay)},
                )
            self._timestamps.append(now)


# Defensively small development default. One bucket per API worker/process.
admin_write_throttle = SlidingWindowQuota(limit=30, window_seconds=60)
