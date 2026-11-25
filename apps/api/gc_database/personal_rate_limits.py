"""Bounded process-local subject write throttling for signed personal-note mutations.

No raw JWT, OIDC subject, IP address, hostname or event body is retained.
Subject identifiers are keyed with an ephemeral per-process HMAC secret. This
is not a distributed quota, production antifraud control or durable audit log.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import time
from collections import deque
from threading import Lock

from fastapi import HTTPException


class SubjectWriteQuota:
    def __init__(self, limit: int = 12, window_seconds: int = 60, max_subjects: int = 512) -> None:
        if min(limit, window_seconds, max_subjects) <= 0:
            raise ValueError("Positive per-subject quota, period, and cardinality bound required")
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_subjects = max_subjects
        self._key = secrets.token_bytes(32)
        self._buckets: dict[bytes, deque[float]] = {}
        self._lock = Lock()

    @staticmethod
    def _denied(retry_after: int) -> HTTPException:
        return HTTPException(
            status_code=429,
            detail="Personal-note write rate limit exceeded",
            headers={"Retry-After": str(max(1, retry_after))},
        )

    def check(self, subject: str) -> None:
        if not isinstance(subject, str) or not 1 <= len(subject) <= 256:
            raise ValueError("Verified OIDC subject is required")
        identifier = hmac.new(self._key, subject.encode("utf-8"), hashlib.sha256).digest()
        now = time.monotonic()
        with self._lock:
            oldest_allowed = now - self.window_seconds
            bucket = self._buckets.get(identifier)
            if bucket is None:
                if len(self._buckets) >= self.max_subjects:
                    # Bounded O(max_subjects) garbage collection only when capacity reached.
                    for identity, timestamps in list(self._buckets.items()):
                        while timestamps and timestamps[0] <= oldest_allowed:
                            timestamps.popleft()
                        if not timestamps:
                            del self._buckets[identity]
                if len(self._buckets) >= self.max_subjects:
                    # Fail closed instead of allowing an unbounded number of subjects.
                    raise self._denied(self.window_seconds)
                bucket = deque()
                self._buckets[identifier] = bucket
            while bucket and bucket[0] <= oldest_allowed:
                bucket.popleft()
            if len(bucket) >= self.limit:
                delay = math.ceil(self.window_seconds - (now - bucket[0]))
                raise self._denied(delay)
            bucket.append(now)


# Development preview only: 12 signed-subject mutation attempts per minute.
personal_note_write_throttle = SubjectWriteQuota()
