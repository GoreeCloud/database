"""Optional read-only OIDC verifier; no implicit admin, per-user RLS or SSO flow.

The API's default Docker network is egress-blocked. Operators can supply
trusted public JWKS JSON (recommended for this preview) without egress; an
explicit same-origin HTTPS JWKS URL is supported for separately authorized
deployments with reviewed network access. No JWT header controls a fetch URL.
"""
from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from urllib.parse import urlsplit

import jwt
from jwt import PyJWKClient, PyJWTError

READ_SCOPE = "goreecloud.database.read"
MAX_JWT_SIZE = 8192
MAX_JWKS_JSON_SIZE = 32768
MAX_TOKEN_AGE_SECONDS = 3600


def _secure_https_url(raw: str, *, allow_root: bool = False):
    parsed = urlsplit(raw)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None or parsed.password is not None
        or parsed.query or parsed.fragment
        or parsed.hostname.endswith(".")
        or not parsed.netloc
        or any(c.isspace() for c in raw)
        or (not allow_root and parsed.path in ("", "/"))
    ):
        raise RuntimeError("OIDC issuer/JWKS must be valid HTTPS URLs without credentials, queries or fragments")
    try:
        port = parsed.port or 443
    except ValueError:
        raise RuntimeError("Invalid OIDC URL port") from None
    return parsed, (parsed.hostname.lower(), port)


@lru_cache(maxsize=4)
def _public_jwks(jwks_json: str) -> dict[str, object]:
    """Accept only bounded, explicit RSA public signing keys with unique kids."""
    try:
        data = json.loads(jwks_json)
        keys = data["keys"]
        if not isinstance(keys, list) or not 1 <= len(keys) <= 16:
            raise ValueError("JWKS key count")
        output: dict[str, object] = {}
        for item in keys:
            if not isinstance(item, dict):
                raise ValueError("Not a JWK")
            kid = item.get("kid")
            if (
                item.get("kty") != "RSA"
                or item.get("alg", "RS256") != "RS256"
                or item.get("use", "sig") != "sig"
                or not isinstance(kid, str)
                or not 1 <= len(kid) <= 256
                or kid in output
                or not isinstance(item.get("n"), str)
                or not isinstance(item.get("e"), str)
                or any(private in item for private in ("d", "p", "q", "dp", "dq", "qi", "oth"))
            ):
                raise ValueError("Untrusted or private JWK")
            key = jwt.PyJWK.from_dict(item, algorithm="RS256").key
            if getattr(key, "key_size", 0) < 2048:
                raise ValueError("RSA key below 2048 bits")
            output[kid] = key
        return output
    except (ValueError, TypeError, KeyError, PyJWTError, AttributeError):
        raise RuntimeError("Invalid trusted public OIDC JWKS configuration") from None


def oidc_settings() -> tuple[str, str, str, bool] | None:
    issuer = os.environ.get("GC_OIDC_ISSUER", "").strip()
    audience = os.environ.get("GC_OIDC_AUDIENCE", "").strip()
    jwks_url = os.environ.get("GC_OIDC_JWKS_URL", "").strip()
    inline_jwks = os.environ.get("GC_OIDC_JWKS_JSON", "").strip()
    if not any((issuer, audience, jwks_url, inline_jwks)):
        return None
    if not all((issuer, audience)) or (bool(jwks_url) == bool(inline_jwks)):
        raise RuntimeError("OIDC requires issuer, audience, and exactly one trusted JWKS source")
    if len(issuer) > 2048 or not 1 <= len(audience) <= 256 or any(c.isspace() for c in audience):
        raise RuntimeError("Invalid OIDC issuer or audience")
    issuer_url, issuer_origin = _secure_https_url(issuer, allow_root=True)
    if inline_jwks:
        if len(inline_jwks) > MAX_JWKS_JSON_SIZE:
            raise RuntimeError("Trusted JWKS JSON exceeds size bound")
        _public_jwks(inline_jwks)
        return issuer, audience, inline_jwks, True
    if len(jwks_url) > 2048:
        raise RuntimeError("OIDC JWKS URL exceeds size bound")
    jwks, jwks_origin = _secure_https_url(jwks_url)
    prefix = issuer_url.path.rstrip("/") + "/"
    if (
        issuer_origin != jwks_origin
        or not jwks.path.startswith(prefix)
        or jwks.path == prefix
        or "/../" in jwks.path or "/./" in jwks.path
    ):
        raise RuntimeError("OIDC JWKS must be located under the exact issuer HTTPS origin and path")
    return issuer, audience, jwks_url, False


@lru_cache(maxsize=4)
def _client(jwks_url: str) -> PyJWKClient:
    # PyJWT >=2.15.1 fixes algorithm confusion and JWKS redirect SSRF issues.
    return PyJWKClient(jwks_url, timeout=4, cache_jwk_set=True, lifespan=300)


def oidc_reader_authorized(token: str) -> bool:
    settings = oidc_settings()
    if settings is None or len(token) > MAX_JWT_SIZE or token.count(".") != 2:
        return False
    issuer, audience, jwks_source, inline = settings
    try:
        header = jwt.get_unverified_header(token)
        # Caller-selected algorithms and URLs are always ignored.
        kid = header.get("kid")
        if (
            header.get("alg") != "RS256"
            or not isinstance(kid, str) or not 1 <= len(kid) <= 256
            or any(field in header for field in ("jku", "x5u", "x5c", "crit"))
        ):
            return False
        if inline:
            public_key = _public_jwks(jwks_source).get(kid)
            if public_key is None:
                return False
        else:
            public_key = _client(jwks_source).get_signing_key_from_jwt(token).key
            if getattr(public_key, "key_size", 0) < 2048:
                return False
        claims = jwt.decode(
            token, public_key, algorithms=["RS256"], audience=audience, issuer=issuer,
            leeway=15,
            options={"require": ["exp", "iat", "sub", "iss", "aud"], "strict_aud": True},
        )
        issued, expires = claims.get("iat"), claims.get("exp")
        subject, scopes = claims.get("sub"), claims.get("scope")
        return bool(
            type(issued) in (int, float)
            and type(expires) in (int, float)
            and 0 < expires - issued <= MAX_TOKEN_AGE_SECONDS
            and issued <= time.time() + 15
            and isinstance(subject, str) and 1 <= len(subject) <= 256
            and isinstance(scopes, str) and READ_SCOPE in scopes.split()
        )
    except (PyJWTError, ValueError, TypeError, KeyError, OSError, TimeoutError):
        return False
