"""Event framing must never permit arbitrary PostgreSQL notification injection."""
import json
from fastapi.testclient import TestClient

from gc_database.main import app
from gc_database.realtime import format_catalog_notice


def test_anonymous_catalog_feed_is_denied(monkeypatch):
    monkeypatch.setenv("GC_ADMIN_TOKEN", "A" * 48)
    monkeypatch.setenv("GC_READ_TOKEN", "R" * 48)
    for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_READ_USER", "DB_READ_PASSWORD"):
        monkeypatch.setenv(key, "dummy")
    with TestClient(app) as client:
        response = client.get("/v1/events/catalog")
    assert response.status_code == 401


def test_valid_catalog_notification():
    raw = json.dumps({"schema": "app", "table": "catalog", "operation": "INSERT", "id": 17})
    assert format_catalog_notice(raw) == 'event: catalog\ndata: {"schema":"app","table":"catalog","operation":"INSERT","id":17}\n\n'


def test_reject_other_tables_and_unknown_operations():
    for value in (
        '{"schema":"app","table":"secrets","operation":"INSERT","id":1}',
        '{"schema":"app","table":"catalog","operation":"TRUNCATE","id":1}',
        '{"schema":"app","table":"catalog","operation":"INSERT","id":true}',
        '{"schema":"app","table":"catalog","operation":"INSERT","id":-1}',
        '{"schema":"app","table":"catalog","operation":"INSERT","id":"1"}',
        '{"schema":"app","table":"catalog","operation":"INSERT","id":1}\nevent: admin',
        "<script>alert(1)</script>",
        "x" * 5000,
    ):
        assert format_catalog_notice(value) is None
