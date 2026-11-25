"""Object erasure requires explicit confirmation and current content checksum."""
from contextlib import contextmanager
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from gc_database.main import app
from gc_database.storage import delete_object


ID = "a87519e4-02ea-40c9-9826-468a93b423ed"
DIGEST = "a" * 64


def configure(monkeypatch):
    monkeypatch.setenv("GC_ADMIN_TOKEN", "A" * 48)
    monkeypatch.setenv("GC_READ_TOKEN", "R" * 48)
    for name in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_READ_USER", "DB_READ_PASSWORD"):
        monkeypatch.setenv(name, "dummy")


def test_delete_requires_admin_and_two_headers(monkeypatch):
    configure(monkeypatch)
    with patch("gc_database.main.storage.delete_object") as deletion:
        with TestClient(app) as client:
            anonymous = client.delete("/v1/objects/" + ID)
            viewer = client.delete("/v1/objects/" + ID, headers={"Authorization": "Bearer " + "R" * 48})
            missing = client.delete("/v1/objects/" + ID, headers={"Authorization": "Bearer " + "A" * 48})
            bad_confirm = client.delete("/v1/objects/" + ID, headers={
                "Authorization": "Bearer " + "A" * 48,
                "X-GC-Confirm-Delete": "delete",
                "X-GC-Expected-SHA256": DIGEST,
            })
            approved = client.delete("/v1/objects/" + ID, headers={
                "Authorization": "Bearer " + "A" * 48,
                "X-GC-Confirm-Delete": "permanently-delete",
                "X-GC-Expected-SHA256": DIGEST,
            })
    assert anonymous.status_code == viewer.status_code == 401
    assert missing.status_code == bad_confirm.status_code == 428
    assert approved.status_code == 204
    assert approved.content == b""
    deletion.assert_called_once_with(ID, DIGEST)


@pytest.mark.parametrize("bad", ["not-a-uuid", "../../etc/passwd", "0", ""])
def test_delete_rejects_bad_id(bad):
    with pytest.raises(HTTPException) as exc:
        delete_object(bad, DIGEST)
    assert exc.value.status_code == 400


@pytest.mark.parametrize("bad", ["A" * 64, "f" * 63, "../secret", "f" * 65])
def test_delete_rejects_bad_digest(bad):
    with pytest.raises(HTTPException) as exc:
        delete_object(ID, bad)
    assert exc.value.status_code == 400


def test_delete_uses_parameterized_single_row_match():
    calls = []
    class Cursor:
        def execute(self, query, params):
            calls.append((query, params))
        def fetchone(self):
            return {"id": ID}
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
    class Db:
        def cursor(self):
            return Cursor()
    @contextmanager
    def fake_connection():
        yield Db()
    with patch("gc_database.storage.connection", side_effect=fake_connection):
        delete_object(ID, DIGEST)
    statement, params = calls[0]
    assert statement == "DELETE FROM gc_storage.objects WHERE id = %s AND sha256 = %s RETURNING id"
    assert params == (UUID(ID), DIGEST)


def test_delete_not_found_fails_closed():
    class Cursor:
        def execute(self, *_):
            pass
        def fetchone(self):
            return None
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
    class Db:
        def cursor(self):
            return Cursor()
    @contextmanager
    def fake_connection():
        yield Db()
    with patch("gc_database.storage.connection", side_effect=fake_connection):
        with pytest.raises(HTTPException) as exc:
            delete_object(ID, DIGEST)
    assert exc.value.status_code == 404
    assert "checksum" in exc.value.detail.lower()
