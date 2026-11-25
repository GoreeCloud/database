"""OIDC subject-bound private notes: scope separation and parameterized RLS context."""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jwt.utils import base64url_encode
from psycopg.errors import CheckViolation

from gc_database.main import app
from gc_database.personal import create_personal_note, list_personal_notes


KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ISSUER = "https://id.example.test/realms/goreecloud"


def encoded_int(value: int) -> str:
    return base64url_encode(value.to_bytes((value.bit_length() + 7) // 8, "big")).decode()


def configure(monkeypatch):
    monkeypatch.setenv("GC_ADMIN_TOKEN", "A" * 48)
    monkeypatch.setenv("GC_READ_TOKEN", "R" * 48)
    for name in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_READ_USER", "DB_READ_PASSWORD"):
        monkeypatch.setenv(name, "dummy")
    pub = KEY.public_key().public_numbers()
    jwks = {
        "keys": [{"kty": "RSA", "alg": "RS256", "use": "sig",
                  "kid": "rls-test", "n": encoded_int(pub.n), "e": encoded_int(pub.e)}]
    }
    monkeypatch.setenv("GC_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("GC_OIDC_AUDIENCE", "goreecloud-database")
    monkeypatch.setenv("GC_OIDC_JWKS_JSON", json.dumps(jwks))
    monkeypatch.delenv("GC_OIDC_JWKS_URL", raising=False)


def signed(subject: str, scope: str) -> str:
    now = int(time.time())
    return jwt.encode({
        "iss": ISSUER,
        "aud": "goreecloud-database",
        "sub": subject,
        "iat": now,
        "exp": now + 600,
        "scope": scope,
    }, KEY, algorithm="RS256", headers={"kid": "rls-test"})


def test_signed_subject_is_bound_to_read_and_write_calls(monkeypatch):
    configure(monkeypatch)
    alice = signed("account-A", "goreecloud.database.read goreecloud.database.write")
    bob = signed("account-B", "goreecloud.database.read")
    row = {"id": "x", "title": "demo", "content": "private", "created_at": "2026-11-25T12:00:00Z"}
    with patch("gc_database.main.personal.list_personal_notes", return_value=[row]) as reader, patch(
        "gc_database.main.personal.create_personal_note", return_value=row
    ) as writer, patch("gc_database.main.store.insert_row") as global_writer:
        with TestClient(app) as client:
            a = client.get("/v1/me/notes", headers={"Authorization": "Bearer " + alice})
            b = client.get("/v1/me/notes", headers={"Authorization": "Bearer " + bob})
            posted = client.post("/v1/me/notes", json={"title": "demo", "content": "private"},
                                 headers={"Authorization": "Bearer " + alice})
            forbidden = client.post("/v1/me/notes", json={"title": "demo", "content": "private"},
                                    headers={"Authorization": "Bearer " + bob})
            global_denied = client.post("/v1/tables/app/catalog/rows", json={"slug": "bad"},
                                        headers={"Authorization": "Bearer " + alice})
    assert a.status_code == b.status_code == 200
    assert posted.status_code == 201
    assert forbidden.status_code == global_denied.status_code == 401
    assert reader.call_args_list[0].args == ("account-A", 25, 0)
    assert reader.call_args_list[1].args == ("account-B", 25, 0)
    writer.assert_called_once_with("account-A", {"title": "demo", "content": "private"})
    global_writer.assert_not_called()


def test_shared_admin_and_viewer_are_not_individual_identities(monkeypatch):
    configure(monkeypatch)
    with TestClient(app) as client:
        for shared in ("A" * 48, "R" * 48):
            assert client.get("/v1/me/notes", headers={"Authorization": "Bearer " + shared}).status_code == 401
            assert client.post("/v1/me/notes", json={"title": "t", "content": "c"},
                               headers={"Authorization": "Bearer " + shared}).status_code == 401


@pytest.mark.parametrize("payload", [
    {}, {"title": "x"}, {"title": "x", "content": "c", "owner_sub": "forged"},
    {"title": "", "content": "c"}, {"title": "a" * 121, "content": "c"},
    {"title": "x", "content": ""}, {"title": "x", "content": "z" * 2049},
    {"title": {"nested": 1}, "content": "c"},
    {"title": "ok", "content": ["not-a-string"]},
])
def test_invalid_notes_fail_without_sql(payload):
    with patch("gc_database.personal.connection") as connect:
        with pytest.raises(HTTPException) as exc:
            create_personal_note("subject-A", payload)
        assert exc.value.status_code == 422
        connect.assert_not_called()


def test_rls_transaction_context_is_bounded_and_parameterized():
    calls = []

    class Cursor:
        def execute(self, query, parameters=None):
            calls.append((query, parameters))
        def fetchall(self):
            return [{"id": "row1"}]
        def fetchone(self):
            return {"id": "row2"}
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def fake_connection(read_only=False):
        calls.append(("connection", read_only))
        yield Connection()

    with patch("gc_database.personal.connection", side_effect=fake_connection):
        assert list_personal_notes("user' OR true", 20, 2) == [{"id": "row1"}]
        assert create_personal_note("owned-subject", {"title": "hi", "content": "c"}) == {"id": "row2"}
    assert calls[0] == ("connection", True)
    assert calls[1] == ("SELECT set_config('gc.request_subject', %s, true)", ("user' OR true",))
    assert "FROM gc_personal.notes" in calls[2][0]
    assert calls[2][1] == (20, 2)
    assert calls[3] == ("connection", False)
    assert calls[4] == ("SELECT set_config('gc.request_subject', %s, true)", ("owned-subject",))
    assert calls[5][1] == ("owned-subject", "hi", "c")


class QuotaExceeded(CheckViolation):
    @property
    def diag(self):
        return SimpleNamespace(constraint_name="gc_personal_notes_quota")


def test_personal_quota_error_not_sql_leak():
    with patch("gc_database.personal.connection", side_effect=QuotaExceeded("private SQL detail")):
        with pytest.raises(HTTPException) as exc:
            create_personal_note("sub-A", {"title": "t", "content": "c"})
    assert exc.value.status_code == 507
    assert "SQL" not in exc.value.detail
