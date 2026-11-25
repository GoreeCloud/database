"""OIDC reader adapter: real RSA signatures, strict claims and fail-closed config.

No network or real identity-provider tokens are used in these tests.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from gc_database.main import app
from gc_database.oidc import oidc_reader_authorized, oidc_settings


ISSUER = "https://id.example.test/realms/goreecloud"
AUDIENCE = "goreecloud-database"
JWKS = "https://id.example.test/realms/goreecloud/protocol/openid-connect/certs"
READ_SCOPE = "goreecloud.database.read"


@pytest.fixture
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def configure(monkeypatch):
    monkeypatch.setenv("GC_ADMIN_TOKEN", "A" * 48)
    monkeypatch.setenv("GC_READ_TOKEN", "R" * 48)
    for label in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_READ_USER", "DB_READ_PASSWORD"):
        monkeypatch.setenv(label, "dummy")
    monkeypatch.setenv("GC_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("GC_OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("GC_OIDC_JWKS_URL", JWKS)


def signed(key, **overrides):
    now = int(datetime.now(tz=timezone.utc).timestamp())
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "user-123",
        "iat": now,
        "exp": now + 900,
        "scope": READ_SCOPE,
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key-1"})


def test_real_rsa_signature_maps_only_to_reader(monkeypatch, key):
    configure(monkeypatch)
    public = SimpleNamespace(key=key.public_key())
    token = signed(key)
    with patch("gc_database.oidc._client") as client, patch(
        "gc_database.main.store.list_tables", return_value=[{"schema": "app", "name": "catalog"}]
    ) as tables:
        client.return_value.get_signing_key_from_jwt.return_value = public
        with TestClient(app) as api:
            response = api.get("/v1/session", headers={"Authorization": "Bearer " + token})
            listing = api.get("/v1/tables", headers={"Authorization": "Bearer " + token})
            rejected = api.post("/v1/tables/app/catalog/rows", json={"slug": "bad"},
                                headers={"Authorization": "Bearer " + token})
    assert response.status_code == 200
    assert response.json() == {"scope": "reader", "permissions": ["read"]}
    assert listing.status_code == 200
    assert rejected.status_code == 401
    tables.assert_called_once()
    client.assert_called_with(JWKS)


@pytest.mark.parametrize("changes", [
    {"aud": "another-api"},
    {"iss": "https://evil.example"},
    {"sub": ""},
    {"scope": "user.profile.read"},
    {"scope": "goreecloud.database.read.bad"},
    {"iat": 0, "exp": 7200},
    {"exp": 0},
    {"iat": 9999999999, "exp": 10000000000},
])
def test_invalid_oidc_claims_denied(monkeypatch, key, changes):
    configure(monkeypatch)
    token = signed(key, **changes)
    with patch("gc_database.oidc._client") as client:
        client.return_value.get_signing_key_from_jwt.return_value = SimpleNamespace(key=key.public_key())
        assert oidc_reader_authorized(token) is False


def test_invalid_signature_fails_closed(monkeypatch, key):
    configure(monkeypatch)
    another = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with patch("gc_database.oidc._client") as client:
        client.return_value.get_signing_key_from_jwt.return_value = SimpleNamespace(key=another.public_key())
        assert oidc_reader_authorized(signed(key)) is False


def test_unapproved_alg_header_and_large_jwt_never_fetch_keys(monkeypatch):
    configure(monkeypatch)
    raw = jwt.encode({"iss": ISSUER, "aud": AUDIENCE, "exp": 9999999999}, "X" * 48,
                     algorithm="HS256", headers={"kid": "untrusted"})
    with patch("gc_database.oidc._client") as client:
        assert oidc_reader_authorized(raw) is False
        assert oidc_reader_authorized("x" * 8193) is False
        client.assert_not_called()


def test_partial_oidc_settings_refused_at_startup(monkeypatch):
    monkeypatch.setenv("GC_OIDC_ISSUER", ISSUER)
    monkeypatch.delenv("GC_OIDC_AUDIENCE", raising=False)
    monkeypatch.delenv("GC_OIDC_JWKS_URL", raising=False)
    with pytest.raises(RuntimeError):
        oidc_settings()


@pytest.mark.parametrize("invalid", [
    "http://id.example.test/realms/goreecloud/certs",
    "https://evil.example/certs",
    "https://id.example.test/other/certs",
    "https://id.example.test/realms/goreecloud/certs?secret=abc",
    "https://alice:pass@id.example.test/realms/goreecloud/certs",
])
def test_jwks_url_must_share_secure_issuer_origin_and_path(monkeypatch, invalid):
    configure(monkeypatch)
    monkeypatch.setenv("GC_OIDC_JWKS_URL", invalid)
    with pytest.raises(RuntimeError):
        oidc_settings()


def test_disabled_oidc_never_attempts_fetch(monkeypatch, key):
    configure(monkeypatch)
    for label in ("GC_OIDC_ISSUER", "GC_OIDC_AUDIENCE", "GC_OIDC_JWKS_URL"):
        monkeypatch.delenv(label, raising=False)
    with patch("gc_database.oidc._client") as client:
        with TestClient(app) as api:
            read = api.get("/v1/session", headers={"Authorization": "Bearer " + "R" * 48})
            unknown = api.get("/v1/session", headers={"Authorization": "Bearer " + signed(key)})
        assert read.status_code == 200
        assert unknown.status_code == 401
        client.assert_not_called()


def _public_jwks_for_key(key, *, kid="test-key-1"):
    import json
    from jwt.utils import base64url_encode

    nums = key.public_key().public_numbers()

    def encoded(value):
        return base64url_encode(value.to_bytes((value.bit_length() + 7) // 8, "big")).decode("ascii")

    return json.dumps({"keys": [{
        "kty": "RSA", "use": "sig", "alg": "RS256", "kid": kid,
        "n": encoded(nums.n), "e": encoded(nums.e),
    }]})


def test_inline_jwks_verifies_rsa_without_any_network(monkeypatch, key):
    configure(monkeypatch)
    monkeypatch.delenv("GC_OIDC_JWKS_URL", raising=False)
    monkeypatch.setenv("GC_OIDC_JWKS_JSON", _public_jwks_for_key(key))
    with patch("gc_database.oidc._client") as fetch:
        with TestClient(app) as client:
            good = client.get("/v1/session", headers={"Authorization": "Bearer " + signed(key)})
            bad = client.get("/v1/session", headers={"Authorization": "Bearer " + signed(
                rsa.generate_private_key(public_exponent=65537, key_size=2048)
            )})
    assert good.status_code == 200
    assert good.json()["scope"] == "reader"
    assert bad.status_code == 401
    fetch.assert_not_called()


def test_inline_jwks_rejects_private_key_material_and_weak_rsa(monkeypatch, key):
    import json

    configure(monkeypatch)
    monkeypatch.delenv("GC_OIDC_JWKS_URL", raising=False)
    raw = json.loads(_public_jwks_for_key(key))
    raw["keys"][0]["d"] = "private-material"
    monkeypatch.setenv("GC_OIDC_JWKS_JSON", json.dumps(raw))
    with pytest.raises(RuntimeError):
        oidc_settings()
    weak = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    monkeypatch.setenv("GC_OIDC_JWKS_JSON", _public_jwks_for_key(weak))
    with pytest.raises(RuntimeError):
        oidc_settings()


def test_inline_jwks_requires_exclusive_source(monkeypatch, key):
    configure(monkeypatch)
    monkeypatch.setenv("GC_OIDC_JWKS_JSON", _public_jwks_for_key(key))
    with pytest.raises(RuntimeError):
        oidc_settings()


def test_inline_jwks_malformed_json_rejected_before_runtime(monkeypatch):
    configure(monkeypatch)
    monkeypatch.delenv("GC_OIDC_JWKS_URL", raising=False)
    monkeypatch.setenv("GC_OIDC_JWKS_JSON", "not-json")
    with pytest.raises(RuntimeError):
        oidc_settings()
