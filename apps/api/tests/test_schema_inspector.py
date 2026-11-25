"""Schema inspection API is read-only, authenticated and restricted to app schema."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from gc_database.main import app


def configured(monkeypatch):
    monkeypatch.setenv("GC_ADMIN_TOKEN", "A" * 48)
    monkeypatch.setenv("GC_READ_TOKEN", "R" * 48)
    for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_READ_USER", "DB_READ_PASSWORD"):
        monkeypatch.setenv(key, "dummy")


def test_viewer_can_inspect_columns_and_primary_key(monkeypatch):
    configured(monkeypatch)
    metadata = {
        "schema": "app",
        "table": "catalog",
        "columns": [
            {"name": "id", "type": "bigint", "nullable": False, "primary_key": True, "default": None},
            {"name": "slug", "type": "text", "nullable": False, "primary_key": False, "default": None},
        ],
        "indexes": [{"name": "catalog_pkey", "definition": "CREATE UNIQUE INDEX ..."}],
    }
    with patch("gc_database.main.store.describe_table", return_value=metadata) as inspect:
        with TestClient(app) as client:
            response = client.get("/v1/tables/app/catalog/schema", headers={"Authorization": "Bearer " + "R" * 48})
    assert response.status_code == 200
    assert response.json()["columns"][0]["primary_key"] is True
    assert response.json()["indexes"][0]["name"] == "catalog_pkey"
    inspect.assert_called_once_with("app", "catalog")


def test_anonymous_schema_metadata_denied(monkeypatch):
    configured(monkeypatch)
    with TestClient(app) as client:
        assert client.get("/v1/tables/app/catalog/schema").status_code == 401


def test_schema_allowlist_does_not_query_system_catalog(monkeypatch):
    configured(monkeypatch)
    with patch("gc_database.main.store.describe_table") as inspect:
        with TestClient(app) as client:
            response = client.get(
                "/v1/tables/pg_catalog/pg_class/schema",
                headers={"Authorization": "Bearer " + "A" * 48},
            )
    assert response.status_code == 404
    inspect.assert_not_called()


def test_invalid_table_identifier_rejected_before_sql(monkeypatch):
    configured(monkeypatch)
    with patch("gc_database.main.store.describe_table") as inspect:
        with TestClient(app) as client:
            response = client.get("/v1/tables/app/bad.table/schema", headers={"Authorization": "Bearer " + "R" * 48})
    assert response.status_code == 400
    inspect.assert_not_called()
