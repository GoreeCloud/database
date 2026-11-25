"""Read-only API tokens must never authorize management mutations."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import patch

from gc_database.main import app
from gc_database.security import require_read, require_admin, require_configuration


def configured(monkeypatch):
    monkeypatch.setenv("GC_ADMIN_TOKEN", "A" * 48)
    monkeypatch.setenv("GC_READ_TOKEN", "R" * 48)
    for name in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_READ_USER", "DB_READ_PASSWORD"):
        monkeypatch.setenv(name, "test")


def test_read_only_token_accepted_on_read_routes(monkeypatch):
    configured(monkeypatch)
    with patch("gc_database.main.store.list_tables", return_value=[{"schema": "app", "name": "catalog"}]):
        with TestClient(app) as client:
            response = client.get("/v1/tables", headers={"Authorization": "Bearer " + "R" * 48})
    assert response.status_code == 200
    assert response.json()["tables"][0]["name"] == "catalog"


def test_read_only_token_refused_on_insert(monkeypatch):
    configured(monkeypatch)
    with TestClient(app) as client:
        response = client.post("/v1/tables/app/catalog/rows", headers={"Authorization": "Bearer " + "R" * 48}, json={"slug":"blocked"})
    assert response.status_code == 401


def test_admin_token_also_reads(monkeypatch):
    configured(monkeypatch)
    require_read("Bearer " + "A" * 48)
    require_admin("Bearer " + "A" * 48)


def test_read_token_must_be_distinct(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setenv("GC_READ_TOKEN", "A" * 48)
    with pytest.raises(RuntimeError, match="distinct"):
        require_configuration()


@pytest.mark.parametrize("bad", ["", "Basic abc", "Bearer " + "x" * 48, "Bearer abc"])
def test_bad_read_auth_rejected(monkeypatch, bad):
    configured(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        require_read(bad)
    assert exc.value.status_code == 401


def test_session_scope_is_server_verified(monkeypatch):
    configured(monkeypatch)
    with TestClient(app) as client:
        viewer = client.get("/v1/session", headers={"Authorization": "Bearer " + "R" * 48})
        admin = client.get("/v1/session", headers={"Authorization": "Bearer " + "A" * 48})
        denied = client.get("/v1/session")
    assert viewer.status_code == 200
    assert viewer.json() == {"scope": "reader", "permissions": ["read"]}
    assert admin.status_code == 200
    assert admin.json() == {"scope": "admin", "permissions": ["read", "write"]}
    assert denied.status_code == 401
