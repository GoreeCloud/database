"""HTTP surface tests that do not require a running PostgreSQL server."""
import os
from unittest.mock import patch
from fastapi.testclient import TestClient

from gc_database.main import app


def configured(monkeypatch):
    monkeypatch.setenv("GC_ADMIN_TOKEN", "T" * 48)
    monkeypatch.setenv("GC_READ_TOKEN", "R" * 48)
    for k in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_READ_USER", "DB_READ_PASSWORD"):
        monkeypatch.setenv(k, "dummy")


def test_api_rejects_no_token(monkeypatch):
    configured(monkeypatch)
    with TestClient(app) as client:
        r = client.get("/v1/tables")
    assert r.status_code == 401
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_api_rejects_wrong_token(monkeypatch):
    configured(monkeypatch)
    with TestClient(app) as client:
        r = client.get("/v1/tables", headers={"Authorization": "Bearer " + "X" * 48})
    assert r.status_code == 401


def test_valid_token_dispatches_to_store(monkeypatch):
    configured(monkeypatch)
    with patch("gc_database.main.store.list_tables", return_value=[{"schema":"app","name":"catalog"}]):
        with TestClient(app) as client:
            r = client.get("/v1/tables", headers={"Authorization":"Bearer " + "T" * 48})
    assert r.status_code == 200
    assert r.json() == {"tables": [{"schema":"app","name":"catalog"}]}


def test_disallow_other_schemas_even_when_authenticated(monkeypatch):
    configured(monkeypatch)
    with TestClient(app) as client:
        r = client.get("/v1/tables/pg_catalog/pg_class/rows", headers={"Authorization":"Bearer " + "T" * 48})
    assert r.status_code == 404
