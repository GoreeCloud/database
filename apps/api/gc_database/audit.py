"""Minimal metadata-only audit inspector; administrative GET only."""
from __future__ import annotations

from typing import Any

from .store import connection


def list_audit_events(limit: int, offset: int) -> list[dict[str, Any]]:
    """Use a read-only transaction as the non-superuser management role."""
    with connection() as db, db.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(
            "SELECT id::text AS id, source_schema, source_table, operation, occurred_at "
            "FROM gc_audit.events ORDER BY id DESC LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()
