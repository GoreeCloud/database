"""Liveness differs from PostgreSQL readiness without leaking private errors."""
from unittest.mock import patch

from fastapi.testclient import TestClient
from psycopg import OperationalError

from gc_database.main import app


def configured(monkeypatch):
    monkeypatch.setenv("GC_ADMIN_TOKEN", "T" * 48)
    monkeypatch.setenv("GC_READ_TOKEN", "R" * 48)
    for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_READ_USER", "DB_READ_PASSWORD"):
        monkeypatch.setenv(key, "dummy")


def test_liveness_is_independent_of_database(monkeypatch):
    configured(monkeypatch)
    with patch("gc_database.main.store.check_database_readiness", side_effect=OperationalError("secret-internal-db")):
        with TestClient(app) as client:
            response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "online"}


def test_ready_only_when_select_only_connection_succeeds(monkeypatch):
    configured(monkeypatch)
    with patch("gc_database.main.store.check_database_readiness", return_value=None) as check:
        with TestClient(app) as client:
            response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    check.assert_called_once()


def test_unready_returns_503_without_sql_credentials(monkeypatch):
    configured(monkeypatch)
    with patch("gc_database.main.store.check_database_readiness", side_effect=OperationalError("secret-internal-db")):
        with TestClient(app) as client:
            response = client.get("/readyz")
    assert response.status_code == 503
    assert "secret" not in response.text
    assert response.headers["cache-control"] == "no-store"
