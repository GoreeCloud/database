"""Small-object input, privilege and content safety tests without PostgreSQL."""
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from gc_database.main import app
from gc_database.storage import check_filename, check_media_type, parse_object_id, MAX_OBJECT_BYTES


def configure(monkeypatch):
    monkeypatch.setenv("GC_ADMIN_TOKEN", "A" * 48)
    monkeypatch.setenv("GC_READ_TOKEN", "R" * 48)
    for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_READ_USER", "DB_READ_PASSWORD"):
        monkeypatch.setenv(key, "dummy")


@pytest.mark.parametrize("bad", ["../secret", "/etc/passwd", ".hidden", 'x"y', "a\nb", "", "x" * 121, "back\\slash"])
def test_filename_rejects_unsafe_values(bad):
    with pytest.raises(HTTPException):
        check_filename(bad)


def test_bounded_media_and_object_id():
    assert check_media_type("image/png") == "image/png"
    assert parse_object_id("a87519e4-02ea-40c9-9826-468a93b423ed") == UUID("a87519e4-02ea-40c9-9826-468a93b423ed")
    with pytest.raises(HTTPException):
        check_media_type("text/html")
    with pytest.raises(HTTPException):
        parse_object_id("not-a-uuid")


def test_admin_only_upload_and_bounded_stream(monkeypatch):
    configure(monkeypatch)
    with TestClient(app) as client:
        denied = client.post("/v1/objects?filename=sample.txt", content=b"hello",
                             headers={"Authorization": "Bearer " + "R" * 48, "Content-Type": "text/plain"})
        assert denied.status_code == 401
        too_large = client.post("/v1/objects?filename=sample.txt", content=b"a" * (MAX_OBJECT_BYTES + 1),
                                headers={"Authorization": "Bearer " + "A" * 48, "Content-Type": "text/plain"})
        assert too_large.status_code == 413


def test_safe_download_headers_and_integrity(monkeypatch):
    configure(monkeypatch)
    object_id = "a87519e4-02ea-40c9-9826-468a93b423ed"
    record = {"filename": "sample.txt", "media_type": "text/plain", "size_bytes": 5,
              "sha256": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
              "contents": b"hello"}
    with patch("gc_database.main.storage.read_object", return_value=record):
        with TestClient(app) as client:
            response = client.get("/v1/objects/" + object_id, headers={"Authorization": "Bearer " + "R" * 48})
    assert response.status_code == 200
    assert response.content == b"hello"
    assert response.headers["content-type"].startswith("application/octet-stream")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == 'attachment; filename="sample.txt"'


def test_no_anonymous_object_listing(monkeypatch):
    configure(monkeypatch)
    with TestClient(app) as client:
        assert client.get("/v1/objects").status_code == 401
