"""Metadata-only audit viewer requires shared admin token; never returns row data."""
from contextlib import contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient

from gc_database.audit import list_audit_events
from gc_database.main import app


def configure(monkeypatch):
    monkeypatch.setenv("GC_ADMIN_TOKEN", "A" * 48)
    monkeypatch.setenv("GC_READ_TOKEN", "R" * 48)
    for name in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_READ_USER", "DB_READ_PASSWORD"):
        monkeypatch.setenv(name, "dummy")


def test_admin_only_metadata_and_response_bounds(monkeypatch):
    configure(monkeypatch)
    approved = {
        "id": "1234", "source_schema": "app", "source_table": "catalog",
        "operation": "INSERT", "occurred_at": "2026-11-25T12:00:00Z",
    }
    with patch("gc_database.main.audit.list_audit_events", return_value=[approved]) as loader:
        with TestClient(app) as client:
            permitted = client.get("/v1/audit/events?limit=8&offset=2",
                                   headers={"Authorization": "Bearer " + "A" * 48})
            denied = client.get("/v1/audit/events",
                                headers={"Authorization": "Bearer " + "R" * 48})
            anonymous = client.get("/v1/audit/events")
            oversize = client.get("/v1/audit/events?limit=101",
                                  headers={"Authorization": "Bearer " + "A" * 48})
    assert permitted.status_code == 200
    assert permitted.json() == {"events": [approved], "limit": 8, "offset": 2}
    assert set(permitted.json()["events"][0]) == {
        "id", "source_schema", "source_table", "operation", "occurred_at",
    }
    assert denied.status_code == 401
    assert anonymous.status_code == 401
    assert oversize.status_code == 422
    loader.assert_called_once_with(8, 2)


def test_sql_inspector_is_read_only_and_parameterized():
    calls = []

    class Cursor:
        def execute(self, statement, params=None):
            calls.append((statement, params))
        def fetchall(self):
            return [{"id": "1", "operation": "INSERT"}]
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def fake_connection(*, read_only=False):
        assert read_only is False  # gc_reader must not have audit schema access
        yield Connection()

    with patch("gc_database.audit.connection", side_effect=fake_connection):
        data = list_audit_events(4, 5)
    assert data == [{"id": "1", "operation": "INSERT"}]
    assert calls[0] == ("SET TRANSACTION READ ONLY", None)
    assert "FROM gc_audit.events" in calls[1][0]
    assert calls[1][1] == (4, 5)
