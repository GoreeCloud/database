"""Signed OIDC grants subject-scoped notes only by default, never global objects."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from gc_database.main import app
from gc_database.security import global_oidc_read_enabled, require_configuration
from test_personal_rls import configure, signed


def test_default_signed_oidc_only_sees_personal_notes(monkeypatch):
    configure(monkeypatch)
    monkeypatch.delenv("GC_OIDC_GLOBAL_READ_ENABLED", raising=False)
    signed_token = signed("person-A", "goreecloud.database.read goreecloud.database.write")
    response_note = {"id": "a", "title": "mine", "content": "private", "created_at": "2026-11-25T00:00:00Z"}
    with patch("gc_database.main.personal.list_personal_notes", return_value=[response_note]) as read:
        with TestClient(app) as client:
            headers = {"Authorization": "Bearer " + signed_token}
            identity = client.get("/v1/session", headers=headers)
            notes = client.get("/v1/me/notes", headers=headers)
            all_tables = client.get("/v1/tables", headers=headers)
            objects = client.get("/v1/objects", headers=headers)
            audit = client.get("/v1/audit/events", headers=headers)
            export = client.get("/v1/tables/app/catalog/export.csv", headers=headers)
            stream = client.get("/v1/events/catalog", headers=headers)
    assert identity.status_code == 200
    assert identity.json() == {"scope": "personal", "permissions": ["personal.read"]}
    assert notes.status_code == 200
    assert notes.json()["notes"] == [response_note]
    assert all(response.status_code == 401 for response in (all_tables, objects, audit, export, stream))
    read.assert_called_once_with("person-A", 25, 0)
    assert "person-A" not in identity.text


def test_shared_management_tokens_retain_scope(monkeypatch):
    configure(monkeypatch)
    monkeypatch.delenv("GC_OIDC_GLOBAL_READ_ENABLED", raising=False)
    with TestClient(app) as client:
        admin = client.get("/v1/session", headers={"Authorization": "Bearer " + "A" * 48})
        reader = client.get("/v1/session", headers={"Authorization": "Bearer " + "R" * 48})
        unauth = client.get("/v1/session")
    assert admin.json() == {"scope": "admin", "permissions": ["read", "write"]}
    assert reader.json() == {"scope": "reader", "permissions": ["read"]}
    assert unauth.status_code == 401


def test_explicit_legacy_oidc_opt_in_allows_global_read_only(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("GC_OIDC_GLOBAL_READ_ENABLED", "true")
    token = signed("person-A", "goreecloud.database.read goreecloud.database.write")
    with patch("gc_database.main.store.list_tables", return_value=[{"schema": "app", "name": "catalog"}]) as listing:
        with TestClient(app) as client:
            session = client.get("/v1/session", headers={"Authorization": "Bearer " + token})
            tables = client.get("/v1/tables", headers={"Authorization": "Bearer " + token})
            denied_write = client.post(
                "/v1/tables/app/catalog/rows",
                json={"slug": "not-allowed"},
                headers={"Authorization": "Bearer " + token},
            )
    assert session.json()["scope"] == "reader"
    assert tables.status_code == 200
    assert denied_write.status_code == 401
    listing.assert_called_once()


@pytest.mark.parametrize("raw", ["TRUE", "1", "yes", "off", " false ", "", "invalid"])
def test_invalid_global_read_setting_fails_closed(monkeypatch, raw):
    configure(monkeypatch)
    monkeypatch.setenv("GC_OIDC_GLOBAL_READ_ENABLED", raw)
    with pytest.raises(RuntimeError, match="GC_OIDC_GLOBAL_READ_ENABLED"):
        global_oidc_read_enabled()
    with pytest.raises(RuntimeError, match="GC_OIDC_GLOBAL_READ_ENABLED"):
        require_configuration()


def test_global_read_opt_in_without_oidc_configuration_is_invalid(monkeypatch):
    configure(monkeypatch)
    for key in ("GC_OIDC_ISSUER", "GC_OIDC_AUDIENCE", "GC_OIDC_JWKS_JSON"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GC_OIDC_GLOBAL_READ_ENABLED", "true")
    with pytest.raises(RuntimeError, match="requires fully configured"):
        require_configuration()
