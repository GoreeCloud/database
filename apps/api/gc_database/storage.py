"""Bounded small-object storage backed by a private PostgreSQL schema.

Intentionally not a general S3 backend; avoids writable host mounts and
never exposes blob tables through the generic /app table explorer.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from psycopg.errors import CheckViolation

from .store import connection

MAX_OBJECT_BYTES = 1_048_576
ALLOWED_MEDIA_TYPES = frozenset({
    "application/octet-stream", "text/plain", "image/png", "image/jpeg", "application/pdf",
})
FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


def check_filename(name: str) -> str:
    if not FILENAME.fullmatch(name):
        raise HTTPException(status_code=400, detail="Filename must be a safe ASCII basename (1-120 characters)")
    return name


def check_media_type(media_type: str) -> str:
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(status_code=415, detail="Content type not supported")
    return media_type


def parse_object_id(value: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Malformed object ID") from None


def save_object(filename: str, media_type: str, payload: bytes) -> dict[str, Any]:
    check_filename(filename)
    check_media_type(media_type)
    if not 1 <= len(payload) <= MAX_OBJECT_BYTES:
        raise HTTPException(status_code=413, detail="Object must be 1 byte to 1 MiB")
    digest = hashlib.sha256(payload).hexdigest()
    try:
        with connection() as db, db.cursor() as cur:
            cur.execute(
                "INSERT INTO gc_storage.objects "
                "(filename, media_type, size_bytes, sha256, contents) "
                "VALUES (%s, %s, %s, %s, %s) "
                "RETURNING id::text AS id, filename, media_type, size_bytes, sha256, created_at",
                (filename, media_type, len(payload), digest, payload),
            )
            return cur.fetchone()
    except CheckViolation as exception:
        # Only the migration's explicitly named global quota maps to 507.
        # Other constraints remain generic database errors, without SQL leakage.
        if getattr(exception.diag, "constraint_name", None) == "gc_storage_total_quota":
            raise HTTPException(status_code=507, detail="Small-object capacity limit reached") from None
        raise


def delete_object(raw_id: str, expected_sha256: str) -> None:
    """Delete exactly one matching object and checksum, never a path or range."""
    object_id = parse_object_id(raw_id)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise HTTPException(status_code=400, detail="Expected SHA-256 must be 64 lowercase hex digits")
    with connection() as db, db.cursor() as cur:
        cur.execute(
            "DELETE FROM gc_storage.objects WHERE id = %s AND sha256 = %s RETURNING id",
            (object_id, expected_sha256),
        )
        deleted = cur.fetchone()
    if deleted is None:
        raise HTTPException(status_code=404, detail="Object missing or checksum changed")


def list_objects(limit: int, offset: int) -> list[dict[str, Any]]:
    with connection(read_only=True) as db, db.cursor() as cur:
        cur.execute(
            "SELECT id::text AS id, filename, media_type, size_bytes, sha256, created_at "
            "FROM gc_storage.objects ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()


def read_object(raw_id: str) -> dict[str, Any]:
    object_id = parse_object_id(raw_id)
    with connection(read_only=True) as db, db.cursor() as cur:
        cur.execute(
            "SELECT filename, media_type, size_bytes, sha256, contents "
            "FROM gc_storage.objects WHERE id = %s",
            (object_id,),
        )
        result = cur.fetchone()
    if result is None:
        raise HTTPException(status_code=404, detail="Object not found")
    body = bytes(result["contents"])
    if len(body) != result["size_bytes"] or hashlib.sha256(body).hexdigest() != result["sha256"]:
        raise HTTPException(status_code=503, detail="Object integrity verification failed")
    return {**result, "contents": body}
