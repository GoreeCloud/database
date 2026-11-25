"""Privacy-preserving bounded per-subject mutation limiter regression tests."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from gc_database.main import app
from gc_database.personal_rate_limits import SubjectWriteQuota
from test_personal_rls import configure, signed


def test_per_subject_window_and_retry_without_raw_identifier():
    quota = SubjectWriteQuota(limit=2, window_seconds=60, max_subjects=3)
    with patch("gc_database.personal_rate_limits.time.monotonic") as clock:
        clock.return_value = 100
        quota.check("account-alice")
        clock.return_value = 103
        quota.check("account-alice")
        quota.check("account-bob")
        clock.return_value = 110
        with pytest.raises(HTTPException) as limited:
            quota.check("account-alice")
        assert limited.value.status_code == 429
        assert limited.value.headers == {"Retry-After": "50"}
        assert "alice" not in limited.value.detail.lower()
        assert all(isinstance(identity, bytes) and b"alice" not in identity
                   for identity in quota._buckets)
        clock.return_value = 161
        quota.check("account-alice")


def test_bounded_subject_cardinality_and_expiry_pruning():
    quota = SubjectWriteQuota(limit=1, window_seconds=30, max_subjects=2)
    with patch("gc_database.personal_rate_limits.time.monotonic") as clock:
        clock.return_value = 100
        quota.check("alice")
        quota.check("bob")
        with pytest.raises(HTTPException) as full:
            quota.check("charlie")
        assert full.value.status_code == 429
        assert full.value.headers == {"Retry-After": "30"}
        assert len(quota._buckets) == 2
        clock.return_value = 131
        quota.check("charlie")
        assert len(quota._buckets) <= 2


def test_concurrent_single_subject_limit():
    quota = SubjectWriteQuota(limit=10, window_seconds=60, max_subjects=10)
    def action(_):
        try:
            quota.check("signed-person")
            return True
        except HTTPException:
            return False
    with ThreadPoolExecutor(max_workers=25) as pool:
        ok = list(pool.map(action, range(70)))
    assert ok.count(True) == 10
    assert ok.count(False) == 60


@pytest.mark.parametrize("limit,window,subjects", [(0, 60, 10), (3, 0, 10), (3, 60, 0)])
def test_refuses_nonpositive_bounds(limit, window, subjects):
    with pytest.raises(ValueError):
        SubjectWriteQuota(limit, window, subjects)


@pytest.mark.parametrize("subject", ["", None, "x" * 257, 42])
def test_refuses_nonverified_subject(subject):
    quota = SubjectWriteQuota()
    with pytest.raises(ValueError):
        quota.check(subject)
    assert not quota._buckets


def test_api_signed_subjects_have_independent_write_quota(monkeypatch):
    configure(monkeypatch)
    alice = signed("alice-person", "goreecloud.database.read goreecloud.database.write")
    bob = signed("bob-person", "goreecloud.database.read goreecloud.database.write")
    no_write = signed("alice-person", "goreecloud.database.read")
    quota = SubjectWriteQuota(limit=2, window_seconds=60)
    row = {"id": "demo", "title": "t", "content": "c", "created_at": "2026-11-25T00:00:00Z"}
    with patch("gc_database.security.personal_note_write_throttle", quota), patch(
        "gc_database.main.personal.create_personal_note", return_value=row
    ) as create, patch(
        "gc_database.main.personal.delete_personal_note"
    ) as delete, patch(
        "gc_database.main.personal.list_personal_notes", return_value=[]
    ) as read:
        with TestClient(app) as client:
            def headers(token: str):
                return {"Authorization": "Bearer " + token}
            denied = client.post("/v1/me/notes", json={"title": "t", "content": "c"},
                                 headers=headers(no_write))
            first = client.post("/v1/me/notes", json={"title": "t", "content": "c"},
                                headers=headers(alice))
            removed = client.delete("/v1/me/notes/94e5dd48-adbf-483b-ac18-e7e9c5e4e7d6",
                                    headers={**headers(alice), "X-GC-Confirm-Delete": "delete-my-note"})
            throttled = client.post("/v1/me/notes", json={"title": "t", "content": "c"},
                                    headers=headers(alice))
            other = client.post("/v1/me/notes", json={"title": "t", "content": "c"},
                                headers=headers(bob))
            personal_read = client.get("/v1/me/notes", headers=headers(alice))
    assert denied.status_code == 401
    assert first.status_code == 201
    assert removed.status_code == 204
    assert throttled.status_code == 429 and 1 <= int(throttled.headers["retry-after"]) <= 60
    assert other.status_code == 201
    assert personal_read.status_code == 200
    assert create.call_count == 2
    delete.assert_called_once()
    read.assert_called_once()
