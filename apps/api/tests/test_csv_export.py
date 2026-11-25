"""CSV formula injection, bounded export and authorization regression checks."""
import csv
import io
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from gc_database.exports import render_csv, safe_csv_cell
from gc_database.main import app


def configure(monkeypatch):
    monkeypatch.setenv("GC_ADMIN_TOKEN", "A" * 48)
    monkeypatch.setenv("GC_READ_TOKEN", "R" * 48)
    for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_READ_USER", "DB_READ_PASSWORD"):
        monkeypatch.setenv(key, "dummy")


@pytest.mark.parametrize("unsafe", [
    "=SUM(1,2)", "+1", "-2", "@USER", "\t=cmd", "  =HYPERLINK(1)", "\r=cmd", "\n=cmd", "\x00=cmd",
])
def test_csv_formula_prefix(unsafe):
    assert safe_csv_cell(unsafe).startswith("'")


def test_csv_quotes_and_headers():
    data = render_csv(["name", "content", "=unsafe header"], [
        {"name": 'a,"b"', "content": "=HYPERLINK(\"https://evil.example\")", "=unsafe header": "normal"},
        {"name": "UTF-8 ✓", "content": "line\r\ntext", "=unsafe header": None},
    ])
    records = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    assert records[0] == ["name", "content", "'=unsafe header"]
    assert records[1][0] == 'a,"b"'
    assert records[1][1].startswith("'=")
    assert records[2][0] == "UTF-8 ✓"
    assert records[2][1] == "line\r\ntext"
    assert records[2][2] == ""


def test_export_size_cap():
    with pytest.raises(HTTPException) as exc:
        render_csv(["content"], [{"content": "A" * 1_100_000}])
    assert exc.value.status_code == 413


def test_viewer_can_export_bounded_attachment(monkeypatch):
    configure(monkeypatch)
    with patch("gc_database.main.export_table_csv", return_value=b"id,slug\r\n1,welcome\r\n") as render:
        with TestClient(app) as client:
            response = client.get("/v1/tables/app/catalog/export.csv?limit=3&offset=5",
                                  headers={"Authorization": "Bearer " + "R" * 48})
    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="app-catalog-page.csv"'
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    render.assert_called_once_with("app", "catalog", 3, 5)


def test_anonymous_or_other_schema_denied(monkeypatch):
    configure(monkeypatch)
    with patch("gc_database.main.export_table_csv") as render:
        with TestClient(app) as client:
            denied = client.get("/v1/tables/app/catalog/export.csv")
            forbidden_schema = client.get("/v1/tables/pg_catalog/pg_class/export.csv",
                headers={"Authorization": "Bearer " + "A" * 48})
            oversized = client.get("/v1/tables/app/catalog/export.csv?limit=999999",
                headers={"Authorization": "Bearer " + "A" * 48})
    assert denied.status_code == 401
    assert forbidden_schema.status_code == 404
    assert oversized.status_code == 422
    render.assert_not_called()
