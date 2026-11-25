"""Private note deletion must be scoped to verified owner and explicit consent."""
from contextlib import contextmanager
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from gc_database.main import app
from gc_database.personal import delete_personal_note
from test_personal_rls import configure, signed


NOTE_ID = "d6ad4a55-d20c-4e7e-b450-898734195ddd"


def test_signed_owner_only_and_exact_confirmation(monkeypatch):
    configure(monkeypatch)
    alice = signed("account-A", "goreecloud.database.read goreecloud.database.write")
    reader = signed("account-A", "goreecloud.database.read")
    with patch("gc_database.main.personal.delete_personal_note") as remove:
        with TestClient(app) as client:
            approved = client.delete("/v1/me/notes/" + NOTE_ID,
                                     headers={"Authorization": "Bearer " + alice,
                                              "X-GC-Confirm-Delete": "delete-my-note"})
            no_confirm = client.delete("/v1/me/notes/" + NOTE_ID,
                                       headers={"Authorization": "Bearer " + alice})
            wrong_confirm = client.delete("/v1/me/notes/" + NOTE_ID,
                                          headers={"Authorization": "Bearer " + alice,
                                                   "X-GC-Confirm-Delete": "yes"})
            read_only = client.delete("/v1/me/notes/" + NOTE_ID,
                                      headers={"Authorization": "Bearer " + reader,
                                               "X-GC-Confirm-Delete": "delete-my-note"})
            shared_admin = client.delete("/v1/me/notes/" + NOTE_ID,
                                         headers={"Authorization": "Bearer " + "A" * 48,
                                                  "X-GC-Confirm-Delete": "delete-my-note"})
            shared_reader = client.delete("/v1/me/notes/" + NOTE_ID,
                                          headers={"Authorization": "Bearer " + "R" * 48,
                                                   "X-GC-Confirm-Delete": "delete-my-note"})
    assert approved.status_code == 204 and approved.content == b""
    assert no_confirm.status_code == wrong_confirm.status_code == 428
    assert read_only.status_code == shared_admin.status_code == shared_reader.status_code == 401
    remove.assert_called_once_with("account-A", NOTE_ID)


@pytest.mark.parametrize("bad", ["../other", "not-a-uuid", "", "ABC"])
def test_malformed_note_id_never_opens_database(bad):
    with patch("gc_database.personal.connection") as connection:
        with pytest.raises(HTTPException) as exc:
            delete_personal_note("owner", bad)
    assert exc.value.status_code == 400
    connection.assert_not_called()


def test_bound_transaction_local_subject_and_row_id():
    calls = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, query, params=None): calls.append((query, params))
        def fetchone(self): return {"id": NOTE_ID}
    class Db:
        def cursor(self): return Cursor()
    @contextmanager
    def fake_connection():
        yield Db()
    with patch("gc_database.personal.connection", side_effect=fake_connection):
        delete_personal_note("malicious' OR true --", NOTE_ID)
    assert calls == [
        ("SELECT set_config('gc.request_subject', %s, true)", ("malicious' OR true --",)),
        ("DELETE FROM gc_personal.notes WHERE id = %s AND owner_sub = %s RETURNING id",
         (UUID(NOTE_ID), "malicious' OR true --")),
    ]


def test_nonexistent_and_cross_owner_same_404():
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, *_): pass
        def fetchone(self): return None
    class Db:
        def cursor(self): return Cursor()
    @contextmanager
    def fake_connection():
        yield Db()
    with patch("gc_database.personal.connection", side_effect=fake_connection):
        with pytest.raises(HTTPException) as exc:
            delete_personal_note("alice", NOTE_ID)
    assert exc.value.status_code == 404
    assert "bob" not in exc.value.detail
