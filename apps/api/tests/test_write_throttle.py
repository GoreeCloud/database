"""Bounded, thread-safe admin mutation quota with no token/IP retention."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from gc_database.main import app
from gc_database.rate_limits import SlidingWindowQuota


def configure(monkeypatch):
    monkeypatch.setenv("GC_ADMIN_TOKEN", "A" * 48)
    monkeypatch.setenv("GC_READ_TOKEN", "R" * 48)
    for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_READ_USER", "DB_READ_PASSWORD"):
        monkeypatch.setenv(key, "dummy")


def test_sliding_window_rate_and_retry_header():
    limiter = SlidingWindowQuota(limit=2, window_seconds=60)
    with patch("gc_database.rate_limits.time.monotonic") as clock:
        clock.return_value = 100.0
        limiter.check()
        clock.return_value = 105.0
        limiter.check()
        clock.return_value = 106.0
        with pytest.raises(HTTPException) as exc:
            limiter.check()
        assert exc.value.status_code == 429
        assert exc.value.headers == {"Retry-After": "54"}
        clock.return_value = 160.1
        limiter.check()


def test_threadsafe_quota_limits_simultaneous_calls():
    limiter = SlidingWindowQuota(limit=10, window_seconds=60)
    def attempt(_):
        try:
            limiter.check()
            return True
        except HTTPException:
            return False
    with ThreadPoolExecutor(max_workers=16) as pool:
        outcomes = list(pool.map(attempt, range(48)))
    assert outcomes.count(True) == 10
    assert outcomes.count(False) == 38
    assert len(limiter._timestamps) == 10


def test_write_routes_share_admin_throttle(monkeypatch):
    configure(monkeypatch)
    limiter = SlidingWindowQuota(limit=2, window_seconds=60)
    with patch("gc_database.security.admin_write_throttle", limiter), patch(
        "gc_database.main.store.insert_row", return_value={"row": {"slug": "one"}}
    ), patch("gc_database.main.storage.save_object", return_value={"id": "test"}):
        with TestClient(app) as client:
            headers = {"Authorization": "Bearer " + "A" * 48}
            row = client.post("/v1/tables/app/catalog/rows", json={"slug": "one"}, headers=headers)
            uploaded = client.post("/v1/objects?filename=one.txt", content=b"one",
                                   headers={**headers, "Content-Type": "text/plain"})
            limit = client.post("/v1/tables/app/catalog/rows", json={"slug": "two"}, headers=headers)
    assert row.status_code == 201
    assert uploaded.status_code == 201
    assert limit.status_code == 429
    assert limit.headers["retry-after"]


def test_bad_token_does_not_exhaust_admin_quota(monkeypatch):
    configure(monkeypatch)
    limiter = SlidingWindowQuota(limit=1, window_seconds=60)
    with patch("gc_database.security.admin_write_throttle", limiter), patch(
        "gc_database.main.store.insert_row", return_value={"row": {"slug": "valid"}}
    ):
        with TestClient(app) as client:
            denied = client.post("/v1/tables/app/catalog/rows", json={"slug": "no"},
                                 headers={"Authorization": "Bearer " + "R" * 48})
            approved = client.post("/v1/tables/app/catalog/rows", json={"slug": "valid"},
                                   headers={"Authorization": "Bearer " + "A" * 48})
    assert denied.status_code == 401
    assert approved.status_code == 201
    assert len(limiter._timestamps) == 1


def test_invalid_quota_construction():
    with pytest.raises(ValueError):
        SlidingWindowQuota(limit=0, window_seconds=1)
    with pytest.raises(ValueError):
        SlidingWindowQuota(limit=1, window_seconds=0)
