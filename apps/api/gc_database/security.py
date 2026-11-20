"""Management-token authentication and request input validation."""
from __future__ import annotations
import hmac
import os
import re

from fastapi import Header, HTTPException, status

IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
SCHEMA = "app"


def require_configuration() -> str:
    token = os.environ.get("GC_ADMIN_TOKEN", "")
    if len(token) < 32 or token.startswith("REPLACE_"):
        raise RuntimeError("GC_ADMIN_TOKEN must be an unpredictable secret of >=32 characters")
    for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        if not os.environ.get(key):
            raise RuntimeError(f"{key} is required")
    return token


def require_admin(authorization: str | None = Header(default=None)) -> None:
    expected = require_configuration()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    candidate = authorization[7:]
    if not hmac.compare_digest(candidate, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")


def check_identifier(value: str) -> str:
    if not IDENTIFIER_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail="Unsupported SQL identifier")
    return value


def check_schema(schema: str) -> str:
    if schema != SCHEMA:
        raise HTTPException(status_code=404, detail="Schema not available")
    return schema
