"""Management and read-only token authentication with fail-closed configuration."""
from __future__ import annotations

import hmac
import os
import re

from fastapi import Header, HTTPException, status

from .oidc import READ_SCOPE, WRITE_SCOPE, oidc_reader_authorized, oidc_settings, oidc_subject
from .rate_limits import admin_write_throttle

IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
SCHEMA = "app"


def require_configuration() -> str:
    admin = os.environ.get("GC_ADMIN_TOKEN", "")
    read = os.environ.get("GC_READ_TOKEN", "")
    if len(admin) < 32 or admin.startswith("REPLACE_"):
        raise RuntimeError("GC_ADMIN_TOKEN must be an unpredictable secret of >=32 characters")
    if len(read) < 32 or read.startswith("REPLACE_"):
        raise RuntimeError("GC_READ_TOKEN must be an unpredictable secret of >=32 characters")
    if hmac.compare_digest(admin, read):
        raise RuntimeError("Admin and read tokens must be distinct")
    for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_READ_USER", "DB_READ_PASSWORD"):
        if not os.environ.get(key):
            raise RuntimeError(f"{key} is required")
    oidc_settings()  # Fail closed on partially configured external identity.
    return admin


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer ") or len(authorization) < 9:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    return authorization[7:]


def current_scope(authorization: str | None = Header(default=None)) -> str:
    admin = require_configuration()
    read = os.environ["GC_READ_TOKEN"]
    candidate = _bearer(authorization)
    is_admin = hmac.compare_digest(candidate, admin)
    is_reader = hmac.compare_digest(candidate, read)
    if is_admin:
        return "admin"
    if is_reader:
        return "reader"
    # OIDC access tokens can ONLY receive the shared read-only capability.
    # They cannot be upgraded to admin and do not confer per-tenant RLS.
    if oidc_reader_authorized(candidate):
        return "reader"
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")


def require_admin(authorization: str | None = Header(default=None)) -> None:
    if current_scope(authorization) != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Administrator token required")
    admin_write_throttle.check()


def require_personal_read(authorization: str | None = Header(default=None)) -> str:
    """Only an explicitly scoped, signed individual OIDC token has identity."""
    require_configuration()
    subject = oidc_subject(_bearer(authorization), (READ_SCOPE,))
    if subject is None:
        raise HTTPException(status_code=401, detail="Verified personal read scope required")
    return subject


def require_personal_write(authorization: str | None = Header(default=None)) -> str:
    """Write scope applies ONLY to the private owner-isolated notes endpoint."""
    require_configuration()
    subject = oidc_subject(_bearer(authorization), (READ_SCOPE, WRITE_SCOPE))
    if subject is None:
        raise HTTPException(status_code=401, detail="Verified personal note write scope required")
    return subject


def require_admin_view(authorization: str | None = Header(default=None)) -> None:
    """Admin-only read authorization, separate from optional write throttling."""
    if current_scope(authorization) != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Administrator token required")


def require_read(authorization: str | None = Header(default=None)) -> None:
    current_scope(authorization)


def check_identifier(value: str) -> str:
    if not IDENTIFIER_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail="Unsupported SQL identifier")
    return value


def check_schema(schema: str) -> str:
    if schema != SCHEMA:
        raise HTTPException(status_code=404, detail="Schema not available")
    return schema
